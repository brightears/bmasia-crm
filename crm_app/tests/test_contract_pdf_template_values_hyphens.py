"""A value filled into a full template prints its hyphens as written.

The full-template layout starts a new page at a "---" marker in the template.
A stored value such as "Alpha---Beta" filled into the template is plain text:
it must print with its three hyphens, inside or outside a tag pair, and must
not start a page. All fixtures are synthetic.
"""
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

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
