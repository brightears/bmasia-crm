"""When a quote's pricing block moves to the next page and when it splits.

The block is the "Services and pricing" heading, the billing line, the item
table's column header, every data row and the totals. A block that fits the
space left on the page stays there. A block taller than a page splits by row
as before. A block that does not fit the space left but does fit a page:

* splits by row with the header repeated, exactly as before the block was
  measured, when at least 3 data rows stay on the current page and at least
  2 carry over;
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


def _quote(row_count, words):
    quote = sample_quote()
    quote.company = _example_company()
    items = [_item(index, words) for index in range(1, row_count + 1)]
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


def _layout(row_count, words, *, layout_before_measuring=False):
    seen = {}
    with _captured_block(seen, layout_before_measuring):
        pdf = quote_pdf.build_quote_pdf_v2(
            _quote(row_count, words),
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
    return Layout(page, (page,), (page,) * len(old.rows), page)


@pytest.mark.parametrize("size", sorted(ROW_SIZES))
@pytest.mark.parametrize("row_count", ROW_COUNTS)
def test_pricing_block_moves_whole_only_when_a_split_would_leave_a_short_fragment(row_count, size):
    words = ROW_SIZES[size]
    old, fits_a_page = _layout(row_count, words, layout_before_measuring=True)
    new, _ = _layout(row_count, words)

    # The old layout already kept the totals with the last row; so does the new one.
    assert old.totals == old.rows[-1]
    assert new.totals == new.rows[-1]
    # The heading always starts on the page of the first row and its header.
    assert new.heading == new.rows[0] == new.headers[0]
    # A header is printed on every page the table occupies, and only there.
    assert sorted(set(new.headers)) == sorted(set(new.rows))
    assert new == _expected(old, fits_a_page)


# (rows, words, pages of rows in the old layout, expected outcome). The word
# counts put the old split on each side of both thresholds.
THRESHOLD_CASES = [
    pytest.param(3, 48, (0, 0, 1), "move", id="3-rows-2-stay-1-carries"),
    pytest.param(4, 18, (0, 0, 0, 1), "move", id="4-rows-3-stay-1-carries"),
    pytest.param(4, 48, (0, 0, 1, 1), "move", id="4-rows-2-stay-2-carry"),
    pytest.param(5, 18, (0, 0, 0, 0, 1), "move", id="5-rows-4-stay-1-carries"),
    pytest.param(5, 36, (0, 0, 0, 1, 1), "split", id="5-rows-3-stay-2-carry"),
    pytest.param(6, 12, (0, 0, 0, 0, 0, 1), "move", id="6-rows-5-stay-1-carries"),
    pytest.param(6, 24, (0, 0, 0, 0, 1, 1), "split", id="6-rows-4-stay-2-carry"),
    pytest.param(7, 18, (0, 0, 0, 0, 1, 1, 1), "split", id="7-rows-4-stay-3-carry"),
    pytest.param(12, 0, (0,) * 9 + (1,) * 3, "split", id="12-short-rows-9-stay-3-carry"),
]


@pytest.mark.parametrize("row_count, words, old_rows, outcome", THRESHOLD_CASES)
def test_pricing_block_split_thresholds(row_count, words, old_rows, outcome):
    old, fits_a_page = _layout(row_count, words, layout_before_measuring=True)
    assert fits_a_page
    assert old.rows == old_rows, "fixture no longer lands on this side of the threshold"

    new, _ = _layout(row_count, words)

    if outcome == "split":
        assert new == old
        assert new.headers == (0, 1)
        assert new.totals == 1
    else:
        assert new == Layout(1, (1,), (1,) * row_count, 1)


def test_split_thresholds_are_named_constants():
    assert commercial_pdf.MIN_ROWS_BEFORE_SPLIT == ROWS_THAT_MUST_STAY
    assert commercial_pdf.MIN_ROWS_AFTER_SPLIT == ROWS_THAT_MUST_CARRY
