"""BMAsia quotation renderer using the approved shared commercial layout."""

from __future__ import annotations

from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app.commercial_pdf import (
    CONTENT_WIDTH,
    build_document_pdf,
    clean_text,
    document_intro,
    document_styles,
    html_text,
    identity_cards,
    is_duplicate_visible_block,
    item_table,
    metadata_table,
    money,
    quantity,
    remarks_block,
    section_start,
    payment_block,
)
from crm_app.quote_pdf import (
    BILLING_FREQUENCY_DISPLAY,
    LEGEND_FULL_NAMES,
    SUBSCRIPTION_CODES,
    _decimal_value,
    _short_code,
    derive_payment_schedule,
    quote_recurring_and_onetime_totals,
)


def _format_date(value):
    return value.strftime("%d %b %Y") if value else "Not specified"


def _address_text(format_address_multiline, company):
    value = clean_text(format_address_multiline(company))
    return value.replace("<br/>", "\n").replace("<br />", "\n")


def _quote_totals(quote, line_items, format_duration, entity):
    currency = quote.currency
    duration_months = quote.contract_duration_months or 12
    billing_frequency = getattr(quote, "billing_frequency", "annual") or "annual"
    rows = []

    if _decimal_value(quote.subtotal) > 0:
        rows.append(("Subtotal", money(currency, quote.subtotal)))
    if _decimal_value(quote.discount_amount) > 0:
        before_discount = sum(
            (_decimal_value(item.quantity) * _decimal_value(item.unit_price) for item in line_items),
            Decimal("0"),
        )
        percentage = (
            (_decimal_value(quote.discount_amount) / before_discount * Decimal("100"))
            if before_discount > 0 else Decimal("0")
        )
        rows.append((f"Discount ({percentage:.0f}%)", f"-{money(currency, quote.discount_amount)}"))
    if _decimal_value(quote.tax_amount) > 0:
        label = "VAT" if entity.get("billing_entity") == "BMAsia (Thailand) Co., Ltd." else "Tax"
        base = _decimal_value(quote.subtotal)
        percentage = (
            (_decimal_value(quote.tax_amount) / base * Decimal("100"))
            if base > 0 else Decimal("0")
        )
        rows.append((f"{label} ({percentage:.0f}%)", money(currency, quote.tax_amount)))

    recurring_total, one_time_total = quote_recurring_and_onetime_totals(line_items)
    mixed = recurring_total > 0 and one_time_total > 0
    total_value = _decimal_value(quote.total_value)

    if billing_frequency == "one-time":
        rows.append(("Total (one-time)", money(currency, total_value)))
    elif duration_months > 12:
        duration_label = format_duration(duration_months)
        annual_subscription = recurring_total if mixed else total_value
        rows.append(("Annual subscription", f"{money(currency, annual_subscription)} / year"))
        if mixed:
            rows.append(("One-time charges", money(currency, one_time_total)))
        years = Decimal(str(duration_months)) / Decimal("12")
        total_contract_value = (
            recurring_total * years + one_time_total
            if mixed else total_value * years
        )
        rows.append((f"Total contract value ({duration_label})", money(currency, total_contract_value)))
    elif duration_months < 12:
        rows.append((f"Total ({format_duration(duration_months)})", money(currency, total_value)))
    else:
        prorated = (
            "prorat" in clean_text(getattr(quote, "notes", "")).lower()
            or any("prorat" in clean_text(getattr(item, "description", "")).lower() for item in line_items)
        )
        if mixed and not prorated:
            rows.extend([
                ("Total (per year)", money(currency, recurring_total)),
                ("One-time charges", money(currency, one_time_total)),
                ("Total", money(currency, total_value)),
            ])
        else:
            rows.append(("Total" if prorated else "Total (per year)", money(currency, total_value)))
    return rows


def build_quote_pdf_v2(
    quote,
    entity,
    logo_path,
    format_address_multiline,
    format_duration,
    *,
    preview=False,
):
    """Render an A4, flow-based quotation and return raw PDF bytes.

    Existing ``quote.notes`` remain customer-visible because that is the CRM
    form's explicit contract and the legacy renderer's behavior. They are
    rendered once only after deduplication against schedule and terms. A future
    explicit ``customer_remarks`` value takes precedence when supplied.
    """
    styles = document_styles()
    duration_months = quote.contract_duration_months or 12
    billing_frequency = getattr(quote, "billing_frequency", "annual") or "annual"
    billing_label = BILLING_FREQUENCY_DISPLAY.get(billing_frequency, billing_frequency.title())

    story = document_intro(
        "Quotation",
        "A clear view of the services, commercial terms and payment details.",
        styles,
    )
    story.append(metadata_table([
        ("Quote number", quote.quote_number),
        ("Issued", _format_date(quote.valid_from)),
        ("Valid until", _format_date(quote.valid_until)),
        ("Currency / term", f"{quote.currency} / {format_duration(duration_months)}"),
    ], styles))

    issuer_lines = [entity["name"], entity["address"], f"Phone: {entity['phone']}"]
    if entity.get("tax"):
        issuer_lines.append(f"Tax ID: {entity['tax']}")

    company = quote.company
    customer_lines = [
        getattr(company, "legal_entity_name", "") or company.name,
        _address_text(format_address_multiline, company),
    ]
    if quote.contact:
        customer_lines.append(f"Attention: {quote.contact.name}")
        if getattr(quote.contact, "email", ""):
            customer_lines.append(quote.contact.email)
        if getattr(quote.contact, "phone", ""):
            customer_lines.append(quote.contact.phone)

    story.append(identity_cards(
        "Issued by", issuer_lines,
        "Prepared for", customer_lines,
        styles,
    ))

    story.extend(section_start("01", "Services and pricing", styles, minimum_following_height=125))
    story.append(Paragraph(
        f"<b>Billing:</b> {escape(clean_text(billing_label))}"
        f" &nbsp;&nbsp;|&nbsp;&nbsp; <b>Contract term:</b> {escape(clean_text(format_duration(duration_months)))}",
        styles["body"],
    ))
    story.append(Spacer(1, 7))

    line_items = list(quote.line_items.all())
    rows = []
    complimentary = []
    used_codes = set()
    complimentary_value = Decimal("0")

    for item in line_items:
        code = _short_code(getattr(item, "product_service", "") or "Service")
        if code in SUBSCRIPTION_CODES:
            used_codes.add(code)
        description = clean_text(getattr(item, "description", ""))
        if description and description.strip().lower().startswith(clean_text(code).lower()):
            description_markup = f"<b>{escape(description)}</b>"
        elif description:
            description_markup = f"<b>{escape(clean_text(code))}</b><br/>{html_text(description)}"
        else:
            description_markup = f"<b>{escape(clean_text(code))}</b>"
        description_cell = Paragraph(description_markup, styles["body"])

        item_quantity = _decimal_value(getattr(item, "quantity", 0))
        unit_price = _decimal_value(getattr(item, "unit_price", 0))
        if unit_price == 0:
            unit_value = _decimal_value(getattr(item, "unit_value", 0))
            if unit_value > 0:
                line_value = unit_value * item_quantity
                complimentary_value += line_value
                value = f"Value {money(quote.currency, line_value)}"
            else:
                value = "Included"
            complimentary.append([description_cell, quantity(item_quantity), "Included", value])
            continue

        unit_value = money(quote.currency, unit_price)
        if code in SUBSCRIPTION_CODES:
            unit_value += "\nper zone / year"
        rows.append([
            description_cell,
            quantity(item_quantity),
            unit_value,
            money(quote.currency, _decimal_value(getattr(item, "line_total", 0))),
        ])

    group_rows = set()
    if complimentary:
        group_rows.add(len(rows) + 1)
        rows.append(["Included at no charge", "", "", ""])
        rows.extend(complimentary)
    if not rows:
        rows.append(["No line items", "", "", ""])

    totals = _quote_totals(quote, line_items, format_duration, entity)
    if complimentary_value > 0:
        totals.insert(max(len(totals) - 1, 0), (
            "Value included at no charge",
            money(quote.currency, complimentary_value),
        ))

    if used_codes:
        legend = "  |  ".join(f"{code} = {LEGEND_FULL_NAMES[code]}" for code in sorted(used_codes))
        story.extend([
            Paragraph(html_text(legend), styles["small"]),
            Spacer(1, 5),
        ])

    story.extend(item_table(
        ["Description", "Qty", "Unit price", "Amount"],
        rows,
        [CONTENT_WIDTH - 264, 54, 98, 112],
        {1, 2, 3},
        styles,
        amount_columns={2, 3},
        totals=totals,
        group_rows=group_rows,
    ))

    story.extend(section_start("02", "Payment and terms", styles, minimum_following_height=210))
    schedule = clean_text(derive_payment_schedule(quote, format_duration)).strip()
    terms = clean_text(getattr(quote, "terms_conditions", "")).strip() or entity["payment_terms_default"]
    visible_prior = [terms]
    if schedule and not is_duplicate_visible_block(schedule, visible_prior):
        schedule_flowables = [
            Paragraph("PAYMENT SCHEDULE", styles["label"]),
            Spacer(1, 3),
            Paragraph(html_text(schedule), styles["body"]),
            Spacer(1, 8),
        ]
        story.append(KeepTogether(schedule_flowables))
        visible_prior.append(schedule)
    story.extend(payment_block(entity, terms, styles))

    customer_remarks = clean_text(
        getattr(quote, "customer_remarks", "") or getattr(quote, "notes", "")
    ).strip()
    if customer_remarks and not is_duplicate_visible_block(customer_remarks, visible_prior):
        story.extend([Spacer(1, 10), remarks_block(customer_remarks, styles)])
        visible_prior.append(customer_remarks)

    return build_document_pdf(
        story,
        document_title="Quotation",
        document_id=quote.quote_number,
        entity=entity,
        logo_path=logo_path,
        preview=preview,
    )
