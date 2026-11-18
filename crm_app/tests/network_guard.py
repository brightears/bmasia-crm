"""Keep the test suite off the network.

Loaded for every run through ``-p crm_app.tests.network_guard`` in pytest.ini.

1. Socket guard. Any socket ``connect``/``connect_ex`` to an address that is
   not loopback (127.0.0.0/8, ::1, "localhost") or a Unix socket raises
   ``NetworkAccessBlocked``. The attempt is also recorded, and the test that
   made it fails afterwards even if the code under test caught the exception
   (several services wrap their HTTP calls in ``except Exception``). Local
   database connections are unaffected.

2. Stubs at the outbound seams, so ordinary tests never reach the guard:
   - Soundtrack Your Brand: ``SoundtrackAPIService._make_graphql_query`` (the
     only method that sends a request) returns None, which the service treats
     as "no data". The Company post-save signal therefore syncs nothing.
     Calls are recorded in the ``soundtrack_calls`` fixture.
   - SMTP: code that asks for the SMTP backend by name
     (``get_connection(backend='django.core.mail.backends.smtp.EmailBackend')``)
     gets Django's in-memory backend, like the default connection already does
     under the test runner. Messages land in ``django.core.mail.outbox``.
   - Anthropic and the prospect-reply IMAP mailbox: their settings are blanked,
     so the services take their "not configured" path.
"""
from __future__ import annotations

import ipaddress
import socket
import traceback

import pytest

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}

_attempts: list[str] = []
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class NetworkAccessBlocked(RuntimeError):
    """Raised when a test tries to open a connection to a non-loopback address."""


def _is_local(family, address) -> bool:
    if family == getattr(socket, "AF_UNIX", object()):
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).split("%", 1)[0]  # drop an IPv6 scope id
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # an unresolved host name other than localhost
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or bool(mapped and mapped.is_loopback)


def _describe(address) -> str:
    if isinstance(address, tuple) and len(address) >= 2:
        return f"{address[0]}:{address[1]}"
    return repr(address)


def _block(sock, address):
    target = _describe(address)
    caller = "".join(traceback.format_stack(limit=12)[:-2])
    _attempts.append(f"{target}\n{caller}")
    raise NetworkAccessBlocked(
        f"Test tried to open a network connection to {target}. "
        "Tests must not reach outside services; stub the client instead "
        "(see crm_app/tests/network_guard.py)."
    )


def _guarded_connect(self, address):
    if not _is_local(self.family, address):
        _block(self, address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if not _is_local(self.family, address):
        _block(self, address)
    return _real_connect_ex(self, address)


def pytest_configure(config):
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex


def pytest_unconfigure(config):
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    _attempts.clear()
    result = yield
    if _attempts:
        attempts = list(_attempts)
        _attempts.clear()
        pytest.fail(
            "Blocked outbound network connection(s) during this test:\n\n"
            + "\n".join(attempts)
            + "\nTests must not reach outside services; stub the client instead "
            "(see crm_app/tests/network_guard.py).",
            pytrace=False,
        )
    return result


def _crm_app_loaded() -> bool:
    try:
        from django.apps import apps
    except ImportError:
        return False
    return apps.ready and apps.is_installed("crm_app")


@pytest.fixture
def soundtrack_calls():
    """Queries the stubbed Soundtrack client received in this test: (query, variables)."""
    return []


@pytest.fixture(autouse=True)
def _stub_outbound_services(request, monkeypatch):
    if not _crm_app_loaded():
        yield
        return

    from django.conf import settings
    from django.core.mail.backends import locmem, smtp

    calls = request.getfixturevalue("soundtrack_calls")

    try:
        from crm_app.services.soundtrack_api import SoundtrackAPIService
    except ImportError:
        SoundtrackAPIService = None
    if SoundtrackAPIService is not None:
        def _no_soundtrack(self, query, variables=None):
            calls.append((query, variables))
            return None

        monkeypatch.setattr(SoundtrackAPIService, "_make_graphql_query", _no_soundtrack)

    monkeypatch.setattr(smtp, "EmailBackend", locmem.EmailBackend)

    for name in ("ANTHROPIC_API_KEY", "PROSPECT_REPLY_IMAP_PASSWORD"):
        if hasattr(settings, name):
            monkeypatch.setattr(settings, name, "")
    yield
