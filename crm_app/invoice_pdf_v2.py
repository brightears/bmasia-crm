"""BMAsia invoice and receipt renderer using the shared commercial layout."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape

from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app.commercial_pdf import (
    CONTENT_WIDTH,
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
    PRODUCT_COLUMN_WIDTH,
    STANDARD_SERVICE_COPY,
    section_start,
)


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _format_date(value):
    return value.strftime("%d %b %Y") if value else "Not specified"


def _address_text(format_address_multiline, company):
    value = clean_text(format_address_multiline(company))
    return value.replace("<br/>", "\n").replace("<br />", "\n")


def _invoice_totals(invoice, entity, *, is_receipt=False):
    rows = []
    currency = invoice.currency
    amount = _decimal(invoice.amount)
    discount = _decimal(invoice.discount_amount)
    tax = _decimal(invoice.tax_amount)
    total = _decimal(invoice.total_amount)
    if amount > 0:
        rows.append(("Subtotal", money(currency, amount)))
    if discount > 0:
        percentage = (discount / amount * Decimal("100")) if amount > 0 else Decimal("0")
        rows.append((f"Discount ({percentage:.0f}%)", f"-{money(currency, discount)}"))
    if tax > 0:
        taxable = amount - discount
        percentage = (tax / taxable * Decimal("100")) if taxable > 0 else Decimal("0")
        label = "VAT" if entity.get("billing_entity") == "BMAsia (Thailand) Co., Ltd." else "Tax"
        rows.append((f"{label} ({percentage:.0f}%)", money(currency, tax)))
    rows.append(("Amount paid" if is_receipt else "Amount due", money(currency, total)))
    return rows


def build_invoice_pdf_v2(
    invoice,
    entity,
    logo_path,
    format_address_multiline,
    *,
    is_receipt=False,
    preview=False,
):
    """Render an A4, flow-based invoice/receipt and return raw PDF bytes.

    Invoice notes are internal CRM context and are never rendered. Payment
    terms remain customer-visible in their named section.
    """
    styles = document_styles()
    document_title = "Receipt / Tax Invoice" if is_receipt else "Invoice"
    document_id = invoice.receipt_number if is_receipt else invoice.invoice_number

    story = document_intro(
        document_title,
        "Clear billing details, service coverage and payment information.",
        styles,
    )
    if is_receipt:
        metadata = [
            ("Receipt number", invoice.receipt_number),
            ("Invoice reference", invoice.invoice_number),
            ("Payment date", _format_date(invoice.paid_date)),
            ("Status / currency", f"Paid / {invoice.currency}"),
        ]
    else:
        metadata = [
            ("Invoice number", invoice.invoice_number),
            ("Issue date", _format_date(invoice.issue_date)),
            ("Due date", _format_date(invoice.due_date)),
            ("Status / currency", f"{invoice.status} / {invoice.currency}"),
        ]
    story.append(metadata_table(metadata, styles))

    issuer_lines = [entity["name"], entity["address"], f"Phone: {entity['phone']}"]
    if entity.get("billing_entity") == "BMAsia (Thailand) Co., Ltd.":
        issuer_lines.insert(1, "Head Office")
    if entity.get("tax"):
        issuer_lines.append(f"Tax ID: {entity['tax']}")

    company = invoice.company
    customer_lines = [
        getattr(company, "legal_entity_name", "") or company.name,
    ]
    if getattr(company, "branch", ""):
        customer_lines.append(f"Branch: {company.branch}")
    if getattr(invoice, "property_name", ""):
        customer_lines.append(f"Property: {invoice.property_name}")
    if getattr(company, "tax_id", ""):
        customer_lines.append(f"Tax ID: {company.tax_id}")
    address = _address_text(format_address_multiline, company)
    if address:
        customer_lines.append(address)

    story.append(identity_cards(
        "Issued by", issuer_lines,
        "Bill to", customer_lines,
        styles,
    ))

    if getattr(invoice, "contract", None):
        contract = invoice.contract
        contract_lines = [f"<b>Contract:</b> {escape(clean_text(contract.contract_number))}"]
        if getattr(contract, "service_type", ""):
            contract_lines.append(
                f"<b>Service:</b> {escape(clean_text(contract.get_service_type_display()))}"
            )
        story.append(KeepTogether([
            Paragraph("<br/>".join(contract_lines), styles["body"]),
            Spacer(1, 7),
        ]))

    story.extend(section_start("01", "Invoice details", styles, minimum_following_height=92))
    line_items = list(invoice.line_items.all())
    has_product = any(clean_text(getattr(item, "product_service", "")).strip() for item in line_items)
    multi_zone = sum(
        (_decimal(getattr(item, "quantity", 0)) for item in line_items if is_subscription_product(getattr(item, "product_service", ""))),
        Decimal("0"),
    ) > 1
    show_shared_service_copy = multi_zone and any(
        contains_standard_service_copy(getattr(item, "description", ""))
        for item in line_items
    )
    rows = []
    zone_index = 0

    if line_items:
        for item in line_items:
            item_quantity = _decimal(getattr(item, "quantity", 0))
            is_subscription = is_subscription_product(getattr(item, "product_service", ""))
            if is_subscription:
                zone_index += 1
            description = compact_line_item_description(
                getattr(item, "description", ""),
                product=getattr(item, "product_service", ""),
                strip_standard_service_copy=show_shared_service_copy,
            )
            if not description:
                if is_subscription and item_quantity == 1:
                    description = f"Zone {zone_index:02d}"
                elif is_subscription and item_quantity > 1:
                    description = f"{quantity(item_quantity)} zones"
                else:
                    description = "Service"
            period_start = getattr(item, "service_period_start", None)
            period_end = getattr(item, "service_period_end", None)
            if (
                period_start == getattr(invoice, "service_period_start", None)
                and period_end == getattr(invoice, "service_period_end", None)
            ):
                period_start = None
                period_end = None
            description_markup = html_text(description)
            if period_start and period_end:
                description_markup += (
                    f"<br/><font size='7' color='#66717D'>Service period: "
                    f"{escape(_format_date(period_start))} - {escape(_format_date(period_end))}</font>"
                )
            elif period_start:
                description_markup += (
                    f"<br/><font size='7' color='#66717D'>From: "
                    f"{escape(_format_date(period_start))}</font>"
                )
            description_cell = Paragraph(description_markup, styles["body"])
            unit_price = _decimal(getattr(item, "unit_price", 0))
            line_amount = item_quantity * unit_price
            if has_product:
                product_label = commercial_product_label(getattr(item, "product_service", ""))
                product_markup = escape(product_label)
                if product_label == "Beat Breeze":
                    product_markup = product_markup.replace(" ", "&#160;")
                rows.append([
                    Paragraph(product_markup, styles["body"]),
                    description_cell,
                    quantity(item_quantity),
                    money(invoice.currency, unit_price),
                    money(invoice.currency, line_amount),
                ])
            else:
                rows.append([
                    description_cell,
                    quantity(item_quantity),
                    money(invoice.currency, unit_price),
                    money(invoice.currency, line_amount),
                ])
    else:
        if getattr(invoice, "contract", None):
            contract = invoice.contract
            description = (
                contract.get_service_type_display()
                if getattr(contract, "service_type", "") else "Professional services"
            )
            description += f"\nContract: {contract.contract_number}"
            if getattr(contract, "start_date", None) and getattr(contract, "end_date", None):
                description += (
                    f"\nPeriod: {_format_date(contract.start_date)} - {_format_date(contract.end_date)}"
                )
        else:
            description = "Professional services"
        rows.append([description, "1", money(invoice.currency, _decimal(invoice.amount)), money(invoice.currency, _decimal(invoice.amount))])

    totals = _invoice_totals(invoice, entity, is_receipt=is_receipt)
    if show_shared_service_copy:
        story.extend([
            Paragraph(html_text(STANDARD_SERVICE_COPY), styles["small"]),
            Spacer(1, 5),
        ])
    if has_product:
        story.extend(item_table(
            ["Service", "Description", "Qty", "Unit price", "Amount"],
            rows,
            [PRODUCT_COLUMN_WIDTH, CONTENT_WIDTH - PRODUCT_COLUMN_WIDTH - 246, 42, 92, 112],
            {2, 3, 4},
            styles,
            amount_columns={3, 4},
            totals=totals,
        ))
    else:
        story.extend(item_table(
            ["Description", "Qty", "Unit price", "Amount"],
            rows,
            [CONTENT_WIDTH - 222, 42, 84, 96],
            {1, 2, 3},
            styles,
            amount_columns={2, 3},
            totals=totals,
        ))

    if getattr(invoice, "service_period_start", None) and getattr(invoice, "service_period_end", None):
        story.extend([
            Spacer(1, 8),
            KeepTogether([
                Paragraph("SERVICE PERIOD", styles["label"]),
                Spacer(1, 3),
                Paragraph(
                    f"{escape(_format_date(invoice.service_period_start))} - "
                    f"{escape(_format_date(invoice.service_period_end))}",
                    styles["body"],
                ),
            ]),
        ])

    story.extend(section_start("02", "Payment details", styles, minimum_following_height=220))
    payment_terms = clean_text(getattr(invoice, "payment_terms_text", "")).strip()
    if not payment_terms:
        payment_terms = entity["payment_terms_default"]
    story.extend(payment_block(entity, payment_terms, styles))

    return build_document_pdf(
        story,
        document_title=document_title,
        document_id=document_id,
        entity=entity,
        logo_path=logo_path,
        preview=preview,
    )
