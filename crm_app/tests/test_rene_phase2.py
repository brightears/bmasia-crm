import base64
import copy
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.test import override_settings
from mcp_server import mcp_server
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from crm_app.models import (
    AuditLog,
    Company,
    Contract,
    ContractDocument,
    ContractLineItem,
    ReneCiraRequest,
    RenePreparedContract,
    ReneRenewalPolicy,
    User,
)
from crm_app.mcp import RenePhase2MCPToolset
from crm_app.rene_auth import RenePhase2MCPCredential
from crm_app.rene_mcp_server import rene_phase2_mcp_server
from crm_app.services.rene_phase2 import (
    _prepared_live_state,
    _receipt_binding,
    _render_contract_pdf,
    _verify_rendered_contract_terms,
    RenePhase2BoundError,
    RenePhase2Error,
    execute_rene_request,
    lookup_rene_receipt,
    materialize_rene_wire_response,
)
from crm_app.services.rene_phase2_common import canonical_sha256, contract_version
from crm_app.services.renewal_book_service import build_renewal_book
from crm_app.services.rene_phase2_transport import MAX_CIRA_REQUEST_BYTES


TOKEN = 'rene-read-token-0123456789'
TOKEN_SHA = hashlib.sha256(TOKEN.encode('ascii')).hexdigest()
MCP_TOKEN = 'rene-phase2-mcp-test-secret-0123456789'
MCP_TOKEN_SHA = hashlib.sha256(MCP_TOKEN.encode('ascii')).hexdigest()
PDF = b'%PDF-1.4\n%%EOF'


def _mcp_post(client, path, payload, authorization=None):
    extra = {'HTTP_ACCEPT': 'application/json, text/event-stream'}
    if authorization is not None:
        extra['HTTP_AUTHORIZATION'] = authorization
    return client.post(path, payload, format='json', **extra)


def _scoped_mcp_request(user):
    return SimpleNamespace(
        user=user,
        auth=RenePhase2MCPCredential(
            token_fingerprint_sha256=MCP_TOKEN_SHA,
            user_id=str(user.id),
        ),
    )


def _envelope(operation, target, version, intent, request_id):
    data = {
        'schema': 'bmasia.cira.rene.v1',
        'requesting_agent': 'rene',
        'collection': 'contract',
        'operation': operation,
        'target_contract_id': str(target),
        'expected_version': version,
        'intent': intent,
    }
    digest = canonical_sha256(data)
    return {
        'schema': 'bmasia.cira.rene.v1',
        'from': 'rene',
        'requesting_agent': 'rene',
        'verb': operation,
        'collection': 'contract',
        'request_id': request_id,
        'request_key': f'rene:{operation}:{target}:{digest}',
        'intent_sha256': digest,
        'id': str(target),
        'expected_version': version,
        'data': data,
    }


def _validate(proposed, request_id):
    return _envelope(
        'validate_only',
        proposed['id'],
        proposed['expected_version'],
        {
            'target_operation': proposed['verb'],
            'target_request_key': proposed['request_key'],
            'target_intent_sha256': proposed['intent_sha256'],
            'target_envelope': proposed,
            'must_not_mutate': True,
        },
        request_id,
    )


def _lookup_for(original, lookup_request_id):
    return {
        'schema': 'bmasia.cira.rene.receipt-lookup.v1',
        'from': 'rene',
        'requesting_agent': 'rene',
        'operation': 'receipt_lookup',
        'lookup_request_id': lookup_request_id,
        'original_request_id': original['request_id'],
        'original_request_key': original['request_key'],
        'original_intent_sha256': original['intent_sha256'],
        'original_operation': original['verb'],
        'must_not_mutate': True,
    }


def _company(name='Exact Rene Hotel', billing_entity='BMAsia Limited'):
    return Company.objects.create(
        name=name,
        country='Thailand',
        billing_entity=billing_entity,
    )


def _contract(
    company,
    end_date=date(2026, 10, 31),
    *,
    contract_number='HK-CT26001',
    currency='USD',
    status='Active',
):
    return Contract.objects.create(
        company=company,
        contract_number=contract_number,
        contract_type='Annual',
        status=status,
        start_date=date(2025, 11, 1),
        end_date=end_date,
        value=Decimal('1200.00'),
        currency=currency,
        renewal_period_months=12,
        is_active=True,
    )


def _policy(post_send=True):
    return ReneRenewalPolicy.objects.create(
        scope_key='global',
        review_status='reviewed',
        start_policy_id='nikki-boundary-start-v1',
        start_rule='NEXT_DAY',
        start_evidence_sha256='a' * 64,
        start_source_ref='chat:spaces-renewals:thread-start',
        start_source_label='Nikki reviewed start boundary',
        start_revision=1,
        end_policy_id='nikki-boundary-end-v1',
        end_rule='INCLUSIVE_MINUS_ONE',
        end_evidence_sha256='b' * 64,
        end_source_ref='chat:spaces-renewals:thread-end',
        end_source_label='Nikki reviewed end boundary',
        end_revision=1,
        contract_number_policy_id='pom-contract-number-v1',
        contract_number_rule='RESERVE_UNUSED_DOCUMENT_SEQUENCE_BEFORE_PDF',
        contract_number_evidence_sha256='c' * 64,
        contract_number_source_ref='crm:document-sequence-policy-v1',
        contract_number_source_label='Reviewed final contract number policy',
        contract_number_revision=1,
        post_send_state_semantics_reviewed=post_send,
        post_send_policy_id='nikki-prepared-to-sent-v1' if post_send else '',
        post_send_rule=(
            'PREPARED_TO_SENT_SOURCE_UNCHANGED' if post_send else ''
        ),
        post_send_evidence_sha256='f' * 64 if post_send else '',
        post_send_source_ref=(
            'chat:spaces-renewals:thread-post-send' if post_send else ''
        ),
        post_send_source_label=(
            'Nikki reviewed prepared contract Sent semantics' if post_send else ''
        ),
        post_send_revision=1,
    )


def _signed_document(contract):
    return ContractDocument.objects.create(
        contract=contract,
        document_type='generated',
        title='Signed official contract',
        file=SimpleUploadedFile('signed-source.pdf', PDF, content_type='application/pdf'),
        is_official=True,
        is_signed=True,
        signed_date=date(2025, 10, 15),
    )


def _inspect_request(contract, request_id='inspect-1', evidence_revision=1):
    return _envelope(
        'inspect_renewal_source',
        contract.id,
        contract_version(contract),
        {
            'target_company_id': str(contract.company_id),
            'document_selection': 'unique_official_signed_document',
            'required_document_count': 1,
            'required_document_flags': {'is_official': True, 'is_signed': True},
            'require_reviewed_renewal_start_policy': True,
            'require_reviewed_renewal_end_policy': True,
            'require_pricing_structure_evidence': True,
            'evidence_revision': evidence_revision,
            'return': [
                'contract_id', 'company_id', 'version', 'contract_updated_at',
                'evidence_revision', 'document', 'terms', 'term_duration',
                'renewal_start_policy', 'renewal_end_policy', 'pricing_structure',
            ],
            'must_not_mutate': True,
        },
        request_id,
    )


def _prepare_request(
    contract,
    inspect_request,
    inspect_receipt,
    *,
    request_id='prepare-1',
    price='1325.00',
):
    source = inspect_receipt['source_inspection']
    start = {
        key: source['renewal_start_policy'][key]
        for key in (
            'policy_id', 'rule', 'evidence_sha256', 'source_ref', 'source_label',
            'revision', 'next_start_date',
        )
    }
    end = {
        key: source['renewal_end_policy'][key]
        for key in (
            'policy_id', 'rule', 'evidence_sha256', 'source_ref', 'source_label',
            'revision', 'next_end_date',
        )
    }
    return _envelope(
        'prepare_renewal_contract',
        contract.id,
        contract_version(contract),
        {
            'source_contract_id': str(contract.id),
            'source_company_id': str(contract.company_id),
            'source_contract_pdf_sha256': source['document']['pdf_sha256'],
            'source_inspection': {
                'request_id': inspect_request['request_id'],
                'request_key': inspect_request['request_key'],
                'intent_sha256': inspect_request['intent_sha256'],
                'binding_sha256': source['binding_sha256'],
                'document_id': source['document']['document_id'],
                'filename': source['document']['filename'],
                'contract_updated_at': source['contract_updated_at'],
                'evidence_revision': source['evidence_revision'],
                'terms': source['terms'],
                'term_duration': source['term_duration'],
                'renewal_start_policy': start,
                'renewal_end_policy': end,
                'pricing_structure': source['pricing_structure'],
            },
            'desired_filename': 'Exact_Rene_Hotel_Renewal.pdf',
            'renewal_terms': {
                'start_date': start['next_start_date'],
                'end_date': end['next_end_date'],
                'price': price,
                'currency': 'USD',
            },
            'sheet_evidence': {
                'spreadsheet_id': 'sheet-international',
                'tab': 'Oct-2026',
                'row': 7,
                'sha256': 'd' * 64,
            },
            'contract_number_requirements': {
                'must_be_final_before_pdf': True,
                'must_be_embedded_in_pdf': True,
                'must_remain_unchanged_on_sent': True,
                'require_reviewed_policy': True,
            },
            'delivery': 'return_pdf_for_nikki_review',
        },
        request_id,
    )


def _verify_request(prepared, prepare, prepare_receipt, request_id='verify-1'):
    prepared_map = prepare_receipt['prepared_contract']
    artifact = prepare_receipt['artifact']
    return _envelope(
        'verify_prepared_contract',
        prepared.id,
        contract_version(prepared),
        {
            'verification_nonce': request_id,
            'prepare_receipt': {
                'request_id': prepare['request_id'],
                'request_key': prepare['request_key'],
                'intent_sha256': prepare['intent_sha256'],
                'receipt_binding_sha256': _receipt_binding(prepare_receipt),
            },
            'prepared_contract': prepared_map,
            'required_live_state': _prepared_live_state(prepared_map),
            'artifact': {
                'filename': artifact['filename'],
                'sha256': artifact['sha256'],
                'size_bytes': artifact['size_bytes'],
            },
            'return_portable_pdf': True,
            'must_not_mutate': True,
        },
        request_id,
    )


@pytest.mark.django_db
@override_settings(
    RENE_RENEWAL_BOOK_TOKEN_SHA256=TOKEN_SHA,
    RENE_RENEWAL_BOOK_TOKEN_EXPIRES_AT='2099-01-01T00:00:00Z',
)
def test_exact_rene_capability_and_renewal_book_identity():
    contract = _contract(_company())
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
    capability = client.get('/api/v1/auth/token-capabilities/')
    assert capability.status_code == 200
    assert capability.json() == {
        'schema': 'bmasia.crm.token-capabilities.v1',
        'subject': 'rene',
        'token_fingerprint_sha256': TOKEN_SHA,
        'permissions': ['contracts.renewal_book.read'],
        'allowed_methods': ['GET'],
        'allowed_paths': ['/api/v1/contracts/renewal-book/'],
        'expires_at': '2099-01-01T00:00:00Z',
    }
    book = client.get('/api/v1/contracts/renewal-book/?year=2026&month=10&currency=USD')
    assert book.status_code == 200
    body = book.json()
    assert body['totals_by_product'] == {
        'Other': {'contracts': 1, 'zones': 0, 'value': 1200.0}
    }
    assert body['totals_by_status'] == {'Active': 1}
    row = body['rows'][0]
    assert row['contract_id'] == str(contract.id)
    assert row['company_id'] == str(contract.company_id)
    assert row['version'] == contract_version(contract)
    assert row['updated_at'].endswith('Z')
    client.credentials(HTTP_AUTHORIZATION='Bearer wrong-token-0123456789')
    assert client.get('/api/v1/contracts/renewal-book/?year=2026&month=10').status_code == 401

    # The existing route remains the ContractViewSet action: normal CRM JWT
    # users still reach it, while the new Rene token grants no other scope.
    user = User.objects.create_user(username='existing-reader', password='unused')
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    assert client.get('/api/v1/contracts/renewal-book/?year=2026&month=10').status_code == 200


@pytest.mark.django_db
def test_renewal_book_service_has_stable_optimistic_identity():
    contract = _contract(_company())
    row = build_renewal_book(2026, 10, 'USD')['rows'][0]
    assert {key: row[key] for key in ('contract_id', 'company_id', 'version')} == {
        'contract_id': str(contract.id),
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
    }


@pytest.mark.django_db
@override_settings(
    RENE_RENEWAL_BOOK_TOKEN_SHA256=TOKEN_SHA,
    RENE_RENEWAL_BOOK_TOKEN_EXPIRES_AT='2099-01-01T00:00:00Z',
)
def test_renewal_book_exact_referenced_undated_rows_are_bounded_and_ordered():
    first = _contract(
        _company('Requested Null Hotel'),
        None,
        contract_number='HK-CT26011',
    )
    second = _contract(
        _company('Second Requested Null Hotel'),
        None,
        contract_number='HK-CT26015',
    )
    unrequested = _contract(
        _company('Unrequested Null Hotel'),
        None,
        contract_number='HK-CT26012',
    )
    dated = _contract(
        _company('Requested Dated Hotel'),
        contract_number='HK-CT26013',
    )
    wrong_currency = _contract(
        _company('Requested THB Hotel'),
        None,
        contract_number='TH-CT26014',
        currency='THB',
    )
    missing = str(uuid4())
    requested = [
        str(dated.id), str(second.id), missing, str(first.id), str(wrong_currency.id)
    ]

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
    plain = client.get('/api/v1/contracts/renewal-book/?year=2026&month=10&currency=USD')
    assert plain.status_code == 200
    assert 'requested_contract_ids' not in plain.json()
    assert 'referenced_undated_rows' not in plain.json()

    suffix = ''.join(f'&contract_id={contract_id}' for contract_id in requested)
    response = client.get(
        '/api/v1/contracts/renewal-book/?year=2026&month=10&currency=USD' + suffix
    )
    assert response.status_code == 200
    body = response.json()
    assert body['requested_contract_ids'] == requested
    # The optional undated lane adds fields without changing the long-standing
    # nested product totals or scalar status-count contracts.
    assert body['totals_by_product'] == {
        'Other': {'contracts': 1, 'zones': 0, 'value': 1200.0}
    }
    assert body['totals_by_status'] == {'Active': 1}
    rows = body['referenced_undated_rows']
    assert [row['contract_id'] for row in rows] == [str(second.id), str(first.id)]
    assert rows[1]['company_id'] == str(first.company_id)
    assert rows[1]['end_date'] is None
    assert rows[1]['version'] == contract_version(first)
    assert str(unrequested.id) not in {row['contract_id'] for row in rows}

    duplicate = client.get(
        '/api/v1/contracts/renewal-book/?year=2026&month=10'
        f'&contract_id={first.id}&contract_id={first.id}'
    )
    assert duplicate.status_code == 400
    noncanonical = client.get(
        '/api/v1/contracts/renewal-book/?year=2026&month=10'
        f'&contract_id={str(first.id).upper()}'
    )
    assert noncanonical.status_code == 400
    with pytest.raises(ValueError, match='at most 100'):
        build_renewal_book(2026, 10, referenced_contract_ids=[
            str(uuid4()) for _ in range(101)
        ])


@pytest.mark.django_db
def test_sanitized_renewal_book_fixtures_match_server_shapes():
    fixture_root = Path(__file__).resolve().parents[2] / 'docs' / 'fixtures'
    monthly = json.loads(
        (fixture_root / 'rene-renewal-book-monthly-v1.json').read_text('utf-8')
    )
    requested = json.loads(
        (fixture_root / 'rene-renewal-book-requested-undated-v1.json').read_text('utf-8')
    )

    dated = _contract(_company('Fixture Shape Hotel'))
    live_monthly = build_renewal_book(2026, 10, 'USD')
    assert set(monthly) == set(live_monthly)
    assert set(monthly['rows'][0]) == set(live_monthly['rows'][0])

    undated = _contract(
        _company('Fixture Shape Undated Hotel'),
        None,
        contract_number='HK-CT26016',
    )
    live_requested = build_renewal_book(
        2026, 10, 'USD', [str(undated.id), str(uuid4())]
    )
    assert set(requested) == set(live_requested)
    assert set(requested['referenced_undated_rows'][0]) == set(
        live_requested['referenced_undated_rows'][0]
    )
    for body in (monthly, requested):
        assert all(
            set(total) == {'contracts', 'zones', 'value'}
            for total in body['totals_by_product'].values()
        )
        assert all(
            isinstance(count, int) and not isinstance(count, bool)
            for count in body['totals_by_status'].values()
        )
    assert dated.id is not None


@pytest.mark.django_db
def test_inspect_is_non_mutating_and_requires_unique_official_signed_pdf(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    contract = _contract(_company())
    _policy()
    _signed_document(contract)
    before = (contract_version(contract), contract.status, contract.contract_number)
    request = _inspect_request(contract)
    receipt = execute_rene_request(request)
    contract.refresh_from_db()
    assert (contract_version(contract), contract.status, contract.contract_number) == before
    assert receipt['outcome'] == 'inspected'
    source = receipt['source_inspection']
    assert source['document_count'] == 1
    assert source['document']['pdf_sha256'] == hashlib.sha256(PDF).hexdigest()
    assert source['renewal_start_policy']['next_start_date'] == '2026-11-01'
    assert source['renewal_end_policy']['next_end_date'] == '2027-10-31'
    assert source['pricing_structure']['mapping_status'] == 'UNIQUE_SIMPLE_TOTAL'
    assert execute_rene_request(request) == receipt


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('field', 'identifier'),
    (
        ('start_policy_id', 'nikki-draft-v2'),
        ('start_policy_id', 'nikki.pending.v2'),
        ('end_policy_id', 'nikki/temp/v2'),
        ('end_policy_id', 'nikki:temporary:v2'),
        ('contract_number_policy_id', 'pom+unknown+v2'),
        ('contract_number_policy_id', 'pom_placeholder_v2'),
        ('contract_number_policy_id', 'pom/unresolved/v2'),
    ),
)
def test_temporary_policy_identifier_components_are_terminal_before_mutation(
    tmp_path, settings, field, identifier
):
    settings.MEDIA_ROOT = tmp_path
    contract = _contract(_company(f'Temporary Policy {field}'))
    policy = _policy()
    setattr(policy, field, identifier)
    policy.save(update_fields=[field])
    _signed_document(contract)
    before = (Contract.objects.count(), contract_version(contract), contract.status)
    request = _inspect_request(contract, request_id=f'inspect-{field}-{identifier}')

    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(request, crm_mcp_invoked=True)

    assert caught.value.code == 'NEEDS_CLARIFICATION'
    assert caught.value.receipt['outcome'] == 'rejected_terminal'
    contract.refresh_from_db()
    assert (Contract.objects.count(), contract_version(contract), contract.status) == before
    assert not Contract.objects.filter(renewed_from=contract).exists()
    assert RenePreparedContract.objects.count() == 0


@pytest.mark.django_db
def test_policy_identifier_reserved_substrings_remain_reviewed(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    contract = _contract(_company('Reviewed Policy Substrings'))
    policy = _policy()
    policy.start_policy_id = 'nikki-drafting-v2'
    policy.end_policy_id = 'nikki-pendingreview-v2'
    policy.contract_number_policy_id = 'pom-attempt-temporarypolicy-v2'
    policy.save(
        update_fields=[
            'start_policy_id',
            'end_policy_id',
            'contract_number_policy_id',
        ]
    )
    _signed_document(contract)

    receipt = execute_rene_request(
        _inspect_request(contract, request_id='inspect-reviewed-policy-substrings')
    )

    assert receipt['outcome'] == 'inspected'


@pytest.mark.django_db
def test_target_id_must_be_canonical_uuid_before_request_admission():
    contract = _contract(_company())
    valid = _inspect_request(contract)
    bad_ids = ('not-a-uuid', str(contract.id).upper(), contract.id.hex)

    for index, bad_id in enumerate(bad_ids, start=1):
        request = _envelope(
            valid['verb'],
            bad_id,
            valid['expected_version'],
            copy.deepcopy(valid['data']['intent']),
            f'inspect-invalid-uuid-{index}',
        )
        with pytest.raises(RenePhase2Error) as caught:
            execute_rene_request(request)
        assert caught.value.code == 'INVALID_SCHEMA'

    assert ReneCiraRequest.objects.count() == 0


@pytest.mark.django_db
def test_prepare_rejects_noncanonical_or_unstorable_money_before_number_reservation(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    source = _contract(_company())
    source.tax_rate = Decimal('7.00')
    source.save(update_fields=['tax_rate', 'updated_at'])
    _policy()
    _signed_document(source)
    inspect = _inspect_request(source, request_id='inspect-money-bounds')
    inspected = execute_rene_request(inspect)
    original_contract_count = Contract.objects.count()
    invalid_prices = (
        '-1.00',
        '0.00',
        '1.001',
        '01.00',
        '1E+2',
        '10000000000.00',
        # Base value fits Decimal(12,2), but its derived tax/total do not.
        '9999999999.99',
    )

    for index, price in enumerate(invalid_prices, start=1):
        prepare = _prepare_request(
            source,
            inspect,
            inspected,
            request_id=f'prepare-invalid-money-{index}',
            price=price,
        )
        with pytest.raises(RenePhase2BoundError) as caught:
            execute_rene_request(_validate(prepare, f'validate-invalid-money-{index}'))
        assert caught.value.code == 'INVALID_SCHEMA'

    assert Contract.objects.count() == original_contract_count
    assert not Contract.objects.filter(renewed_from=source).exists()
    assert RenePreparedContract.objects.count() == 0


@pytest.mark.django_db
def test_prepare_fails_closed_when_source_already_has_any_renewal_successor(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    company = _company()
    source = _contract(company)
    _policy()
    _signed_document(source)
    inspect = _inspect_request(source, request_id='inspect-existing-successor')
    inspected = execute_rene_request(inspect)
    prepare = _prepare_request(
        source,
        inspect,
        inspected,
        request_id='prepare-existing-successor',
    )
    execute_rene_request(_validate(prepare, 'validate-before-existing-successor'))
    successor = _contract(
        company,
        end_date=date(2027, 10, 31),
        contract_number='HK-CT26998',
        status='Draft',
    )
    successor.renewed_from = source
    successor.save(update_fields=['renewed_from', 'updated_at'])

    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(prepare)
    assert caught.value.code == 'SOURCE_LIFECYCLE_CHANGED'
    terminal_lookup = lookup_rene_receipt(
        _lookup_for(prepare, 'lookup-existing-successor-terminal')
    )
    assert terminal_lookup['status'] == 'rejected_terminal'
    assert materialize_rene_wire_response(terminal_lookup) == terminal_lookup

    revised = _prepare_request(
        source,
        inspect,
        inspected,
        request_id='prepare-existing-successor-revised',
        price='1326.00',
    )
    with pytest.raises(RenePhase2BoundError) as validation_caught:
        execute_rene_request(
            _validate(revised, 'validate-existing-successor-revised')
        )
    assert validation_caught.value.code == 'SOURCE_LIFECYCLE_CHANGED'
    assert list(Contract.objects.filter(renewed_from=source)) == [successor]
    assert RenePreparedContract.objects.count() == 0


@pytest.mark.django_db
def test_failed_exact_request_is_terminal_and_new_evidence_revision_can_succeed(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    contract = _contract(_company())
    _signed_document(contract)
    request = _inspect_request(contract, request_id='inspect-policy-reopen')

    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(request, crm_mcp_invoked=True)
    assert caught.value.code == 'NEEDS_CLARIFICATION'
    failed = ReneCiraRequest.objects.get(request_id=request['request_id'])
    assert failed.state == 'failed'
    terminal = caught.value.receipt
    assert terminal == failed.receipt
    assert terminal['schema'] == 'bmasia.cira.rene.crm-terminal-rejection.v1'
    assert terminal['outcome'] == 'rejected_terminal'
    assert terminal['request_id'] == request['request_id']
    assert terminal['request_key'] == request['request_key']
    assert terminal['intent_sha256'] == request['intent_sha256']
    assert terminal['operation'] == request['verb']
    assert terminal['effect'] == {
        'boundary': 'crm_atomic_rollback',
        'crm_mcp_invoked': True,
        'transaction_committed': False,
        'effect_persisted': False,
        'request_state': 'failed',
    }

    _policy()
    with pytest.raises(RenePhase2BoundError) as replayed:
        execute_rene_request(copy.deepcopy(request), crm_mcp_invoked=True)
    assert replayed.value.receipt == terminal
    failed.refresh_from_db()
    assert failed.state == 'failed' and failed.receipt == terminal

    lookup = lookup_rene_receipt(_lookup_for(request, 'lookup-terminal-policy'))
    assert lookup['status'] == 'rejected_terminal'
    assert lookup['receipt'] == terminal

    corrupt = copy.deepcopy(terminal)
    corrupt['effect']['request_state'] = 'accepted'
    failed.receipt = corrupt
    failed.save(update_fields=['receipt', 'updated_at'])
    uncertain_lookup = lookup_rene_receipt(
        _lookup_for(request, 'corrupt-terminal-lookup')
    )
    assert uncertain_lookup['status'] == 'pending'
    assert uncertain_lookup['receipt'] is None
    failed.receipt = terminal
    failed.save(update_fields=['receipt', 'updated_at'])

    revised = _inspect_request(
        contract,
        request_id='inspect-policy-evidence-r2',
        evidence_revision=2,
    )
    receipt = execute_rene_request(revised, crm_mcp_invoked=True)
    assert receipt['outcome'] == 'inspected'
    assert receipt['source_inspection']['evidence_revision'] == 2

    changed = copy.deepcopy(request)
    changed['data']['intent']['target_company_id'] = str(uuid4())
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(changed)
    assert caught.value.code == 'HASH_MISMATCH'


@pytest.mark.django_db
def test_internal_contract_renderer_returns_pdf_without_api_or_audit_mutation():
    contract = _contract(_company())
    before = contract_version(contract)
    pdf = _render_contract_pdf(contract)
    visible = _verify_rendered_contract_terms(pdf, contract)
    assert contract.contract_number in visible
    assert '01 November 2025' in visible
    assert '31 October 2026' in visible
    assert 'USD' in visible and '1,200.00' in visible

    contract.contract_number = 'HK-CT26999'
    with pytest.raises(RenePhase2Error) as caught:
        _verify_rendered_contract_terms(pdf, contract)
    assert caught.value.code == 'PDF_RENDER_BLOCKED'

    contract.refresh_from_db()
    assert pdf.startswith(b'%PDF-') and pdf.rstrip().endswith(b'%%EOF')
    assert contract_version(contract) == before
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_dedicated_cira_mcp_tool_requires_exact_principal_and_strict_json(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    cira = User.objects.create_user(username='exact-cira-mcp')
    other = User.objects.create_user(username='other-mcp-agent')
    contract = _contract(_company())
    _policy()
    _signed_document(contract)
    request = _inspect_request(contract, request_id='inspect-via-mcp')

    settings.CIRA_RENE_MCP_TOKEN_SHA256 = MCP_TOKEN_SHA
    settings.CIRA_RENE_MCP_USER_ID = ''
    disabled_tool = RenePhase2MCPToolset(request=_scoped_mcp_request(cira))
    disabled = json.loads(disabled_tool.rene_phase2_request(json.dumps(request)))
    assert disabled['error']['code'] == 'FORBIDDEN'

    settings.CIRA_RENE_MCP_USER_ID = str(cira.id)
    assert 'rene_phase2_request' not in mcp_server._tool_manager._tools
    registered = rene_phase2_mcp_server._tool_manager._tools[
        'rene_phase2_request'
    ]
    assert callable(registered.fn)
    assert registered.parameters == {
        'properties': {'request_json': {'title': 'Request Json', 'type': 'string'}},
        'required': ['request_json'],
        'title': 'rene_phase2_requestArguments',
        'type': 'object',
    }
    denied_tool = RenePhase2MCPToolset(request=_scoped_mcp_request(other))
    denied = json.loads(denied_tool.rene_phase2_request(json.dumps(request)))
    assert denied['schema'] == 'bmasia.cira.rene.crm-uncertain.v1'
    assert denied['outcome'] == 'uncertain'
    assert denied['error']['code'] == 'FORBIDDEN'
    assert ReneCiraRequest.objects.count() == 0

    cira.is_active = False
    cira.save(update_fields=['is_active'])
    inactive_tool = RenePhase2MCPToolset(request=_scoped_mcp_request(cira))
    inactive = json.loads(inactive_tool.rene_phase2_request(json.dumps(request)))
    assert inactive['error']['code'] == 'FORBIDDEN'
    cira.is_active = True
    cira.save(update_fields=['is_active'])

    tool = RenePhase2MCPToolset(request=_scoped_mcp_request(cira))
    duplicate = json.loads(
        tool.rene_phase2_request('{"schema":"first","schema":"second"}')
    )
    assert duplicate['schema'] == 'bmasia.cira.rene.crm-uncertain.v1'
    assert duplicate['error']['code'] == 'INVALID_JSON'
    assert duplicate['effect']['request_state'] == 'unknown'
    oversized = json.loads(
        tool.rene_phase2_request(
            '{"padding":"' + ('x' * MAX_CIRA_REQUEST_BYTES) + '"}'
        )
    )
    assert oversized['error']['code'] == 'REQUEST_TOO_LARGE'
    assert ReneCiraRequest.objects.count() == 0
    assert APIClient().post('/api/v1/cira/rene-phase2/', request, format='json').status_code == 404

    receipt = json.loads(tool.rene_phase2_request(json.dumps(request)))
    assert receipt['schema'] == 'bmasia.cira.rene.v1'
    assert receipt['outcome'] == 'inspected'
    assert receipt['source_inspection']['evidence_revision'] == 1


@pytest.mark.django_db
def test_dedicated_rene_mcp_handler_has_scoped_registry_and_auth(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    cira = User.objects.create_user(username='handler-cira-mcp')
    generic_token = Token.objects.create(user=cira)
    settings.CIRA_RENE_MCP_TOKEN_SHA256 = MCP_TOKEN_SHA
    settings.CIRA_RENE_MCP_USER_ID = str(cira.id)
    contract = _contract(_company())
    _policy()
    _signed_document(contract)
    request = _inspect_request(contract, request_id='inspect-via-handler')
    client = APIClient()

    listed = _mcp_post(
        client,
        '/mcp/rene-phase2/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}},
        authorization=f'Rene {MCP_TOKEN}',
    )
    assert listed.status_code == 200
    names = {tool['name'] for tool in listed.json()['result']['tools']}
    assert names == {'get_server_instructions', 'rene_phase2_request'}
    assert names.isdisjoint(
        {
            'query_data_collections',
            'create_record',
            'update_record',
            'delete_record',
            'convert_quote_to_contract',
            'generate_contract_pdf',
            'generate_proforma_pdf',
            'generate_quote_pdf',
            'generate_invoice_pdf',
        }
    )

    called = _mcp_post(
        client,
        '/mcp/rene-phase2/',
        {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {
                'name': 'rene_phase2_request',
                'arguments': {'request_json': json.dumps(request)},
            },
        },
        authorization=f'Rene {MCP_TOKEN}',
    )
    assert called.status_code == 200
    receipt = json.loads(called.json()['result']['content'][0]['text'])
    assert receipt['schema'] == 'bmasia.cira.rene.v1'
    assert receipt['request_id'] == request['request_id']
    assert receipt['outcome'] == 'inspected'

    global_list = _mcp_post(
        client,
        '/mcp/',
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list', 'params': {}},
        authorization=f'Token {generic_token.key}',
    )
    assert global_list.status_code == 200
    global_names = {
        tool['name'] for tool in global_list.json()['result']['tools']
    }
    assert 'rene_phase2_request' not in global_names
    assert {'create_record', 'update_record', 'delete_record'} <= global_names

    assert _mcp_post(
        client,
        '/mcp/',
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list', 'params': {}},
        authorization=f'Rene {MCP_TOKEN}',
    ).status_code == 401
    assert _mcp_post(
        client,
        '/mcp/',
        {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/list', 'params': {}},
        authorization=f'Token {MCP_TOKEN}',
    ).status_code == 401
    before = Contract.objects.count()
    rest = client.post(
        '/api/v1/contracts/',
        {},
        format='json',
        HTTP_AUTHORIZATION=f'Rene {MCP_TOKEN}',
    )
    assert rest.status_code == 401
    assert Contract.objects.count() == before
    assert client.post(
        '/api/v1/contracts/',
        {},
        format='json',
        HTTP_AUTHORIZATION=f'Token {MCP_TOKEN}',
    ).status_code == 401
    assert Contract.objects.count() == before
    assert _mcp_post(
        client,
        '/mcp/rene-phase2/',
        {'jsonrpc': '2.0', 'id': 6, 'method': 'tools/list', 'params': {}},
        authorization=f'Token {generic_token.key}',
    ).status_code == 401
    assert _mcp_post(
        client,
        f'/mcp/rene-phase2/?token={generic_token.key}',
        {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/list', 'params': {}},
    ).status_code == 401


@pytest.mark.django_db
def test_scoped_mcp_materializes_one_stored_pdf_for_direct_duplicate_and_lookup(
    tmp_path, settings, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path
    cira = User.objects.create_user(username='artifact-cira-mcp')
    settings.CIRA_RENE_MCP_TOKEN_SHA256 = MCP_TOKEN_SHA
    settings.CIRA_RENE_MCP_USER_ID = str(cira.id)
    source = _contract(_company())
    _policy()
    _signed_document(source)
    inspect = _inspect_request(source, request_id='inspect-wire-artifact')
    inspected = execute_rene_request(inspect)
    prepare = _prepare_request(
        source,
        inspect,
        inspected,
        request_id='prepare-wire-artifact',
    )
    execute_rene_request(_validate(prepare, 'validate-prepare-wire-artifact'))
    monkeypatch.setattr(
        'crm_app.services.rene_phase2._render_contract_pdf', lambda contract: PDF
    )
    client = APIClient()

    def wire_call(request, rpc_id):
        response = _mcp_post(
            client,
            '/mcp/rene-phase2/',
            {
                'jsonrpc': '2.0',
                'id': rpc_id,
                'method': 'tools/call',
                'params': {
                    'name': 'rene_phase2_request',
                    'arguments': {'request_json': json.dumps(request)},
                },
            },
            authorization=f'Rene {MCP_TOKEN}',
        )
        assert response.status_code == 200
        return json.loads(response.json()['result']['content'][0]['text'])

    prepared_wire = wire_call(prepare, 20)
    expected_base64 = base64.b64encode(PDF).decode('ascii')
    assert prepared_wire['artifact']['content_base64'] == expected_base64
    prepare_journal = ReneCiraRequest.objects.get(request_id=prepare['request_id'])
    assert 'content_base64' not in json.dumps(prepare_journal.receipt)
    assert set(prepare_journal.receipt['artifact']) == {
        'filename', 'sha256', 'size_bytes',
    }
    assert bytes(RenePreparedContract.objects.get().pdf_content) == PDF

    monkeypatch.setattr(
        'crm_app.services.rene_phase2._render_contract_pdf',
        lambda contract: (_ for _ in ()).throw(AssertionError('must not re-render')),
    )
    assert wire_call(prepare, 21) == prepared_wire
    prepare_lookup = wire_call(
        _lookup_for(prepare, 'lookup-prepare-wire-artifact'), 22
    )
    assert prepare_lookup['status'] == 'found'
    assert prepare_lookup['receipt'] == prepared_wire

    prepared = Contract.objects.get(
        pk=prepared_wire['prepared_contract']['contract_id']
    )
    verify = _verify_request(
        prepared,
        prepare,
        prepared_wire,
        request_id='verify-wire-artifact',
    )
    verified_wire = wire_call(verify, 23)
    assert verified_wire['artifact']['content_base64'] == expected_base64
    verify_journal = ReneCiraRequest.objects.get(request_id=verify['request_id'])
    assert 'content_base64' not in json.dumps(verify_journal.receipt)
    assert RenePreparedContract.objects.count() == 1
    assert wire_call(verify, 24) == verified_wire
    verify_lookup = wire_call(
        _lookup_for(verify, 'lookup-verify-wire-artifact'), 25
    )
    assert verify_lookup['receipt'] == verified_wire

    metadata = RenePreparedContract.objects.get(contract=prepared)
    duplicate_contract = _contract(
        source.company,
        end_date=date(2027, 10, 31),
        contract_number='HK-CT26997',
        status='Draft',
    )
    duplicate_values = {
        field.attname: getattr(metadata, field.attname)
        for field in RenePreparedContract._meta.concrete_fields
        if field.name not in {
            'id', 'created_at', 'updated_at', 'contract', 'source_contract',
        }
    }
    duplicate_values.update(
        {
            'prepare_request_id': 'db-constraint-prepare-request',
            'prepare_request_key': 'db-constraint-prepare-key',
            'prepare_intent_sha256': '9' * 64,
        }
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RenePreparedContract.objects.create(
                contract=duplicate_contract,
                source_contract=source,
                **duplicate_values,
            )
    assert RenePreparedContract.objects.count() == 1

    prepared.status = 'Sent'
    prepared.save(update_fields=['status', 'updated_at'])
    metadata.state = 'Sent'
    metadata.save(update_fields=['state', 'updated_at'])
    sent_prepare_lookup = wire_call(
        _lookup_for(prepare, 'lookup-prepare-wire-artifact-sent'), 26
    )
    sent_verify_lookup = wire_call(
        _lookup_for(verify, 'lookup-verify-wire-artifact-sent'), 27
    )
    assert sent_prepare_lookup['receipt'] == prepared_wire
    assert sent_verify_lookup['receipt'] == verified_wire


@pytest.mark.django_db
def test_dedicated_rene_mcp_handler_fails_closed_for_bad_configuration(settings):
    cira = User.objects.create_user(username='handler-config-cira')
    client = APIClient()
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
    configurations = (
        ('', str(cira.id)),
        ('f' * 63, str(cira.id)),
        (MCP_TOKEN_SHA, ''),
        (MCP_TOKEN_SHA, 'not-a-uuid'),
        (MCP_TOKEN_SHA, str(uuid4())),
    )
    for fingerprint, user_id in configurations:
        settings.CIRA_RENE_MCP_TOKEN_SHA256 = fingerprint
        settings.CIRA_RENE_MCP_USER_ID = user_id
        denied = _mcp_post(
            client,
            '/mcp/rene-phase2/',
            payload,
            authorization=f'Rene {MCP_TOKEN}',
        )
        assert denied.status_code == 401
        assert denied['WWW-Authenticate'] == 'Rene'

    settings.CIRA_RENE_MCP_TOKEN_SHA256 = MCP_TOKEN_SHA
    settings.CIRA_RENE_MCP_USER_ID = str(cira.id)
    assert _mcp_post(
        client,
        '/mcp/rene-phase2/',
        payload,
        authorization='Rene wrong-but-long-enough-secret-0123456789',
    ).status_code == 401
    assert _mcp_post(
        client,
        '/mcp/rene-phase2/',
        payload,
        authorization='Rene short',
    ).status_code == 401
    cira.is_active = False
    cira.save(update_fields=['is_active'])
    assert _mcp_post(
        client,
        '/mcp/rene-phase2/',
        payload,
        authorization=f'Rene {MCP_TOKEN}',
    ).status_code == 401


@pytest.mark.django_db
def test_cira_mcp_terminal_rejection_is_bound_lookup_only_and_never_replayed(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    cira = User.objects.create_user(username='terminal-cira-mcp')
    settings.CIRA_RENE_MCP_TOKEN_SHA256 = MCP_TOKEN_SHA
    settings.CIRA_RENE_MCP_USER_ID = str(cira.id)
    tool = RenePhase2MCPToolset(request=_scoped_mcp_request(cira))
    contract = _contract(_company())
    _signed_document(contract)
    request = _inspect_request(contract, request_id='mcp-terminal-r1')
    before = (
        contract_version(contract),
        contract.status,
        contract.contract_number,
        Contract.objects.count(),
        RenePreparedContract.objects.count(),
    )

    terminal = json.loads(tool.rene_phase2_request(json.dumps(request)))
    assert terminal['schema'] == 'bmasia.cira.rene.crm-terminal-rejection.v1'
    assert terminal['outcome'] == 'rejected_terminal'
    assert {
        key: terminal[key]
        for key in (
            'request_id', 'request_key', 'intent_sha256', 'operation',
        )
    } == {
        'request_id': request['request_id'],
        'request_key': request['request_key'],
        'intent_sha256': request['intent_sha256'],
        'operation': request['verb'],
    }
    assert terminal['effect'] == {
        'boundary': 'crm_atomic_rollback',
        'crm_mcp_invoked': True,
        'transaction_committed': False,
        'effect_persisted': False,
        'request_state': 'failed',
    }
    journal = ReneCiraRequest.objects.get(request_id=request['request_id'])
    assert journal.state == 'failed' and journal.receipt == terminal
    contract.refresh_from_db()
    assert (
        contract_version(contract),
        contract.status,
        contract.contract_number,
        Contract.objects.count(),
        RenePreparedContract.objects.count(),
    ) == before

    _policy()
    assert json.loads(tool.rene_phase2_request(json.dumps(request))) == terminal
    assert ReneCiraRequest.objects.get(pk=journal.pk).state == 'failed'

    lookup = json.loads(
        tool.rene_phase2_request(json.dumps(_lookup_for(request, 'mcp-terminal-lookup')))
    )
    assert lookup['status'] == 'rejected_terminal'
    assert lookup['receipt'] == terminal

    revised = _inspect_request(
        contract, request_id='mcp-terminal-r2', evidence_revision=2
    )
    inspected = json.loads(tool.rene_phase2_request(json.dumps(revised)))
    assert inspected['outcome'] == 'inspected'
    assert inspected['source_inspection']['evidence_revision'] == 2


@pytest.mark.django_db
def test_fill_blank_date_requires_exact_validation_and_changes_only_end_date():
    contract = _contract(_company(), end_date=None)
    version = contract_version(contract)
    fill_intent = {
        'target_company_id': str(contract.company_id),
        'crm_before': {
            'contract_id': str(contract.id),
            'company_id': str(contract.company_id),
            'version': version,
            'end_date': None,
        },
        'sheet_evidence': {
            'spreadsheet_id': 'sheet-international',
            'tab': 'Oct-2026',
            'row': 9,
            'column': 'E',
            'value': '2026-10-31',
            'sha256': 'e' * 64,
        },
        'mutation': {'field': 'end_date', 'from': None, 'to': '2026-10-31'},
    }
    unvalidated_intent = {
        **fill_intent,
        'sheet_evidence': {**fill_intent['sheet_evidence'], 'row': 8},
    }
    unvalidated = _envelope(
        'fill_blank_renewal_date',
        contract.id,
        version,
        unvalidated_intent,
        'fill-unvalidated',
    )
    with pytest.raises(Exception, match='validate_only'):
        execute_rene_request(unvalidated)
    fill = _envelope(
        'fill_blank_renewal_date', contract.id, version, fill_intent, 'fill-2'
    )
    validation = _validate(fill, 'validate-fill-2')
    validated = execute_rene_request(validation)
    assert validated['before'] == validated['after']
    receipt = execute_rene_request(fill)
    contract.refresh_from_db()
    assert receipt['before']['end_date'] is None
    assert receipt['after']['end_date'] == '2026-10-31'
    assert receipt['before']['version'] != receipt['after']['version']
    assert contract.end_date == date(2026, 10, 31)
    lookup = lookup_rene_receipt(
        {
            'schema': 'bmasia.cira.rene.receipt-lookup.v1',
            'from': 'rene',
            'requesting_agent': 'rene',
            'operation': 'receipt_lookup',
            'lookup_request_id': 'lookup-fill-2',
            'original_request_id': fill['request_id'],
            'original_request_key': fill['request_key'],
            'original_intent_sha256': fill['intent_sha256'],
            'original_operation': fill['verb'],
            'must_not_mutate': True,
        }
    )
    assert lookup['status'] == 'found'
    assert lookup['receipt'] == receipt


@pytest.mark.django_db
def test_prepare_verify_and_record_sent_preserve_source_and_final_number(
    tmp_path, settings, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path
    source = _contract(_company())
    _policy(post_send=True)
    _signed_document(source)
    inspect_request = _inspect_request(source)
    inspect_receipt = execute_rene_request(inspect_request)
    prepare = _prepare_request(source, inspect_request, inspect_receipt)
    execute_rene_request(_validate(prepare, 'validate-prepare-1'))
    monkeypatch.setattr(
        'crm_app.services.rene_phase2._render_contract_pdf', lambda contract: PDF
    )
    source_before = (contract_version(source), source.status, source.contract_number)
    prepare_receipt = execute_rene_request(prepare)
    source.refresh_from_db()
    assert (contract_version(source), source.status, source.contract_number) == source_before
    prepared_map = prepare_receipt['prepared_contract']
    prepared = Contract.objects.get(pk=prepared_map['contract_id'])
    final_number = prepared.contract_number
    assert prepared.status == 'Draft'
    assert final_number.startswith('HK-CT') and not final_number.startswith('DRAFT-')
    metadata = RenePreparedContract.objects.get(contract=prepared)
    assert metadata.state == 'ready_for_review'
    assert bytes(metadata.pdf_content) == PDF
    assert metadata.contract_number_policy_rule == (
        'RESERVE_UNUSED_DOCUMENT_SEQUENCE_BEFORE_PDF'
    )

    artifact = prepare_receipt['artifact']
    verify = _verify_request(prepared, prepare, prepare_receipt)
    verify_receipt = execute_rene_request(verify)
    assert verify_receipt['before'] == verify_receipt['after']
    gmail = {
        'action_id': 'renew-action-1',
        'revision': 1,
        'draft_sha256': '1' * 64,
        'gmail_message_id': 'gmail-message-1',
        'gmail_thread_id': 'gmail-thread-1',
        'gmail_internal_date': '1780000000000',
        'rfc_message_id': '<rene-renew-1@bmasiamusic.com>',
        'sent_at': '2026-05-28T20:26:40Z',
        'authenticated_mailbox': 'norbert@bmasiamusic.com',
        'visible_from': 'nikki.h@bmasiamusic.com',
        'to': ['client@example.com'],
        'cc': [],
        'subject_sha256': '2' * 64,
        'plain_body_sha256': '3' * 64,
        'html_body_sha256': '4' * 64,
        'attachment': {
            'filename': artifact['filename'],
            'sha256': artifact['sha256'],
            'size_bytes': artifact['size_bytes'],
        },
        'reconciliation': 'EXACT_GMAIL_SENT',
    }
    gmail_hash = canonical_sha256(gmail)
    record = _envelope(
        'record_prepared_contract_sent',
        prepared.id,
        contract_version(prepared),
        {
            'prepared_verification': {
                'request_id': verify['request_id'],
                'request_key': verify['request_key'],
                'intent_sha256': verify['intent_sha256'],
                'receipt_binding_sha256': _receipt_binding(verify_receipt),
            },
            'prepared_contract': prepared_map,
            'gmail_sent_evidence': gmail,
            'gmail_sent_evidence_sha256': gmail_hash,
            'mutation': {
                'field': 'state',
                'from': 'ready_for_review',
                'to': 'Sent',
                'contract_number_must_remain': final_number,
                'source_contract_must_not_change': {
                    'contract_id': prepared_map['source_contract_id'],
                    'version': prepared_map['source_contract_version'],
                    'updated_at': prepared_map['source_contract_updated_at'],
                    'status': prepared_map['source_contract_status'],
                },
            },
        },
        'record-sent-1',
    )
    execute_rene_request(_validate(record, 'validate-record-sent-1'))
    record_receipt = execute_rene_request(record)
    prepared.refresh_from_db()
    source.refresh_from_db()
    metadata.refresh_from_db()
    assert prepared.status == 'Sent'
    assert prepared.contract_number == final_number
    assert metadata.state == 'Sent'
    assert metadata.post_send_policy_rule == 'PREPARED_TO_SENT_SOURCE_UNCHANGED'
    assert metadata.post_send_policy_id == 'nikki-prepared-to-sent-v1'
    assert metadata.post_send_policy_evidence_sha256 == 'f' * 64
    assert record_receipt['before']['state'] == 'ready_for_review'
    assert record_receipt['after']['state'] == 'Sent'
    assert record_receipt['before']['version'] != record_receipt['after']['version']
    assert (contract_version(source), source.status, source.contract_number) == source_before
    assert ReneCiraRequest.objects.filter(state='succeeded').count() == 6


@pytest.mark.django_db
def test_live_verify_holds_when_signed_source_document_changes(
    tmp_path, settings, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path
    source = _contract(_company())
    _policy()
    document = _signed_document(source)
    inspect = _inspect_request(source, request_id='inspect-source-change')
    inspected = execute_rene_request(inspect)
    prepare = _prepare_request(source, inspect, inspected)
    prepare['request_id'] = 'prepare-source-change'
    # request_id is outside the intent hash/key; keep the content-derived key.
    execute_rene_request(_validate(prepare, 'validate-prepare-source-change'))
    monkeypatch.setattr(
        'crm_app.services.rene_phase2._render_contract_pdf', lambda contract: PDF
    )
    prepared_receipt = execute_rene_request(prepare)
    prepared = Contract.objects.get(
        pk=prepared_receipt['prepared_contract']['contract_id']
    )
    changed_pdf = b'%PDF-1.4\nchanged source\n%%EOF'
    document.file.save(
        'changed-signed-source.pdf',
        SimpleUploadedFile(
            'changed-signed-source.pdf', changed_pdf, content_type='application/pdf'
        ),
        save=True,
    )
    verify = _verify_request(
        prepared, prepare, prepared_receipt, request_id='verify-source-change'
    )
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(verify)
    assert caught.value.code == 'EVIDENCE_CHANGED'
    assert RenePreparedContract.objects.get(contract=prepared).state == 'ready_for_review'


@pytest.mark.django_db
def test_content_key_with_new_request_id_is_non_replayable_identity_collision():
    contract = _contract(_company(), end_date=None)
    version = contract_version(contract)
    intent = {
        'target_company_id': str(contract.company_id),
        'crm_before': {
            'contract_id': str(contract.id),
            'company_id': str(contract.company_id),
            'version': version,
            'end_date': None,
        },
        'sheet_evidence': {
            'spreadsheet_id': 'sheet-international',
            'tab': 'Oct-2026',
            'row': 12,
            'column': 'E',
            'value': '2026-10-31',
            'sha256': '8' * 64,
        },
        'mutation': {'field': 'end_date', 'from': None, 'to': '2026-10-31'},
    }
    fill = _envelope('fill_blank_renewal_date', contract.id, version, intent, 'fill-original')
    execute_rene_request(_validate(fill, 'validate-fill-original'))
    original = execute_rene_request(fill)
    original_journal = ReneCiraRequest.objects.get(request_id=fill['request_id'])
    contract.refresh_from_db()
    after_original = (
        contract.end_date,
        contract_version(contract),
        ReneCiraRequest.objects.filter(operation='fill_blank_renewal_date').count(),
    )
    reconciled = copy.deepcopy(fill)
    reconciled['request_id'] = 'fill-reconciled-with-new-id'
    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(reconciled, crm_mcp_invoked=True)
    bound = caught.value.receipt
    assert caught.value.code == 'REQUEST_KEY_IDENTITY_MISMATCH'
    assert bound['schema'] == 'bmasia.cira.rene.crm-bound-error.v1'
    assert bound['outcome'] == 'existing_request_identity'
    assert bound['request_id'] == reconciled['request_id']
    assert bound['request_key'] == reconciled['request_key']
    assert bound['effect'] == {
        'boundary': 'crm_request_journal',
        'crm_mcp_invoked': True,
        'transaction_committed': None,
        'effect_persisted': None,
        'request_state': 'succeeded',
    }
    assert 'before' not in bound and 'after' not in bound
    assert original['request_id'] == 'fill-original'
    assert ReneCiraRequest.objects.get(pk=original_journal.pk).receipt == original
    contract.refresh_from_db()
    assert (
        contract.end_date,
        contract_version(contract),
        ReneCiraRequest.objects.filter(operation='fill_blank_renewal_date').count(),
    ) == after_original


@pytest.mark.django_db
def test_request_identity_and_hash_tampering_fail_closed(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    first = _contract(_company('First Collision Hotel'), contract_number='HK-CT26021')
    second = _contract(_company('Second Collision Hotel'), contract_number='HK-CT26022')
    _policy()
    _signed_document(first)
    _signed_document(second)
    request = _inspect_request(first, request_id='fixed-request-id')
    execute_rene_request(request)

    collision = _inspect_request(second, request_id='fixed-request-id')
    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(collision)
    assert caught.value.code == 'REQUEST_ID_COLLISION'
    assert caught.value.receipt['schema'] == 'bmasia.cira.rene.crm-bound-error.v1'
    assert caught.value.receipt['outcome'] == 'collision'
    assert caught.value.receipt['request_id'] == collision['request_id']
    assert caught.value.receipt['request_key'] == collision['request_key']

    tampered = copy.deepcopy(_inspect_request(first, request_id='tampered-hash'))
    tampered['data']['intent']['target_company_id'] = str(second.company_id)
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(tampered)
    assert caught.value.code == 'HASH_MISMATCH'

    wrong_caller = copy.deepcopy(_inspect_request(first, request_id='wrong-caller'))
    wrong_caller['from'] = 'another-agent'
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(wrong_caller)
    assert caught.value.code == 'FORBIDDEN'

    generic = _envelope(
        'delete', first.id, contract_version(first), {'must_not_mutate': True}, 'delete-1'
    )
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(generic)
    assert caught.value.code == 'FORBIDDEN'

    accepted = _inspect_request(second, request_id='accepted-uncertain')
    ReneCiraRequest.objects.create(
        request_id=accepted['request_id'],
        request_key=accepted['request_key'],
        intent_sha256=accepted['intent_sha256'],
        operation=accepted['verb'],
        envelope=accepted,
        canonical_envelope_sha256=canonical_sha256(accepted),
        state='accepted',
    )
    with pytest.raises(RenePhase2BoundError) as caught:
        execute_rene_request(accepted)
    assert caught.value.code == 'REQUEST_PENDING'
    assert caught.value.receipt['outcome'] == 'accepted_or_unknown'
    assert caught.value.receipt['effect']['request_state'] == 'accepted'
    assert caught.value.receipt['effect']['effect_persisted'] is None
    assert ReneCiraRequest.objects.get(request_id='accepted-uncertain').state == 'accepted'


@pytest.mark.django_db
def test_inspection_holds_on_missing_or_ambiguous_source_and_structured_pricing(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    contract = _contract(_company())
    inspect = _inspect_request(contract, request_id='inspect-evidence-r1')
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(inspect)
    assert caught.value.code == 'NEEDS_CLARIFICATION'

    _policy()
    inspect = _inspect_request(
        contract, request_id='inspect-evidence-r2', evidence_revision=2
    )
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(inspect)
    assert caught.value.code == 'NEEDS_CLARIFICATION'

    first = _signed_document(contract)
    second = _signed_document(contract)
    inspect = _inspect_request(
        contract, request_id='inspect-evidence-r3', evidence_revision=3
    )
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(inspect)
    assert caught.value.code == 'NEEDS_CLARIFICATION'
    second.delete()

    ContractLineItem.objects.create(
        contract=contract,
        product_service='Structured plan',
        quantity=1,
        unit_price=Decimal('1200.00'),
        line_total=Decimal('1200.00'),
    )
    inspect = _inspect_request(
        contract, request_id='inspect-evidence-r4', evidence_revision=4
    )
    receipt = execute_rene_request(inspect)
    pricing = receipt['source_inspection']['pricing_structure']
    assert pricing['kind'] == 'LINE_ITEMS'
    assert pricing['mapping_status'] == 'NEEDS_CLARIFICATION'
    prepare = _prepare_request(contract, inspect, receipt)
    with pytest.raises(RenePhase2Error) as caught:
        execute_rene_request(_validate(prepare, 'validate-structured-prepare'))
    assert caught.value.code == 'NEEDS_CLARIFICATION'
    assert Contract.objects.filter(renewed_from=contract).count() == 0
    assert first.pk is not None
    assert ReneCiraRequest.objects.filter(state='failed').count() == 4
    assert ReneCiraRequest.objects.filter(state='succeeded').count() == 1


@pytest.mark.django_db
def test_policy_admin_revisions_are_monotonic_across_review_state_changes():
    from crm_app.admin import ReneRenewalPolicyAdminForm

    policy = _policy()
    data = model_to_dict(policy)
    data['start_source_label'] = 'Changed reviewed start evidence'
    stale = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert not stale.is_valid()
    assert 'start_revision' in stale.errors

    data['start_revision'] = 2
    revised = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert revised.is_valid(), revised.errors
    revised.save()

    # Moving out of reviewed state cannot open a same-revision edit bypass.
    data = model_to_dict(policy)
    data['review_status'] = 'pending'
    pending = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert pending.is_valid(), pending.errors
    pending.save()
    data = model_to_dict(policy)
    data['end_source_label'] = 'Changed while policy is pending'
    stale_pending = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert not stale_pending.is_valid()
    assert 'end_revision' in stale_pending.errors

    data = model_to_dict(policy)
    data['start_revision'] = 1
    decreased = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert not decreased.is_valid()
    assert 'start_revision' in decreased.errors

    data = model_to_dict(policy)
    data['post_send_state_semantics_reviewed'] = False
    stale_post_send = ReneRenewalPolicyAdminForm(data=data, instance=policy)
    assert not stale_post_send.is_valid()
    assert 'post_send_revision' in stale_post_send.errors
