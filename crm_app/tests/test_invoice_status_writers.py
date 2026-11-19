"""Every writer of an invoice's status follows crm_app/services/invoice_status.py.

Writers: the serializer (REST, agents, bulk; see test_invoice_status_moves.py for its 36 pairs),
the send endpoint and EmailService.send_invoice_email, the Django admin change form and its
actions. Mail goes to Django's in-memory outbox only.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory
from rest_framework.test import APIClient

from crm_app.admin import InvoiceAdmin, InvoiceAdminForm
from crm_app.models import AuditLog, Company, Contact, Invoice, User
from crm_app.services import invoice_status

STATUSES = ['Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled', 'Refunded']

# Sending: what the status becomes, or None when the send is refused.
AFTER_SEND = {'Draft': 'Sent', 'Sent': 'Sent', 'Overdue': 'Overdue', 'Paid': 'Paid',
              'Cancelled': None, 'Refunded': None}


@pytest.fixture
def staff():
    return User.objects.create_user(username='writers-staff', email='writers-staff@example.com',
                                    password='test-only-password', role='Admin', is_active=True,
                                    is_staff=True, is_superuser=True)


@pytest.fixture
def api(staff):
    client = APIClient()
    client.force_authenticate(user=staff)
    return client


def _invoice(status, number):
    company, _ = Company.objects.get_or_create(name='Writer Test Resort', defaults={'billing_entity': 'BMAsia Limited'})
    Contact.objects.get_or_create(company=company, email='billing@example.com',
                                  defaults={'name': 'Billing', 'receives_invoice_emails': True})
    extra = {'receipt_number': f'REC-HK-2026-{number[-4:]}', 'paid_date': date(2026, 11, 2)} if status == 'Paid' else {}
    return Invoice.objects.create(company=company, invoice_number=number, status=status,
                                  issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
                                  amount=Decimal('10'), total_amount=Decimal('10'), **extra)


@pytest.fixture
def pdf():
    with mock.patch('crm_app.views.InvoiceViewSet.pdf') as rendered:
        rendered.return_value.content = b'%PDF-1.4'
        rendered.return_value.status_code = 200
        yield rendered


# --- the send endpoint ---------------------------------------------------------------------

@pytest.mark.parametrize('current', STATUSES)
def test_sending_moves_only_a_draft_and_refuses_cancelled_or_refunded(api, pdf, current):
    invoice = _invoice(current, f'INV-SEND-{STATUSES.index(current):04d}')
    response = api.post(f'/api/v1/invoices/{invoice.pk}/send/', {'recipients': ['billing@example.com']},
                        format='json')
    invoice.refresh_from_db()
    expected = AFTER_SEND[current]
    if expected is None:
        assert response.status_code == 409
        assert response.data['code'] == 'not_sendable'
        assert invoice.status == current
        assert mail.outbox == []
    else:
        assert response.status_code == 200, response.data
        assert invoice.status == expected
        assert len(mail.outbox) == 1  # a resend is still a send
        log = AuditLog.objects.get(model_name='Invoice', record_id=str(invoice.pk))
        assert log.changes['status'] == {'old': current, 'new': expected}
        assert log.changes['action'] == ('Email sent' if current == 'Draft' else 'Email resent')
    if current == 'Paid':
        assert invoice.receipt_number and invoice.paid_date


@pytest.mark.parametrize('current', STATUSES)
def test_the_mail_layer_follows_the_same_rule(pdf, current):
    from crm_app.services.email_service import EmailService
    invoice = _invoice(current, f'INV-MAIL-{STATUSES.index(current):04d}')
    ok, message = EmailService().send_invoice_email(invoice_id=invoice.pk, recipients=['billing@example.com'])
    invoice.refresh_from_db()
    expected = AFTER_SEND[current]
    assert ok is (expected is not None), message
    assert invoice.status == (expected or current)


def test_editing_a_paid_invoice_and_resending_keeps_it_paid(api, pdf):
    """The form's "Resend invoice by email after saving": an edit (no status), then a send."""
    invoice = _invoice('Paid', 'INV-SEND-EDIT')
    assert api.patch(f'/api/v1/invoices/{invoice.pk}/', {'notes': 'New bank details'}, format='json').status_code == 200
    assert api.post(f'/api/v1/invoices/{invoice.pk}/send/', {'recipients': ['billing@example.com']},
                    format='json').status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == 'Paid'


# --- two plain updates cannot un-pay -------------------------------------------------------

def test_paid_refunded_sent_is_closed(api):
    invoice = _invoice('Paid', 'INV-TWO-STEP')
    assert api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Refunded'}, format='json').status_code == 200
    response = api.patch(f'/api/v1/invoices/{invoice.pk}/', {'status': 'Sent'}, format='json')
    assert response.status_code == 400
    assert 'stays refunded' in str(response.data['status'])


# --- the admin -----------------------------------------------------------------------------

@pytest.mark.parametrize('current', STATUSES)
@pytest.mark.parametrize('target', STATUSES)
def test_the_admin_form_follows_the_rule(current, target):
    invoice = _invoice(current, f'INV-ADM-{STATUSES.index(current)}{STATUSES.index(target)}00')
    form = InvoiceAdminForm(instance=invoice)
    form.cleaned_data = {'status': target}
    allowed = target == current or (target != 'Paid' and target in invoice_status.PLAIN_UPDATE_MOVES[current])
    if allowed:
        assert form.clean_status() == target
    else:
        with pytest.raises(Exception):
            form.clean_status()


def _admin_request(user):
    request = RequestFactory().post('/admin/crm_app/invoice/')
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.parametrize('current', STATUSES)
def test_mark_unpaid_moves_only_paid_invoices(staff, current):
    invoice = _invoice(current, f'INV-UNPAY-{STATUSES.index(current):04d}')
    InvoiceAdmin(Invoice, AdminSite()).bulk_mark_unpaid(_admin_request(staff), Invoice.objects.filter(pk=invoice.pk))
    invoice.refresh_from_db()
    assert invoice.status == ('Sent' if current == 'Paid' else current)
    if current == 'Paid':
        assert invoice.receipt_number  # kept


@pytest.mark.parametrize('current', STATUSES)
def test_reopen_moves_only_cancelled_invoices(staff, current):
    invoice = _invoice(current, f'INV-REOPEN-{STATUSES.index(current):04d}')
    InvoiceAdmin(Invoice, AdminSite()).bulk_reopen_cancelled(_admin_request(staff),
                                                             Invoice.objects.filter(pk=invoice.pk))
    invoice.refresh_from_db()
    assert invoice.status == ('Sent' if current == 'Cancelled' else current)


@pytest.mark.parametrize('action,current,label', [
    ('bulk_mark_unpaid', 'Paid', 'Marked unpaid (admin)'),
    ('bulk_reopen_cancelled', 'Cancelled', 'Reopened (admin)'),
])
def test_admin_status_actions_write_one_audit_row_per_invoice(staff, action, current, label):
    first, second = _invoice(current, f'INV-AUD-{action[-4:]}-1'), _invoice(current, f'INV-AUD-{action[-4:]}-2')
    getattr(InvoiceAdmin(Invoice, AdminSite()), action)(_admin_request(staff),
                                                         Invoice.objects.filter(pk__in=[first.pk, second.pk]))
    rows = AuditLog.objects.filter(model_name='Invoice', changes__action=label)
    assert sorted(r.record_id for r in rows) == sorted([str(first.pk), str(second.pk)])
    assert all(r.changes['status'] == {'old': current, 'new': 'Sent'} and r.user == staff for r in rows)


def test_admin_invoice_actions_need_the_change_permission():
    from django.contrib.auth.models import Permission
    clerk = User.objects.create_user(username='view-only-staff', email='view-only@example.com',
                                     password='test-only-password', role='Finance', is_active=True, is_staff=True)
    clerk.user_permissions.add(Permission.objects.get(codename='view_invoice'))
    admin = InvoiceAdmin(Invoice, AdminSite())
    names = {'bulk_mark_paid', 'bulk_mark_unpaid', 'bulk_reopen_cancelled'}
    assert not names & set(admin.get_actions(_admin_request(clerk)))
    clerk.user_permissions.add(Permission.objects.get(codename='change_invoice'))
    clerk = User.objects.get(pk=clerk.pk)  # permissions are cached per user object
    assert names <= set(admin.get_actions(_admin_request(clerk)))


def test_a_payment_recorded_while_the_draft_is_being_sent_is_kept(pdf):
    """The send's Draft -> Sent move is conditional: it does not write Sent over Paid."""
    from django.core.mail.backends.locmem import EmailBackend

    from crm_app.services.email_service import EmailService
    invoice = _invoice('Draft', 'INV-RACE-0001')
    original = EmailBackend.send_messages

    def paid_meanwhile(self, messages):
        Invoice.objects.filter(pk=invoice.pk).update(status='Paid', paid_date=date(2026, 11, 3),
                                                     receipt_number='REC-HK-2026-9001')
        return original(self, messages)

    with mock.patch.object(EmailBackend, 'send_messages', paid_meanwhile):
        ok, message = EmailService().send_invoice_email(invoice_id=invoice.pk, recipients=['billing@example.com'])
    assert ok, message
    assert len(mail.outbox) == 1
    invoice.refresh_from_db()
    assert (invoice.status, invoice.receipt_number) == ('Paid', 'REC-HK-2026-9001')


# --- the rule itself -----------------------------------------------------------------------

def test_send_rule_and_edit_rule_agree_on_what_is_final():
    for current in STATUSES:
        final_for_edits = not invoice_status.PLAIN_UPDATE_MOVES[current] - {'Refunded'} and current != 'Paid'
        if current in ('Cancelled', 'Refunded'):
            assert final_for_edits
            assert invoice_status.send_refusal(current)
        else:
            assert invoice_status.send_refusal(current) is None
