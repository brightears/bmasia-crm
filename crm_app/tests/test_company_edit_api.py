"""Exercise the human company-edit endpoint with synthetic invoice details."""
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import uuid

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.models import AuditLog, Company, User
from crm_app.views import CompanyViewSet, serialize_audit_changes


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


def test_company_audit_snapshot_handles_nested_dates_and_numbers():
    audit = serialize_audit_changes({
        'old': {'date': date(2026, 9, 1), 'ids': [uuid.UUID('00000000-0000-0000-0000-000000000001')]},
        'new': {'time': datetime(2026, 9, 28, tzinfo=timezone.utc), 'amount': Decimal('12.50')},
    })
    assert audit['old']['date'] == '2026-09-01'
    assert audit['old']['ids'] == ['00000000-0000-0000-0000-000000000001']
    assert audit['new']['amount'] == '12.50'
    json.dumps(audit)


@pytest.mark.django_db
def test_company_patch_rolls_back_if_audit_fails(monkeypatch):
    company = Company.objects.create(name='Rollback fixture', country='Thailand', industry='Hotels')
    user = User.objects.create_user(username='company-audit-test', role='Sales')
    request = APIRequestFactory().patch(
        '/api/v1/companies/' + str(company.pk) + '/', {'city': 'Changed city'}, format='json'
    )
    force_authenticate(request, user=user)

    def fail_audit(*args, **kwargs):
        raise ValueError('synthetic audit failure')

    monkeypatch.setattr(CompanyViewSet, 'log_action', fail_audit)
    with pytest.raises(ValueError, match='synthetic audit failure'):
        CompanyViewSet.as_view({'patch': 'partial_update'})(request, pk=str(company.pk))
    company.refresh_from_db()
    assert company.city == ''
