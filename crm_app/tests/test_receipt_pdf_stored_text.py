"""The legacy receipt layout prints stored text exactly as stored.

While COMMERCIAL_DOCUMENT_V2_RECEIPT_LIVE is off, receipts use the legacy
builder. Its bill-to card, line items, payment terms and notes are plain
stored text placed into ReportLab Paragraph markup, so "&" and "<" must be
escaped exactly once. All fixtures are synthetic.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.test import override_settings
from pypdf import PdfReader
from rest_framework.test import APIClient

from crm_app.models import Company, Contract, Invoice, InvoiceLineItem, User

pytestmark = pytest.mark.django_db

LEGAL_NAME = 'Example A&B Hospitality <HQ> Ltd'
BRANCH = 'Branch R&D <02>'
PROPERTY = 'Example P&L Property'
TAX_ID = 'TX&1 <A>'
ADDRESS = '9 R&D Road <Unit 3>'
PRODUCT = 'Music&Media <Pack>'
DESCRIPTION = 'Covers F&B "lounge" <areas>\nSecond line & more'
PAYMENT_TERMS = 'Pay F&B fees <net 30>\nby transfer'
NOTES = 'Note for Q&A <team>'
CONTRACT_NUMBER = 'TH-C&D<26>-01'


def _receipt_text(*, line_items=True, contract=False, **invoice_extra):
    company = Company.objects.create(
        name='Example Receipt Hotel', legal_entity_name=LEGAL_NAME, branch=BRANCH, tax_id=TAX_ID,
        country='Thailand', address_line1=ADDRESS, city='Example City',
        billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    if contract:
        invoice_extra['contract'] = Contract.objects.create(
            company=company, contract_number=CONTRACT_NUMBER, contract_type='Annual', status='Active',
            start_date=date(2026, 9, 1), end_date=date(2027, 8, 31), value=Decimal('1300.00'),
            currency='USD', service_type='soundtrack_essential_yearly',
        )
    invoice = Invoice.objects.create(
        company=company, invoice_number='TH-IV-RECEIPT-TEST', receipt_number='TH-RCP-RECEIPT-TEST',
        status='Paid', issue_date=date(2026, 9, 9), due_date=date(2026, 9, 9) + timedelta(days=30),
        paid_date=date(2026, 9, 10), amount=Decimal('1300.00'), total_amount=Decimal('1300.00'),
        currency='USD', property_name=PROPERTY, **invoice_extra,
    )
    if line_items:
        InvoiceLineItem.objects.create(
            invoice=invoice, product_service=PRODUCT, description=DESCRIPTION, quantity=Decimal('1'),
            tax_rate=Decimal('0'),
            unit_price=Decimal('1300.00'), line_total=Decimal('1300.00'),
        )
    user = User.objects.create_user(
        username='receipt-finance', email='receipt-finance@example.com', password='test-only-password',
        role='Finance', is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    with override_settings(COMMERCIAL_DOCUMENT_V2_RECEIPT_LIVE=False):
        response = client.get(f'/api/v1/invoices/{invoice.id}/receipt-pdf/')
    assert response.status_code == 200
    text = ' '.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    return ' '.join(text.split())


def test_legacy_receipt_prints_stored_text_as_stored():
    text = _receipt_text(payment_terms_text=PAYMENT_TERMS, notes=NOTES)
    for value in (LEGAL_NAME, f'({BRANCH})', f'Property: {PROPERTY}', f'Tax ID: {TAX_ID}', ADDRESS,
                  PRODUCT, 'Covers F&B "lounge" <areas>', 'Second line & more',
                  'Pay F&B fees <net 30>', 'by transfer', NOTES):
        assert value in text, (value, text)
    assert 'F&B;' not in text and '&amp;' not in text


def test_legacy_receipt_default_payment_terms_are_unchanged():
    text = _receipt_text()
    assert 'Payment Terms:' in text
    assert '&amp;' not in text and '&lt;' not in text


@pytest.mark.parametrize('line_items', [True, False], ids=['line_items', 'no_line_items'])
def test_legacy_receipt_prints_the_contract_number_as_stored(line_items):
    text = _receipt_text(line_items=line_items, contract=True)
    assert f'Contract: {CONTRACT_NUMBER}' in text
    assert text.count(CONTRACT_NUMBER) == (1 if line_items else 2)
