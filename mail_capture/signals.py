"""The purge hook other apps subscribe to.

When mail capture purges messages (a never-log rule, a private label, a Gmail
deletion of the last copy), it sends ``mail_purged`` once the purge has
committed::

    from mail_capture.signals import mail_purged

    @receiver(mail_purged)
    def redact(sender, source_system, source_refs, reason, reason_text, **kwargs):
        ...  # void or redact what this app holds for these refs

Arguments:

* ``source_system``: always ``'gmail'``.
* ``source_refs``: a list of canonical refs (``identity.canonical_source_ref``),
  nothing else about the messages. Messages stored under an internal
  ``synthetic:`` key have no canonical ref and are not listed.
* ``reason``: ``'rule'``, ``'label'`` or ``'gmail_deleted'``.
* ``reason_text``: the same reason as a readable sentence (``REASON_TEXT``).

Mail capture never imports a subscriber. A receiver that raises is logged
(by class name only) and does not undo the purge. Unmatched mail is never
stored, so only its hashed key is known and no ref can be sent for it.
"""
import logging

from django.db import transaction
from django.dispatch import Signal


logger = logging.getLogger(__name__)

mail_purged = Signal()

# ``reason`` is a code; ``reason_text`` the same in words, for a receiver that
# stores a human-readable reason.
REASON_TEXT = {
    'rule': 'Removed by a never-log rule in mail capture.',
    'label': 'Marked private in Gmail (CRM private label or a label rule).',
    'gmail_deleted': 'Deleted in Gmail from every captured mailbox.',
}


def send_purged(refs, reason):
    refs = sorted({r for r in refs if r and not r.startswith('synthetic:')})
    if not refs:
        return

    reason_text = REASON_TEXT.get(reason, 'Purged by mail capture.')

    def fire():
        for receiver, result in mail_purged.send_robust(
            sender='mail_capture', source_system='gmail', source_refs=list(refs), reason=reason,
            reason_text=reason_text,
        ):
            if isinstance(result, Exception):
                logger.warning('mail_purged receiver failed: %s', type(result).__name__)

    transaction.on_commit(fire)
