"""Switch state and settings for mail capture, read at call time (never cached).

Every entry point asks ``capture_state()`` first. While capture is off it
returns a reason and the caller must stop before creating any Gmail client.
"""
from dataclasses import dataclass

from django.conf import settings


DISABLED_FLAG = 'GOOGLE_CAPTURE_ENABLED is off'
DISABLED_NO_DOMAINS = 'CAPTURE_INTERNAL_DOMAINS is empty'
DISABLED_NO_MAILBOX = 'no mailbox is enabled'
DISABLED_MAILBOX = 'this mailbox is not enabled'


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


def capture_state():
    """Global switch: the flag must be on and our own domains must be known.

    Without internal domains every message would look external, so capture
    refuses to run rather than store internal mail.
    """
    if not flag_enabled():
        return CaptureState(False, DISABLED_FLAG)
    if not internal_domains():
        return CaptureState(False, DISABLED_NO_DOMAINS)
    return CaptureState(True)
