"""The send endpoints answer "nobody is set to receive this" as 422 with a code, and a hand-picked
send is the same email as a normal send.

All mail goes to the test outbox (locmem backend); nothing leaves the machine.
"""
import re
from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from rest_framework.test import APIClient

from crm_app.models import Company, Contact, Contract, Invoice, Quote, User


@pytest.fixture
def company(db):
    return Company.objects.create(name='Lotus Bay Hotel', billing_entity='BMAsia (Thailand) Co., Ltd.',
                                  country='Thailand')


@pytest.fixture
def client(db):
    operator = User.objects.create_user(username='send-tester', email='send-tester@example.test',
                                        password='test-only-password', role='Admin', is_active=True)
    api = APIClient()
    api.force_authenticate(user=operator)
    return api


OFF = {'receives_invoice_emails': False, 'receives_quote_emails': False, 'receives_contract_emails': False}


def _contact(company, email, **fields):
    return Contact.objects.create(company=company, name=email.split('@')[0].title(), email=email, **fields)


def _invoice(company, number='INV-TEST-0001', **extra):
    return Invoice.objects.create(company=company, invoice_number=number, status='Draft',
                                  issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
                                  amount=Decimal('108000.00'), total_amount=Decimal('108000.00'), currency='THB',
                                  **extra)


def _quote(company, number='QT-TEST-0001'):
    return Quote.objects.create(company=company, quote_number=number, status='Draft', currency='THB',
                                valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1))


def _contract(company):
    return Contract.objects.create(company=company, contract_number='CT-TEST-0001', status='Draft',
                                   start_date=date(2027, 1, 1), end_date=date(2027, 12, 31),
                                   value=Decimal('108000.00'), currency='THB')


def _expected(company, kind):
    label = {'receipt': 'receipt (invoice)'}.get(kind, kind)
    return {'code': 'no_recipient', 'kind': kind, 'company_id': str(company.pk),
            'message': f'No contact of Lotus Bay Hotel is set to receive {label} emails.'}


@pytest.mark.parametrize('kind', ['invoice', 'receipt', 'quote', 'contract'])
def test_nobody_set_to_receive_it_is_a_422_with_a_code(company, client, kind):
    _contact(company, 'kim@lotusbay.example.com', contact_type='Billing', **OFF)
    if kind == 'invoice':
        url = f'/api/v1/invoices/{_invoice(company).pk}/send/'
    elif kind == 'receipt':
        url = f'/api/v1/invoices/{_invoice(company, receipt_number="REC-TH-2026-0001").pk}/send-receipt/'
    elif kind == 'quote':
        url = f'/api/v1/quotes/{_quote(company).pk}/send/'
    else:
        url = f'/api/v1/contracts/{_contract(company).pk}/send/'
    response = client.post(url, {}, format='json')
    assert response.status_code == 422, response.content
    assert response.json() == _expected(company, kind)
    assert mail.outbox == []


def test_mark_paid_carries_the_refusal_code(company, client):
    _contact(company, 'kim@lotusbay.example.com', contact_type='Billing', **OFF)
    invoice = _invoice(company)
    Invoice.objects.filter(pk=invoice.pk).update(status='Sent')
    response = client.post(f'/api/v1/invoices/{invoice.pk}/mark_paid/',
                           {'paid_date': '2026-11-10', 'send_receipt': True}, format='json')
    assert response.status_code == 200, response.content
    data = response.json()
    assert data['receipt_email_refusal'] == _expected(company, 'receipt')
    assert data['receipt_email_status'] == 'failed: ' + _expected(company, 'receipt')['message']
    assert mail.outbox == []


def test_other_failures_carry_no_refusal_code(company, client):
    invoice = _invoice(company)
    Invoice.objects.filter(pk=invoice.pk).update(status='Sent')
    response = client.post(f'/api/v1/invoices/{invoice.pk}/mark_paid/', {'paid_date': '2026-11-10'}, format='json')
    assert response.json()['receipt_email_refusal'] is None


def _sent(response):
    assert response.status_code == 200, response.content
    assert len(mail.outbox) == 1, [m.to for m in mail.outbox]
    message = mail.outbox.pop()
    return {
        'to': message.to,
        'subject': message.subject,
        'body': message.body,
        # Each email has its own open-tracking token; everything else must match.
        'html': [re.sub(r'/t/[A-Za-z0-9_-]+/', '/t/<token>/', content)
                 for content, mimetype in getattr(message, 'alternatives', [])],
        'attachments': [(name, len(content), mimetype) for name, content, mimetype in message.attachments],
    }


@pytest.mark.parametrize('extra', [{}, {'subject': '', 'body': ''}], ids=['picker', 'empty-keys'])
@pytest.mark.parametrize('kind', ['invoice', 'quote'])
def test_a_hand_picked_send_is_the_same_email_as_a_normal_send(company, client, kind, extra):
    """The picker posts only the recipients and CC (no subject or text): the server builds the same email.

    Empty subject and text, as an older page posted them, mean the same.
    """
    _contact(company, 'kim@lotusbay.example.com', contact_type='Billing', is_primary=True)
    if kind == 'invoice':
        record, url = _invoice(company), '/api/v1/invoices/{}/send/'
        model = Invoice
    else:
        record, url = _quote(company), '/api/v1/quotes/{}/send/'
        model = Quote
    mail.outbox.clear()
    normal = _sent(client.post(url.format(record.pk), {}, format='json'))
    model.objects.filter(pk=record.pk).update(status='Draft')
    picked = _sent(client.post(url.format(record.pk), {
        'recipients': ['kim@lotusbay.example.com'], 'cc': [], **extra}, format='json'))
    assert normal == picked
    assert normal['to'] == ['kim@lotusbay.example.com']
    assert normal['attachments'] and normal['attachments'][0][0].endswith('.pdf')
