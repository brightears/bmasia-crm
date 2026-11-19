"""Review follow-ups for the encrypted SMTP password.

C1 an unreadable token is never treated as plain text; C2 every write encrypts or is refused;
C3 no encryption under the built-in key in production; C4 dumpdata keeps the stored form;
C5 the reverse of 0106 refuses to cut values; C6 a malformed previous key; settings wiring;
rotation and wrong-key scenarios end in correct sends or the clear unreadable state.

Keys are generated per test; every password is invented; nothing connects to a mail server.
"""
import io
import json
import logging
import os
import smtplib
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.db.models import F, TextField, Value
from django.db.models.functions import Cast, Upper
from django.test import override_settings
from rest_framework.test import APIClient

from crm_app import fields
from crm_app.fields import UndecryptableSecret, UnreadableSecret, is_token_shaped
from crm_app.models import SMTP_PASSWORD_UNREADABLE_MESSAGE, User

PLAIN = 'legacy-app-pass-fixture'
OTHER = 'second-app-pass-fixture'
REPO_ROOT = Path(__file__).resolve().parents[2]


def _key():
    return Fernet.generate_key().decode()


@pytest.fixture
def key():
    k = _key()
    with override_settings(FIELD_ENCRYPTION_KEY=k):
        yield k


def _raw(user):
    return User.objects.filter(pk=user.pk).annotate(
        raw=Cast(F('smtp_password'), output_field=TextField())
    ).values_list('raw', flat=True)[0]


def _write_raw(user, value):
    from crm_app.management.commands.encrypt_smtp_passwords import _write_raw
    _write_raw(User, user.pk, value)


def _user(name='sender', password=None, **extra):
    return User.objects.create_user(
        username=f'{name}-fixture', email=f'{name}-fixture@example.com', password='test-only-password',
        role='Sales', smtp_email=f'{name}-fixture@example.com', smtp_password=password, **extra,
    )


def _staff():
    return User.objects.create_user(username='staff-fixture', password='test-only-password', role='Admin',
                                    is_staff=True, is_superuser=True)


def _run(*args):
    out = io.StringIO()
    call_command('encrypt_smtp_passwords', *args, stdout=out)
    return out.getvalue()


def _token_under_other_key(text=PLAIN):
    return Fernet(_key()).encrypt(text.encode()).decode()


def _decrypts_under(k, stored, expected):
    return Fernet(k).decrypt(stored.encode()).decode() == expected


# --- the token-shape rule -------------------------------------------------------------------

def test_token_shape_rule_and_near_misses():
    token = Fernet(_key()).encrypt(b'x').decode()
    assert is_token_shaped(token)
    assert is_token_shaped(Fernet(_key()).encrypt(b'y' * 300).decode())
    near_misses = [
        'abcdefghijklmnop',                      # a Gmail app password
        'abcd efgh ijkl mnop',                   # the same, spaced
        'gAAAAA' + 'a' * 10,                     # the prefix, far too short
        token[:-4],                              # one base64 group short
        token[:-1],                              # length not a multiple of 4
        token.replace('g', 'h', 1),              # first byte is not the version byte
        token[:99] + '!',                        # a character outside urlsafe base64
        'A' * 100,                               # right length, wrong version byte
        'gAAAAA' + 'B' * 94,                     # right length and prefix, padding missing
        'gA' + 'A' * 102,                        # version byte but blocks misaligned
        PLAIN,
        '',
    ]
    for value in near_misses:
        assert not is_token_shaped(value), value


# --- C1: unreadable values ------------------------------------------------------------------

def test_token_under_another_key_reads_as_unreadable_never_as_text(key):
    user = _user()
    _write_raw(user, _token_under_other_key())
    fresh = User.objects.get(pk=user.pk)
    assert isinstance(fresh.smtp_password, UnreadableSecret)
    assert fresh.smtp_password_state == 'unreadable'
    with pytest.raises(UndecryptableSecret):
        str(fresh.smtp_password)
    with pytest.raises(UndecryptableSecret):
        fresh.smtp_password.encode()
    assert repr(fresh.smtp_password) == '<unreadable secret>'


def test_unreadable_value_is_never_sent_and_logs_one_warning(key, caplog):
    user = _user()
    token = _token_under_other_key()
    _write_raw(user, token)
    fresh = User.objects.get(pk=user.pk)
    with caplog.at_level(logging.WARNING, logger='crm_app.models'):
        assert fresh.get_smtp_config() is None
    warnings = [r for r in caplog.records if r.name == 'crm_app.models']
    assert len(warnings) == 1 and str(user.pk) in warnings[0].getMessage()
    assert token not in caplog.text

    from crm_app.services.email_service import EmailService
    with mock.patch('django.core.mail.get_connection') as get_connection:
        assert EmailService()._get_smtp_connection_for_sender(fresh.smtp_email) is None
    get_connection.assert_not_called()

    own = APIClient()
    own.force_authenticate(fresh)
    staff = APIClient()
    staff.force_authenticate(_staff())
    with mock.patch('smtplib.SMTP') as smtp:
        r1 = own.post('/api/v1/users/test_smtp/')
        r2 = staff.post(f'/api/v1/users/{user.pk}/test_smtp_send/', {'to_email': 'to@example.com'}, format='json')
    assert r1.status_code == r2.status_code == 400
    assert r1.data['error'] == r2.data['error'] == SMTP_PASSWORD_UNREADABLE_MESSAGE
    smtp.return_value.login.assert_not_called()


def test_rest_and_admin_show_unreadable_and_let_a_person_replace_or_remove(key, client):
    user = _user()
    token = _token_under_other_key()
    _write_raw(user, token)
    staff_user = _staff()
    api = APIClient()
    api.force_authenticate(staff_user)
    data = api.get(f'/api/v1/users/{user.pk}/').data
    assert data['smtp_status'] == 'Set (unreadable: needs re-entry)'
    assert data['smtp_configured'] is False
    assert token not in str(data)

    client.force_login(staff_user)
    page = client.get(f'/admin/crm_app/user/{user.pk}/change/').content.decode()
    assert 'Set (unreadable: needs re-entry)' in page
    assert token not in page

    # Saving another field keeps the stored token as it is (no double encryption).
    fresh = User.objects.get(pk=user.pk)
    fresh.first_name = 'Changed'
    fresh.save()
    assert _raw(user) == token

    assert api.patch(f'/api/v1/users/{user.pk}/', {'smtp_password': OTHER}, format='json').status_code == 200
    assert _decrypts_under(key, _raw(user), OTHER)
    assert User.objects.get(pk=user.pk).smtp_password_state == 'set'

    _write_raw(user, token)
    own = APIClient()
    own.force_authenticate(User.objects.get(pk=user.pk))
    assert own.post('/api/v1/users/update_smtp/', {'smtp_email': '', 'smtp_password': ''},
                    format='json').status_code == 200
    assert _raw(user) is None


def test_command_counts_refuses_skips_and_verify_fails(key):
    readable = _user('readable')
    _write_raw(readable, PLAIN)
    unreadable = _user('unreadable')
    token = _token_under_other_key()
    _write_raw(unreadable, token)

    out = _run()
    assert 'undecryptable: 1' in out and '(plain: 1, previous key: 0)' in out
    assert '--execute will refuse' in out
    with pytest.raises(CommandError, match='1 stored value\\(s\\) cannot be decrypted'):
        _run('--execute')
    assert _raw(readable) == PLAIN and _raw(unreadable) == token  # nothing changed

    out = _run('--execute', '--skip-undecryptable')
    assert 'Encrypted 1 value(s).' in out and 'Left untouched: 1' in out
    assert _raw(unreadable) == token
    assert _decrypts_under(key, _raw(readable), PLAIN)
    with pytest.raises(CommandError, match='1 cannot be decrypted'):
        _run('--verify')
    assert token not in out and PLAIN not in out


# --- C2: every write path -------------------------------------------------------------------

def test_every_orm_write_encrypts(key):
    a = _user('a')
    a.smtp_password = PLAIN
    a.save()
    assert _decrypts_under(key, _raw(a), PLAIN)

    created = User.objects.bulk_create([User(username='bulk-fixture', email='b@example.com', smtp_password=PLAIN)])
    assert _decrypts_under(key, _raw(created[0]), PLAIN)

    a.smtp_password = OTHER
    User.objects.bulk_update([a], ['smtp_password'])
    assert _decrypts_under(key, _raw(a), OTHER)

    User.objects.filter(pk=a.pk).update(smtp_password=PLAIN)
    assert _decrypts_under(key, _raw(a), PLAIN)


@pytest.mark.parametrize('expression', [
    Value(PLAIN), Value(PLAIN, output_field=TextField()), F('smtp_email'), Upper(Value(PLAIN)),
])
def test_expressions_are_refused(key, expression):
    user = _user(password=PLAIN)
    before = _raw(user)
    with pytest.raises(FieldError, match='database expression'), transaction.atomic():
        User.objects.filter(pk=user.pk).update(smtp_password=expression)
    assert _raw(user) == before


def test_bulk_update_with_an_expression_is_refused(key):
    user = _user(password=PLAIN)
    user.smtp_password = F('smtp_email')
    with pytest.raises(FieldError), transaction.atomic():
        User.objects.bulk_update([user], ['smtp_password'])


def test_admin_and_serializer_assignment_encrypt(key, client):
    user = _user(password=PLAIN)
    staff_user = _staff()
    api = APIClient()
    api.force_authenticate(staff_user)
    created = api.post('/api/v1/users/', {
        'username': 'made-fixture', 'email': 'made@example.com', 'password': 'test-only-password',
        'role': 'Sales', 'smtp_email': 'made@example.com', 'smtp_password': PLAIN,
    }, format='json')
    assert created.status_code == 201
    made = User.objects.get(pk=created.data['id'])
    assert _decrypts_under(key, _raw(made), PLAIN)

    from crm_app.admin import UserAdminChangeForm
    form = UserAdminChangeForm(instance=user)
    data = {k: v for k, v in form.initial.items() if v is not None and k not in ('password', 'groups',
                                                                                 'user_permissions')}
    data['new_smtp_password'] = OTHER
    bound = UserAdminChangeForm(data, instance=user)
    assert bound.is_valid(), bound.errors
    bound.save()
    assert _decrypts_under(key, _raw(user), OTHER)


def test_lookups_other_than_isnull_and_empty_are_refused(key):
    user = _user(password=PLAIN)
    assert User.objects.filter(smtp_password__isnull=False).filter(pk=user.pk).exists()
    assert not User.objects.filter(smtp_password='').exists()
    for bad in ({'smtp_password': PLAIN}, {'smtp_password__icontains': 'x'}, {'smtp_password__in': [PLAIN]},
                {'smtp_password__startswith': 'g'}, {'smtp_password__lower': PLAIN}):
        with pytest.raises(FieldError):
            list(User.objects.filter(**bad))


# --- C4: dumpdata and loaddata --------------------------------------------------------------

def test_dumpdata_writes_the_stored_form_and_loaddata_round_trips(key, tmp_path):
    encrypted = _user('enc', password=PLAIN)
    legacy = _user('legacy')
    _write_raw(legacy, OTHER)
    stored_encrypted = _raw(encrypted)

    out = io.StringIO()
    call_command('dumpdata', 'crm_app.user', stdout=out)
    dump = out.getvalue()
    assert PLAIN not in dump
    rows = {r['fields']['username']: r['fields']['smtp_password'] for r in json.loads(dump)}
    assert rows['enc-fixture'] == stored_encrypted
    assert rows['legacy-fixture'] == OTHER  # a value stored before encryption dumps as stored

    fixture = tmp_path / 'users.json'
    fixture.write_text(dump)
    User.objects.filter(pk__in=[encrypted.pk, legacy.pk]).delete()
    call_command('loaddata', str(fixture), stdout=io.StringIO())
    assert _raw(encrypted) == stored_encrypted  # not encrypted twice
    assert User.objects.get(pk=encrypted.pk).smtp_password == PLAIN
    assert _decrypts_under(key, _raw(legacy), OTHER)  # the plain value is encrypted on load


# --- C3: built-in key in production ---------------------------------------------------------

def test_field_refuses_to_encrypt_with_the_builtin_key_in_production(monkeypatch):
    from bmasia_crm import settings as project_settings
    builtin = project_settings._BUILTIN_FIELD_ENCRYPTION_KEY
    user = _user()
    with override_settings(FIELD_ENCRYPTION_KEY=builtin):
        monkeypatch.setenv('RENDER', 'true')
        user.smtp_password = PLAIN
        with pytest.raises(ImproperlyConfigured) as err, transaction.atomic():
            user.save()
        assert 'FIELD_ENCRYPTION_KEY is the built-in development default' in str(err.value)
        assert builtin not in str(err.value)
        monkeypatch.delenv('RENDER')
        user.save()  # development keeps working with the built-in key


# --- C5: reverse of 0106 --------------------------------------------------------------------

def _reverse_guard():
    import importlib
    module = importlib.import_module('crm_app.migrations.0106_user_smtp_password_encrypted_field')
    class _Editor:  # what the guard uses from a schema editor, without opening one mid-test
        quote_name = staticmethod(connection.ops.quote_name)

    _Editor.connection = connection
    module.refuse_reverse_while_values_would_not_fit(None, _Editor())


def test_reverse_guard_refuses_encrypted_or_long_values(key):
    user = _user(password=PLAIN)
    with pytest.raises(RuntimeError, match='1 stored SMTP password\\(s\\) are encrypted'):
        _reverse_guard()
    _write_raw(user, 'x' * 256)
    with pytest.raises(RuntimeError, match='1 are longer than 255'):
        _reverse_guard()
    _write_raw(user, PLAIN)
    _reverse_guard()  # plain and short: the narrowing may go ahead
    assert _raw(user) == PLAIN


def test_decrypt_to_plain_then_reverse_guard_passes(key):
    user = _user(password=PLAIN)
    _run('--decrypt-to-plain', '--execute')
    assert _raw(user) == PLAIN
    _reverse_guard()


# --- C6 and the settings wiring -------------------------------------------------------------

def _settings_in_subprocess(code, **env_overrides):
    env = {k: v for k, v in os.environ.items()
           if k not in ('FIELD_ENCRYPTION_KEY', 'FIELD_ENCRYPTION_KEY_PREVIOUS', 'RENDER')}
    env.setdefault('SECRET_KEY', 'test-only-secret-key-not-a-real-one')
    env.update(env_overrides)
    return subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_rotation_list_is_built_from_the_environment():
    new, old = _key(), _key()
    old_token = Fernet(old).encrypt(PLAIN.encode()).decode()
    code = (
        'import django, os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bmasia_crm.settings"); django.setup()\n'
        'from django.conf import settings; from crm_app.fields import read_stored, encrypt_text\n'
        'from cryptography.fernet import Fernet\n'
        f'assert settings.FIELD_ENCRYPTION_KEY == [os.environ["FIELD_ENCRYPTION_KEY"], os.environ["FIELD_ENCRYPTION_KEY_PREVIOUS"]]\n'
        f'assert read_stored("{old_token}") == "{PLAIN}"\n'
        'assert Fernet(os.environ["FIELD_ENCRYPTION_KEY"]).decrypt(encrypt_text("x").encode()) == b"x"\n'
        'print("ok")'
    )
    result = _settings_in_subprocess(code, FIELD_ENCRYPTION_KEY=new, FIELD_ENCRYPTION_KEY_PREVIOUS=old)
    assert result.returncode == 0, result.stderr[-2000:]
    assert 'ok' in result.stdout
    for value in (new, old, old_token, PLAIN):
        assert value not in result.stderr


def test_malformed_previous_key_stops_production_and_warns_in_development():
    real = _key()
    prod = _settings_in_subprocess('import bmasia_crm.settings', RENDER='true', FIELD_ENCRYPTION_KEY=real,
                                   FIELD_ENCRYPTION_KEY_PREVIOUS='not-a-fernet-key')
    assert prod.returncode != 0
    assert 'FIELD_ENCRYPTION_KEY_PREVIOUS is set but is not in the expected format.' in prod.stderr
    assert 'not-a-fernet-key' not in prod.stderr and real not in prod.stderr

    dev = _settings_in_subprocess(
        'import bmasia_crm.settings as s; assert s.FIELD_ENCRYPTION_KEY == __import__("os").environ["FIELD_ENCRYPTION_KEY"]',
        FIELD_ENCRYPTION_KEY=real, FIELD_ENCRYPTION_KEY_PREVIOUS='not-a-fernet-key')
    assert dev.returncode == 0, dev.stderr[-2000:]
    assert 'FIELD_ENCRYPTION_KEY_PREVIOUS is set but is not in the expected format; it is ignored' in dev.stderr
    assert 'not-a-fernet-key' not in dev.stderr


def test_a_malformed_key_never_breaks_reading_a_user(key):
    user = _user(password=PLAIN)
    with override_settings(FIELD_ENCRYPTION_KEY=[key, 'not-a-fernet-key']):
        assert User.objects.get(pk=user.pk).smtp_password == PLAIN  # the bad extra key is ignored
    with override_settings(FIELD_ENCRYPTION_KEY='not-a-fernet-key'):
        fresh = User.objects.get(pk=user.pk)  # no exception: sign-in and pages keep working
        assert fresh.smtp_password_state == 'unreadable'


# --- rotation scenarios ---------------------------------------------------------------------

def _send_outcome(user):
    """What a send would do: the password handed to the mail server, or the unreadable message."""
    client = APIClient()
    client.force_authenticate(User.objects.get(pk=user.pk))
    with mock.patch('smtplib.SMTP') as smtp:
        response = client.post('/api/v1/users/test_smtp/')
    if response.status_code == 200:
        return ('sent', smtp.return_value.login.call_args.args[1])
    assert response.data['error'] == SMTP_PASSWORD_UNREADABLE_MESSAGE
    smtp.return_value.login.assert_not_called()
    return ('unreadable', None)


def test_rotation_then_mistaken_rollback_to_the_old_key_then_recovery():
    k1, k2 = _key(), _key()
    with override_settings(FIELD_ENCRYPTION_KEY=k1):
        a = _user('a', password=PLAIN)
        b = _user('b')
        _write_raw(b, OTHER)
        _run('--execute')
        assert 'Verified' in _run('--verify')
    with override_settings(FIELD_ENCRYPTION_KEY=[k2, k1]):
        assert _send_outcome(a) == ('sent', PLAIN)
        assert '(plain: 0, previous key: 2)' in _run()
        _run('--execute')
        assert 'Verified' in _run('--verify')
    stored = {a.pk: _raw(a), b.pk: _raw(b)}
    with override_settings(FIELD_ENCRYPTION_KEY=k1):  # back to the old key by mistake
        assert _send_outcome(a) == ('unreadable', None)
        assert _send_outcome(b) == ('unreadable', None)
        assert 'undecryptable: 2' in _run()
        with pytest.raises(CommandError):
            _run('--execute')
        with pytest.raises(CommandError):
            _run('--verify')
        assert {a.pk: _raw(a), b.pk: _raw(b)} == stored  # never encrypted twice
    with override_settings(FIELD_ENCRYPTION_KEY=[k1, k2]):  # recovery: the newer key as previous
        assert _send_outcome(a) == ('sent', PLAIN)
        assert _send_outcome(b) == ('sent', OTHER)
        _run('--execute')
        assert 'Verified' in _run('--verify')
        assert _decrypts_under(k1, _raw(a), PLAIN) and _decrypts_under(k1, _raw(b), OTHER)


def test_wrong_key_on_one_service():
    shared, wrong = _key(), _key()
    with override_settings(FIELD_ENCRYPTION_KEY=shared):
        user = _user(password=PLAIN)
    stored = _raw(user)
    with override_settings(FIELD_ENCRYPTION_KEY=wrong):  # e.g. a cron with its own value
        assert _send_outcome(user) == ('unreadable', None)
        fresh = User.objects.get(pk=user.pk)
        fresh.last_name = 'Touched'
        fresh.save()  # a save on that service keeps the stored token
        assert _raw(user) == stored
        with pytest.raises(CommandError):
            _run('--execute')
    with override_settings(FIELD_ENCRYPTION_KEY=shared):
        assert _send_outcome(user) == ('sent', PLAIN)
