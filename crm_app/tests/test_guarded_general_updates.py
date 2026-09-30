"""A guarded update may change what the plain update may change, plus a lock.

Only final statuses, issued-contract prices, Sent bookkeeping, Sent-contract
dates, company re-binding and document numbers keep extra conditions.
"""
from datetime import date
from decimal import Decimal
import json

import pytest

from crm_app.mcp import update_record
from crm_app.models import AuditLog, Company, Contract, ContractServiceLocation, Opportunity, Quote
from crm_app.serializers import (
    CompanySerializer, ContractSerializer, OpportunitySerializer, QuoteSerializer,
)


def _guarded(collection, record, observed, patch, context=None):
    return json.loads(update_record(
        collection, str(record.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({key: observed.get(key) for key in patch}),
        authorization_context=json.dumps(context or {}),
    ))


def _instruction(record, patch, **overrides):
    context = {
        'kind': 'explicit_user_instruction',
        'requested_by': 'norbert',
        'source_reference': 'telegram:norbert:12345',
        'record_id': str(record.pk),
        'authorized_changes': patch,
    }
    context.update(overrides)
    return context


def _contract(status='Draft'):
    company = Company.objects.create(name='General guard company', billing_entity='BMAsia Limited')
    return Contract.objects.create(
        company=company, contract_number='DRAFT-GENERAL-1' if status == 'Draft' else 'HK-CT269901',
        start_date=date(2026, 10, 15), end_date=date(2027, 10, 14),
        value=Decimal('520.00'), total_value=Decimal('520.00'), status=status,
    )


@pytest.mark.django_db
def test_company_legal_name_tax_id_and_address_need_no_special_context():
    company = Company.objects.create(
        name='Somerset Diamond Bay Garden', billing_entity='BMAsia Limited', country='Cambodia',
    )
    observed = CompanySerializer(company).data
    patch = {
        'legal_entity_name': 'THE DIAMOND BAY GARDEN CO., LTD.',
        'tax_id': 'L001-902104216',
        'address_line1': 'Sales Centre, Koh Pich Road',
    }

    result = _guarded('company', company, observed, patch)

    assert result['updated'] is True, result
    company.refresh_from_db()
    assert company.legal_entity_name == patch['legal_entity_name']
    assert company.tax_id == patch['tax_id']
    assert company.name == 'Somerset Diamond Bay Garden'
    audit = AuditLog.objects.get(record_id=str(company.pk))
    assert audit.additional_data['kind'] == 'guarded_update'
    assert audit.changes['legal_entity_name'] == {
        'before': observed['legal_entity_name'], 'after': patch['legal_entity_name'],
    }


@pytest.mark.django_db
def test_guarded_update_keeps_optimistic_lock():
    company = Company.objects.create(name='Lock company', billing_entity='BMAsia Limited')
    observed = CompanySerializer(company).data
    company.city = 'Changed elsewhere'
    company.save()

    result = _guarded('company', company, observed, {'legal_entity_name': 'Lock Company Ltd'})

    assert result['error'] == 'Stale expected_version; nothing was saved.'
    company.refresh_from_db()
    assert company.legal_entity_name == ''
    assert not AuditLog.objects.filter(record_id=str(company.pk)).exists()


@pytest.mark.django_db
def test_draft_contract_terms_and_dates_update_without_context():
    contract = _contract()
    observed = ContractSerializer(contract).data
    patch = {'custom_terms': 'Installation by the customer.', 'start_date': '2026-11-01',
             'end_date': '2027-10-31', 'value': '600.00'}

    result = _guarded('contract', contract, observed, patch)

    assert result['updated'] is True, result
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 11, 1)
    assert contract.value == Decimal('600.00')


@pytest.mark.django_db
def test_sent_contract_dates_still_need_the_date_lane():
    contract = _contract(status='Sent')
    observed = ContractSerializer(contract).data

    result = _guarded('contract', contract, observed, {'start_date': '2026-11-01'})

    assert result['updated'] is False
    assert 'routine_contract_date_correction' in result['error']
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 10, 15)


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['Sent', 'Active'])
def test_issued_contract_price_needs_an_instruction(status):
    contract = _contract(status=status)
    observed = ContractSerializer(contract).data
    patch = {'value': '600.00'}

    refused = _guarded('contract', contract, observed, patch)
    accepted = _guarded('contract', contract, observed, patch, _instruction(contract, patch))

    assert refused['updated'] is False
    assert 'explicit_user_instruction' in refused['error']
    assert accepted['updated'] is True, accepted
    contract.refresh_from_db()
    assert contract.value == Decimal('600.00')
    audit = AuditLog.objects.get(record_id=str(contract.pk))
    assert audit.additional_data['requested_by'] == 'norbert'
    assert audit.additional_data['source_reference'] == 'telegram:norbert:12345'


@pytest.mark.django_db
def test_final_contract_status_needs_an_instruction():
    contract = _contract()
    observed = ContractSerializer(contract).data
    patch = {'status': 'Cancelled'}

    refused = _guarded('contract', contract, observed, patch)
    accepted = _guarded('contract', contract, observed, patch, _instruction(contract, patch))

    assert refused['updated'] is False
    assert 'requires an explicit_user_instruction' in refused['error']
    assert accepted['updated'] is True, accepted
    contract.refresh_from_db()
    assert contract.status == 'Cancelled'


@pytest.mark.django_db
@pytest.mark.parametrize('override, message', [
    ({'requested_by': 'vera'}, 'requested_by must be'),
    ({'record_id': 'other-record'}, 'different record'),
    ({'authorized_changes': {'status': 'Expired'}}, 'does not exactly match'),
    ({'source_reference': ' '}, 'valid source_reference'),
    ({'extra': 'field'}, 'exactly kind'),
])
def test_instruction_must_bind_person_record_and_patch(override, message):
    contract = _contract()
    observed = ContractSerializer(contract).data
    patch = {'status': 'Cancelled'}

    result = _guarded('contract', contract, observed, patch, _instruction(contract, patch, **override))

    assert result['updated'] is False
    assert message in result['error']
    contract.refresh_from_db()
    assert contract.status == 'Draft'


@pytest.mark.django_db
def test_final_quote_status_needs_an_instruction():
    company = Company.objects.create(name='Quote status company')
    quote = Quote.objects.create(
        company=company, quote_number='HK-QT269901', status='Sent', sent_date=date(2026, 9, 25),
        valid_from=date(2026, 9, 25), valid_until=date(2026, 10, 25),
    )
    observed = QuoteSerializer(quote).data
    patch = {'status': 'Accepted'}

    refused = _guarded('quote', quote, observed, patch)
    accepted = _guarded('quote', quote, observed, patch, _instruction(quote, patch, requested_by='nikki'))

    assert refused['updated'] is False
    assert accepted['updated'] is True, accepted
    quote.refresh_from_db()
    assert quote.status == 'Accepted'


@pytest.mark.django_db
def test_opportunity_won_accepts_an_instruction():
    company = Company.objects.create(name='Opportunity instruction company', billing_entity='BMAsia Limited')
    opportunity = Opportunity.objects.create(
        company=company, name='Instruction deal', stage='Quotation Sent',
        expected_value=Decimal('520.00'), probability=50,
    )
    observed = OpportunitySerializer(opportunity).data
    patch = {'stage': 'Won'}

    result = _guarded('opportunity', opportunity, observed, patch,
                      _instruction(opportunity, patch, requested_by='lyra'))

    assert result['updated'] is True, result
    opportunity.refresh_from_db()
    assert opportunity.stage == 'Won'


@pytest.mark.django_db
def test_document_number_and_unknown_context_are_refused():
    contract = _contract()
    observed = ContractSerializer(contract).data

    number = _guarded('contract', contract, observed, {'contract_number': 'HK-CT269999'})
    unknown = _guarded('contract', contract, observed, {'notes': 'x'}, {'kind': 'made_up'})

    assert number['error'] == 'Document numbers are issued by the CRM and cannot be patched; nothing was saved.'
    assert unknown['error'] == 'Unknown authorization_context kind; nothing was saved.'
    contract.refresh_from_db()
    assert contract.contract_number == 'DRAFT-GENERAL-1'
    assert contract.notes != 'x'


@pytest.mark.django_db
def test_draft_service_locations_can_be_replaced_under_the_lock():
    contract = _contract()
    ContractServiceLocation.objects.create(
        contract=contract, location_name='Lobby', platform='beatbreeze', sort_order=0,
        price=Decimal('260.00'),
    )
    observed = ContractSerializer(contract).data
    patch = {
        'replace_service_locations': True,
        'service_locations': [
            {'location_name': 'Lobby', 'platform': 'beatbreeze', 'sort_order': 0, 'price': '260.00'},
            {'location_name': 'Pool', 'platform': 'beatbreeze', 'sort_order': 1, 'price': '260.00'},
        ],
    }
    expected_values = {
        'replace_service_locations': None,
        'service_locations': json.loads(json.dumps(observed['service_locations'], default=str)),
    }

    result = json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps(expected_values),
    ))

    assert result['updated'] is True, result
    assert [row['location_name'] for row in result['applied']['service_locations']] == ['Lobby', 'Pool']
    assert result['applied']['replace_service_locations'] is True
    assert contract.service_locations.count() == 2


def _query_style_opportunity():
    company = Company.objects.create(name='Query shape company', billing_entity='BMAsia Limited')
    return Opportunity.objects.create(
        company=company, name='Query shape deal', stage='Quotation Sent',
        expected_value=Decimal('260.00'), probability=30,
    )


@pytest.mark.django_db
def test_query_tool_numbers_match_serializer_decimals():
    # Cira reads with query_data_collections, which returns 260.0, not "260.00".
    opportunity = _query_style_opportunity()
    observed = OpportunitySerializer(opportunity).data
    patch = {'stage': 'Contract Sent', 'probability': 60, 'expected_value': 520}

    result = json.loads(update_record(
        'opportunity', str(opportunity.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'stage': 'Quotation Sent', 'probability': 30, 'expected_value': 260.0}),
        authorization_context=json.dumps(_instruction(opportunity, patch)),
    ))

    assert result['updated'] is True, result
    opportunity.refresh_from_db()
    assert opportunity.expected_value == Decimal('520.00')
    assert opportunity.probability == 60


@pytest.mark.django_db
@pytest.mark.parametrize('before', [
    {'expected_value': 261.0},
    {'expected_value': '260.01'},
    {'expected_value': None},
    {'expected_value': True},
])
def test_a_different_number_still_fails_the_lock(before):
    opportunity = _query_style_opportunity()
    observed = OpportunitySerializer(opportunity).data
    patch = {'expected_value': 520}

    result = json.loads(update_record(
        'opportunity', str(opportunity.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps(before),
        authorization_context=json.dumps(_instruction(opportunity, patch)),
    ))

    assert result['error'] == 'Expected values no longer match; nothing was saved.'
    opportunity.refresh_from_db()
    assert opportunity.expected_value == Decimal('260.00')


@pytest.mark.django_db
def test_nested_zone_price_accepts_query_tool_number():
    contract = _contract()
    location = ContractServiceLocation.objects.create(
        contract=contract, location_name='Lobby', platform='beatbreeze', sort_order=0,
        price=Decimal('520.00'),
    )
    observed = ContractSerializer(contract).data
    before = json.loads(json.dumps(observed['service_locations'], default=str))
    before[0]['price'] = 520.0
    patch = {'service_locations': [{'id': str(location.pk), 'location_name': 'Main lobby',
                                    'platform': 'beatbreeze', 'sort_order': 0, 'price': '520.00'}]}

    result = json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'service_locations': before}),
    ))

    assert result['updated'] is True, result
    location.refresh_from_db()
    assert location.location_name == 'Main lobby'
