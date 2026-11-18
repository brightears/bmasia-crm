"""REST DELETE of a company is refused while it has contracts, invoices or quotes."""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from crm_app.models import AuditLog, Company, Contact, Contract, Invoice, Quote, User


@pytest.fixture
def api():
    user = User.objects.create_user(
        username='delete-tester', email='delete-tester@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _company(name):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited')


def test_company_with_contracts_invoices_or_quotes_is_not_deleted(api):
    company = _company('Keep Me Resort')
    Contract.objects.create(company=company, contract_number='HK-CT-KEEP-1', status='Active',
                            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), value=Decimal('100'))
    Invoice.objects.create(company=company, invoice_number='INV-KEEP-1', issue_date=date(2026, 1, 1),
                           due_date=date(2026, 2, 1), amount=Decimal('100'), total_amount=Decimal('100'))
    Quote.objects.create(company=company, quote_number='HK-QT-KEEP-1', valid_from=date(2026, 1, 1),
                         valid_until=date(2026, 2, 1))

    response = api.delete(f'/api/v1/companies/{company.pk}/')

    assert response.status_code == 409
    assert response.data['code'] == 'company_has_records'
    assert (response.data['contracts'], response.data['invoices'], response.data['quotes']) == (1, 1, 1)
    assert response.data['error'] == (
        'Keep Me Resort has 1 contract, 1 invoice, 1 quote, so it cannot be deleted: that would '
        'delete them too. Set the company inactive instead (is_active = false).'
    )
    assert Company.objects.filter(pk=company.pk).exists()
    assert not AuditLog.objects.filter(action='DELETE').exists()


def test_company_without_documents_can_still_be_deleted(api):
    company = _company('Typo Duplicate Ltd')
    Contact.objects.create(company=company, name='Only Contact', email='only@example.com')

    response = api.delete(f'/api/v1/companies/{company.pk}/')

    assert response.status_code == 204
    assert not Company.objects.filter(pk=company.pk).exists()
    assert AuditLog.objects.filter(action='DELETE', record_id=str(company.pk)).count() == 1
