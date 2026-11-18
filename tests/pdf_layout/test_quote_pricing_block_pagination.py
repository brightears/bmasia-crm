"""Quote PDF "Services and pricing" block pagination.

When the whole block (heading, billing line, column header, rows, totals) fits
on one page it is kept together unless a split leaves enough rows on both
pages (see test_quote_pricing_block_split_rule.py); a taller block still
splits by row. Synthetic fixtures only; assertions run on the rendered PDF's
per-page text.
"""

from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from reportlab.platypus import CondPageBreak, Paragraph, Spacer

from crm_app.commercial_pdf import PAGE_HEIGHT, document_styles, entity_profile_for
from crm_app.quote_pdf_v2 import build_quote_pdf_v2
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


def _zone_item(token, zone, words):
    description = f"{token}-BEGIN {zone}: " + " ".join(
        f"detail{index}" for index in range(words)
    ) + f" {token}-END"
    return SimpleNamespace(
        product_service="soundtrack",
        description=description,
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        unit_value=None,
        line_total=Decimal("1000.00"),
    )


def _render(items):
    quote = sample_quote()
    quote.company = _example_company()
    quote.contact = None
    quote.line_items = RelatedList(items)
    quote.subtotal = sum((item.line_total for item in items), Decimal("0"))
    quote.total_value = quote.subtotal
    quote.contract_duration_months = 24
    pdf = build_quote_pdf_v2(
        quote,
        ENTITY,
        str(LOGO),
        format_address_multiline,
        format_duration,
        preview=True,
    )
    reader = PdfReader(BytesIO(pdf))
    return [" ".join((page.extract_text() or "").split()) for page in reader.pages]


def _pages_with(texts, token):
    return [index for index, text in enumerate(texts) if token in text]


def _assert_block_on_one_page(texts, tokens, expected_page):
    assert _pages_with(texts, "Services and pricing") == [expected_page]
    # The column header appears once: the table was not split.
    assert _pages_with(texts, HEADER_ROW) == [expected_page]
    assert "".join(texts).count(HEADER_ROW) == 1
    for token in tokens:
        assert _pages_with(texts, f"{token}-BEGIN") == [expected_page], token
        assert _pages_with(texts, f"{token}-END") == [expected_page], token
    assert _pages_with(texts, "Total contract value") == [expected_page]


def test_single_row_pricing_block_that_fits_stays_on_page_one():
    texts = _render([_zone_item("LOBBY", "Lobby", 12)])

    _assert_block_on_one_page(texts, ["LOBBY"], expected_page=0)


def test_three_short_rows_that_fit_the_remaining_space_stay_on_page_one():
    texts = _render([
        _zone_item("LOBBY", "Lobby", 6),
        _zone_item("POOLBAR", "Pool Bar", 6),
        _zone_item("RESTAURANT", "Restaurant", 6),
    ])

    _assert_block_on_one_page(texts, ["LOBBY", "POOLBAR", "RESTAURANT"], expected_page=0)


@pytest.mark.parametrize("words", [14, 24])
def test_three_tall_rows_move_to_the_next_page_together_instead_of_splitting(words):
    texts = _render([
        _zone_item("LOBBY", "Lobby", words),
        _zone_item("POOLBAR", "Pool Bar", words),
        _zone_item("RESTAURANT", "Restaurant", words),
    ])

    _assert_block_on_one_page(texts, ["LOBBY", "POOLBAR", "RESTAURANT"], expected_page=1)
    # Page one keeps the intro, metadata and identity cards.
    assert "PREPARED FOR" in texts[0]
    if words == 14:
        # Payment and terms still fits under the moved block. With taller
        # rows it moves to a third page (its own 210 pt reservation).
        assert len(texts) == 2


def test_pricing_block_taller_than_a_page_still_splits_by_row_with_heading_and_first_rows():
    tokens = [f"ZONE{index:02d}" for index in range(1, 29)]
    texts = _render([
        _zone_item(token, f"Zone {index}", 14)
        for index, token in enumerate(tokens, start=1)
    ])

    assert _pages_with(texts, "Services and pricing") == [0]
    header_pages = _pages_with(texts, HEADER_ROW)
    assert len(header_pages) >= 2, "a split table repeats its column header"
    assert header_pages[0] == 0
    assert _pages_with(texts, "ZONE01-BEGIN") == [0]
    assert _pages_with(texts, "ZONE01-END") == [0]
    for token in tokens:
        begin = _pages_with(texts, f"{token}-BEGIN")
        assert len(begin) == 1, token
        assert _pages_with(texts, f"{token}-END") == begin, token
        assert begin[0] in header_pages, token
    assert _pages_with(texts, "Total contract value") == _pages_with(texts, "ZONE28-END")


def test_section_block_reserves_the_measured_height_only_when_it_fits_one_page():
    from crm_app.commercial_pdf import section_block

    styles = document_styles()
    short = section_block(
        "01", "Example", [Paragraph("One line", styles["body"])], styles,
        minimum_following_height=125,
    )
    assert isinstance(short[0], CondPageBreak)
    assert 0 < short[0].height < 125

    tall = section_block(
        "01", "Example", [Spacer(1, PAGE_HEIGHT)], styles,
        minimum_following_height=125,
    )
    assert tall[0].height == 125

    # A body with its own page-break logic is never measured as one block.
    nested = section_block(
        "01", "Example", [CondPageBreak(96), Spacer(1, 10)], styles,
        minimum_following_height=125,
    )
    assert nested[0].height == 125
