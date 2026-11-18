"""The corporate participation format reports a render error.

A participation contract whose corporate parent selects the combined
Attachment A / Exhibit D format must not silently turn into the standard
participation agreement when that render fails. Only a missing corporate
template falls back to the standard format.

All fixtures are synthetic.
"""
from types import SimpleNamespace

import pytest

from crm_app.models import Company
from crm_app.tests.test_contract_pdf_malformed_markup import _corporate
from crm_app.tests.test_contract_pdf_stored_text_escaping import _category, _render, agreement  # noqa: F401
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db


def _response(agreement):
    view = ContractViewSet()
    view.get_object = lambda: agreement
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False), _bmasia_suppress_pdf_activity=True,
    )
    return view.pdf(view.request, pk=agreement.pk)


def test_render_error_in_the_corporate_format_is_reported(agreement, monkeypatch):  # noqa: F811
    _corporate(agreement, warranty_text='Example warranty.')
    agreement.save()

    def failing_render(self, contract):
        raise RuntimeError('example layout failure')

    monkeypatch.setattr(ContractViewSet, '_generate_hilton_combined_pdf', failing_render)
    standard = []
    monkeypatch.setattr(ContractViewSet, '_contract_v2_response',
                        lambda self, *args, **kwargs: standard.append(args) or None)
    response = _response(agreement)
    assert response.status_code == 500
    assert response.data['code'] == 'CONTRACT_PDF_RENDER_FAILED'
    assert 'example layout failure' not in str(response.data)
    assert not standard


def test_corporate_parent_without_a_template_uses_the_standard_format(agreement):  # noqa: F811
    parent = Company.objects.create(
        name='Example Corporate Parent', country='Vietnam',
        billing_entity='BMAsia Limited', is_corporate_parent=True,
    )
    agreement.company.parent_company = parent
    agreement.company.save()
    _category(agreement, 'participation')
    text = _render(agreement)
    assert 'PARTICIPATION AGREEMENT' in text.upper()
    assert 'HOTEL PARTICIPATION AGREEMENT' not in text.upper()
