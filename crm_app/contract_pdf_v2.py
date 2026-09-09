"""Brand the existing agreement content without rewriting its legal clauses.

The legacy generators remain the content source. This adapter replaces only
their page furniture and layout, recursively fitting their variable tables to
the same A4 grid as quotations and invoices. Corporate-native PDFs bypass it.
"""
from copy import copy
from io import BytesIO
import re
from html import unescape

from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from crm_app.commercial_pdf import (
    ALT_SURFACE, BOLD_FONT, BODY_FONT, CONTENT_WIDTH, INK, LINE, MUTED,
    ORANGE, SURFACE, build_document_pdf, clean_text, document_intro,
    document_styles, entity_profile_for, html_text, identity_cards,
    metadata_table,
)
from crm_app.services.document_context import effective_billing_entity


class ContractTailoringClarification(ValueError):
    def __init__(self, fields):
        self.fields = fields
        super().__init__('The selected full template needs an editable slot for the requested override.')

    def payload(self):
        return {
            'error': str(self), 'code': 'clarification_required',
            'fields': self.fields,
            'detail': 'Requested edits cannot be silently discarded. A named replacement slot is needed for: ' + ', '.join(item['field'] for item in self.fields),
            'next_action': 'Identify the clause to replace and add its named slot to a tailored template copy, or use the standard agreement with these explicit overrides. The original template is unchanged.',
        }


def watermark_native_pdf(data):
    """Mark an in-memory corporate review copy; never replace its stored file."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen.canvas import Canvas
    from crm_app.commercial_pdf import ensure_pdf_fonts
    ensure_pdf_fonts()
    reader, writer = PdfReader(BytesIO(data)), PdfWriter()
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        overlay = BytesIO()
        canvas = Canvas(overlay, pagesize=(width, height))
        canvas.setFillColorRGB(.72, .74, .76)
        canvas.setFillAlpha(.32)
        canvas.translate(width / 2, height / 2)
        canvas.rotate(33)
        canvas.setFont(BOLD_FONT, 23)
        canvas.drawCentredString(0, 0, 'DRAFT PREVIEW - NOT FOR CUSTOMER')
        canvas.save()
        page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0])
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def tailored_template_content(contract, resolved_content=None):
    """Resolve explicit slots; never drop an edit or append conflicting terms.

    Additional terms and a payment schedule have a safe insertion point before
    signatures. Replacing existing legal prose needs a named replacement slot.
    Dynamic values stay plain text; template markup remains the template's.
    """
    content = contract.preamble_template.content
    content = re.sub(r'\{\{\s*(\w+)\s*\}\}', r'{{\1}}', content)
    def already_present(value):
        def normalized(text):
            return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', clean_text(text))).split()).casefold()
        value = normalized(value)
        return bool(value) and value in normalized(resolved_content or content)
    missing = []
    for field, slots, template_field in (
        ('preamble_custom', ('preamble',), None),
        ('payment_custom', ('payment_clause', 'payment_terms'), 'payment_template'),
        ('activation_custom', ('activation_clause', 'activation_terms'), 'activation_template'),
    ):
        value = getattr(contract, field, '')
        selected = getattr(contract, template_field, None) if template_field else None
        if not value and selected:
            value = selected.content
        found = [f'{{{{{slot}}}}}' for slot in slots if f'{{{{{slot}}}}}' in content]
        if getattr(contract, field, '') and not found and not already_present(value):
            missing.append({'field': field, 'accepted_slots': list(slots)})
        for slot in found:
            # payment_terms remains the existing short due-rule variable when
            # no explicit payment wording is supplied.
            if not value and slot == '{{payment_terms}}':
                continue
            content = content.replace(slot, html_text(value) if getattr(contract, field, '') else _markup(value))
    if missing:
        raise ContractTailoringClarification(missing)

    custom_services = getattr(contract, 'custom_service_items', None) or []
    if custom_services:
        if '{{service_items}}' not in content:
            raise ContractTailoringClarification([{'field': 'custom_service_items', 'accepted_slots': ['service_items']}])
        content = content.replace('{{service_items}}', '<br/>'.join(
            html_text(item.get('name', '')) + (': ' + html_text(item['description']) if item.get('description') else '')
            for item in custom_services if isinstance(item, dict)
        ))
    else:
        content = content.replace('{{service_items}}', '')

    inserts = []
    for field, slots, heading in (
        ('custom_terms', ('additional_terms', 'custom_terms'), 'Additional terms and conditions'),
        ('payment_schedule', ('payment_schedule',), 'Payment schedule'),
    ):
        value = getattr(contract, field, '')
        found = [f'{{{{{slot}}}}}' for slot in slots if f'{{{{{slot}}}}}' in content]
        for slot in found:
            content = content.replace(slot, html_text(value))
        if value and not found and not already_present(value):
            inserts.append(f'<b>{heading}</b><br/>{html_text(value)}')
    if inserts:
        extra = '<br/><br/>'.join(inserts) + '<br/><br/>'
        # Place the additions before the complete signature segment, including
        # its heading if separated from the body by a paragraph break.
        marker = content.find('{{signature_blocks}}')
        if marker >= 0:
            boundary = content.rfind('<br/><br/>', 0, marker)
            marker = boundary + len('<br/><br/>') if boundary >= 0 else marker
            content = content[:marker] + extra + content[marker:]
        else:
            content += '<br/><br/>' + extra
    return content


def _markup(text):
    # A pasted clause may carry Word font/color/size tags. Keep semantic inline
    # emphasis but let the document, not pasted formatting, own typography.
    text = clean_text(text)
    text = re.sub(r'</?(?:font|span)\b[^>]*>', '', text, flags=re.I)
    return text


def _plain(value):
    if isinstance(value, Paragraph):
        return value.getPlainText()
    if isinstance(value, (tuple, list)):
        return ' '.join(_plain(item) for item in value)
    if isinstance(value, Table):
        return ' '.join(_plain(row) for row in value._cellvalues)
    return str(value or '')


def _paragraph(item, styles, *, cell=False, bold=False, alignment=None):
    text = _markup(item.text) if isinstance(item, Paragraph) else html_text(item)
    old = item.style if isinstance(item, Paragraph) else None
    name = getattr(old, 'name', '').lower()
    heading = not cell and ('heading' in name or name == 'section_heading')
    style = copy(styles['section' if heading else 'body'])
    if cell:
        style.fontSize, style.leading = 8.4, 11.7
    elif not heading:
        style.fontSize, style.leading = 9.5, 13.4
        style.spaceAfter = 7
    if bold or (old and 'bold' in old.fontName.lower()):
        style.fontName = BOLD_FONT
    if old:
        style.leftIndent = min(getattr(old, 'leftIndent', 0), 16)
        style.bulletIndent = min(getattr(old, 'bulletIndent', 0), 8)
    style.alignment = alignment if alignment is not None else getattr(old, 'alignment', 0)
    style.keepWithNext = heading or bool(getattr(old, 'keepWithNext', False))
    style.allowWidows = style.allowOrphans = 0
    # Keep product name on one line; table width is independently constrained.
    text = text.replace('Beat Breeze', 'Beat&#160;Breeze')
    return Paragraph(text, style)


def _table(source, width, styles, *, nested=False):
    cols = len(source._cellvalues[0])
    raw_widths = source._argW
    if all(isinstance(w, (float, int)) for w in raw_widths) and sum(raw_widths):
        widths = [width * w / sum(raw_widths) for w in raw_widths]
    else:
        widths = [width / cols] * cols
    text = _plain(source)
    signature = '___' in text or ('Date:' in text and cols <= 2)
    image_only = any(isinstance(v, Image) for row in source._cellvalues for v in row)
    header = not (signature or nested or image_only) and (
        bool(source.repeatRows) or any(word in _plain(source._cellvalues[0]).lower()
        for word in ('zone', 'property', 'agreement number', 'beneficiary', 'location', 'service'))
    )
    data = []
    for row_index, row in enumerate(source._cellvalues):
        result = []
        for col, value in enumerate(row):
            cell_width = max(widths[col] - (8 if nested else 18), 12)
            if isinstance(value, Table):
                result.append(_table(value, cell_width, styles, nested=True))
            elif isinstance(value, (list, tuple)):
                result.append(_flowables(list(value), cell_width, styles, cell=True))
            elif isinstance(value, Image):
                img = copy(value)
                factor = min(1, cell_width / img.drawWidth)
                img.drawWidth *= factor
                img.drawHeight *= factor
                result.append(img)
            elif isinstance(value, Spacer):
                result.append(Spacer(1, min(value.height, 14)))
            else:
                # Long underscore rules cannot wrap; cap to the measured cell.
                if isinstance(value, str) and re.fullmatch('_+', value):
                    value = '_' * max(8, int(cell_width / 6))
                numeric = bool(re.match(r'^(?:(?:USD|THB|EUR|GBP)\s+|\$)[\d,.]+', _plain(value).strip()))
                result.append(_paragraph(value, styles, cell=True,
                    bold=header and row_index == 0,
                    alignment=TA_CENTER if signature else 2 if numeric else None))
        data.append(result)
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0,
                  hAlign='LEFT', splitByRow=0 if signature else 1)
    commands = [
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM' if signature else 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 if nested else 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4 if nested else 9),
        ('TOPPADDING', (0, 0), (-1, -1), 3 if nested else 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 if nested else 7),
    ]
    if not (nested or signature or image_only):
        commands += [('ROWBACKGROUNDS', (0, 0), (-1, -1), [ALT_SURFACE, None]),
                     ('LINEBELOW', (0, 0), (-1, -1), .45, LINE)]
    if header:
        commands += [('BACKGROUND', (0, 0), (-1, 0), SURFACE),
                     ('LINEBELOW', (0, 0), (-1, 0), 1, ORANGE)]
    commands += list(source._spanCmds)
    table.setStyle(TableStyle(commands))
    return table


def _flowables(source, width, styles, *, cell=False):
    output = []
    for item in source:
        if isinstance(item, Paragraph):
            # Split explicit paragraph boundaries so long tailored content flows
            # naturally and headings cannot strand at the bottom of a page.
            parts = re.split(r'(?:<br\s*/?>\s*){2,}', item.text, flags=re.I)
            # Inline emphasis may span a paragraph boundary. Keep that one
            # balanced paragraph intact rather than feed malformed fragments.
            if any(len(re.findall(r'<(?:b|i|u)>', part, re.I)) !=
                   len(re.findall(r'</(?:b|i|u)>', part, re.I)) for part in parts):
                parts = [item.text]
            for part in parts:
                if part.strip():
                    p = _paragraph(Paragraph(_markup(part), item.style), styles, cell=cell)
                    if re.fullmatch(r'\s*<b>[^<]+</b>\s*', part):
                        p.style.keepWithNext = True
                    output.append(p)
        elif isinstance(item, Table):
            output.append(_table(item, width, styles, nested=cell))
        elif isinstance(item, KeepTogether):
            children = _flowables(item._content, width, styles, cell=cell)
            # Legal schedules must flow across pages; signatures stay atomic.
            long_table = any(isinstance(v, Table) and len(v._cellvalues) > 8 for v in children)
            output.extend(children if long_table and '___' not in _plain(item._content)
                          else [KeepTogether(children)])
        elif isinstance(item, Spacer):
            output.append(Spacer(1, min(item.height, 14)))
        else:
            output.append(item)
    return output


def build_contract_pdf(contract, body, *, title, logo_path=None, preview=False):
    styles = document_styles()
    entity = entity_profile_for(effective_billing_entity(contract))
    company = contract.company
    document_id = contract.contract_number or ''
    if document_id.startswith('DRAFT-'):
        document_id = ''
    story = document_intro(title, '', styles)
    start = contract.start_date.strftime('%d %b %Y') if contract.start_date else 'Not specified'
    end = contract.end_date.strftime('%d %b %Y') if contract.end_date else 'Open-ended'
    story.append(metadata_table([
        ('Agreement date', start),
        ('Service period', f'{start} - {end}'),
        ('Currency', contract.currency),
    ], styles))
    issuer_lines = [entity['name'], entity['address'], f"Phone: {entity['phone']}"]
    if entity.get('tax'):
        issuer_lines.append(f"Tax ID: {entity['tax']}")
    if entity.get('registration_number'):
        issuer_lines.append(f"Business Registration Certificate No.: {entity['registration_number']}")
    address = getattr(company, 'full_address', '')
    if not address:
        address = '\n'.join(str(getattr(company, key, '') or '') for key in
                            ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country'))
    customer_lines = [company.legal_entity_name or company.name, address]
    if getattr(company, 'tax_id', ''):
        customer_lines.append(f'Tax ID: {company.tax_id}')
    story.append(identity_cards('Issued by', issuer_lines, 'Prepared for', customer_lines, styles))
    story.append(Spacer(1, 12))
    story.extend(_flowables(body, CONTENT_WIDTH, styles))
    while story and isinstance(story[-1], (Spacer, PageBreak)):
        story.pop()
    return build_document_pdf(story, document_title=title, document_id=document_id,
                              entity=entity, logo_path=logo_path, preview=preview)
