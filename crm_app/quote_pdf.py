"""
Quote PDF renderer — pure / reportlab-only.

Single source of truth for the customer-facing quotation PDF. Deliberately has
NO Django model / request imports at module top level so it can be unit-tested
and previewed with only `reportlab` + `Pillow` installed (see
scripts/preview_quote_pdf.py). The Django view (QuoteViewSet.pdf) resolves the
billing entity + helper callables and delegates here.

5-point best-practice format (Norbert-approved 02.06.2026, msg 10613):
  1. Product shown as SYB / BB shorthand on every line (description = zone only),
     with a one-line legend footnote mapping the codes to full names.
  2. 1-year vs multi-year made unmistakable:
       a) a Term / Billing band above the line items,
       b) subscription unit price reads "<cur>X.XX  per zone / year",
       c) totals ladder: Total (Annual) -> Total Contract Value (term).
  3. Complimentary (zero-price) items grouped in their own "Included at no
     charge" block, showing their list value to anchor the saving.
  4. An explicit payment-schedule line (derived from billing_frequency + term
     if the quote does not override it).
  5. Quote number / issue date / valid-until in the metadata band.
"""

from io import BytesIO
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


# Map product_service slug -> short customer-facing code. The stored data stays
# a lowercase slug (validation contract); only the rendered label is shortened.
# Anything not in this map renders unchanged (e.g. "Soundtrack Player").
PRODUCT_SHORT_CODES = {
    'beatbreeze': 'BB',
    'beatbreze': 'BB',
    'bb': 'BB',
    'soundtrack': 'SYB',
    'soundtrackyourbrand': 'SYB',
    'syb': 'SYB',
}

# Codes that represent a per-zone / per-year music subscription (drives the
# "per zone / year" unit-price suffix).
SUBSCRIPTION_CODES = {'SYB', 'BB'}

LEGEND_FULL_NAMES = {
    'SYB': 'Soundtrack Your Brand',
    'BB': 'Beat Breeze',
}

BILLING_FREQUENCY_DISPLAY = {
    'annual': 'Annual',
    'upfront': 'Upfront (full term)',
    'biannual': 'Bi-annual',
    'quarterly': 'Quarterly',
    'monthly': 'Monthly',
}


def _short_code(raw_product):
    return PRODUCT_SHORT_CODES.get(
        (raw_product or '').strip().lower().replace(' ', ''), raw_product or 'Service'
    )


def _qty_str(quantity):
    try:
        return f"{quantity:,.0f}" if quantity == int(quantity) else f"{quantity:,.2f}"
    except (TypeError, ValueError):
        return str(quantity)


def derive_payment_schedule(quote, format_duration):
    """Explicit payment-schedule sentence. Quote override wins; else derive from
    billing_frequency + contract term."""
    override = (getattr(quote, 'payment_schedule', '') or '').strip()
    if override:
        return override
    freq = getattr(quote, 'billing_frequency', 'annual') or 'annual'
    months = getattr(quote, 'contract_duration_months', 12) or 12
    term = format_duration(months)
    if freq in ('one-time', 'one_time', 'once'):
        return "Billed once, in full, on invoice."
    if freq == 'upfront':
        return f"Billed once, in full, upfront for the {term} term."
    if freq == 'biannual':
        return "Billed twice per year."
    if freq == 'quarterly':
        return "Billed quarterly."
    if freq == 'monthly':
        return "Billed monthly."
    # annual (default)
    if months > 12:
        return f"Billed annually — one invoice per year for the full {term}."
    return "Billed annually."


def build_quote_pdf(quote, entity, logo_path, format_address_multiline, format_duration):
    """Render the quote PDF and return the raw bytes.

    quote: a Quote-like object (Django model or duck-typed mock for previews).
    entity: dict with keys name, address, phone, tax, bank, swift, account,
            payment_terms_default, billing_entity.
    logo_path: absolute path to the BMAsia logo PNG (may not exist).
    format_address_multiline: callable(company) -> '<br/>'-joined address string.
    format_duration: callable(months) -> human-readable duration string.
    """
    entity_name = entity['name']
    entity_address = entity['address']
    entity_phone = entity['phone']
    entity_tax = entity.get('tax')
    entity_bank = entity['bank']
    entity_swift = entity['swift']
    entity_account = entity['account']
    payment_terms_default = entity['payment_terms_default']
    billing_entity = entity.get('billing_entity', '')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.3 * inch, bottomMargin=0.65 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
    )

    # Brand palette
    ACCENT = '#E8910C'
    ACCENT_LIGHT = '#FFF3E0'
    CARD_BG = '#FFF8F0'
    TEXT_DARK = '#3A3A3A'
    TEXT_MID = '#666666'
    TEXT_LIGHT = '#888888'
    GRID_COLOR = '#E8E0D8'

    def draw_quote_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        page_width = letter[0]
        canvas_obj.setStrokeColor(colors.HexColor('#E8E0D8'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(doc_obj.leftMargin, 0.55 * inch, page_width - doc_obj.rightMargin, 0.55 * inch)
        canvas_obj.setFont('DejaVuSans-Bold', 7)
        canvas_obj.setFillColor(colors.HexColor('#888888'))
        canvas_obj.drawCentredString(page_width / 2, 0.38 * inch, f"{entity_name} — Wherever Music Matters")
        canvas_obj.setFont('DejaVuSans', 7)
        canvas_obj.drawCentredString(page_width / 2, 0.23 * inch, f"{entity_address} | Phone: {entity_phone}")
        canvas_obj.restoreState()

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=22,
                                 textColor=colors.HexColor(TEXT_DARK), spaceAfter=8, fontName='DejaVuSans-Bold')
    body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=9,
                                textColor=colors.HexColor(TEXT_DARK), leading=12, fontName='DejaVuSans')
    small_style = ParagraphStyle('SmallText', parent=styles['Normal'], fontSize=7,
                                 textColor=colors.HexColor(TEXT_MID), leading=9, fontName='DejaVuSans')
    terms_style = ParagraphStyle('TermsText', parent=styles['Normal'], fontSize=7,
                                 textColor=colors.HexColor('#757575'), leading=8, fontName='DejaVuSans')
    unit_style = ParagraphStyle('UnitCell', parent=styles['Normal'], fontSize=8,
                                textColor=colors.HexColor(TEXT_DARK), leading=9, alignment=TA_RIGHT,
                                fontName='DejaVuSans')

    # Header logo
    try:
        if logo_path and os.path.exists(logo_path):
            logo = Image(logo_path, width=120, height=48, kind='proportional')
            logo.hAlign = 'LEFT'
            elements.append(logo)
        else:
            elements.append(Paragraph("BM ASIA", title_style))
    except Exception:
        elements.append(Paragraph("BM ASIA", title_style))

    elements.append(Spacer(1, 0.03 * inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(ACCENT), spaceBefore=0, spaceAfter=0))
    elements.append(Spacer(1, 0.05 * inch))

    quote_title_style = ParagraphStyle('QuoteTitle', parent=styles['Heading1'], fontSize=20,
                                       textColor=colors.HexColor(ACCENT), spaceAfter=2,
                                       alignment=TA_CENTER, fontName='DejaVuSans-Bold')
    tagline_style = ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=7,
                                   textColor=colors.HexColor(TEXT_LIGHT), alignment=TA_CENTER,
                                   spaceAfter=8, fontName='DejaVuSans')
    elements.append(Paragraph("QUOTATION", quote_title_style))
    elements.append(Paragraph("Wherever Music Matters", tagline_style))

    # Metadata band (Pt5: quote number / issue date / valid until / term)
    metadata_data = [
        ['Quote Number', 'Date', 'Valid Until', 'Contract Term'],
        [quote.quote_number,
         quote.valid_from.strftime('%b %d, %Y'),
         quote.valid_until.strftime('%b %d, %Y'),
         ('One-time' if (getattr(quote, 'billing_frequency', '') or '') in ('one-time', 'one_time', 'once')
          else format_duration(quote.contract_duration_months))],
    ]
    metadata_table = Table(metadata_data, colWidths=[1.7 * inch, 1.7 * inch, 1.7 * inch, 1.8 * inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ACCENT)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
        ('TOPPADDING', (0, 0), (-1, 0), 3),
        ('FONT', (0, 1), (-1, 1), 'DejaVuSans', 10),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor(TEXT_DARK)),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        ('TOPPADDING', (0, 1), (-1, 1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
    ]))
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.05 * inch))

    # From / Bill To
    from_header_style = ParagraphStyle('FromHeader', parent=styles['Normal'], fontSize=8,
                                       textColor=colors.HexColor('#888888'), spaceAfter=4, fontName='DejaVuSans-Bold')
    from_bill_data = [
        [Paragraph('FROM', from_header_style), Paragraph('BILL TO', from_header_style)],
        [
            Paragraph(f"""
            <b>{entity_name}</b><br/>
            {entity_address.replace(', ', '<br/>')}<br/>
            Phone: {entity_phone}
            {f"<br/>Tax No.: {entity_tax}" if entity_tax else ""}
            """, body_style),
            Paragraph(f"""
            <b>{quote.company.legal_entity_name or quote.company.name}</b><br/>
            {format_address_multiline(quote.company)}
            {f"<br/><br/><b>Contact:</b> {quote.contact.name}" if quote.contact else ""}
            {f"<br/>Email: {quote.contact.email}" if quote.contact and quote.contact.email else ""}
            {f"<br/>Phone: {quote.contact.phone}" if quote.contact and quote.contact.phone else ""}
            """, body_style),
        ],
    ]
    from_bill_table = Table(from_bill_data, colWidths=[3.4 * inch, 3.4 * inch])
    from_bill_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(CARD_BG)),
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor(CARD_BG)),
        ('LINEBELOW', (0, 0), (0, 0), 2, colors.HexColor(ACCENT)),
        ('LINEBELOW', (1, 0), (1, 0), 2, colors.HexColor(ACCENT)),
    ]))
    elements.append(from_bill_table)
    elements.append(Spacer(1, 0.05 * inch))

    currency_symbol = {'USD': '$', 'THB': 'THB ', 'EUR': 'EUR ', 'GBP': 'GBP '}.get(
        quote.currency, quote.currency + ' ')

    # Pt2a — Term / Billing band (makes 1yr vs multi-year unmistakable up front)
    duration_months = quote.contract_duration_months or 12
    term_label = format_duration(duration_months)
    billing_freq = getattr(quote, 'billing_frequency', 'annual') or 'annual'
    billing_label = BILLING_FREQUENCY_DISPLAY.get(billing_freq, billing_freq.title())
    band_style = ParagraphStyle('TermBand', parent=styles['Normal'], fontSize=10,
                                textColor=colors.HexColor(TEXT_DARK), fontName='DejaVuSans-Bold', leading=13)
    if billing_freq in ('one-time', 'one_time', 'once'):
        band_text = "One-time purchase &nbsp;&nbsp;|&nbsp;&nbsp; No recurring subscription"
    else:
        band_text = f"Term: {term_label} &nbsp;&nbsp;|&nbsp;&nbsp; Billing: {billing_label}"
    term_band = Table(
        [[Paragraph(band_text, band_style)]],
        colWidths=[6.9 * inch])
    term_band.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(ACCENT_LIGHT)),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor(ACCENT)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(term_band)
    elements.append(Spacer(1, 0.04 * inch))

    # Line items — split paid vs complimentary (Pt1 codes, Pt2b unit period, Pt3 grouping)
    line_items = list(quote.line_items.all())
    used_codes = set()
    paid_rows = [['Product / Service', 'Quantity', 'Unit Price', 'Total']]
    comp_items = []  # (code/name label paragraph, qty_str, value_str)
    total_comp_value = 0.0

    for item in line_items:
        raw_product = item.product_service or 'Service'
        code = _short_code(raw_product)
        if code in SUBSCRIPTION_CODES:
            used_codes.add(code)
        description_text = item.description or ''
        # Avoid repeating the product name: if the description already begins with
        # the product label, show the description alone (Norbert note 03.06.2026).
        if description_text and description_text.strip().lower().startswith(code.lower()):
            cell_content = f"<b>{description_text}</b>"
        elif description_text:
            cell_content = f"<b>{code}</b><br/>{description_text}"
        else:
            cell_content = f"<b>{code}</b>"
        qty_str = _qty_str(item.quantity)
        is_complimentary = float(item.unit_price) == 0

        if is_complimentary:
            unit_value = getattr(item, 'unit_value', None)
            if unit_value is not None and float(unit_value) > 0:
                line_value = float(unit_value) * float(item.quantity)
                total_comp_value += line_value
                value_str = f"{currency_symbol}{float(unit_value):,.2f} each (value {currency_symbol}{line_value:,.2f})"
            else:
                value_str = "Included"
            comp_items.append([
                Paragraph(cell_content, body_style),
                qty_str,
                Paragraph(value_str, unit_style),
            ])
        else:
            unit_cell = f"{currency_symbol}{item.unit_price:,.2f}"
            if code in SUBSCRIPTION_CODES:
                unit_cell = (f"{currency_symbol}{item.unit_price:,.2f}"
                             f"<br/><font size='6' color='{TEXT_LIGHT}'>per zone / year</font>")
            paid_rows.append([
                Paragraph(cell_content, body_style),
                qty_str,
                Paragraph(unit_cell, unit_style),
                Paragraph(f"{currency_symbol}{item.line_total:,.2f}", unit_style),
            ])

    if len(paid_rows) > 1:
        line_items_table = Table(paid_rows, colWidths=[3.5 * inch, 1 * inch, 1.2 * inch, 1.2 * inch])
        line_items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ACCENT)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('FONT', (0, 1), (-1, -1), 'DejaVuSans', 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(TEXT_DARK)),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(CARD_BG)]),
        ]))
        elements.append(line_items_table)
    elif not comp_items:
        elements.append(Paragraph("No line items", body_style))

    # Pt3 — complimentary "Included at no charge" group
    if comp_items:
        elements.append(Spacer(1, 0.04 * inch))
        comp_data = [['Included at no charge', 'Quantity', 'Value']] + comp_items
        comp_table = Table(comp_data, colWidths=[3.5 * inch, 1 * inch, 2.4 * inch])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B07C2A')),  # bronze = included (brand-warm)
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('FONT', (0, 1), (-1, -1), 'DejaVuSans', 8),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FBF1DD')),
        ]))
        elements.append(comp_table)
        if total_comp_value > 0:
            saving_style = ParagraphStyle('Saving', parent=small_style, alignment=TA_RIGHT,
                                          textColor=colors.HexColor('#8A5E15'), fontName='DejaVuSans-Bold')
            elements.append(Paragraph(
                f"Total value included at no charge: {currency_symbol}{total_comp_value:,.2f}", saving_style))

    elements.append(Spacer(1, 0.02 * inch))

    # Totals (Pt2c ladder — annual then total contract value for multi-year)
    totals_data = []
    if quote.subtotal > 0:
        totals_data.append(['Subtotal:', f"{currency_symbol}{quote.subtotal:,.2f}"])
    if quote.discount_amount > 0:
        total_before_discount = sum(item.quantity * item.unit_price for item in line_items)
        discount_pct = (quote.discount_amount / total_before_discount * 100) if total_before_discount > 0 else 0
        totals_data.append([f'Discount ({discount_pct:.0f}%):', f"-{currency_symbol}{quote.discount_amount:,.2f}"])
    if quote.tax_amount > 0:
        tax_label = "VAT" if billing_entity == 'BMAsia (Thailand) Co., Ltd.' else "Tax"
        after_discount = quote.subtotal
        tax_pct = (quote.tax_amount / after_discount * 100) if after_discount > 0 else 0
        totals_data.append([f'{tax_label} ({tax_pct:.0f}%):', f"{currency_symbol}{quote.tax_amount:,.2f}"])

    if billing_freq in ('one-time', 'one_time', 'once'):
        totals_data.append(['<b>Total (one-time):</b>', f"<b>{currency_symbol}{quote.total_value:,.2f}</b>"])
    elif duration_months > 12:
        duration_label = format_duration(duration_months)
        totals_data.append(['<b>Annual subscription:</b>', f"<b>{currency_symbol}{quote.total_value:,.2f} / year</b>"])
        years = duration_months / 12
        total_contract_value = float(quote.total_value) * years
        totals_data.append([f'<b>Total Contract Value ({duration_label}):</b>',
                            f"<b>{currency_symbol}{total_contract_value:,.2f}</b>"])
    elif duration_months < 12:
        duration_label = format_duration(duration_months)
        totals_data.append([f'<b>Total ({duration_label}):</b>', f"<b>{currency_symbol}{quote.total_value:,.2f}</b>"])
    else:
        totals_data.append(['<b>Total (per year):</b>', f"<b>{currency_symbol}{quote.total_value:,.2f}</b>"])

    totals_data_parsed = [[Paragraph(label, body_style), Paragraph(value, body_style)] for label, value in totals_data]
    totals_table = Table(totals_data_parsed, colWidths=[5 * inch, 1.9 * inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONT', (0, 0), (-1, -1), 'DejaVuSans', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(TEXT_DARK)),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('FONT', (0, -1), (-1, -1), 'DejaVuSans-Bold', 11),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor(ACCENT)),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor(ACCENT_LIGHT)),
    ]))
    elements.append(totals_table)

    # Pt4 — explicit payment-schedule line
    elements.append(Spacer(1, 0.04 * inch))
    pay_sched_style = ParagraphStyle('PaySched', parent=styles['Normal'], fontSize=9,
                                     textColor=colors.HexColor(TEXT_DARK), leading=12,
                                     alignment=TA_RIGHT, fontName='DejaVuSans')
    elements.append(Paragraph(
        f"<b>Payment schedule:</b> {derive_payment_schedule(quote, format_duration)}", pay_sched_style))

    elements.append(Spacer(1, 0.06 * inch))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(GRID_COLOR), spaceBefore=0, spaceAfter=6))

    # Bank details
    bank_heading_style = ParagraphStyle('BankHeading', parent=styles['Normal'], fontSize=9,
                                        textColor=colors.HexColor(TEXT_LIGHT), spaceAfter=4, spaceBefore=4,
                                        fontName='DejaVuSans-Bold')
    elements.append(Paragraph("Payment Information", bank_heading_style))
    bank_data = [
        ['Beneficiary', entity_name],
        ['Bank', entity_bank],
        ['SWIFT Code', entity_swift],
        ['Account Number', entity_account],
    ]
    bank_table = Table(bank_data, colWidths=[1.5 * inch, 5.4 * inch])
    bank_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(CARD_BG)),
        ('FONT', (0, 0), (0, -1), 'DejaVuSans-Bold', 8),
        ('FONT', (1, 0), (1, -1), 'DejaVuSans', 8),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(TEXT_MID)),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#E8E0D8')),
    ]))
    elements.append(bank_table)

    # Terms & conditions
    elements.append(Spacer(1, 0.06 * inch))
    if getattr(quote, 'terms_conditions', ''):
        terms_text = quote.terms_conditions.replace('\n', '<br/>')
        elements.append(Paragraph(terms_text, terms_style))
    else:
        elements.append(Paragraph(payment_terms_default.replace('\n', '<br/>'), terms_style))

    # Notes
    if getattr(quote, 'notes', '') and quote.notes.strip():
        elements.append(Spacer(1, 0.08 * inch))
        notes_style = ParagraphStyle('NotesStyled', parent=styles['Normal'], fontSize=7,
                                     textColor=colors.HexColor(TEXT_MID), leading=9, leftIndent=8,
                                     borderPadding=4, fontName='DejaVuSans')
        notes_text = quote.notes.strip().replace('\n', '<br/>')
        elements.append(Paragraph(f"<b>Notes:</b> {notes_text}", notes_style))

    # Pt1 — product-code legend at the very bottom (cleaner placement, Norbert 03.06.2026)
    if used_codes:
        legend = "  ·  ".join(f"{c} = {LEGEND_FULL_NAMES[c]}" for c in sorted(used_codes))
        elements.append(Spacer(1, 0.06 * inch))
        legend_style = ParagraphStyle('Legend', parent=small_style, textColor=colors.HexColor(TEXT_LIGHT))
        elements.append(Paragraph(legend, legend_style))

    doc.build(elements, onFirstPage=draw_quote_footer, onLaterPages=draw_quote_footer)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
