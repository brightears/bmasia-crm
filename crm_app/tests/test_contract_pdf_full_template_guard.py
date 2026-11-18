"""Full-template contracts guard the template body before it is laid out.

The stored template body (or a contract's full-body preamble override) is
markup by design. A bare "&", a stray "<", a non-formatting tag or tags that
do not pair up must not stop the PDF: the body is guarded once, before the
layout splits it at the zones table, the signature blocks and page-break
markers. Values substituted into it are still escaped exactly once.

All fixtures are synthetic.
"""
import logging

import pytest

from crm_app.models import ContractTemplate
from crm_app.tests.test_contract_pdf_stored_text_escaping import (  # noqa: F401
    BMA_SIGNER_NAME, LEGAL_NAME, ZONE_NAME, _render, agreement,
)

pytestmark = pytest.mark.django_db

TAIL = 'Services: {{service_items}}<br/>{{zones_table}}<br/>{{signature_blocks}}'


def _template(agreement, body, *, override=False):
    template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard',
        content='<b>Client:</b> {{legal_entity_name}}<br/>Standard body.<br/>' + TAIL,
    )
    agreement.preamble_template = template
    if override:
        agreement.preamble_custom = body + TAIL
    else:
        template.content = body + TAIL
        template.save()
    agreement.save()
    return template


@pytest.mark.parametrize('override', [False, True], ids=['template', 'full_body_override'])
def test_stray_characters_in_the_body_print_as_written(agreement, override):  # noqa: F811
    _template(agreement, '<b>Client:</b> {{legal_entity_name}}<br/>'
                         'Clause for F&B outlets where A<B and <p>notes</p> apply.<br/>', override=override)
    text = _render(agreement)
    assert f'Client: {LEGAL_NAME}' in text
    assert 'Clause for F&B outlets where A<B and <p>notes</p> apply.' in text
    assert ZONE_NAME in text and BMA_SIGNER_NAME in text


@pytest.mark.parametrize('override', [False, True], ids=['template', 'full_body_override'])
@pytest.mark.parametrize('body', [
    'Clause <b>opened and never closed.<br/>',
    '<b>Part one ---<br/>Part two</b><br/>',
    '<i>Spans</i> <b>the line<br/><br/>break</b> <i>crossed</b></i><br/>',
], ids=['unclosed', 'across_page_break', 'crossed'])
def test_body_whose_tags_do_not_pair_up_prints_tags_as_text(agreement, override, body, caplog):  # noqa: F811
    template = _template(agreement, '<b>Client:</b> {{legal_entity_name}}<br/>' + body, override=override)
    with caplog.at_level(logging.WARNING, logger='crm_app.contract_pdf_v2'):
        text = _render(agreement)
    # The body's tags print as text, substituted values are still escaped
    # once, and the zones table and the signature blocks still render.
    assert f'<b>Client:</b> {LEGAL_NAME}' in text
    assert ZONE_NAME in text and BMA_SIGNER_NAME in text
    field, record = (('Contract.preamble_custom', agreement.pk) if override
                     else ('ContractTemplate.content', template.pk))
    messages = [r.getMessage() for r in caplog.records]
    assert any(field in m and str(record) in m for m in messages), messages
    assert not any('Part one' in m or 'opened' in m for m in messages)


@pytest.mark.parametrize('content', [
    'Intro <b>schedule<br/><br/>Locations:</b><br/>{{zones_table}}<br/>{{signature_blocks}}',
    'Intro <b>schedule<br/>Description of the services:</b><br/>{{zones_table}}<br/>{{signature_blocks}}',
], ids=['after_blank_line', 'heading_line'])
def test_tags_spanning_the_zones_heading_print_as_text(agreement, content):  # noqa: F811
    agreement.custom_service_items = []
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard', content=content,
    )
    agreement.save()
    text = _render(agreement)
    assert 'Intro <b>schedule' in text
    assert ZONE_NAME in text and BMA_SIGNER_NAME in text


def test_well_formed_body_keeps_its_formatting(agreement):  # noqa: F811
    _template(agreement, '<b>Client:</b> {{legal_entity_name}}<br/><b>Bold</b> and <i>italic</i> clause.<br/>'
                         '<b>---</b><br/>After the break.<br/>')
    text = _render(agreement)
    assert 'Bold and italic clause.' in text and 'After the break.' in text
    assert '<b>' not in text and '---' not in text
