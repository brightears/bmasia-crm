"""Shared input checks and the error type both write surfaces translate.

The services raise ``ServiceError``; the REST views turn it into a response
with the same status and body, and the MCP tools into a JSON string.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone as dt_timezone
from uuid import UUID

from django.utils import timezone

KEY_RE = re.compile(r'[A-Za-z0-9:._-]{8,200}\Z')
BATCH_RE = re.compile(r'[A-Za-z0-9:._-]{1,100}\Z')
FUTURE_TOLERANCE = timedelta(minutes=10)
EARLIEST = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)


class ServiceError(Exception):
    """A refused request: HTTP status, a stable code and a one-line detail."""

    def __init__(self, http_status, code, detail, **extra):
        super().__init__(detail)
        self.status = http_status
        self.code = code
        self.detail = detail
        self.extra = extra

    def body(self):
        return {'detail': self.detail, 'code': self.code, **self.extra}


def bad(detail, **extra):
    return ServiceError(400, 'invalid', detail, **extra)


def unprocessable(code, detail, **extra):
    return ServiceError(422, code, detail, **extra)


# ------------------------------------------------------------------ structure


def strict_object(body, allowed, required=()):
    if not isinstance(body, dict):
        raise bad('Body must be a JSON object')
    unknown = sorted(str(key) for key in set(body) - set(allowed))
    if unknown:
        raise bad('Unknown keys: ' + ', '.join(unknown))
    missing = sorted(key for key in required if body.get(key) in (None, ''))
    if missing:
        raise bad('Missing keys: ' + ', '.join(missing))
    return body


def payload_sha256(body):
    canonical = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ------------------------------------------------------------------ text


# Characters refused in single-line values: they change the order or the look of
# text without being seen. Direction embeddings, overrides and isolates, direction
# marks, the Arabic letter mark, zero-width space, word joiner, invisible
# operators, the byte-order mark, soft hyphen, Mongolian vowel separator and the
# interlinear annotation characters.
REFUSED_FORMAT_CHARACTERS = frozenset(
    [chr(c) for c in range(0x202A, 0x202F)] + [chr(c) for c in range(0x2066, 0x206A)]
    + ['‎', '‏', '؜', '​', '⁠', '⁡', '⁢', '⁣', '⁤',
       '﻿', '­', '᠎', '￹', '￺', '￻']
)
# Zero-width non-joiner and joiner: needed inside words of some scripts and in
# emoji sequences (a family, a profession), never between ASCII characters.
_JOINERS = frozenset('‌‍')
_TAG_FIRST, _TAG_LAST, _TAG_CANCEL, _BLACK_FLAG = 0xE0020, 0xE007E, 0xE007F, 0x1F3F4


def _joinable(char):
    if ord(char) <= 0x7F:
        return False
    return unicodedata.category(char)[0] in 'LMS' or 0x1F3FB <= ord(char) <= 0x1F3FF


def _joiner_allowed(text, index):
    """A joiner sits between two non-ASCII letters, marks or symbols (emoji)."""
    if index == 0 or index == len(text) - 1:
        return False
    return _joinable(text[index - 1]) and _joinable(text[index + 1])


def _tag_allowed(text, index):
    """Tag characters only inside a subdivision flag: black flag, tags, cancel tag."""
    previous = ord(text[index - 1]) if index else 0
    in_sequence = previous == _BLACK_FLAG or _TAG_FIRST <= previous <= _TAG_LAST
    code = ord(text[index])
    if code == _TAG_CANCEL:
        return _TAG_FIRST <= previous <= _TAG_LAST
    return in_sequence


def has_control(text, allow_newlines=False, allow_format=False):
    """True when the text holds characters that change how it looks or reads without showing.

    Always refused: control characters (tabs and line breaks only with
    allow_newlines), surrogates and line/paragraph separators. Unless
    allow_format (used for bodies and quotes copied verbatim from a source),
    also refused: private-use and unassigned code points, the characters in
    REFUSED_FORMAT_CHARACTERS, a joiner that is not between two non-ASCII letters,
    marks or emoji, and tag characters outside a subdivision flag. Other format
    characters (emoji sequences, Thai, Arabic and Indic text) are kept.
    """
    for index, char in enumerate(text):
        if allow_newlines and char in '\n\r\t':
            continue
        category = unicodedata.category(char)
        if category in ('Cc', 'Cs', 'Zl', 'Zp'):
            return True
        if allow_format:
            continue
        if category in ('Co', 'Cn') or char in REFUSED_FORMAT_CHARACTERS:
            return True
        if char in _JOINERS and not _joiner_allowed(text, index):
            return True
        if _TAG_FIRST <= ord(char) <= _TAG_CANCEL and not _tag_allowed(text, index):
            return True
    return False


_HOMOGLYPH_SCRIPTS = frozenset({'CYRILLIC', 'GREEK'})


def mixed_script(text):
    """Whether a value mixes scripts in a way that can mislead a reader.

    Latin letters together with Cyrillic or Greek letters (look-alikes), or
    right-to-left letters together with left-to-right letters (the display order
    can differ from the stored order). Thai or Indic text next to Latin, as in
    an address, is not flagged.
    """
    scripts, rtl, ltr = set(), False, False
    for char in text or '':
        if not unicodedata.category(char).startswith('L'):
            continue
        bidi = unicodedata.bidirectional(char)
        rtl = rtl or bidi in ('R', 'AL')
        ltr = ltr or bidi == 'L'
        name = unicodedata.name(char, '')
        scripts.add(name.split(' ', 1)[0])
    return ('LATIN' in scripts and bool(scripts & _HOMOGLYPH_SCRIPTS)) or (rtl and ltr)


def optional_str(body, key):
    value = body.get(key)
    if value is None:
        return ''
    if not isinstance(value, str):
        raise bad(f'{key} must be a string')
    return value


def text_field(body, key, max_length, *, required=False, multiline=False, allow_format=False):
    """A plain-text value: capped, without control or invisible characters (newlines only if multiline)."""
    value = optional_str(body, key)
    if multiline:
        value = value.replace('\r\n', '\n').replace('\r', '\n')
    value = value.strip()
    if required and not value:
        raise bad(f'{key} is required')
    if len(value) > max_length:
        raise bad(f'{key} must be at most {max_length} characters')
    if has_control(value, allow_newlines=multiline, allow_format=allow_format):
        if multiline:
            raise bad(f'{key} must not contain control or invisible characters other than newlines and tabs')
        raise bad(f'{key} must be a single line without control or invisible characters')
    return value


def token_field(body, key, max_length):
    value = optional_str(body, key)
    if len(value) > max_length:
        raise bad(f'{key} must be at most {max_length} characters')
    if any(char.isspace() for char in value) or has_control(value):
        raise bad(f'{key} must not contain whitespace or control characters')
    return value


def source_ref_field(body, key, source_system, max_length):
    """A source reference; for gmail the canonical Message-ID (agent_inbox.message_ids)."""
    if source_system == 'gmail' and body.get(key) not in (None, ''):
        from agent_inbox.message_ids import canonical_message_id, gmail_ref_problem

        canonical = canonical_message_id(optional_str(body, key))
        problem = gmail_ref_problem(canonical)
        if problem:
            raise bad(f'{key} for gmail must be the message\'s RFC 822 Message-ID, '
                      f'for example <CAB12345@mail.example.com>: this one {problem}')
        return canonical
    return token_field(body, key, max_length)


GMAIL_HOST = 'mail.google.com'
_DEFAULT_PORTS = {'http': 80, 'https': 443}
_HOST_LABEL_RE = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')


def checked_url(value, source_system=''):
    """``(url, None)`` with the URL rebuilt from its checked parts, or ``(None, reason)``.

    Accepted: scheme exactly http or https; no user name or password (no @ in
    the host part); a host name that is an ASCII domain after IDNA, with at
    least two labels, not an IP address and not localhost; no port other than
    the scheme's default (dropped when given). For a gmail source the host must
    be exactly mail.google.com. What is stored is the rebuilt URL, so what a
    reviewer sees is what was checked.
    """
    from urllib.parse import urlsplit, urlunsplit
    import ipaddress

    scheme, sep, _rest = value.partition(':')
    if not sep or scheme not in _DEFAULT_PORTS or not value.startswith(scheme + '://'):
        return None, 'must be an http or https URL'
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None, 'is not a valid URL'
    netloc = parts.netloc
    if '@' in netloc or parts.username is not None or parts.password is not None:
        return None, 'must not contain a user name or password'
    if '[' in netloc or ']' in netloc:
        return None, 'must name a host, not an IP address'
    host = parts.hostname or ''
    if netloc.count(':') > 1 or (':' in netloc and port is None):
        return None, 'has an invalid port'
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        return None, 'must use the default port'
    try:
        ascii_host = host.encode('idna').decode('ascii') if not host.isascii() else host
    except UnicodeError:
        return None, 'has a host name that is not a valid domain'
    ascii_host = ascii_host.lower()
    try:
        ipaddress.ip_address(ascii_host)
        return None, 'must name a host, not an IP address'
    except ValueError:
        pass
    labels = ascii_host.split('.')
    if len(ascii_host) > 253 or len(labels) < 2 or not all(_HOST_LABEL_RE.match(label) for label in labels):
        return None, 'has a host name that is not a valid domain'
    if labels[-1].isdigit():
        return None, 'must name a host, not an IP address'
    if labels[-1] == 'localhost':
        return None, 'must not point at localhost'
    if source_system == 'gmail' and ascii_host != GMAIL_HOST:
        return None, f'must be a {GMAIL_HOST} link for a gmail source'
    return urlunsplit((scheme, ascii_host, parts.path, parts.query, parts.fragment)), None


def url_field(body, key, max_length, source_system=''):
    value = token_field(body, key, max_length)
    if not value:
        return value
    url, reason = checked_url(value, source_system)
    if reason:
        raise bad(f'{key} {reason}')
    if len(url) > max_length:
        raise bad(f'{key} must be at most {max_length} characters')
    return url


def url_warnings(field, value, source_system=''):
    """Reviewer warnings for a stored link: a punycode host, or a link that would now be refused."""
    if not value:
        return []
    url, reason = checked_url(value, source_system)
    if reason:
        return [{'field': field, 'code': 'url_not_accepted',
                 'detail': f'This link {reason}; it was stored before links were checked. Do not follow it.'}]
    from urllib.parse import urlsplit
    if any(label.startswith('xn--') for label in (urlsplit(url).hostname or '').split('.')):
        return [{'field': field, 'code': 'url_punycode_host',
                 'detail': 'The link\'s host is written in punycode (xn--) and may imitate another name; '
                           'check where it really points'}]
    return []


def choice(body, key, choices, default=None):
    value = body.get(key, default)
    if value is None:
        value = default
    allowed = [c[0] for c in choices] if choices and isinstance(choices[0], tuple) else list(choices)
    if value not in allowed:
        raise bad(f'{key} must be one of: ' + ', '.join(allowed))
    return value


def uuid_value(value, key):
    if not isinstance(value, str):
        raise bad(f'{key} must be a UUID string')
    try:
        return UUID(value)
    except ValueError:
        raise bad(f'{key} must be a UUID string') from None


def optional_uuid(body, key):
    value = body.get(key)
    if value in (None, ''):
        return None
    return uuid_value(value, key)


def aware_datetime(value, key):
    if not isinstance(value, str):
        raise bad(f'{key} must be an ISO 8601 string with a timezone')
    raw = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise bad(f'{key} must be an ISO 8601 string with a timezone') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise bad(f'{key} must include a timezone')
    return parsed


def past_datetime(value, key):
    parsed = aware_datetime(value, key)
    if parsed > timezone.now() + FUTURE_TOLERANCE:
        raise bad(f'{key} is in the future')
    if parsed < EARLIEST:
        raise bad(f'{key} is before 2000')
    return parsed


def key_field(body, key='idempotency_key'):
    value = body.get(key)
    if not isinstance(value, str) or not KEY_RE.fullmatch(value):
        raise bad(f'{key} must be 8-200 characters of [A-Za-z0-9:._-]')
    return value


def batch_field(body, key='batch_key'):
    value = optional_str(body, key)
    if value and not BATCH_RE.fullmatch(value):
        raise bad(f'{key} must be 1-100 characters of [A-Za-z0-9:._-]')
    return value


# ------------------------------------------------------------------ verbatim evidence


def normalise_for_quote(text):
    """NFC, and every run of whitespace (including line breaks) as one space.

    Line wrapping and spacing differ between a stored body and a quote copied
    from it; letters, digits, punctuation and case must match exactly.
    """
    return ' '.join(unicodedata.normalize('NFC', text or '').split())


def quote_occurs_in(quote, text):
    needle = normalise_for_quote(quote)
    return bool(needle) and needle in normalise_for_quote(text)
