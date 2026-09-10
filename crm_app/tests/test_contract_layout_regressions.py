"""Geometry regressions for the September 2026 principal-terms layout.

The compact Jakarta fixture deliberately reproduces the formerly three-page
contract: a short zone schedule and the signature pair must not acquire pages
of their own. PDF coordinates catch regressions that plain-text tests cannot.
These tests supplement, and do not replace, full-page raster release review.
"""

import base64
import json
import os
import re
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from pypdf import PdfReader

from crm_app.mcp import generate_contract_pdf
from crm_app.models import (
    AuditLog, Company, Contract, ContractDocument, ContractTemplate,
    DocumentSequence, EmailLog, User,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def approved_contract_layout():
    with override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True):
        yield


@pytest.fixture
def jakarta_contract():
    """Synthetic customer; commercially equivalent to the reported failure."""
    User.objects.create_user(
        username="contract-layout-reviewer", email="contract-layout@example.com",
        password="test-only-password", role="Admin", is_active=True,
    )
    company = Company.objects.create(
        name="Example Jakarta", legal_entity_name="Example Jakarta",
        city="Jakarta", country="Indonesia", billing_entity="BMAsia Limited",
    )
    contract = Contract.objects.create(
        company=company, contract_number="DRAFT-LAYOUT-0174",
        contract_type="Annual", contract_category="standard", status="Draft",
        is_active=False, start_date=date(2026, 9, 15), end_date=date(2027, 9, 14),
        value=Decimal("380.00"), total_value=Decimal("380.00"),
        price_per_zone=Decimal("380.00"),
        tax_rate=Decimal("0.00"), currency="USD", billing_frequency="Annually",
        property_name="Example Jakarta", notes="PRIVATE-LAYOUT-TEST-NOTE",
    )
    contract.service_locations.create(
        location_name="Lobby", platform="soundtrack", price=Decimal("380.00"),
    )
    return contract


def _compact(text):
    return " ".join(text.split())


def _render(contract):
    result = json.loads(generate_contract_pdf(str(contract.pk)))
    assert set(result) == {"filename", "size", "content_b64"}, result
    content = base64.b64decode(result["content_b64"], validate=True)
    assert len(content) == result["size"]
    if os.environ.get("CONTRACT_LAYOUT_REVIEW_DIR"):
        review_dir = Path(os.environ["CONTRACT_LAYOUT_REVIEW_DIR"])
        review_dir.mkdir(parents=True, exist_ok=True)
        test_name = os.environ.get("PYTEST_CURRENT_TEST", "contract-layout").split("::")[-1].split(" ")[0]
        review_name = re.sub(r"[^a-zA-Z0-9_-]", "_", test_name)
        (review_dir / f"{review_name}.pdf").write_bytes(content)
    reader = PdfReader(BytesIO(content))
    for page in reader.pages:
        assert float(page.mediabox.width) == pytest.approx(595.276, abs=1)
        assert float(page.mediabox.height) == pytest.approx(841.890, abs=1)
    return reader


def _page_text(page):
    return _compact(page.extract_text() or "")


def _text_positions(page):
    """Transform text-space origins into page space (including nested tables)."""
    positions = []

    def visit(text, cm, tm, font, size):
        if text.strip():
            positions.append({
                "text": _compact(text),
                "x": tm[4] * cm[0] + tm[5] * cm[2] + cm[4],
                "y": tm[4] * cm[1] + tm[5] * cm[3] + cm[5],
            })

    page.extract_text(visitor_text=visit)
    return positions


def _signature_lines(page):
    # New templates use real horizontal rules rather than printable underscore
    # strings. Exclude the full-width page/table rules by their measured length.
    lines, start = [], None

    def point(x, y, cm):
        x, y = float(x), float(y)
        return x * cm[0] + y * cm[2] + cm[4], x * cm[1] + y * cm[3] + cm[5]

    def visit(operator, operands, cm, tm):
        nonlocal start
        if operator == b"m":
            start = point(*operands, cm)
        elif operator == b"l" and start is not None:
            end = point(*operands, cm)
            length = abs(end[0] - start[0])
            if abs(end[1] - start[1]) < .1 and 175 <= length <= 250:
                lines.append({"x": min(start[0], end[0]), "y": start[1]})
            start = end
        elif operator in (b"n", b"S", b"s", b"f", b"F", b"f*"):
            start = None

    page.extract_text(visitor_operand_before=visit)
    if lines:
        return lines
    # Keeping this fallback makes the pre-repair rendering fail the baseline
    # assertion for the actual visual defect, not merely a representation change.
    return [item for item in _text_positions(page)
            if re.fullmatch(r"_{8,}", item["text"])]


def _image_boxes(page):
    """Actual drawn image bounds, not source PNG dimensions or cell estimates."""
    boxes = []
    resources = page["/Resources"].get_object()
    objects = resources.get("/XObject")
    if objects is None:
        return boxes
    objects = objects.get_object()

    def visit(operator, operands, cm, tm):
        if operator != b"Do":
            return
        obj = objects[operands[0]].get_object()
        if obj.get("/Subtype") != "/Image":
            return
        corners = [(cm[0] * x + cm[2] * y + cm[4],
                    cm[1] * x + cm[3] * y + cm[5])
                   for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))]
        boxes.append((min(x for x, y in corners), min(y for x, y in corners),
                      max(x for x, y in corners), max(y for x, y in corners)))

    page.extract_text(visitor_operand_before=visit)
    return boxes


def _snapshot(contract):
    return {
        "contract": Contract.objects.values().get(pk=contract.pk),
        "company": Company.objects.values().get(pk=contract.company_id),
        "zones": list(contract.service_locations.order_by("pk").values()),
        "templates": list(ContractTemplate.objects.order_by("pk").values()),
        "sequences": list(DocumentSequence.objects.order_by("pk").values()),
        "documents": list(ContractDocument.objects.order_by("pk").values()),
        "audit_count": AuditLog.objects.count(),
        "email_count": EmailLog.objects.count(),
    }


def test_short_principal_terms_use_two_pages_without_stranded_zones_or_signatures(jakarta_contract):
    reader = _render(jakarta_contract)
    assert len(reader.pages) <= 2, "Short principal terms must not have a signature-only third page"
    assert "Zone 1: Lobby" in _page_text(reader.pages[0]), "A small zone schedule belongs with its introduction"
    last = _page_text(reader.pages[-1])
    assert "9. Contacts:" in last
    assert "norbert@bmasiamusic.com" in last
    assert "Chris Andrews" in last
    assert "Authorized Representative" in last
    assert "Service Packages - Music Design & Management" in last
    assert "Price: USD 380.00 per zone per year" in last


def test_nested_keep_together_measures_the_actual_small_table():
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import KeepTogether, Paragraph, Table
    from crm_app.commercial_pdf import CONTENT_WIDTH, document_styles
    from crm_app.contract_pdf_v2 import _flowables
    styles = document_styles()
    source = KeepTogether([
        Paragraph('Locations for provision of services:', styles['body']),
        KeepTogether([Table([['Property', 'Zone'], ['Example', 'Lobby']])]),
    ])
    result = _flowables([source], CONTENT_WIDTH, styles)
    assert isinstance(result[0], KeepTogether)
    assert not any(isinstance(child, KeepTogether) for child in result[0]._content)
    result[0].wrapOn(Canvas(BytesIO()), CONTENT_WIDTH, 700)
    assert result[0]._H < 200


def test_unrecognized_nested_signing_content_falls_back_without_losing_text(jakarta_contract):
    from reportlab.platypus import Paragraph, Table
    from crm_app.commercial_pdf import CONTENT_WIDTH, document_styles
    from crm_app.contract_pdf_v2 import _signature_table
    from crm_app.views import ContractViewSet
    styles = document_styles()
    source = ContractViewSet()._build_signature_blocks_table(jakarta_contract, 'BMAsia Limited', 'BMAsia Limited')
    source._cellvalues[0][0]._cellvalues[0][0] = Table([[Paragraph('Additional signing authority must be retained.', styles['body'])]])
    assert _signature_table(source, CONTENT_WIDTH, styles) is None


def test_signature_rules_share_a_baseline_and_supplier_artwork_is_never_embedded(jakarta_contract):
    page = _render(jakarta_contract).pages[-1]
    rules = sorted(_signature_lines(page), key=lambda item: item["x"])
    assert len(rules) == 2
    left, right = rules
    middle = float(page.mediabox.width) / 2
    assert left["x"] < middle < right["x"]
    assert left["y"] == pytest.approx(right["y"], abs=1), "Supplier and customer signing lines drifted"

    # The repeated page-header logo sits above this region. The supplier line
    # itself must remain blank for manual signature and stamping.
    marks = [box for box in _image_boxes(page) if box[1] < left["y"] + 100]
    assert marks == [], "Supplier signature or stamp artwork must be added manually"


def test_compact_layout_preserves_every_principal_clause_and_has_no_business_writes(jakarta_contract):
    before = _snapshot(jakarta_contract)
    with CaptureQueriesContext(connection) as captured:
        reader = _render(jakarta_contract)
    text = _compact(" ".join(_page_text(page) for page in reader.pages))
    for phrase in (
        "These principal terms and the standard terms & conditions comprise together the entire agreement between the parties.",
        "Locations for provision of services:",
        "Commencement Date: 15 September 2026",
        "Duration: 1 year from 15 September 2026 to 14 September 2027",
        "Service Packages - Music Design & Management",
        "Assistance to design playlists and schedules on the SYB platform",
        "Remote on-line activation assistance",
        "Monthly refresh of music content",
        "Special event playlists as needed",
        "First Line Technical Support",
        "Price: USD 380.00 per zone per year",
        "Total cost: USD 380.00 for 1 zone",
        "Terms of payment: by bank transfer on a net received, paid in full basis, with no offset to BMA's HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription.",
        "All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.",
        "HSBCHKHHHKH", "808-021570-838",
        "Activation Date: Music service will be activated within 3 business days of receipt of payment and completion of account setup.",
        "9. Contacts:", "Chris Andrews", "Authorized Representative",
    ):
        assert text.count(phrase) == 1, phrase
    assert "PRIVATE-LAYOUT-TEST-NOTE" not in text
    assert "CUSTOMER REMARKS" not in text
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" not in text
    writes = [item["sql"] for item in captured.captured_queries
              if re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", item["sql"], re.I)]
    assert writes == []
    assert _snapshot(jakarta_contract) == before


def test_long_zone_schedule_repeats_headers_and_keeps_each_zone_once(jakarta_contract):
    jakarta_contract.service_locations.all().delete()
    names = [f"Level {index:02d} reception and hospitality lounge" for index in range(1, 37)]
    for name in names:
        jakarta_contract.service_locations.create(
            location_name=name, platform="soundtrack", price=Decimal("380.00"),
        )
    jakarta_contract.value = jakarta_contract.total_value = Decimal("13680.00")
    jakarta_contract.save()
    reader = _render(jakarta_contract)
    texts = [_page_text(page) for page in reader.pages]
    combined = " ".join(texts)
    zone_pages = [text for text in texts if any(name in text for name in names)]
    assert len(zone_pages) >= 2, "Fixture must exercise a split service-location table"
    for text in zone_pages:
        assert "Property Service Zone Price/Zone" in text
    for name in names:
        assert combined.count(name) == 1
    assert "13,680.00" in combined
    assert "Chris Andrews" in texts[-1]
    assert "Authorized Representative" in texts[-1]
    assert "9. Contacts:" in texts[-1], "Closing context must accompany a signing continuation"


def test_template_signature_pairs_allow_long_names_and_preserve_poa_on_same_page(jakarta_contract):
    jakarta_contract.customer_signatory_name = "Alexandra Catherine Example-Wellington"
    jakarta_contract.customer_signatory_title = "Regional Director of Property and Facilities Management"
    additional = [
        {
            "name": f"Additional Authorized Representative {index:02d} Example-Wellington",
            "title": "Director of Commercial Property and Asset Management",
            "legal_entity_name": f"Example Hospitality and Property Management Entity {index:02d} Limited",
            "poa_reference": f"JAKARTA-POA-2026-{index:02d}, executed on 01 September 2026",
        }
        for index in range(1, 4)
    ]
    jakarta_contract.additional_customer_signatories = additional
    jakarta_contract.preamble_template = ContractTemplate.objects.create(
        name="Synthetic multi-signatory layout agreement", template_type="preamble",
        pdf_format="standard", content=(
            "Supplier: {{issuer_name}}.<br/><br/>"
            "The approved rights and obligations are unchanged by signature formatting.<br/><br/>"
            "{{zones_table}}<br/><br/>{{signature_blocks}}"
        ),
    )
    jakarta_contract.save()
    before = _snapshot(jakarta_contract)
    reader = _render(jakarta_contract)
    texts = [_page_text(page) for page in reader.pages]
    combined = " ".join(texts)
    assert combined.count("The approved rights and obligations are unchanged by signature formatting.") == 1
    primary_page = next(page for page in reader.pages if "Chris Andrews" in _page_text(page))
    assert jakarta_contract.customer_signatory_name in _page_text(primary_page)
    primary_rules = sorted(_signature_lines(primary_page), key=lambda item: (-item["y"], item["x"]))[:2]
    assert len(primary_rules) == 2
    assert primary_rules[0]["y"] == pytest.approx(primary_rules[1]["y"], abs=1)
    for signatory in additional:
        matching = [text for text in texts if signatory["name"] in text]
        assert len(matching) == 1
        assert signatory["title"] in matching[0]
        assert signatory["legal_entity_name"] in matching[0]
        assert f"POA: {signatory['poa_reference']}" in matching[0]
        assert "Date: _________________" in matching[0]
    assert _snapshot(jakarta_contract) == before
