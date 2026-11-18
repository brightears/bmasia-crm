"""Thai stored text prints in Sarabun in every customer PDF (D4/D5).

DejaVu Sans has no Thai glyphs, so a Thai legal name or address printed as
boxes. Thai runs now switch to the bundled Sarabun Regular/Bold, the rest of
the document stays in DejaVu, and the text layer keeps the stored string.

The fonts are read from crm_app/fonts/. These tests fail when the files are
missing, on purpose: a missing font must never pass silently. All names and
addresses below are invented.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
import os
import re
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table

from crm_app import pdf_thai
from crm_app.commercial_pdf import BOLD_FONT, BODY_FONT, document_styles, entity_profile_for, html_text
from crm_app.models import (
    Company, Contact, Contract, ContractLineItem, CorporatePdfTemplate, Invoice, InvoiceLineItem,
)
from crm_app.pdf_thai import ThaiAwareParagraph, check_thai_fonts, ensure_thai_fonts


THAI_LEGAL_NAME = 'บริษัท ฮาร์เบอร์ ทดสอบ จำกัด'
THAI_ADDRESS = 'เลขที่ 99/9 ถนนทดสอบ แขวงตัวอย่าง'
THAI_CITY = 'กรุงเทพมหานคร'
THAI_SIGNER = 'นางสาวสมหญิง ทดสอบ'
THAI_SIGNER_TITLE = 'ผู้จัดการทั่วไป'
# Mixed Latin and Thai with characters that must stay escaped exactly.
THAI_CONTACT_TITLE = 'ผู้จัดการฝ่าย F&B <ห้องอาหาร>'
THAI_ZONE = 'ห้องอาหาร & บาร์ <ชั้น 1>'
# Tone marks above an upper vowel or a sara am: the unshaped cases.
THAI_STACKED = 'ที่ปรึกษา ชื่อ น้ำ ปั้น'
THAI_LONG_RUN = 'บริษัทโรงแรมและรีสอร์ทระหว่างประเทศเพื่อการท่องเที่ยวทดสอบจำกัด'

THAI_CHAR = re.compile(r'[฀-๿]')
COMBINING = re.compile(r'[ัิ-ฺ็-๎]')
ALL_THAI_FIXTURES = [
    THAI_LEGAL_NAME, THAI_ADDRESS, THAI_CITY, THAI_SIGNER, THAI_SIGNER_TITLE,
    THAI_CONTACT_TITLE, THAI_ZONE, THAI_STACKED, THAI_LONG_RUN,
]


def _flat(text):
    return ' '.join(text.split())


def _runs(pdf_bytes):
    """(page, font, text) for every text operation in the PDF."""
    runs = []
    for number, page in enumerate(PdfReader(BytesIO(pdf_bytes)).pages, start=1):
        def visit(text, _cm, _tm, font, _size, number=number):
            if text.strip() and font is not None:
                runs.append((number, str(font['/BaseFont']).split('+')[-1], text))
        page.extract_text(visitor_text=visit)
    return runs


def _text(pdf_bytes):
    return _flat(' '.join(page.extract_text() for page in PdfReader(BytesIO(pdf_bytes)).pages))


def _assert_thai_in_sarabun(pdf_bytes):
    runs = _runs(pdf_bytes)
    thai_runs = [(font, text) for _page, font, text in runs if THAI_CHAR.search(text)]
    assert thai_runs, 'no Thai text was drawn'
    wrong = [(font, text) for font, text in thai_runs if not font.startswith('Sarabun')]
    assert not wrong, wrong
    # Latin text around it stays in the document's own font.
    latin_fonts = {font for _page, font, text in runs if re.search(r'[A-Za-z]{3}', text)}
    assert latin_fonts <= {'DejaVuSans', 'DejaVuSans-Bold'}, latin_fonts
    return runs


# --- font files and the startup guard ------------------------------------

def test_font_files_ship_with_the_code_and_cover_every_fixture_character():
    for font_name, path in pdf_thai.THAI_FONT_FILES.items():
        assert os.path.isfile(path), f'{font_name} missing at {path}'
        face = TTFont(f'{font_name}-coverage', path).face
        missing = sorted({
            hex(ord(char)) for value in ALL_THAI_FIXTURES for char in value
            if THAI_CHAR.match(char) and ord(char) not in face.charToGlyph
        })
        assert not missing, (font_name, missing)
    assert check_thai_fonts() == []


def test_system_check_is_registered_and_reports_a_missing_font(monkeypatch, tmp_path):
    from django.core import checks
    assert check_thai_fonts in checks.registry.registry.get_checks()

    monkeypatch.setattr(pdf_thai, 'THAI_FONT_FILES', {
        pdf_thai.THAI_FONT: str(tmp_path / 'Sarabun-Regular.ttf'),
        pdf_thai.THAI_BOLD_FONT: str(tmp_path / 'Sarabun-Bold.ttf'),
    })
    assert [error.id for error in check_thai_fonts()] == ['crm_app.E101', 'crm_app.E101']
    with pytest.raises(RuntimeError, match='Thai PDF font file missing'):
        ensure_thai_fonts()
    # A Thai value fails loudly instead of printing boxes.
    with pytest.raises(RuntimeError, match='Thai PDF font file missing'):
        ThaiAwareParagraph(html_text(THAI_LEGAL_NAME), document_styles()['body'])


# --- paragraph mechanism ---------------------------------------------------

def _frag_view(paragraph):
    return [(frag.text, frag.fontName, frag.fontSize, getattr(frag, 'rise', 0)) for frag in paragraph.frags]


def test_paragraph_without_thai_is_identical_to_a_plain_paragraph():
    styles = document_styles()
    for markup, style in [
        ('Harbour Light Hospitality Limited', styles['body']),
        ('<b>Billing:</b> Annual &amp; F&amp;B &lt;Ops&gt; Đà Nẵng ✓', styles['body']),
        ('TOTAL', styles['body_bold']),
    ]:
        assert _frag_view(ThaiAwareParagraph(markup, style)) == _frag_view(Paragraph(markup, style))


def test_mixed_line_switches_font_per_run_and_keeps_escaped_text_exact():
    styles = document_styles()
    value = f'Harbour Test Co., Ltd. / {THAI_LEGAL_NAME}, {THAI_CONTACT_TITLE}'
    paragraph = ThaiAwareParagraph(html_text(value), styles['body'])
    assert paragraph.getPlainText() == value
    for frag in paragraph.frags:
        if THAI_CHAR.search(frag.text):
            # Sarabun, or a Sarabun variant (the mark of ฝ่าย is ".narrow").
            assert frag.fontName.split('.')[0] == pdf_thai.THAI_FONT, frag.text
            assert not re.search(r'[A-Za-z&<>]', frag.text), frag.text
        else:
            assert frag.fontName == BODY_FONT, frag.text
    assert 'F&B <' in ''.join(frag.text for frag in paragraph.frags)


def test_bold_text_uses_the_thai_bold_face():
    styles = document_styles()
    paragraph = ThaiAwareParagraph(html_text(f'TOTAL {THAI_LEGAL_NAME}'), styles['body_bold'])
    fonts = {frag.fontName for frag in paragraph.frags if THAI_CHAR.search(frag.text)}
    assert fonts == {pdf_thai.THAI_BOLD_FONT}
    assert {frag.fontName for frag in paragraph.frags if 'TOTAL' in frag.text} == {BOLD_FONT}
    # Inline <b> in a DejaVu paragraph resolves to the regular DejaVu face
    # (no DejaVu family is registered), so Thai next to it stays regular too.
    inline = ThaiAwareParagraph(f'<b>Name {THAI_LEGAL_NAME}</b>', styles['body'])
    assert {frag.fontName for frag in inline.frags} == {BODY_FONT, pdf_thai.THAI_FONT}


def test_only_marks_sarabun_moves_are_redrawn():
    # Where each mark lands is measured in test_pdf_thai_geometry.py; this
    # pins which marks are touched at all.
    style = document_styles()['body']
    text = THAI_STACKED + ' ป่า กา ไม่'
    paragraph = ThaiAwareParagraph(html_text(text), style)
    assert paragraph.getPlainText() == text
    lifted = [frag.text for frag in paragraph.frags if getattr(frag, 'rise', 0) > 0]
    # ที่ (over sara ii), ชื่อ (over sara uee), น้ำ (before sara am), ปั้น (over mai han-akat).
    assert lifted == ['่', '่', '้', '้']
    narrow = [frag.text for frag in paragraph.frags if frag.fontName.endswith('.narrow')]
    # ปั้น: the vowel, and the tone above it; ป่า: the tone.
    assert narrow == ['ั', '้', '่']


def _wrapped_lines(paragraph, width):
    """(text, spare width) per line, for both of ReportLab's line layouts."""
    paragraph.wrap(width, 1000)
    lines = []
    for line in paragraph.blPara.lines:
        if paragraph.blPara.kind == 0:
            extra, words = line
            lines.append((' '.join(words), extra))
        else:
            lines.append((''.join(frag.text for frag in line.words), line.extraSpace))
    return lines


def test_long_thai_run_wraps_inside_a_narrow_cell_and_keeps_marks_with_their_base():
    style = document_styles()['body']
    value = f'{THAI_LONG_RUN} {THAI_ADDRESS}'
    paragraph = ThaiAwareParagraph(html_text(value), style)
    width = 120
    lines = _wrapped_lines(paragraph, width)
    assert len(lines) >= 4
    for text, extra in lines:
        assert extra >= -0.01, f'line wider than the cell: {text}'
        assert not COMBINING.match(text[:1]), f'a mark was separated from its consonant: {text}'
    assert ''.join(text for text, _ in lines).replace(' ', '') == value.replace(' ', '')
    # The same text in a table cell lays out without an error.
    Table([[paragraph]], colWidths=[width + 18]).wrap(width + 18, 1000)


def test_width_is_measured_with_the_thai_font():
    style = document_styles()['body']
    ensure_thai_fonts()
    paragraph = ThaiAwareParagraph(html_text(THAI_LEGAL_NAME), style)
    [(_text, extra)] = _wrapped_lines(paragraph, 1000)
    expected = pdfmetrics.stringWidth(THAI_LEGAL_NAME, pdf_thai.THAI_FONT, style.fontSize)
    assert 1000 - extra == pytest.approx(expected, abs=0.01)
    assert expected != pytest.approx(pdfmetrics.stringWidth(THAI_LEGAL_NAME, BODY_FONT, style.fontSize))


# --- documents -------------------------------------------------------------

def _thai_company(**extra):
    values = dict(
        name='Harbour Test Hotel', legal_entity_name=THAI_LEGAL_NAME, country='Thailand',
        city=THAI_CITY, address_line1=THAI_ADDRESS, billing_entity='BMAsia (Thailand) Co., Ltd.',
        branch='Branch 00001', tax_id='0100000000001',
    )
    values.update(extra)
    return Company.objects.create(**values)


def _thai_agreement():
    agreement = Contract.objects.create(
        company=_thai_company(), contract_number='TH-CT-THAI-TEST',
        contract_type='Annual', contract_category='standard', status='Draft',
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('1000.00'), total_value=Decimal('1000.00'), tax_rate=Decimal('0.00'),
        currency='THB', billing_frequency='Annual', property_name='Harbour Test Hotel',
        customer_contact_name=THAI_SIGNER, customer_contact_title=THAI_CONTACT_TITLE,
        customer_contact_email='contact@example.com',
        bmasia_contact_name='Example Account Lead', bmasia_contact_title='Account Manager',
        bmasia_contact_email='lead@example.com',
        customer_signatory_name=THAI_SIGNER, customer_signatory_title=THAI_SIGNER_TITLE,
        bmasia_signatory_name='Example Supplier Signer', bmasia_signatory_title='Director',
        custom_terms=f'Additional terms: {THAI_STACKED}',
    )
    agreement.service_locations.create(location_name=THAI_ZONE, platform='soundtrack', sort_order=0)
    ContractLineItem.objects.create(
        contract=agreement, product_service='Soundtrack', quantity=Decimal('1'),
        unit_price=Decimal('1000.00'), line_total=Decimal('1000.00'),
    )
    return agreement


def _render_contract(agreement):
    from crm_app.views import ContractViewSet
    view = ContractViewSet()
    view.get_object = lambda: agreement
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False), _bmasia_suppress_pdf_activity=True,
    )
    response = view.pdf(view.request, pk=agreement.pk)
    assert response.status_code == 200, getattr(response, 'data', None)
    assert response['X-BMAsia-Renderer'] == 'contract-v2'
    return response.content


@pytest.mark.django_db
def test_standard_agreement_prints_thai_in_every_slot():
    pdf = _render_contract(_thai_agreement())
    text = _text(pdf)
    # Identity card, preamble and customer signature block.
    assert text.count(THAI_LEGAL_NAME) >= 3, text
    for value in (THAI_ADDRESS, THAI_SIGNER, THAI_SIGNER_TITLE, THAI_CONTACT_TITLE, THAI_ZONE, THAI_STACKED):
        assert _flat(value) in text, value
    assert not re.search(r'\w&\w+;', text)
    _assert_thai_in_sarabun(pdf)


@pytest.mark.django_db
@pytest.mark.parametrize('category', ['corporate_master', 'participation'])
def test_master_and_participation_agreements_print_thai(category):
    agreement = _thai_agreement()
    agreement.contract_category = category
    if category == 'participation':
        agreement.master_contract = Contract.objects.create(
            company=_thai_company(name='Harbour Test Group', legal_entity_name='บริษัท กลุ่มทดสอบ จำกัด'),
            contract_number='MASTER-THAI-TEST', contract_category='corporate_master', status='Draft',
            start_date=agreement.start_date, end_date=agreement.end_date,
            value=agreement.value, currency=agreement.currency,
        )
    agreement.save()
    pdf = _render_contract(agreement)
    text = _text(pdf)
    for value in (THAI_LEGAL_NAME, THAI_SIGNER, THAI_SIGNER_TITLE, THAI_STACKED):
        assert _flat(value) in text, value
    if category == 'participation':
        assert 'บริษัท กลุ่มทดสอบ จำกัด' in text
    _assert_thai_in_sarabun(pdf)


@pytest.mark.django_db
def test_corporate_participation_format_prints_thai():
    agreement = _thai_agreement()
    parent = Company.objects.create(
        name='Harbour Corporate Parent', country='Thailand',
        billing_entity='BMAsia (Thailand) Co., Ltd.', is_corporate_parent=True,
    )
    corporate_format = next(
        key for key, _label in CorporatePdfTemplate.TEMPLATE_FORMAT_CHOICES if key.endswith('_hpa')
    )
    CorporatePdfTemplate.objects.create(
        name='Harbour corporate layout', template_format=corporate_format, company=parent,
        warranty_text='Warranty covers every listed area.',
    )
    agreement.company.parent_company = parent
    agreement.company.save()
    Contact.objects.create(
        company=agreement.company, name=THAI_SIGNER, email='contact@example.com',
        contact_type='Primary', title=THAI_CONTACT_TITLE,
    )
    agreement.contract_category = 'participation'
    agreement.save()
    pdf = _render_contract(agreement)
    text = _text(pdf)
    assert f'and {THAI_LEGAL_NAME} (Branch 00001) ("Hotel")' in text
    for value in (THAI_ZONE, THAI_SIGNER, THAI_SIGNER_TITLE):
        assert _flat(value) in text, value
    _assert_thai_in_sarabun(pdf)


def _commercial_fixtures():
    from scripts.preview_commercial_pdf_v2 import (
        ROOT, format_address_multiline, format_duration, sample_invoice, sample_quote,
    )
    return ROOT, format_address_multiline, format_duration, sample_invoice, sample_quote


def _thai_namespace_company(company):
    company.legal_entity_name = THAI_LEGAL_NAME
    company.address_line1 = THAI_ADDRESS
    company.address_line2 = ''
    company.city = THAI_CITY
    company.country = 'Thailand'
    return company


def test_quote_prints_thai_prepared_for_contact_and_line_item():
    from crm_app.quote_pdf_v2 import build_quote_pdf_v2
    root, address, duration, _sample_invoice, sample_quote = _commercial_fixtures()
    quote = sample_quote()
    _thai_namespace_company(quote.company)
    quote.contact.name = THAI_SIGNER
    quote.line_items.all()[0].description = f'{THAI_ZONE} {THAI_LONG_RUN}'
    pdf = build_quote_pdf_v2(
        quote, entity_profile_for('BMAsia (Thailand) Co., Ltd.'),
        str(root / 'crm_app/static/crm_app/images/bmasia_logo.png'), address, duration,
    )
    text = _text(pdf)
    for value in (THAI_LEGAL_NAME, THAI_ADDRESS, THAI_SIGNER, THAI_ZONE):
        assert value in text, value
    assert THAI_LONG_RUN in text.replace(' ', '') or THAI_LONG_RUN in text
    _assert_thai_in_sarabun(pdf)


@pytest.mark.parametrize('is_receipt', [False, True])
def test_invoice_and_receipt_print_thai_bill_to_and_description(is_receipt):
    from crm_app.invoice_pdf_v2 import build_invoice_pdf_v2
    root, address, _duration, sample_invoice, _sample_quote = _commercial_fixtures()
    invoice = sample_invoice()
    _thai_namespace_company(invoice.company)
    invoice.line_items.all()[0].description = THAI_STACKED
    pdf = build_invoice_pdf_v2(
        invoice, entity_profile_for('BMAsia (Thailand) Co., Ltd.'),
        str(root / 'crm_app/static/crm_app/images/bmasia_logo.png'), address, is_receipt=is_receipt,
    )
    text = _text(pdf)
    for value in (THAI_LEGAL_NAME, THAI_ADDRESS, THAI_STACKED):
        assert value in text, value
    _assert_thai_in_sarabun(pdf)


@pytest.mark.django_db
def test_legacy_receipt_layout_prints_thai_bill_to():
    from crm_app.views import InvoiceViewSet
    invoice = Invoice.objects.create(
        company=_thai_company(), invoice_number='TH-IV-THAI-TEST', status='Paid',
        issue_date=date(2026, 9, 9), due_date=date(2026, 10, 9), paid_date=date(2026, 9, 20),
        amount=Decimal('1300.00'), total_amount=Decimal('1300.00'), currency='THB',
        receipt_number='TH-RCP-THAI-TEST',
    )
    InvoiceLineItem.objects.create(
        invoice=invoice, product_service='Soundtrack', description=THAI_STACKED,
        quantity=Decimal('1'), unit_price=Decimal('1300.00'), tax_rate=Decimal('0'),
    )
    view = InvoiceViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    pdf = view._build_invoice_pdf(invoice, is_receipt=True).content
    text = _text(pdf)
    for value in (THAI_LEGAL_NAME, THAI_ADDRESS, THAI_STACKED):
        assert value in text, value
    _assert_thai_in_sarabun(pdf)


@pytest.mark.django_db
def test_proforma_prints_thai_bill_to():
    from django.conf import settings
    from crm_app.proforma_pdf import build_proforma_pdf
    from crm_app.views import format_address_multiline
    agreement = _thai_agreement()
    pdf = build_proforma_pdf(
        agreement, entity_profile_for('BMAsia (Thailand) Co., Ltd.'),
        os.path.join(settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png'),
        format_address_multiline=format_address_multiline,
    )
    text = _text(pdf)
    assert THAI_LEGAL_NAME in text, text
    _assert_thai_in_sarabun(pdf)


def test_document_without_thai_embeds_no_thai_font():
    from crm_app.quote_pdf_v2 import build_quote_pdf_v2
    root, address, duration, _sample_invoice, sample_quote = _commercial_fixtures()
    pdf = build_quote_pdf_v2(
        sample_quote(), entity_profile_for('BMAsia (Thailand) Co., Ltd.'),
        str(root / 'crm_app/static/crm_app/images/bmasia_logo.png'), address, duration,
    )
    fonts = {
        str(font.get_object()['/BaseFont']).split('+')[-1]
        for page in PdfReader(BytesIO(pdf)).pages
        for font in page['/Resources']['/Font'].values()
    }
    assert not any(name.startswith('Sarabun') for name in fonts), fonts
