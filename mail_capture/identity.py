"""The one identity other apps use to refer to an email: pure, no imports
from other apps, no database.

``source_system='gmail'`` with ``source_ref=canonical_source_ref(<Message-ID>)``
names the same email in every mailbox (Gmail's own message and thread ids are
per mailbox and must not be used as a reference). It equals
``MailMessage.rfc_message_id``, so another app can find, de-duplicate against
and redact what it holds about a captured message.

The rule, exactly (``parse.normalise_message_id``):

1. Unfold the header (CRLF/LF followed by spaces or tabs becomes one space),
   remove NUL characters, replace lone surrogates with U+FFFD, trim.
2. If it contains a ``<...>`` token with no whitespace inside, take the first
   such token without its angle brackets. Case is kept: Message-IDs are
   case-sensitive.
3. Else, if the value has no whitespace, take it with any angle brackets
   stripped from both ends.
4. Else (a malformed id such as ``<a b@x.test>``) the ref is
   ``raw:`` + the hex SHA-256 of the cleaned value.
5. A result longer than 500 characters becomes ``long:`` + its hex SHA-256.
6. An empty header gives ``''``: there is no canonical ref. (Captured mail
   without a Message-ID is stored under a ``synthetic:`` key that is internal
   to mail capture and must not be used by other apps.)

The function is idempotent: applying it to its own output returns the same
value, so callers may pass either a raw header or a stored ref.
"""
from .parse import normalise_message_id


SOURCE_SYSTEM = 'gmail'


def canonical_source_ref(value):
    """Canonical ``source_ref`` for ``source_system='gmail'`` (rule above)."""
    ref = normalise_message_id(value)
    if ref.startswith('synthetic:'):
        return ''
    return ref
