"""Explicit contract additions must belong visually to the native agreement.

No customer data is used. The native view renders synthetic records with all
PDF activity logging suppressed; database writes during rendering are forbidden.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
import os
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pypdf import PdfReader

from crm_app.models import Company, Contract, ContractTemplate
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def agreement():
    company = Company.objects.create(
        name='Example Coastal Hotel', country='Vietnam', city='Ha Long',
        address_line1='Example Review Address', billing_entity='BMAsia Limited',
    )
    agreement = Contract.objects.create(
        company=company, contract_number='DRAFT-OPTIONAL-LAYOUT',
        contract_type='Annual', contract_category='standard', status='Draft',
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('2000.00'), total_value=Decimal('2000.00'),
        price_per_zone=Decimal('200.00'), tax_rate=Decimal('0.00'),
        currency='USD', billing_frequency='Annually',
        bmasia_signatory_name='Chris Andrews', bmasia_signatory_title='Director',
        property_name='Example Coastal Property',
        notes='INTERNAL-REVIEW-ONLY: verify legal entity, dates and area names.',
    )
    for index in range(10):
        agreement.service_locations.create(
            location_name=f'Area {index + 1} - to be confirmed',
            platform='beatbreeze', price=Decimal('200.00'), sort_order=index,
        )
    return agreement


def _category(agreement, category):
    agreement.contract_category = category
    if category == 'participation':
        agreement.master_contract = Contract.objects.create(
            company=agreement.company, contract_number='MASTER-OPTIONAL-LAYOUT',
            contract_category='corporate_master', status='Draft',
            start_date=agreement.start_date, end_date=agreement.end_date,
            value=agreement.value, currency=agreement.currency,
        )


def _render(agreement, artifact_name):
    before = Contract.objects.values().get(pk=agreement.pk)
    view = ContractViewSet()
    view.get_object = lambda: agreement
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False),
        _bmasia_suppress_pdf_activity=True,
    )
    with CaptureQueriesContext(connection) as queries:
        response = view.pdf(view.request, pk=agreement.pk)
    assert response.status_code == 200, getattr(response, 'data', None)
    assert response['X-BMAsia-Renderer'] == 'contract-v2'
    assert not [q['sql'] for q in queries.captured_queries
                if re.match(r'^\s*(INSERT|UPDATE|DELETE)\b', q['sql'], re.I)]
    assert Contract.objects.values().get(pk=agreement.pk) == before
    reader = PdfReader(BytesIO(response.content))
    for page in reader.pages:
        assert tuple(map(float, (page.mediabox.width, page.mediabox.height))) == pytest.approx((595.2756, 841.8898), abs=.01)
        assert len(page.images) == 1  # Logo only: no supplier signature/stamp.
    if os.environ.get('CONTRACT_OPTIONAL_REVIEW_DIR'):
        target = Path(os.environ['CONTRACT_OPTIONAL_REVIEW_DIR'])
        target.mkdir(parents=True, exist_ok=True)
        (target / (artifact_name + '.pdf')).write_bytes(response.content)
    return reader


def _text(reader):
    return ' '.join(' '.join(page.extract_text() for page in reader.pages).split())


def _assert_integrated_optional_labels(reader):
    labels = []
    for page in reader.pages:
        def visit(text, cm, tm, font, size):
            if re.search(r'(?:additional|custom) terms|payment schedule', text, re.I):
                labels.append((text, size, font.get('/BaseFont', '') if font else ''))
        page.extract_text(visitor_text=visit)
    assert len(labels) >= 2
    for text, size, font in labels:
        assert size == pytest.approx(9.5), (text, size)
        assert 'DejaVuSans' in font, font
        assert not text.strip().isupper(), text


@pytest.mark.parametrize('category', ['standard', 'corporate_master', 'participation'])
@pytest.mark.parametrize('blank', ['', ' \n  '])
def test_empty_optional_fields_never_invent_customer_sections(agreement, category, blank):
    _category(agreement, category)
    agreement.custom_terms = blank
    agreement.payment_schedule = blank
    reader = _render(agreement, f'{category}-no-additions')
    text = _text(reader)
    assert not re.search(r'(?:additional|custom) terms|payment schedule', text, re.I)
    assert 'INTERNAL-REVIEW-ONLY' not in text
    assert 'verify legal entity' not in text


@pytest.mark.parametrize('category', ['standard', 'corporate_master', 'participation'])
def test_requested_additions_use_body_typography_and_appear_once(agreement, category):
    _category(agreement, category)
    agreement.custom_terms = 'The client-approved seasonal playlist applies to the Lobby.'
    agreement.payment_schedule = 'Two instalments of USD 1,000, due on the agreed dates.'
    reader = _render(agreement, f'{category}-requested-additions')
    text = _text(reader)
    assert text.count(agreement.custom_terms) == 1
    assert text.count(agreement.payment_schedule) == 1
    assert 'INTERNAL-REVIEW-ONLY' not in text
    _assert_integrated_optional_labels(reader)
    if category == 'standard':
        assert text.index('Terms of payment:') < text.index(agreement.payment_schedule) < text.index('Activation Date:')
        assert text.index(agreement.custom_terms) < text.index('Chris Andrews')


@pytest.mark.parametrize('has_slots', [False, True])
def test_full_template_preserves_requested_text_without_duplicate_addenda(agreement, has_slots):
    agreement.custom_terms = 'Approved template exception remains unchanged.'
    agreement.payment_schedule = 'The approved invoice is payable in two instalments.'
    slots = '{{additional_terms}}<br/>{{payment_schedule}}<br/>' if has_slots else ''
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Explicit full agreement layout test', template_type='preamble',
        pdf_format='standard', content=(
            'Supplier: {{issuer_name}}.<br/>The agreed liability allocation remains unchanged.<br/>'
            '{{zones_table}}<br/>' + slots + '{{signature_blocks}}'
        ),
    )
    reader = _render(agreement, f'full-template-slots-{has_slots}')
    text = _text(reader)
    assert text.count(agreement.custom_terms) == 1
    assert text.count(agreement.payment_schedule) == 1
    assert 'The agreed liability allocation remains unchanged.' in text
    assert '{{' not in text
    if not has_slots:
        _assert_integrated_optional_labels(reader)


def test_long_requested_additions_preserve_paragraphs_footer_and_signature(agreement):
    clauses = [f'Approved provision {i:02}: The agreed service applies to the listed music areas.' for i in range(45)]
    agreement.custom_terms = '\n'.join(clauses)
    agreement.payment_schedule = 'Payment follows the customer-approved annual schedule.'
    reader = _render(agreement, 'standard-long-requested-additions')
    text = _text(reader)
    for clause in clauses:
        assert text.count(clause) == 1
    assert text.count(agreement.payment_schedule) == 1
    for index, page in enumerate(reader.pages, 1):
        page_text = ' '.join(page.extract_text().split())
        assert 'BMAsia Limited | bmasiamusic.com' in page_text
        assert f'{index} / {len(reader.pages)}' in page_text
    assert 'Chris Andrews' in text
    _assert_integrated_optional_labels(reader)


def test_short_template_does_not_drop_requested_additions(agreement):
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Short approved preamble', template_type='preamble',
        pdf_format='standard', content='The approved service remains as agreed.',
    )
    agreement.custom_terms = 'The approved short-template exception is retained.'
    agreement.payment_schedule = 'The approved payment date is 1 October 2026.'
    reader = _render(agreement, 'short-template-requested-additions')
    text = _text(reader)
    assert text.count(agreement.custom_terms) == 1
    assert text.count(agreement.payment_schedule) == 1
    _assert_integrated_optional_labels(reader)


def test_pasted_optional_text_cannot_override_agreement_typography(agreement):
    agreement.custom_terms = '<font size="24" color="red"><span style="font-size:30pt">Approved <b>seasonal</b> service wording.</span></font>'
    agreement.payment_schedule = 'The approved payment schedule is retained.'
    reader = _render(agreement, 'standard-pasted-formatting')
    text = _text(reader)
    assert text.count('Approved seasonal service wording.') == 1
    _assert_integrated_optional_labels(reader)
    for page in reader.pages:
        def visit(text, cm, tm, font, size):
            if 'seasonal' in text:
                assert size == pytest.approx(9.5)
                assert 'DejaVuSans' in font['/BaseFont']
        page.extract_text(visitor_text=visit)
