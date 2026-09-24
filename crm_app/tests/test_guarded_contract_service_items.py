"""Only a source-bound, version-locked Draft can replace custom service items."""
from datetime import date
from decimal import Decimal
import json

import pytest

from crm_app.mcp import update_record
from crm_app.models import Company, Contract
from crm_app.serializers import ContractSerializer


def _contract():
    company = Company.objects.create(
        name='Service-item guard fixture', billing_entity='BMAsia Limited',
    )
    return Contract.objects.create(
        company=company, contract_number='DRAFT-SERVICE-GUARD',
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('990.00'), total_value=Decimal('990.00'), status='Draft',
        custom_service_items=[{'name': 'Existing service', 'description': 'Existing scope'}],
    )


def _patch():
    return {'custom_service_items': [
        {'name': 'Revised service', 'description': 'Agreed scope'},
        {'name': 'Second service', 'description': 'Additional agreed scope'},
    ]}


def _authorization(contract, patch, **overrides):
    context = {
        'kind': 'explicit_user_contract_service_items',
        'source_reference': 'test-theo-user-instruction',
        'record_id': str(contract.pk),
        'authorized_changes': patch,
    }
    context.update(overrides)
    return json.dumps(context)


def _update(contract, patch, record, *, authorization=None, before=None, version=None):
    return json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=version or record['updated_at'],
        expected_values=json.dumps(before if before is not None else {
            key: record[key] for key in patch
        }),
        authorization_context=authorization or _authorization(contract, patch),
    ))


@pytest.mark.django_db
def test_guarded_service_items_save_only_the_authorized_array_and_read_back():
    contract = _contract()
    record = ContractSerializer(contract).data
    patch = _patch()

    result = _update(contract, patch, record)

    contract.refresh_from_db()
    assert result == {
        'updated': True, 'id': str(contract.pk), 'applied': patch,
    }
    assert contract.custom_service_items == patch['custom_service_items']
    assert contract.status == 'Draft'
    assert contract.value == Decimal('990.00')


@pytest.mark.django_db
def test_guarded_service_items_replayed_lock_does_not_write_twice():
    contract = _contract()
    record = ContractSerializer(contract).data
    patch = _patch()

    first = _update(contract, patch, record)
    second = _update(contract, patch, record)

    contract.refresh_from_db()
    assert first['updated'] is True
    assert second == {
        'updated': False, 'id': str(contract.pk),
        'error': 'Stale expected_version; nothing was saved.',
    }
    assert contract.custom_service_items == patch['custom_service_items']


@pytest.mark.django_db
@pytest.mark.parametrize('case', [
    'missing', 'wrong_kind', 'wrong_record', 'wrong_patch', 'blank_source',
])
def test_guarded_service_items_require_exact_source_record_and_patch(case):
    contract = _contract()
    record = ContractSerializer(contract).data
    patch = _patch()
    contexts = {
        'missing': '{}',
        'wrong_kind': _authorization(contract, patch, kind='unrelated'),
        'wrong_record': _authorization(contract, patch, record_id='other-record'),
        'wrong_patch': _authorization(contract, {'custom_service_items': []}),
        'blank_source': _authorization(contract, patch, source_reference='  '),
    }

    result = _update(contract, patch, record, authorization=contexts[case])

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['id'] == str(contract.pk)
    assert result['error']
    assert contract.custom_service_items == record['custom_service_items']


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['Sent', 'Active'])
def test_guarded_service_items_reject_non_draft(status):
    contract = _contract()
    contract.status = status
    contract.save()
    record = ContractSerializer(contract).data

    result = _update(contract, _patch(), record)

    contract.refresh_from_db()
    assert result == {
        'updated': False, 'id': str(contract.pk),
        'error': 'Contract service-item correction requires Draft status; nothing was saved.',
    }
    assert contract.custom_service_items == record['custom_service_items']


@pytest.mark.django_db
def test_guarded_service_items_reject_stale_version_and_before_value():
    contract = _contract()
    record = ContractSerializer(contract).data
    patch = _patch()
    contract.custom_service_items = [{'name': 'Other edit', 'description': 'Concurrent'}]
    contract.save()

    stale = _update(contract, patch, record)
    current = ContractSerializer(contract).data
    mismatched = _update(contract, patch, current, before={
        'custom_service_items': record['custom_service_items'],
    })

    contract.refresh_from_db()
    assert stale['updated'] is False
    assert stale['error'] == 'Stale expected_version; nothing was saved.'
    assert mismatched['updated'] is False
    assert mismatched['error'] == 'Expected values no longer match; nothing was saved.'
    assert contract.custom_service_items == current['custom_service_items']


@pytest.mark.django_db
def test_guarded_service_items_reject_mixed_contract_patch():
    contract = _contract()
    record = ContractSerializer(contract).data
    patch = {**_patch(), 'customer_signatory_name': 'Unrelated signer'}

    result = _update(contract, patch, record)

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Contract service-item correction must contain custom_service_items only.'
    assert contract.custom_service_items == record['custom_service_items']
    assert contract.customer_signatory_name == record['customer_signatory_name']


@pytest.mark.django_db
@pytest.mark.parametrize('items', [
    {'name': 'Not an array'},
    ['Not an object'],
    [{'name': 'Missing description'}],
    [{'name': 'Priced', 'description': 'Scope', 'unit_price': 0}],
    [{'name': ' ', 'description': '  '}],
])
def test_guarded_service_items_reject_malformed_or_pricing_data(items):
    contract = _contract()
    record = ContractSerializer(contract).data

    result = _update(contract, {'custom_service_items': items}, record)

    contract.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Contract service items must be an array of non-empty name/description objects.'
    assert contract.custom_service_items == record['custom_service_items']
