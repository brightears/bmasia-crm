"""The one rule for how an email is identified in this app.

An activity with ``source_system='gmail'`` (and a proposal whose evidence source
is gmail) stores the message's canonical Message-ID in ``source_ref``. The rule is
the mail-capture app's ``identity.canonical_source_ref`` (``parse.normalise_message_id``),
reproduced here without importing that app, so a purge there reaches the rows
here. ``tests/test_message_ids.py`` holds a shared table of cases; both
implementations must give the same result for every row.
"""
import hashlib
import re

MESSAGE_ID_MAX = 500
_UNFOLD_LIMIT = 4096
_FOLD_RE = re.compile(r'\r?\n[ \t]*')
_ANGLE_ID_RE = re.compile(r'<([^<>\s]+)>')
_SURROGATE_RE = re.compile('[\ud800-\udfff]')
# A Gmail API message id: per mailbox, never a Message-ID.
_GMAIL_API_ID = re.compile(r'[0-9a-f]{16}\Z')


def _hash_id(prefix, raw):
    return f'{prefix}:' + hashlib.sha256(raw.encode('utf-8', 'replace')).hexdigest()


def canonical_message_id(value):
    """The canonical reference for a Message-ID header or a stored reference; '' when there is none.

    1. Cut to 4096 characters, unfold (CRLF/LF followed by spaces or tabs becomes
       one space; other line breaks become spaces), remove NUL, replace lone
       surrogates with U+FFFD, trim.
    2. If it contains a ``<...>`` token with no whitespace inside, take the first
       such token without its angle brackets. Case is kept.
    3. Else, if it has no whitespace, take it with angle brackets stripped from
       both ends.
    4. Else, or if that leaves nothing, ``raw:`` + the hex SHA-256 of the cleaned value.
    5. A result longer than 500 characters becomes ``long:`` + its hex SHA-256.
    6. A capture-internal ``synthetic:`` key, or an empty value, gives ''.
    It is idempotent, so a raw header or a stored reference may be passed.
    """
    if value is None:
        return ''
    raw = str(value)[:_UNFOLD_LIMIT]
    raw = _FOLD_RE.sub(' ', raw).replace('\r', '').replace('\n', ' ').strip()
    raw = _SURROGATE_RE.sub('�', raw.replace('\x00', '')).strip()
    if not raw:
        return ''
    found = _ANGLE_ID_RE.search(raw)
    if found:
        token = found.group(1).strip()
    elif not any(char.isspace() for char in raw):
        token = raw.strip('<>').strip()
    else:
        return _hash_id('raw', raw)
    if not token:
        return _hash_id('raw', raw)
    if len(token) > MESSAGE_ID_MAX:
        return _hash_id('long', token)
    if token.startswith('synthetic:'):
        return ''
    return token


def gmail_ref_problem(canonical):
    """Why a canonical reference cannot be recorded here, or None.

    Recording is stricter than the shared rule: an empty reference and a Gmail API
    message id (16 hex digits, which identifies a copy in one mailbox, not the
    message) are refused.
    """
    if not canonical:
        return 'is not a Message-ID'
    if _GMAIL_API_ID.match(canonical):
        return 'looks like a Gmail API id, which names a copy in one mailbox; use the Message-ID header'
    return None
