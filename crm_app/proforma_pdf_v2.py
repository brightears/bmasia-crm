"""Proforma invoice renderer using the approved BMAsia commercial design."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app.commercial_pdf import (
    CONTENT_WIDTH,
    PRODUCT_COLUMN_WIDTH,
    STANDARD_SERVICE_COPY,
    build_document_pdf,
    clean_text,
    commercial_product_label,
    compact_line_item_description,
    contains_standard_service_copy,
    document_intro,
    document_styles,
    html_text,
    identity_cards,
    is_subscription_product,
    item_table,
    metadata_table,
    money,
    payment_block,
    quantity,
    section_start,
)
from crm_app.quote_pdf import SUBSCRIPTION_CODES, _decimal_value, _short_code


def _format_date(value):
    return value.strftime("%d %b %Y") if value else "Not specified"


def _address_text(format_address_multiline, company):
    value = clean_text(format_address_multiline(company))
    return value.replace("<br/>", "\n").replace("<br />", "\n")


def _stored_totals(contract, entity):
    """Return the exact stored contract amounts without inferring new tax."""
    currency = getattr(contract, "currency", "USD") or "USD"
    value = _decimal_value(getattr(contract, "value", 0))
    tax_amount = _decimal_value(getattr(contract, "tax_amount", 0))
    total_value = _decimal_value(getattr(contract, "total_value", 0)) or (value + tax_amount)
    discount = value + tax_amount - total_value
    rows = []
    if tax_amount > 0 or discount > Decimal("0.005"):
        rows.append(("Subtotal", money(currency, value)))
    if discount > Decimal("0.005"):
        discount_percentage = _decimal_value(getattr(contract, "discount_percentage", 0))
        if not discount_percentage and value:
            discount_percentage = discount / value * Decimal("100")
        rows.append((f"Less discount ({discount_percentage:.0f}%)", f"-{money(currency, discount)}"))
    if tax_amount > 0:
        tax_label = "VAT" if entity.get("billing_entity") == "BMAsia (Thailand) Co., Ltd." else "Tax"
        tax_rate = _decimal_value(getattr(contract, "tax_rate", 0))
        rate = f" ({tax_rate:.0f}%)" if tax_rate else ""
        rows.append((f"{tax_label}{rate}", money(currency, tax_amount)))
    rows.append(("Total payable", money(currency, total_value)))
    return rows


def build_proforma_pdf_v2(
    contract,
    entity,
    logo_path,
    format_address_multiline,
    issue_date=None,
    *,
    preview=False,
):
    """Render an A4 proforma from a contract without accounting-side effects."""
    issue_date = issue_date or date.today()
    company = contract.company
    currency = getattr(contract, "currency", "USD") or "USD"
    contract_number = contract.contract_number or str(contract.id)[:8]
    proforma_number = f"PF-{contract_number}"
    start = getattr(contract, "start_date", None)
    end = getattr(contract, "end_date", None)
    payment_due = _format_date(start) if start and start > issue_date else "Upon receipt"
    service_period = (
        f"{_format_date(start)} - {_format_date(end)}" if start and end else "Not specified"
    )
    official_document = (
        "tax invoice / receipt"
        if entity.get("billing_entity") == "BMAsia (Thailand) Co., Ltd."
        else "invoice / receipt"
    )

    styles = document_styles()
    story = document_intro(
        "Proforma invoice",
        "Advance-payment document only - not a tax invoice. "
        f"An official {official_document} will be issued after payment is received.",
        styles,
    )
    story.append(metadata_table([
        ("Proforma number", proforma_number),
        ("Issued", _format_date(issue_date)),
        ("Payment due", payment_due),
        ("Currency / service period", f"{currency} / {service_period}"),
    ], styles))

    issuer_lines = [entity["name"], entity["address"], f"Phone: {entity['phone']}"]
    if entity.get("tax"):
        issuer_lines.append(f"Tax ID: {entity['tax']}")
    if entity.get("registration_number"):
        issuer_lines.append(
            f"Business Registration Certificate No.: {entity['registration_number']}"
        )
    customer_lines = [
        getattr(company, "legal_entity_name", "") or company.name,
        _address_text(format_address_multiline, company),
    ]
    story.append(identity_cards(
        "Issued by", issuer_lines,
        "Prepared for", customer_lines,
        styles,
    ))

    story.extend(section_start("01", "Services and amount due", styles, minimum_following_height=125))
    line_items = list(contract.line_items.all())
    multi_zone = sum(
        (_decimal_value(getattr(item, "quantity", 0)) for item in line_items
         if is_subscription_product(getattr(item, "product_service", ""))),
        Decimal("0"),
    ) > 1
    show_shared_service_copy = multi_zone and any(
        contains_standard_service_copy(getattr(item, "description", ""))
        for item in line_items
    )
    rows = []
    zone_index = 0
    for item in line_items:
        product = getattr(item, "product_service", "") or "Service"
        code = _short_code(product)
        item_quantity = _decimal_value(getattr(item, "quantity", 0))
        is_subscription = code in SUBSCRIPTION_CODES
        if is_subscription:
            zone_index += 1
        description = compact_line_item_description(
            getattr(item, "description", ""),
            product=product,
            strip_standard_service_copy=show_shared_service_copy,
        )
        if not description:
            if is_subscription and item_quantity == 1:
                description = f"Zone {zone_index:02d}"
            elif is_subscription and item_quantity > 1:
                description = f"{quantity(item_quantity)} zones"
            else:
                description = "Service"
        product_label = commercial_product_label(product)
        product_markup = escape(product_label)
        if product_label == "Beat Breeze":
            product_markup = product_markup.replace(" ", "&#160;")
        unit_price = _decimal_value(getattr(item, "unit_price", 0))
        unit_value = money(currency, unit_price)
        if is_subscription:
            unit_value += "\nper zone / year"
        rows.append([
            Paragraph(product_markup, styles["body"]),
            Paragraph(html_text(description), styles["body"]),
            quantity(item_quantity),
            unit_value,
            money(currency, _decimal_value(getattr(item, "line_total", 0))),
        ])

    if not rows:
        amount = _decimal_value(getattr(contract, "value", 0))
        rows.append([
            "Music service",
            f"{company.name}\n{service_period}",
            "1",
            money(currency, amount),
            money(currency, amount),
        ])
    if show_shared_service_copy:
        story.extend([
            Paragraph(html_text(STANDARD_SERVICE_COPY), styles["small"]),
            Spacer(1, 5),
        ])
    story.extend(item_table(
        ["Service", "Zone / description", "Qty", "Unit price", "Amount"],
        rows,
        [PRODUCT_COLUMN_WIDTH, CONTENT_WIDTH - PRODUCT_COLUMN_WIDTH - 246, 42, 92, 112],
        {2, 3, 4},
        styles,
        amount_columns={3, 4},
        totals=_stored_totals(contract, entity),
    ))

    story.extend(section_start("02", "Payment and remittance", styles, minimum_following_height=210))
    reference = (
        f"Please quote {proforma_number} (contract {contract_number}) with your remittance."
    )
    story.append(KeepTogether([
        Paragraph("PAYMENT REFERENCE", styles["label"]),
        Spacer(1, 3),
        Paragraph(html_text(reference), styles["body"]),
        Spacer(1, 8),
    ]))
    story.extend(payment_block(entity, entity["payment_terms_default"], styles))

    return build_document_pdf(
        story,
        document_title="Proforma invoice",
        document_id=proforma_number,
        entity=entity,
        logo_path=logo_path,
        preview=preview,
    )
