"""Exercise the human company-edit endpoint with synthetic invoice details."""
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.models import AuditLog, Company, User
from crm_app.views import CompanyViewSet


@pytest.mark.django_db
def test_human_company_patch_saves_address_and_audits_it():
    company = Company.objects.create(name='Island fixture', country='Maldives', industry='Hotels')
    user = User.objects.create_user(username='company-editor-test', role='Sales')
    patch = {
        'name': 'Island fixture', 'country': 'Maldives', 'industry': 'Hotels',
        'legal_entity_name': 'Island Fixture C/O Example Limited',
        'tax_id': 'TIN:EXAMPLE123', 'address_line1': '4th Floor, Example Tower',
        'address_line2': 'Example Road', 'city': 'Male', 'state': '',
        'postal_code': '20066', 'parent_company': None,
        'phone': '+960 7308525', 'billing_entity': 'BMAsia Limited',
    }
    request = APIRequestFactory().patch('/api/v1/companies/' + str(company.pk) + '/', patch, format='json')
    force_authenticate(request, user=user)
    response = CompanyViewSet.as_view({'patch': 'partial_update'})(request, pk=str(company.pk))
    assert response.status_code == 200, response.data
    company.refresh_from_db()
    for field, value in patch.items():
        assert getattr(company, field) == value
    assert AuditLog.objects.filter(model_name='Company', record_id=str(company.pk), action='UPDATE').exists()
