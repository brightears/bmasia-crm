"""Thai text together with the contract layout rules added alongside it.

* Wording that prints as plain text because its formatting tags do not pair
  up (stored_markup -> markup_as_text) still switches Thai runs to Sarabun
  and keeps the stored characters.
* A filled template value whose hyphens are written as "&#45;" keeps its
  Thai runs in Sarabun.
* The Commencement Date / Duration grouping (KeepTogether) measures Thai
  wording placed under the Duration clause with the Thai font, so the two
  clauses still share a page across the foot of page one.
* The legacy receipt escapes stored text and prints Thai in Sarabun.

Invented names and wording only.
"""
import re

import pytest

from crm_app.models import ContractTemplate, User
from crm_app.tests import test_contract_commencement_duration_pagination as clause_flow
from crm_app.tests.test_pdf_thai_text import (
    THAI_LEGAL_NAME, THAI_STACKED, _assert_thai_in_sarabun, _render_contract, _text, _thai_agreement,
)

pytestmark = pytest.mark.django_db

THAI_UNDER_DURATION = (
    '[under: duration]\n'
    'ก่อนสิ้นสุดระยะเวลา ผู้ให้บริการตัวอย่างจะส่งข้อเสนอเป็นหนังสือถึงลูกค้าตัวอย่าง '
    'เพื่อให้บริการต่อ อย่างน้อยสี่สิบห้าวันล่วงหน้า ที่ปรึกษา ชื่อ น้ำ\n\n'
    'การต่ออายุมีผลเมื่อทั้งสองฝ่ายตกลงกันเป็นหนังสือแล้วเท่านั้น'
)


def test_wording_printed_as_plain_text_still_switches_thai_font():
    agreement = _thai_agreement()
    # An unclosed <b>: the field prints as text, tags included.
    agreement.custom_terms = f'<b>{THAI_STACKED} F&B'
    agreement.save()
    pdf = _render_contract(agreement)
    text = _text(pdf)
    assert f'<b>{THAI_STACKED} F&B' in text, text
    _assert_thai_in_sarabun(pdf)


def test_filled_value_with_literal_hyphens_keeps_thai_font():
    agreement = _thai_agreement()
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard',
        content='<b>Client:</b> {{legal_entity_name}}<br/>Services: {{service_items}}<br/>'
                '{{additional_terms}}<br/>{{zones_table}}<br/>{{signature_blocks}}',
    )
    agreement.custom_service_items = [{'name': f'-{THAI_STACKED}--ชุดเพลง-', 'description': ''}]
    agreement.save()
    pdf = _render_contract(agreement)
    text = _text(pdf)
    assert f'-{THAI_STACKED}--ชุดเพลง-' in text, text
    assert f'Client: {THAI_LEGAL_NAME}' in text
    _assert_thai_in_sarabun(pdf)


def test_commencement_and_duration_share_a_page_with_thai_wording_under_duration():
    # The renderer used by these layout helpers needs a signed-in reviewer.
    User.objects.create_user(username='thai-clause-flow-reviewer', role='Admin', is_active=True)
    pair_pages = set()
    for extra_lines in range(0, 20):
        pages = clause_flow._pages(clause_flow._contract(extra_lines, THAI_UNDER_DURATION, 'thai'))
        commencement = clause_flow._page_of(pages, clause_flow.COMMENCEMENT)
        duration = clause_flow._page_of(pages, clause_flow.DURATION)
        under = clause_flow._page_of(pages, 'ก่อนสิ้นสุดระยะเวลา')
        assert commencement == duration == under, (extra_lines, commencement, duration, under)
        pair_pages.add(commencement)
    assert pair_pages == {0, 1}


def test_legacy_receipt_escapes_and_prints_thai():
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    from crm_app.models import Invoice, InvoiceLineItem
    from crm_app.tests.test_pdf_thai_text import _thai_company
    from crm_app.views import InvoiceViewSet

    invoice = Invoice.objects.create(
        company=_thai_company(legal_entity_name=f'{THAI_LEGAL_NAME} F&B <สาขา>'),
        invoice_number='TH-IV-THAI-ESC', status='Paid', issue_date=date(2026, 9, 9),
        due_date=date(2026, 10, 9), paid_date=date(2026, 9, 20), amount=Decimal('1300.00'),
        total_amount=Decimal('1300.00'), currency='THB', receipt_number='TH-RCP-THAI-ESC',
        notes=f'{THAI_STACKED} & <หมายเหตุ>',
    )
    InvoiceLineItem.objects.create(
        invoice=invoice, product_service='Soundtrack', description=f'{THAI_STACKED} R&D <A>',
        quantity=Decimal('1'), unit_price=Decimal('1300.00'), tax_rate=Decimal('0'),
    )
    view = InvoiceViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    pdf = view._build_invoice_pdf(invoice, is_receipt=True).content
    text = _text(pdf)
    for value in (f'{THAI_LEGAL_NAME} F&B <สาขา>', f'{THAI_STACKED} R&D <A>'):
        assert value in text, value
    assert not re.search(r'\w&\w+;', text)
    _assert_thai_in_sarabun(pdf)
