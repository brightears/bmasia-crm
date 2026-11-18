"""Switch state and settings for mail capture, read at call time (never cached).

Every entry point asks ``capture_state()`` first. While capture is off it
returns a reason and the caller must stop before creating any Gmail client.
"""
from dataclasses import dataclass

from django.conf import settings


DISABLED_FLAG = 'GOOGLE_CAPTURE_ENABLED is off'
DISABLED_NO_DOMAINS = 'CAPTURE_INTERNAL_DOMAINS is empty'
DISABLED_BAD_DOMAINS = 'CAPTURE_INTERNAL_DOMAINS holds a public suffix or a freemail domain'
DISABLED_NO_MAILBOX = 'no mailbox is enabled'
DISABLED_MAILBOX = 'this mailbox is not enabled'

DEFAULT_RUN_RETENTION_DAYS = 90
DEFAULT_ACCESS_LOG_RETENTION_DAYS = 365


@dataclass(frozen=True)
class CaptureState:
    enabled: bool
    reason: str = ''


def _clean_list(values):
    out = []
    for value in values or ():
        value = str(value).strip().lower().lstrip('@').rstrip('.')
        if value and value not in out:
            out.append(value)
    return tuple(out)


def internal_domains():
    """The company's own mail domains, lower-case, from settings."""
    return _clean_list(getattr(settings, 'CAPTURE_INTERNAL_DOMAINS', ()))


def internal_addresses():
    """Single internal sending addresses outside the internal domains."""
    return _clean_list(getattr(settings, 'CAPTURE_INTERNAL_ADDRESSES', ()))


def flag_enabled():
    return bool(getattr(settings, 'GOOGLE_CAPTURE_ENABLED', False))


def _days(name, default):
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def run_retention_days():
    return _days('CAPTURE_RUN_RETENTION_DAYS', DEFAULT_RUN_RETENTION_DAYS)


def access_log_retention_days():
    return _days('CAPTURE_ACCESS_LOG_RETENTION_DAYS', DEFAULT_ACCESS_LOG_RETENTION_DAYS)


def domains_state():
    """Our own domains must be known, and none may be a public suffix or a
    freemail domain (that would make every customer there look internal)."""
    from .rules import internal_domain_problem
    domains = internal_domains()
    if not domains:
        return CaptureState(False, DISABLED_NO_DOMAINS)
    if any(internal_domain_problem(d) for d in domains):
        return CaptureState(False, DISABLED_BAD_DOMAINS)
    return CaptureState(True)


def capture_state():
    """Global switch: the flag must be on and our own domains must be sound."""
    if not flag_enabled():
        return CaptureState(False, DISABLED_FLAG)
    return domains_state()
