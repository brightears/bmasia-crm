"""Commercial exceptions remain explicit, discoverable and lossless."""
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.response import Response

from crm_app.mcp import (
    ContractQuery, InvoiceQuery, QuoteQuery, _pdf_response_payload,
    convert_quote_to_contract as convert_quote_tool,
    get_commercial_document_context,
)
from crm_app.models import Company, Contract, ContractTemplate, Invoice, Quote
from crm_app.serializers import ContractSerializer, InvoiceSerializer, QuoteSerializer
from crm_app.services.document_context import document_region, effective_billing_entity
from crm_app.services.quote_conversion import convert_quote_to_contract


THAILAND = 'BMAsia (Thailand) Co., Ltd.'
HONG_KONG = 'BMAsia Limited'


@pytest.mark.parametrize('currency', ['USD', 'THB'])
def test_issuer_is_explicit_and_independent_of_country_and_currency(currency):
    company = SimpleNamespace(billing_entity=HONG_KONG, country='Hong Kong')
    document = SimpleNamespace(company=company, billing_entity=THAILAND, currency=currency)
    assert effective_billing_entity(document) == THAILAND
    assert document_region(document) == 'TH'
    assert company.billing_entity == HONG_KONG
    document.billing_entity = ''
    assert effective_billing_entity(document) == HONG_KONG
    assert document_region(document) == 'HK'


def test_unknown_issuer_does_not_fall_back_to_company_currency_or_country():
    document = SimpleNamespace(
        billing_entity='Unverified issuer', currency='USD',
        company=SimpleNamespace(billing_entity=THAILAND, country='Thailand'),
    )
    with pytest.raises(ValueError, match='Unsupported billing entity'):
        effective_billing_entity(document)


@pytest.mark.parametrize('serializer_class', [QuoteSerializer, ContractSerializer, InvoiceSerializer])
def test_all_document_serializers_accept_canonical_issuer_override(serializer_class):
    serializer = serializer_class(data={'billing_entity': THAILAND, 'currency': 'USD'}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['billing_entity'] == THAILAND
    assert serializer.fields['effective_billing_entity'].read_only
    invalid = serializer_class(data={'billing_entity': 'Thailand'}, partial=True)
    assert not invalid.is_valid()
    assert 'billing_entity' in invalid.errors
    cleared = serializer_class(data={'billing_entity': ''}, partial=True)
    assert cleared.is_valid(), cleared.errors


def test_mcp_queries_publish_customer_facing_tailoring_fields():
    assert {'billing_entity', 'payment_schedule', 'terms_conditions'} <= set(QuoteQuery.fields)
    assert {
        'billing_entity', 'payment_schedule', 'preamble_custom', 'payment_custom',
        'activation_custom', 'custom_terms', 'preamble_template',
    } <= set(ContractQuery.fields)
    assert {'billing_entity', 'payment_terms_text'} <= set(InvoiceQuery.fields)


def test_mcp_pdf_error_preserves_actionable_clarification_and_evidence():
    payload = {
        'error': 'clarification_required',
        'detail': 'Corporate template has no editable payment slot.',
        'next_action': 'Select the intended template clause for revision.',
        'evidence': {'missing_slots': ['payment_custom']},
    }
    assert json.loads(_pdf_response_payload(Response(payload, status=422), 'unused.pdf')) == {
        **payload, 'status_code': 422,
    }


def _quote():
    company = Company.objects.create(
        name='Tailoring Test Customer', country='Hong Kong', billing_entity=HONG_KONG,
    )
    return Quote.objects.create(
        company=company, billing_entity=THAILAND, currency='USD',
        valid_from=date(2026, 9, 9), valid_until=date(2026, 10, 9),
        subtotal=Decimal('1300.00'), total_value=Decimal('1300.00'),
        payment_schedule='50% on signature; 50% after onboarding.',
        terms_conditions='Approved customer wording: net received, no offset.',
        notes='INTERNAL-NOTE-DO-NOT-PRINT',
    )


@pytest.mark.django_db
def test_quote_conversion_preserves_exact_approved_terms_schedule_and_issuer():
    quote = _quote()
    contract, _ = convert_quote_to_contract(quote)
    contract.refresh_from_db()
    quote.company.refresh_from_db()
    assert quote.quote_number.startswith('TH-QT')
    assert contract.billing_entity == THAILAND
    assert contract.effective_billing_entity == THAILAND
    assert contract.currency == 'USD'
    assert contract.payment_custom == quote.terms_conditions
    assert contract.payment_schedule == quote.payment_schedule
    assert 'INTERNAL-NOTE' not in contract.payment_custom
    assert quote.company.billing_entity == HONG_KONG
    with patch('crm_app.models.DocumentSequence.get_next_number', return_value='TH-CT-TEST') as number:
        contract.status = 'Sent'
        contract.save()
    number.assert_called_once_with('TH', 'CT')


@pytest.mark.django_db
def test_quote_conversion_honors_explicit_empty_text_and_tailored_clauses():
    quote = _quote()
    contract, _ = convert_quote_to_contract(quote, {
        'payment_custom': '', 'payment_schedule': '',
        'preamble_custom': 'Specific approved preamble.',
        'custom_terms': 'A precisely approved exception.',
    })
    assert contract.payment_custom == ''
    assert contract.payment_schedule == ''
    assert contract.preamble_custom == 'Specific approved preamble.'
    assert contract.custom_terms == 'A precisely approved exception.'


@pytest.mark.django_db
@pytest.mark.parametrize('overrides', [
    {'unknown_clause_field': 'Do not silently drop'},
    {'billing_entity': 'Thailand'},
    {'payment_custom': ['not text']},
    ['not an object'],
])
def test_unknown_or_invalid_conversion_override_cannot_partially_create_a_contract(overrides):
    quote = _quote()
    before = Contract.objects.count()
    result = json.loads(convert_quote_tool(str(quote.pk), json.dumps(overrides)))
    assert result['error'] == 'clarification_required'
    assert Contract.objects.count() == before


@pytest.mark.django_db
def test_mcp_context_exposes_effective_issuer_and_tailoring_without_writes():
    quote = _quote()
    with CaptureQueriesContext(connection) as queries:
        result = json.loads(get_commercial_document_context('quote', str(quote.pk)))
    assert result['record']['billing_entity'] == THAILAND
    assert result['record']['effective_billing_entity'] == THAILAND
    assert result['company_default_billing_entity'] == HONG_KONG
    assert result['record']['currency'] == 'USD'
    assert {'billing_entity', 'terms_conditions', 'payment_schedule'} <= set(result['writable_fields'])
    assert 'effective_billing_entity' not in result['writable_fields']
    assert not any(
        query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
        for query in queries.captured_queries
    )


@pytest.mark.django_db
@pytest.mark.parametrize('explicit_issuer,expected', [(None, THAILAND), ('', HONG_KONG), (HONG_KONG, HONG_KONG)])
def test_invoice_creation_inherits_contract_issuer_only_when_override_is_omitted(explicit_issuer, expected):
    quote = _quote()
    contract, _ = convert_quote_to_contract(quote)
    data = {
        'company': str(quote.company_id), 'contract': str(contract.pk),
        'invoice_number': 'INV-TAILORING-TEST', 'status': 'Draft',
        'issue_date': '2026-09-09', 'due_date': '2026-10-09',
        'amount': '1300.00', 'total_amount': '1300.00', 'currency': 'USD',
    }
    if explicit_issuer is not None:
        data['billing_entity'] = explicit_issuer
    serializer = InvoiceSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    invoice = serializer.save()
    assert invoice.effective_billing_entity == expected
    assert invoice.company.billing_entity == HONG_KONG


@pytest.mark.django_db
def test_explicit_tax_rate_survives_currency_and_line_item_updates():
    quote = _quote()
    data = {
        'company': str(quote.company_id), 'start_date': '2026-10-01',
        'end_date': '2027-09-30', 'value': '100.00', 'currency': 'USD',
        'billing_entity': THAILAND, 'tax_rate': '7.00',
    }
    serializer = ContractSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    contract = serializer.save()
    assert contract.tax_rate == Decimal('7.00')
    assert contract.tax_amount == Decimal('7.00')
    changed = ContractSerializer(contract, data={'currency': 'THB', 'tax_rate': '0.00'}, partial=True)
    assert changed.is_valid(), changed.errors
    contract = changed.save()
    assert contract.tax_rate == Decimal('0.00')
    assert contract.tax_amount == Decimal('0.00')
    value_change = ContractSerializer(contract, data={'value': '200.00'}, partial=True)
    assert value_change.is_valid(), value_change.errors
    contract = value_change.save()
    assert contract.tax_rate == Decimal('0.00')
    assert contract.total_value == Decimal('200.00')
    line_change = ContractSerializer(contract, data={'line_items': [{
        'product_service': 'Beat Breeze', 'description': 'Lobby',
        'quantity': '1', 'unit_price': '260.00',
    }]}, partial=True)
    assert line_change.is_valid(), line_change.errors
    contract = line_change.save()
    assert contract.tax_rate == Decimal('0.00')
    assert contract.tax_amount == Decimal('0.00')
    assert contract.total_value == Decimal('260.00')


@pytest.mark.django_db
def test_mcp_contract_context_reports_exact_current_slots_without_writes():
    quote = _quote()
    contract, _ = convert_quote_to_contract(quote)
    template = ContractTemplate.objects.create(
        name='Tailored corporate test', template_type='preamble', pdf_format='standard',
        content='Approved introduction. {{ payment_clause }} {{signature_blocks}}',
    )
    contract.preamble_template = template
    contract.save(update_fields=['preamble_template'])
    with CaptureQueriesContext(connection) as queries:
        result = json.loads(get_commercial_document_context('contract', str(contract.pk)))
    assert result['tailoring']['template_id'] == str(template.pk)
    assert result['tailoring']['template_placeholders'] == ['payment_clause', 'signature_blocks']
    payment = result['tailoring']['tailoring_fields']['payment_custom']
    assert payment['present_template_slots'] == ['payment_clause']
    assert result['tailoring']['tailoring_fields']['preamble_custom']['present_template_slots'] == []
    assert not any(
        query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
        for query in queries.captured_queries
    )


@pytest.mark.django_db
@pytest.mark.parametrize('status,receipt', [('Sent', None), ('Paid', None), ('Draft', 'TH-RECEIPT-TEST')])
def test_invoice_issuer_change_cannot_rewrite_issued_history(status, receipt):
    quote = _quote()
    invoice = Invoice.objects.create(
        company=quote.company, billing_entity=HONG_KONG,
        invoice_number='HK-INV-ISSUED-TEST', status=status,
        issue_date=date(2026, 9, 9), due_date=date(2026, 10, 9),
        amount=Decimal('1300.00'), total_amount=Decimal('1300.00'),
        currency='USD', receipt_number=receipt,
    )
    serializer = InvoiceSerializer(invoice, data={'billing_entity': THAILAND}, partial=True)
    assert not serializer.is_valid()
    assert 'reissue' in str(serializer.errors['billing_entity'])
    invoice.refresh_from_db()
    assert invoice.billing_entity == HONG_KONG
    same_issuer = InvoiceSerializer(invoice, data={'billing_entity': ''}, partial=True)
    assert same_issuer.is_valid(), same_issuer.errors


@pytest.mark.django_db
def test_invoice_issuer_change_is_blocked_when_recognition_already_exists():
    quote = _quote()
    invoice = Invoice.objects.create(
        company=quote.company, billing_entity=HONG_KONG,
        invoice_number='HK-INV-SCHEDULE-TEST', status='Draft',
        issue_date=date(2026, 9, 9), due_date=date(2026, 10, 9),
        amount=Decimal('1300.00'), total_amount=Decimal('1300.00'), currency='USD',
    )
    with patch.object(type(invoice.recognition_schedules), 'exists', return_value=True):
        serializer = InvoiceSerializer(invoice, data={'billing_entity': THAILAND}, partial=True)
        assert not serializer.is_valid()
    assert 'accounting-reconciliation' in str(serializer.errors['billing_entity'])


@pytest.mark.django_db
def test_mixed_explicit_line_tax_uses_exact_amount_not_rounded_weighted_header():
    quote = _quote()
    data = {
        'company': str(quote.company_id), 'start_date': '2026-10-01',
        'end_date': '2027-09-30', 'value': '3.00', 'currency': 'USD',
        'billing_entity': THAILAND,
        'line_items': [
            {'product_service': 'Taxed', 'description': 'Line A', 'quantity': '1', 'unit_price': '1.00', 'tax_rate': '7.00'},
            {'product_service': 'Zero-rated', 'description': 'Line B', 'quantity': '1', 'unit_price': '2.00', 'tax_rate': '0.00'},
        ],
    }
    serializer = ContractSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    contract = serializer.save()
    assert contract.tax_amount == Decimal('0.07')
    assert contract.total_value == Decimal('3.07')
    assert contract.tax_rate == Decimal('2.33')
    # An explicitly instructed header rate remains authoritative when supplied.
    override = ContractSerializer(contract, data={
        'tax_rate': '0.00', 'line_items': data['line_items'],
    }, partial=True)
    assert override.is_valid(), override.errors
    contract = override.save()
    assert contract.tax_amount == Decimal('0.00')
    assert contract.total_value == Decimal('3.00')


@pytest.mark.django_db
def test_quote_conversion_preserves_approved_tax_amount_and_zero_line_rates():
    quote = _quote()
    quote.tax_amount = Decimal('0.07')
    quote.save(update_fields=['tax_amount'])
    quote.line_items.create(product_service='Taxed', description='Line A', quantity=1, unit_price=Decimal('1.00'), tax_rate=Decimal('7.00'))
    quote.line_items.create(product_service='Zero-rated', description='Line B', quantity=1, unit_price=Decimal('2.00'), tax_rate=Decimal('0.00'))
    quote.refresh_from_db()
    contract, _ = convert_quote_to_contract(quote)
    assert contract.tax_amount == quote.tax_amount == Decimal('0.07')
    assert contract.total_value == quote.total_value == Decimal('3.07')
    assert contract.tax_rate == Decimal('2.33')
    assert list(contract.line_items.order_by('unit_price').values_list('tax_rate', flat=True)) == [Decimal('7.00'), Decimal('0.00')]


@pytest.mark.django_db
def test_wording_and_currency_edits_preserve_exact_existing_tax_authority():
    quote = _quote()
    contract, _ = convert_quote_to_contract(quote)
    contract.line_items.create(
        product_service='Beat Breeze', description='Original wording',
        quantity=1, unit_price=Decimal('1300.00'), tax_rate=Decimal('0.00'),
    )
    contract.tax_rate = Decimal('7.00')
    contract.tax_amount = Decimal('91.00')
    contract.total_value = Decimal('1391.00')
    contract.save(update_fields=['tax_rate', 'tax_amount', 'total_value'])
    edit = ContractSerializer(contract, data={
        'currency': 'THB', 'custom_terms': 'Approved wording change.',
        'line_items': [{
            'product_service': 'Beat Breeze', 'description': 'Tailored clearer wording',
            'quantity': '1.00', 'unit_price': '1300.00', 'tax_rate': '0.00',
            'discount_percentage': '0.00',
        }],
    }, partial=True)
    assert edit.is_valid(), edit.errors
    contract = edit.save()
    assert contract.tax_rate == Decimal('7.00')
    assert contract.tax_amount == Decimal('91.00')
    assert contract.total_value == Decimal('1391.00')
