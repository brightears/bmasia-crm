"""Quote PDF "Prepared for" card: legal name with branch, plus tax ID.

Synthetic fixtures only. Assertions run on the rendered PDF's extracted text.
"""

from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from crm_app.commercial_pdf import entity_profile_for
from crm_app.quote_pdf_v2 import build_quote_pdf_v2
from crm_app.services.document_context import customer_legal_entity_name
from scripts.preview_commercial_pdf_v2 import (
    ROOT,
    RelatedList,
    format_address_multiline,
    format_duration,
    sample_quote,
)


LOGO = ROOT / "crm_app/static/crm_app/images/bmasia_logo.png"
ENTITY = entity_profile_for("BMAsia (Thailand) Co., Ltd.")


def example_company(**overrides):
    values = dict(
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
    values.update(overrides)
    return SimpleNamespace(**values)


def quote_for(company, items=None):
    quote = sample_quote()
    quote.company = company
    quote.contact = None
    if items is None:
        items = quote.line_items.all()[:1]
    quote.line_items = RelatedList(items)
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    quote.subtotal = subtotal
    quote.total_value = subtotal
    return quote


def render_page_texts(quote):
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


def _joined(company):
    return "\n".join(render_page_texts(quote_for(company)))


def test_prepared_for_prints_legal_name_with_branch_and_tax_id_like_the_contract():
    company = example_company()
    joined = _joined(company)

    # The contract card uses the same helper, so both documents agree.
    expected_name = customer_legal_entity_name(company)
    assert expected_name == "Example Hotel Co., Ltd. (Branch 00001)"
    assert joined.count(expected_name) == 1
    assert joined.count("Tax ID: 0100000000001") == 1


def test_prepared_for_does_not_repeat_a_branch_already_in_the_legal_name():
    joined = _joined(example_company(legal_entity_name="Example Hotel Co., Ltd. (Branch 00001)"))

    assert joined.count("Branch 00001") == 1


def test_prepared_for_without_branch_or_tax_id_adds_no_empty_line_or_punctuation():
    joined = _joined(example_company(branch="", tax_id=""))

    assert "Example Hotel Co., Ltd." in joined
    assert "Example Hotel Co., Ltd. (" not in joined
    assert "()" not in joined
    # Only the issuer's own Tax ID line remains.
    assert joined.count("Tax ID:") == 1
    assert "Tax ID: 0100000000001" not in joined


def test_prepared_for_with_tax_id_but_no_branch_prints_plain_legal_name_and_tax_id():
    joined = _joined(example_company(branch=""))

    assert "Example Hotel Co., Ltd." in joined
    assert "Example Hotel Co., Ltd. (" not in joined
    assert joined.count("Tax ID: 0100000000001") == 1


def test_prepared_for_blank_tax_id_prints_no_tax_id_line():
    joined = _joined(example_company(branch="", tax_id="   "))

    assert joined.count("Tax ID:") == 1


def test_prepared_for_falls_back_to_company_name_without_a_legal_name():
    joined = _joined(example_company(legal_entity_name="", branch="", tax_id=""))

    assert "Example Hotel" in joined
    assert "Example Hotel Co., Ltd." not in joined
    assert "()" not in joined
