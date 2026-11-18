"""/api/v1/audit-logs/ can be filtered to one record (``record_id``)."""
from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient

from crm_app.models import AuditLog, Company, Contract, User


def test_audit_log_list_filters_by_record_id():
    admin = User.objects.create(username='alex.audit', role='Admin')
    company = Company.objects.create(name='Audit Filter Test Co', billing_entity='BMAsia Limited')
    a, b = (Contract.objects.create(company=company, contract_number=n, start_date=date(2026, 1, 1),
                                    value=Decimal('1')) for n in ('TH-CT26914', 'TH-CT26915'))
    for contract in (a, b):
        AuditLog.objects.create(user=admin, action='UPDATE', model_name='Contract', record_id=str(contract.pk),
                                changes={'notes': {'old': '', 'new': 'x'}})
    client = APIClient()
    client.force_authenticate(admin)
    response = client.get('/api/v1/audit-logs/', {'record_id': str(a.pk)})
    assert response.status_code == 200
    assert [row['record_id'] for row in response.json()['results']] == [str(a.pk)]
