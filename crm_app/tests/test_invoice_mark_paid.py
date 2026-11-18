"""POST /invoices/{id}/mark_paid/: once only, a stated payment date, and email only on request."""
import threading
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.db import connection, connections
from django.utils import timezone
from rest_framework.test import APIClient

from crm_app.models import AuditLog, Company, Invoice, User
from crm_app.services import invoice_payments

SEND_RECEIPT = 'crm_app.services.email_service.EmailService.send_receipt_email'
THAI = 'BMAsia (Thailand) Co., Ltd.'
HK = 'BMAsia Limited'


@pytest.fixture
def operator():
    return User.objects.create_user(
        username='finance-tester', email='finance-tester@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )


@pytest.fixture
def api(operator):
    client = APIClient()
    client.force_authenticate(user=operator)
    return client


def _invoice(number='INV-TEST-0001', status='Sent', entity=THAI, company_name='Lotus Bay Hotel', **extra):
    company, _ = Company.objects.get_or_create(
        name=company_name, defaults={'billing_entity': entity, 'country': 'Thailand'},
    )
    return Invoice.objects.create(
        company=company, invoice_number=number, status=status,
        issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
        amount=Decimal('108000.00'), total_amount=Decimal('108000.00'), currency='THB', **extra,
    )


def _url(invoice):
    return f'/api/v1/invoices/{invoice.pk}/mark_paid/'


def _year():
    return timezone.localdate().year


# --- once only ---------------------------------------------------------------------------

def test_marks_paid_and_numbers_the_receipt(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT) as send:
        response = api.post(_url(invoice), {'paid_date': '2026-11-10'}, format='json')

    assert response.status_code == 200, response.data
    invoice.refresh_from_db()
    assert invoice.status == 'Paid'
    assert invoice.paid_date == date(2026, 11, 10)
    assert invoice.receipt_number == f'REC-TH-{_year()}-0001'
    assert response.data['receipt_number'] == invoice.receipt_number
    assert response.data['paid_date'] == '2026-11-10'
    assert response.data['receipt_email_status'] == 'not_requested'
    send.assert_not_called()


def test_second_request_is_refused_with_the_existing_receipt(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT, return_value=(True, 'sent')) as send:
        first = api.post(_url(invoice), {'send_receipt': True}, format='json')
        second = api.post(_url(invoice), {'send_receipt': True}, format='json')

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.data['code'] == 'already_paid'
    assert second.data['receipt_number'] == first.data['receipt_number']
    assert second.data['paid_date'] == first.data['paid_date']
    assert 'already' in second.data['error'].lower()
    assert send.call_count == 1
    assert Invoice.objects.exclude(receipt_number=None).count() == 1


def test_invoice_paid_by_other_means_is_refused(api):
    invoice = _invoice(status='Paid', paid_date=date(2026, 11, 2))
    with mock.patch(SEND_RECEIPT) as send:
        response = api.post(_url(invoice), {}, format='json')
    assert response.status_code == 409
    assert response.data['receipt_number'] is None
    assert response.data['paid_date'] == '2026-11-02'
    send.assert_not_called()
    invoice.refresh_from_db()
    assert invoice.receipt_number is None


@pytest.mark.parametrize('status', ['Cancelled', 'Refunded'])
def test_cancelled_or_refunded_invoice_is_refused(api, status):
    invoice = _invoice(status=status)
    response = api.post(_url(invoice), {}, format='json')
    assert response.status_code == 409
    assert response.data['code'] == 'not_payable'
    invoice.refresh_from_db()
    assert invoice.status == status and invoice.receipt_number is None


@pytest.mark.parametrize('status', ['Draft', 'Sent', 'Overdue'])
def test_open_invoices_can_be_marked_paid(api, status):
    invoice = _invoice(status=status)
    assert api.post(_url(invoice), {}, format='json').status_code == 200


def test_a_receipt_number_already_on_the_invoice_is_kept(api):
    """An invoice that was paid, then set back to Sent, keeps its first receipt number."""
    invoice = _invoice(receipt_number=f'REC-TH-{_year()}-0007')
    response = api.post(_url(invoice), {}, format='json')
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.receipt_number == f'REC-TH-{_year()}-0007'


def test_numbering_continues_per_issuer(api):
    _invoice(number='INV-A', status='Paid', receipt_number=f'REC-TH-{_year()}-0041')
    _invoice(number='INV-B', status='Paid', receipt_number=f'REC-HK-{_year()}-0003',
             company_name='Harbour Lane Cafe', entity=HK)
    thai = _invoice(number='INV-C')
    hk = _invoice(number='INV-D', company_name='Harbour Lane Cafe', entity=HK)

    assert api.post(_url(thai), {}, format='json').data['receipt_number'] == f'REC-TH-{_year()}-0042'
    assert api.post(_url(hk), {}, format='json').data['receipt_number'] == f'REC-HK-{_year()}-0004'


# --- payment date ------------------------------------------------------------------------

def test_payment_date_defaults_to_today(api):
    invoice = _invoice()
    response = api.post(_url(invoice), {}, format='json')
    invoice.refresh_from_db()
    assert invoice.paid_date == timezone.localdate()
    assert response.data['paid_date'] == timezone.localdate().isoformat()


@pytest.mark.parametrize('value', ['10/11/2026', '2026-13-01', 'yesterday', 12])
def test_unreadable_payment_date_is_refused(api, value):
    invoice = _invoice()
    response = api.post(_url(invoice), {'paid_date': value}, format='json')
    assert response.status_code == 400
    assert 'paid_date' in response.data
    invoice.refresh_from_db()
    assert invoice.status == 'Sent'


def test_future_payment_date_is_refused(api):
    invoice = _invoice()
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    response = api.post(_url(invoice), {'paid_date': tomorrow}, format='json')
    assert response.status_code == 400
    assert 'future' in str(response.data['paid_date']).lower()


def test_payment_method_and_reference_are_recorded(api, operator):
    invoice = _invoice()
    response = api.post(_url(invoice), {
        'paid_date': '2026-11-12', 'payment_method': 'Bank Transfer',
        'transaction_id': 'BANK-REF-123', 'notes': 'Paid in one transfer',
    }, format='json')
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.payment_method == 'Bank Transfer'
    assert invoice.transaction_id == 'BANK-REF-123'
    assert invoice.notes == ''  # the invoice's own notes print on the PDF; payment notes go to the log
    log = AuditLog.objects.get(model_name='Invoice', record_id=str(invoice.pk))
    assert log.user == operator
    assert log.changes['status'] == {'old': 'Sent', 'new': 'Paid'}
    assert log.changes['paid_date'] == '2026-11-12'
    assert log.changes['payment_notes'] == 'Paid in one transfer'


def test_overlong_payment_reference_is_refused(api):
    invoice = _invoice()
    response = api.post(_url(invoice), {'transaction_id': 'x' * 101}, format='json')
    assert response.status_code == 400
    assert 'transaction_id' in response.data


# --- receipt email only on request -------------------------------------------------------

def test_receipt_email_is_sent_only_when_asked(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT, return_value=(True, 'Receipt sent')) as send:
        response = api.post(_url(invoice), {'send_receipt': True}, format='json')
    assert response.status_code == 200
    assert response.data['receipt_email_status'] == 'sent'
    send.assert_called_once()
    assert send.call_args.kwargs['invoice_id'] == invoice.pk


def test_send_receipt_false_does_not_send(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT) as send:
        response = api.post(_url(invoice), {'send_receipt': False}, format='json')
    assert response.data['receipt_email_status'] == 'not_requested'
    send.assert_not_called()


@pytest.mark.parametrize('value', ['yes', 1, None, [True]])
def test_unclear_send_receipt_value_is_refused(api, value):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT) as send:
        response = api.post(_url(invoice), {'send_receipt': value}, format='json')
    assert response.status_code == 400
    assert 'send_receipt' in response.data
    send.assert_not_called()
    invoice.refresh_from_db()
    assert invoice.status == 'Sent'


def test_failed_receipt_email_keeps_the_payment_and_says_so(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT, return_value=(False, 'No recipients found for this receipt')):
        response = api.post(_url(invoice), {'send_receipt': True}, format='json')
    assert response.status_code == 200
    assert response.data['receipt_email_status'] == 'failed: No recipients found for this receipt'
    invoice.refresh_from_db()
    assert invoice.status == 'Paid'


def test_receipt_email_error_text_is_not_returned(api):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT, side_effect=RuntimeError('smtp.internal.example: auth 535')):
        response = api.post(_url(invoice), {'send_receipt': True}, format='json')
    assert response.status_code == 200
    assert response.data['receipt_email_status'].startswith('failed')
    assert 'smtp.internal' not in response.data['receipt_email_status']


# --- concurrency (PostgreSQL: SQLite serialises writers and ignores row locks) -----------

postgres_only = pytest.mark.skipif(
    connection.vendor != 'postgresql', reason='row locks and advisory locks need PostgreSQL',
)


def _post_in_threads(user, invoices, payload):
    barrier = threading.Barrier(len(invoices))
    results = [None] * len(invoices)

    def worker(index, invoice):
        try:
            client = APIClient()
            client.force_authenticate(user=user)
            barrier.wait(timeout=10)
            results[index] = client.post(_url(invoice), payload, format='json')
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i, inv)) for i, inv in enumerate(invoices)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def _slow_sequence_read():
    """Widen the window between reading the last number and saving the new one."""
    real = invoice_payments._last_receipt_sequence

    def slow(pattern):
        value = real(pattern)
        time.sleep(0.4)
        return value
    return mock.patch.object(invoice_payments, '_last_receipt_sequence', side_effect=slow)


@postgres_only
@pytest.mark.django_db(transaction=True)
def test_two_concurrent_requests_for_one_invoice_make_one_receipt(operator):
    invoice = _invoice()
    with mock.patch(SEND_RECEIPT, return_value=(True, 'sent')) as send, _slow_sequence_read():
        results = _post_in_threads(operator, [invoice, invoice], {'send_receipt': True})

    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409]
    assert send.call_count == 1
    invoice.refresh_from_db()
    assert invoice.receipt_number == f'REC-TH-{_year()}-0001'
    assert AuditLog.objects.filter(model_name='Invoice', record_id=str(invoice.pk)).count() == 1


@postgres_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_for_different_invoices_get_different_numbers(operator):
    invoices = [_invoice(number=f'INV-RACE-{i}') for i in range(3)]
    with _slow_sequence_read():
        results = _post_in_threads(operator, invoices, {})

    assert [r.status_code for r in results] == [200, 200, 200]
    numbers = sorted(Invoice.objects.values_list('receipt_number', flat=True))
    assert numbers == [f'REC-TH-{_year()}-000{i}' for i in (1, 2, 3)]
