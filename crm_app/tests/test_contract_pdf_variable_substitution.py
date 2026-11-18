"""Template variables are filled in one pass.

A stored value that itself contains "{{variable}}" text prints as written; it
is never filled in a second time. All fixtures are synthetic.
"""
import pytest

from crm_app.models import ContractTemplate
from crm_app.tests.test_contract_pdf_stored_text_escaping import _render, agreement  # noqa: F401

pytestmark = pytest.mark.django_db


def test_full_template_value_with_variable_text_prints_as_written(agreement):  # noqa: F811
    agreement.property_name = 'Example {{contract_number}} Venue'
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard',
        content=('Trading as {{hotel_trading_name}} under {{contract_number}}.<br/>'
                 'Services: {{service_items}}<br/>{{zones_table}}<br/>{{signature_blocks}}'),
    )
    agreement.save()
    text = _render(agreement)
    assert 'Trading as Example {{contract_number}} Venue under DRAFT-ESCAPE-TEST.' in text


def test_standard_wording_value_with_variable_text_prints_as_written(agreement):  # noqa: F811
    agreement.company.legal_entity_name = 'Example {{issuer_name}} Holdings'
    agreement.company.save()
    agreement.payment_custom = 'Invoices go to {{legal_entity_name}} from {{issuer_name}}.'
    agreement.save()
    text = _render(agreement)
    assert 'Invoices go to Example {{issuer_name}} Holdings from BMAsia Limited.' in text
