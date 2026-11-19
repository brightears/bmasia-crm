"""Every send path turns a mail error into text through one function: no raw mail server reply
in a log record, an EmailLog row, a sequence execution or a reply.

The fake mail server answers every send with a 535 whose text contains a password marker
(a server that echoes what it was sent). A source check keeps new except blocks honest.
All data is invented; nothing connects to a mail server.
"""
import ast
import logging
import smtplib
import traceback
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from django.http import HttpResponse
from django.utils import timezone

from crm_app.models import (
    Company, Contact, Contract, EmailLog, EmailSequence, EmailTemplate, Invoice, Quote,
    SequenceEnrollment, SequenceStep, SequenceStepExecution, User,
)
from crm_app.services.email_service import EmailService, exception_text

MARKER = 'echoed-pass-marker-7f3'
REPO = Path(__file__).resolve().parents[2]
CHECKED_MODULES = [
    REPO / 'crm_app' / 'services' / 'email_service.py',
    REPO / 'crm_app' / 'management' / 'commands' / 'send_task_digest.py',
]


def _echo(*args, **kwargs):
    raise smtplib.SMTPAuthenticationError(535, f'5.7.8 login rejected for pass {MARKER}'.encode())


def _logged(caplog):
    parts = []
    for record in caplog.records:
        parts.append(record.getMessage())
        if record.exc_info:
            parts.append(''.join(traceback.format_exception(*record.exc_info)))
    return '\n'.join(parts)


def _assert_clean(caplog, *texts):
    assert MARKER not in _logged(caplog)
    for text in texts:
        assert MARKER not in str(text)
    for row in EmailLog.objects.all():
        assert MARKER not in (row.error_message or '')


@pytest.fixture
def echo_server(monkeypatch, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    monkeypatch.setattr('django.core.mail.message.EmailMessage.send', _echo)
    pdf = lambda self, request, pk=None: HttpResponse(b'%PDF-1.4 synthetic', content_type='application/pdf')
    from crm_app import views
    for viewset, name in ((views.QuoteViewSet, 'pdf'), (views.ContractViewSet, 'pdf'),
                          (views.InvoiceViewSet, 'pdf'), (views.InvoiceViewSet, 'receipt_pdf')):
        monkeypatch.setattr(viewset, name, pdf)
    return monkeypatch


@pytest.fixture
def records():
    company = Company.objects.create(name='Echo Test Hotel')
    contact = Contact.objects.create(company=company, name='Pat Example', email='pat@lagoon.test')
    quote = Quote.objects.create(company=company, contact=contact, quote_number='TH-QT98001',
                                 valid_from=date(2099, 1, 1), valid_until=date(2099, 2, 1))
    contract = Contract.objects.create(
        company=company, contract_number='TH-CT98001', start_date=date(2099, 1, 1),
        end_date=date(2099, 12, 31), value=Decimal('100.00'), status='Sent', sent_date=date(2099, 1, 1),
    )
    invoice = Invoice.objects.create(
        company=company, contract=contract, invoice_number='INV-TH-2099-0981', issue_date=date(2099, 1, 1),
        due_date=date(2099, 2, 1), amount=Decimal('100'), total_amount=Decimal('100'),
        receipt_number='REC-TH-2099-0981', status='Paid', paid_date=date(2099, 1, 10),
    )
    return SimpleNamespace(company=company, contact=contact, quote=quote, contract=contract, invoice=invoice)


def _senders(r, request=None):
    service = EmailService()
    body = 'Synthetic body text.'
    return {
        'generic': lambda: service.send_email(
            to_email='pat@lagoon.test', subject='s', body_html='<p>s</p>', body_text=body,
            from_email='sender@ourco.example', company=r.company, contact=r.contact),
        'quote': lambda: service.send_quote_email(r.quote.pk, recipients=['pat@lagoon.test'], subject='Q',
                                                  body=body, request=request),
        'contract': lambda: service.send_contract_email(r.contract.pk, recipients=['pat@lagoon.test'],
                                                        subject='C', body=body, request=request),
        'invoice': lambda: service.send_invoice_email(r.invoice.pk, recipients=['pat@lagoon.test'],
                                                      subject='I', body=body, request=request),
        'receipt': lambda: service.send_receipt_email(r.invoice.pk, recipients=['pat@lagoon.test'],
                                                      subject='R', body=body, request=request),
        'renewal': lambda: service.send_manual_renewal_reminder(r.contract.pk, recipients=['pat@lagoon.test'],
                                                                subject='Renewal', body=body, request=request),
    }


SENDERS = ['generic', 'quote', 'contract', 'invoice', 'receipt', 'renewal']


@pytest.mark.parametrize('name', SENDERS)
def test_every_sender_keeps_the_reply_out_of_logs_rows_and_replies(name, echo_server, records, caplog):
    with caplog.at_level(logging.DEBUG):
        ok, message = _senders(records)[name]()
    assert ok is False
    _assert_clean(caplog, message)
    assert 'SMTPAuthenticationError (SMTP code 535)' in _logged(caplog)


@pytest.mark.parametrize('name', ['quote', 'contract', 'invoice', 'receipt'])
def test_failed_user_smtp_connection_is_logged_without_the_reply(name, echo_server, records, caplog):
    user = User.objects.create_user(username='echo-sender', email='echo-sender@ourco.example',
                                    password='test-only-password', role='Sales',
                                    smtp_email='echo-sender@ourco.example', smtp_password='plain-fixture-pass')
    request = SimpleNamespace(user=user, META={}, method='POST', path='/x/')
    with caplog.at_level(logging.DEBUG), mock.patch('django.core.mail.get_connection', side_effect=_echo):
        ok, message = _senders(records, request)[name]()
    assert ok is False
    _assert_clean(caplog, message)
    assert 'Failed to create user SMTP connection: SMTPAuthenticationError (SMTP code 535)' in _logged(caplog)


@pytest.mark.parametrize('name', ['quote', 'contract', 'invoice', 'receipt'])
def test_document_send_replies_keep_their_shape(name, echo_server, records):
    ok, message = _senders(records)[name]()
    assert ok is False
    summary = {
        'quote': 'Failed to send the quote to any recipient',
        'contract': 'Failed to send the contract to any recipient',
        'invoice': 'Failed to send the invoice to any recipient',
        'receipt': 'Failed to send the receipt to any recipient',
    }[name]
    assert message.startswith(f'{summary}. Reference: ')


def test_manual_renewal_reply_is_unchanged(echo_server, records):
    assert _senders(records)['renewal']() == (False, 'Failed to send renewal reminder to any recipients')


def test_sequence_step_stores_no_reply(echo_server, records, caplog):
    owner = User.objects.create_user(username='seq-owner', password='test-only-password', role='Admin')
    template = EmailTemplate.objects.create(name='Echo sequence step', template_type='payment_reminder',
                                            subject='Hello', body_text='Hello', body_html='<p>Hello</p>')
    sequence = EmailSequence.objects.create(name='Echo sequence', created_by=owner, sequence_type='manual')
    step = SequenceStep.objects.create(sequence=sequence, step_number=1, name='Step 1', email_template=template)
    enrollment = SequenceEnrollment.objects.create(sequence=sequence, contact=records.contact,
                                                   company=records.company)
    execution = SequenceStepExecution.objects.create(enrollment=enrollment, step=step,
                                                     scheduled_for=timezone.now() - timedelta(minutes=1))
    with caplog.at_level(logging.DEBUG):
        assert EmailService().execute_sequence_step(execution.id) is False
    execution.refresh_from_db()
    _assert_clean(caplog, execution.error_message)


def test_follow_up_loops_log_no_reply(echo_server, records, caplog):
    """The follow-up senders catch errors around send_email; their log lines go through the same function."""
    service = EmailService()
    with caplog.at_level(logging.DEBUG), mock.patch.object(EmailService, 'send_email', side_effect=_echo):
        for runner in (service.send_quote_followups, service.send_contract_followups,
                       service.send_renewal_reminders, service.send_payment_reminders,
                       service.send_quarterly_checkins):
            try:
                runner()
            except Exception as exc:  # a loop that lets the error out must not carry the reply either
                assert MARKER not in exception_text(exc)
    assert MARKER not in _logged(caplog)


def test_exception_text_rules():
    assert exception_text(smtplib.SMTPAuthenticationError(535, MARKER.encode())) == \
        'SMTPAuthenticationError (SMTP code 535): the mail server did not accept the login'
    refused = smtplib.SMTPRecipientsRefused({
        'a.person@lagoon.test': (550, f'no such user {MARKER}'.encode()),
        'b@other.example': (553, b'relay denied'),
        'odd-address': ('x', b'?'),
    })
    text = exception_text(refused)
    assert text == ('SMTPRecipientsRefused: the mail server refused 3 recipient(s) '
                    '(lagoon.test: 550; other.example: 553; unknown domain: no code)')
    assert MARKER not in text and 'a.person' not in text
    assert exception_text(ValueError('a plain message')) == 'a plain message'


ALLOWED_LOGGER = 'log_caught_exception'


def _misuses_in_source(source, filename='<sample>'):
    """(line, what) for every way this module could turn an exception into text or a traceback
    other than exception_text(<name>) or log_caught_exception(<context>, <name>[, level]).

    Anywhere outside the body of log_caught_exception (the one allowed logging site):
    exc_info= or stack_info= keywords, logger.exception(), any call on the traceback module,
    sys.exc_info(). In every except block: a bare except, and any use of the caught name other
    than as the argument of exception_text() or the exception argument of log_caught_exception().
    """
    tree = ast.parse(source, filename=filename)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    allowed_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == ALLOWED_LOGGER:
            allowed_nodes.update(ast.walk(node))

    problems = []
    for node in ast.walk(tree):
        if node in allowed_nodes or not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg in ('exc_info', 'stack_info'):
                problems.append((node.lineno, kw.arg))
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == 'exception':
                problems.append((node.lineno, 'logger.exception'))
            if isinstance(func.value, ast.Name) and func.value.id == 'traceback':
                problems.append((node.lineno, f'traceback.{func.attr}'))
            if isinstance(func.value, ast.Name) and func.value.id == 'sys' and func.attr == 'exc_info':
                problems.append((node.lineno, 'sys.exc_info'))
        if isinstance(func, ast.Name) and func.id in ('format_exc', 'print_exc', 'format_exception', 'exc_info'):
            problems.append((node.lineno, func.id))

    log_methods = {'debug', 'info', 'warning', 'warn', 'error', 'critical', 'log', 'exception'}
    for handler in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
        if handler.type is None:
            problems.append((handler.lineno, 'bare except'))
        if not handler.name:
            continue
        # The log call of a handler must be the helper: a logger call carrying exception_text()
        # would quietly drop a bug's traceback again.
        calls_helper = False
        for node in ast.walk(handler):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Name) and func.id == ALLOWED_LOGGER and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Name) and node.args[1].id == handler.name):
                calls_helper = True
            if isinstance(func, ast.Attribute) and func.attr in log_methods:
                for inner in ast.walk(node):
                    if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                            and inner.func.id == 'exception_text'):
                        problems.append((node.lineno, f'logger.{func.attr} with exception_text(); use {ALLOWED_LOGGER}()'))
                        break
        if not calls_helper and not any(isinstance(n, ast.Raise) for n in ast.walk(handler)):
            problems.append((handler.lineno, f'except block neither calls {ALLOWED_LOGGER}() nor re-raises'))
        for node in ast.walk(handler):
            if isinstance(node, ast.Name) and node.id == handler.name and isinstance(node.ctx, ast.Load):
                parent = parents.get(node)
                in_text = (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                           and parent.func.id == 'exception_text' and parent.args == [node])
                in_logger = (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                             and parent.func.id == ALLOWED_LOGGER and len(parent.args) >= 2
                             and parent.args[1] is node)
                if not (in_text or in_logger):
                    problems.append((node.lineno, f'{handler.name} used outside exception_text()/{ALLOWED_LOGGER}()'))
    return problems


def _handler_misuses(path):
    return _misuses_in_source(path.read_text(), str(path))


@pytest.mark.parametrize('path', CHECKED_MODULES, ids=lambda p: p.name)
def test_no_except_block_turns_an_exception_into_text_another_way(path):
    assert _handler_misuses(path) == []


SAMPLE_BLOCKS = [
    ('logger.error(f"failed: {exception_text(e)}")', True),
    ('msg = exception_text(e)', True),  # builds text but never logs through the helper
    ('raise', False),
    ('msg = exception_text(e); log_caught_exception("ctx", e)', False),
    ('x = str(e)', True),
    ('y = f"{e}"', True),
    ('z = repr(e)', True),
    ('log.error("%s", e, exc_info=True)', True),
    ('log.error("x", stack_info=True)', True),
    ('t = traceback.format_exc()', True),
    ('traceback.print_exc()', True),
    ('t = traceback.format_exception(e)', True),
    ('t = sys.exc_info()', True),
    ('log.exception("x")', True),
    ('log_caught_exception(e, "wrong order")', True),
    ('log_caught_exception("context", e)', False),
    ('log_caught_exception(f"context {x}", e, mail_level=logging.WARNING)', False),
]


@pytest.mark.parametrize('body,flagged', SAMPLE_BLOCKS)
def test_the_source_check_catches_the_patterns_it_must(body, flagged):
    source = f'try:\n    pass\nexcept Exception as e:\n    {body}\n'
    assert bool(_misuses_in_source(source)) is flagged


def test_the_source_check_refuses_a_bare_except_and_allows_the_helper_body():
    assert _misuses_in_source('try:\n    pass\nexcept:\n    pass\n') == [(3, 'bare except')]
    helper = ('def log_caught_exception(context, exc, level=0):\n'
              '    logger.log(level, "%s", context, exc_info=(type(exc), exc, exc.__traceback__))\n')
    assert _misuses_in_source(helper) == []
    assert _misuses_in_source(helper.replace('log_caught_exception', 'some_other_helper')) == [(2, 'exc_info')]


# --- bug evidence: non-mail errors keep type and traceback, mail errors never ---------------

@pytest.mark.parametrize('name', SENDERS)
def test_a_mail_error_is_logged_without_any_traceback(name, echo_server, records, caplog):
    with caplog.at_level(logging.DEBUG):
        _senders(records)[name]()
    mail_records = [r for r in caplog.records if 'SMTPAuthenticationError' in r.getMessage()]
    assert mail_records
    assert all(r.exc_info is None and not r.stack_info for r in caplog.records if r.name.startswith('crm_app'))
    assert MARKER not in _logged(caplog)


@pytest.mark.parametrize('name,viewset,attr', [
    ('quote', 'QuoteViewSet', 'pdf'),
    ('contract', 'ContractViewSet', 'pdf'),
    ('invoice', 'InvoiceViewSet', 'pdf'),
    ('receipt', 'InvoiceViewSet', 'receipt_pdf'),
])
def test_a_bug_in_the_pdf_step_is_logged_with_type_message_and_traceback(name, viewset, attr, echo_server, records,
                                                                        caplog):
    from crm_app import views

    def broken(self, request, pk=None):
        return 1 + 'one'  # a TypeError, the kind of bug that needs its traceback

    echo_server.setattr(getattr(views, viewset), attr, broken)
    with caplog.at_level(logging.DEBUG):
        ok, message = _senders(records)[name]()
    assert ok is False
    assert message.startswith('Failed to generate the ')  # the reply is unchanged: summary and reference
    assert 'Reference: ' in message and 'TypeError' not in message
    bug = [r for r in caplog.records if r.exc_info and r.exc_info[0] is TypeError]
    assert len(bug) == 1
    text = bug[0].getMessage()
    assert 'TypeError: unsupported operand type(s)' in text
    formatted = ''.join(traceback.format_exception(*bug[0].exc_info))
    assert 'in broken' in formatted and "1 + 'one'" in formatted
    assert MARKER not in _logged(caplog)


def test_log_caught_exception_refuses_a_traceback_for_a_mail_error(caplog):
    from crm_app.services.email_service import log_caught_exception
    try:
        _echo()
    except smtplib.SMTPException as exc:
        with caplog.at_level(logging.DEBUG):
            log_caught_exception('Context', exc)
    (record,) = caplog.records
    assert record.exc_info is None
    assert record.getMessage() == 'Context: SMTPAuthenticationError (SMTP code 535): the mail server did not accept the login'
    try:
        raise TypeError('a bug')
    except TypeError as exc:
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            log_caught_exception('Context', exc, mail_level=logging.WARNING)
    (record,) = caplog.records
    assert record.levelno == logging.ERROR and record.exc_info[0] is TypeError  # a bug is always ERROR here
    assert record.getMessage() == 'Context: TypeError: a bug'
