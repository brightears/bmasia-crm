"""Sensitive settings that fall back to built-in defaults.

Development and tests: one warning naming the setting. Production (RENDER set, as on
every Render service, cron and job): the process stops at startup naming the setting.
No test output contains a value.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bmasia_crm import settings as settings_module

REPO_ROOT = Path(settings_module.__file__).resolve().parent.parent
GUARDED = ("SECRET_KEY", "FIELD_ENCRYPTION_KEY")
BUILTIN_DEFAULTS = {
    "SECRET_KEY": settings_module._BUILTIN_SECRET_KEY,
    "FIELD_ENCRYPTION_KEY": settings_module._BUILTIN_FIELD_ENCRYPTION_KEY,
}


def _message(name):
    return f"{name} is not set in the environment; using the built-in development default"


def _run(args, **overrides):
    env = {k: v for k, v in os.environ.items() if k not in GUARDED + ("RENDER",)}
    env.update(overrides)
    return subprocess.run(
        [sys.executable, *args], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


def _import_settings_stderr(**overrides):
    """Import the settings module in a fresh interpreter and return its stderr."""
    result = _run(["-c", "import bmasia_crm.settings"], **overrides)
    assert result.returncode == 0, result.stderr
    return result.stderr


REAL = {
    "SECRET_KEY": "test-only-secret-key-not-a-real-one",
    "FIELD_ENCRYPTION_KEY": "dGVzdC1vbmx5LWZpZWxkLWVuY3J5cHRpb24ta2V5MDA=",
}


@pytest.mark.parametrize("name", GUARDED)
def test_builtin_default_logs_one_warning_naming_only_the_setting(name, caplog):
    default = BUILTIN_DEFAULTS[name]
    with caplog.at_level(logging.WARNING, logger="bmasia_crm.settings"):
        settings_module._warn_if_builtin_default(name, default, default)

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, _message(name))
    ]
    assert default not in caplog.text


def test_configured_value_logs_nothing(caplog):
    with caplog.at_level(logging.DEBUG, logger="bmasia_crm.settings"):
        settings_module._warn_if_builtin_default("SECRET_KEY", "configured", "builtin")

    assert caplog.records == []


@pytest.mark.skipif(
    any(
        (directory / name).exists()
        for directory in (REPO_ROOT / "bmasia_crm", REPO_ROOT)
        for name in (".env", "settings.ini")
    ),
    reason="a local config file can supply the settings",
)
def test_settings_import_warns_once_per_unset_setting():
    stderr = _import_settings_stderr()

    for name in GUARDED:
        assert stderr.count(_message(name)) == 1
    for value in BUILTIN_DEFAULTS.values():
        assert value not in stderr


def test_settings_import_is_silent_when_both_settings_are_set():
    stderr = _import_settings_stderr(
        SECRET_KEY="test-only-secret-key",
        FIELD_ENCRYPTION_KEY="dGVzdC1vbmx5LWZpZWxkLWVuY3J5cHRpb24ta2V5MDA=",
    )

    for name in GUARDED:
        assert _message(name) not in stderr


# --- production (RENDER set) ------------------------------------------------------------------

def _assert_no_value(text):
    for value in list(BUILTIN_DEFAULTS.values()) + list(REAL.values()):
        assert value not in text


def test_production_starts_when_both_settings_are_real():
    result = _run(["-c", "import bmasia_crm.settings as s; assert s.IS_PRODUCTION"], RENDER="true", **REAL)
    assert result.returncode == 0, result.stderr
    for name in GUARDED:
        assert _message(name) not in result.stderr


@pytest.mark.parametrize("name", GUARDED)
@pytest.mark.parametrize("how", ["missing", "empty", "builtin"])
def test_production_stops_naming_the_setting(name, how):
    env = dict(REAL, RENDER="true")
    if how == "missing":
        env.pop(name)
    elif how == "empty":
        env[name] = ""
    else:
        env[name] = BUILTIN_DEFAULTS[name]
    result = _run(["-c", "import bmasia_crm.settings"], **env)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert f"{name} must be set in the environment of this service" in result.stderr
    _assert_no_value(result.stderr)


def test_production_refuses_a_malformed_encryption_key():
    result = _run(["-c", "import bmasia_crm.settings"], RENDER="true", SECRET_KEY=REAL["SECRET_KEY"],
                  FIELD_ENCRYPTION_KEY="not-a-fernet-key")
    assert result.returncode != 0
    assert "FIELD_ENCRYPTION_KEY is set but is not in the expected format." in result.stderr
    assert "not-a-fernet-key" not in result.stderr


@pytest.mark.parametrize("command", [["check"], ["migrate", "--check"], ["collectstatic", "--noinput", "--dry-run"]])
def test_deploy_commands_stop_before_doing_anything_when_the_key_is_missing(command):
    """build.sh (collectstatic), the pre-deploy migrate and start.sh all import settings first."""
    env = dict(REAL, RENDER="true")
    env.pop("FIELD_ENCRYPTION_KEY")
    env.pop("DATABASE_URL", None)
    result = _run(["manage.py", *command], **env)
    assert result.returncode != 0
    assert "FIELD_ENCRYPTION_KEY must be set in the environment of this service" in result.stderr
    _assert_no_value(result.stderr + result.stdout)


def test_development_keeps_working_with_the_builtin_defaults():
    result = _run(["manage.py", "check"])
    assert result.returncode == 0, result.stderr
