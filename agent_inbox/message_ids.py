"""The one rule for how an email is identified in this app.

An activity with ``source_system='gmail'`` (and a proposal whose evidence source
is gmail) stores the message's RFC 822 Message-ID in ``source_ref``, in the same
canonical form the mail-capture app uses, so a purge there reaches the rows here.
"""
import re

MESSAGE_ID_MAX = 500
# Ids the capture app makes for a message without a Message-ID, or for an overlong one.
_CAPTURE_FORMS = re.compile(r'(?:synthetic|long):[0-9a-f]{64}\Z')


def canonical_message_id(value):
    """The canonical Message-ID for ``value``, or None when it is not a plausible one.

    Rule (shared with the mail-capture app; compare the results case-sensitively):
    1. Remove surrounding whitespace.
    2. If the value then starts with ``<`` and ends with ``>``, remove those two
       characters. Nothing else is changed: no case folding, no inner trimming.
    3. The result is accepted when it is 1-500 printable ASCII characters with no
       whitespace and no ``<`` or ``>``, and either contains ``@`` with text on
       both sides of the last ``@`` (``left@right``), or is one of the capture
       app's own forms ``synthetic:<64 hex>`` or ``long:<64 hex>``.
       A Gmail API message id (hex digits, no ``@``) is therefore refused.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) >= 2 and text.startswith('<') and text.endswith('>'):
        text = text[1:-1]
    if not 1 <= len(text) <= MESSAGE_ID_MAX:
        return None
    if any(not ('\x21' <= char <= '\x7e') or char in '<>' for char in text):
        return None
    if _CAPTURE_FORMS.match(text):
        return text
    left, at, right = text.rpartition('@')
    if not at or not left or not right:
        return None
    return text
