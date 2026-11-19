"""User.smtp_password is stored encrypted; plain values stored earlier keep working until encrypted.

Keys are generated per test; every password is invented; no test connects to a mail server.
"""
import io
import smtplib
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F, TextField, Value
from django.db.models.functions import Cast
from django.test import override_settings
from rest_framework.test import APIClient

from crm_app.models import User

PLAIN = 'legacy-app-pass-fixture'
OTHER = 'second-app-pass-fixture'


def _use_keys(monkeypatch, keys):
    """Use these keys for the rest of the test (the field reads the setting on every use)."""
    value = keys if len(keys) > 1 else keys[0]
    ctx = override_settings(FIELD_ENCRYPTION_KEY=value)
    ctx.enable()
    return ctx


@pytest.fixture
def key(monkeypatch):
    k = Fernet.generate_key().decode()
    ctx = _use_keys(monkeypatch, [k])
    yield k
    ctx.disable()


def _raw(user):
    return User.objects.filter(pk=user.pk).annotate(
        raw=Cast(F('smtp_password'), output_field=TextField())
    ).values_list('raw', flat=True)[0]


def _store_plain(user, value):
    """Write the column directly, as values were stored before this change."""
    from crm_app.management.commands.encrypt_smtp_passwords import _write_raw
    _write_raw(User, user.pk, value)


def _user(name='sender', password=None, **extra):
    return User.objects.create_user(
        username=f'{name}-fixture', email=f'{name}-fixture@example.com', password='test-only-password',
        role='Admin', smtp_email=f'{name}-fixture@example.com', smtp_password=password, **extra,
    )


def _run(*args):
    out = io.StringIO()
    call_command('encrypt_smtp_passwords', *args, stdout=out)
    return out.getvalue()


# --- the field ------------------------------------------------------------------------------

def test_saves_encrypt_and_reads_decrypt(key):
    user = _user(password=PLAIN)
    raw = _raw(user)
    assert raw != PLAIN and PLAIN not in raw
    assert Fernet(key).decrypt(raw.encode()).decode() == PLAIN
    assert User.objects.get(pk=user.pk).smtp_password == PLAIN


def test_plain_value_stored_earlier_still_reads(key):
    user = _user()
    _store_plain(user, PLAIN)
    assert _raw(user) == PLAIN
    fresh = User.objects.get(pk=user.pk)
    assert fresh.smtp_password == PLAIN
    assert fresh.get_smtp_config()['password'] == PLAIN


def test_longest_allowed_password_fits_the_column(key):
    long_value = 'x' * 255
    assert len(Fernet(key).encrypt(long_value.encode())) > 255
    user = _user(password=long_value)
    assert User.objects.get(pk=user.pk).smtp_password == long_value


def test_migration_only_changes_the_column_type():
    import importlib
    migration = importlib.import_module('crm_app.migrations.0106_user_smtp_password_encrypted_field').Migration
    from django.db import migrations
    # The column change, then a reverse-only guard (a no-op forward).
    assert [type(op) for op in migration.operations] == [migrations.AlterField, migrations.RunPython]
    assert migration.operations[0].field.get_internal_type() == 'TextField'
    assert migration.operations[1].code is migrations.RunPython.noop


def test_none_stays_none(key):
    user = _user(password=None)
    assert _raw(user) is None
    assert User.objects.get(pk=user.pk).get_smtp_config() is None


# --- the command ----------------------------------------------------------------------------

def test_dry_run_counts_only_and_changes_nothing(key):
    legacy = _user('legacy')
    _store_plain(legacy, PLAIN)
    _user('encrypted', password=OTHER)
    _user('empty', password=None)
    out = _run()
    assert 'Users with a stored SMTP password: 2; already encrypted with the current key: 1; would encrypt: 1' in out
    assert 'Dry run: would encrypt 1 value(s). Nothing was changed.' in out
    assert PLAIN not in out and OTHER not in out
    assert _raw(legacy) == PLAIN


def test_verify_fails_before_and_passes_after_execute(key):
    legacy = _user('legacy')
    _store_plain(legacy, PLAIN)
    with pytest.raises(CommandError, match='1 stored value'):
        _run('--verify')
    out = _run('--execute')
    assert 'Encrypted 1 value(s).' in out
    assert PLAIN not in out
    assert Fernet(key).decrypt(_raw(legacy).encode()).decode() == PLAIN
    assert User.objects.get(pk=legacy.pk).smtp_password == PLAIN
    assert 'Verified' in _run('--verify')


def test_execute_is_idempotent(key):
    legacy = _user('legacy')
    _store_plain(legacy, PLAIN)
    _run('--execute')
    first = _raw(legacy)
    out = _run('--execute')
    assert 'Encrypted 0 value(s).' in out
    assert _raw(legacy) == first


@pytest.mark.parametrize('setting', ['builtin', 'empty'])
def test_refuses_without_a_real_key(setting, monkeypatch):
    from bmasia_crm import settings as project_settings
    value = project_settings._BUILTIN_FIELD_ENCRYPTION_KEY if setting == 'builtin' else ''
    user = _user()
    _store_plain(user, PLAIN)
    with override_settings(FIELD_ENCRYPTION_KEY=value):
        for args in ([], ['--execute'], ['--verify'], ['--decrypt-to-plain', '--execute']):
            with pytest.raises(CommandError, match='unset or is the built-in development default') as err:
                _run(*args)
            assert value == '' or value not in str(err.value)
    assert _raw(user) == PLAIN


def test_failed_verification_rolls_the_row_back(key, monkeypatch):
    legacy = _user('legacy')
    _store_plain(legacy, PLAIN)
    # The field encrypts with a different key than the command checks against.
    from cryptography.fernet import MultiFernet
    import crm_app.fields as fields
    monkeypatch.setattr(fields, 'crypter', lambda: MultiFernet([Fernet(Fernet.generate_key())]))
    with pytest.raises(CommandError, match='Verification failed'):
        _run('--execute')
    assert _raw(legacy) == PLAIN


def test_rotation_reencrypts_values_under_the_previous_key(monkeypatch):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    ctx = _use_keys(monkeypatch, [old])
    user = _user(password=PLAIN)
    ctx.disable()
    ctx = _use_keys(monkeypatch, [new, old])
    try:
        assert User.objects.get(pk=user.pk).smtp_password == PLAIN  # both keys read
        out = _run()
        assert '(plain: 0, previous key: 1)' in out
        _run('--execute')
        assert Fernet(new).decrypt(_raw(user).encode()).decode() == PLAIN
        assert 'Verified' in _run('--verify')
    finally:
        ctx.disable()


def test_decrypt_to_plain_is_the_rollback(key):
    user = _user(password=PLAIN)
    assert 'would store 1 value(s) as plain text' in _run('--decrypt-to-plain')
    assert _raw(user) != PLAIN
    out = _run('--decrypt-to-plain', '--execute')
    assert 'Stored 1 value(s) as plain text.' in out and PLAIN not in out
    assert _raw(user) == PLAIN
    assert User.objects.get(pk=user.pk).smtp_password == PLAIN


# --- mail paths work with both forms --------------------------------------------------------

@pytest.fixture(params=['plain', 'encrypted'])
def sender(request, key):
    user = _user(password=PLAIN)
    if request.param == 'plain':
        _store_plain(user, PLAIN)
    return User.objects.get(pk=user.pk)


def test_get_smtp_config_and_sender_connection(sender):
    from crm_app.services.email_service import EmailService
    assert sender.get_smtp_config()['password'] == PLAIN
    with mock.patch('django.core.mail.get_connection') as get_connection:
        EmailService()._get_smtp_connection_for_sender(f'Fixture <{sender.smtp_email}>')
    assert get_connection.call_args.kwargs['username'] == sender.smtp_email
    assert get_connection.call_args.kwargs['password'] == PLAIN


def test_test_smtp_and_test_smtp_send_log_in_with_the_plain_password(sender):
    own = APIClient()
    own.force_authenticate(sender)
    admin = User.objects.create_user(username='adm-send-fixture', password='test-only-password', role='Admin',
                                     is_staff=True, is_superuser=True)
    staff = APIClient()
    staff.force_authenticate(admin)
    with mock.patch('smtplib.SMTP') as smtp:
        assert own.post('/api/v1/users/test_smtp/').status_code == 200
        assert smtp.return_value.login.call_args.args == (sender.smtp_email, PLAIN)
        response = staff.post(f'/api/v1/users/{sender.pk}/test_smtp_send/', {'to_email': 'to@example.com'},
                              format='json')
        assert response.status_code == 200, response.data
        assert smtp.return_value.login.call_args.args == (sender.smtp_email, PLAIN)


def test_update_smtp_stores_encrypted(key):
    user = _user()
    _store_plain(user, PLAIN)
    client = APIClient()
    client.force_authenticate(user)
    response = client.post('/api/v1/users/update_smtp/', {'smtp_email': user.smtp_email, 'smtp_password': OTHER},
                           format='json')
    assert response.status_code == 200 and response.data['smtp_configured'] is True
    assert Fernet(key).decrypt(_raw(user).encode()).decode() == OTHER


def test_admin_change_page_opens_for_both_forms(sender, client):
    admin = User.objects.create_user(username='adm-enc-fixture', password='test-only-password', role='Admin',
                                     is_staff=True, is_superuser=True)
    client.force_login(admin)
    response = client.get(f'/admin/crm_app/user/{sender.pk}/change/')
    assert response.status_code == 200
    raw = _raw(sender)
    if raw != PLAIN:
        assert raw not in response.content.decode()  # the stored token never reaches the page


def test_quote_send_uses_the_plain_password(sender, settings):
    """The per-user SMTP connection built for document sends gets the decrypted password."""
    from django.core import mail
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    config = sender.get_smtp_config()
    connection = mail.get_connection(
        backend='django.core.mail.backends.locmem.EmailBackend',
        host=config['host'], port=config['port'], username=config['email'], password=config['password'],
    )
    mail.EmailMessage('s', 'b', config['email'], ['to@example.com'], connection=connection).send()
    assert len(mail.outbox) == 1
    assert config['password'] == PLAIN
