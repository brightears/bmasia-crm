"""Startup warnings for sensitive settings that fall back to built-in defaults."""

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


def _import_settings_stderr(**overrides):
    """Import the settings module in a fresh interpreter and return its stderr."""
    env = {k: v for k, v in os.environ.items() if k not in GUARDED}
    env.update(overrides)
    result = subprocess.run(
        [sys.executable, "-c", "import bmasia_crm.settings"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stderr


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
