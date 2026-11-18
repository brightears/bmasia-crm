"""The suite must never reach an outside service (crm_app/tests/network_guard.py)."""
import os
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from django.core import mail
from django.core.mail import EmailMessage, get_connection

from crm_app.models import Company
from crm_app.tests import network_guard

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_company_with_soundtrack_account_uses_the_stub(soundtrack_calls):
    company = Company.objects.create(name="Guard Test Hotel", soundtrack_account_id="SA-GUARD-1")

    assert len(soundtrack_calls) == 1
    _query, variables = soundtrack_calls[0]
    assert variables == {"accountId": "SA-GUARD-1"}
    assert company.zones.count() == 0


def test_named_smtp_backend_delivers_to_the_test_outbox():
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.example.com", port=587, username="sender@example.com",
        password="not-a-password", use_tls=True,
    )
    EmailMessage("Subject", "Body", "sender@example.com", ["to@example.com"],
                 connection=connection).send()

    assert [m.subject for m in mail.outbox] == ["Subject"]


def test_ai_and_imap_settings_are_blank(settings):
    assert settings.ANTHROPIC_API_KEY == ""
    assert settings.PROSPECT_REPLY_IMAP_PASSWORD == ""


def test_connect_to_outside_address_is_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(network_guard.NetworkAccessBlocked, match="203.0.113.7:443"):
            sock.connect(("203.0.113.7", 443))  # TEST-NET-3, documentation range
    finally:
        sock.close()
        network_guard._attempts.clear()  # this test made the attempt on purpose


@pytest.mark.parametrize("host", ["example.com", "10.0.0.5", "2001:db8::1"])
def test_non_loopback_addresses_are_not_local(host):
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    assert not network_guard._is_local(family, (host, 80))


@pytest.mark.parametrize("host", ["127.0.0.1", "127.8.9.10", "localhost", "::1", "::ffff:127.0.0.1"])
def test_loopback_addresses_are_local(host):
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    assert network_guard._is_local(family, (host, 5432))


def test_loopback_connection_is_allowed():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()


def test_a_swallowed_outbound_attempt_still_fails_the_test(tmp_path):
    """Code that catches the error (as the HTTP clients here do) cannot hide the attempt."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_offender.py").write_text(textwrap.dedent("""
        import requests

        def test_calls_an_outside_api():
            try:
                requests.get("http://203.0.113.9/v2", timeout=2)
            except Exception:
                pass  # the code under test hides the failure
    """))
    env = {k: v for k, v in os.environ.items() if k not in ("DJANGO_SETTINGS_MODULE", "DATABASE_URL")}
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(tmp_path / "pytest.ini"),
         "-p", "crm_app.tests.network_guard", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 failed" in result.stdout
    assert "Blocked outbound network connection(s) during this test" in result.stdout
    assert "203.0.113.9:80" in result.stdout
