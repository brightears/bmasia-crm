"""A malformed value can no longer stop a contract PDF from rendering.

Wording fields that are markup by design may still hold tags that do not pair
up (an unclosed <b>, mis-nested tags). Such a value prints as plain text, the
rest of the document keeps its formatting, and a warning names the field and
the record but not the wording.

All fixtures are synthetic.
"""
import logging

import pytest

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from crm_app.contract_pdf_v2 import paragraph_markup, stored_markup
from crm_app.models import Company, Contact, ContractTemplate, CorporatePdfTemplate
from crm_app.tests.test_contract_pdf_stored_text_escaping import (  # noqa: F401
    CONTACT_EMAIL, CONTACT_NAME, CONTACT_TITLE, _category, _render, agreement,
)

pytestmark = pytest.mark.django_db

MALFORMED = 'Begin <b>open and <i>crossed</b> tags</i> end'
WELL_FORMED = '<b>Bold</b> F&B wording'


def test_well_formed_value_is_guarded_markup(caplog):
    with caplog.at_level(logging.WARNING):
        assert stored_markup(WELL_FORMED, field='Contract.payment_custom', record=7) == paragraph_markup(WELL_FORMED)
    assert not caplog.records


@pytest.mark.parametrize('value', [MALFORMED, '<b>unclosed', 'stray </i> close', '<sub>a<super>b</sub></super>'])
def test_malformed_value_prints_as_plain_text_and_warns_without_content(value, caplog):
    with caplog.at_level(logging.WARNING, logger='crm_app.contract_pdf_v2'):
        fallback = stored_markup(value, field='Contract.payment_custom', record=7)
    assert Paragraph(fallback, ParagraphStyle('t')).getPlainText() == value
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert 'Contract.payment_custom' in messages[0] and '7' in messages[0]
    assert value not in messages[0] and 'open' not in messages[0]


def _corporate(agreement, **template_fields):
    parent = Company.objects.create(
        name='Example Corporate Parent', country='Vietnam',
        billing_entity='BMAsia Limited', is_corporate_parent=True,
    )
    corporate_format = next(
        key for key, _label in CorporatePdfTemplate.TEMPLATE_FORMAT_CHOICES if key.endswith('_hpa')
    )
    CorporatePdfTemplate.objects.create(
        name='Example corporate layout', template_format=corporate_format, company=parent, **template_fields,
    )
    agreement.company.parent_company = parent
    agreement.company.save()
    Contact.objects.create(
        company=agreement.company, name=CONTACT_NAME, email=CONTACT_EMAIL,
        contact_type='Primary', title=CONTACT_TITLE,
    )
    _category(agreement, 'participation')


SLOTS = [
    'preamble_custom', 'payment_custom', 'activation_custom', 'custom_terms', 'custom_terms_placed',
    'payment_template', 'activation_template', 'warranty_text', 'legal_terms',
    'master_custom_terms', 'participation_custom_terms',
]


@pytest.mark.parametrize('slot', SLOTS)
def test_malformed_wording_prints_as_text_in_every_slot(agreement, slot):  # noqa: F811
    value = f'MK {MALFORMED} KM'
    if slot in ('preamble_custom', 'payment_custom', 'activation_custom', 'custom_terms'):
        setattr(agreement, slot, value)
    elif slot == 'custom_terms_placed':
        agreement.custom_terms = f'[under: payment]\n{value}'
    elif slot in ('payment_template', 'activation_template'):
        setattr(agreement, slot, ContractTemplate.objects.create(
            name='Example wording', template_type=slot.split('_')[0], pdf_format='standard', content=value,
        ))
    elif slot in ('warranty_text', 'legal_terms'):
        _corporate(agreement, **{slot: value})
    else:
        _category(agreement, slot.split('_')[0].replace('master', 'corporate_master'))
        agreement.custom_terms = f'{value}\n[under: duration]\n{value}'
    agreement.save()
    text = _render(agreement)
    assert value in text
    # The rest of the document still formats its own tags.
    assert '<b>' not in text.replace(value, '')


def test_formatting_that_spans_a_line_break_still_renders(agreement):  # noqa: F811
    agreement.payment_custom = 'Pay <strong>first line<br/>second line</strong> and <super>x<br/>y</super>.'
    agreement.save()
    text = _render(agreement)
    assert 'first line' in text and 'second line' in text
    assert '<strong>' not in text and '<super>' not in text


# Upper case, an attribute, an entity and a bare "&": the fallback prints the
# stored wording itself, not the guarded form of it, and decodes its entities
# as the markup would have.
MALFORMED_WITH_ENTITIES = 'Fee <B class="x">A &amp; B & C &lt;D&gt;'


def test_malformed_field_falls_back_from_the_stored_wording(agreement):  # noqa: F811
    agreement.payment_custom = MALFORMED_WITH_ENTITIES
    agreement.save()
    text = _render(agreement)
    assert 'Fee <B class="x">A & B & C <D>' in text


# A malformed value that also holds a bare "&" and a character reference
# outside Unicode: the fallback prints both as written.
MALFORMED_WITH_REFERENCE = 'Fee <b>open F&B &#99999999; and &#x110000; end'


def test_malformed_value_prints_an_invalid_character_reference_as_written():
    fallback = stored_markup(MALFORMED_WITH_REFERENCE, field='Contract.payment_custom', record=7)
    assert Paragraph(fallback, ParagraphStyle('t')).getPlainText() == MALFORMED_WITH_REFERENCE


def test_malformed_field_with_an_invalid_character_reference_renders(agreement):  # noqa: F811
    agreement.payment_custom = MALFORMED_WITH_REFERENCE
    agreement.save()
    text = _render(agreement)
    assert MALFORMED_WITH_REFERENCE in text


def test_fallback_decodes_entities_and_keeps_line_breaks():
    value = 'One &amp; two <b>open<br/>next &#169; line'
    fallback = stored_markup(value, field='Contract.payment_custom', record=7)
    assert fallback.count('<br/>') == 1
    assert Paragraph(fallback, ParagraphStyle('t')).getPlainText() == 'One & two <b>opennext \u00a9 line'
    # Applying it again changes nothing.
    assert stored_markup(fallback, field='Contract.payment_custom', record=7) == fallback
