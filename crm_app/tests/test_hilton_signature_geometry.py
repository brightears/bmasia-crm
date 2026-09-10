"""Native Hilton pages must not bypass the approved signing-area geometry."""
from collections import Counter
from io import BytesIO
import re
from types import SimpleNamespace

from pypdf import PdfReader
import pytest
from reportlab.platypus import SimpleDocTemplate

from crm_app.tests.test_contract_layout_regressions import _image_boxes, _signature_lines
from crm_app.tests.test_hilton_template_rendering import _contract
from crm_app.views import ContractViewSet


def signing_contract():
    contract = _contract('{{service_product_managed_name}}<br/>{{zones_table}}<br/>{{signature_blocks}}')
    contract.bmasia_signatory_name = 'Chris Andrews'
    contract.bmasia_signatory_title = 'Director'
    contract.additional_customer_signatories = []
    return contract


def test_hilton_native_pdf_aligns_rules_and_contains_both_marks():
    contract = signing_contract()
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    response = view._generate_principal_terms_pdf(contract)
    assert response.status_code == 200
    pages = PdfReader(BytesIO(response.content)).pages
    signing_pages = [p for p in pages if 'Chris Andrews' in (p.extract_text() or '')]
    assert len(signing_pages) == 1
    page = signing_pages[0]
    rules = sorted(_signature_lines(page), key=lambda item: item['x'])
    assert len(rules) == 2
    assert rules[0]['y'] == pytest.approx(rules[1]['y'], abs=1)
    marks = [b for b in _image_boxes(page) if b[1] < rules[0]['y'] + 100]
    assert len(marks) == 2
    for x0, y0, x1, y1 in marks:
        assert 78 <= x0 < x1 <= 306 - 8
        assert -1 <= y0 - rules[0]['y'] <= 14
        assert 0 < y1 - y0 <= 58
    assert '{{' not in ' '.join(p.extract_text() or '' for p in pages)


def test_native_adapter_preserves_signer_words_and_authority(monkeypatch):
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
    assert getattr(aligned, '_bmasia_signature_pairs', False)
    assert len(aligned._cellvalues) == 2


def test_non_hilton_native_signatures_keep_existing_route():
    contract = signing_contract()
    contract.preamble_template.name = 'Independent corporate format'
    table = ContractViewSet()._build_signature_blocks_table(contract, 'BMAsia Limited', 'BMAsia Limited')
    assert not getattr(table, '_bmasia_signature_pairs', False)
