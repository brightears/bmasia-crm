"""
Proforma Invoice PDF renderer — pure / reportlab-only.

Standalone advance-payment document generated FROM A CONTRACT (Pom's design,
09.06.2026): "A Proforma Invoice is similar to a quotation, but formatted more
like an invoice, clearly labeled 'Proforma Invoice'. The data should be
generated from the contract. It is not recorded in the accounting or tax
system until an official invoice is issued — a separate function, distinct
from the standard invoice process."

Accordingly this module creates NO Invoice row, touches NO AR / revenue
recognition / receipt logic, and the rendered document must never read as a
tax invoice: it carries an explicit "not a tax invoice" notice and no
claimable-VAT presentation. The official tax invoice / receipt is still
issued on payment via the existing Invoice -> mark_paid flow (for the Thai
entity this keeps the VAT tax point at the payment date — see
docs/renewal-to-cash-plan-2026-06-09.md in the desk repo).

Mirrors crm_app/quote_pdf.py (house style + module pattern): no Django
imports at module top level so it can be previewed with reportlab + Pillow
only. The Django view (ContractViewSet.proforma_pdf) resolves the billing
entity + helpers and delegates here.
"""

from datetime import date
from io import BytesIO
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from .quote_pdf import _short_code, _qty_str, SUBSCRIPTION_CODES, LEGEND_FULL_NAMES


def build_proforma_pdf(contract, entity, logo_path, format_address_multiline, issue_date=None):
    """Render the proforma-invoice PDF for a contract and return raw bytes.

    contract: a Contract-like object (Django model or duck-typed mock).
    entity: dict with keys name, address, phone, tax, bank, swift, account,
            payment_terms_default, billing_entity (same dict as quote PDF).
    logo_path: absolute path to the BMAsia logo PNG (may not exist).
    format_address_multiline: callable(company) -> '<br/>'-joined address string.
    issue_date: date the proforma is issued (defaults to today).
    """
    issue_date = issue_date or date.today()
    entity_name = entity['name']
    entity_address = entity['address']
    entity_phone = entity['phone']
    entity_tax = entity.get('tax')
    entity_bank = entity['bank']
    entity_swift = entity['swift']
    entity_account = entity['account']
    payment_terms_default = entity['payment_terms_default']
    billing_entity = entity.get('billing_entity', '')

    company = contract.company
    contract_number = contract.contract_number or str(contract.id)[:8]
    proforma_no = f"PF-{contract_number}"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.3 * inch, bottomMargin=0.65 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
    )

    # Brand palette (house style, same as quote_pdf.py)
    ACCENT = '#E8910C'
    ACCENT_LIGHT = '#FFF3E0'
    CARD_BG = '#FFF8F0'
    TEXT_DARK = '#3A3A3A'
    TEXT_MID = '#666666'
    TEXT_LIGHT = '#888888'
    GRID_COLOR = '#E8E0D8'

    def draw_footer(canvas_obj, doc_obj):
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

    doc_title_style = ParagraphStyle('ProformaTitle', parent=styles['Heading1'], fontSize=20,
                                     textColor=colors.HexColor(ACCENT), spaceAfter=2,
                                     alignment=TA_CENTER, fontName='DejaVuSans-Bold')
    tagline_style = ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=7,
                                   textColor=colors.HexColor(TEXT_LIGHT), alignment=TA_CENTER,
                                   spaceAfter=6, fontName='DejaVuSans')
    elements.append(Paragraph("PROFORMA INVOICE", doc_title_style))
    elements.append(Paragraph("Wherever Music Matters", tagline_style))

    # The load-bearing tax-safety notice: this document must never read as a tax invoice.
    notice_style = ParagraphStyle('Notice', parent=styles['Normal'], fontSize=8.5,
                                  textColor=colors.HexColor(TEXT_DARK), leading=11, fontName='DejaVuSans')
    notice = Table([[Paragraph(
        "<b>This is a proforma invoice issued for advance payment — it is not a tax invoice "
        "and not a demand for tax purposes.</b> An official "
        + ("tax invoice / receipt" if billing_entity == 'BMAsia (Thailand) Co., Ltd.' else "invoice / receipt")
        + " will be issued upon receipt of payment.", notice_style)]],
        colWidths=[7.5 * inch])
    notice.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(ACCENT_LIGHT)),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor(ACCENT)),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(notice)
    elements.append(Spacer(1, 0.06 * inch))

    # Metadata band: proforma ref / issue date / payment due / service period
    start = getattr(contract, 'start_date', None)
    end = getattr(contract, 'end_date', None)
    if start and start > issue_date:
        due_label = start.strftime('%b %d, %Y')
    else:
        due_label = 'Upon receipt'
    period_label = (f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"
                    if start and end else '—')
    metadata_data = [
        ['Proforma No.', 'Issue Date', 'Payment Due', 'Service Period'],
        [proforma_no, issue_date.strftime('%b %d, %Y'), due_label, period_label],
    ]
    metadata_table = Table(metadata_data, colWidths=[1.8 * inch, 1.5 * inch, 1.5 * inch, 2.1 * inch])
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

    # From / Bill To cards
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
            <b>{company.legal_entity_name or company.name}</b><br/>
            {format_address_multiline(company)}
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

    currency = getattr(contract, 'currency', 'USD') or 'USD'
    currency_symbol = {'USD': '$', 'THB': 'THB ', 'EUR': 'EUR ', 'GBP': 'GBP '}.get(
        currency, currency + ' ')

    # Line items — from the contract (Pom: data generated from the contract).
    # Falls back to a single subscription row when a contract has no line items
    # (common on imported/legacy contracts) so the document is still complete.
    line_items = list(contract.line_items.all())
    used_codes = set()
    rows = [['Product / Service', 'Quantity', 'Unit Price', 'Total']]
    for item in line_items:
        code = _short_code(item.product_service or 'Service')
        if code in SUBSCRIPTION_CODES:
            used_codes.add(code)
        description_text = item.description or ''
        if description_text and description_text.strip().lower().startswith(code.lower()):
            cell_content = f"<b>{description_text}</b>"
        elif description_text:
            cell_content = f"<b>{code}</b><br/>{description_text}"
        else:
            cell_content = f"<b>{code}</b>"
        unit_cell = f"{currency_symbol}{float(item.unit_price):,.2f}"
        if code in SUBSCRIPTION_CODES:
            unit_cell = (f"{currency_symbol}{float(item.unit_price):,.2f}"
                         f"<br/><font size='6' color='{TEXT_LIGHT}'>per zone / year</font>")
        rows.append([
            Paragraph(cell_content, body_style),
            _qty_str(item.quantity),
            Paragraph(unit_cell, unit_style),
            Paragraph(f"{currency_symbol}{float(item.line_total):,.2f}", unit_style),
        ])
    if len(rows) == 1:
        period_text = f" — {period_label}" if period_label != '—' else ''
        rows.append([
            Paragraph(f"<b>Music service subscription</b><br/>{company.name}{period_text}", body_style),
            '1',
            Paragraph(f"{currency_symbol}{float(contract.value or 0):,.2f}", unit_style),
            Paragraph(f"{currency_symbol}{float(contract.value or 0):,.2f}", unit_style),
        ])

    line_items_table = Table(rows, colWidths=[3.5 * inch, 1 * inch, 1.2 * inch, 1.2 * inch])
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
    elements.append(Spacer(1, 0.02 * inch))

    # Totals — rendered exactly as stored on the contract. VAT shown only when
    # the contract carries tax (informational; the claimable document is the
    # tax invoice issued on payment). A discount is shown EXPLICITLY whenever
    # value+tax != total, so the customer's AP sees the reduction is already
    # applied and doesn't deduct it a second time.
    value = float(getattr(contract, 'value', 0) or 0)
    tax_amount = float(getattr(contract, 'tax_amount', 0) or 0)
    total_value = float(getattr(contract, 'total_value', 0) or 0) or (value + tax_amount)
    discount = round(value + tax_amount - total_value, 2)
    totals_data = []
    if tax_amount > 0 or discount > 0.005:
        totals_data.append(['Subtotal:', f"{currency_symbol}{value:,.2f}"])
    if discount > 0.005:
        discount_pct = float(getattr(contract, 'discount_percentage', 0) or 0) or (
            (discount / value * 100) if value else 0)
        totals_data.append([f'Less discount ({discount_pct:.0f}%):', f"-{currency_symbol}{discount:,.2f}"])
    if tax_amount > 0:
        tax_label = "VAT" if billing_entity == 'BMAsia (Thailand) Co., Ltd.' else "Tax"
        tax_rate = float(getattr(contract, 'tax_rate', 0) or 0)
        rate_str = f" ({tax_rate:.0f}%)" if tax_rate else ""
        totals_data.append([f'{tax_label}{rate_str}:', f"{currency_symbol}{tax_amount:,.2f}"])
    totals_data.append(['<b>Total payable:</b>', f"<b>{currency_symbol}{total_value:,.2f}</b>"])
    totals_data_parsed = [[Paragraph(label, body_style), Paragraph(v, body_style)] for label, v in totals_data]
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

    # Payment-reference instruction (helps the customer's AP route the remittance)
    elements.append(Spacer(1, 0.04 * inch))
    ref_style = ParagraphStyle('PayRef', parent=styles['Normal'], fontSize=9,
                               textColor=colors.HexColor(TEXT_DARK), leading=12,
                               alignment=TA_RIGHT, fontName='DejaVuSans')
    elements.append(Paragraph(
        f"<b>Payment reference:</b> please quote <b>{proforma_no}</b> (contract {contract_number}) with your remittance.",
        ref_style))

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

    # Payment terms
    elements.append(Spacer(1, 0.06 * inch))
    elements.append(Paragraph(payment_terms_default.replace('\n', '<br/>'), terms_style))

    # Repeat the not-a-tax-invoice line at the bottom (belt and suspenders)
    elements.append(Spacer(1, 0.04 * inch))
    elements.append(Paragraph(
        "Proforma invoice for advance payment only — not a tax invoice. "
        + ("An official tax invoice / receipt will be issued upon receipt of payment."
           if billing_entity == 'BMAsia (Thailand) Co., Ltd.'
           else "An official invoice / receipt will be issued upon receipt of payment."),
        small_style))

    # Product-code legend
    if used_codes:
        legend = "  ·  ".join(f"{c} = {LEGEND_FULL_NAMES[c]}" for c in sorted(used_codes))
        elements.append(Spacer(1, 0.04 * inch))
        legend_style = ParagraphStyle('Legend', parent=small_style, textColor=colors.HexColor(TEXT_LIGHT))
        elements.append(Paragraph(legend, legend_style))

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
