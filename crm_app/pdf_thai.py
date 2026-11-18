"""Thai text in ReportLab PDFs: a per-run font fallback.

DejaVu Sans, the body font of every BMAsia PDF, has no Thai glyphs, so a Thai
legal name or address printed as empty boxes. This module keeps DejaVu as the
base font and switches only runs of Thai characters to Sarabun (SIL OFL 1.1),
with the bold DejaVu face mapped to Sarabun Bold. A paragraph without Thai
characters is not touched, so its PDF does not change.

The switch is done on the parsed paragraph fragments, after ReportLab has read
the markup, so it applies to every value however it was escaped or tagged, and
line wrapping measures each run with its own font.

ReportLab 4.0.7 does not shape text, and Sarabun relies on OpenType rules to
place stacked marks. Without them a tone mark is drawn inside an upper vowel
or inside the tall stem of ป ฝ ฟ and disappears (ที่ reads as ที, ฝ่าย as
ฝาย). Two corrections stand in for the font's rules, in exactly the contexts
where Sarabun applies them:

* A tone mark above an upper vowel or above the nikhahit of sara am is lifted
  and reduced to the geometry of Sarabun's own ``.small`` mark.
* The marks of a tall consonant, and the consonants and below vowels Sarabun
  changes before a below vowel or a mark (ญ ฐ ฎ ฏ ฬ), are drawn with the font's
  own variant glyph (``.narrow``, ``.less``, ``.short``, ``.small``). A variant
  font is the same Sarabun file with those characters pointed at the variant
  glyph, so the PDF still maps each glyph to the stored character.

The characters themselves are never changed or reordered, so the text layer
still holds the stored Thai string.
"""

from __future__ import annotations

import os
import re
import struct

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

BAHT = "\u0E3F"
# Thai block. A run continues across ordinary and no-break spaces so the
# spaces inside a Thai name use the Thai font's spacing.
THAI_RUN = re.compile("[\u0E00-\u0E7F]+(?:[ \u00A0]+[\u0E00-\u0E7F]+)*")
# Thai letters, marks and digits: everything in the block except the baht
# sign, which DejaVu draws. A run holding only baht signs stays in DejaVu, so a
# document whose only Thai-block character is "฿" does not change.
_THAI_LETTER = re.compile("[\u0E00-\u0E3E\u0E40-\u0E7F]")

# Zero-width characters a paste may leave inside a syllable. They are not part
# of a Thai run (DejaVu draws them, with no width) but do not separate a mark
# from its consonant when deciding how the mark is drawn.
_IGNORABLE = frozenset("\u200B\u200C\u200D")
_TALL = frozenset("\u0E1B\u0E1D\u0E1F")            # ป ฝ ฟ
_LO_CHULA = "\u0E2C"                               # ฬ
_DESCENDER_LESS = frozenset("\u0E0D\u0E10")        # ญ ฐ
_DESCENDER_SHORT = frozenset("\u0E0E\u0E0F")       # ฎ ฏ
_BELOW = frozenset("\u0E38\u0E39\u0E3A")
_UPPER_VOWEL = frozenset("\u0E31\u0E34\u0E35\u0E36\u0E37")
_TONE = frozenset("\u0E48\u0E49\u0E4A\u0E4B\u0E4C")  # four tone marks and thanthakhat
_ABOVE = _UPPER_VOWEL | _TONE | frozenset("\u0E47\u0E4D")
_SARA_AM = "\u0E33"

# Characters each variant font points at Sarabun's variant glyph: the glyph's
# name plus the suffix (uni0E48 -> uni0E48.narrow), or for the consonants the
# font's descriptive name for that variant.
VARIANT_CHARACTERS = {
    ".narrow": tuple(sorted(_ABOVE)),
    ".less": tuple(sorted(_DESCENDER_LESS)),
    ".short": tuple(sorted(_DESCENDER_SHORT | {_LO_CHULA})),
    ".small": tuple(sorted(_BELOW)),
}
_VARIANT_GLYPH_NAMES = {
    ("\u0E0D", ".less"): "yoYingthai.less",
    ("\u0E10", ".less"): "thoThanthai.less",
    ("\u0E0E", ".short"): "doChadathai.short",
    ("\u0E0F", ".short"): "toPatakthai.short",
    ("\u0E2C", ".short"): "loChulathai.short",
}

# Sarabun's ".small" tone marks are about 0.9 of the default mark and start
# at 1007 units instead of 689 (Regular; Bold 1017 instead of 684). Scaling
# the default glyph by 0.9 and lifting it by 0.39 em lands on those values.
# The tests check the result against the ".small" glyphs themselves.
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


def glyph_names(face):
    """Glyph names by glyph index, from the font's 'post' table (format 2).

    Standard Macintosh names (indexes below 258) are returned as None; the Thai
    glyphs and their variants all carry their own names.
    """
    data = face.get_table("post")
    if data[:4] != b"\x00\x02\x00\x00":
        return []
    count = struct.unpack(">H", data[32:34])[0]
    indexes = struct.unpack(f">{count}H", data[34:34 + 2 * count])
    position, custom = 34 + 2 * count, []
    while position < len(data):
        length = data[position]
        custom.append(data[position + 1:position + 1 + length].decode("latin-1"))
        position += 1 + length
    return [custom[i - 258] if 258 <= i < 258 + len(custom) else None for i in indexes]


def _variant_glyphs(face, suffix):
    """{character: variant glyph index}; raises if the font lacks one."""
    names = glyph_names(face)
    by_name = {name: index for index, name in enumerate(names) if name}
    glyphs = {}
    for character in VARIANT_CHARACTERS[suffix]:
        base = face.charToGlyph.get(ord(character))
        name = _VARIANT_GLYPH_NAMES.get((character, suffix))
        if name is None and base is not None and base < len(names) and names[base]:
            name = f"{names[base]}{suffix}"
        variant = by_name.get(name)
        if variant is None:
            raise RuntimeError(f"Thai PDF font has no {suffix} glyph for U+{ord(character):04X}")
        glyphs[ord(character)] = variant
    return glyphs


def _variant_font(font_name, suffix):
    """Name of the registered variant of a Thai font, registering it once."""
    if not suffix:
        return font_name
    name = f"{font_name}{suffix}"
    try:
        pdfmetrics.getFont(name)
        return name
    except KeyError:
        pass
    font = TTFont(name, THAI_FONT_FILES[font_name])
    face = font.face
    for code, glyph in _variant_glyphs(face, suffix).items():
        face.charToGlyph[code] = glyph
        face.charWidths[code] = face.hmetrics[glyph][0] * 1000.0 / face.unitsPerEm
    # A distinct face name keeps ReportLab from sharing the original face, and
    # names the embedded subset (e.g. Sarabun-Regular-narrow).
    face.name = type(face.name)(face.name + suffix.replace(".", "-").encode("ascii"))
    pdfmetrics.registerFont(font)
    return name


def _is_thai_font(font_name):
    return str(font_name).split(".")[0] in THAI_FONT_FILES


def check_thai_fonts(app_configs=None, **kwargs):
    """Django system check: the Thai font files ship with the code.

    start.sh runs ``manage.py migrate --check`` before Gunicorn starts, and
    that runs the system checks, so a deploy without the fonts stops there
    instead of printing boxes. (``collectstatic`` only runs staticfiles checks.)
    start.sh then adds its own "pending migrations" line; the error printed
    above it is the cause.
    """
    from django.core.checks import Error

    stopped = (" The deploy stops here; the 'pending migrations' message start.sh"
               " prints after this is a consequence of this check.")
    errors = []
    for font_name, path in THAI_FONT_FILES.items():
        if not os.path.isfile(path):
            errors.append(Error(
                f"Thai PDF font file is missing: {path}",
                hint="Add Sarabun Regular and Bold (SIL OFL 1.1) to crm_app/fonts/." + stopped,
                id="crm_app.E101",
            ))
            continue
        try:
            face = TTFont(f"{font_name}-check", path).face
        except Exception as exc:
            errors.append(Error(f"Thai PDF font file cannot be read: {path} ({exc})",
                                hint=stopped.strip(), id="crm_app.E102"))
            continue
        if 0x0E01 not in face.charToGlyph:
            errors.append(Error(f"Thai PDF font file has no Thai glyphs: {path}",
                                hint=stopped.strip(), id="crm_app.E103"))
            continue
        for suffix in VARIANT_CHARACTERS:
            try:
                _variant_glyphs(face, suffix)
            except RuntimeError as exc:
                errors.append(Error(f"{exc}: {path}", hint=stopped.strip(), id="crm_app.E104"))
                break
    return errors


def _thai_face_for(font_name):
    if _is_thai_font(font_name):
        return str(font_name).split(".")[0]
    return THAI_BOLD_FONT if "bold" in str(font_name).lower() else THAI_FONT


def glyph_plan(text):
    """How each character of ``text`` is drawn: a list of (variant suffix, lift).

    Mirrors what Sarabun's OpenType rules do (checked with HarfBuzz):

    * tone mark or thanthakhat right after an upper vowel, or right before
      sara am: lifted (the font uses its ".small" mark there);
    * the first mark above ป ฝ ฟ, directly or after a below vowel: ".narrow"
      (moved left of the stem); a tone above an upper vowel or before sara am
      on those consonants is ".narrow" and lifted;
    * ญ ฐ before a below vowel: ".less" (no descender); ฎ ฏ before a below
      vowel: ".short", and the vowel ".small"; ฬ before a mark: ".short".

    Zero-width characters inside a syllable are skipped when looking for the
    consonant and the neighbouring marks. A markup tag inside a syllable splits
    the text into separate fragments that are planned together, so it does not
    hide a mark either; a line break does end the syllable.
    """
    plan = [(None, False)] * len(text)

    def step(index, direction):
        index += direction
        while 0 <= index < len(text) and text[index] in _IGNORABLE:
            index += direction
        return index

    def char_at(index):
        return text[index] if 0 <= index < len(text) else ""

    for index, character in enumerate(text):
        previous, following = char_at(step(index, -1)), char_at(step(index, 1))
        if character in _ABOVE:
            # Walk back over marks to the consonant carrying them.
            base, first_above = step(index, -1), True
            while char_at(base) in _ABOVE or char_at(base) in _BELOW:
                first_above = first_above and char_at(base) not in _ABOVE
                base = step(base, -1)
            lift = character in _TONE and (previous in _UPPER_VOWEL or following == _SARA_AM)
            tall = char_at(base) in _TALL and (first_above or lift)
            plan[index] = (".narrow" if tall else None, lift)
        elif character in _DESCENDER_LESS and following in _BELOW:
            plan[index] = (".less", False)
        elif character in _DESCENDER_SHORT and following in _BELOW:
            plan[index] = (".short", False)
        elif character in _BELOW and previous in _DESCENDER_SHORT:
            plan[index] = (".small", False)
        elif character == _LO_CHULA and following in _ABOVE:
            plan[index] = (".short", False)
    return plan


def _pieces(text, plan):
    """Split a Thai run into (text, suffix, lift) pieces of one kind."""
    start = 0
    for index in range(1, len(text) + 1):
        if index == len(text) or plan[index] != plan[start]:
            yield text[start:index], plan[start][0], plan[start][1]
            start = index


def thai_fragments(frags):
    """Return paragraph fragments with every Thai run in the Thai font."""
    if not any(_THAI_LETTER.search(getattr(frag, "text", "") or "") for frag in frags):
        return frags
    ensure_thai_fonts()
    # Plan the whole paragraph at once, so a tag between a consonant and its
    # mark does not change how the mark is drawn. Fragments that are not text
    # (images, line breaks) end a syllable.
    texts = [
        (getattr(frag, "text", "") or "") if getattr(frag, "cbDefn", None) is None
        and not getattr(frag, "lineBreak", False) else "\n"
        for frag in frags
    ]
    plan = glyph_plan("".join(texts))
    result, offset = [], 0
    for frag, text in zip(frags, texts):
        start, offset = offset, offset + len(text)
        if (
            not _THAI_LETTER.search(text)
            or getattr(frag, "cbDefn", None) is not None
            or _is_thai_font(frag.fontName)
        ):
            result.append(frag)
            continue
        thai_face = _thai_face_for(frag.fontName)
        position = 0
        for match in THAI_RUN.finditer(text):
            if not _THAI_LETTER.search(match.group(0)):
                continue  # only baht signs: DejaVu draws them
            if match.start() > position:
                result.append(frag.clone(text=text[position:match.start()]))
            run_plan = plan[start + match.start():start + match.end()]
            for piece, suffix, lift in _pieces(match.group(0), run_plan):
                extra = {}
                if lift:
                    extra = {
                        "fontSize": frag.fontSize * STACKED_MARK_SCALE,
                        "rise": getattr(frag, "rise", 0) + frag.fontSize * STACKED_MARK_RISE,
                    }
                result.append(frag.clone(text=piece, fontName=_variant_font(thai_face, suffix), **extra))
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
