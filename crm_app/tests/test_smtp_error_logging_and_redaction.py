"""Mail errors are logged without the mail server's raw reply; audit redaction covers nested keys;
audit_secret_scan counts old rows (names and counts only).

A fake mail server echoes the password in its reply: nothing may carry it to a log, a reply
or an email log row. Every value is invented; nothing connects to a mail server.
"""
import io
import logging
import smtplib
from unittest import mock

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from crm_app.models import AuditLog, User

PASSWORD = 'echoed-app-pass-fixture'


def _echoing_failure():
    return smtplib.SMTPAuthenticationError(535, f'5.7.8 rejected login {PASSWORD} for sender'.encode())


@pytest.fixture
def sender():
    return User.objects.create_user(
        username='echo-fixture', email='echo-fixture@example.com', password='test-only-password',
        role='Admin', is_staff=True, is_superuser=True,
        smtp_email='echo-fixture@example.com', smtp_password=PASSWORD,
    )


def _everything_logged(caplog):
    import traceback
    parts = []
    for record in caplog.records:
        parts.append(record.getMessage())
        if record.exc_info:
            parts.append(''.join(traceback.format_exception(*record.exc_info)))
    return '\n'.join(parts)


@pytest.mark.parametrize('route', ['test_smtp', 'test_smtp_send'])
def test_refused_login_logs_type_and_code_only(route, sender, caplog):
    client = APIClient()
    client.force_authenticate(sender)
    url = '/api/v1/users/test_smtp/' if route == 'test_smtp' else f'/api/v1/users/{sender.pk}/test_smtp_send/'
    with caplog.at_level(logging.DEBUG), mock.patch('smtplib.SMTP') as smtp:
        smtp.return_value.login.side_effect = _echoing_failure()
        response = client.post(url, {'to_email': 'to@example.com'}, format='json')
    assert response.status_code == 400
    logged = _everything_logged(caplog)
    assert PASSWORD not in logged
    assert PASSWORD not in str(response.data)
    assert 'SMTPAuthenticationError (SMTP code 535): the mail server did not accept the login' in logged


def test_describe_mail_exception_never_includes_the_reply():
    from crm_app.api_errors import describe_mail_exception
    text = describe_mail_exception(_echoing_failure())
    assert text == 'SMTPAuthenticationError (SMTP code 535): the mail server did not accept the login'
    assert describe_mail_exception(smtplib.SMTPRecipientsRefused({'x@example.com': (550, PASSWORD.encode())})) == \
        'SMTPRecipientsRefused: the mail server refused the recipients'
    assert describe_mail_exception(ConnectionRefusedError(PASSWORD)) == \
        'ConnectionRefusedError: could not connect to the mail server'
    assert describe_mail_exception(ValueError('not mail')) is None


def test_mail_failure_text_logs_a_mail_exception_without_its_reply(caplog):
    from crm_app.api_errors import mail_failure_text
    with caplog.at_level(logging.DEBUG):
        reply = mail_failure_text(None, 'Failed to send email', _echoing_failure())
    assert PASSWORD not in _everything_logged(caplog) and PASSWORD not in reply


def test_a_failed_send_keeps_the_reply_out_of_the_log_and_the_email_log(sender, caplog):
    from crm_app.models import Company, EmailLog
    from crm_app.services.email_service import EmailService
    company = Company.objects.create(name='Echo Fixture Resort', country='Thailand')
    with caplog.at_level(logging.DEBUG), \
            mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=_echoing_failure()):
        ok, message = EmailService().send_email(
            to_email='to@example.com', subject='s', body_html='<p>b</p>', body_text='b',
            from_email=sender.smtp_email, company=company,
        )
    assert ok is False
    assert PASSWORD not in message
    assert PASSWORD not in _everything_logged(caplog)
    rows = list(EmailLog.objects.all())
    assert rows
    for row in rows:
        assert PASSWORD not in (row.error_message or '')


# --- audit redaction ------------------------------------------------------------------------

def test_redaction_reaches_nested_keys():
    from crm_app.views import redact_secret_changes
    changes = {
        'smtp_password': {'old': 'a', 'new': 'b'},
        'settings': {'old': {'api_key': 'k1', 'name': 'x'}, 'new': {'api_key': 'k2', 'name': 'y'}},
        'items': {'old': [{'token': 't1'}], 'new': [{'token': 't2', 'qty': 1}]},
        'name': {'old': 'A', 'new': 'B'},
    }
    out = redact_secret_changes(changes)
    assert out['smtp_password'] == {'old': '[redacted]', 'new': '[redacted]'}
    assert out['settings'] == {'old': {'api_key': '[redacted]', 'name': 'x'},
                               'new': {'api_key': '[redacted]', 'name': 'y'}}
    assert out['items'] == {'old': [{'token': '[redacted]'}], 'new': [{'token': '[redacted]', 'qty': 1}]}
    assert out['name'] == {'old': 'A', 'new': 'B'}


def test_admin_form_class_has_no_stored_password_field():
    from crm_app.admin import UserAdminChangeForm
    assert 'smtp_password' not in UserAdminChangeForm.base_fields
    assert 'smtp_password' not in UserAdminChangeForm().fields


def test_audit_secret_scan_counts_names_only_and_writes_nothing(sender):
    common = {'user': sender, 'action': 'UPDATE', 'record_id': '1'}
    AuditLog.objects.create(model_name='User', changes={'smtp_password': {'old': PASSWORD, 'new': 'x'}}, **common)
    AuditLog.objects.create(model_name='User', changes={'smtp_password': {'old': '[redacted]', 'new': '[redacted]'}},
                            **common)
    AuditLog.objects.create(model_name='Company', changes={'cfg': {'old': {'api_key': PASSWORD}, 'new': {}}},
                            additional_data={'token': PASSWORD}, **common)
    AuditLog.objects.create(model_name='Company', changes={'name': {'old': 'A', 'new': 'B'}}, **common)
    before = list(AuditLog.objects.order_by('pk').values_list('changes', 'additional_data'))

    out = io.StringIO()
    call_command('audit_secret_scan', stdout=out)
    text = out.getvalue()
    assert 'Audit rows scanned: 4' in text
    assert 'Rows with a secret-like key holding a value: 2' in text
    assert '  User smtp_password: 1' in text
    assert '  Company cfg.old.api_key: 1' in text
    assert '  Company additional_data.token: 1' in text
    assert PASSWORD not in text
    assert list(AuditLog.objects.order_by('pk').values_list('changes', 'additional_data')) == before
