"""Native Hilton pages must not bypass the approved signing-area geometry."""
from collections import Counter
from decimal import Decimal
from io import BytesIO
import re
from types import SimpleNamespace

from pypdf import PdfReader
import pytest
from django.test import override_settings
from reportlab.lib.pagesizes import A4
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate

from crm_app.commercial_pdf import CONTENT_WIDTH, document_styles
from crm_app.contract_pdf_v2 import _flowables
from crm_app.tests.test_contract_layout_regressions import _image_boxes, _signature_lines
from crm_app.tests.test_hilton_template_rendering import FakeRelatedManager, _contract
from crm_app.views import ContractViewSet


def signing_contract():
    contract = _contract('{{service_product_managed_name}}<br/>{{zones_table}}<br/>{{signature_blocks}}')
    contract.bmasia_signatory_name = 'Chris Andrews'
    contract.bmasia_signatory_title = 'Director'
    contract.additional_customer_signatories = []
    return contract


@override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True)
def test_hilton_uses_approved_v2_design_with_blank_aligned_signing_area():
    contract = signing_contract()
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    response = view._generate_principal_terms_pdf(contract)
    assert response.status_code == 200
    assert response['X-BMAsia-Renderer'] == 'contract-v2'
    pages = PdfReader(BytesIO(response.content)).pages
    assert all(float(page.mediabox.width) == pytest.approx(A4[0], abs=1)
               and float(page.mediabox.height) == pytest.approx(A4[1], abs=1)
               for page in pages)
    first_text = pages[0].extract_text() or ''
    assert 'Hotel participation agreement' in first_text
    assert 'ISSUED BY' in first_text and 'PREPARED FOR' in first_text
    signing_pages = [p for p in pages if 'Chris Andrews' in (p.extract_text() or '')]
    assert len(signing_pages) == 1
    page = signing_pages[0]
    all_column_rules = _signature_lines(page)
    signing_y = min(item['y'] for item in all_column_rules)
    rules = sorted(
        (item for item in all_column_rules if abs(item['y'] - signing_y) <= .1),
        key=lambda item: item['x'],
    )
    assert len(rules) == 2
    assert rules[0]['y'] == pytest.approx(rules[1]['y'], abs=1)
    marks = [b for b in _image_boxes(page) if b[1] < rules[0]['y'] + 100]
    assert marks == [], 'Hilton signing artwork is intentionally added manually'
    assert '{{' not in ' '.join(p.extract_text() or '' for p in pages)


@override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=False)
def test_signing_blocks_preserve_signer_words_and_authority_without_artwork(monkeypatch):
    contract = signing_contract()
    contract.customer_signatory_name = 'Alexandra Example'
    contract.customer_signatory_title = 'Authorized Signatory'
    contract.additional_customer_signatories = [{'name': 'Second Signatory',
        'title': 'Director', 'legal_entity_name': 'Second Legal Entity',
        'poa_reference': 'POA-2026-VERIFIED'}]
    view = ContractViewSet()
    aligned = view._build_signature_blocks_table(contract, 'BMAsia Limited', 'BMAsia Limited')
    monkeypatch.setattr(view, '_is_hilton_full_template', lambda _: False)
    legacy = view._build_signature_blocks_table(contract, 'BMAsia Limited', 'BMAsia Limited')
    def words(table):
        output = BytesIO()
        SimpleDocTemplate(output).build([table])
        text = ' '.join(p.extract_text() or '' for p in PdfReader(BytesIO(output.getvalue())).pages)
        return Counter(re.sub(r'_+', '', text).split())
    assert words(aligned) == words(legacy)
    for table in (aligned, legacy):
        output = BytesIO()
        SimpleDocTemplate(output).build([table])
        assert all(_image_boxes(page) == [] for page in PdfReader(BytesIO(output.getvalue())).pages)


def test_non_hilton_native_signatures_keep_existing_route():
    contract = signing_contract()
    contract.preamble_template.name = 'Independent corporate format'
    table = ContractViewSet()._build_signature_blocks_table(contract, 'BMAsia Limited', 'BMAsia Limited')
    assert not getattr(table, '_bmasia_signature_pairs', False)

    output = BytesIO()
    SimpleDocTemplate(output).build([table])
    pages = PdfReader(BytesIO(output.getvalue())).pages
    assert all(_image_boxes(page) == [] for page in pages)


@override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True)
def test_hilton_template_identity_can_never_select_the_retired_design():
    contract = signing_contract()
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    assert view._contract_v2_enabled(contract) is True
    response = view._generate_principal_terms_pdf(contract)
    assert response['X-BMAsia-Renderer'] == 'contract-v2'


@override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=False)
def test_parent_hilton_participation_route_also_uses_approved_v2_design():
    contract = signing_contract()
    # Exercise the separate parent-company CorporatePdfTemplate route rather
    # than the maintained full-text Hilton ContractTemplate route above.
    contract.preamble_template.name = 'Independent participation source'
    contract.preamble_template.id = 999
    contract.contract_category = 'participation'
    contract.master_contract = None
    contract.monthly_value = Decimal('21.67')
    contract.company.full_address = '1 Garden Road, Guangzhou, Guangdong 510000, China'
    contract.company.contacts = FakeRelatedManager([])
    contract.company.parent_company = SimpleNamespace(
        pdf_template=SimpleNamespace(
            template_format='hilton_hpa',
            warranty_text='Approved supplier warranty text.',
            legal_terms='<b>1. APPROVED CORPORATE TERMS</b><br/>Preserved legal body.',
        )
    )

    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    response = view._generate_participation_agreement_pdf(contract)

    assert response.status_code == 200
    assert response['X-BMAsia-Renderer'] == 'contract-v2'
    pages = PdfReader(BytesIO(response.content)).pages
    assert pages
    assert all(float(page.mediabox.width) == pytest.approx(A4[0], abs=1)
               and float(page.mediabox.height) == pytest.approx(A4[1], abs=1)
               for page in pages)
    text = '\n'.join(page.extract_text() or '' for page in pages)
    assert 'Hotel participation agreement' in text
    assert 'ATTACHMENT A TO HPA' in text
    assert 'EXHIBIT D' in text
    assert 'APPROVED CORPORATE TERMS' in text
    signing_page = next(page for page in pages if 'Chris Andrews' in (page.extract_text() or ''))
    assert 'IN WITNESS WHEREOF' in (signing_page.extract_text() or '')
    assert [box for box in _image_boxes(signing_page) if box[1] < 700] == []


def test_explicit_legal_lines_are_split_before_reportlab_pagination():
    styles = document_styles()
    source = Paragraph(
        '17. TERMINATION:<br/>A. First condition;<br/>B. Second condition;'
        '<br/><br/><b>18. POST TERMINATION OBLIGATIONS:</b><br/>Closing text.',
        styles['body'],
    )

    flowables = _flowables([source], CONTENT_WIDTH, styles)
    paragraphs = [item for item in flowables if isinstance(item, Paragraph)]

    assert [item.getPlainText() for item in paragraphs] == [
        '17. TERMINATION:',
        'A. First condition;',
        'B. Second condition;',
        '18. POST TERMINATION OBLIGATIONS:',
        'Closing text.',
    ]
    assert all('<br' not in item.text.lower() for item in paragraphs)
    assert paragraphs[0].style.spaceAfter == 0
    assert paragraphs[2].style.spaceAfter > 0
    assert paragraphs[3].style.keepWithNext


def test_short_hilton_deliverables_list_stays_on_one_page():
    styles = document_styles()
    deliverables = [
        'Music Management - For the term of service',
        'Music Curation - Completed prior to Installation',
        'Music Change Request - Accommodated within 30 days following Installation',
        'Music Playlist/Online Support - For the term of service',
        'Music Content Leasing - For the term of service',
        'Unlimited Festival or special event change of music - As requested by the Hotel',
        'Monthly music refresh - For the term of service',
        'Free Online Install - At time of install',
    ]
    source = Paragraph(
        '<b>3. Deliverables and timelines:</b><br/>' + '<br/>'.join(deliverables)
        + '<br/><br/><b>4. Fees and Payments:</b>',
        styles['body'],
    )

    flowables = _flowables([source], CONTENT_WIDTH, styles)

    assert len(flowables) == 3
    assert isinstance(flowables[0], KeepTogether)
    assert isinstance(flowables[1], KeepTogether)
    first_half = [
        item.getPlainText() for item in flowables[0]._content
        if isinstance(item, Paragraph)
    ]
    second_half = [
        item.getPlainText() for item in flowables[1]._content
        if isinstance(item, Paragraph)
    ]
    assert first_half == ['3. Deliverables and timelines:', *deliverables[:4]]
    assert second_half == deliverables[4:]
    assert flowables[2].getPlainText() == '4. Fees and Payments:'
