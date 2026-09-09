from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4

from crm_app.commercial_pdf import (
    AMOUNT_RIGHT_PADDING,
    TOTALS_SIDE_PADDING,
    entity_profile_for,
)
from crm_app.invoice_pdf_v2 import build_invoice_pdf_v2
from crm_app.quote_pdf_v2 import build_quote_pdf_v2
from scripts.preview_commercial_pdf_v2 import (
    ROOT,
    format_address_multiline,
    format_duration,
    sample_invoice,
    sample_quote,
)


LOGO = ROOT / "crm_app/static/crm_app/images/bmasia_logo.png"
ENTITY = entity_profile_for("BMAsia (Thailand) Co., Ltd.")


def _reader(pdf_bytes):
    return PdfReader(BytesIO(pdf_bytes))


def _page_texts(reader):
    return [" ".join((page.extract_text() or "").split()) for page in reader.pages]


def _quote_bytes(quote=None):
    return build_quote_pdf_v2(
        quote or sample_quote(),
        ENTITY,
        str(LOGO),
        format_address_multiline,
        format_duration,
        preview=True,
    )


def _invoice_bytes(invoice=None):
    return build_invoice_pdf_v2(
        invoice or sample_invoice(),
        ENTITY,
        str(LOGO),
        format_address_multiline,
        preview=True,
    )


def test_shared_layout_contract_uses_print_safe_numeric_gutters():
    assert AMOUNT_RIGHT_PADDING >= 18
    assert TOTALS_SIDE_PADDING >= 26


def test_quote_preview_is_a4_multipage_and_renders_notes_once():
    reader = _reader(_quote_bytes())
    texts = _page_texts(reader)
    joined = "\n".join(texts)

    assert len(reader.pages) >= 2
    assert abs(float(reader.pages[0].mediabox.width) - A4[0]) < 1
    assert abs(float(reader.pages[0].mediabox.height) - A4[1]) < 1
    assert joined.count("DRAFT PREVIEW - NOT FOR CUSTOMER") == len(reader.pages)
    assert joined.count("DESCRIPTION") >= 2
    assert joined.count("Customer-facing assumptions are shown once only when deliberately supplied.") == 1
    assert all("TH-QT-PREVIEW-001" in text for text in texts)
    assert not any(character in joined for character in "\u2010\u2011\u2012\u2013\u2014")


def test_invoice_preview_repeats_headers_and_keeps_totals_with_final_item():
    reader = _reader(_invoice_bytes())
    texts = _page_texts(reader)
    joined = "\n".join(texts)

    assert len(reader.pages) >= 2
    assert joined.count("PRODUCT / SERVICE") >= 2
    assert joined.count("Please quote the invoice number with the bank transfer.") == 1
    assert all("TH-INV-PREVIEW-001" in text for text in texts)

    last_item_page = next(index for index, text in enumerate(texts) if "venue zone 32" in text)
    total_page = next(index for index, text in enumerate(texts) if "Amount due" in text)
    assert last_item_page == total_page

    for item_number in range(1, 33):
        token = f"venue zone {item_number:02d}"
        assert sum(token in text for text in texts) == 1


def test_customer_remarks_are_suppressed_when_already_in_terms():
    quote = sample_quote()
    quote.terms_conditions = "Deliberate customer wording appears exactly once."
    quote.notes = quote.terms_conditions

    joined = "\n".join(_page_texts(_reader(_quote_bytes(quote))))
    assert joined.count("Deliberate customer wording appears exactly once.") == 1
    assert "CUSTOMER REMARKS" not in joined


def test_customer_remarks_preserve_wording_that_extends_existing_terms():
    quote = sample_quote()
    quote.terms_conditions = "Payment is due immediately."
    quote.notes = "Payment is due immediately. Please include purchase order PO-123."

    joined = "\n".join(_page_texts(_reader(_quote_bytes(quote))))
    assert "CUSTOMER REMARKS" in joined
    assert "Please include purchase order PO-123." in joined


def test_payment_heading_schedule_and_bank_table_stay_together():
    quote = sample_quote()
    quote.line_items = type(quote.line_items)(quote.line_items.all()[:16])

    texts = _page_texts(_reader(_quote_bytes(quote)))
    heading_page = next(index for index, text in enumerate(texts) if "Payment and terms" in text)
    bank_page = next(index for index, text in enumerate(texts) if "Beneficiary" in text)

    assert heading_page == bank_page


def test_product_legend_stays_with_pricing_content():
    quote = sample_quote()
    quote.line_items = type(quote.line_items)(quote.line_items.all()[:1])

    texts = _page_texts(_reader(_quote_bytes(quote)))
    legend_page = next(index for index, text in enumerate(texts) if "BB = Beat Breeze" in text)

    assert "DESCRIPTION" in texts[legend_page]


def test_complimentary_group_heading_stays_with_first_included_item():
    quote = sample_quote()
    items = quote.line_items.all()
    quote.line_items = type(quote.line_items)(items[:4] + [items[-1]])

    texts = _page_texts(_reader(_quote_bytes(quote)))
    heading_page = next(index for index, text in enumerate(texts) if "INCLUDED AT NO CHARGE" in text)
    item_page = next(index for index, text in enumerate(texts) if "Soundtrack Player" in text)

    assert heading_page == item_page


def test_large_quantity_stays_on_one_line():
    quote = sample_quote()
    first = quote.line_items.all()[0]
    first.quantity = Decimal("100000")
    first.line_total = first.quantity * first.unit_price
    quote.line_items = type(quote.line_items)([first])

    joined = "\n".join(_page_texts(_reader(_quote_bytes(quote))))

    assert "100,000" in joined


def test_max_model_range_price_stays_unbroken_in_line_and_total_cells():
    quote = sample_quote()
    first = quote.line_items.all()[0]
    first.quantity = Decimal("1")
    first.unit_price = Decimal("9999999999.99")
    first.line_total = first.unit_price
    quote.line_items = type(quote.line_items)([first])
    quote.subtotal = first.line_total
    quote.total_value = first.line_total

    joined = "\n".join(_page_texts(_reader(_quote_bytes(quote))))

    assert joined.count("USD 9,999,999,999.99") >= 3


def test_receipt_uses_amount_paid_wording():
    invoice = sample_invoice()
    invoice.status = "Paid"
    invoice.paid_date = invoice.issue_date

    pdf = build_invoice_pdf_v2(
        invoice,
        ENTITY,
        str(LOGO),
        format_address_multiline,
        is_receipt=True,
        preview=True,
    )
    joined = "\n".join(_page_texts(_reader(pdf)))

    assert "Amount paid" in joined
    assert "Amount due" not in joined


def test_long_payment_terms_flow_across_pages_without_layout_failure():
    quote = sample_quote()
    quote.line_items = type(quote.line_items)(quote.line_items.all()[:2])
    quote.terms_conditions = " ".join(
        f"Clause {index}: customer-facing payment wording remains readable and splittable."
        for index in range(1, 181)
    )

    reader = _reader(_quote_bytes(quote))
    joined = "\n".join(_page_texts(reader))

    assert len(reader.pages) >= 3
    assert "Clause 1:" in joined
    assert "Clause 180:" in joined
    assert all("TH-QT-PREVIEW-001" in text for text in _page_texts(reader))


def test_long_customer_notes_flow_across_pages_without_layout_failure():
    quote = sample_quote()
    quote.line_items = type(quote.line_items)(quote.line_items.all()[:1])
    quote.notes = " ".join(
        f"Remark {index}: deliberately entered client wording remains readable."
        for index in range(1, 501)
    )

    reader = _reader(_quote_bytes(quote))
    joined = "\n".join(_page_texts(reader))

    assert len(reader.pages) >= 3
    assert "Remark 1:" in joined
    assert "Remark 500:" in joined


def test_exceptionally_long_line_item_splits_only_when_a_page_cannot_hold_it():
    quote = sample_quote()
    first = quote.line_items.all()[0]
    first.description = "ROW-BEGIN " + " ".join(
        f"service-detail-{index}" for index in range(1, 401)
    ) + " ROW-END"
    quote.line_items = type(quote.line_items)([first])

    reader = _reader(_quote_bytes(quote))
    texts = _page_texts(reader)
    joined = "\n".join(texts)

    assert len(reader.pages) >= 2
    assert joined.count("ROW-BEGIN") == 1
    assert joined.count("ROW-END") == 1


def test_oversized_invoice_row_does_not_orphan_later_final_item_totals():
    invoice = sample_invoice()
    invoice.line_items.all()[0].description = " ".join(
        f"oversized-description-{index}" for index in range(1, 500)
    )

    texts = _page_texts(_reader(_invoice_bytes(invoice)))
    last_item_page = next(index for index, text in enumerate(texts) if "venue zone 32" in text)
    total_page = next(index for index, text in enumerate(texts) if "Amount due" in text)

    assert last_item_page == total_page


def test_final_oversized_invoice_row_keeps_last_fragment_with_totals():
    for word_count in (180, 195, 210, 260, 400, 550):
        invoice = sample_invoice()
        item = invoice.line_items.all()[0]
        end_token = f"FINAL-END-{word_count}"
        item.description = "FINAL-BEGIN " + " ".join(
            f"xword{index}" for index in range(1, word_count + 1)
        ) + f" {end_token}"
        invoice.line_items = type(invoice.line_items)([item])
        invoice.amount = item.quantity * item.unit_price
        invoice.total_amount = invoice.amount

        texts = _page_texts(_reader(_invoice_bytes(invoice)))
        final_fragment_page = next(index for index, text in enumerate(texts) if end_token in text)
        total_page = next(index for index, text in enumerate(texts) if "Amount due" in text)

        assert final_fragment_page == total_page


def test_medium_long_final_quote_row_renders_and_keeps_totals_together():
    for word_count in (210, 243, 260, 277, 320, 500):
        quote = sample_quote()
        item = quote.line_items.all()[0]
        end_token = f"BOUNDARY-END-{word_count}"
        item.description = "BOUNDARY-BEGIN " + " ".join(
            f"word{index}" for index in range(1, word_count + 1)
        ) + f" {end_token}"
        quote.line_items = type(quote.line_items)([item])
        quote.subtotal = item.line_total
        quote.total_value = item.line_total

        texts = _page_texts(_reader(_quote_bytes(quote)))
        final_fragment_page = next(index for index, text in enumerate(texts) if end_token in text)
        total_page = next(index for index, text in enumerate(texts) if "Total (per year)" in text)

        assert final_fragment_page == total_page


def test_oversized_quote_row_does_not_orphan_complimentary_group_heading():
    quote = sample_quote()
    items = quote.line_items.all()
    items[0].description = " ".join(
        f"oversized-description-{index}" for index in range(1, 500)
    )
    quote.line_items = type(quote.line_items)(items[:3] + [items[-1]])

    texts = _page_texts(_reader(_quote_bytes(quote)))
    heading_page = next(index for index, text in enumerate(texts) if "INCLUDED AT NO CHARGE" in text)
    item_page = next(index for index, text in enumerate(texts) if "Soundtrack Player" in text)

    assert heading_page == item_page


def test_oversized_complimentary_item_keeps_group_with_first_fragment():
    quote = sample_quote()
    item = quote.line_items.all()[-1]
    item.description = "COMP-BEGIN " + " ".join(
        f"word{index}" for index in range(1, 501)
    ) + " COMP-END"
    quote.line_items = type(quote.line_items)([item])
    quote.subtotal = Decimal("0")
    quote.total_value = Decimal("0")

    texts = _page_texts(_reader(_quote_bytes(quote)))
    heading_page = next(index for index, text in enumerate(texts) if "INCLUDED AT NO CHARGE" in text)
    first_fragment_page = next(index for index, text in enumerate(texts) if "COMP-BEGIN" in text)
    final_fragment_page = next(index for index, text in enumerate(texts) if "COMP-END" in text)
    total_page = next(index for index, text in enumerate(texts) if "Total (per year)" in text)

    assert heading_page == first_fragment_page
    assert final_fragment_page == total_page


def test_invoice_supports_hong_kong_customer_thailand_issuer_and_usd():
    joined = "\n".join(_page_texts(_reader(_invoice_bytes())))
    assert "Harbour Light Hospitality Limited" in joined
    assert "BMAsia (Thailand) Co., Ltd." in joined
    assert "USD 1,300.00" in joined
    assert "TMBThanachart Bank" in joined
    assert "HSBC" not in joined
