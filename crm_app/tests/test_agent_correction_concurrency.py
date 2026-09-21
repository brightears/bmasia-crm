"""Opt-in MCP correction updates must compare current CRM state atomically."""
from datetime import date, datetime, timezone
import json
from decimal import Decimal
from uuid import UUID

import pytest

from crm_app.mcp import update_record
from crm_app.models import Company, Contact, Contract, Opportunity
from crm_app.serializers import ContractSerializer, ContactSerializer, OpportunitySerializer


ONE_TIME_CONTRACT_ID = '42678604-f01f-4ef2-a8c3-0c90efef0a41'
ONE_TIME_SOURCE_THREAD = '01a03892-ee6f-71d1-b590-bd53606fe2a0'
ONE_TIME_EXPECTED_VERSION = '2026-09-21T04:03:20.253356Z'


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


def _commercial_authorization(opportunity, changes):
    return json.dumps({
        'kind': 'explicit_user_commercial',
        'source_thread_id': 'test-thread',
        'record_id': str(opportunity.pk),
        'authorized_changes': changes,
    })


def _one_time_contract(company):
    contract = Contract.objects.create(
        id=UUID(ONE_TIME_CONTRACT_ID),
        company=company,
        contract_number='DRAFT-0180',
        status='Draft',
        start_date=date(2026, 9, 21),
        end_date=date(2027, 9, 20),
        value=Decimal('0.00'),
        currency='USD',
        billing_entity='BMAsia Limited',
    )
    observed = datetime.fromisoformat(
        ONE_TIME_EXPECTED_VERSION.replace('Z', '+00:00')
    ).astimezone(timezone.utc)
    Contract.objects.filter(pk=contract.pk).update(updated_at=observed)
    contract.refresh_from_db()
    record = ContractSerializer(contract).data
    return contract, record


def _one_time_contract_authorization(**overrides):
    context = {
        'source_thread_id': ONE_TIME_SOURCE_THREAD,
        'record_type': 'contract',
        'record_id': ONE_TIME_CONTRACT_ID,
        'authorized_by': 'Norbert',
        'authorized_changes': {'status': 'Cancelled'},
    }
    context.update(overrides)
    return json.dumps(context)


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
def test_exact_one_time_contract_cancellation_succeeds_then_goes_stale():
    company = Company.objects.create(
        name='One-time cancellation fixture', billing_entity='BMAsia Limited',
    )
    contract, record = _one_time_contract(company)

    result = json.loads(update_record(
        'contract',
        str(contract.pk),
        json.dumps({'status': 'Cancelled'}),
        expected_version=ONE_TIME_EXPECTED_VERSION,
        expected_values=json.dumps({'status': record['status']}),
        authorization_context=_one_time_contract_authorization(),
    ))

    contract.refresh_from_db()
    assert result['updated'] is True
    assert result['applied'] == {'status': 'Cancelled'}
    assert contract.status == 'Cancelled'
    assert contract.contract_number == 'DRAFT-0180'

    replay = json.loads(update_record(
        'contract',
        str(contract.pk),
        json.dumps({'status': 'Cancelled'}),
        expected_version=ONE_TIME_EXPECTED_VERSION,
        expected_values=json.dumps({'status': record['status']}),
        authorization_context=_one_time_contract_authorization(),
    ))
    contract.refresh_from_db()
    assert replay == {
        'updated': False,
        'id': str(contract.pk),
        'error': 'Stale expected_version; nothing was saved.',
    }
    assert contract.status == 'Cancelled'


@pytest.mark.django_db
@pytest.mark.parametrize('authorization_context', [
    '{}',
    _one_time_contract_authorization(source_thread_id='wrong-thread'),
    _one_time_contract_authorization(record_type='opportunity'),
    _one_time_contract_authorization(record_id='00000000-0000-4000-8000-000000000000'),
    _one_time_contract_authorization(authorized_by='Someone Else'),
    _one_time_contract_authorization(authorized_changes={'status': 'Sent'}),
    _one_time_contract_authorization(extra_field='drift'),
])
def test_one_time_contract_cancellation_rejects_nonexact_authorization(
    authorization_context,
):
    company = Company.objects.create(
        name='Rejected cancellation fixture', billing_entity='BMAsia Limited',
    )
    contract, record = _one_time_contract(company)

    result = json.loads(update_record(
        'contract',
        str(contract.pk),
        json.dumps({'status': 'Cancelled'}),
        expected_version=ONE_TIME_EXPECTED_VERSION,
        expected_values=json.dumps({'status': record['status']}),
        authorization_context=authorization_context,
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': False,
        'id': str(contract.pk),
        'error': 'Contract cancellation is limited to the exact authorized one-time operation.',
    }
    assert contract.status == 'Draft'


@pytest.mark.django_db
@pytest.mark.parametrize('expected_version, expected_values', [
    ('2026-09-21T04:03:20.253357Z', {'status': 'Draft'}),
    (ONE_TIME_EXPECTED_VERSION, {'status': 'Sent'}),
])
def test_one_time_contract_cancellation_rejects_nonexact_guard_inputs(
    expected_version, expected_values,
):
    company = Company.objects.create(
        name='Rejected guard fixture', billing_entity='BMAsia Limited',
    )
    contract, _ = _one_time_contract(company)

    result = json.loads(update_record(
        'contract',
        str(contract.pk),
        json.dumps({'status': 'Cancelled'}),
        expected_version=expected_version,
        expected_values=json.dumps(expected_values),
        authorization_context=_one_time_contract_authorization(),
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': False,
        'id': str(contract.pk),
        'error': 'Contract cancellation is limited to the exact authorized one-time operation.',
    }
    assert contract.status == 'Draft'


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['Sent', 'Active'])
def test_one_time_contract_authorization_cannot_launder_intermediate_status(status):
    company = Company.objects.create(
        name='Rejected status fixture', billing_entity='BMAsia Limited',
    )
    contract, record = _one_time_contract(company)

    result = json.loads(update_record(
        'contract',
        str(contract.pk),
        json.dumps({'status': status}),
        expected_version=ONE_TIME_EXPECTED_VERSION,
        expected_values=json.dumps({'status': record['status']}),
        authorization_context=_one_time_contract_authorization(),
    ))

    contract.refresh_from_db()
    assert result == {
        'updated': False,
        'id': str(contract.pk),
        'error': 'Contract cancellation is limited to the exact authorized one-time operation.',
    }
    assert contract.status == 'Draft'


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
