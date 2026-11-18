"""Where Thai marks are actually drawn, measured from the glyph outlines.

ReportLab 4.0.7 does not shape text, so crm_app/pdf_thai.py corrects how
stacked Thai marks are drawn. These tests do not compare against the module's
own numbers. They lay out a paragraph's fragments the way ReportLab draws them
(pen advance per character, size, rise), take every outline point of each
glyph from the embedded Sarabun file, and assert outcomes:

* a mark that sits over an upper vowel or a sara am clears that mark's ink,
  and lands where Sarabun's own ".small" mark sits;
* a mark on ป ฝ ฟ is drawn clear of the consonant's tall stem;
* a below vowel under ญ ฐ ฎ ฏ clears the consonant;
* nothing rises above the baseline of the line above at the documents'
  line spacing.

The font files are the ones in crm_app/fonts/. Invented words and names only.
"""
import os
import shutil
import struct
from xml.sax.saxutils import escape

import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph

from crm_app import pdf_thai
from crm_app.commercial_pdf import BODY_FONT, BOLD_FONT, document_styles
from crm_app.pdf_thai import ThaiAwareParagraph, check_thai_fonts

SIZES = (7.6, 9.2, 11)
# Clearance between two marks, and tolerance against Sarabun's own glyphs.
MARGIN_EM = 0.03
# Leading / size of the styles Thai text is printed in (body, table cell,
# small print, payment terms).
LEADING_RATIOS = (13 / 9.2, 11.7 / 8.4, 10.5 / 7.6, 11.5 / 8.2)


# --- reading glyph outlines from the font file ------------------------------

def _glyph_names(face):
    """Glyph names from the 'post' table (format 2), read independently here."""
    data = face.get_table('post')
    assert data[:4] == b'\x00\x02\x00\x00'
    count = struct.unpack('>H', data[32:34])[0]
    indexes = struct.unpack(f'>{count}H', data[34:34 + 2 * count])
    position, names = 34 + 2 * count, []
    while position < len(data):
        names.append(data[position + 1:position + 1 + data[position]].decode('latin-1'))
        position += 1 + data[position]
    return [names[i - 258] if i >= 258 else None for i in indexes]


def _outline(face, glyph):
    """Every outline point of a glyph, in font units (composites resolved)."""
    table = face.get_table('glyf')
    start, end = face.glyphPos[glyph], face.glyphPos[glyph + 1]
    if start == end:
        return []
    data = table[start:end]
    contours = struct.unpack('>h', data[:2])[0]
    if contours < 0:
        points, position = [], 10
        while True:
            flags, component = struct.unpack('>HH', data[position:position + 4])
            position += 4
            if flags & 0x0001:
                dx, dy = struct.unpack('>hh', data[position:position + 4])
                position += 4
            else:
                dx, dy = struct.unpack('>bb', data[position:position + 2])
                position += 2
            assert not flags & 0x00C8, 'scaled composite components are not expected'
            points += [(x + dx, y + dy) for x, y in _outline(face, component)]
            if not flags & 0x0020:
                return points
    ends = struct.unpack(f'>{contours}H', data[10:10 + 2 * contours])
    count = ends[-1] + 1 if contours else 0
    position = 10 + 2 * contours
    position += 2 + struct.unpack('>H', data[position:position + 2])[0]
    flags = []
    while len(flags) < count:
        flag = data[position]
        position += 1
        flags.append(flag)
        if flag & 8:
            flags.extend([flag] * data[position])
            position += 1
    coordinates = []
    for short, same in ((2, 16), (4, 32)):
        value, values = 0, []
        for flag in flags:
            if flag & short:
                delta = data[position]
                position += 1
                value += delta if flag & same else -delta
            elif not flag & same:
                value += struct.unpack('>h', data[position:position + 2])[0]
                position += 2
            values.append(value)
        coordinates.append(values)
    return list(zip(*coordinates))


def _ink(paragraph):
    """[(character, points in pt)] for a one-line paragraph, as drawn."""
    pen, drawn = 0.0, []
    for frag in paragraph.frags:
        font = pdfmetrics.getFont(frag.fontName)
        scale = frag.fontSize / font.face.unitsPerEm
        rise = getattr(frag, 'rise', 0) or 0
        for character in frag.text:
            glyph = font.face.charToGlyph.get(ord(character), 0)
            points = [(pen + x * scale, rise + y * scale) for x, y in _outline(font.face, glyph)]
            drawn.append((character, points))
            pen += font.stringWidth(character, frag.fontSize)
    return drawn


def _paragraph(text, size, bold=False):
    style = document_styles()['body_bold' if bold else 'body']
    style.fontSize, style.leading = size, size * LEADING_RATIOS[0]
    return ThaiAwareParagraph(escape(text), style)


def _glyph_points(font_name, glyph_name):
    face = pdfmetrics.getFont(font_name).face
    return _outline(face, _glyph_names(face).index(glyph_name))


def _cases():
    for size in SIZES:
        for bold in (False, True):
            yield size, bold


def _at(drawn, word, index):
    character, points = drawn[index]
    assert character == word[index]
    return points


def _top(points):
    return max(y for _, y in points)


def _bottom(points):
    return min(y for _, y in points)


# --- tone marks over an upper vowel or sara am -----------------------------

# (word, index of the mark, index of the mark or vowel beneath it)
STACKED = [
    ('ที่', 2, 1),       # mai ek over sara ii
    ('นี้', 2, 1),       # mai tho over sara ii
    ('ชื่อ', 2, 1),      # mai ek over sara uee
    ('ทั้ง', 2, 1),      # mai tho over mai han-akat
    ('หนึ่ง', 3, 2),     # mai ek over sara ue
    ('กิ๊ฟ', 2, 1),      # mai tri over sara i
    ('ศักดิ์', 5, 4),    # thanthakhat over sara i
    ('สิทธิ์', 5, 4),    # thanthakhat over sara i
]
SARA_AM = [('น้ำ', 1, 2), ('ค่ำ', 1, 2), ('ซ้ำ', 1, 2)]  # tone above the nikhahit of sara am


@pytest.mark.parametrize('word, mark, beneath', STACKED + SARA_AM)
def test_stacked_mark_clears_the_mark_beneath_it(word, mark, beneath):
    for size, bold in _cases():
        drawn = _ink(_paragraph(word, size, bold))
        assert ''.join(c for c, _ in drawn) == word
        gap = _bottom(_at(drawn, word, mark)) - _top(_at(drawn, word, beneath))
        assert gap >= MARGIN_EM * size, (word, size, bold, gap)


@pytest.mark.parametrize('word, mark, beneath', STACKED + SARA_AM)
def test_stacked_mark_sits_where_sarabuns_own_small_mark_sits(word, mark, beneath):
    for size, bold in _cases():
        paragraph = _paragraph(word, size, bold)
        drawn = _ink(paragraph)
        points = _at(drawn, word, mark)
        face_name = pdf_thai.THAI_BOLD_FONT if bold else pdf_thai.THAI_FONT
        small = _glyph_points(face_name, f'uni{ord(word[mark]):04X}.small')
        scale = size / 1000
        tolerance = MARGIN_EM * size
        assert abs(_bottom(points) - _bottom(small) * scale) <= tolerance, (word, size, bold)
        assert abs(_top(points) - _top(small) * scale) <= tolerance, (word, size, bold)


@pytest.mark.parametrize('word', ['ที่', 'ทั้ง', 'ศักดิ์', 'น้ำ', 'ปี่', 'ฟื้น', 'ปั้น'])
def test_lifted_marks_stay_below_the_line_above(word):
    for size, bold in _cases():
        drawn = _ink(_paragraph(word, size, bold))
        highest = max(_top(points) for _, points in drawn if points)
        for ratio in LEADING_RATIOS:
            assert highest <= size * ratio, (word, size, bold, ratio, highest)


def test_a_tone_on_a_bare_consonant_is_not_moved():
    # Sarabun draws these with its default marks; so must the PDF.
    for size, bold in _cases():
        for word in ('ไม่', 'ได้', 'ก่อน', 'แล้ว'):
            for frag in _paragraph(word, size, bold).frags:
                assert not getattr(frag, 'rise', 0)
                assert frag.fontSize == size
                assert frag.fontName in (pdf_thai.THAI_FONT, pdf_thai.THAI_BOLD_FONT)


# --- tall consonants ป ฝ ฟ --------------------------------------------------

def _stem(points):
    """The tall stem: the part of the consonant above its x-height, as a box."""
    tall = [(x, y) for x, y in points if y > 0.8 * _top(points)]
    stem_left = min(x for x, _ in tall)
    return stem_left, max(x for x, _ in points), _top(points)


# (word, index of the consonant, indexes of the marks above it)
TALL = [
    ('ฝ่าย', 0, (1,)), ('ป่า', 0, (1,)), ('ปู่', 0, (2,)), ('ปุ่ม', 0, (2,)),
    ('ฟ้า', 0, (1,)), ('ป๊า', 0, (1,)), ('ป๋า', 0, (1,)), ('ฟ์', 0, (1,)),
    ('เป็น', 1, (2,)), ('ปิด', 0, (1,)), ('ฝึก', 0, (1,)), ('ปืน', 0, (1,)), ('ฟัน', 0, (1,)),
    ('ปี่', 0, (1, 2)), ('ฟื้น', 0, (1, 2)), ('ปั้น', 0, (1, 2)),
]


@pytest.mark.parametrize('word, consonant, marks', TALL)
def test_marks_on_a_tall_consonant_stay_clear_of_its_stem(word, consonant, marks):
    for size, bold in _cases():
        drawn = _ink(_paragraph(word, size, bold))
        assert ''.join(c for c, _ in drawn) == word
        left, right, top = _stem(_at(drawn, word, consonant))
        for mark in marks:
            points = _at(drawn, word, mark)
            if _bottom(points) >= top + MARGIN_EM * size:
                continue  # drawn above the stem
            # Beside the stem: the part of the mark lower than the stem's top
            # must not reach over the stem's columns (the curl of mai han-akat
            # or the tail of mai tho may pass above the stem's top).
            low = [x for x, y in points if y < top]
            overlap = max(0.0, min(max(low), right) - max(min(low), left))
            mark_width = max(x for x, _ in points) - min(x for x, _ in points)
            assert overlap <= 0.15 * mark_width, (word, size, bold, mark, overlap)


def test_a_tone_above_a_vowel_on_a_tall_consonant_clears_the_vowel():
    for size, bold in _cases():
        for word in ('ปี่', 'ฟื้น', 'ปั้น', 'ฝั่ง'):
            drawn = _ink(_paragraph(word, size, bold))
            gap = _bottom(_at(drawn, word, 2)) - _top(_at(drawn, word, 1))
            assert gap >= MARGIN_EM * size, (word, size, bold, gap)


# --- consonants with a descender before a below vowel -----------------------

@pytest.mark.parametrize('word, consonant, vowel', [
    ('กตัญญู', 4, 5), ('ญุ', 0, 1), ('ฐุ', 0, 1), ('ฐู', 0, 1), ('ฎุ', 0, 1), ('ฏู', 0, 1),
])
def test_below_vowel_clears_the_consonant_above_it(word, consonant, vowel):
    for size, bold in _cases():
        drawn = _ink(_paragraph(word, size, bold))
        gap = _bottom(_at(drawn, word, consonant)) - _top(_at(drawn, word, vowel))
        assert gap >= MARGIN_EM * size, (word, size, bold, gap)


# --- run boundaries ----------------------------------------------------------

def test_no_break_space_stays_inside_a_thai_run():
    paragraph = _paragraph('บริษัท ทดสอบ จำกัด', 9.2)
    assert [frag.text for frag in paragraph.frags] == ['บริษัท ทดสอบ จำกัด']
    assert paragraph.frags[0].fontName == pdf_thai.THAI_FONT


def test_lift_adds_to_an_existing_rise():
    style = document_styles()['body']
    paragraph = ThaiAwareParagraph('x<super>ที่</super>', style)
    drawn = _ink(paragraph)
    word = 'xที่'
    gap = _bottom(_at(drawn, word, 3)) - _top(_at(drawn, word, 2))
    assert gap >= MARGIN_EM * style.fontSize
    assert _bottom(_at(drawn, word, 1)) > 0  # the superscript itself is raised


@pytest.mark.parametrize('markup, word', [
    ('ที​่', 'ที​่'),          # zero-width space pasted inside the syllable
    ('ที<b>่</b>', 'ที่'),                # a tag inside the syllable
    ('ป​่า', 'ป​่า'),
])
def test_zero_width_space_or_tag_inside_a_syllable_does_not_hide_the_mark(markup, word):
    style = document_styles()['body']
    paragraph = ThaiAwareParagraph(markup, style)
    assert paragraph.getPlainText() == word
    drawn = _ink(paragraph)
    base = 0
    mark = len(word) - (2 if word.endswith('า') else 1)
    if word.startswith('ที'):
        gap = _bottom(_at(drawn, word, mark)) - _top(_at(drawn, word, 1))
        assert gap >= MARGIN_EM * style.fontSize
    else:
        left, right, top = _stem(_at(drawn, word, base))
        assert all(not (left < x < right and y < top) for x, y in _at(drawn, word, mark))


def test_a_lone_baht_sign_stays_in_the_document_font():
    style = document_styles()['body']
    for markup in ('฿1,000', 'Fee ฿ 1,000 per year', '฿'):
        plain, thai = Paragraph(markup, style), ThaiAwareParagraph(markup, style)
        assert [(f.text, f.fontName) for f in thai.frags] == [(f.text, f.fontName) for f in plain.frags]
    assert 0x0E3F in pdfmetrics.getFont(BODY_FONT).face.charToGlyph
    assert 0x0E3F in pdfmetrics.getFont(BOLD_FONT).face.charToGlyph
    # Inside a Thai phrase it belongs to the Thai run.
    phrase = ThaiAwareParagraph('ค่าบริการ ฿1,000', style)
    assert phrase.frags[0].text == 'ค่าบริการ ฿' and phrase.frags[0].fontName == pdf_thai.THAI_FONT


# --- environment and startup checks -----------------------------------------

def test_document_font_is_real_dejavu_without_thai():
    # On a machine without DejaVu, ReportLab can register another font (one
    # that has Thai) under the DejaVu name and hide the original boxes. The
    # Thai tests must not pass for that reason.
    for name in (BODY_FONT, BOLD_FONT):
        face = pdfmetrics.getFont(name).face
        assert bytes(face.name).startswith(b'DejaVuSans'), face.name
        assert 0x0E01 not in face.charToGlyph


def test_check_reports_an_unreadable_font_file(monkeypatch, tmp_path):
    broken = tmp_path / 'Sarabun-Regular.ttf'
    broken.write_bytes(open(pdf_thai.THAI_FONT_FILES[pdf_thai.THAI_FONT], 'rb').read()[:2000])
    monkeypatch.setattr(pdf_thai, 'THAI_FONT_FILES', {
        pdf_thai.THAI_FONT: str(broken),
        pdf_thai.THAI_BOLD_FONT: pdf_thai.THAI_FONT_FILES[pdf_thai.THAI_BOLD_FONT],
    })
    assert [error.id for error in check_thai_fonts()] == ['crm_app.E102']


def test_check_reports_a_font_without_thai(monkeypatch, tmp_path):
    import reportlab
    latin_only = tmp_path / 'Sarabun-Bold.ttf'
    shutil.copy(os.path.join(os.path.dirname(reportlab.__file__), 'fonts', 'Vera.ttf'), latin_only)
    monkeypatch.setattr(pdf_thai, 'THAI_FONT_FILES', {
        pdf_thai.THAI_FONT: pdf_thai.THAI_FONT_FILES[pdf_thai.THAI_FONT],
        pdf_thai.THAI_BOLD_FONT: str(latin_only),
    })
    assert [error.id for error in check_thai_fonts()] == ['crm_app.E103']


def test_check_reports_a_font_without_the_variant_glyphs(monkeypatch):
    monkeypatch.setitem(pdf_thai._VARIANT_GLYPH_NAMES, ('ญ', '.less'), 'noSuchGlyph.less')
    assert [error.id for error in check_thai_fonts()] == ['crm_app.E104', 'crm_app.E104']


def test_missing_font_message_names_the_cause_for_the_deploy_log(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_thai, 'THAI_FONT_FILES', {
        pdf_thai.THAI_FONT: str(tmp_path / 'Sarabun-Regular.ttf'),
        pdf_thai.THAI_BOLD_FONT: pdf_thai.THAI_FONT_FILES[pdf_thai.THAI_BOLD_FONT],
    })
    [error] = check_thai_fonts()
    assert error.id == 'crm_app.E101'
    assert 'missing' in error.msg and 'pending migrations' in error.hint
