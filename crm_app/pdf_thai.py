"""Thai text in ReportLab PDFs: a per-run font fallback.

DejaVu Sans, the body font of every BMAsia PDF, has no Thai glyphs, so a Thai
legal name or address printed as empty boxes. This module keeps DejaVu as the
base font and switches only runs of Thai characters to Sarabun (SIL OFL 1.1),
with the bold DejaVu face mapped to Sarabun Bold. A paragraph without Thai
characters is not touched, so its PDF does not change.

The switch is done on the parsed paragraph fragments, after ReportLab has read
the markup, so it applies to every value however it was escaped or tagged, and
line wrapping measures each run with its own font.

ReportLab 4.0.7 does not shape text. Sarabun places a tone mark at the height
it has above a consonant alone and relies on OpenType rules to lift it over an
upper vowel; unshaped, the mark is drawn inside the vowel and disappears
(``ที่`` reads as ``ที``). The fragments for exactly those marks are lifted and
reduced to the geometry of Sarabun's own ``.small`` mark glyphs. The
characters themselves are unchanged, so the text layer still holds the stored
Thai string.
"""

from __future__ import annotations

import os
import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph


THAI_FONT = "Sarabun"
THAI_BOLD_FONT = "Sarabun-Bold"

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
THAI_FONT_FILES = {
    THAI_FONT: os.path.join(FONT_DIR, "Sarabun-Regular.ttf"),
    THAI_BOLD_FONT: os.path.join(FONT_DIR, "Sarabun-Bold.ttf"),
}

# Thai block. A run continues across ordinary spaces so the spaces inside a
# Thai name use the Thai font's spacing.
THAI_RUN = re.compile(r"[฀-๿]+(?:[  ]+[฀-๿]+)*")
_HAS_THAI = re.compile(r"[฀-๿]")

# Tone marks and thanthakhat that sit above an upper vowel, or above the
# nikhahit of a following sara am. Unshaped, these collide with that mark.
_STACKED_MARK = re.compile(
    r"(?<=[ัิ-ื])[่-์]"
    r"|[่-์](?=ำ)"
)
# Sarabun's ".small" tone marks are about 0.9 of the default mark and start
# at 1007 units instead of 689 (Regular; Bold 1017 instead of 684). Scaling
# the default glyph by 0.9 and lifting it by 0.39 em lands on those values.
STACKED_MARK_SCALE = 0.9
STACKED_MARK_RISE = 0.39


def ensure_thai_fonts():
    """Register Sarabun Regular and Bold from the repository, or fail loudly.

    A missing font file must stop the render (and the deploy check) rather
    than let Thai text print as boxes again.
    """
    missing = [path for path in THAI_FONT_FILES.values() if not os.path.isfile(path)]
    if missing:
        raise RuntimeError(
            "Thai PDF font file missing: " + ", ".join(missing)
            + ". Sarabun Regular and Bold must ship in crm_app/fonts/."
        )
    for font_name, path in THAI_FONT_FILES.items():
        try:
            pdfmetrics.getFont(font_name)
        except KeyError:
            pdfmetrics.registerFont(TTFont(font_name, path))


def check_thai_fonts(app_configs=None, **kwargs):
    """Django system check: the Thai font files ship with the code.

    start.sh runs ``manage.py migrate --check`` before Gunicorn starts, and
    that runs the system checks, so a deploy without the fonts stops there
    instead of printing boxes. (``collectstatic`` only runs staticfiles checks.)
    """
    from django.core.checks import Error

    errors = []
    for font_name, path in THAI_FONT_FILES.items():
        if not os.path.isfile(path):
            errors.append(Error(
                f"Thai PDF font file is missing: {path}",
                hint="Add Sarabun Regular and Bold (SIL OFL 1.1) to crm_app/fonts/.",
                id="crm_app.E101",
            ))
            continue
        try:
            face = TTFont(f"{font_name}-check", path).face
        except Exception as exc:  # pragma: no cover - a corrupt file
            errors.append(Error(f"Thai PDF font file cannot be read: {path} ({exc})", id="crm_app.E102"))
            continue
        if 0x0E01 not in face.charToGlyph:
            errors.append(Error(f"Thai PDF font file has no Thai glyphs: {path}", id="crm_app.E103"))
    return errors


def _thai_face_for(font_name):
    if font_name in THAI_FONT_FILES:
        return font_name
    return THAI_BOLD_FONT if "bold" in str(font_name).lower() else THAI_FONT


def _split_marks(frag, text):
    """Yield (text, extra attributes) pieces of one Thai run."""
    position = 0
    for match in _STACKED_MARK.finditer(text):
        if match.start() > position:
            yield text[position:match.start()], {}
        yield match.group(0), {
            "fontSize": frag.fontSize * STACKED_MARK_SCALE,
            "rise": getattr(frag, "rise", 0) + frag.fontSize * STACKED_MARK_RISE,
        }
        position = match.end()
    if position < len(text):
        yield text[position:], {}


def thai_fragments(frags):
    """Return paragraph fragments with every Thai run in the Thai font."""
    if not any(_HAS_THAI.search(getattr(frag, "text", "") or "") for frag in frags):
        return frags
    ensure_thai_fonts()
    result = []
    for frag in frags:
        text = getattr(frag, "text", "") or ""
        if (
            not _HAS_THAI.search(text)
            or getattr(frag, "cbDefn", None) is not None
            or frag.fontName in THAI_FONT_FILES
        ):
            result.append(frag)
            continue
        thai_face = _thai_face_for(frag.fontName)
        position = 0
        for match in THAI_RUN.finditer(text):
            if match.start() > position:
                result.append(frag.clone(text=text[position:match.start()]))
            for piece, extra in _split_marks(frag, match.group(0)):
                result.append(frag.clone(text=piece, fontName=thai_face, **extra))
            position = match.end()
        if position < len(text):
            result.append(frag.clone(text=text[position:]))
    return result


class ThaiAwareParagraph(Paragraph):
    """A Paragraph that prints Thai runs in Sarabun. Identical otherwise."""

    def _setup(self, text, style, bulletText, frags, cleaner):
        parse = frags is None
        super()._setup(text, style, bulletText, frags, cleaner)
        # Fragments handed in by split() were already converted.
        if parse:
            self.frags = thai_fragments(self.frags)
