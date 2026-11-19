"""A stored SMTP app password never goes back out: not to the admin page, the API, audit rows or logs.

Every value below is invented. No test connects to a mail server.
"""
import logging
import smtplib
from unittest import mock

import pytest
from django.contrib.admin.models import LogEntry
from django.urls import reverse
from rest_framework.test import APIClient

from crm_app.models import AuditLog, User

STORED = 'stored-app-pass-fixture-1'
NEW = 'new-app-pass-fixture-2'


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username='adm-fixture', email='adm-fixture@example.com', password='test-only-password',
        role='Admin', is_staff=True, is_superuser=True,
    )


@pytest.fixture
def sender():
    return User.objects.create_user(
        username='sender-fixture', email='sender-fixture@example.com', password='test-only-password',
        role='Sales', smtp_email='sender-fixture@example.com', smtp_password=STORED,
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def api(admin_user):
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


def _change_url(user):
    return reverse('admin:crm_app_user_change', args=[user.pk])


def _form_data(admin_client, user, **extra):
    """The change form's current values, as a browser would post them back."""
    response = admin_client.get(_change_url(user))
    form = response.context['adminform'].form
    data = {}
    for name, field in form.fields.items():
        value = form.initial.get(name, field.initial)
        if value is None or name in ('password',):
            continue
        if isinstance(value, bool):
            if value:
                data[name] = 'on'
            continue
        if isinstance(value, (list, tuple)):
            data[name] = [getattr(v, 'pk', v) for v in value]
            continue
        data[name] = getattr(value, 'pk', value)
    for key in ('date_joined', 'last_login'):
        value = form.initial.get(key)
        if value:
            data[f'{key}_0'] = value.strftime('%Y-%m-%d')
            data[f'{key}_1'] = value.strftime('%H:%M:%S')
        data.pop(key, None)
    data.update(extra)
    return data


# --- Django admin -------------------------------------------------------------------------

def test_change_page_never_contains_the_stored_password(admin_client, sender):
    response = admin_client.get(_change_url(sender))
    page = response.content.decode()
    assert response.status_code == 200
    assert STORED not in page
    assert 'Leave blank to keep the current password.' in page
    assert 'Remove the stored password' in page
    assert 'Stored SMTP app password' in page
    form = response.context['adminform'].form
    assert 'smtp_password' not in form.fields
    assert form.fields['new_smtp_password'].widget.render_value is False


def test_list_page_shows_only_whether_a_password_is_set(admin_client, sender):
    response = admin_client.get(reverse('admin:crm_app_user_changelist'))
    page = response.content.decode()
    assert response.status_code == 200
    assert STORED not in page
    assert 'SMTP password set' in page


def test_blank_keeps_new_replaces_checkbox_clears(admin_client, sender):
    response = admin_client.post(_change_url(sender), _form_data(admin_client, sender, new_smtp_password=''))
    assert response.status_code == 302, response.context['adminform'].form.errors
    sender.refresh_from_db()
    assert sender.smtp_password == STORED

    response = admin_client.post(_change_url(sender), _form_data(admin_client, sender, new_smtp_password=NEW))
    assert response.status_code == 302
    sender.refresh_from_db()
    assert sender.smtp_password == NEW

    response = admin_client.post(_change_url(sender), _form_data(admin_client, sender, clear_smtp_password='on'))
    assert response.status_code == 302
    sender.refresh_from_db()
    assert sender.smtp_password is None


def test_new_value_and_remove_together_is_refused(admin_client, sender):
    response = admin_client.post(
        _change_url(sender),
        _form_data(admin_client, sender, new_smtp_password=NEW, clear_smtp_password='on'),
    )
    assert response.status_code == 200
    assert 'not both' in response.content.decode()
    assert NEW not in response.content.decode()
    sender.refresh_from_db()
    assert sender.smtp_password == STORED


def test_admin_history_names_the_field_but_not_the_value(admin_client, sender):
    admin_client.post(_change_url(sender), _form_data(admin_client, sender, new_smtp_password=NEW))
    entry = LogEntry.objects.filter(object_id=str(sender.pk)).latest('action_time')
    assert NEW not in entry.change_message and STORED not in entry.change_message
    history = admin_client.get(reverse('admin:crm_app_user_history', args=[sender.pk])).content.decode()
    assert NEW not in history and STORED not in history


# --- REST API -----------------------------------------------------------------------------

def _no_secret(payload):
    text = str(payload)
    assert STORED not in text and NEW not in text
    assert 'smtp_password' not in text


def test_user_list_retrieve_and_me_leave_the_password_out(api, sender, admin_user):
    _no_secret(api.get('/api/v1/users/').data)
    _no_secret(api.get(f'/api/v1/users/{sender.pk}/').data)
    own = APIClient()
    own.force_authenticate(sender)
    me = own.get('/api/v1/users/me/').data
    _no_secret(me)
    assert me['smtp_configured'] is True
    _no_secret(own.get('/api/v1/auth/me/').data)


def test_create_and_update_replies_leave_the_password_out(api):
    created = api.post('/api/v1/users/', {
        'username': 'made-fixture', 'email': 'made-fixture@example.com', 'password': 'test-only-password',
        'role': 'Sales', 'smtp_email': 'made-fixture@example.com', 'smtp_password': STORED,
    }, format='json')
    assert created.status_code == 201, created.data
    _no_secret(created.data)
    updated = api.patch(f"/api/v1/users/{created.data['id']}/", {'smtp_password': NEW}, format='json')
    assert updated.status_code == 200
    _no_secret(updated.data)
    assert User.objects.get(pk=created.data['id']).smtp_password == NEW


def test_audit_row_of_a_password_change_has_no_value(api, sender):
    api.patch(f'/api/v1/users/{sender.pk}/', {'smtp_password': NEW}, format='json')
    for row in AuditLog.objects.filter(model_name='User', record_id=str(sender.pk)):
        assert NEW not in str(row.changes) and STORED not in str(row.changes)


def test_audit_redaction_covers_secret_like_fields():
    from crm_app.views import redact_secret_changes
    changes = {
        'smtp_password': {'old': STORED, 'new': NEW},
        'api_key': {'old': 'a', 'new': 'b'},
        'smtp_configured': {'old': False, 'new': True},
        'name': {'old': 'A', 'new': 'B'},
    }
    out = redact_secret_changes(changes)
    assert out['smtp_password'] == {'old': '[redacted]', 'new': '[redacted]'}
    assert out['api_key'] == {'old': '[redacted]', 'new': '[redacted]'}
    assert out['smtp_configured'] == {'old': False, 'new': True}
    assert out['name'] == {'old': 'A', 'new': 'B'}


def test_update_smtp_reply_has_no_password(sender):
    own = APIClient()
    own.force_authenticate(sender)
    response = own.post('/api/v1/users/update_smtp/',
                        {'smtp_email': 'sender-fixture@example.com', 'smtp_password': NEW}, format='json')
    assert response.status_code == 200
    _no_secret(response.data)
    assert response.data['smtp_configured'] is True


@pytest.mark.parametrize('route', ['test_smtp', 'test_smtp_send'])
def test_failed_mail_login_never_reports_or_logs_the_password(route, api, sender, caplog):
    client = api
    url = f'/api/v1/users/{sender.pk}/test_smtp_send/'
    if route == 'test_smtp':
        client = APIClient()
        client.force_authenticate(sender)
        url = '/api/v1/users/test_smtp/'
    failure = smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted: sender-fixture@example.com')
    with caplog.at_level(logging.DEBUG), mock.patch('smtplib.SMTP') as smtp:
        smtp.return_value.login.side_effect = failure
        response = client.post(url, {'to_email': 'to-fixture@example.com'}, format='json')
    assert response.status_code == 400
    _no_secret(response.data)
    logged = '\n'.join(r.getMessage() + (str(r.exc_info[1]) if r.exc_info else '') for r in caplog.records)
    assert STORED not in logged
    assert smtp.return_value.login.call_args.args == ('sender-fixture@example.com', STORED)
