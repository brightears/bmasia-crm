"""Contract text fields accept basic formatting tags only.

Wording fields that are markup by design (custom preamble, payment and
activation wording, additional terms, template bodies and corporate clause
text) keep ``b``, ``i``, ``u``, ``br``, ``strong``, ``em``, ``super`` and
``sub``. Any other tag prints as literal text. Pasted ``font`` and ``span``
tags are dropped and their text kept, as the contract layout already did.
Entities keep working.

All fixtures are synthetic.
"""
import random
import re

import pytest
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from crm_app.contract_pdf_v2 import paragraph_markup, paragraph_text
from crm_app.models import ContractTemplate
from crm_app.tests.test_contract_pdf_stored_text_escaping import _render, agreement  # noqa: F401

STYLE = ParagraphStyle('formatting-tags-test')
FORMATTING_TAGS = {'<b>', '</b>', '<i>', '</i>', '<u>', '</u>', '<strong>', '</strong>', '<em>', '</em>',
                   '<super>', '</super>', '<sub>', '</sub>', '<br/>'}


def printed(markup):
    return Paragraph(markup, STYLE).getPlainText()


def test_formatting_tags_are_kept():
    value = ('<b>bold</b> <i>italic</i> <u>under</u> <strong>strong</strong> <em>em</em> '
             'H<sub>2</sub>O m<super>2</super><br/>next')
    assert paragraph_markup(value) == value
    assert printed(paragraph_markup(value)) == 'bold italic under strong em H2O m2next'


def test_formatting_tags_are_written_one_way():
    assert paragraph_markup('<B>x</B> a<br>b<BR />c<br/>d') == '<b>x</b> a<br/>b<br/>c<br/>d'


def test_attributes_on_formatting_tags_are_dropped():
    value = '<b class="x">Bold</b> <u title="y">under</u> a<br clear="all"/>b'
    assert paragraph_markup(value) == '<b>Bold</b> <u>under</u> a<br/>b'


@pytest.mark.parametrize('value', ['A<B and C>D', 'x <b or c> y', 'a <i.e.> b', '<u + v>', 'one <br or not> two',
                                   '</b x>', '<b title="x>y">z'])
def test_text_that_only_looks_like_a_formatting_tag_prints_as_written(value):
    assert printed(paragraph_markup(value)) == value


@pytest.mark.parametrize('tag', ['para', 'a', 'img', 'link', 'seq', 'unichar', 'strike', 'sup', 'p', 'Ops'])
def test_other_tags_print_as_literal_text(tag):
    value = f'Before <{tag}>inside</{tag}> then <{tag} name="x"/> after'
    guarded = paragraph_markup(value)
    assert f'<{tag}' not in guarded and f'</{tag}' not in guarded
    assert printed(guarded) == value


def test_pasted_font_and_span_tags_are_dropped_and_their_text_kept():
    value = '<font size="9">small</font> and <span class="x">span</span> <b>bold</b>'
    assert paragraph_markup(value) == 'small and span <b>bold</b>'


def test_entities_keep_working():
    value = 'A &amp; B &lt;tag&gt; &#160; &#x41; &nbsp; &euro; &quot;'
    assert paragraph_markup(value) == value
    assert printed(paragraph_markup(value)) == 'A & B <tag> \xa0 A \xa0 € "'


def test_character_references_outside_unicode_print_as_written():
    value = 'x &#1114112; &#x110000; &#99999999; &#xD800; &#0; y'
    guarded = paragraph_markup(value)
    assert printed(guarded) == value


def test_guarding_is_idempotent_and_leaves_only_formatting_tags():
    tokens = ['<b>', '</b>', '<i>', '</i>', '<u>', '<strong>', '</em>', '<br>', '<br/>', '<BR />', '<p>',
              '<para>', '</para>', '<x y="1">', '<font size="2">', '</span>', '<b class="c">', '&', '&amp;',
              '&lt;', '&#38;', '&#x26;', '&#99999999;', '&nbsp', '<', '>', '<!-- c -->', '<?x?>', ';', '#',
              '"', '=', '/', 'a', 'B', ' ', '\n', 'é', 'ก']
    rng = random.Random(51)
    for _ in range(5000):
        value = ''.join(rng.choice(tokens) for _ in range(rng.randint(0, 14)))
        guarded = paragraph_markup(value)
        assert paragraph_markup(guarded) == guarded, value
        assert set(re.findall(r'<[^<>]*>', guarded)) <= FORMATTING_TAGS, value
    # Escaped plain text passes through unchanged.
    assert paragraph_markup(paragraph_text('a < b & <c>')) == paragraph_text('a < b & <c>')


@pytest.mark.django_db
def test_standard_agreement_prints_other_tags_in_wording_fields_as_text(agreement):  # noqa: F811
    agreement.payment_custom = 'Pay <u>promptly</u> per <para>Clause 7</para> and H<sub>2</sub>O.'
    agreement.custom_terms = 'Extra <strong>term</strong> with <seq/> marker.'
    agreement.save()
    text = _render(agreement)
    assert 'Pay promptly per <para>Clause 7</para> and H2O.' in text
    assert 'Extra term with <seq/> marker.' in text


@pytest.mark.django_db
def test_full_template_prints_other_tags_as_text(agreement):  # noqa: F811
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example tagged template', template_type='preamble', pdf_format='standard',
        content=('<b>Client:</b> {{legal_entity_name}}<br/>'
                 'Clause <em>one</em> keeps <p>this</p> visible.<br/>'
                 'Services: {{service_items}}<br/>{{zones_table}}<br/>{{signature_blocks}}'),
    )
    agreement.save()
    text = _render(agreement)
    assert 'Clause one keeps <p>this</p> visible.' in text
