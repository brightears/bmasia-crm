"""Removing captured mail: never-log rules applied to stored mail, private
labels, Gmail deletions, queue expiry and record retention.

Purge mechanics:

* A purge deletes the ``MailMessage`` row; its copies, participants and
  message-level matches go with it (CASCADE). No tombstone is kept.
* Everything else that can hold its content is cleaned in the same
  transaction: its key and subject leave every unmatched-queue row (rows left
  empty are deleted); surviving messages' References / In-Reply-To and a
  conversation key equal to the purged Message-ID are replaced by an opaque
  ``purged:<hash>`` token; the conversation's subject, counts and clocks are
  recomputed from what remains, and an empty conversation is deleted.
  ``CaptureRun``, ``CapturePurge`` and the access log hold counts only.
* Other apps are told through ``signals.mail_purged`` with the canonical
  Message-IDs only, after commit.
* Rules reach stored mail only after a person confirmed them
  (``CaptureRule.purge_state``), in chunks of at most ``PURGE_CAP`` messages
  per rule per call; the rest follows on later runs. Each chunk writes one
  ``CapturePurge`` row. Rules that are not confirmed, or already done, cost
  nothing on a run: no table is scanned for them.
* Label rules (and the built-in ``CRM private`` label) work per copy: the
  labelled copy is dropped, and the message is purged when no copy is left.
  A Gmail deletion of the last copy purges the message too.
"""
import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Min, Q
from django.utils import timezone

from . import conf
from .models import (
    CapturePurge, CaptureRule, CaptureRun, MailboxAccessLog, MailboxCopy, MailConversation,
    MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from .parse import normalise_subject
from .rules import ACTION_HEADERS_ONLY, DROP_ACTIONS, rule_problem
from .signals import send_purged


PURGE_CAP = 500
QUEUE_KEY_BATCH = 50


def message_key(rfc_message_id):
    """The hashed key the unmatched queue stores for a message."""
    return hashlib.sha256((rfc_message_id or '').encode('utf-8', 'replace')).hexdigest()[:16]


def purged_token(rfc_message_id):
    return 'purged:' + hashlib.sha256((rfc_message_id or '').encode('utf-8', 'replace')).hexdigest()[:32]


def _empty_counts():
    return {'messages': 0, 'copies': 0, 'conversations': 0, 'queue_rows': 0, 'queue_samples': 0,
            'bodies_cleared': 0}


def _add(total, part):
    for key, value in part.items():
        total[key] = total.get(key, 0) + value
    return total


# --- the unmatched queue ------------------------------------------------------

def _strip_row(row, keys, mailbox=None):
    """Remove the given message keys (from one mailbox, or all) from a queue
    row. Returns (row deleted, samples removed)."""
    def hit(key, box):
        return key in keys and (mailbox is None or box == mailbox)

    pairs = [p for p in (row.message_keys or []) if isinstance(p, (list, tuple)) and len(p) == 2]
    samples = [s for s in (row.samples or []) if isinstance(s, dict)]
    kept_pairs = [p for p in pairs if not hit(p[0], p[1])]
    kept_keys = {p[0] for p in kept_pairs}
    kept_samples = [s for s in samples if not hit(s.get('k'), s.get('m')) and s.get('k') in kept_keys]
    removed = len(samples) - len(kept_samples)
    if not kept_pairs:
        row.delete()
        return True, removed
    if len(kept_pairs) != len(pairs) or removed:
        row.message_keys = kept_pairs
        row.samples = kept_samples
        row.message_count = len({p[0] for p in kept_pairs})
        row.mailboxes = sorted({p[1] for p in kept_pairs})
        row.save(update_fields=['message_keys', 'samples', 'message_count', 'mailboxes', 'updated_at'])
    return False, removed


def scrub_queue(keys, mailbox=None):
    """Remove these message keys from every queue row that mentions them."""
    keys = set(keys)
    counts = {'queue_rows': 0, 'queue_samples': 0}
    key_list = sorted(keys)
    for start in range(0, len(key_list), QUEUE_KEY_BATCH):
        chunk = key_list[start:start + QUEUE_KEY_BATCH]
        query = Q()
        for key in chunk:
            query |= Q(message_keys__icontains=key) | Q(samples__icontains=key)
        for row in UnmatchedSender.objects.select_for_update().filter(query).order_by('address'):
            deleted, removed = _strip_row(row, keys, mailbox)
            counts['queue_rows'] += int(deleted)
            counts['queue_samples'] += removed
    return counts


def _queue_filter(rule):
    if rule.kind == 'address':
        return _address_q(rule.value, 'address')
    return Q(domain=rule.value) | Q(domain__endswith='.' + rule.value)


def _address_q(value, field):
    """The address and its plus-addressed variants, the same way capture
    compares them (``parse.match_key``)."""
    query = Q(**{field: value})
    if '@' in value and '+' not in value.split('@', 1)[0]:
        local, domain = value.split('@', 1)
        query |= Q(**{f'{field}__startswith': local + '+', f'{field}__endswith': '@' + domain})
    return query


def _participant_filter(rule):
    if rule.kind == 'address':
        return _address_q(rule.value, 'address')
    return Q(domain=rule.value) | Q(domain__endswith='.' + rule.value)


def queue_rows_for_rule(rule):
    return UnmatchedSender.objects.filter(_queue_filter(rule))


def _purge_queue_for_rule(rule):
    """Queue rows of the rule's address or domain go, and so does every
    sample of the same messages in other rows."""
    counts = {'queue_rows': 0, 'queue_samples': 0}
    mailbox = rule.mailbox.email if rule.scope == 'mailbox' and rule.mailbox_id else None
    keys = set()
    for row in queue_rows_for_rule(rule).select_for_update().order_by('address'):
        pairs = [p for p in (row.message_keys or []) if isinstance(p, (list, tuple)) and len(p) == 2]
        keys.update(p[0] for p in pairs if mailbox is None or p[1] == mailbox)
    if keys:
        _add(counts, scrub_queue(keys, mailbox))
    return counts


# --- conversations and references ---------------------------------------------

def refresh_conversations(conversation_ids):
    """Recompute counts, clocks and the subject; delete conversations
    without messages. Returns how many were deleted."""
    deleted = 0
    for conversation in MailConversation.objects.filter(pk__in=set(conversation_ids)):
        messages = MailMessage.objects.filter(conversation=conversation)
        count = messages.count()
        if count == 0:
            conversation.delete()
            deleted += 1
            continue
        stats = messages.aggregate(first=Min('sent_at'), last=Max('sent_at'))
        earliest = messages.order_by('sent_at').values_list('subject', flat=True).first() or ''
        conversation.message_count = count
        conversation.first_message_at = stats['first']
        conversation.last_message_at = stats['last']
        conversation.last_inbound_at = messages.filter(direction='inbound').aggregate(
            v=Max('sent_at'))['v']
        conversation.last_outbound_at = messages.filter(direction='outbound').aggregate(
            v=Max('sent_at'))['v']
        conversation.last_claimed_internal_at = messages.filter(direction='claimed_internal').aggregate(
            v=Max('sent_at'))['v']
        conversation.subject_normalised = normalise_subject(earliest)
        conversation.save(update_fields=[
            'message_count', 'first_message_at', 'last_message_at', 'last_inbound_at',
            'last_outbound_at', 'last_claimed_internal_at', 'subject_normalised', 'updated_at',
        ])
    return deleted


def _rewrite_references(purged_ids, conversation_ids):
    """Replace purged Message-IDs where surviving rows still name them."""
    purged_ids = set(purged_ids)
    tokens = {rid: purged_token(rid) for rid in purged_ids}
    for message in MailMessage.objects.filter(conversation_id__in=conversation_ids):
        changed = False
        refs = list(message.references or [])
        if any(r in purged_ids for r in refs):
            message.references = [tokens.get(r, r) for r in refs]
            changed = True
        if message.in_reply_to in purged_ids:
            message.in_reply_to = tokens[message.in_reply_to]
            changed = True
        if changed:
            message.save(update_fields=['references', 'in_reply_to', 'updated_at'])
    for conversation in MailConversation.objects.filter(conversation_key__in=purged_ids):
        token = tokens[conversation.conversation_key]
        existing = MailConversation.objects.filter(conversation_key=token).first()
        if existing is None:
            conversation.conversation_key = token
            conversation.save(update_fields=['conversation_key', 'updated_at'])
            continue
        # A conversation already carries the token: fold this one into it, so
        # the purged Message-ID survives nowhere.
        MailMessage.objects.filter(conversation=conversation).update(conversation=existing)
        for row in MailMatch.objects.filter(conversation=conversation):
            if MailMatch.objects.filter(conversation=existing, target_type=row.target_type,
                                        target_id=row.target_id).exists():
                row.delete()
            else:
                MailMatch.objects.filter(pk=row.pk).update(conversation=existing)
        if conversation.is_mixed and not existing.is_mixed:
            MailConversation.objects.filter(pk=existing.pk).update(is_mixed=True)
        conversation.delete()
        refresh_conversations([existing.pk])


# --- messages and copies ------------------------------------------------------

def purge_messages(message_ids, reason='rule'):
    """Delete messages with everything attached and every trace elsewhere."""
    counts = _empty_counts()
    message_ids = set(message_ids)
    if not message_ids:
        return counts
    rows = list(MailMessage.objects.filter(pk__in=message_ids).values_list(
        'pk', 'rfc_message_id', 'conversation_id'))
    if not rows:
        return counts
    rfc_ids = {r[1] for r in rows}
    conversation_ids = {r[2] for r in rows}
    counts['copies'] = MailboxCopy.objects.filter(message_id__in=message_ids).count()
    MailMessage.objects.filter(pk__in=message_ids).delete()
    counts['messages'] = len(rows)
    _add(counts, scrub_queue({message_key(r) for r in rfc_ids}))
    _rewrite_references(rfc_ids, conversation_ids)
    counts['conversations'] = refresh_conversations(conversation_ids)
    send_purged(rfc_ids, reason)
    return counts


def purge_orphans(message_ids, reason='rule'):
    """Purge those of ``message_ids`` that no mailbox holds any more."""
    message_ids = set(message_ids)
    if not message_ids:
        return _empty_counts()
    still_held = set(
        MailboxCopy.objects.filter(message_id__in=message_ids).values_list('message_id', flat=True)
    )
    return purge_messages(message_ids - still_held, reason)


def drop_copies(copy_ids, reason='label', record_for=None, actor=''):
    """Delete copies; scrub their mailbox's queue samples of those messages;
    purge any message left without a copy. Returns counts. With
    ``record_for`` (a mailbox) a ``CapturePurge`` summary row is written."""
    copy_ids = set(copy_ids)
    counts = _empty_counts()
    if not copy_ids:
        return counts
    rows = list(MailboxCopy.objects.filter(pk__in=copy_ids).values_list(
        'message_id', 'mailbox__email', 'message__rfc_message_id'))
    MailboxCopy.objects.filter(pk__in=copy_ids).delete()
    counts['copies'] = len(rows)
    by_mailbox = {}
    for _, mailbox, rfc in rows:
        by_mailbox.setdefault(mailbox, set()).add(message_key(rfc))
    for mailbox, keys in by_mailbox.items():
        _add(counts, scrub_queue(keys, mailbox))
    part = purge_orphans({r[0] for r in rows}, reason)
    part.pop('copies', None)
    _add(counts, part)
    if record_for is not None:
        _record(reason, counts, mailbox=record_for, actor=actor)
    return counts


def _record(reason, counts, rule=None, mailbox=None, actor='', remaining=False):
    if not any(counts.get(k) for k in ('messages', 'copies', 'conversations', 'queue_rows',
                                       'queue_samples', 'bodies_cleared')):
        return None
    return CapturePurge.objects.create(
        at=timezone.now(), reason=reason, rule=rule, mailbox=mailbox, actor=actor[:80],
        messages=counts.get('messages', 0), copies=counts.get('copies', 0),
        conversations=counts.get('conversations', 0), queue_rows=counts.get('queue_rows', 0),
        queue_samples=counts.get('queue_samples', 0),
        bodies_cleared=counts.get('bodies_cleared', 0), remaining=remaining,
    )


# --- rules ---------------------------------------------------------------------

def _rule_message_ids(rule):
    """Stored messages a rule reaches (ids), for its scope."""
    ids = MailParticipant.objects.filter(_participant_filter(rule)).values_list('message_id', flat=True)
    if rule.scope == 'mailbox':
        return MailboxCopy.objects.filter(mailbox_id=rule.mailbox_id, message_id__in=ids) \
            .values_list('message_id', flat=True)
    return ids


def preview_rule(rule):
    """What confirming ``rule`` would remove, as counts. Reads only."""
    if rule.kind == 'label':
        return _preview_label_rule(rule)
    message_ids = set(_rule_message_ids(rule))
    if rule.action == ACTION_HEADERS_ONLY:
        bodies = MailMessage.objects.filter(pk__in=message_ids, body_text__isnull=False).count()
        return {'messages': 0, 'bodies': bodies, 'conversations': 0, 'queue_rows': 0}
    if rule.scope == 'mailbox':
        held_elsewhere = set(MailboxCopy.objects.filter(message_id__in=message_ids)
                             .exclude(mailbox_id=rule.mailbox_id).values_list('message_id', flat=True))
        purged = message_ids - held_elsewhere
    else:
        purged = message_ids
    conversations = set(MailMessage.objects.filter(pk__in=purged).values_list('conversation_id', flat=True))
    return {
        'messages': len(purged),
        'copies': MailboxCopy.objects.filter(message_id__in=message_ids).count()
        if rule.scope == 'org' else
        MailboxCopy.objects.filter(message_id__in=message_ids, mailbox_id=rule.mailbox_id).count(),
        'conversations': len(conversations),
        'queue_rows': queue_rows_for_rule(rule).count(),
    }


def _preview_label_rule(rule):
    """Copies carrying the rule's label, from each mailbox's last-seen label
    ids (recorded by the sync engine), and the messages left with no copy."""
    from .models import CaptureMailbox
    name = rule.value.strip().lower()
    mailboxes = CaptureMailbox.objects.all()
    if rule.scope == 'mailbox':
        mailboxes = mailboxes.filter(pk=rule.mailbox_id)
    copy_ids, message_ids = set(), set()
    for mailbox in mailboxes:
        ids = set(((mailbox.enforced_label_ids or {}).get('rule_labels') or {}).get(name) or ())
        if not ids:
            continue
        for pk, message_id, labels in MailboxCopy.objects.filter(mailbox=mailbox).values_list(
                'pk', 'message_id', 'label_ids').iterator():
            if set(labels or ()) & ids:
                copy_ids.add(pk)
                message_ids.add(message_id)
    if rule.action == ACTION_HEADERS_ONLY:
        bodies = MailMessage.objects.filter(pk__in=message_ids, body_text__isnull=False).count()
        return {'messages': 0, 'bodies': bodies, 'copies': 0, 'conversations': 0, 'queue_rows': 0}
    held_elsewhere = set(MailboxCopy.objects.filter(message_id__in=message_ids)
                         .exclude(pk__in=copy_ids).values_list('message_id', flat=True))
    purged = message_ids - held_elsewhere
    conversations = set(MailMessage.objects.filter(pk__in=purged).values_list('conversation_id', flat=True))
    return {'messages': len(purged), 'copies': len(copy_ids), 'conversations': len(conversations),
            'queue_rows': 0,
            'note': 'Counted from the labels each mailbox showed at its last run; applied per '
                    'mailbox on its next run after confirmation.'}


RULE_CHANGED = 'the rule changed since the preview: preview again'


class RuleChanged(Exception):
    """The rule is no longer the one that was previewed (or is already
    confirmed as it stands): nothing was confirmed."""


def confirm_rule(rule, user=None, *, expected_fingerprint):
    """Confirm exactly the rule that was previewed. ``expected_fingerprint``
    is ``rule.fingerprint()`` as shown on the preview; it is compared with
    the rule as it stands now, under a row lock, and a mismatch (an edit since
    the preview, by any route) raises ``RuleChanged`` and confirms nothing.
    Every confirm route (the admin page, a shell, a future command) must pass
    it; there is no default. A rule whose earlier confirmation went stale
    (changed by ``QuerySet.update``) can be confirmed again the same way."""
    with transaction.atomic():
        current = CaptureRule.objects.select_for_update().filter(pk=rule.pk).first()
        if current is None or not expected_fingerprint or current.fingerprint() != expected_fingerprint:
            raise RuleChanged(RULE_CHANGED)
        if current.is_confirmed:
            raise RuleChanged('this rule is already confirmed as it stands')
        current.purge_state = 'confirmed'
        current.confirmed_by = user if (user is not None and getattr(user, 'is_authenticated', False)) else None
        current.confirmed_at = timezone.now()
        current.confirmed_fingerprint = expected_fingerprint
        CaptureRule.objects.filter(pk=current.pk).update(
            purge_state=current.purge_state, confirmed_by=current.confirmed_by,
            confirmed_at=current.confirmed_at, confirmed_fingerprint=current.confirmed_fingerprint,
            purge_done_at=None,
        )
    rule.refresh_from_db()
    return rule


def demote_changed_rules():
    """Rules changed after confirmation by any route (QuerySet.update, a
    shell, a data migration) go back to awaiting confirmation."""
    changed = [r.pk for r in CaptureRule.objects.filter(purge_state__in=('confirmed', 'done'))
               if not r.is_confirmed]
    if changed:
        CaptureRule.objects.filter(pk__in=changed).update(
            purge_state='awaiting_confirmation', confirmed_fingerprint='', confirmed_at=None,
            confirmed_by=None, purge_done_at=None,
        )
    return len(changed)


def _enforce_one(rule, cap, actor):
    counts = _empty_counts()
    if rule.kind == 'label':
        # Applied per mailbox by the engine, which knows that mailbox's label ids.
        return counts, False
    if rule.action == ACTION_HEADERS_ONLY:
        ids = list(MailMessage.objects.filter(
            pk__in=_rule_message_ids(rule), body_text__isnull=False).values_list('pk', flat=True)[:cap + 1])
        remaining = len(ids) > cap
        ids = ids[:cap]
        counts['bodies_cleared'] = MailMessage.objects.filter(pk__in=ids).update(
            body_text=None, body_sha256='', capture_state='headers', headers_only_rule=True,
        )
        return counts, remaining
    if rule.action not in DROP_ACTIONS:
        return counts, False
    ids = list(set(_rule_message_ids(rule)))
    remaining = len(ids) > cap
    ids = ids[:cap]
    if rule.scope == 'mailbox':
        copy_ids = set(MailboxCopy.objects.filter(mailbox_id=rule.mailbox_id, message_id__in=ids)
                       .values_list('pk', flat=True))
        _add(counts, drop_copies(copy_ids, 'rule'))
    else:
        _add(counts, purge_messages(ids, 'rule'))
    if not remaining:
        _add(counts, _purge_queue_for_rule(rule))
    return counts, remaining


def enforce_rules(rules=None, cap=PURGE_CAP, actor='job'):
    """Apply confirmed address and domain rules to mail already stored, at
    most ``cap`` messages per rule per call. Rules whose value is refused
    (``rules.rule_problem``) are never applied. Returns total counts."""
    if rules is None:
        demote_changed_rules()
        rules = CaptureRule.objects.filter(purge_state='confirmed').select_related('mailbox')
    total = _empty_counts()
    for rule in rules:
        if rule.purge_state != 'confirmed' or not rule.is_confirmed or rule.kind == 'label' \
                or rule_problem(rule.kind, rule.value):
            continue
        with transaction.atomic():
            counts, remaining = _enforce_one(rule, cap, actor)
            _record('rule', counts, rule=rule, mailbox=rule.mailbox if rule.scope == 'mailbox' else None,
                    actor=actor, remaining=remaining)
            if not remaining and rule.kind != 'label':
                CaptureRule.objects.filter(pk=rule.pk).update(
                    purge_state='done', purge_done_at=timezone.now())
        _add(total, counts)
    return total


def enforce_label_rules(mailbox, private_ids, headers_only_ids, actor='job'):
    """Drop this mailbox's copies that carry a private label; clear bodies of
    messages whose copy carries a headers-only label. Scans the mailbox's
    copies, so the sync engine calls it only when the label set changed."""
    counts = _empty_counts()
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
        _add(counts, drop_copies(drop, 'label'))
        if clear:
            counts['bodies_cleared'] = MailMessage.objects.filter(
                pk__in=clear, body_text__isnull=False).update(
                body_text=None, body_sha256='', capture_state='headers', headers_only_rule=True)
        _record('label', counts, mailbox=mailbox, actor=actor)
    return counts


# --- expiry and retention ---------------------------------------------------------

def purge_expired_unmatched(now):
    """Delete open queue rows past their expiry (30 days after Gmail last
    delivered a message from them)."""
    qs = UnmatchedSender.objects.filter(status='open', expires_at__lt=now)
    count = qs.count()
    if count:
        qs.delete()
        _record('expiry', {'queue_rows': count})
    return count


def purge_old_records(now=None):
    """Retention for capture's own records (no scheduler here): finished runs
    older than CAPTURE_RUN_RETENTION_DAYS; access-log and purge-summary rows
    older than CAPTURE_ACCESS_LOG_RETENTION_DAYS."""
    now = now or timezone.now()
    run_cutoff = now - timedelta(days=conf.run_retention_days())
    log_cutoff = now - timedelta(days=conf.access_log_retention_days())
    runs = CaptureRun.objects.filter(started_at__lt=run_cutoff).exclude(outcome='running')
    logs = MailboxAccessLog.objects.filter(at__lt=log_cutoff)
    purges = CapturePurge.objects.filter(at__lt=log_cutoff)
    counts = {'runs': runs.count(), 'access_log': logs.count(), 'purge_summaries': purges.count()}
    with transaction.atomic():
        logs.delete()
        runs.delete()
        purges.delete()
    return counts
