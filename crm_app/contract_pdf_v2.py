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
from reportlab.platypus import CondPageBreak, HRFlowable, Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

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


def _template_issuer_conflicts(content, issuer):
    """Recognize the other configured supplier's fixed remittance details.

    Inspect the tailored source, not substituted customer data. Bank names alone
    are not conflicts: a client may legitimately mention its own sending bank.
    """
    other_issuer = ('BMAsia Limited' if issuer == 'BMAsia (Thailand) Co., Ltd.'
                    else 'BMAsia (Thailand) Co., Ltd.')
    other = entity_profile_for(other_issuer)
    plain = unescape(clean_text(content))
    plain = re.sub(r'<(?:br\s*/?|/p|/div)>', '\n', plain, flags=re.I)
    plain = re.sub(r'<[^>]+>', '', plain).casefold()
    plain = plain.replace('\u2019', "'").replace('\u2013', '-').replace('\u2014', '-')
    lines = [' '.join(line.split()) for line in plain.splitlines()]
    normalized = ' '.join(lines)
    if other_issuer.casefold() in normalized:
        return True
    for identifier in (other['account'], other['swift']):
        if re.search(r'(?<!\w)' + re.escape(identifier.casefold()) + r'(?!\w)', normalized):
            return True

    bank = (r'hsbc(?:\s+bank)?(?:\s*,?\s*(?:hong\s+kong|hk))?'
            if other_issuer == 'BMAsia Limited'
            else r'tmb[\s-]*thanachart(?:\s+bank)?')
    for line in lines:
        # Known supplier-bank labels, BMA's bank, and explicit remittance
        # instructions are distinct from a client's incidental bank reference.
        if re.search(r'^(?:(?:remittance|beneficiary|supplier)\s+)?bank\s*:\s*' + bank + r'\b', line):
            return True
        if re.search(r"\b(?:bma|bmasia|supplier|beneficiary)'s\s+" + bank + r'\b', line):
            return True
        if re.search(r'\b(?:pay|payment|payments|remit|remittance|transfer)\b[^.;\n]{0,100}\b(?:to|into)\s+(?:the\s+)?' + bank + r'\b', line):
            return True
    return False


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
    # Run after clause insertion so custom wording cannot bypass this check.
    # Keep issuer variables unresolved here; their values follow the validated
    # document issuer, while customer names/banks are not supplier evidence.
    if _template_issuer_conflicts(content, effective_billing_entity(contract)):
        raise ContractTailoringClarification([{
            'field': 'billing_entity',
            'accepted_slots': ['issuer_name', 'issuer_address', 'issuer_bank', 'issuer_account', 'issuer_swift'],
        }])
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
    text = text.replace('Soundtrack Your Brand', 'Soundtrack Your&#160;Brand')
    paragraph = Paragraph(text, style)
    paragraph._bmasia_source_style = name
    return paragraph


def _signature_table(source, width, styles):
    """Lay out legacy signing content on shared rows, not offset nested columns.

    This is a layout-only adapter: use the exact existing names, dates, entities,
    authority text and image resources. Never add a signature or change a signer.
    Equal signing areas and real rules replace oversized images/negative padding.
    Each signer pair is atomic; additional pairs may continue onto another page.
    """
    if len(source._cellvalues) != 1 or len(source._cellvalues[0]) != 2:
        return None
    columns = source._cellvalues[0]
    if not all(isinstance(c, Table) and all(len(row) == 1 for row in c._cellvalues)
               for c in columns):
        return None

    def segments(column):
        result, current, pictures = [], None, []
        for row in column._cellvalues:
            item = row[0]
            if isinstance(item, Table):
                if any(not isinstance(v, Image) and v not in ('', None)
                       for cells in item._cellvalues for v in cells):
                    return []  # Unknown nested wording must never be discarded.
                pictures.extend(v for cells in item._cellvalues for v in cells if isinstance(v, Image))
            elif isinstance(item, Paragraph):
                if re.fullmatch(r'_+', item.getPlainText().strip()):
                    current = {'images': pictures, 'fields': []}
                    pictures = []
                    result.append(current)
                elif current is not None:
                    current['fields'].append(item)
                else:
                    return []  # Not a recognized signing block: retain generic layout.
            elif not isinstance(item, Spacer) and item not in ('', None):
                return []
        return result

    left, right = [segments(c) for c in columns]
    if not left or not right:
        return None
    gutter = 28
    column_width = (width - gutter) / 2

    def pictures(items):
        images = []
        for index, item in enumerate(items):
            img = copy(item)
            max_width = min(124 if index == 0 else 58, column_width / max(len(items), 1))
            # Preserve the original resource's aspect ratio, not legacy distortion.
            factor = min(max_width / img.imageWidth, 58 / img.imageHeight)
            img.drawWidth, img.drawHeight = img.imageWidth * factor, img.imageHeight * factor
            images.append(img)
        if not images:
            return Spacer(1, 62)
        table = Table([images], colWidths=[column_width / len(images)] * len(images), rowHeights=[62])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        return table

    pairs = []
    for index in range(max(len(left), len(right))):
        pair = [side[index] if index < len(side) else None for side in (left, right)]
        rows = [[pictures(pair[0]['images']) if pair[0] else '', '',
                 pictures(pair[1]['images']) if pair[1] else '']]
        rows.append([HRFlowable(width=column_width, thickness=.5, color=MUTED) if s else '' for s in (pair[0], None, pair[1])])
        # Field styles carry their semantic role from the content generator. Align
        # names/titles/entities/dates even when the client has no separate title.
        roles = ['signame', 'sigtitle', 'sigcompany', 'sigdate']
        recognized = all(p.style.name.lower() in roles for s in pair if s for p in s['fields'])
        if recognized:
            for role in roles:
                cells = []
                for signatory in pair:
                    fields = [p for p in signatory['fields'] if p.style.name.lower() == role] if signatory else []
                    cells.append([_paragraph(p, styles, cell=True, alignment=TA_CENTER) for p in fields] or '')
                rows.append([cells[0], '', cells[1]])
        else:
            # Preserve unfamiliar text in source order instead of dropping it.
            count = max(len(s['fields']) if s else 0 for s in pair)
            for position in range(count):
                cells = [_paragraph(s['fields'][position], styles, cell=True, alignment=TA_CENTER)
                         if s and position < len(s['fields']) else '' for s in pair]
                rows.append([cells[0], '', cells[1]])
        table = Table(rows, colWidths=[column_width, gutter, column_width], hAlign='LEFT', splitByRow=0)
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 2), (-1, 2), 6),
            ('TOPPADDING', (0, -1), (-1, -1), 9),
        ]))
        pairs.append([table])
    table = Table(pairs, colWidths=[width], hAlign='LEFT', splitByRow=1)
    table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    table._bmasia_signature_pairs = True
    return table


def _table(source, width, styles, *, nested=False):
    if not nested:
        signing = _signature_table(source, width, styles)
        if signing is not None:
            return signing
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
            # ReportLab's KeepTogether.wrap returns a sentinel height. Nesting it
            # inside another KeepTogether measures a small table as millions of
            # points and forces a spurious page break (the JLL one-zone case).
            def flatten(values):
                for value in values:
                    if isinstance(value, KeepTogether):
                        yield from flatten(value._content)
                    else:
                        yield value
            children = list(flatten(children))
            # Legal schedules must flow across pages; signatures stay atomic.
            long_table = any(isinstance(v, Table) and len(v._cellvalues) > 8 for v in children)
            signature_pairs = any(getattr(v, '_bmasia_signature_pairs', False) for v in children)
            output.extend(children if signature_pairs or (long_table and '___' not in _plain(item._content))
                          else [KeepTogether(children)])
        elif isinstance(item, Spacer):
            output.append(Spacer(1, min(item.height, 14)))
        else:
            output.append(item)
    # A short service-package list should not leave its final price bullet alone
    # on the next page. Large/custom lists must still be able to flow normally.
    grouped, index = [], 0
    while index < len(output):
        item = output[index]
        end = index + 1
        if isinstance(item, Paragraph) and 'Service Packages' in item.getPlainText():
            while end < len(output) and getattr(output[end], '_bmasia_source_style', '') == 'bulletstyle':
                end += 1
        if end > index + 1:
            group = output[index:end]
            height = sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in group)
            if height <= 200:
                grouped.append(KeepTogether(group))
            else:
                item.style.keepWithNext = True
                grouped.extend(group)
        else:
            grouped.append(item)
        index = end
    # If a signing pair has to move, bring the short closing contacts section
    # with it. A signature-only continuation page has no contractual context.
    # Do not bind arbitrary long legal prose or multiple signer pairs together.
    for position, item in enumerate(grouped):
        if not getattr(item, '_bmasia_signature_pairs', False) or len(item._cellvalues) != 1:
            continue
        for start in range(position - 1, max(-1, position - 9), -1):
            previous = grouped[start]
            if not isinstance(previous, (Paragraph, Spacer)):
                break
            if isinstance(previous, Paragraph) and re.fullmatch(r'\d+\.\s*Contacts:', previous.getPlainText().strip()):
                closing = grouped[start:position + 1]
                height = sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in closing)
                if height < 300:
                    grouped[start:position + 1] = [KeepTogether(closing)]
                break
    return grouped


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
