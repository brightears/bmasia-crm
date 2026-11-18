"""EmailLog.message_id must be the Message-ID that was actually sent.

For every sender (generic, quote, contract, invoice, receipt, manual
renewal) the outgoing message is built twice: once with the Message-ID
generation of the old code (Django's own, at send time) and once with the
fix. Apart from the Message-ID value the two are byte-identical; the fixed
header equals the stored EmailLog.message_id and uses the From domain.
All data is synthetic.
"""
import email.generator
import re
from datetime import date
from decimal import Decimal

import pytest
from django.http import HttpResponse

from crm_app.models import Company, Contact, Contract, EmailLog, Invoice, Quote
from crm_app.services import email_service
from crm_app.services.email_service import EmailService


pytestmark = pytest.mark.django_db

REAL_ASSIGN = email_service.assign_message_id

MESSAGE_ID_RE = re.compile(rb'^Message-ID: [^\r\n]*\r?\n', re.MULTILINE)


@pytest.fixture
def deterministic(monkeypatch, settings):
    """Fixed MIME boundaries, Date, tracking tokens and the old-style id."""
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    monkeypatch.setattr(email.generator.Generator, '_make_boundary',
                        classmethod(lambda cls, text=None: '===============SYNTHETIC=='))
    monkeypatch.setattr('django.core.mail.message.formatdate',
                        lambda localtime=False: 'Mon, 05 Jan 2099 09:00:00 -0000')
    monkeypatch.setattr('django.core.mail.message.make_msgid',
                        lambda domain=None: '<old-style-id@host.invalid>')
    monkeypatch.setattr('secrets.token_urlsafe', lambda n=32: 'synthetic-token')
    pdf = lambda self, request, pk=None: HttpResponse(b'%PDF-1.4 synthetic', content_type='application/pdf')
    from crm_app import views
    monkeypatch.setattr(views.QuoteViewSet, 'pdf', pdf)
    monkeypatch.setattr(views.ContractViewSet, 'pdf', pdf)
    monkeypatch.setattr(views.InvoiceViewSet, 'pdf', pdf)
    monkeypatch.setattr(views.InvoiceViewSet, 'receipt_pdf', pdf)
    return monkeypatch


@pytest.fixture
def records():
    company = Company.objects.create(name='Message Id Test Hotel')
    contact = Contact.objects.create(company=company, name='Pat Example', email='pat@lagoon.test')
    quote = Quote.objects.create(company=company, contact=contact, quote_number='TH-QT99001',
                                 valid_from=date(2099, 1, 1), valid_until=date(2099, 2, 1))
    contract = Contract.objects.create(
        company=company, contract_number='TH-CT99001', start_date=date(2099, 1, 1),
        end_date=date(2099, 12, 31), value=Decimal('100.00'), status='Sent', sent_date=date(2099, 1, 1),
    )
    invoice = Invoice.objects.create(
        company=company, contract=contract, invoice_number='INV-TH-2099-0001', issue_date=date(2099, 1, 1),
        due_date=date(2099, 2, 1), amount=Decimal('100'), total_amount=Decimal('100'),
        receipt_number='REC-TH-2099-0001', status='Paid', paid_date=date(2099, 1, 10),
    )
    return {'company': company, 'contact': contact, 'quote': quote, 'contract': contract,
            'invoice': invoice}


def _senders(r):
    service = EmailService()
    body = 'Synthetic body text.'
    return {
        'generic': lambda: service.send_email(
            to_email='pat@lagoon.test', subject='Synthetic subject', body_html='<p>Synthetic</p>',
            body_text=body, from_email='Sender Name <sender@ourco.example>', company=r['company'],
            contact=r['contact']),
        'quote': lambda: service.send_quote_email(r['quote'].pk, recipients=['pat@lagoon.test'],
                                                  subject='Quote', body=body),
        'contract': lambda: service.send_contract_email(r['contract'].pk, recipients=['pat@lagoon.test'],
                                                        subject='Contract', body=body),
        'invoice': lambda: service.send_invoice_email(r['invoice'].pk, recipients=['pat@lagoon.test'],
                                                      subject='Invoice', body=body),
        'receipt': lambda: service.send_receipt_email(r['invoice'].pk, recipients=['pat@lagoon.test'],
                                                      subject='Receipt', body=body),
        'renewal': lambda: service.send_manual_renewal_reminder(r['contract'].pk, recipients=['pat@lagoon.test'],
                                                                subject='Renewal', body=body),
    }


def _old_behaviour(msg, from_email):
    """What the code did before: no Message-ID until Django builds the message."""
    return ''


@pytest.mark.parametrize('name', ['generic', 'quote', 'contract', 'invoice', 'receipt', 'renewal'])
def test_stored_message_id_is_the_one_sent_and_nothing_else_changes(name, deterministic, records, mailoutbox):
    send = _senders(records)[name]

    deterministic.setattr(email_service, 'assign_message_id', _old_behaviour)
    ok, _ = send()
    assert ok, name
    # The generic sender puts the EmailLog's own (random) id in a header.
    before = mailoutbox[-1].message().as_bytes().replace(str(EmailLog.objects.get().pk).encode(), b'LOG')
    EmailLog.objects.all().delete()
    mailoutbox.clear()

    deterministic.setattr(email_service, 'assign_message_id', REAL_ASSIGN)
    ok, _ = send()
    assert ok, name
    sent = mailoutbox[-1]
    log = EmailLog.objects.get()
    after = sent.message().as_bytes().replace(str(log.pk).encode(), b'LOG')

    header = sent.message()['Message-ID']
    assert header and log.message_id == header
    from email.utils import parseaddr
    from_domain = parseaddr(sent.from_email)[1].rsplit('@', 1)[1]
    assert header.endswith(f'@{from_domain}>')
    assert b'old-style-id' in before and b'old-style-id' not in after
    assert MESSAGE_ID_RE.sub(b'Message-ID: X\n', before) == MESSAGE_ID_RE.sub(b'Message-ID: X\n', after)


def test_each_message_gets_its_own_id(deterministic, records, mailoutbox):
    service = EmailService()
    for _ in range(2):
        service.send_email(to_email='pat@lagoon.test', subject='s', body_html='<p>x</p>', body_text='x',
                           from_email='sender@ourco.example', company=records['company'],
                           contact=records['contact'])
        EmailLog.objects.update(tracking_token=None)
    ids = [m.message()['Message-ID'] for m in mailoutbox]
    assert len(set(ids)) == 2
    assert sorted(EmailLog.objects.values_list('message_id', flat=True)) == sorted(ids)


def test_assign_message_id_keeps_other_headers_and_their_order():
    from django.core.mail import EmailMultiAlternatives
    msg = EmailMultiAlternatives('s', 'b', 'Name <a@ourco.example>', ['pat@lagoon.test'])
    msg.extra_headers['X-BMAsia-Email-ID'] = 'quote_x'
    msg.extra_headers['List-Unsubscribe'] = '<https://example.test/u>'
    value = REAL_ASSIGN(msg, msg.from_email)
    assert list(msg.extra_headers) == ['Message-ID', 'X-BMAsia-Email-ID', 'List-Unsubscribe']
    assert msg.extra_headers['Message-ID'] == value and value.endswith('@ourco.example>')
    # Without a usable From the server's name is used, as Django did.
    msg2 = EmailMultiAlternatives('s', 'b', 'no-address', ['pat@lagoon.test'])
    assert REAL_ASSIGN(msg2, 'no-address').startswith('<')
