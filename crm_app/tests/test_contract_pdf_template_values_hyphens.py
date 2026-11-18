"""A value filled into a full template prints its hyphens as written.

The full-template layout starts a new page at a "---" marker in the template.
A stored value such as "Alpha---Beta" filled into the template is plain text:
it must print with its three hyphens, inside or outside a tag pair, and must
not start a page. All fixtures are synthetic.
"""
from io import BytesIO
import re
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from crm_app.contract_pdf_v2 import fill_template_values
from crm_app.models import ContractTemplate
from crm_app.tests.test_contract_pdf_stored_text_escaping import _render, agreement  # noqa: F401
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db

SLOTS = [
    'company_name', 'legal_entity_name', 'hotel_trading_name', 'contact_name', 'contact_title', 'contact_email',
    'venue_names', 'client_address', 'client_signatory_name', 'client_signatory_title', 'bmasia_contact_name',
    'bmasia_contact_title', 'bmasia_contact_email', 'contract_number', 'service_items', 'payment_clause',
    'activation_clause', 'under_duration', 'payment_schedule', 'additional_terms',
]


def _fill(agreement, value, *, wrap):
    company = agreement.company
    company.name = company.legal_entity_name = company.address_line1 = value
    company.save()
    for field in ('property_name', 'customer_contact_name', 'customer_contact_title', 'customer_signatory_name',
                  'customer_signatory_title', 'bmasia_contact_name', 'bmasia_contact_title', 'contract_number',
                  'payment_custom', 'activation_custom', 'payment_schedule'):
        setattr(agreement, field, value)
    agreement.customer_contact_email = agreement.bmasia_contact_email = f'{value.lower()}@example.com'
    agreement.custom_service_items = [{'name': value}]
    agreement.custom_terms = f'{value}\n[under: duration]\n{value}'
    agreement.service_locations.update(location_name=value)
    lines = [f'K{n:02d}:' + (f'<b>{{{{{slot}}}}}</b>' if wrap else f'{{{{{slot}}}}}') for n, slot in enumerate(SLOTS)]
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard',
        content='<br/>'.join(lines) + '<br/>{{zones_table}}<br/>{{signature_blocks}}',
    )
    agreement.save()


def _pages(agreement):
    view = ContractViewSet()
    view.get_object = lambda: agreement
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False), _bmasia_suppress_pdf_activity=True)
    response = view.pdf(view.request, pk=agreement.pk)
    assert response.status_code == 200, getattr(response, 'data', None)
    return len(PdfReader(BytesIO(response.content)).pages)


@pytest.mark.parametrize('wrap', [True, False], ids=['in_bold', 'plain'])
def test_filled_values_print_their_hyphens_and_start_no_page(agreement, wrap):  # noqa: F811
    _fill(agreement, 'Alpha-Beta', wrap=wrap)
    control_pages = _pages(agreement)
    _fill(agreement, 'Alpha---Beta', wrap=wrap)
    assert _pages(agreement) == control_pages
    text = _render(agreement)
    for n, slot in enumerate(SLOTS):
        expected = 'alpha---beta@example.com' if slot.endswith('email') else 'Alpha---Beta'
        assert f'K{n:02d}:{expected}' in text, slot


# The template itself writes hyphens directly beside a variable. A value that
# starts or ends with a hyphen then sits next to them; together they print as
# written and start no page.
EDGE_TEMPLATE = (
    'E1:A--{{company_name}}-B<br/>E2:A-{{company_name}}--B<br/>{{service_items}}<br/>'
    '{{zones_table}}<br/>{{signature_blocks}}'
)


def _edge_template(agreement, value, *, mode):
    agreement.company.name = value
    agreement.company.save()
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example edge agreement', template_type='preamble', pdf_format='standard', content=EDGE_TEMPLATE,
    )
    agreement.preamble_custom = EDGE_TEMPLATE if mode == 'override' else ''
    agreement.save()


@pytest.mark.parametrize('mode', ['template', 'override'])
def test_value_edge_hyphens_beside_template_hyphens_start_no_page(agreement, mode):  # noqa: F811
    _edge_template(agreement, 'Alpha', mode=mode)
    control_pages = _pages(agreement)
    _edge_template(agreement, '-Alpha-', mode=mode)
    assert _pages(agreement) == control_pages
    text = _render(agreement)
    assert 'E1:A---Alpha--B' in text
    assert 'E2:A--Alpha---B' in text


# An empty value between the template's own hyphens: "A--" and "-B" meet.
JOINED_TEMPLATE = (
    'N1:A--{{billing_note}}-B<br/>{{service_items}}<br/>{{zones_table}}<br/>{{signature_blocks}}'
)


@pytest.mark.parametrize('mode', ['template', 'override'])
def test_template_hyphens_around_an_empty_value_start_no_page(agreement, mode):  # noqa: F811
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example joined agreement', template_type='preamble', pdf_format='standard',
        content=JOINED_TEMPLATE.replace('A--{{billing_note}}-B', 'A-B'),
    )
    agreement.preamble_custom = ''
    agreement.save()
    control_pages = _pages(agreement)
    agreement.preamble_template.content = JOINED_TEMPLATE
    agreement.preamble_template.save()
    agreement.preamble_custom = JOINED_TEMPLATE if mode == 'override' else ''
    agreement.save()
    assert _pages(agreement) == control_pages
    assert 'N1:A---B' in _render(agreement)


VALUES = {'{{x}}': '', '{{y}}': '', '{{v}}': 'Value'}


@pytest.mark.parametrize('content, filled', [
    ('A--{{x}}-B', 'A&#45;&#45;&#45;B'),
    ('A-{{x}}--B', 'A&#45;&#45;&#45;B'),
    ('A--{{x}}--B', 'A&#45;&#45;&#45;&#45;B'),
    ('A-{{x}}-{{y}}-B', 'A&#45;&#45;&#45;B'),
    ('A-{{x}}{{y}}--B', 'A&#45;&#45;&#45;B'),
])
def test_hyphens_that_meet_across_an_empty_value_are_written_as_references(content, filled):
    assert fill_template_values(content, VALUES) == filled
    assert Paragraph(filled, ParagraphStyle('t')).getPlainText() == content.replace('{{x}}', '').replace('{{y}}', '')


@pytest.mark.parametrize('content', [
    'A-{{x}}-B',            # two hyphens only
    'A---{{x}}-B',          # the template wrote three hyphens on one side
    'A-{{x}}---B',
    'A--{{v}}-B',           # the value keeps the template hyphens apart
    'A---B<br/>{{x}}--C',   # the template's own marker, away from the value
    '-{{x}}', '{{x}}--', 'A{{x}}B', 'No variables -- here',
])
def test_other_hyphens_are_filled_as_before(content):
    pattern = '|'.join(map(re.escape, VALUES))
    assert fill_template_values(content, VALUES) == re.sub(pattern, lambda m: VALUES[m.group(0)], content)
