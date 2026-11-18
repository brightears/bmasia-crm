"""When a quote's pricing block moves to the next page and when it splits.

The block is the "Services and pricing" heading, the billing line, the item
table's column header, every data row and the totals. A block that fits the
space left on the page stays there. A block taller than a page splits by row
as before. A block that does not fit the space left but does fit a page:

* splits by row with the header repeated, exactly as before the block was
  measured, when at least 3 data rows stay on the current page and at least
  2 carry over;
* splits one row earlier when only 1 row would carry over and at least 3
  still stay after giving one up (so 4 + 1 becomes 3 + 2), never leaving a
  group heading as the last line of a page;
* otherwise moves to the next page as one unit.

Expected layouts come from the old layout (heading reservation plus a plain
row split) with that rule applied, so every page assertion is independent of
the measuring code. Synthetic fixtures only; assertions run on the rendered
PDF's per-page text.
"""

from contextlib import contextmanager
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from typing import NamedTuple
from unittest import mock

import pytest
from pypdf import PdfReader

import crm_app.quote_pdf_v2 as quote_pdf
from crm_app import commercial_pdf
from crm_app.commercial_pdf import entity_profile_for, section_start
from scripts.preview_commercial_pdf_v2 import (
    ROOT,
    RelatedList,
    format_address_multiline,
    format_duration,
    sample_quote,
)


LOGO = ROOT / "crm_app/static/crm_app/images/bmasia_logo.png"
ENTITY = entity_profile_for("BMAsia (Thailand) Co., Ltd.")
HEADER_ROW = "SERVICE ZONE / DESCRIPTION QTY UNIT PRICE AMOUNT"
USABLE_HEIGHT = (
    commercial_pdf.PAGE_HEIGHT
    - commercial_pdf.CONTINUATION_PAGE_TOP
    - commercial_pdf.PAGE_BOTTOM
)

# The rule under test, stated independently of the implementation.
ROWS_THAT_MUST_STAY = 3
ROWS_THAT_MUST_CARRY = 2

ROW_COUNTS = list(range(1, 15)) + [20, 28]
ROW_SIZES = {"short": 0, "medium": 18, "tall": 36}
TALL_ROW_WORDS = 40


class Layout(NamedTuple):
    heading: int
    headers: tuple  # page index of each printed column header
    rows: tuple  # page index of each data row, in order
    totals: int


def _example_company():
    return SimpleNamespace(
        name="Example Hotel",
        legal_entity_name="Example Hotel Co., Ltd.",
        branch="Branch 00001",
        tax_id="0100000000001",
        address_line1="1 Example Road",
        address_line2="Example District",
        city="Bangkok",
        state="",
        postal_code="10110",
        country="Thailand",
        billing_entity="BMAsia (Thailand) Co., Ltd.",
    )


def _item(index, words):
    description = (
        f"R{index:02d}B Example area {index} "
        + " ".join(f"d{word}" for word in range(words))
        + f" R{index:02d}E"
    )
    return SimpleNamespace(
        product_service="soundtrack",
        description=description,
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        unit_value=None,
        line_total=Decimal("1000.00"),
    )


def _one_time_item(index):
    return SimpleNamespace(
        product_service="Soundtrack Player",
        description=f"R{index:02d}B Playback hardware R{index:02d}E",
        quantity=Decimal("1"),
        unit_price=Decimal("0"),
        unit_value=Decimal("250"),
        line_total=Decimal("0"),
    )


def _quote(row_count, words, one_time=0, tall=()):
    quote = sample_quote()
    quote.company = _example_company()
    items = [
        _item(index, TALL_ROW_WORDS if index in tall else words)
        for index in range(1, row_count + 1)
    ]
    # The last ``one_time`` data rows become items included at no charge,
    # printed under their own group heading.
    for index in range(row_count - one_time + 1, row_count + 1):
        items[index - 1] = _one_time_item(index)
    quote.line_items = RelatedList(items)
    quote.subtotal = sum((item.line_total for item in items), Decimal("0"))
    quote.total_value = quote.subtotal
    quote.contract_duration_months = 24
    return quote


def _old_section_block(number, title, body, styles, minimum_following_height=72):
    """The layout before the block was measured: heading reservation only."""
    return [*section_start(number, title, styles, minimum_following_height), *body]


@contextmanager
def _captured_block(seen, layout_before_measuring=False):
    real = quote_pdf.section_block

    def spy(number, title, body, styles, minimum_following_height=72):
        builder = _old_section_block if layout_before_measuring else real
        flowables = builder(number, title, body, styles, minimum_following_height)
        seen["height"] = commercial_pdf._measured_block_height(
            flowables[1:], commercial_pdf.CONTENT_WIDTH,
        )
        return flowables

    with mock.patch.object(quote_pdf, "section_block", spy):
        yield


def _layout(row_count, words, *, layout_before_measuring=False, one_time=0, tall=()):
    seen = {}
    with _captured_block(seen, layout_before_measuring):
        pdf = quote_pdf.build_quote_pdf_v2(
            _quote(row_count, words, one_time, tall),
            ENTITY,
            str(LOGO),
            format_address_multiline,
            format_duration,
            preview=True,
        )
    texts = [
        " ".join((page.extract_text() or "").split())
        for page in PdfReader(BytesIO(pdf)).pages
    ]

    def pages(token):
        return [index for index, text in enumerate(texts) if token in text]

    rows = []
    for index in range(1, row_count + 1):
        begin, end = pages(f"R{index:02d}B"), pages(f"R{index:02d}E")
        assert len(begin) == 1 and begin == end, (index, begin, end)
        rows.append(begin[0])
    (heading,) = pages("Services and pricing")
    (totals,) = pages("Total contract value")
    headers = tuple(
        index for index, text in enumerate(texts) for _ in range(text.count(HEADER_ROW))
    )
    fits_a_page = seen["height"] is not None and seen["height"] <= USABLE_HEIGHT
    return Layout(heading, headers, tuple(rows), totals), fits_a_page


def _expected(old, fits_a_page):
    """Apply the rule to the old layout."""
    split = len(set(old.headers)) > 1
    if not split or not fits_a_page:
        return old
    stayed = sum(1 for page in old.rows if page == old.heading)
    carried = len(old.rows) - stayed
    if stayed >= ROWS_THAT_MUST_STAY and carried >= ROWS_THAT_MUST_CARRY:
        return old
    page = old.heading + 1
    give_up = ROWS_THAT_MUST_CARRY - carried
    if stayed - give_up >= ROWS_THAT_MUST_STAY:
        # Split earlier: the last rows that stayed move over as well.
        keep = stayed - give_up
        rows = (old.heading,) * keep + (page,) * (len(old.rows) - keep)
        return Layout(old.heading, (old.heading, page), rows, page)
    return Layout(page, (page,), (page,) * len(old.rows), page)


@pytest.mark.parametrize("size", sorted(ROW_SIZES) + ["tall-second-last"])
@pytest.mark.parametrize("row_count", ROW_COUNTS)
def test_pricing_block_moves_whole_only_when_a_split_would_leave_a_short_fragment(row_count, size):
    # "tall-second-last": short rows except the one an earlier split gives up.
    tall = (row_count - 1,) if size == "tall-second-last" else ()
    words = ROW_SIZES.get(size, 0)
    old, fits_a_page = _layout(row_count, words, layout_before_measuring=True, tall=tall)
    new, _ = _layout(row_count, words, tall=tall)

    # The old layout already kept the totals with the last row; so does the new one.
    assert old.totals == old.rows[-1]
    assert new.totals == new.rows[-1]
    # The heading always starts on the page of the first row and its header.
    assert new.heading == new.rows[0] == new.headers[0]
    # A header is printed on every page the table occupies, and only there.
    assert sorted(set(new.headers)) == sorted(set(new.rows))
    assert new == _expected(old, fits_a_page)


# (rows, words, rows made tall, pages of rows in the old layout, outcome).
# The word counts put the old split on each side of every condition.
THRESHOLD_CASES = [
    pytest.param(3, 48, (), (0, 0, 1), "move", id="2+1-moves"),
    pytest.param(4, 18, (), (0, 0, 0, 1), "move", id="3+1-moves"),
    pytest.param(4, 48, (), (0, 0, 1, 1), "move", id="2+2-moves"),
    pytest.param(5, 18, (), (0, 0, 0, 0, 1), "earlier", id="4+1-becomes-3+2"),
    pytest.param(5, 0, (4,), (0, 0, 0, 0, 1), "earlier", id="4+1-tall-row-given-up-becomes-3+2"),
    pytest.param(5, 36, (), (0, 0, 0, 1, 1), "split", id="3+2-splits"),
    pytest.param(6, 12, (), (0, 0, 0, 0, 0, 1), "earlier", id="5+1-becomes-4+2"),
    pytest.param(6, 24, (), (0, 0, 0, 0, 1, 1), "split", id="4+2-splits"),
    pytest.param(7, 18, (), (0, 0, 0, 0, 1, 1, 1), "split", id="4+3-splits"),
    pytest.param(8, 0, (7,), (0,) * 7 + (1,), "earlier", id="7+1-tall-row-given-up-becomes-6+2"),
    pytest.param(9, 0, (), (0,) * 8 + (1,), "earlier", id="8+1-becomes-7+2"),
    pytest.param(10, 0, (), (0,) * 9 + (1,), "earlier", id="9+1-becomes-8+2"),
    pytest.param(10, 3, (), (0,) * 8 + (1,) * 2, "split", id="8+2-splits"),
    pytest.param(12, 0, (), (0,) * 9 + (1,) * 3, "split", id="9+3-splits"),
]


@pytest.mark.parametrize("row_count, words, tall, old_rows, outcome", THRESHOLD_CASES)
def test_pricing_block_split_thresholds(row_count, words, tall, old_rows, outcome):
    old, fits_a_page = _layout(row_count, words, layout_before_measuring=True, tall=tall)
    assert fits_a_page
    assert old.rows == old_rows, "fixture no longer lands on this side of the threshold"

    new, _ = _layout(row_count, words, tall=tall)

    if outcome == "split":
        assert new == old
    elif outcome == "earlier":
        stayed = old_rows.count(0) - 1
        assert new == Layout(0, (0, 1), (0,) * stayed + (1,) * (row_count - stayed), 1)
    else:
        assert new == Layout(1, (1,), (1,) * row_count, 1)


def _page_texts(row_count, words, **options):
    pdf = quote_pdf.build_quote_pdf_v2(
        _quote(row_count, words, **options),
        ENTITY,
        str(LOGO),
        format_address_multiline,
        format_duration,
        preview=True,
    )
    return [
        " ".join((page.extract_text() or "").split())
        for page in PdfReader(BytesIO(pdf)).pages
    ]


@pytest.mark.parametrize("row_count, words, tall", [(9, 0, ()), (5, 0, (4,)), (8, 0, (7,))])
def test_space_left_by_an_earlier_split_is_not_used_by_anything_else(row_count, words, tall):
    texts = _page_texts(row_count, words, tall=tall)
    keep = row_count - 2

    # Page 1 ends with the last row that stays: no repeated header, carried
    # row, totals or payment section is pulled back into the space it left.
    assert texts[0].count(HEADER_ROW) == 1
    assert f"R{keep:02d}E" in texts[0]
    for index in range(keep + 1, row_count + 1):
        assert f"R{index:02d}B" not in texts[0]
    assert "Total contract value" not in texts[0]
    assert "Payment and terms" not in texts[0]
    # Page 2 starts with the repeated header and carries the rest, as any
    # split does; the payment section follows on the same page.
    assert texts[1].count(HEADER_ROW) == 1
    assert "Total contract value" in texts[1]
    assert "Payment and terms" in texts[1]
    assert len(texts) == 2


def test_group_heading_is_not_counted_as_a_data_row():
    # Four zone rows stay; only the included item carries over, under its
    # group heading. That is one data row, so one zone row moves with it.
    old, fits_a_page = _layout(5, 0, layout_before_measuring=True, one_time=1)
    assert fits_a_page
    assert old.rows == (0, 0, 0, 0, 1)

    new, _ = _layout(5, 0, one_time=1)

    assert new == Layout(0, (0, 1), (0, 0, 0, 1, 1), 1)


def test_earlier_split_never_leaves_a_group_heading_last_on_the_page():
    # Three zone rows, then the "Included at no charge" heading with two
    # included items. Naturally the heading and the first included item
    # stay and only the second carries over. Giving up the first included
    # item would leave the heading alone at the foot of the page, so the
    # split moves up to just before the heading.
    old, fits_a_page = _layout(5, 0, layout_before_measuring=True, one_time=2)
    assert fits_a_page
    assert old.rows == (0, 0, 0, 0, 1)

    new, _ = _layout(5, 0, one_time=2)
    texts = _page_texts(5, 0, one_time=2)

    assert new == Layout(0, (0, 1), (0, 0, 0, 1, 1), 1)
    # The group heading prints in capitals; the totals label does not.
    assert "INCLUDED AT NO CHARGE" not in texts[0]
    assert "INCLUDED AT NO CHARGE" in texts[1]


def test_block_never_splits_where_the_heading_reservation_would_already_break():
    # Three small rows fit in less than the 125 pt heading reservation. The
    # old layout broke the page there, so the block moves whole even though
    # a 3 + 2 split would be possible.
    from reportlab.platypus import Paragraph, Spacer

    styles = commercial_pdf.document_styles()
    rows = [[f"ZROW{index}", "Example", "1", "1", "1"] for index in range(1, 6)]
    body = commercial_pdf.item_table(
        ["Service", "Zone", "Qty", "Unit", "Amount"],
        rows,
        [78, commercial_pdf.CONTENT_WIDTH - 324, 42, 92, 112],
        {2, 3, 4},
        styles,
        amount_columns={4},
    )
    table = body[0]
    table.wrap(commercial_pdf.CONTENT_WIDTH, USABLE_HEIGHT)
    heading = commercial_pdf.section_heading("01", "Block", styles).wrap(
        commercial_pdf.CONTENT_WIDTH, USABLE_HEIGHT,
    )[1]
    three_rows = heading + sum(table._rowHeights[:4])
    assert three_rows + 0.5 < 125
    block = commercial_pdf.section_block("01", "Block", body, styles, minimum_following_height=125)
    first_page = (
        commercial_pdf.PAGE_HEIGHT - commercial_pdf.FIRST_PAGE_TOP - commercial_pdf.PAGE_BOTTOM
    )
    pdf = commercial_pdf.build_document_pdf(
        [Spacer(1, first_page - three_rows - 0.5), *block, Paragraph("AFTERMARK", styles["body"])],
        document_title="Example", document_id="EX-0001", entity=ENTITY,
    )
    texts = [" ".join((page.extract_text() or "").split()) for page in PdfReader(BytesIO(pdf)).pages]

    assert "Block" not in texts[0] and "ZROW" not in texts[0]
    assert "Block" in texts[1]
    assert all(f"ZROW{index}" in texts[1] for index in range(1, 6))


def test_split_thresholds_are_named_constants():
    assert commercial_pdf.MIN_ROWS_BEFORE_SPLIT == ROWS_THAT_MUST_STAY
    assert commercial_pdf.MIN_ROWS_AFTER_SPLIT == ROWS_THAT_MUST_CARRY
