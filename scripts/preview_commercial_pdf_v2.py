#!/usr/bin/env python3
"""Render sanitized v2 quotation and invoice previews without Django or CRM writes."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm_app.commercial_pdf import entity_profile_for
from crm_app.invoice_pdf_v2 import build_invoice_pdf_v2
from crm_app.quote_pdf_v2 import build_quote_pdf_v2


class RelatedList:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


def format_duration(months):
    if not months or months <= 0:
        return "As specified"
    if months == 1:
        return "1 month"
    if months < 12:
        return f"{months} months"
    if months == 12:
        return "1 year"
    if months % 12 == 0:
        years = months // 12
        return f"{years} years"
    years, remainder = divmod(months, 12)
    return f"{years} years and {remainder} months"


def format_address_multiline(company):
    values = [
        company.address_line1,
        company.address_line2,
        company.city,
        company.state,
        company.postal_code,
        company.country,
    ]
    return "<br/>".join(value for value in values if value and value != "Other")


def sample_company():
    # Synthetic matrix fixture: a Hong Kong customer issued from Thailand in USD.
    return SimpleNamespace(
        name="Harbour Light Hospitality",
        legal_entity_name="Harbour Light Hospitality Limited",
        branch="",
        tax_id="",
        address_line1="18 Harbour View Road",
        address_line2="Suite 1208",
        city="Hong Kong",
        state="",
        postal_code="",
        country="Hong Kong",
        billing_entity="BMAsia (Thailand) Co., Ltd.",
    )


def sample_quote():
    company = sample_company()
    contact = SimpleNamespace(
        name="Alex Morgan",
        email="alex.morgan@example.com",
        phone="+852 5555 0101",
    )
    items = []
    for index in range(1, 29):
        quantity = Decimal("1")
        unit_price = Decimal("260.00")
        items.append(SimpleNamespace(
            product_service="beatbreeze",
            description=(
                f"Venue zone {index:02d} - managed music service with curated scheduling "
                "and remote onboarding"
            ),
            quantity=quantity,
            unit_price=unit_price,
            unit_value=None,
            line_total=quantity * unit_price,
        ))
    items.append(SimpleNamespace(
        product_service="Soundtrack Player",
        description="Playback hardware supplied for the launch configuration",
        quantity=Decimal("2"),
        unit_price=Decimal("0"),
        unit_value=Decimal("250"),
        line_total=Decimal("0"),
    ))
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    return SimpleNamespace(
        quote_number="TH-QT-PREVIEW-001",
        company=company,
        contact=contact,
        valid_from=date(2026, 9, 9),
        valid_until=date(2026, 10, 9),
        contract_duration_months=12,
        currency="USD",
        subtotal=subtotal,
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_value=subtotal,
        billing_frequency="annual",
        payment_schedule="Billed annually.",
        terms_conditions="",
        notes="Customer-facing assumptions are shown once only when deliberately supplied.",
        line_items=RelatedList(items),
    )


def sample_invoice():
    company = sample_company()
    items = []
    for index in range(1, 33):
        start = date(2026, 10, 1) + timedelta(days=index - 1)
        items.append(SimpleNamespace(
            product_service="Beat Breeze",
            description=(
                f"Managed music service - venue zone {index:02d} with a deliberately long "
                "description to exercise safe row and page breaking"
            ),
            quantity=Decimal("1"),
            unit_price=Decimal("1300.00"),
            service_period_start=start,
            service_period_end=date(2027, 9, 30),
        ))
    amount = sum((item.quantity * item.unit_price for item in items), Decimal("0"))
    return SimpleNamespace(
        invoice_number="TH-INV-PREVIEW-001",
        receipt_number="TH-RCP-PREVIEW-001",
        status="Draft",
        issue_date=date(2026, 9, 9),
        due_date=date(2026, 10, 9),
        paid_date=None,
        currency="USD",
        amount=amount,
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=amount,
        company=company,
        contract=None,
        property_name="Harbour Light Hotel",
        service_period_start=date(2026, 10, 1),
        service_period_end=date(2027, 9, 30),
        payment_terms="Net 30",
        payment_terms_text="",
        notes="Please quote the invoice number with the bank transfer.",
        line_items=RelatedList(items),
    )


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bmasia-commercial-v2")
    output_dir.mkdir(parents=True, exist_ok=True)
    logo = ROOT / "crm_app/static/crm_app/images/bmasia_logo.png"
    entity = entity_profile_for("BMAsia (Thailand) Co., Ltd.")

    quote_path = output_dir / "quotation-preview-v2.pdf"
    quote_path.write_bytes(build_quote_pdf_v2(
        sample_quote(),
        entity,
        str(logo),
        format_address_multiline,
        format_duration,
        preview=True,
    ))

    invoice_path = output_dir / "invoice-preview-v2.pdf"
    invoice_path.write_bytes(build_invoice_pdf_v2(
        sample_invoice(),
        entity,
        str(logo),
        format_address_multiline,
        preview=True,
    ))

    print(quote_path)
    print(invoice_path)


if __name__ == "__main__":
    main()
