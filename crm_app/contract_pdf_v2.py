"""Brand the existing agreement content without rewriting its legal clauses.

The legacy generators remain the content source. This adapter replaces only
their page furniture and layout, recursively fitting their variable tables to
the same A4 grid as quotations and invoices. Only immutable format-native PDFs
bypass it; full legal templates such as Hilton use this approved design.
"""
from copy import copy
from io import BytesIO
import logging
import re
from html import unescape
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import CondPageBreak, HRFlowable, Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from crm_app.commercial_pdf import (
    ALT_SURFACE, BOLD_FONT, BODY_FONT, CONTENT_WIDTH, CONTINUATION_PAGE_TOP,
    INK, LINE, MUTED, ORANGE, PAGE_BOTTOM, PAGE_HEIGHT, SURFACE,
    build_document_pdf, clean_text, document_intro, document_styles,
    entity_profile_for, html_text, identity_cards, metadata_table,
)
from crm_app.pdf_thai import ThaiAwareParagraph
from crm_app.services.document_context import customer_legal_entity_name, effective_billing_entity
from crm_app.contract_signature_layouts import (
    SIGNATURE_LAYOUT_SLOTS,
    SIGNATURE_LAYOUT_TOKEN_PATTERN,
    canonical_signature_slot,
)


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


# Customer wording that belongs inside a numbered principal-terms clause, not
# in "Additional terms and conditions" after clause 8. 12 Oct 2026: The Naka
# Phuket wanted its e-signature sentences under clause 4 (Duration), as in the
# prior agreement. In custom_terms, a line "[under: duration]" starts a block
# for that clause; text before the first marker stays an additional term.
# Other bracketed lines are ordinary wording and print as written.
CLAUSE_PLACEMENTS = ('commencement', 'duration', 'payment', 'activation')
_CLAUSE_PLACEMENT_MARKER = re.compile(
    r'^[ \t]*\[\s*under\s*:\s*(' + '|'.join(CLAUSE_PLACEMENTS) + r')\s*\][ \t]*(?:\r?\n|$)',
    re.I | re.M,
)


def split_clause_placements(value):
    """Split custom_terms into (additional terms, {clause: wording})."""
    value = value or ''
    parts = _CLAUSE_PLACEMENT_MARKER.split(value)
    if len(parts) == 1:
        return value, {}
    placed = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        body = body.strip()
        if body:
            name = name.lower()
            placed[name] = placed[name] + '\n' + body if name in placed else body
    return parts[0].strip(), placed


def clause_addition_markup(placed, clause, *, record=None):
    """Markup appended inside a numbered clause, on its own line.

    The placed wording comes from the contract's custom_terms (``record``).
    """
    value = placed.get(clause, '')
    if not clean_text(value).strip():
        return ''
    text = stored_markup(clean_text(value), field='Contract.custom_terms', record=record)
    return '<br/>' + text.replace('\n', '<br/>')


def full_template_source(contract):
    """Select an explicit full-body override without mutating its shared template.

    Structural table/signature slots distinguish a complete template body from
    an ordinary preamble clause. A full override must retain the selected
    template's structural slots; incomplete copies are rejected, never guessed.
    """
    template = getattr(contract, 'preamble_template', None)
    content = getattr(template, 'content', '') or ''
    custom = getattr(contract, 'preamble_custom', '') or ''
    structural_pattern = r'\{\{\s*(zones_table|' + '|'.join(
        re.escape(slot) for slot in SIGNATURE_LAYOUT_SLOTS
    ) + r')\s*\}\}'
    structural = lambda text: {
        canonical_signature_slot(slot)
        for slot in re.findall(structural_pattern, text)
    }
    custom_slots = structural(custom)
    if custom_slots:
        required = structural(content)
        if not template or 'zones_table' not in custom_slots or custom_slots != required:
            raise ContractTailoringClarification([{
                'field': 'preamble_custom',
                'accepted_slots': sorted(required) or ['preamble_template'],
            }])
        return custom, True
    return content, False


def tailored_template_content(contract, resolved_content=None):
    """Resolve explicit slots; never drop an edit or append conflicting terms.

    Additional terms and a payment schedule have a safe insertion point before
    signatures. Replacing existing legal prose needs a named replacement slot.
    Dynamic values stay plain text; template markup remains the template's.
    """
    content, full_body_override = full_template_source(contract)
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
        if field == 'preamble_custom' and full_body_override:
            continue
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
            content = content.replace(slot, filled_text(value) if getattr(contract, field, '') else stored_markup(
                clean_text(value), field='ContractTemplate.content', record=getattr(selected, 'pk', None)))
    additional_terms, placed = split_clause_placements(getattr(contract, 'custom_terms', ''))
    for clause in CLAUSE_PLACEMENTS:
        slot = f'{{{{under_{clause}}}}}'
        value = placed.get(clause, '')
        if value and slot not in content and not already_present(value):
            missing.append({'field': 'custom_terms', 'accepted_slots': [f'under_{clause}']})
        content = content.replace(slot, filled_text(value) if value else '')
    if missing:
        raise ContractTailoringClarification(missing)

    custom_services = getattr(contract, 'custom_service_items', None) or []
    if custom_services:
        if '{{service_items}}' not in content:
            raise ContractTailoringClarification([{'field': 'custom_service_items', 'accepted_slots': ['service_items']}])
        content = content.replace('{{service_items}}', '<br/>'.join(
            filled_text(item.get('name', '')) + (': ' + filled_text(item['description']) if item.get('description') else '')
            for item in custom_services if isinstance(item, dict)
        ))
    else:
        content = content.replace('{{service_items}}', '')

    inserts = []
    for field, slots, heading in (
        ('custom_terms', ('additional_terms', 'custom_terms'), 'Additional terms and conditions'),
        ('payment_schedule', ('payment_schedule',), 'Payment schedule'),
    ):
        value = (additional_terms if field == 'custom_terms' else getattr(contract, field, '')) or ''
        found = [f'{{{{{slot}}}}}' for slot in slots if f'{{{{{slot}}}}}' in content]
        for slot in found:
            content = content.replace(slot, filled_text(value) if value.strip() else '')
        if value.strip() and not found and not already_present(value):
            inserts.append(literal_hyphens(optional_clause_markup(heading, value)))
    if inserts:
        extra = '<br/><br/>'.join(inserts) + '<br/><br/>'
        # Place the additions before the complete signature segment, including
        # its heading if separated from the body by a paragraph break.
        signature_marker = re.search(SIGNATURE_LAYOUT_TOKEN_PATTERN, content)
        if signature_marker:
            marker = signature_marker.start()
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


# A hyphen that could join others into the full-template page-break marker
# "---": one beside another hyphen, or at either end of a filled value.
_MARKER_HYPHEN = re.compile(r'^-|-$|-(?=-)|(?<=-)-')


def literal_hyphens(markup):
    """Write a filled value's marker-forming hyphens as "&#45;".

    The full-template layout starts a page at "---" after the template's
    values are filled in. A value such as "Alpha---Beta" is plain text and
    prints its hyphens; the entity prints the same character.
    """
    return _MARKER_HYPHEN.sub('&#45;', markup)


_HYPHEN_RUN = re.compile(r'-+')


def fill_template_values(content, values):
    """Fill each "{{variable}}" in content with its value, in one pass.

    A value that itself contains "{{variable}}" text prints as written. An
    empty value can bring the template's own hyphens on either side of it
    together ("A--{{x}}-B" with x empty). When no side holds three hyphens of
    its own, the hyphens they form are written as "&#45;", which prints the
    same character, so the layout does not read them as a "---" marker the
    template never wrote. Every other run of hyphens is left as it is.
    """
    parts, joins, length, position = [], [], 0, 0
    for match in re.finditer('|'.join(map(re.escape, values)), content):
        literal, value = content[position:match.start()], values[match.group(0)]
        if not value:
            joins.append(length + len(literal))
        parts += [literal, value]
        length += len(literal) + len(value)
        position = match.end()
    parts.append(content[position:])
    text = ''.join(parts)

    def run(match):
        cuts = [join - match.start() for join in joins if match.start() < join < match.end()]
        bounds = [0, *cuts, len(match.group(0))]
        if not cuts or len(match.group(0)) < 3 or max(b - a for a, b in zip(bounds, bounds[1:])) >= 3:
            return match.group(0)
        return '&#45;' * len(match.group(0))
    return _HYPHEN_RUN.sub(run, text) if joins else text


def filled_text(value):
    """html_text() for a plain value filled into a full template."""
    return literal_hyphens(html_text(value))


def paragraph_text(value):
    """Escape one stored plain-text value for ReportLab Paragraph markup.

    ReportLab parses Paragraph source as markup, so a stored "F&B" prints as
    "F&B;" and "<Ops>" disappears. Every database value and template variable
    that code places into Paragraph markup goes through this exactly once; the
    tags the code adds around it (<b>, <br/>) keep working.
    """
    return '' if value is None else escape(str(value))


# "&" that does not start a character or entity reference. ReportLab misreads
# it ("F&B" prints as "F&B;").
_BARE_AMPERSAND = re.compile(r'&(?!#[0-9]+;|#[xX][0-9a-fA-F]+;|[A-Za-z][A-Za-z0-9]*;)')
_CHARACTER_REFERENCE = re.compile(r'&#(?:([0-9]+)|[xX]([0-9a-fA-F]+));')
# The formatting tags contract text fields accept. An opening tag may carry
# name="value" attributes (they are dropped); anything else, such as the prose
# "A<B and C>D", is text. Tag names and spacing are ASCII only (re.A), so no
# other letter or space case-folds into an allowed tag.
_TAG_ATTRIBUTES = r'''(?:\s+[A-Za-z_:][-\w:.]*\s*=\s*(?:"[^"<>]*"|'[^'<>]*'))*'''
_FORMATTING_TAG = re.compile(
    r'<(?:/(b|i|u|strong|em|super|sub)\s*|(b|i|u|strong|em|super|sub)' + _TAG_ATTRIBUTES + r'\s*)>'
    r'|<br' + _TAG_ATTRIBUTES + r'\s*/?\s*>', re.I | re.A)
# Pasted Word formatting; the document, not the paste, owns typography.
_PASTED_FONT_TAG = re.compile(r'</?(?:font|span)\b[^<>]*>', re.I | re.A)


def _character_reference(match):
    code = int(match.group(1) or match.group(2), 10 if match.group(1) else 16)
    if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF:
        return match.group(0)
    return '&amp;' + match.group(0)[1:]


def paragraph_markup(value):
    """Guard stored wording that is Paragraph markup by design.

    Template bodies, corporate clause text, custom_terms and the standard
    agreement's custom preamble/payment/activation wording accept basic
    formatting tags only: b, i, u, br, strong, em, super and sub, written
    without attributes. Pasted font/span tags are dropped and their text kept.
    Every other "<" and every bare "&" is escaped, so it prints as written;
    entities keep working. Idempotent: guarded or escaped text is returned
    unchanged, so it can never double-escape.
    """
    text = '' if value is None else str(value)
    text = _PASTED_FONT_TAG.sub('', text)
    text = _CHARACTER_REFERENCE.sub(_character_reference, _BARE_AMPERSAND.sub('&amp;', text))
    parts, position = [], 0
    for match in _FORMATTING_TAG.finditer(text):
        closing, opening = match.group(1), match.group(2)
        tag = f'</{closing.lower()}>' if closing else f'<{opening.lower()}>' if opening else '<br/>'
        parts += [text[position:match.start()].replace('<', '&lt;'), tag]
        position = match.end()
    parts.append(text[position:].replace('<', '&lt;'))
    return ''.join(parts)


logger = logging.getLogger(__name__)
_MARKUP_CHECK_STYLE = ParagraphStyle('stored-markup-check')


def _markup_parses(text, pieces=None):
    for piece in [text] + (list(pieces(text)) if pieces else []):
        try:
            Paragraph(piece or '', _MARKUP_CHECK_STYLE)
        except Exception:
            return False
    return True


_LINE_BREAK_TAG = re.compile(r'<br' + _TAG_ATTRIBUTES + r'\s*/?\s*>', re.I | re.A)


def markup_as_text(value):
    """Stored wording as plain text: every tag prints as written.

    Line breaks stay line breaks and entities are decoded, as the markup would
    have printed them, so a stored "&amp;" prints as "&". Values a full
    template body already holds escaped are not escaped a second time.
    """
    text = '' if value is None else str(value)
    text = _CHARACTER_REFERENCE.sub(_character_reference, _BARE_AMPERSAND.sub('&amp;', text))
    return '<br/>'.join(part.replace('<', '&lt;') for part in _LINE_BREAK_TAG.split(text))


def stored_markup(value, *, field, record=None, pieces=None):
    """paragraph_markup() for one stored wording field, sure to render.

    Guarded formatting tags can still fail to pair up (an unclosed <b>, tags
    closed out of order). Such a value prints as plain text instead, so a
    malformed value can no longer stop a PDF from rendering (markup_as_text).
    ``pieces`` returns the parts the layout turns into separate paragraphs;
    each must then render on its own as well. The warning names the field and the record, never the
    wording.
    """
    text = paragraph_markup(value)
    if _markup_parses(text, pieces):
        return text
    logger.warning('Contract PDF: %s on record %s has formatting tags that do not pair up; '
                   'printed as plain text.', field, record)
    return markup_as_text(value)


def _markup(text):
    # A pasted clause may carry Word font/color/size tags. Keep semantic inline
    # emphasis but let the document, not pasted formatting, own typography.
    text = paragraph_markup(clean_text(text))
    text = re.sub(r'</?(?:font|span)\b[^>]*>', '', text, flags=re.I)
    return text


def optional_clause_markup(label, value, *, allow_markup=False, record=None):
    """Render supplied optional wording as part of the agreement body.

    These fields are not a source of new terms or approval authority. Their
    caller supplies the wording; blank fields produce no label. Keep the label
    inline so it cannot become an oversized or orphaned section heading.
    Markup is allowed only for the contract's custom_terms (``record``).
    """
    if not clean_text(value).strip():
        return ''
    text = (stored_markup(clean_text(value), field='Contract.custom_terms', record=record).replace('\n', '<br/>')
            if allow_markup else html_text(value))
    return f'<b>{html_text(label)}:</b> {text}'


def optional_clause_paragraph(label, value, style, *, allow_markup=False, record=None):
    text = optional_clause_markup(label, value, allow_markup=allow_markup, record=record)
    return Paragraph(text, style) if text else None


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
    # Every contract body paragraph and table cell is printed from here. The
    # markup is already escaped; Thai runs switch font after parsing.
    paragraph = ThaiAwareParagraph(text, style)
    paragraph._bmasia_source_style = name
    return paragraph


def _signature_table(source, width, styles):
    """Lay out legacy signing content on shared rows, not offset nested columns.

    This is a layout-only adapter: use the exact existing names, dates, entities,
    authority text and image resources. Never add a signature or change a signer.
    Equal signing areas and real rules replace oversized images/negative padding.
    Each signer pair is atomic. A short execution section containing at most
    two pairs is also atomic so the primary and additional customer signer do
    not straddle pages. Larger signer sets stay row-splittable here; the
    page flow keeps them whole when they fit (_keep_execution_section) and
    lets them continue onto another page only when they are taller than one.
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
    # A supplier/customer pair followed by one additional customer signer is
    # short enough to fit in the document frame. Keep that complete execution
    # section together so pagination cannot leave the first customer signer on
    # the preceding page. Larger sets remain row-splittable to avoid a layout
    # error when the full section is taller than one page; _flowables keeps
    # them together whenever they fit (_keep_execution_section).
    table = _signature_rows(pairs, width, splittable=len(pairs) > 2)
    table._bmasia_signature_pairs = True
    return table


def _signature_rows(pairs, width, *, splittable):
    """The outer signing table: one row per signer pair, each pair atomic."""
    table = Table(pairs, colWidths=[width], hAlign='LEFT', splitByRow=1 if splittable else 0)
    table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
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
    # A signing table that is not laid out as signer pairs: the master and
    # participation formats and the opt-in witness layout. It cannot split.
    table._bmasia_execution_table = not nested and '___' in text
    return table


def _flowables(source, width, styles, *, cell=False, execution=True):
    output = []
    for item in source:
        if isinstance(item, Paragraph):
            # Split every explicit source line before ReportLab paginates it.
            # When a single very long Paragraph containing many <br/> tags is
            # split across pages, ReportLab can retain the fragment's original
            # line offsets and paint continuation text into the running header.
            # One source line per Paragraph also gives the layout engine real
            # semantic break points instead of cutting a numbered clause/list
            # at an arbitrary visual line.
            tokens = re.split(r'((?:<br\s*/?>\s*)+)', item.text, flags=re.I)
            parts = []
            for position in range(0, len(tokens), 2):
                part = tokens[position]
                following = tokens[position + 1] if position + 1 < len(tokens) else ''
                parts.append((part, len(re.findall(r'<br\s*/?>', following, flags=re.I))))
            # Inline emphasis may span a paragraph boundary. Keep that one
            # balanced paragraph intact rather than feed malformed fragments.
            if any(len(re.findall(r'<(?:b|i|u|strong|em|super|sub)>', part, re.I | re.A)) !=
                   len(re.findall(r'</(?:b|i|u|strong|em|super|sub)>', part, re.I | re.A)) for part, _ in parts):
                parts = [(item.text, 0)]
            explicit_group = object()
            for part, break_count in parts:
                if part.strip():
                    p = _paragraph(Paragraph(_markup(part), item.style), styles, cell=cell)
                    p._bmasia_explicit_group = explicit_group
                    if not cell and break_count == 1:
                        p.style.spaceAfter = 0
                    if re.fullmatch(r'\s*<b>[^<]+</b>\s*', part):
                        p.style.keepWithNext = True
                    output.append(p)
        elif isinstance(item, Table):
            output.append(_table(item, width, styles, nested=cell))
        elif isinstance(item, KeepTogether):
            # The execution-section pass runs once, on the outer flow: the
            # groups it would make here are flattened just below.
            children = _flowables(item._content, width, styles, cell=cell, execution=False)
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
            _mark_signing_lead(children)
            # Legal schedules without vertical spans may flow across pages.
            # A short zones table can have more than eight rows but span its
            # Property/Service cells down every row, making it indivisible.
            # Keep its heading with that table instead of stranding the heading
            # at the foot of the preceding page.
            long_table = any(
                isinstance(v, Table) and len(v._cellvalues) > 8 and not any(
                    start[1] != end[1] for _, start, end in v._spanCmds
                )
                for v in children
            )
            signature_pairs = any(getattr(v, '_bmasia_signature_pairs', False) for v in children)
            if signature_pairs or (long_table and '___' not in _plain(item._content)):
                output.extend(children)
            else:
                output.append(KeepTogether(_keep_execution_intro_with_table(children, width)))
        elif isinstance(item, Spacer):
            output.append(Spacer(1, min(item.height, 14)))
        else:
            output.append(item)
    # Legacy clause/status/signature builders each add their own separator.
    # After flattening, adjacent separators describe the same visual gap;
    # accumulating them can push an otherwise fitting closing block to a
    # separate page. Preserve the largest gap and all signing space inside
    # the signature table, without shrinking text or page margins.
    spaced = []
    for item in output:
        if isinstance(item, Spacer) and spaced and isinstance(spaced[-1], Spacer):
            spaced[-1] = Spacer(1, max(spaced[-1].height, item.height))
        else:
            spaced.append(item)
    output = spaced
    # A short service-package or deliverables list should stay together instead
    # of leaving its final items alone on the next page. Large/custom lists must
    # still be able to flow normally.
    grouped, index = [], 0
    while index < len(output):
        item = output[index]
        end = index + 1
        plain_text = item.getPlainText().strip() if isinstance(item, Paragraph) else ''
        is_service_packages = 'Service Packages' in plain_text
        is_deliverables = bool(re.fullmatch(
            r'\d+\.\s*Deliverables and timelines:', plain_text, flags=re.I,
        ))
        if isinstance(item, Paragraph) and (is_service_packages or is_deliverables):
            explicit_group = getattr(item, '_bmasia_explicit_group', None)
            while end < len(output):
                candidate = output[end]
                same_explicit_group = (
                    explicit_group is not None and
                    getattr(candidate, '_bmasia_explicit_group', None) is explicit_group
                )
                if is_service_packages:
                    belongs = (
                        getattr(candidate, '_bmasia_source_style', '') == 'bulletstyle' or
                        same_explicit_group
                    )
                else:
                    candidate_text = (
                        candidate.getPlainText().strip()
                        if isinstance(candidate, Paragraph) else ''
                    )
                    belongs = same_explicit_group and not re.match(
                        r'\d+\.\s+', candidate_text,
                    )
                if not belongs:
                    break
                end += 1
        if end > index + 1:
            group = output[index:end]
            height = sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in group)
            deliverable_count = len(group) - 1 if is_deliverables else 0
            service_item_count = len(group) - 1 if is_service_packages else 0
            charged_player_package = is_service_packages and any(
                isinstance(candidate, Paragraph) and
                'charged as itemized below' in candidate.getPlainText().casefold()
                for candidate in group
            )
            if charged_player_package and service_item_count >= 6:
                # Keep the heading with the first half, then keep the remaining
                # bullets together. A six-line player-box package otherwise
                # moves wholesale to page two and leaves an avoidable half-page
                # gap after the zone schedule.
                split_at = 1 + (service_item_count // 2)
                grouped.append(KeepTogether(group[:split_at]))
                grouped.append(KeepTogether(group[split_at:]))
            elif is_deliverables and deliverable_count >= 6:
                # Preserve useful space on the current page while preventing a
                # short tail of deliverables on the next one. Two balanced,
                # indivisible halves avoid both the 5/3 orphan and a mostly
                # empty extra final page caused by moving the entire list.
                split_at = 1 + (deliverable_count // 2)
                grouped.append(KeepTogether(group[:split_at]))
                grouped.append(KeepTogether(group[split_at:]))
            elif height <= 200:
                grouped.append(KeepTogether(group))
            else:
                item.style.keepWithNext = True
                grouped.extend(group)
        else:
            grouped.append(item)
        index = end
    if not cell:
        grouped = _keep_commencement_with_duration(grouped, width)
    if execution and not cell:
        grouped = _keep_execution_section(grouped, width)
    # If a signing pair has to move, bring its short closing context with it.
    # A signature-only continuation page has no contractual context. Standard
    # templates end with numbered Contacts; Hilton uses an execution sentence.
    # Do not bind arbitrary long legal prose or multiple signer pairs together.
    for position, item in enumerate(grouped):
        if not getattr(item, '_bmasia_signature_pairs', False) or len(item._cellvalues) != 1:
            continue
        for start in range(position - 1, max(-1, position - 9), -1):
            previous = grouped[start]
            if not isinstance(previous, (Paragraph, Spacer)):
                break
            previous_text = previous.getPlainText().strip() if isinstance(previous, Paragraph) else ''
            if isinstance(previous, Paragraph) and (
                re.fullmatch(r'\d+\.\s*Contacts:', previous_text) or
                previous_text.casefold().startswith('in witness whereof')
            ):
                closing = grouped[start:position + 1]
                height = sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in closing)
                if height < 300:
                    grouped[start:position + 1] = [KeepTogether(closing)]
                break
    return grouped


_NUMBERED_CLAUSE = re.compile(r'(\d+)\.\s+')
_COMMENCEMENT_CLAUSE = re.compile(r'(\d+)\.\s*Commencement Date\b', re.I)
_DURATION_CLAUSE = re.compile(r'\d+\.\s*Duration\b', re.I)
# Points. Same bound as a short service-package list: small enough that moving
# a kept group to the next page never leaves a large gap behind it.
_COMMENCEMENT_JOINT_MAX_HEIGHT = 200


def _keep_commencement_with_duration(items, width):
    """Never leave the Commencement Date clause alone at the foot of a page.

    18 Nov 2026, DRAFT-0078 (defect sd-e915228b9697d948): clause 3 (one
    line) ended page 1 and clause 4 (Duration, with its "[under: duration]"
    renewal wording) began page 2. Keep the commencement clause, including
    wording placed under it, with the duration line and, when it fits, the
    first paragraph under that line. Every kept group stays within the height
    cap, so moving it never leaves a large gap; when the commencement wording
    is long, its last paragraph joins the duration line and its first line
    keeps its first paragraph. Only page flow changes; no text is added,
    removed or reordered.
    """
    def text(item):
        return item.getPlainText().strip() if isinstance(item, Paragraph) else ''

    def height(group):
        return sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in group)

    def fits(group):
        return height(group) <= _COMMENCEMENT_JOINT_MAX_HEIGHT

    def duration_after(index):
        # Wording under clause N, up to the Duration line. Numbered lines in
        # clause N's own source paragraph ("1. Installation") are its wording,
        # unless numbered N+1; any other numbered line is a different clause.
        number = int(_COMMENCEMENT_CLAUSE.match(text(items[index])).group(1))
        group = getattr(items[index], '_bmasia_explicit_group', None)
        position = index + 1
        while position < len(items) and isinstance(items[position], (Paragraph, Spacer)):
            value = text(items[position])
            if _DURATION_CLAUSE.match(value):
                return position
            numbered = _NUMBERED_CLAUSE.match(value)
            if numbered and (
                group is None or
                getattr(items[position], '_bmasia_explicit_group', None) is not group or
                int(numbered.group(1)) == number + 1
            ):
                return None
            position += 1
        return None

    output, index = [], 0
    while index < len(items):
        item = items[index]
        duration = duration_after(index) if _COMMENCEMENT_CLAUSE.match(text(item)) else None
        if duration is None:
            output.append(item)
            index += 1
            continue
        ends = [duration + 1]
        group = getattr(items[duration], '_bmasia_explicit_group', None)
        if (duration + 1 < len(items) and group is not None and
                getattr(items[duration + 1], '_bmasia_explicit_group', None) is group and
                not _NUMBERED_CLAUSE.match(text(items[duration + 1]))):
            ends.insert(0, duration + 2)
        paragraphs = [position for position in range(index, duration)
                      if isinstance(items[position], Paragraph)]
        # Prefer the whole commencement clause; the clause line pairs with its
        # first paragraph, so a later paragraph is the next possible start.
        choice = next(((first, last) for first in [index] + paragraphs[2:]
                       for last in ends if fits(items[first:last])), None)
        first, last = choice or (duration, duration)
        if first > index:
            lead_end = paragraphs[1] + 1 if len(paragraphs) > 1 else None
            if lead_end and lead_end <= first and fits(items[index:lead_end]):
                output.append(KeepTogether(items[index:lead_end]))
                output.extend(items[lead_end:first])
            else:
                output.extend(items[index:first])
        if last > first:
            output.append(KeepTogether(items[first:last]))
        index = last
    return output


# Points. A section that moves goes to a continuation page, so a section that
# fits this frame fits the page it moves to.
_PAGE_FRAME_HEIGHT = PAGE_HEIGHT - CONTINUATION_PAGE_TOP - PAGE_BOTTOM
# Points. The most text that travels with the signatures: the bound PR 53 and
# the short service-package lists use. The standard Contacts clause with a
# status line measures about 140 pt, so it always fits; longer wording only
# keeps its last lines that fit.
_EXECUTION_LEAD_MAX_HEIGHT = 200
# Paragraphs or gaps searched before a signing table. The standard Contacts
# block with a status line uses 8; the height cap is the real limit.
_EXECUTION_LOOKBACK = 12
_CONTACTS_CLAUSE = re.compile(r'\d+\.\s*Contacts:')


def _stack_height(items, width):
    return sum(p.wrap(width, 10000)[1] + p.getSpaceBefore() + p.getSpaceAfter() for p in items)


def _is_signing_table(item):
    return (getattr(item, '_bmasia_signature_pairs', False) or
            getattr(item, '_bmasia_execution_table', False))


def _mark_signing_lead(children):
    """Mark the line a template places right before its signature token.

    A template's signature token arrives in one kept group with the text
    before it (views.py, render_segment). The last paragraph of that text is
    the section's opening line, whatever it says and in whatever script.
    """
    for index, item in enumerate(children):
        if not _is_signing_table(item):
            continue
        position = index - 1
        while position >= 0 and isinstance(children[position], Spacer):
            position -= 1
        if position >= 0 and isinstance(children[position], Paragraph):
            children[position]._bmasia_signing_lead = True


def _execution_lead(items, position, width):
    """The opening line of the execution section at items[position], with what follows it.

    The opening line is found first by structure: the paragraph a template
    placed right before its signature token (_mark_signing_lead), or a line
    that keeps with the next one (a heading such as SIGNATURES, a status
    line). Text extends it back to a numbered "Contacts:" clause or an
    "IN WITNESS WHEREOF" line when one is near; for the standard builder and
    the corporate combined format that is the only route. Of a long lead only
    the last lines that fit _EXECUTION_LEAD_MAX_HEIGHT travel. [] when none.
    """
    start = position
    while (start > 0 and position - start < _EXECUTION_LOOKBACK and
           isinstance(items[start - 1], (Paragraph, Spacer))):
        start -= 1
    run = items[start:position]
    paragraphs = [index for index, item in enumerate(run) if isinstance(item, Paragraph)]
    if not paragraphs:
        return []

    def opens(paragraph):
        text = paragraph.getPlainText().strip()
        return bool(_CONTACTS_CLAUSE.fullmatch(text)) or text.casefold().startswith('in witness whereof')

    opening = next((index for index in reversed(paragraphs) if opens(run[index])), None)
    last = run[paragraphs[-1]]
    if opening is None and (getattr(last, '_bmasia_signing_lead', False) or last.getKeepWithNext()):
        opening = paragraphs[-1]
    if opening is None:
        return []
    lead = run[opening:]
    while lead and (not isinstance(lead[0], Paragraph) or
                    _stack_height(lead, width) > _EXECUTION_LEAD_MAX_HEIGHT):
        lead = lead[1:]
    return lead


def _keep_execution_section(items, width):
    """Keep the execution section on one page whenever it fits on a page.

    17 Nov 2026: with a primary customer signer and two witnesses (three
    signer pairs), the supplier and the primary signer ended one page and
    the witnesses began the next; an opening line could also end a page
    without its signatures. The section is its opening line
    (_execution_lead) and every signer row of both parties:

    1. Opening line and table fit on a page: they move as one unit.
    2. Otherwise, the table fits on a page: the table stays whole and the
       opening line stays on the page before. Signer rows come first.
    3. Otherwise: the opening line keeps the first signer row and the other
       rows follow, splitting only between whole rows.

    One-pair sections keep the rule in _flowables. Only page flow changes;
    no text is added, removed or moved.
    """
    output = []
    for item in items:
        pairs = getattr(item, '_bmasia_signature_pairs', False) and len(item._cellvalues) > 1
        generic = getattr(item, '_bmasia_execution_table', False)
        if not (pairs or generic):
            output.append(item)
            continue
        lead = _execution_lead(output, len(output), width)
        if lead:
            del output[len(output) - len(lead):]
        table_height = _stack_height([item], width)
        if lead and _stack_height(lead, width) + table_height <= _PAGE_FRAME_HEIGHT:
            output.append(KeepTogether(lead + [item]))
            continue
        if table_height <= _PAGE_FRAME_HEIGHT:
            # The table starts a page and the opening line flows before it, as
            # on the old flow. Keeping a clause heading with its next line
            # here would push that line onto the table's page and the table
            # onto a page of its own.
            output.extend(lead)
            output.append(KeepTogether([item]) if pairs and item.splitByRow else item)
            continue
        if pairs:
            rows, row_width = item._cellvalues, item._argW[0]
            first = lead + [_signature_rows(rows[:1], row_width, splittable=False)]
            if _stack_height(first, width) <= _PAGE_FRAME_HEIGHT:
                output.append(KeepTogether(first))
                output.append(_signature_rows(rows[1:], row_width, splittable=True))
                continue
        output.extend(lead)
        output.append(item)
    return output


def _keep_execution_intro_with_table(children, width):
    """Keep an execution section's opening line with its table in a kept group.

    The opt-in witness layout arrives in one kept group with the template
    text before it. The group stays whole when it fits on a page; when it is
    taller, ReportLab flows its content and the opening line could end a page
    while the table starts the next. keepWithNext on the opening line and the
    gaps after it brings them to the table's page. Nothing moves when the
    group fits, because it then stays whole anyway.
    """
    for index, item in enumerate(children):
        if not getattr(item, '_bmasia_execution_table', False):
            continue
        lead = _execution_lead(children, index, width)
        if lead and _stack_height(lead + [item], width) <= _PAGE_FRAME_HEIGHT:
            for value in lead:
                value.keepWithNext = True
    return children


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
    customer_lines = [customer_legal_entity_name(company), address]
    if getattr(company, 'tax_id', ''):
        customer_lines.append(f'Tax ID: {company.tax_id}')
    story.append(identity_cards('Issued by', issuer_lines, 'Prepared for', customer_lines, styles))
    story.append(Spacer(1, 12))
    story.extend(_flowables(body, CONTENT_WIDTH, styles))
    while story and isinstance(story[-1], (Spacer, PageBreak)):
        story.pop()
    return build_document_pdf(story, document_title=title, document_id=document_id,
                              entity=entity, logo_path=logo_path, preview=preview)
