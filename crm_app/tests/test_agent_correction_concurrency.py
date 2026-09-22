"""Opt-in MCP correction updates must compare current CRM state atomically."""
from datetime import date
import json
from decimal import Decimal

import pytest

from crm_app.mcp import _guarded_json_value, update_record
from crm_app.models import Company, Contact, Contract, Opportunity
from crm_app.serializers import ContractSerializer, ContactSerializer, OpportunitySerializer


def _contact():
    company = Company.objects.create(
        name='Optimistic lock fixture', billing_entity='BMAsia Limited',
    )
    return Contact.objects.create(
        company=company,
        name='Correction contact',
        email='correction@example.test',
        title='Director',
        department='',
    )


def _observed(contact):
    record = ContactSerializer(contact).data
    return record['updated_at'], record


def _opportunity(company):
    return Opportunity.objects.create(
        company=company,
        name='Guarded value correction',
        stage='Quotation Sent',
        expected_value=Decimal('1140.00'),
        probability=50,
    )


def _contract(additional_signatories=None):
    company = Company.objects.create(
        name='Nested guard fixture', legal_entity_name='Nested Guard Fixture Limited',
        billing_entity='BMAsia Limited',
    )
    if additional_signatories is None:
        additional_signatories = [{
            'name': 'Existing Signer',
            'title': 'Director',
            'legal_entity_name': 'Nested Guard Fixture Limited',
            'authority': {'active': True, 'scope': ['sign', 'review'], 'expires': None},
        }]
    return Contract.objects.create(
        company=company, contract_number='DRAFT-NESTED-GUARD',
        start_date=date(2026, 9, 22), end_date=date(2027, 9, 21),
        value=Decimal('990.00'), total_value=Decimal('990.00'), status='Draft',
        additional_customer_signatories=additional_signatories,
    )


def _commercial_authorization(opportunity, changes):
    return json.dumps({
        'kind': 'explicit_user_commercial',
        'source_thread_id': 'test-thread',
        'record_id': str(opportunity.pk),
        'authorized_changes': changes,
    })


@pytest.mark.django_db
def test_guarded_update_rejects_stale_version_without_saving():
    contact = _contact()
    version, record = _observed(contact)
    contact.title = 'Changed elsewhere'
    contact.save()

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        expected_version=version,
        expected_values=json.dumps({'title': record['title']}),
    ))

    contact.refresh_from_db()
    assert result == {
        'updated': False, 'id': str(contact.pk),
        'error': 'Stale expected_version; nothing was saved.',
    }
    assert contact.title == 'Changed elsewhere'


@pytest.mark.django_db
def test_guarded_update_rejects_before_value_mismatch_and_null_coercion():
    contact = _contact()
    version, _ = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'department': 'Operations'}),
        expected_version=version,
        # Blank string is distinct from null and must not be silently coerced.
        expected_values=json.dumps({'department': None}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Expected values no longer match; nothing was saved.'
    assert contact.department == ''


@pytest.mark.django_db
def test_guarded_update_rejects_unknown_or_company_binding_fields_without_saving():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'company': str(contact.company_id)}),
        expected_version=version,
        expected_values=json.dumps({'company': str(contact.company_id)}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Guarded patch contains fields outside the approved correction scope.'
    assert contact.company_id == record['company']


@pytest.mark.django_db
def test_guarded_commercial_update_requires_exact_explicit_authorization():
    company = Company.objects.create(
        name='Opportunity authorization fixture', billing_entity='BMAsia Limited',
    )
    opportunity = _opportunity(company)
    record = OpportunitySerializer(opportunity).data
    changes = {
        'stage': 'Won',
        'expected_value': '990.00',
        'probability': 100,
    }

    result = json.loads(update_record(
        'opportunity',
        str(opportunity.pk),
        json.dumps(changes),
        expected_version=record['updated_at'],
        expected_values=json.dumps({
            'stage': record['stage'],
            'expected_value': record['expected_value'],
            'probability': record['probability'],
        }),
    ))

    opportunity.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Commercial opportunity update requires explicit authorization context.'
    assert opportunity.stage == 'Quotation Sent'
    assert str(opportunity.expected_value) == '1140.00'
    assert opportunity.probability == 50


@pytest.mark.django_db
def test_guarded_opportunity_value_and_probability_update_atomically():
    company = Company.objects.create(
        name='Opportunity correction fixture', billing_entity='BMAsia Limited',
    )
    opportunity = _opportunity(company)
    record = OpportunitySerializer(opportunity).data
    changes = {
        'stage': 'Won',
        'expected_value': '990.00',
        'probability': 100,
    }

    result = json.loads(update_record(
        'opportunity',
        str(opportunity.pk),
        json.dumps(changes),
        expected_version=record['updated_at'],
        expected_values=json.dumps({
            'stage': record['stage'],
            'expected_value': record['expected_value'],
            'probability': record['probability'],
        }),
        authorization_context=_commercial_authorization(opportunity, changes),
    ))

    opportunity.refresh_from_db()
    assert result['updated'] is True
    assert result['applied'] == {
        'stage': 'Won',
        'expected_value': '990.00',
        'probability': '100',
    }
    assert opportunity.stage == 'Won'
    assert str(opportunity.expected_value) == '990.00'
    assert opportunity.probability == 100


@pytest.mark.django_db
def test_guarded_update_saves_then_returns_readback():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        expected_version=version,
        expected_values=json.dumps({'title': record['title']}),
    ))

    contact.refresh_from_db()
    assert result == {
        'updated': True, 'id': str(contact.pk),
        'applied': {'title': 'General Manager'},
    }
    assert contact.title == 'General Manager'


@pytest.mark.django_db
def test_guarded_contract_array_update_uses_deep_equality_and_returns_json():
    contract = _contract()
    record = ContractSerializer(contract).data
    changes = [{
        'name': 'Mr. Nopparat Piyarattanayotin',
        'title': 'Authorized Director',
        'legal_entity_name': 'Nested Guard Fixture Limited',
        'authority': {
            'active': True,
            'scope': ['sign', 'review'],
            'references': [{'kind': 'poa', 'number': 'TEST-2026-01'}],
        },
    }]

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps({'additional_customer_signatories': changes}),
        expected_version=record['updated_at'],
        expected_values=json.dumps({
            'additional_customer_signatories': record['additional_customer_signatories'],
        }),
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': True,
        'id': str(contract.pk),
        'applied': {'additional_customer_signatories': changes},
    }
    assert contract.additional_customer_signatories == changes


@pytest.mark.django_db
def test_guarded_contract_all_signatory_fields_succeed_together():
    contract = _contract([])
    record = ContractSerializer(contract).data
    additional_signatories = [{
        'name': 'Authorized Signer',
        'title': 'Authorized Director',
        'legal_entity_name': 'Nested Guard Fixture Limited',
    }]
    changes = {
        'customer_signatory_name': 'Primary Signer',
        'customer_signatory_title': 'Managing Director',
        'additional_customer_signatories': additional_signatories,
    }

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps(changes),
        expected_version=record['updated_at'],
        expected_values=json.dumps({
            'customer_signatory_name': record['customer_signatory_name'],
            'customer_signatory_title': record['customer_signatory_title'],
            'additional_customer_signatories': [],
        }),
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': True,
        'id': str(contract.pk),
        'applied': changes,
    }
    assert contract.customer_signatory_name == 'Primary Signer'
    assert contract.customer_signatory_title == 'Managing Director'
    assert contract.additional_customer_signatories == additional_signatories


@pytest.mark.django_db
def test_guarded_contract_array_mismatch_rejects_without_mutation():
    contract = _contract()
    record = ContractSerializer(contract).data
    before = contract.additional_customer_signatories
    mismatched = json.loads(json.dumps(before))
    mismatched[0]['authority']['scope'] = ['review', 'sign']

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps({'additional_customer_signatories': []}),
        expected_version=record['updated_at'],
        expected_values=json.dumps({'additional_customer_signatories': mismatched}),
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': False,
        'id': str(contract.pk),
        'error': 'Expected values no longer match; nothing was saved.',
    }
    assert contract.additional_customer_signatories == before


@pytest.mark.django_db
def test_guarded_contract_nested_bool_int_mismatch_rejects_without_mutation():
    contract = _contract()
    record = ContractSerializer(contract).data
    before = contract.additional_customer_signatories
    mismatched = json.loads(json.dumps(before))
    mismatched[0]['authority']['active'] = 1

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps({'additional_customer_signatories': []}),
        expected_version=record['updated_at'],
        expected_values=json.dumps({'additional_customer_signatories': mismatched}),
    ))

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Expected values no longer match; nothing was saved.'
    assert contract.additional_customer_signatories == before


@pytest.mark.django_db
@pytest.mark.parametrize('data, expected_values', [
    (
        '{"additional_customer_signatories":[{"name":NaN}]}',
        '{"additional_customer_signatories":[]}',
    ),
    (
        '{"additional_customer_signatories":[]}',
        '{"additional_customer_signatories":[{"authority":{"limits":[Infinity]}}]}',
    ),
    (
        '{"additional_customer_signatories":[{"name":"First","name":"Second"}]}',
        '{"additional_customer_signatories":[]}',
    ),
])
def test_guarded_contract_nested_invalid_json_rejects_without_mutation(data, expected_values):
    contract = _contract()
    record = ContractSerializer(contract).data
    before = contract.additional_customer_signatories

    result = json.loads(update_record(
        'contract', str(contract.pk), data,
        expected_version=record['updated_at'], expected_values=expected_values,
    ))

    contract.refresh_from_db()
    assert result['updated'] is False
    assert contract.additional_customer_signatories == before


@pytest.mark.django_db
@pytest.mark.parametrize('key_shape', ['missing', 'extra'])
def test_guarded_contract_expected_keys_must_exactly_match_patch(key_shape):
    contract = _contract([])
    record = ContractSerializer(contract).data
    expected = {} if key_shape == 'missing' else {
        'additional_customer_signatories': [],
        'status': 'Draft',
    }

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps({'additional_customer_signatories': []}),
        expected_version=record['updated_at'], expected_values=json.dumps(expected),
    ))

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Guarded expected_values keys must exactly match patch keys.'
    assert contract.additional_customer_signatories == []


@pytest.mark.django_db
def test_guarded_contract_other_fields_remain_outside_approved_scope():
    contract = _contract([])
    record = ContractSerializer(contract).data

    result = json.loads(update_record(
        'contract', str(contract.pk),
        json.dumps({'status': 'Sent'}),
        expected_version=record['updated_at'],
        expected_values=json.dumps({'status': record['status']}),
    ))

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Guarded patch contains fields outside the approved correction scope.'
    assert contract.status == 'Draft'


@pytest.mark.parametrize('value', [
    ('tuple',),
    {'not-json'},
    {'nested': Decimal('1.00')},
    {'nested': [float('inf')]},
])
def test_guarded_json_value_rejects_non_json_and_nonfinite_python_values(value):
    assert _guarded_json_value(value) is False


@pytest.mark.django_db
def test_guarded_version_accepts_equivalent_query_timestamp_format():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        # query_data_collections renders Django datetimes with an explicit UTC
        # offset, while DRF's serializer commonly returns a trailing Z.
        expected_version=version.replace('Z', '+00:00'),
        expected_values=json.dumps({'title': record['title']}),
    ))

    assert result['updated'] is True


@pytest.mark.django_db
@pytest.mark.parametrize('data, expected_values', [
    ('{"title":"Director","title":"Other"}', '{"title":"Director"}'),
    ('{"title":NaN}', '{"title":"Director"}'),
    ('{"title":"Other"}', '{"title":"Director","title":"Other"}'),
])
def test_guarded_json_rejects_duplicate_keys_and_nonfinite_values(data, expected_values):
    contact = _contact()
    version, _ = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), data,
        expected_version=version, expected_values=expected_values,
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert contact.title == 'Director'


@pytest.mark.django_db
def test_legacy_three_argument_update_remains_available():
    contact = _contact()

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is True
    assert result['applied'] == {'title': 'General Manager'}
    assert contact.title == 'General Manager'
