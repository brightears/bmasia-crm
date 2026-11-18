"""Removing captured mail: never-log rules applied to stored mail, private
labels, and expiry of the unmatched queue.

Purge mechanics (decided for PR-A):

* A purge deletes the ``MailMessage`` row; its copies, participants and
  message-level matches go with it (CASCADE). No tombstone is kept, so no
  header of a purged message survives. The rule itself stops the message from
  being captured again.
* The conversation is then recomputed from its remaining messages, and
  deleted when none remain.
* Rules reach stored mail in two ways: ``enforce_rules`` runs at the start of
  every non-dry sync run, and the admin calls it when a rule is saved.
* Label rules (and the built-in ``CRM private`` label) work per copy: the
  labelled copy is dropped, and the message is purged only when no copy is
  left. Labels added later arrive through history and are handled by the sync
  engine with the same functions.
"""
from django.db import transaction
from django.db.models import Max, Min, Q

from .models import (
    CaptureRule, MailboxCopy, MailConversation, MailMessage, MailParticipant,
    UnmatchedSender,
)
from .rules import ACTION_HEADERS_ONLY, ACTION_PRIVATE, ACTION_SKIP


def _participant_filter(rule):
    if rule.kind == 'address':
        return Q(address=rule.value)
    return Q(domain=rule.value) | Q(domain__endswith='.' + rule.value)


def refresh_conversations(conversation_ids):
    """Recompute counts and times; delete conversations without messages."""
    deleted = 0
    for conversation in MailConversation.objects.filter(pk__in=set(conversation_ids)):
        messages = MailMessage.objects.filter(conversation=conversation)
        stats = messages.aggregate(first=Min('sent_at'), last=Max('sent_at'))
        count = messages.count()
        if count == 0:
            conversation.delete()
            deleted += 1
            continue
        conversation.message_count = count
        conversation.first_message_at = stats['first']
        conversation.last_message_at = stats['last']
        conversation.last_inbound_at = messages.filter(direction='inbound').aggregate(
            v=Max('sent_at'))['v']
        conversation.last_outbound_at = messages.filter(direction='outbound').aggregate(
            v=Max('sent_at'))['v']
        conversation.save(update_fields=[
            'message_count', 'first_message_at', 'last_message_at',
            'last_inbound_at', 'last_outbound_at', 'updated_at',
        ])
    return deleted


def purge_messages(message_ids):
    """Delete messages with everything attached; returns how many went."""
    message_ids = set(message_ids)
    if not message_ids:
        return 0
    conversation_ids = set(
        MailMessage.objects.filter(pk__in=message_ids).values_list('conversation_id', flat=True)
    )
    count = MailMessage.objects.filter(pk__in=message_ids).count()
    MailMessage.objects.filter(pk__in=message_ids).delete()
    refresh_conversations(conversation_ids)
    return count


def purge_orphans(message_ids):
    """Purge those of ``message_ids`` that no mailbox holds any more."""
    message_ids = set(message_ids)
    if not message_ids:
        return 0
    still_held = set(
        MailboxCopy.objects.filter(message_id__in=message_ids).values_list('message_id', flat=True)
    )
    return purge_messages(message_ids - still_held)


def drop_copies(copy_ids):
    """Delete copies and purge any message left without a copy."""
    copy_ids = set(copy_ids)
    if not copy_ids:
        return 0
    message_ids = set(
        MailboxCopy.objects.filter(pk__in=copy_ids).values_list('message_id', flat=True)
    )
    MailboxCopy.objects.filter(pk__in=copy_ids).delete()
    return purge_orphans(message_ids)


def enforce_rules(rules=None):
    """Apply address and domain rules to mail already stored.

    Returns counts: purged messages, dropped copies, cleared bodies and
    removed queue rows. Label rules are applied per mailbox by
    ``enforce_label_rules`` because label ids differ between mailboxes.
    """
    rules = list(CaptureRule.objects.all() if rules is None else rules)
    counts = {'purged': 0, 'copies_dropped': 0, 'bodies_cleared': 0, 'queue_removed': 0}
    with transaction.atomic():
        for rule in rules:
            if rule.kind not in ('address', 'domain'):
                continue
            message_ids = set(
                MailParticipant.objects.filter(_participant_filter(rule))
                .values_list('message_id', flat=True)
            )
            if rule.action in (ACTION_SKIP, ACTION_PRIVATE):
                if rule.scope == 'mailbox':
                    copies = MailboxCopy.objects.filter(
                        mailbox_id=rule.mailbox_id, message_id__in=message_ids,
                    ).values_list('pk', flat=True)
                    copy_ids = set(copies)
                    counts['copies_dropped'] += len(copy_ids)
                    counts['purged'] += drop_copies(copy_ids)
                else:
                    counts['purged'] += purge_messages(message_ids)
                    queue = UnmatchedSender.objects.filter(
                        Q(address=rule.value) if rule.kind == 'address'
                        else Q(domain=rule.value) | Q(domain__endswith='.' + rule.value)
                    )
                    counts['queue_removed'] += queue.count()
                    queue.delete()
            elif rule.action == ACTION_HEADERS_ONLY:
                qs = MailMessage.objects.filter(pk__in=message_ids)
                counts['bodies_cleared'] += qs.filter(body_text__isnull=False).count()
                qs.update(
                    body_text=None, body_sha256='', capture_state='headers',
                    headers_only_rule=True,
                )
    return counts


def enforce_label_rules(mailbox, private_ids, headers_only_ids):
    """Drop this mailbox's copies that carry a private label; clear bodies of
    messages whose copy carries a headers-only label. Scans the mailbox's
    copies, so the sync engine calls it only when the label set changed."""
    counts = {'purged': 0, 'copies_dropped': 0, 'bodies_cleared': 0}
    if not private_ids and not headers_only_ids:
        return counts
    drop, clear = set(), set()
    for pk, message_id, labels in MailboxCopy.objects.filter(mailbox=mailbox).values_list(
        'pk', 'message_id', 'label_ids',
    ).iterator():
        labels = set(labels or ())
        if labels & private_ids:
            drop.add(pk)
        elif labels & headers_only_ids:
            clear.add(message_id)
    with transaction.atomic():
        counts['copies_dropped'] = len(drop)
        counts['purged'] = drop_copies(drop)
        if clear:
            qs = MailMessage.objects.filter(pk__in=clear)
            counts['bodies_cleared'] = qs.filter(body_text__isnull=False).count()
            qs.update(body_text=None, body_sha256='', capture_state='headers', headers_only_rule=True)
    return counts


def purge_expired_unmatched(now):
    """Delete open queue rows past their expiry (30 days after last seen)."""
    qs = UnmatchedSender.objects.filter(status='open', expires_at__lt=now)
    count = qs.count()
    qs.delete()
    return count
