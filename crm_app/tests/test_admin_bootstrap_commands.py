"""Admin bootstrap commands have no built-in password.

createadmin, reset_admin and initialize_database take the password from
ADMIN_INITIAL_PASSWORD or an interactive prompt, and refuse to run when
neither is available.
"""
import io
import secrets
import sys

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from crm_app.management import admin_password
from crm_app.management.commands import initialize_database

ENV = admin_password.ADMIN_PASSWORD_ENV_VAR


@pytest.fixture
def no_env_password(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)


@pytest.fixture
def env_password(monkeypatch):
    password = secrets.token_urlsafe(16)
    monkeypatch.setenv(ENV, password)
    return password


@pytest.fixture
def not_a_tty(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)


@pytest.fixture
def tty_answers(monkeypatch):
    def install(*answers):
        replies = iter(answers)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(admin_password.getpass, "getpass", lambda prompt="": next(replies))

    return install


def _admin():
    return get_user_model().objects.filter(username="admin").first()


def _make_admin():
    user = get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password=secrets.token_urlsafe(16)
    )
    return user


# createadmin


def test_createadmin_refuses_without_password_source(no_env_password, not_a_tty):
    with pytest.raises(CommandError, match=ENV):
        call_command("createadmin")

    assert _admin() is None


def test_createadmin_noinput_ignores_terminal(no_env_password, tty_answers):
    tty_answers("should-not-be-asked")

    with pytest.raises(CommandError, match=ENV):
        call_command("createadmin", "--noinput")

    assert _admin() is None


def test_createadmin_uses_env_password_and_does_not_print_it(env_password):
    out = io.StringIO()

    call_command("createadmin", "--noinput", stdout=out)

    admin = _admin()
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password(env_password)
    assert env_password not in out.getvalue()


def test_createadmin_prompts_when_interactive(no_env_password, tty_answers):
    password = secrets.token_urlsafe(16)
    tty_answers(password, password)

    call_command("createadmin", stdout=io.StringIO())

    assert _admin().check_password(password)


def test_createadmin_rejects_mismatched_prompt(no_env_password, tty_answers):
    tty_answers(secrets.token_urlsafe(16), secrets.token_urlsafe(16))

    with pytest.raises(CommandError, match="did not match"):
        call_command("createadmin")

    assert _admin() is None


def test_createadmin_rejects_weak_env_password(monkeypatch):
    monkeypatch.setenv(ENV, "12345678")

    with pytest.raises(CommandError, match="rejected"):
        call_command("createadmin", "--noinput")

    assert _admin() is None


def test_createadmin_is_a_no_op_when_admin_exists(no_env_password, not_a_tty):
    admin = _make_admin()
    original_hash = admin.password

    call_command("createadmin", "--noinput", stdout=io.StringIO())

    admin.refresh_from_db()
    assert admin.password == original_hash


# reset_admin


def test_reset_admin_refuses_without_password_source(no_env_password, not_a_tty):
    admin = _make_admin()
    original_hash = admin.password

    with pytest.raises(CommandError, match=ENV):
        call_command("reset_admin")

    admin.refresh_from_db()
    assert admin.password == original_hash


def test_reset_admin_uses_env_password_and_does_not_print_it(env_password):
    _make_admin()
    out = io.StringIO()

    call_command("reset_admin", "--noinput", stdout=out)

    assert _admin().check_password(env_password)
    assert env_password not in out.getvalue()


def test_reset_admin_without_admin_user_is_an_error(env_password):
    with pytest.raises(CommandError, match="not found"):
        call_command("reset_admin", "--noinput")


# initialize_database


@pytest.fixture
def stub_initialize_subcommands(monkeypatch):
    calls = []
    monkeypatch.setattr(
        initialize_database, "call_command", lambda *args, **kwargs: calls.append(args)
    )
    return calls


def test_initialize_database_refuses_before_migrating(
    no_env_password, not_a_tty, stub_initialize_subcommands
):
    with pytest.raises(CommandError, match=ENV):
        call_command("initialize_database", "--noinput")

    assert stub_initialize_subcommands == []
    assert _admin() is None


def test_initialize_database_creates_admin_from_env(env_password, stub_initialize_subcommands):
    out = io.StringIO()

    call_command("initialize_database", "--noinput", stdout=out)

    assert stub_initialize_subcommands[0] == ("migrate", "--noinput")
    assert _admin().check_password(env_password)
    assert env_password not in out.getvalue()
