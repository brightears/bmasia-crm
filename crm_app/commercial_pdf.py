"""Shared BMAsia commercial-document PDF foundation.

The module is deliberately independent from Django and database models.  It
contains the approved print-light brand tokens, page templates and reusable
ReportLab components used by the quotation and invoice pilot renderers.
"""

from __future__ import annotations

from copy import copy
from functools import partial
from io import BytesIO
import os
import re
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


PAGE_SIZE = A4
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
PAGE_MARGIN = 20 * mm
FIRST_PAGE_TOP = 31 * mm
CONTINUATION_PAGE_TOP = 27 * mm
PAGE_BOTTOM = 21 * mm
CONTENT_WIDTH = PAGE_WIDTH - (2 * PAGE_MARGIN)

# These are public layout contracts and are intentionally asserted by tests.
AMOUNT_RIGHT_PADDING = 18
TOTALS_SIDE_PADDING = 26
IDENTITY_CARD_GAP = 12
PRODUCT_COLUMN_WIDTH = 78
TOTALS_SECTION_GAP = 14

STANDARD_SERVICE_COPY = (
    "Managed music service with curated scheduling and remote onboarding"
)

NAVY = colors.HexColor("#06111A")
INK = colors.HexColor("#101A27")
MUTED = colors.HexColor("#66717D")
ORANGE = colors.HexColor("#E8850C")
ORANGE_TEXT = colors.HexColor("#B35F00")
GOLD = colors.HexColor("#EFA634")
TEAL = colors.HexColor("#00C6D7")
GREEN = colors.HexColor("#73CF98")
SURFACE = colors.HexColor("#F4F6F8")
ALT_SURFACE = colors.HexColor("#FAFBFC")
LINE = colors.HexColor("#D9E0E6")
PREVIEW_INK = colors.HexColor("#E4E8EC")
WHITE = colors.white

BODY_FONT = "DejaVuSans"
BOLD_FONT = "DejaVuSans-Bold"


ENTITY_PROFILES = {
    "BMAsia (Thailand) Co., Ltd.": {
        "name": "BMAsia (Thailand) Co., Ltd.",
        "address": (
            "725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, "
            "Klongtan Nuea Watthana, Bangkok 10110, Thailand"
        ),
        "phone": "+66 2153 3520",
        "tax": "0105548025073",
        "registration_number": None,
        "bank": "TMBThanachart Bank, Thonglor Soi 17 Branch",
        "swift": "TMBKTHBK",
        "account": "916-1-00579-9",
        "payment_terms_default": (
            "by bank transfer on a net received, paid in full basis, with no offset "
            "to BMA's TMB-Thanachart Bank, Bangkok, Thailand due immediately on "
            "invoicing to activate the music subscription. All outbound and inbound "
            "bank transfer fees are borne by the Client in remitting payments as "
            "invoiced less Withholding Tax required by Thai Law."
        ),
        "billing_entity": "BMAsia (Thailand) Co., Ltd.",
    },
    "BMAsia Limited": {
        "name": "BMAsia Limited",
        "address": "22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong",
        "phone": "+66 2153 3520",
        "tax": None,
        "registration_number": "34683002-000-05-26-3",
        "bank": "HSBC, HK",
        "swift": "HSBCHKHHHKH",
        "account": "808-021570-838",
        "payment_terms_default": (
            "by bank transfer on a net received, paid in full basis, with no offset "
            "to BMA's HSBC Bank, Hong Kong due immediately as invoiced to activate "
            "the music subscription. All Bank transfer fees, and all taxes are borne "
            "by the Client in remitting payments as invoiced."
        ),
        "billing_entity": "BMAsia Limited",
    },
}


def entity_profile_for(billing_entity):
    """Return a detached, validated issuer profile for the requested entity."""
    if billing_entity not in ENTITY_PROFILES:
        raise ValueError(f"Unsupported billing entity: {clean_text(billing_entity) or 'blank'}")
    return dict(ENTITY_PROFILES[billing_entity])


def ensure_pdf_fonts():
    """Register the Unicode-capable fonts used by the renderers exactly once."""
    font_candidates = {
        BODY_FONT: (
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "Vera.ttf",
        ),
        BOLD_FONT: (
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "VeraBd.ttf",
        ),
    }
    for font_name, candidates in font_candidates.items():
        try:
            pdfmetrics.getFont(font_name)
            continue
        except KeyError:
            pass
        last_error = None
        for candidate in candidates:
            try:
                pdfmetrics.registerFont(TTFont(font_name, candidate))
                break
            except Exception as exc:  # pragma: no cover - candidate availability differs by host
                last_error = exc
        else:  # pragma: no cover - exercised only on a misconfigured runtime
            raise RuntimeError(f"Unable to register required PDF font {font_name}") from last_error


_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u00a0": " ",
})


def clean_text(value):
    """Normalize renderer input without changing substantive wording."""
    return str(value or "").translate(_DASH_TRANSLATION).replace("\r\n", "\n").replace("\r", "\n")


def _product_key(value):
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).casefold())


_SUBSCRIPTION_PRODUCT_LABELS = {
    "bb": "Beat Breeze",
    "beatbreze": "Beat Breeze",
    "beatbreeze": "Beat Breeze",
    "soundtrack": "Soundtrack",
    "soundtrackyourbrand": "Soundtrack",
    "syb": "Soundtrack",
}

_SUBSCRIPTION_PRODUCT_CODES = {
    "bb": "BB",
    "beatbreze": "BB",
    "beatbreeze": "BB",
    "soundtrack": "SYB",
    "soundtrackyourbrand": "SYB",
    "syb": "SYB",
}

_STANDARD_SERVICE_RE = re.compile(
    r"managed\s+music\s+service\s+with\s+curated\s+scheduling\s+and\s+remote\s+onboarding",
    flags=re.IGNORECASE,
)


def commercial_product_label(value):
    """Return the concise customer-facing service name used in line-item tables."""
    raw = clean_text(value).strip()
    return _SUBSCRIPTION_PRODUCT_LABELS.get(_product_key(raw), raw or "Service")


def is_subscription_product(value):
    return _product_key(value) in _SUBSCRIPTION_PRODUCT_LABELS


def contains_standard_service_copy(value):
    return bool(_STANDARD_SERVICE_RE.search(clean_text(value)))


def compact_line_item_description(value, *, product=None, strip_standard_service_copy=False):
    """Keep a line item's specific zone/detail while removing safe repetition.

    Only the exact shared service sentence is removed, and only when the caller
    has established a multi-zone presentation. Product names are removed only
    when they are an explicit prefix followed by a separator. All other
    customer-authored wording remains untouched.
    """
    text = clean_text(value).strip()
    if not text:
        return ""

    product_key = _product_key(product)
    aliases = {
        clean_text(product).strip(),
        commercial_product_label(product),
        _SUBSCRIPTION_PRODUCT_CODES.get(product_key, ""),
    }
    for alias in sorted((item for item in aliases if item), key=len, reverse=True):
        if normalized_visible_text(text) == normalized_visible_text(alias):
            text = ""
            break
        text = re.sub(
            rf"^\s*{re.escape(alias)}\s*(?:[-:|]\s*)",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )

    if strip_standard_service_copy:
        text = _STANDARD_SERVICE_RE.sub("", text)
        text = re.sub(r"\s*[-:|]\s*[-:|]\s*", " - ", text)
    return text.strip(" \t\n-:|")


def html_text(value):
    """Escape plain text for a ReportLab Paragraph and preserve explicit lines."""
    return "<br/>".join(escape(line) for line in clean_text(value).split("\n"))


def html_lines(values):
    return "<br/>".join(html_text(value) for value in values if clean_text(value).strip())


def normalized_visible_text(value):
    text = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def is_duplicate_visible_block(candidate, prior_blocks):
    """Detect only exact duplicates after safe visible normalization.

    A visible block may intentionally extend wording from another section.
    Treating containment as duplication would silently drop the added
    instruction, so only a complete normalized match is suppressed.
    """
    normalized = normalized_visible_text(candidate)
    if not normalized:
        return True
    for prior in prior_blocks:
        other = normalized_visible_text(prior)
        if other and normalized == other:
            return True
    return False


def money(currency, value):
    return f"{clean_text(currency or 'USD')} {value:,.2f}"


def quantity(value):
    try:
        return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"
    except (TypeError, ValueError):
        return clean_text(value)


def _fit_right_style(value, base_style, available_width, *, minimum_font_size=5.8):
    """Shrink an exceptional numeric value just enough to keep it on one line.

    Normal prices remain at the standard body size. This only engages for
    large, still-valid DecimalField values that would otherwise wrap and make
    the number ambiguous.
    """
    style = copy(base_style)
    lines = clean_text(value).split("\n") or [""]
    widest = max(
        (pdfmetrics.stringWidth(line, style.fontName, style.fontSize) for line in lines),
        default=0,
    )
    if widest > available_width > 0:
        style.fontSize = max(
            minimum_font_size,
            style.fontSize * (available_width / widest) * 0.97,
        )
        style.leading = max(style.fontSize * 1.28, style.fontSize + 1.5)
    return style


def document_styles():
    ensure_pdf_fonts()
    base = getSampleStyleSheet()
    for style_name in list(base.byName):
        style = base[style_name]
        if getattr(style, "fontName", "") in {
            "Helvetica",
            "Helvetica-Oblique",
            "Helvetica-BoldOblique",
        }:
            style.fontName = BODY_FONT
        elif getattr(style, "fontName", "") == "Helvetica-Bold":
            style.fontName = BOLD_FONT

    return {
        "title": ParagraphStyle(
            "CommercialTitle",
            parent=base["Heading1"],
            fontName=BOLD_FONT,
            fontSize=24,
            leading=28,
            textColor=INK,
            spaceAfter=6,
            allowWidows=0,
            allowOrphans=0,
        ),
        "lead": ParagraphStyle(
            "CommercialLead",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=9,
            leading=13,
            textColor=MUTED,
            spaceAfter=13,
            allowWidows=0,
            allowOrphans=0,
        ),
        "body": ParagraphStyle(
            "CommercialBody",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=9.2,
            leading=13,
            textColor=INK,
            allowWidows=0,
            allowOrphans=0,
        ),
        "body_right": ParagraphStyle(
            "CommercialBodyRight",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=9.2,
            leading=13,
            textColor=INK,
            alignment=TA_RIGHT,
            allowWidows=0,
            allowOrphans=0,
        ),
        "body_bold": ParagraphStyle(
            "CommercialBodyBold",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=9.2,
            leading=13,
            textColor=INK,
            allowWidows=0,
            allowOrphans=0,
        ),
        "body_bold_right": ParagraphStyle(
            "CommercialBodyBoldRight",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=9.2,
            leading=13,
            textColor=INK,
            alignment=TA_RIGHT,
            allowWidows=0,
            allowOrphans=0,
        ),
        "small": ParagraphStyle(
            "CommercialSmall",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=7.6,
            leading=10.5,
            textColor=MUTED,
            allowWidows=0,
            allowOrphans=0,
        ),
        "small_right": ParagraphStyle(
            "CommercialSmallRight",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=7.6,
            leading=10.5,
            textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        "label": ParagraphStyle(
            "CommercialLabel",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=7,
            leading=9,
            textColor=MUTED,
        ),
        "label_right": ParagraphStyle(
            "CommercialLabelRight",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=7,
            leading=9,
            textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "CommercialSection",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=12,
            leading=15,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=False,
            allowWidows=0,
            allowOrphans=0,
        ),
        "terms": ParagraphStyle(
            "CommercialTerms",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=8.2,
            leading=11.5,
            textColor=INK,
            allowWidows=0,
            allowOrphans=0,
        ),
    }


def _lerp(left, right, position):
    return left + ((right - left) * position)


def _gradient_rule(canvas_obj, x, y, width, height=2.5):
    stops = (ORANGE, GOLD, GREEN, TEAL)
    steps = 96
    for index in range(steps):
        position = index / max(steps - 1, 1)
        scaled = position * (len(stops) - 1)
        stop_index = min(int(scaled), len(stops) - 2)
        local = scaled - stop_index
        left, right = stops[stop_index], stops[stop_index + 1]
        fill = colors.Color(
            _lerp(left.red, right.red, local),
            _lerp(left.green, right.green, local),
            _lerp(left.blue, right.blue, local),
        )
        canvas_obj.setFillColor(fill)
        canvas_obj.rect(x + (width * index / steps), y, (width / steps) + 0.4, height, stroke=0, fill=1)


def _draw_logo(canvas_obj, logo_path, x, y, width=88):
    if logo_path and os.path.exists(logo_path):
        try:
            canvas_obj.drawImage(
                logo_path,
                x,
                y,
                width=width,
                height=width * (377 / 880),
                preserveAspectRatio=True,
                mask="auto",
                anchor="sw",
            )
            return
        except Exception:
            pass
    canvas_obj.setFillColor(INK)
    canvas_obj.setFont(BOLD_FONT, 14)
    canvas_obj.drawString(x, y + 4, "bmasia")


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, footer_context=None, **kwargs):
        self._saved_page_states = []
        self._footer_context = footer_context or {}
        super().__init__(*args, **kwargs)

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for page_state in self._saved_page_states:
            self.__dict__.update(page_state)
            self._draw_footer(page_count)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count):
        entity_name = clean_text(self._footer_context.get("entity_name"))
        document_id = clean_text(self._footer_context.get("document_id"))
        self.saveState()
        self.setStrokeColor(LINE)
        self.setLineWidth(0.55)
        self.line(PAGE_MARGIN, 15 * mm, PAGE_WIDTH - PAGE_MARGIN, 15 * mm)
        self.setFillColor(MUTED)
        self.setFont(BODY_FONT, 6.8)
        self.drawString(PAGE_MARGIN, 10.5 * mm, f"{entity_name}  |  bmasiamusic.com")
        self.drawRightString(
            PAGE_WIDTH - PAGE_MARGIN,
            10.5 * mm,
            f"{document_id}  |  {self._pageNumber} / {page_count}",
        )
        self.restoreState()


class CommercialDocumentTemplate(BaseDocTemplate):
    """A4 flow-based template with distinct first and continuation frames."""

    def __init__(self, filename, *, document_context, **kwargs):
        self.document_context = document_context
        super().__init__(
            filename,
            pagesize=PAGE_SIZE,
            leftMargin=PAGE_MARGIN,
            rightMargin=PAGE_MARGIN,
            topMargin=FIRST_PAGE_TOP,
            bottomMargin=PAGE_BOTTOM,
            **kwargs,
        )
        first_frame = Frame(
            PAGE_MARGIN,
            PAGE_BOTTOM,
            CONTENT_WIDTH,
            PAGE_HEIGHT - FIRST_PAGE_TOP - PAGE_BOTTOM,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="commercial-first-frame",
        )
        continuation_frame = Frame(
            PAGE_MARGIN,
            PAGE_BOTTOM,
            CONTENT_WIDTH,
            PAGE_HEIGHT - CONTINUATION_PAGE_TOP - PAGE_BOTTOM,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="commercial-continuation-frame",
        )
        self.addPageTemplates([
            PageTemplate(
                id="commercial-first",
                frames=[first_frame],
                onPage=self._draw_page_header,
                autoNextPageTemplate="commercial-continuation",
            ),
            PageTemplate(
                id="commercial-continuation",
                frames=[continuation_frame],
                onPage=self._draw_page_header,
                autoNextPageTemplate="commercial-continuation",
            ),
        ])

    def _draw_page_header(self, canvas_obj, _doc):
        context = self.document_context
        canvas_obj.saveState()
        _draw_logo(canvas_obj, context.get("logo_path"), PAGE_MARGIN, PAGE_HEIGHT - 21 * mm, width=84)
        canvas_obj.setFillColor(MUTED)
        canvas_obj.setFont(BOLD_FONT, 6.8)
        canvas_obj.drawRightString(
            PAGE_WIDTH - PAGE_MARGIN,
            PAGE_HEIGHT - 11 * mm,
            clean_text(context.get("document_title", "COMMERCIAL DOCUMENT")).upper(),
        )
        canvas_obj.setFillColor(INK)
        canvas_obj.setFont(BOLD_FONT, 9.5)
        canvas_obj.drawRightString(
            PAGE_WIDTH - PAGE_MARGIN,
            PAGE_HEIGHT - 16.2 * mm,
            clean_text(context.get("document_id")),
        )
        _gradient_rule(canvas_obj, 0, PAGE_HEIGHT - 25.3 * mm, PAGE_WIDTH)
        if context.get("preview"):
            canvas_obj.saveState()
            canvas_obj.translate(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)
            canvas_obj.rotate(33)
            canvas_obj.setFillColor(PREVIEW_INK)
            canvas_obj.setFont(BOLD_FONT, 25)
            canvas_obj.drawCentredString(0, 0, "DRAFT PREVIEW - NOT FOR CUSTOMER")
            canvas_obj.restoreState()
        canvas_obj.restoreState()


def build_document_pdf(story, *, document_title, document_id, entity, logo_path=None, preview=False):
    buffer = BytesIO()
    context = {
        "document_title": document_title,
        "document_id": document_id,
        "entity_name": entity["name"],
        "logo_path": logo_path,
        "preview": preview,
    }
    doc = CommercialDocumentTemplate(buffer, document_context=context)
    canvas_factory = partial(
        _NumberedCanvas,
        footer_context={"entity_name": entity["name"], "document_id": document_id},
    )
    doc.build(story, canvasmaker=canvas_factory)
    value = buffer.getvalue()
    buffer.close()
    return value


def document_intro(title, lead, styles):
    return [
        Paragraph(escape(clean_text(title)), styles["title"]),
        Paragraph(html_text(lead), styles["lead"]),
    ]


def metadata_table(items, styles):
    values = list(items)
    width = CONTENT_WIDTH / len(values)
    data = [
        [Paragraph(escape(clean_text(label).upper()), styles["label"]) for label, _ in values],
        [Paragraph(html_text(value), styles["body_bold"]) for _, value in values],
    ]
    table = Table(data, colWidths=[width] * len(values), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.65, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return KeepTogether([table, Spacer(1, 14)])


def _identity_card_body(lines, styles):
    content = list(lines)
    if content:
        first, rest = content[0], content[1:]
        body_markup = f"<b>{escape(clean_text(first))}</b>"
        if rest:
            body_markup += "<br/>" + html_lines(rest)
    else:
        body_markup = ""
    return Paragraph(body_markup, styles["body"])


def identity_cards(left_title, left_lines, right_title, right_lines, styles):
    """Build two true sibling cards with equal outer width and height."""
    width = (CONTENT_WIDTH - IDENTITY_CARD_GAP) / 2
    outer = Table([
        [
            Paragraph(escape(clean_text(left_title).upper()), styles["label"]),
            "",
            Paragraph(escape(clean_text(right_title).upper()), styles["label"]),
        ],
        [
            _identity_card_body(left_lines, styles),
            "",
            _identity_card_body(right_lines, styles),
        ],
    ], colWidths=[width, IDENTITY_CARD_GAP, width], hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 1), WHITE),
        ("BACKGROUND", (2, 0), (2, 1), WHITE),
        ("BOX", (0, 0), (0, 1), 0.65, LINE),
        ("BOX", (2, 0), (2, 1), 0.65, LINE),
        ("LINEBELOW", (0, 0), (0, 0), 1.25, ORANGE),
        ("LINEBELOW", (2, 0), (2, 0), 1.25, ORANGE),
        ("LEFTPADDING", (0, 0), (0, 1), 12),
        ("RIGHTPADDING", (0, 0), (0, 1), 12),
        ("LEFTPADDING", (2, 0), (2, 1), 12),
        ("RIGHTPADDING", (2, 0), (2, 1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("TOPPADDING", (2, 0), (2, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (2, 0), (2, 0), 6),
        ("TOPPADDING", (0, 1), (0, 1), 8),
        ("TOPPADDING", (2, 1), (2, 1), 8),
        ("BOTTOMPADDING", (0, 1), (0, 1), 10),
        ("BOTTOMPADDING", (2, 1), (2, 1), 10),
        ("LEFTPADDING", (1, 0), (1, 1), 0),
        ("RIGHTPADDING", (1, 0), (1, 1), 0),
        ("TOPPADDING", (1, 0), (1, 1), 0),
        ("BOTTOMPADDING", (1, 0), (1, 1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return KeepTogether([outer, Spacer(1, 9)])


def section_heading(number, title, styles):
    number_style = copy(styles["label"])
    number_style.textColor = ORANGE_TEXT
    table = Table([
        [Paragraph(escape(clean_text(number)), number_style), Paragraph(escape(clean_text(title)), styles["section"])],
    ], colWidths=[28, CONTENT_WIDTH - 28], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def section_start(number, title, styles, minimum_following_height=72):
    """Keep a section heading away from the foot of a page without grouping
    it with an arbitrarily large table or terms block.

    ``keepWithNext`` is intentionally avoided here: ReportLab can otherwise
    move a splittable multi-page table wholesale to the next page, leaving an
    almost empty first page.  The conditional break reserves enough room for
    the heading plus a table header and at least one useful content row.
    """
    return [
        CondPageBreak(minimum_following_height),
        section_heading(number, title, styles),
    ]


def totals_panel(rows, styles, width=300):
    parsed = []
    for index, (label, value) in enumerate(rows):
        is_last = index == len(rows) - 1
        value_style = _fit_right_style(
            value,
            styles["body_bold_right"] if is_last else styles["body_right"],
            (width * 0.45) - (2 * TOTALS_SIDE_PADDING),
        )
        parsed.append([
            Paragraph(escape(clean_text(label)), styles["body_bold"] if is_last else styles["body"]),
            Paragraph(
                escape(clean_text(value)).replace(" ", "&#160;"),
                value_style,
            ),
        ])
    table = Table(parsed, colWidths=[width * 0.55, width * 0.45], hAlign="RIGHT")
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.65, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), TOTALS_SIDE_PADDING),
        ("RIGHTPADDING", (0, 0), (-1, -1), TOTALS_SIDE_PADDING),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if parsed:
        commands.extend([
            ("LINEABOVE", (0, -1), (-1, -1), 1.15, ORANGE),
            ("BACKGROUND", (0, -1), (-1, -1), SURFACE),
        ])
    table.setStyle(TableStyle(commands))
    return table


def item_table(
    headers,
    rows,
    widths,
    numeric_columns,
    styles,
    *,
    amount_columns=None,
    totals=None,
    group_rows=None,
):
    amount_columns = set(amount_columns or ())
    group_rows = set(group_rows or ())
    header_cells = []
    for column, value in enumerate(headers):
        style = styles["label_right"] if column in numeric_columns else styles["label"]
        header_cells.append(Paragraph(escape(clean_text(value).upper()), style))

    data = [header_cells]
    for row_index, row in enumerate(rows, start=1):
        if row_index in group_rows:
            data.append([Paragraph(escape(clean_text(row[0]).upper()), styles["label"])] + [""] * (len(headers) - 1))
            continue
        parsed = []
        for column, value in enumerate(row):
            if column in numeric_columns:
                right_padding = AMOUNT_RIGHT_PADDING if column in amount_columns else 9
                style = _fit_right_style(
                    value,
                    styles["body_right"],
                    widths[column] - 9 - right_padding,
                )
            else:
                style = styles["body"]
            if hasattr(value, "wrap"):
                parsed.append(value)
            elif column in numeric_columns:
                numeric_markup = "<br/>".join(
                    escape(line).replace(" ", "&#160;")
                    for line in clean_text(value).split("\n")
                )
                parsed.append(Paragraph(numeric_markup, style))
            else:
                parsed.append(Paragraph(html_text(value), style))
        data.append(parsed)

    totals_row = None
    if totals:
        totals_row = len(data)
        data.append([totals_panel(totals, styles), *([""] * (len(headers) - 1))])

    usable_height = PAGE_HEIGHT - CONTINUATION_PAGE_TOP - PAGE_BOTTOM

    def measured_row_height(row_index):
        row_height = 0
        for column, cell in enumerate(data[row_index]):
            if not hasattr(cell, "wrap"):
                continue
            if row_index in group_rows and column == 0:
                cell_width = CONTENT_WIDTH - 18
            else:
                right_padding = AMOUNT_RIGHT_PADDING if column in amount_columns else 9
                cell_width = max(widths[column] - 9 - right_padding, 1)
            row_height = max(row_height, cell.wrap(cell_width, usable_height)[1])
        return row_height

    last_content_row = totals_row if totals_row is not None else len(data)
    header_height = measured_row_height(0) + 16
    totals_height = (
        data[totals_row][0].wrap(CONTENT_WIDTH, usable_height)[1] + 12
        if totals_row is not None else 0
    )

    def protected_row_height(row_index):
        height = header_height + measured_row_height(row_index) + 14
        if row_index - 1 in group_rows:
            height += measured_row_height(row_index - 1) + 14
        if totals_row is not None and row_index == last_content_row - 1:
            height += totals_height
        return height

    # The threshold includes the repeated header and every block protected with
    # this row. Testing only cell height creates a medium-length crash band in
    # which the cell fits by itself but the complete unsplittable unit does not.
    oversized_rows = {
        row_index
        for row_index in range(1, last_content_row)
        if row_index not in group_rows
        and protected_row_height(row_index) > usable_height
    }

    def build_segment(row_indices, *, include_totals=False, allow_in_row_split=False):
        """Build one table segment with styles remapped to local row indexes.

        ReportLab's ``splitInRow`` flag applies to an entire table and can
        override unrelated ``NOSPLIT`` rules. Oversized rows therefore receive
        their own segment; ordinary rows retain strict group and totals
        pagination guarantees.
        """
        segment_data = [[copy(cell) for cell in header_cells]]
        segment_data.extend(data[row_index] for row_index in row_indices)
        local_groups = {
            local_index
            for local_index, original_index in enumerate(row_indices, start=1)
            if original_index in group_rows
        }
        local_totals_row = None
        if include_totals and totals_row is not None:
            local_totals_row = len(segment_data)
            segment_data.append(data[totals_row])

        table = Table(
            segment_data,
            colWidths=widths,
            repeatRows=1,
            # Tall-row segments must split inside the row on the first pass;
            # otherwise a preceding group heading becomes a header-only
            # fragment. Ordinary segments continue to split strictly by row.
            splitByRow=0 if allow_in_row_split else 1,
            splitInRow=1 if allow_in_row_split else 0,
            hAlign="LEFT",
        )
        content_line_end = local_totals_row - 1 if local_totals_row is not None else -1
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
            ("LINEBELOW", (0, 0), (-1, 0), 1.25, ORANGE),
            ("LINEBELOW", (0, 1), (-1, content_line_end), 0.45, LINE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ALT_SURFACE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for column in numeric_columns:
            commands.append(("ALIGN", (column, 0), (column, -1), "RIGHT"))
        for column in amount_columns:
            commands.append(
                ("RIGHTPADDING", (column, 0), (column, -1), AMOUNT_RIGHT_PADDING)
            )
        for row_index in sorted(local_groups):
            commands.extend([
                ("SPAN", (0, row_index), (-1, row_index)),
                ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#EAF8F9")),
                ("LINEBELOW", (0, row_index), (-1, row_index), 0.8, TEAL),
            ])
            if row_index + 1 < len(segment_data) and not allow_in_row_split:
                commands.append(("NOSPLIT", (0, row_index), (-1, row_index + 1)))
        if local_totals_row is not None:
            commands.extend([
                ("SPAN", (0, local_totals_row), (-1, local_totals_row)),
                ("ALIGN", (0, local_totals_row), (-1, local_totals_row), "RIGHT"),
                ("LEFTPADDING", (0, local_totals_row), (-1, local_totals_row), 0),
                ("RIGHTPADDING", (0, local_totals_row), (-1, local_totals_row), 0),
                ("TOPPADDING", (0, local_totals_row), (-1, local_totals_row), 12),
                ("BOTTOMPADDING", (0, local_totals_row), (-1, local_totals_row), TOTALS_SECTION_GAP),
            ])
            if row_indices and not allow_in_row_split:
                last_height = measured_row_height(row_indices[-1])
                totals_height = data[totals_row][0].wrap(CONTENT_WIDTH, usable_height)[1]
                if last_height + totals_height + 40 <= usable_height:
                    commands.append(
                        ("NOSPLIT", (0, local_totals_row - 1), (-1, local_totals_row))
                    )
        table.setStyle(TableStyle(commands))
        return table

    def build_totals_segment():
        table = Table(
            [[data[totals_row][0], *([""] * (len(headers) - 1))]],
            colWidths=widths,
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)),
            ("ALIGN", (0, 0), (-1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, 0), 0),
            ("RIGHTPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), TOTALS_SECTION_GAP),
        ]))
        return table

    def pre_split_oversized_table(table, maximum_height):
        """Split a tall one-row segment into page-safe table fragments.

        The returned fragments have in-row splitting disabled so the document
        template moves them intact when the current page lacks room. This also
        lets the final fragment be paired with a totals panel using
        ``KeepTogether``.
        """
        pending = table
        fragments = []
        while True:
            pending.wrap(CONTENT_WIDTH, maximum_height)
            if pending._height <= maximum_height:
                pending.splitInRow = 0
                fragments.append(pending)
                break
            parts = pending.split(CONTENT_WIDTH, maximum_height)
            if len(parts) < 2:
                raise ValueError("Commercial PDF row cannot be split safely")
            first, pending = parts[0], parts[1]
            first.splitInRow = 0
            fragments.append(first)
        return fragments

    if not oversized_rows:
        return [
            build_segment(
                list(range(1, last_content_row)),
                include_totals=totals_row is not None,
            )
        ]

    # Isolate every physically oversized row. A group heading immediately
    # before it moves with that segment, and a conditional break guarantees
    # room for the heading/header plus a useful first fragment of the row.
    segments = []
    ordinary_rows = []
    for row_index in range(1, last_content_row):
        if row_index not in oversized_rows:
            ordinary_rows.append(row_index)
            continue

        leading_group = None
        if ordinary_rows and ordinary_rows[-1] in group_rows:
            leading_group = ordinary_rows.pop()
        if ordinary_rows:
            segments.append((ordinary_rows, False, False))
        oversized_segment = [row_index]
        if leading_group is not None:
            oversized_segment.insert(0, leading_group)
        segments.append((oversized_segment, True, leading_group is not None))
        ordinary_rows = []
    if ordinary_rows:
        segments.append((ordinary_rows, False, False))

    flowables = []
    for segment_index, (row_indices, allow_in_row_split, has_group) in enumerate(segments):
        is_final_segment = segment_index == len(segments) - 1
        if allow_in_row_split:
            flowables.append(CondPageBreak(150 if has_group else 96))
            totals_segment = build_totals_segment() if totals_row is not None and is_final_segment else None
            maximum_height = usable_height - 8
            if totals_segment is not None:
                totals_segment.wrap(CONTENT_WIDTH, usable_height)
                maximum_height -= totals_segment._height
            fragments = pre_split_oversized_table(
                build_segment(row_indices, allow_in_row_split=True),
                maximum_height,
            )
            if totals_segment is not None:
                flowables.extend(fragments[:-1])
                flowables.append(KeepTogether([fragments[-1], totals_segment]))
            else:
                flowables.extend(fragments)
            continue
        flowables.append(build_segment(
            row_indices,
            include_totals=totals_row is not None and is_final_segment,
        ))
    return flowables


def payment_block(entity, payment_terms, styles):
    bank_rows = [
        ("Beneficiary", entity["name"]),
        ("Bank", entity["bank"]),
        ("SWIFT code", entity["swift"]),
        ("Account number", entity["account"]),
    ]
    data = [[
        Paragraph(escape(clean_text(label)), styles["label"]),
        Paragraph(html_text(value), styles["body"]),
    ] for label, value in bank_rows]
    table = Table(data, colWidths=[105, CONTENT_WIDTH - 105], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.65, LINE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    # The compact bank table is atomic, while long payment terms remain a
    # normal Paragraph so they can flow safely over as many pages as needed.
    flowables = [table]
    if clean_text(payment_terms).strip():
        terms_markup = (
            f"<font name='{BOLD_FONT}' size='7' color='#66717D'>PAYMENT TERMS</font>"
            f"<br/>{html_text(payment_terms)}"
        )
        flowables.extend([
            Spacer(1, 7),
            # One splittable paragraph prevents the label from being orphaned
            # when a short page remainder cannot hold the first terms line.
            Paragraph(terms_markup, styles["terms"]),
        ])
    return flowables


def remarks_block(remarks, styles):
    if not clean_text(remarks).strip():
        return None
    data = [[
        Paragraph("CUSTOMER REMARKS", styles["label"]),
        Paragraph(html_text(remarks), styles["body"]),
    ]]
    table = Table(
        data,
        colWidths=[112, CONTENT_WIDTH - 112],
        hAlign="LEFT",
        splitByRow=1,
        splitInRow=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF8F9")),
        ("BOX", (0, 0), (-1, -1), 0.65, colors.HexColor("#B6E8EB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table
