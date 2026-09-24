"""Only a verified, version-locked already-sent contract can be marked Sent."""
from datetime import date, datetime
from decimal import Decimal
import json
from unittest import mock
from uuid import UUID, uuid4

import pytest

import crm_app.mcp as crm_mcp
from crm_app.mcp import update_record
from crm_app.models import Company, Contract, DocumentSequence
from crm_app.serializers import ContractSerializer


FINAL_NUMBER = 'HK-CT261015'
PATCH = {'status': 'Sent', 'sent_date': '2026-09-09'}
PREMIER_ID = UUID('1941a3bc-9d3b-4161-9d9e-7ff07677f34b')


@pytest.fixture(autouse=True)
def synthetic_operator_receipt(monkeypatch):
    # Production has no digest until the real protected receipt is issued.
    monkeypatch.setitem(crm_mcp._PREMIER_SEND_BOOKKEEPING, 'verified_receipt_sha256', 'a' * 64)


def _contract():
    company = Company.objects.create(name='Send bookkeeping fixture', billing_entity='BMAsia Limited')
    contract = Contract.objects.create(
        id=PREMIER_ID,
        company=company, contract_number=FINAL_NUMBER,
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('990.00'), total_value=Decimal('990.00'), status='Draft',
    )
    Contract.objects.filter(pk=contract.pk).update(
        updated_at=datetime.fromisoformat('2026-09-08T05:03:57.672476+00:00')
    )
    contract.refresh_from_db()
    return contract


def _authorization(contract, patch=PATCH, **overrides):
    context = {
        'kind': 'verified_contract_send_bookkeeping',
        'source_reference': 'theo:approved-proposal-and-provider-receipt',
        'record_id': str(contract.pk),
        'authorized_changes': patch,
        'verified_receipt_sha256': 'a' * 64,
        'contract_number': FINAL_NUMBER,
    }
    context.update(overrides)
    return json.dumps(context)


def _update(contract, record, patch=PATCH, *, before=None, version=None, authorization=None):
    return json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=version or record['updated_at'],
        expected_values=json.dumps(before if before is not None else {
            key: record[key] for key in patch
        }),
        authorization_context=authorization or _authorization(contract, patch),
    ))


@pytest.mark.django_db
def test_bookkeeping_changes_only_status_date_and_preserves_final_number():
    contract = _contract()
    record = ContractSerializer(contract).data
    with mock.patch.object(DocumentSequence, 'get_next_number', side_effect=AssertionError('new number')), \
         mock.patch('crm_app.services.email_service.EmailService.send_contract_email',
                    side_effect=AssertionError('duplicate email')):
        result = _update(contract, record)

    contract.refresh_from_db()
    assert result == {
        'updated': True, 'id': str(contract.pk), 'applied': PATCH,
        'contract_number': FINAL_NUMBER,
    }
    assert contract.status == 'Sent'
    assert contract.sent_date == date(2026, 9, 9)
    assert contract.contract_number == FINAL_NUMBER
    assert contract.value == Decimal('990.00')


@pytest.mark.django_db
def test_bookkeeping_replay_is_stale_and_does_not_write_twice():
    contract = _contract()
    record = ContractSerializer(contract).data
    first = _update(contract, record)
    second = _update(contract, record)
    assert first['updated'] is True
    assert second['updated'] is False
    assert second['error'] == 'Contract send bookkeeping requires the same Draft/null record and final number; nothing was saved.'


@pytest.mark.django_db
@pytest.mark.parametrize('case', [
    'missing', 'kind', 'record', 'patch', 'digest', 'source', 'number',
])
def test_bookkeeping_rejects_unbound_or_unverified_context(case):
    contract = _contract()
    record = ContractSerializer(contract).data
    contexts = {
        'missing': '{}',
        'kind': _authorization(contract, kind='explicit_user_contract_service_items'),
        'record': _authorization(contract, record_id='wrong'),
        'patch': _authorization(contract, patch={'status': 'Sent'}),
        'digest': _authorization(contract, verified_receipt_sha256='not-a-hash'),
        'source': _authorization(contract, source_reference=' '),
        'number': _authorization(contract, contract_number='DRAFT-0153'),
    }
    result = _update(contract, record, authorization=contexts[case])
    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error']
    assert contract.status == 'Draft'
    assert contract.sent_date is None


@pytest.mark.django_db
@pytest.mark.parametrize('patch', [
    {'status': 'Sent'},
    {'sent_date': '2026-09-09'},
    {'status': 'Active', 'sent_date': '2026-09-09'},
    {'status': 'Sent', 'sent_date': '2026-02-30'},
    {'status': 'Sent', 'sent_date': '2026-9-9'},
    {'status': 'Sent', 'sent_date': '2026-09-09', 'value': 1},
])
def test_bookkeeping_rejects_malformed_or_mixed_patch(patch):
    contract = _contract()
    record = ContractSerializer(contract).data
    result = _update(contract, record, patch)
    contract.refresh_from_db()
    assert result['updated'] is False
    assert contract.status == 'Draft'
    assert contract.sent_date is None


@pytest.mark.django_db
def test_bookkeeping_requires_exact_before_values_and_fresh_version():
    contract = _contract()
    record = ContractSerializer(contract).data
    bad_before = _update(contract, record, before={'status': 'Sent', 'sent_date': None})
    contract.notes = 'Concurrent edit'
    contract.save()
    stale = _update(contract, record)
    assert bad_before['updated'] is False
    assert stale['error'] == 'Stale expected_version; nothing was saved.'


@pytest.mark.django_db
def test_bookkeeping_rejects_non_draft_existing_date_and_number_mismatch():
    contract = _contract()
    record = ContractSerializer(contract).data
    wrong_number = _update(contract, record, authorization=_authorization(
        contract, contract_number='HK-CT261016'))
    contract.sent_date = date(2026, 9, 8)
    contract.save()
    with_date = _update(contract, ContractSerializer(contract).data, before={
        'status': 'Draft', 'sent_date': None,
    })
    contract.sent_date = None
    contract.status = 'Active'
    contract.save()
    non_draft = _update(contract, ContractSerializer(contract).data, before={
        'status': 'Draft', 'sent_date': None,
    })
    assert wrong_number['updated'] is False
    assert with_date['updated'] is False
    assert non_draft['updated'] is False


@pytest.mark.django_db
def test_bookkeeping_rejects_draft_number_before_save():
    contract = _contract()
    contract.contract_number = 'DRAFT-0153'
    contract.save()
    record = ContractSerializer(contract).data
    result = _update(contract, record)
    contract.refresh_from_db()
    assert result['updated'] is False
    assert contract.status == 'Draft'
    assert contract.contract_number == 'DRAFT-0153'


@pytest.mark.django_db
def test_bookkeeping_rejects_other_record_even_with_valid_context():
    contract = _contract()
    contract.pk = uuid4()
    contract.contract_number = 'HK-CT261016'
    contract.save(force_insert=True)
    record = ContractSerializer(contract).data
    result = _update(contract, record)
    assert result['updated'] is False
    assert result['error'] == 'Contract send bookkeeping is not the approved Premier recovery.'


@pytest.mark.django_db
def test_bookkeeping_rejects_unconfigured_operator_receipt(monkeypatch):
    contract = _contract()
    record = ContractSerializer(contract).data
    monkeypatch.setitem(crm_mcp._PREMIER_SEND_BOOKKEEPING, 'verified_receipt_sha256', None)
    result = _update(contract, record)
    assert result['updated'] is False
    assert result['error'] == 'Contract send bookkeeping operator receipt is not configured.'


@pytest.mark.django_db
def test_bookkeeping_requires_exact_original_version_instant():
    contract = _contract()
    record = ContractSerializer(contract).data
    result = _update(contract, record, version='2026-09-08T05:03:57.672477+00:00')
    assert result['updated'] is False
    assert result['error'] == 'Contract send bookkeeping is not the approved Premier recovery.'
