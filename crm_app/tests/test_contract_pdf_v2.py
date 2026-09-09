"""Approved contract design must preserve legal content and read-only review.

These integration tests exercise the same routes used by the CRM, Cira's MCP
client, and the direct renewal-review renderer. Raster visual QA remains a
separate release requirement; PDF text and page size cannot prove alignment.
"""

import base64
import json
import re
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from pypdf import PdfReader
from rest_framework.test import APIClient

from crm_app.mcp import generate_contract_pdf
from crm_app.models import (
    AuditLog, Company, Contract, ContractDocument, ContractTemplate,
    DocumentSequence, EmailLog, User,
)
from crm_app.views import ContractViewSet


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def contract_v2_enabled():
    with override_settings(
        COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True,
        COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True,
    ):
        yield


@pytest.fixture
def operator():
    return User.objects.create_user(
        username="contract-v2-reviewer", email="contract-v2@example.com",
        password="test-only-password", role="Admin", is_active=True,
    )


@pytest.fixture
def client(operator):
    api = APIClient()
    api.force_authenticate(user=operator)
    return api


@pytest.fixture
def contract():
    company = Company.objects.create(
        name="Harbour Music Hotel", legal_entity_name="Harbour Hospitality Limited",
        country="Hong Kong", address_line1="1 Test Harbour Road",
        city="Hong Kong", billing_entity="BMAsia (Thailand) Co., Ltd.",
    )
    agreement = Contract.objects.create(
        company=company, contract_number="TH-CT-V2-FIXTURE", contract_type="Annual",
        contract_category="standard", status="Draft", is_active=False,
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal("260.00"), total_value=Decimal("260.00"),
        tax_rate=Decimal("0.00"), currency="USD", billing_frequency="Annually",
        property_name="Harbour Music Hotel", notes="INTERNAL-ONLY-CRM-TRACKING-SENTINEL",
        customer_contact_name="Alex Example", customer_contact_email="alex@example.com",
        customer_contact_title="General Manager",
        customer_signatory_name="Alex Example", customer_signatory_title="General Manager",
        bmasia_signatory_name="Chris Andrews", bmasia_signatory_title="Director",
        bmasia_contact_name="Norbert Platzer", bmasia_contact_email="norbert@example.com",
    )
    agreement.service_locations.create(
        location_name="Lobby", platform="beatbreeze", price=Decimal("260.00"),
    )
    return agreement


def _reader(content):
    return PdfReader(BytesIO(content))


def _text(content):
    return " ".join(" ".join(page.extract_text() or "" for page in _reader(content).pages).split())


def _writes(captured):
    return [query["sql"] for query in captured.captured_queries if re.match(
        r"^\s*(INSERT|UPDATE|DELETE)\b", query["sql"], flags=re.IGNORECASE,
    )]


def _snapshot(contract):
    return {
        "contract": Contract.objects.values().get(pk=contract.pk),
        "company": Company.objects.values().get(pk=contract.company_id),
        "sequences": list(DocumentSequence.objects.order_by("pk").values()),
        "documents": list(ContractDocument.objects.order_by("pk").values()),
        "audit_count": AuditLog.objects.count(),
        "email_count": EmailLog.objects.count(),
    }


def _assert_a4(response):
    assert response.status_code == 200, getattr(response, "data", None)
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    for page in _reader(response.content).pages:
        assert float(page.mediabox.width) == pytest.approx(595.2756, abs=1)
        assert float(page.mediabox.height) == pytest.approx(841.8898, abs=1)


@pytest.mark.parametrize("category,title", [
    ("standard", "PRINCIPAL TERMS"),
    ("corporate_master", "MASTER SERVICE AGREEMENT"),
    ("participation", "PARTICIPATION AGREEMENT"),
])
def test_standard_master_and_generic_participation_download_use_v2(contract, client, category, title):
    contract.contract_category = category
    if category == "participation":
        contract.master_contract = Contract.objects.create(
            company=contract.company, contract_number="TH-CT-V2-MASTER",
            contract_category="corporate_master", status="Draft",
            start_date=contract.start_date, end_date=contract.end_date,
            value=Decimal("260.00"), currency="USD",
        )
    contract.custom_terms = "The agreed custom provision remains binding in every format."
    contract.save()

    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")

    _assert_a4(response)
    text = _text(response.content)
    assert title.casefold() in text.casefold()
    assert "ISSUED BY" in text
    assert "Harbour Hospitality Limited" in text
    assert contract.custom_terms in text
    assert "INTERNAL-ONLY-CRM-TRACKING-SENTINEL" not in text
    assert "CUSTOMER REMARKS" not in text
    assert "Spacer(" not in text
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" not in text
    assert response["Content-Disposition"].startswith("attachment;")


def test_standard_contract_keeps_principal_terms_and_explicit_tailoring(contract, client):
    contract.preamble_custom = "This individually agreed introduction identifies the Parties."
    contract.payment_custom = "Payment is due in USD within 45 days of the invoice date."
    contract.activation_custom = "Activation follows written approval of the agreed schedule."
    contract.custom_terms = "The Lobby zone may use a separate seasonal playlist."
    contract.save()

    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")

    _assert_a4(response)
    text = _text(response.content)
    for expected in (
        contract.preamble_custom, contract.payment_custom,
        contract.activation_custom, contract.custom_terms,
        "These principal terms and the standard terms & conditions comprise together the entire agreement between the parties.",
        "Commencement Date", "Duration", "Lobby", "Beat Breeze", "Alex Example",
    ):
        assert expected in text
    assert text.count(contract.custom_terms) == 1
    assert "INTERNAL-ONLY-CRM-TRACKING-SENTINEL" not in text


def test_full_generic_template_preserves_legal_text_and_includes_tailored_clauses(contract, client):
    template = ContractTemplate.objects.create(
        name="Independent Hospitality Agreement", template_type="preamble",
        pdf_format="standard", content=(
            "<b>AGREED FRAMEWORK</b><br/>"
            "The negotiated liability allocation remains unchanged by the service schedule.<br/>"
            "The legal customer is {{hotel_legal_name}}.<br/>"
            "Payment: {{payment_clause}}<br/>Activation: {{activation_clause}}<br/>"
            "{{zones_table}}<br/>{{signature_blocks}}"
        ),
    )
    contract.preamble_template = template
    contract.payment_custom = "The approved payment deadline is 45 calendar days."
    contract.activation_custom = "The activation date requires written confirmation by both Parties."
    contract.custom_terms = "The specific approved exception is a seasonal Lobby schedule."
    contract.save()
    original_template = ContractTemplate.objects.values().get(pk=template.pk)

    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")

    _assert_a4(response)
    text = _text(response.content)
    for expected in (
        "The negotiated liability allocation remains unchanged by the service schedule.",
        "The legal customer is Harbour Hospitality Limited.",
        contract.payment_custom, contract.activation_custom, contract.custom_terms,
    ):
        assert expected in text
        assert text.count(expected) == 1
    assert "{{" not in text
    assert ContractTemplate.objects.values().get(pk=template.pk) == original_template


def test_existing_template_override_already_present_is_not_duplicated_or_blocked(contract, client):
    contract.preamble_template = ContractTemplate.objects.create(
        name='Approved tailored agreement', template_type='preamble', pdf_format='standard',
        content='The service begins upon written confirmation.<br/>{{zones_table}}<br/>{{signature_blocks}}',
    )
    contract.activation_custom = 'The service begins upon written confirmation.'
    contract.custom_terms = contract.activation_custom
    contract.save()
    response = client.get(f'/api/v1/contracts/{contract.pk}/preview-pdf/')
    _assert_a4(response)
    assert _text(response.content).count(contract.activation_custom) == 1


def test_template_override_without_replaceable_slot_requests_specific_clarification(contract, client):
    contract.preamble_template = ContractTemplate.objects.create(
        name="Fixed Negotiated Payment Agreement", template_type="preamble",
        pdf_format="standard", content=(
            "The Parties agree payment is due immediately.<br/>"
            "{{zones_table}}<br/>{{signature_blocks}}"
        ),
    )
    contract.payment_custom = "Payment is due within 45 days."
    contract.save()
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    assert response.status_code == 422
    detail = str(response.data).casefold()
    assert "clarification_required" in detail
    assert "payment" in detail
    assert "slot" in detail
    assert _writes(captured) == []
    assert _snapshot(contract) == before


def test_thailand_issuer_with_hong_kong_customer_and_usd_is_not_inferred_from_country(contract, client):
    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")
    _assert_a4(response)
    text = _text(response.content)
    assert "BMAsia (Thailand) Co., Ltd." in text
    assert "0105548025073" in text
    assert "USD" in text
    assert "260.00" in text
    assert "278.20" not in text
    assert "7% VAT" not in text
    assert "HSBC" not in text
    assert "34683002-000-05-26-3" not in text


def test_hong_kong_contract_issuer_uses_verified_registration_number(contract, client):
    contract.company.billing_entity = "BMAsia Limited"
    contract.company.save(update_fields=["billing_entity"])
    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")
    _assert_a4(response)
    text = _text(response.content)
    assert "Business Registration Certificate No.: 34683002-000-05-26-3" in text
    assert "0105548025073" not in text


def test_unknown_contract_issuer_fails_without_business_mutation(contract, client):
    Company.objects.filter(pk=contract.company_id).update(billing_entity="Unverified Supplier")
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    assert response.status_code == 422
    assert _writes(captured) == []
    assert _snapshot(contract) == before


def test_contract_preview_is_watermarked_and_side_effect_free(contract, client):
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    _assert_a4(response)
    assert response["Content-Disposition"].startswith('inline; filename="PREVIEW_ONLY_')
    assert response["Cache-Control"] == "private, no-store, max-age=0"
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" in _text(response.content)
    assert _writes(captured) == []
    assert _snapshot(contract) == before


@pytest.mark.parametrize("live", [False, True])
def test_mcp_nonreserving_contract_pdf_has_no_business_or_audit_writes(contract, operator, live):
    before = _snapshot(contract)
    with override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=live):
        with CaptureQueriesContext(connection) as captured:
            payload = json.loads(generate_contract_pdf(str(contract.pk)))
    assert set(payload) == {"filename", "size", "content_b64"}
    content = base64.b64decode(payload["content_b64"])
    assert content.startswith(b"%PDF-")
    assert len(content) == payload["size"]
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" not in _text(content)
    assert _writes(captured) == []
    assert _snapshot(contract) == before


@pytest.mark.parametrize("method", [
    "_generate_principal_terms_pdf", "_generate_master_agreement_pdf",
    "_generate_participation_agreement_pdf",
])
def test_direct_renewal_style_generator_uses_v2_without_audit_mutation(contract, method):
    request = RequestFactory().get(f"/api/v1/contracts/{contract.pk}/pdf/")
    request.user = AnonymousUser()
    view = ContractViewSet()
    view.request = request
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as captured:
        response = getattr(view, method)(contract)
    _assert_a4(response)
    assert _writes(captured) == []
    assert _snapshot(contract) == before


def test_long_tailored_contract_retains_every_clause_across_pages(contract, client):
    clauses = [
        f"Clause marker {index:03d}. The Parties agree that the service schedule for "
        "the designated venue will be reviewed in writing, with existing obligations "
        "continuing until a mutually approved replacement takes effect."
        for index in range(1, 49)
    ]
    contract.custom_terms = "\n\n".join(clauses)
    contract.save()
    response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    _assert_a4(response)
    reader = _reader(response.content)
    assert len(reader.pages) >= 3
    text = _text(response.content)
    for clause in clauses:
        assert text.count(clause) == 1
    assert "Alex Example" in text
    # A bare footer/page-number/watermark page must not be emitted at the end.
    assert len(" ".join((reader.pages[-1].extract_text() or "").split())) > 180


def test_long_zone_schedule_splits_cleanly_and_preserves_each_zone(contract, client):
    contract.service_locations.all().delete()
    names = [f"Venue-zone-{index:03d}" for index in range(1, 41)]
    for name in names:
        contract.service_locations.create(
            location_name=name, platform="beatbreeze", price=Decimal("260.00"),
        )
    contract.value = contract.total_value = Decimal("10400.00")
    contract.save()
    response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    _assert_a4(response)
    reader = _reader(response.content)
    assert len(reader.pages) >= 2
    text = _text(response.content)
    for name in names:
        assert text.count(name) == 1
    assert "10,400.00" in text
    assert "Alex Example" in text


def test_contract_pricing_conflict_is_still_actionable_and_nonmutating(contract, client):
    Contract.objects.filter(pk=contract.pk).update(value=Decimal("999.00"))
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/contracts/{contract.pk}/preview-pdf/")
    assert response.status_code == 409
    assert "pricing" in str(response.data).casefold()
    assert _writes(captured) == []
    assert _snapshot(contract) == before
