"""A plain invoice update (REST, the agents' update_record, bulk update_status) never moves an invoice backwards.

- Paid is reached only by "Mark as paid" (crm_app/services/invoice_payments.py) and left only for
  Refunded; undoing a payment is the admin's "Mark selected invoices as unpaid".
- Nothing goes back to Draft once it has left Draft.
Every other move a single update could make before is still allowed.
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from crm_app.mcp import update_record
from crm_app.models import Company, Invoice, User

STATUSES = ['Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled', 'Refunded']
ALLOWED = {
    'Draft': {'Draft', 'Sent', 'Overdue', 'Cancelled', 'Refunded'},
    'Sent': {'Sent', 'Overdue', 'Cancelled', 'Refunded'},
    'Overdue': {'Overdue', 'Sent', 'Cancelled', 'Refunded'},
    'Paid': {'Paid', 'Refunded'},
    'Cancelled': {'Cancelled', 'Sent', 'Overdue', 'Refunded'},
    'Refunded': {'Refunded', 'Sent', 'Overdue', 'Cancelled'},
}


@pytest.fixture
def api():
    user = User.objects.create_user(username='status-moves', email='status-moves@example.com',
                                    password='test-only-password', role='Admin', is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _invoice(status, number):
    company, _ = Company.objects.get_or_create(name='Status Move Resort', defaults={'billing_entity': 'BMAsia Limited'})
    extra = {'receipt_number': f'REC-HK-2026-{number[-4:]}', 'paid_date': date(2026, 11, 2)} if status == 'Paid' else {}
    return Invoice.objects.create(company=company, invoice_number=number, status=status,
                                  issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
                                  amount=Decimal('10'), total_amount=Decimal('10'), **extra)


@pytest.mark.parametrize('current', STATUSES)
@pytest.mark.parametrize('target', STATUSES)
def test_plain_update_moves(api, current, target):
    invoice = _invoice(current, f'INV-MOVE-{STATUSES.index(current)}{STATUSES.index(target)}00')
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': target}, format='json')
    invoice.refresh_from_db()
    if target in ALLOWED[current]:
        assert response.status_code == 200, (current, target, response.data)
        assert invoice.status == target
    else:
        assert response.status_code == 400, (current, target)
        assert invoice.status == current
        assert 'status' in response.data


def test_saving_other_fields_of_a_paid_invoice_keeps_it_paid(api):
    invoice = _invoice('Paid', 'INV-MOVE-KEEP')
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'notes': 'Corrected the note'}, format='json')
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert (invoice.status, invoice.notes) == ('Paid', 'Corrected the note')


def test_the_refusal_names_the_way_to_undo_a_payment(api):
    invoice = _invoice('Paid', 'INV-MOVE-UNDO')
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Sent'}, format='json')
    assert 'Mark selected invoices as unpaid' in str(response.data['status'])


def test_agents_cannot_move_an_invoice_back_to_draft():
    invoice = _invoice('Sent', 'INV-MOVE-MCP1')
    out = update_record('invoice', str(invoice.pk), json.dumps({'status': 'Draft'}))
    invoice.refresh_from_db()
    assert invoice.status == 'Sent', out


def test_bulk_update_status_cannot_un_pay(api, monkeypatch):
    from crm_app.views import InvoiceViewSet
    # Bulk operations are offered per record type; enable this one to check the rule it would apply.
    monkeypatch.setattr(InvoiceViewSet, 'bulk_allowed', frozenset({'update_status'}))
    invoice = _invoice('Paid', 'INV-MOVE-BULK')
    response = api.post('/api/v1/invoices/bulk_operations/',
                        {'action': 'update_status', 'ids': [str(invoice.pk)], 'data': {'status': 'Sent'}},
                        format='json')
    assert response.data['updated'] == 0
    invoice.refresh_from_db()
    assert invoice.status == 'Paid'


def test_admin_mark_unpaid_still_works():
    from django.contrib.admin.sites import AdminSite
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from crm_app.admin import InvoiceAdmin
    invoice = _invoice('Paid', 'INV-MOVE-ADMN')
    request = RequestFactory().post('/admin/')
    request.user = User.objects.create_user(username='staff-unpay', is_staff=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    InvoiceAdmin(Invoice, AdminSite()).bulk_mark_unpaid(request, Invoice.objects.filter(pk=invoice.pk))
    invoice.refresh_from_db()
    assert invoice.status == 'Sent' and invoice.receipt_number  # the receipt number is kept
