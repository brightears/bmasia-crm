"""A mail error chained to another exception never reaches a log, a stored row or a reply.

``raise X from smtp_error`` (``__cause__``) and an error raised while handling one
(``__context__``) both carry the mail server's reply; Python's traceback formatting would
print it. crm_app/services/exception_safety.py treats any chain with a mail link as
mail-tainted. The fake server's 535 reply contains a marker; nothing connects anywhere.
"""
import logging
import smtplib
import traceback
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.http import HttpResponse
from rest_framework.test import APIClient

from crm_app.models import Company, Contact, Contract, EmailLog, Invoice, Quote, User
from crm_app.services import exception_safety as es
from crm_app.services.email_service import EmailService, exception_text

MARKER = 'chained-pass-marker-9c1'


def _mail_error():
    return smtplib.SMTPAuthenticationError(535, f'5.7.8 login rejected for pass {MARKER}'.encode())


def _raise_mail():
    raise _mail_error()


# --- the kinds of chain ---------------------------------------------------------------------

def explicit(*args, **kwargs):
    try:
        _raise_mail()
    except smtplib.SMTPException as err:
        raise RuntimeError('send step broke') from err


def implicit(*args, **kwargs):
    try:
        _raise_mail()
    except smtplib.SMTPException:
        raise AttributeError("'NoneType' object has no attribute 'close'")


def three_deep(*args, **kwargs):
    try:
        try:
            _raise_mail()
        except smtplib.SMTPException as err:
            raise ValueError('middle link') from err
    except ValueError as middle:
        raise RuntimeError('outer link') from middle


def cycle(*args, **kwargs):
    outer = RuntimeError('outer in a cycle')
    middle = ValueError('middle in a cycle')
    mail = _mail_error()
    outer.__cause__ = middle
    middle.__context__ = mail
    mail.__context__ = outer  # a cycle back to the start
    raise outer


def embedded(*args, **kwargs):
    try:
        _raise_mail()
    except smtplib.SMTPException as err:
        raise RuntimeError(f'send failed: {err}') from err


def suppressed(*args, **kwargs):
    try:
        _raise_mail()
    except smtplib.SMTPException:
        raise RuntimeError('replaced on purpose') from None


def grouped(*args, **kwargs):
    raise ExceptionGroup('several sends failed', [ValueError('other'), _mail_error()])


CHAINS = {'explicit': explicit, 'implicit': implicit, 'three_deep': three_deep, 'cycle': cycle,
          'embedded': embedded, 'grouped': grouped}


def _caught(maker):
    try:
        maker()
    except BaseException as exc:  # noqa: BLE001 - the test inspects any exception
        return exc
    raise AssertionError('no exception')


def _everything_in(record):
    formatted = logging.Formatter('%(message)s').format(record)
    return '\n'.join([formatted, record.getMessage(), str(record.args), str(record.exc_text),
                      str(record.stack_info), str(vars(record))])


def _assert_no_marker(caplog, *texts):
    for record in caplog.records:
        assert MARKER not in _everything_in(record), record.getMessage()[:200]
    for text in texts:
        assert MARKER not in str(text)
    for row in EmailLog.objects.all():
        assert MARKER not in (row.error_message or '')


# --- the shared rule ------------------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(CHAINS))
def test_every_kind_of_chain_is_mail_tainted(name):
    exc = _caught(CHAINS[name])
    assert es.mail_link(exc) is not None
    assert MARKER not in es.describe_exception(exc)
    assert MARKER not in es.own_frames_text(exc)
    assert MARKER not in es.safe_exception_message(exc)
    assert MARKER not in exception_text(exc)


def test_a_suppressed_context_is_not_a_link():
    exc = _caught(suppressed)
    assert es.mail_link(exc) is None
    assert MARKER not in ''.join(traceback.format_exception(exc))  # Python does not print it either


def test_a_cycle_ends_and_visits_each_link_once():
    exc = _caught(cycle)
    chain = es.exception_chain(exc)
    assert len(chain) == 3 and len({id(link) for link in chain}) == 3


def test_an_outer_message_that_repeats_the_mail_error_becomes_its_type():
    exc = _caught(embedded)
    assert MARKER in str(exc)
    assert es.safe_exception_message(exc) == 'RuntimeError'
    assert es.safe_exception_message(_caught(explicit)) == 'send step broke'


@pytest.mark.parametrize('name', sorted(CHAINS))
def test_log_exception_keeps_the_bug_frames_and_never_the_chain(name, caplog):
    exc = _caught(CHAINS[name])
    with caplog.at_level(logging.DEBUG):
        es.log_exception(logging.getLogger('crm_app.test_chain'), 'Context', exc)
    (record,) = caplog.records
    assert record.exc_info is None and not record.stack_info
    text = record.getMessage()
    assert 'Traceback (most recent call last, chained exceptions not shown)' in text
    assert 'while handling SMTPAuthenticationError (SMTP code 535)' in text
    assert f'in {CHAINS[name].__name__}' in text or name == 'grouped'
    _assert_no_marker(caplog)


def test_log_exception_without_a_mail_link_keeps_the_full_traceback(caplog):
    exc = _caught(suppressed)
    with caplog.at_level(logging.DEBUG):
        es.log_exception(logging.getLogger('crm_app.test_chain'), 'Context', exc)
    (record,) = caplog.records
    assert record.exc_info[0] is RuntimeError
    _assert_no_marker(caplog)


# --- through every sender -------------------------------------------------------------------

@pytest.fixture
def records(monkeypatch, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    pdf = lambda self, request, pk=None: HttpResponse(b'%PDF-1.4 synthetic', content_type='application/pdf')
    from crm_app import views
    for viewset, name in ((views.QuoteViewSet, 'pdf'), (views.ContractViewSet, 'pdf'),
                          (views.InvoiceViewSet, 'pdf'), (views.InvoiceViewSet, 'receipt_pdf')):
        monkeypatch.setattr(viewset, name, pdf)
    company = Company.objects.create(name='Chain Test Hotel')
    contact = Contact.objects.create(company=company, name='Pat Example', email='pat@lagoon.test')
    quote = Quote.objects.create(company=company, contact=contact, quote_number='TH-QT94001',
                                 valid_from=date(2099, 1, 1), valid_until=date(2099, 2, 1))
    contract = Contract.objects.create(company=company, contract_number='TH-CT94001', start_date=date(2099, 1, 1),
                                       end_date=date(2099, 12, 31), value=Decimal('100'), status='Sent',
                                       sent_date=date(2099, 1, 1))
    invoice = Invoice.objects.create(company=company, contract=contract, invoice_number='INV-TH-2099-0941',
                                     issue_date=date(2099, 1, 1), due_date=date(2099, 2, 1), amount=Decimal('100'),
                                     total_amount=Decimal('100'), receipt_number='REC-TH-2099-0941', status='Paid',
                                     paid_date=date(2099, 1, 10))
    return SimpleNamespace(company=company, contact=contact, quote=quote, contract=contract, invoice=invoice)


def _senders(r, request=None):
    service = EmailService()
    return {
        'generic': lambda: service.send_email(to_email='pat@lagoon.test', subject='s', body_html='<p>s</p>',
                                              body_text='s', from_email='sender@ourco.example', company=r.company,
                                              contact=r.contact),
        'quote': lambda: service.send_quote_email(r.quote.pk, recipients=['pat@lagoon.test'], subject='Q', body='b',
                                                  request=request),
        'contract': lambda: service.send_contract_email(r.contract.pk, recipients=['pat@lagoon.test'], subject='C',
                                                        body='b', request=request),
        'invoice': lambda: service.send_invoice_email(r.invoice.pk, recipients=['pat@lagoon.test'], subject='I',
                                                      body='b', request=request),
        'receipt': lambda: service.send_receipt_email(r.invoice.pk, recipients=['pat@lagoon.test'], subject='R',
                                                      body='b', request=request),
        'renewal': lambda: service.send_manual_renewal_reminder(r.contract.pk, recipients=['pat@lagoon.test'],
                                                                subject='R', body='b', request=request),
    }


SENDERS = ['generic', 'quote', 'contract', 'invoice', 'receipt', 'renewal']


@pytest.mark.parametrize('chain', sorted(CHAINS))
@pytest.mark.parametrize('sender', SENDERS)
def test_a_chained_mail_error_at_the_send_leaks_nowhere(sender, chain, records, caplog, monkeypatch):
    monkeypatch.setattr('django.core.mail.message.EmailMessage.send', CHAINS[chain])
    with caplog.at_level(logging.DEBUG):
        ok, message = _senders(records)[sender]()
    assert ok is False
    _assert_no_marker(caplog, message)


@pytest.mark.parametrize('chain', sorted(CHAINS))
@pytest.mark.parametrize('sender', ['quote', 'contract', 'invoice', 'receipt'])
def test_a_chained_mail_error_in_the_user_connection_leaks_nowhere(sender, chain, records, caplog, monkeypatch):
    user = User.objects.create_user(username='chain-sender', email='chain-sender@ourco.example',
                                    password='test-only-password', role='Sales',
                                    smtp_email='chain-sender@ourco.example', smtp_password='plain-fixture-pass')
    request = SimpleNamespace(user=user, META={}, method='POST', path='/x/')
    monkeypatch.setattr('django.core.mail.message.EmailMessage.send', lambda *a, **k: 1)
    with caplog.at_level(logging.DEBUG), mock.patch('django.core.mail.get_connection', side_effect=CHAINS[chain]):
        _senders(records, request)[sender]()
    _assert_no_marker(caplog)
    assert any('Failed to create user SMTP connection' in r.getMessage() for r in caplog.records)


# --- the DRF handler (crm_app/api_errors.py) ------------------------------------------------

def test_failure_recording_that_raises_after_a_mail_error_leaks_nowhere(records, caplog, monkeypatch):
    """The send fails with the echo reply, then recording the failure raises: the error reaches
    DRF's handler with the mail error as its context."""
    monkeypatch.setattr('django.core.mail.message.EmailMessage.send', lambda *a, **k: _raise_mail())

    def recording_breaks(self, error_message):
        raise RuntimeError('could not record the failure')

    monkeypatch.setattr(EmailLog, 'mark_as_failed', recording_breaks)
    staff = User.objects.create_user(username='chain-staff', password='test-only-password', role='Admin',
                                     is_staff=True, is_superuser=True)
    api = APIClient()
    api.force_authenticate(staff)
    with caplog.at_level(logging.DEBUG):
        response = api.post(f'/api/v1/invoices/{records.invoice.pk}/send/',
                            {'recipients': ['pat@lagoon.test'], 'subject': 'S', 'body': 'B'}, format='json')
    assert response.status_code == 500
    assert any('could not record the failure' in r.getMessage() for r in caplog.records)
    _assert_no_marker(caplog, response.data)


def test_internal_error_text_follows_the_same_rule(caplog):
    from crm_app.api_errors import internal_error_text
    exc = _caught(implicit)
    request = SimpleNamespace(META={}, method='POST', path='/x/')
    with caplog.at_level(logging.DEBUG):
        text = internal_error_text(request, exc)
    _assert_no_marker(caplog, text)
    plain_bug = _caught(lambda: 1 + 'one')
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        internal_error_text(request, plain_bug)
    assert caplog.records[0].exc_info[0] is TypeError  # a bug keeps its full traceback


def test_receipt_failure_text_follows_the_same_rule(records, caplog):
    from crm_app.services.invoice_payments import receipt_email_failure_text
    with caplog.at_level(logging.DEBUG):
        text = receipt_email_failure_text(None, records.invoice, _caught(explicit))
    _assert_no_marker(caplog, text)


# --- levels at the two degraded-but-sent sites ----------------------------------------------

def test_smtp_connection_lookup_levels(records, caplog):
    User.objects.create_user(username='lookup-user', email='lookup@ourco.example', password='test-only-password',
                             smtp_email='lookup@ourco.example', smtp_password='plain-fixture-pass')
    service = EmailService()
    for side_effect, level in ((_mail_error(), logging.WARNING), (TypeError('a bug'), logging.ERROR)):
        caplog.clear()
        with caplog.at_level(logging.DEBUG), mock.patch('django.core.mail.get_connection', side_effect=side_effect):
            assert service._get_smtp_connection_for_sender('lookup@ourco.example') is None
        (record,) = [r for r in caplog.records if 'Error getting SMTP connection' in r.getMessage()]
        assert record.levelno == level
    _assert_no_marker(caplog)


def test_attachment_step_levels(records, caplog, monkeypatch):
    from crm_app.models import DocumentAttachment
    monkeypatch.setattr('django.core.mail.message.EmailMessage.send', lambda *a, **k: 1)
    attachment = SimpleNamespace(name='fixture.pdf', file=SimpleNamespace(path='/nonexistent'))
    for side_effect, level in ((_mail_error(), logging.WARNING), (TypeError('a bug'), logging.ERROR)):
        caplog.clear()
        with caplog.at_level(logging.DEBUG), \
                mock.patch('django.core.mail.EmailMultiAlternatives.attach_file', side_effect=side_effect), \
                mock.patch.object(EmailLog, 'attachments', create=True):
            EmailService().send_email(to_email='pat@lagoon.test', subject='s', body_html='<p>s</p>', body_text='s',
                                      from_email='sender@ourco.example', company=records.company,
                                      contact=records.contact, attachments=[attachment])
        matches = [r for r in caplog.records if 'Failed to attach file' in r.getMessage()]
        assert matches and matches[0].levelno == level
    _assert_no_marker(caplog)
    assert DocumentAttachment  # the real model exists; the attachment above is a stand-in
