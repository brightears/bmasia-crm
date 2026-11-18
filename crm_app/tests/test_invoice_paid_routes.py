"""Every route that could set an invoice Paid or write a receipt number goes through mark_paid or is refused."""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from crm_app.admin import InvoiceAdmin, InvoiceAdminForm
from crm_app.mcp import create_record, update_record
from crm_app.models import AuditLog, Company, Invoice, User
from crm_app.serializers import InvoiceSerializer

THAI = 'BMAsia (Thailand) Co., Ltd.'


@pytest.fixture(autouse=True)
def bulk_operations_enabled(monkeypatch):
    """These tests check what bulk operations do once a record type enables them; which types enable
    which operations is pinned in test_bulk_operations_rules.py."""
    from crm_app.views import BaseModelViewSet
    monkeypatch.setattr(BaseModelViewSet, 'bulk_allowed', frozenset({'delete', 'update_status'}))


@pytest.fixture
def user():
    return User.objects.create_user(
        username='paid-routes', email='paid-routes@example.com',
        password='test-only-password', role='Admin', is_active=True, is_staff=True, is_superuser=True,
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def company():
    return Company.objects.create(name='Route Test Resort', billing_entity=THAI, country='Thailand')


def _invoice(company, number='INV-ROUTE-1', status='Sent', **extra):
    return Invoice.objects.create(
        company=company, invoice_number=number, status=status,
        issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
        amount=Decimal('1000.00'), total_amount=Decimal('1000.00'), currency='THB', **extra,
    )


# --- REST ----------------------------------------------------------------------------------

def test_rest_patch_cannot_set_paid(api, company):
    invoice = _invoice(company)
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Paid'}, format='json')
    assert response.status_code == 400
    assert 'Mark as paid' in str(response.data['status'])
    invoice.refresh_from_db()
    assert invoice.status == 'Sent'


def test_rest_create_cannot_start_paid(api, company):
    response = api.post('/api/v1/invoices/', {
        'company': str(company.pk), 'invoice_number': 'INV-ROUTE-NEW', 'status': 'Paid',
        'issue_date': '2026-11-01', 'due_date': '2026-12-01', 'amount': '10.00', 'total_amount': '10.00',
    }, format='json')
    assert response.status_code == 400
    assert 'status' in response.data


def test_rest_patch_cannot_write_a_receipt_number(api, company):
    invoice = _invoice(company)
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'receipt_number': 'REC-TH-2026-0500'}, format='json')
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.receipt_number is None


def test_a_paid_invoice_can_still_be_edited_and_set_back(api, company):
    invoice = _invoice(company, status='Paid', receipt_number='REC-TH-2026-0003', paid_date=date(2026, 11, 2))
    assert api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Paid', 'notes': 'x'},
                     format='json').status_code == 200
    assert api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Sent'}, format='json').status_code == 200
    invoice.refresh_from_db()
    assert (invoice.status, invoice.receipt_number) == ('Sent', 'REC-TH-2026-0003')


def test_serializer_lists_receipt_number_as_read_only():
    assert 'receipt_number' in InvoiceSerializer.Meta.read_only_fields


def test_next_receipt_number_endpoint_is_gone(api):
    assert api.get('/api/v1/invoices/next-receipt-number/?entity=Thailand').status_code == 404


# --- bulk_operations update_status ---------------------------------------------------------

def _bulk(api, ids, data):
    return api.post('/api/v1/invoices/bulk_operations/',
                    {'action': 'update_status', 'ids': [str(i) for i in ids], 'data': data}, format='json')


def test_bulk_update_status_refuses_paid_per_record(api, company):
    invoice = _invoice(company)
    response = _bulk(api, [invoice.pk], {'status': 'Paid'})
    assert response.status_code == 200
    assert response.data['updated'] == 0
    assert 'Mark as paid' in str(response.data['results'][0]['errors']['status'])
    invoice.refresh_from_db()
    assert invoice.status == 'Sent'
    assert not AuditLog.objects.exists()


def test_bulk_update_status_changes_only_status_with_one_audit_row_each(api, company):
    first, second = _invoice(company, 'INV-ROUTE-A'), _invoice(company, 'INV-ROUTE-B')
    response = _bulk(api, [first.pk, second.pk], {'status': 'Overdue'})
    assert response.data['updated'] == 2
    for invoice in (first, second):
        invoice.refresh_from_db()
        assert invoice.status == 'Overdue'
        # the same audit row a single PATCH writes (InvoiceViewSet.perform_update)
        assert AuditLog.objects.filter(model_name='Invoice', record_id=str(invoice.pk), action='UPDATE').count() == 1


@pytest.mark.parametrize('data', [
    {'status': 'Sent', 'receipt_number': 'REC-TH-2026-0900'},
    {'paid_date': '2026-11-02'},
    {},
])
def test_bulk_update_status_refuses_other_fields(api, company, data):
    invoice = _invoice(company)
    response = _bulk(api, [invoice.pk], data)
    assert response.status_code == 400
    invoice.refresh_from_db()
    assert invoice.receipt_number is None and invoice.paid_date is None


def test_bulk_update_status_reports_unknown_ids(api, company):
    response = _bulk(api, ['00000000-0000-0000-0000-000000000001'], {'status': 'Sent'})
    assert response.data['results'] == [
        {'id': '00000000-0000-0000-0000-000000000001', 'updated': False, 'error': 'Not found.'}]


def test_bulk_update_status_uses_each_models_own_rules(api, company):
    """Contracts too: an invalid status is refused per record instead of written."""
    from crm_app.models import Contract
    contract = Contract.objects.create(company=company, contract_number='TH-CT-ROUTE', status='Draft',
                                       start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), value=Decimal('1'))
    response = api.post('/api/v1/contracts/bulk_operations/',
                        {'action': 'update_status', 'ids': [str(contract.pk)], 'data': {'status': 'Bogus'}},
                        format='json')
    assert response.data['updated'] == 0
    contract.refresh_from_db()
    assert contract.status == 'Draft'


# --- MCP -----------------------------------------------------------------------------------

def test_mcp_update_record_cannot_set_paid(company):
    invoice = _invoice(company)
    out = update_record('invoice', str(invoice.pk), json.dumps({'status': 'Paid'}))
    invoice.refresh_from_db()
    assert invoice.status == 'Sent'
    assert 'Mark as paid' in out
    # what an agent can do instead
    assert 'Payments are recorded by a person in the CRM' in out
    assert 'tell the person which invoice was paid and the payment date' in out


def test_agent_documentation_names_the_real_invoice_statuses():
    from crm_app import mcp
    from crm_app.models import Invoice as InvoiceModel

    instructions = mcp.mcp_server.instructions if hasattr(mcp, 'mcp_server') else ''
    text = ' '.join([instructions or '', mcp.update_record.__doc__ or ''])
    assert 'Void' not in text
    assert 'invoice Paid/' not in text
    assert 'Paid' not in mcp._GUARDED_TERMINAL_STATUSES['invoice']
    statuses = {value for value, _label in InvoiceModel.INVOICE_STATUS_CHOICES}
    assert statuses == {'Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled', 'Refunded'}
    source = open(mcp.__file__).read()
    assert 'Void' not in source


def test_mcp_update_record_cannot_write_a_receipt_number(company):
    invoice = _invoice(company)
    update_record('invoice', str(invoice.pk), json.dumps({'receipt_number': 'REC-TH-2026-0700', 'notes': 'n'}))
    invoice.refresh_from_db()
    assert invoice.receipt_number is None


def test_mcp_create_record_cannot_start_paid(company):
    out = create_record('invoice', json.dumps({
        'company': str(company.pk), 'invoice_number': 'INV-ROUTE-MCP', 'status': 'Paid',
        'issue_date': '2026-11-01', 'due_date': '2026-12-01', 'amount': '10.00', 'total_amount': '10.00',
    }))
    assert not Invoice.objects.filter(invoice_number='INV-ROUTE-MCP').exists(), out


# --- Django admin --------------------------------------------------------------------------

def _admin_request(user):
    request = RequestFactory().post('/admin/crm_app/invoice/')
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def test_admin_bulk_mark_paid_goes_through_the_payment_service(user, company):
    sent = _invoice(company, 'INV-ROUTE-ADM1')
    year = timezone.localdate().year
    already = _invoice(company, 'INV-ROUTE-ADM2', status='Paid', receipt_number=f'REC-TH-{year}-0001')
    InvoiceAdmin(Invoice, AdminSite()).bulk_mark_paid(_admin_request(user), Invoice.objects.filter(
        pk__in=[sent.pk, already.pk]))
    sent.refresh_from_db()
    already.refresh_from_db()
    assert sent.status == 'Paid' and sent.receipt_number == f'REC-TH-{year}-0002' and sent.paid_date is not None
    assert already.receipt_number == f'REC-TH-{year}-0001'


def test_admin_form_refuses_a_change_to_paid(company):
    invoice = _invoice(company)
    form = InvoiceAdminForm(instance=invoice)
    form.cleaned_data = {'status': 'Paid'}
    with pytest.raises(Exception, match='Mark selected invoices as paid'):
        form.clean_status()
    form.cleaned_data = {'status': 'Overdue'}
    assert form.clean_status() == 'Overdue'
