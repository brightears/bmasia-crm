import base64
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from pypdf import PdfReader
from rest_framework.test import APIClient

from crm_app.models import AuditLog, Company, EmailLog, Invoice, Quote, QuoteActivity, User
from crm_app.mcp import generate_invoice_pdf, generate_quote_pdf


pytestmark = pytest.mark.django_db


def _user(role):
    return User.objects.create_user(
        username=f"preview-{role.lower()}",
        email=f"preview-{role.lower()}@example.com",
        password="test-only-password",
        role=role,
        is_active=True,
    )


def _company():
    return Company.objects.create(
        name="Preview Fixture Hotel",
        legal_entity_name="Preview Fixture Hospitality Limited",
        country="Hong Kong",
        address_line1="1 Test Harbour Road",
        city="Hong Kong",
        billing_entity="BMAsia (Thailand) Co., Ltd.",
    )


def _quote(company, user):
    return Quote.objects.create(
        quote_number="TH-QT-PREVIEW-API",
        company=company,
        status="Draft",
        valid_from=date(2026, 9, 9),
        valid_until=date(2026, 10, 9),
        subtotal=Decimal("1300.00"),
        total_value=Decimal("1300.00"),
        currency="USD",
        notes="Internal quote note.",
        created_by=user,
    )


def _invoice(company):
    return Invoice.objects.create(
        company=company,
        invoice_number="TH-IV-PREVIEW-API",
        status="Draft",
        issue_date=date(2026, 9, 9),
        due_date=date(2026, 9, 9) + timedelta(days=30),
        amount=Decimal("1300.00"),
        total_amount=Decimal("1300.00"),
        currency="USD",
        notes="Internal invoice note.",
    )


def _write_queries(captured):
    return [
        query["sql"]
        for query in captured.captured_queries
        if re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", query["sql"], flags=re.IGNORECASE)
    ]


def _pdf_text(pdf_bytes):
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_quote_preview_is_inline_watermarked_and_side_effect_free():
    user = _user("Sales")
    quote = _quote(_company(), user)
    client = APIClient()
    client.force_authenticate(user=user)
    counts_before = (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count())

    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/quotes/{quote.id}/preview-pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    text = _pdf_text(response.content)
    assert response["Content-Disposition"].startswith('inline; filename="PREVIEW_ONLY_')
    assert response["Cache-Control"] == "private, no-store, max-age=0"
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" in text
    assert "Internal quote note." not in text
    assert "CUSTOMER REMARKS" not in text
    assert _write_queries(captured) == []
    assert (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count()) == counts_before


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_invoice_preview_is_inline_watermarked_and_side_effect_free():
    user = _user("Finance")
    invoice = _invoice(_company())
    client = APIClient()
    client.force_authenticate(user=user)
    counts_before = (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count())

    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/invoices/{invoice.id}/preview-pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    text = _pdf_text(response.content)
    assert response["Content-Disposition"].startswith('inline; filename="PREVIEW_ONLY_')
    assert response["Cache-Control"] == "private, no-store, max-age=0"
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" in text
    assert "Internal invoice note." not in text
    assert "CUSTOMER REMARKS" not in text
    assert _write_queries(captured) == []
    assert (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count()) == counts_before


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_invoice_preview_preserves_existing_authenticated_read_access():
    user = _user("Sales")
    invoice = _invoice(_company())
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/invoices/{invoice.id}/preview-pdf/")

    assert response.status_code == 200


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_preview_rejects_anonymous_and_inactive_users():
    active_user = _user("Tech")
    inactive_user = _user("Music")
    inactive_user.is_active = False
    inactive_user.save(update_fields=["is_active"])
    quote = _quote(_company(), active_user)

    anonymous = APIClient().get(f"/api/v1/quotes/{quote.id}/preview-pdf/")
    inactive_client = APIClient()
    inactive_client.force_authenticate(user=inactive_user)
    inactive = inactive_client.get(f"/api/v1/quotes/{quote.id}/preview-pdf/")

    assert anonymous.status_code in {401, 403}
    assert inactive.status_code == 403


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=False)
def test_preview_flag_off_returns_not_found_without_activity():
    user = _user("Admin")
    quote = _quote(_company(), user)
    client = APIClient()
    client.force_authenticate(user=user)
    before = QuoteActivity.objects.count()

    response = client.get(f"/api/v1/quotes/{quote.id}/preview-pdf/")

    assert response.status_code == 404
    assert QuoteActivity.objects.count() == before


@override_settings(
    COMMERCIAL_DOCUMENT_V2_QUOTE_LIVE=False,
    COMMERCIAL_DOCUMENT_V2_INVOICE_LIVE=False,
)
def test_mcp_pdf_generation_keeps_payload_schema_and_does_not_write_activity():
    user = _user("Admin")
    company = _company()
    quote = _quote(company, user)
    invoice = _invoice(company)
    counts_before = (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count())

    with CaptureQueriesContext(connection) as captured:
        quote_payload = json.loads(generate_quote_pdf(str(quote.id)))
        invoice_payload = json.loads(generate_invoice_pdf(str(invoice.id)))

    for payload in (quote_payload, invoice_payload):
        assert set(payload) == {"filename", "size", "content_b64"}
        pdf_bytes = base64.b64decode(payload["content_b64"])
        assert pdf_bytes.startswith(b"%PDF-")
        assert payload["size"] == len(pdf_bytes)
    assert _write_queries(captured) == []
    assert (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count()) == counts_before


@pytest.mark.parametrize("live", [False, True])
def test_ordinary_quote_download_remains_attachment_and_records_activity(live):
    user = _user("Sales")
    quote = _quote(_company(), user)
    client = APIClient()
    client.force_authenticate(user=user)

    with override_settings(COMMERCIAL_DOCUMENT_V2_QUOTE_LIVE=live):
        response = client.get(f"/api/v1/quotes/{quote.id}/pdf/")

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="Quote_')
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" not in _pdf_text(response.content)
    assert QuoteActivity.objects.filter(quote=quote, activity_type="Viewed").count() == 1


@pytest.mark.parametrize("live", [False, True])
def test_ordinary_invoice_download_remains_attachment_and_records_audit(live):
    user = _user("Finance")
    invoice = _invoice(_company())
    client = APIClient()
    client.force_authenticate(user=user)
    before = AuditLog.objects.count()

    with override_settings(COMMERCIAL_DOCUMENT_V2_INVOICE_LIVE=live):
        response = client.get(f"/api/v1/invoices/{invoice.id}/pdf/")

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="Invoice_')
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" not in _pdf_text(response.content)
    assert AuditLog.objects.count() == before + 1


@override_settings(
    COMMERCIAL_DOCUMENT_V2_INVOICE_LIVE=True,
    COMMERCIAL_DOCUMENT_V2_RECEIPT_LIVE=False,
)
def test_receipt_release_is_independent_from_invoice_release():
    user = _user("Finance")
    invoice = _invoice(_company())
    invoice.receipt_number = "TH-RCP-PREVIEW-API"
    invoice.status = "Paid"
    invoice.save(update_fields=["receipt_number", "status"])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/invoices/{invoice.id}/receipt-pdf/")

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith(
        'attachment; filename="Receipt_Tax_Invoice_'
    )
    page_width = float(PdfReader(BytesIO(response.content)).pages[0].mediabox.width)
    assert abs(page_width - 612.0) < 1


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_receipt_preview_is_watermarked_and_side_effect_free():
    user = _user("Finance")
    invoice = _invoice(_company())
    invoice.receipt_number = "TH-RCP-PREVIEW-API"
    invoice.paid_date = date(2026, 9, 10)
    invoice.status = "Paid"
    invoice.save(update_fields=["receipt_number", "paid_date", "status", "total_amount"])
    client = APIClient()
    client.force_authenticate(user=user)
    counts_before = (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count())

    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/invoices/{invoice.id}/preview-receipt-pdf/")

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('inline; filename="PREVIEW_ONLY_Receipt_')
    assert "DRAFT PREVIEW - NOT FOR CUSTOMER" in _pdf_text(response.content)
    assert _write_queries(captured) == []
    assert (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count()) == counts_before


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_receipt_preview_without_receipt_number_is_side_effect_free_error():
    user = _user("Finance")
    invoice = _invoice(_company())
    client = APIClient()
    client.force_authenticate(user=user)
    counts_before = (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count())

    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/invoices/{invoice.id}/preview-receipt-pdf/")

    assert response.status_code == 400
    assert _write_queries(captured) == []
    assert (QuoteActivity.objects.count(), AuditLog.objects.count(), EmailLog.objects.count()) == counts_before


@override_settings(COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True)
def test_preview_fails_closed_for_unknown_billing_entity_without_activity():
    user = _user("Sales")
    company = _company()
    company.billing_entity = "Unsupported Issuer"
    company.save(update_fields=["billing_entity"])
    quote = _quote(company, user)
    client = APIClient()
    client.force_authenticate(user=user)
    before = QuoteActivity.objects.count()

    response = client.get(f"/api/v1/quotes/{quote.id}/preview-pdf/")

    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_BILLING_ENTITY"
    assert QuoteActivity.objects.count() == before
