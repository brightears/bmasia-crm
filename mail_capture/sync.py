"""The sync engine: reads one mailbox through a ``GmailClient`` and stores
what the matcher accepts.

Entry points are ``sync_mailbox`` and ``sync_all_enabled``. Both return
"capture disabled" before creating a client while the master switch is off,
while our own domains are not configured, or when the mailbox (or every
mailbox) is not enabled.

Guarantees (research/11 B.7 "Idempotency and ordering"):

* One runner per mailbox: a lease on the ``CaptureMailbox`` row, taken with
  ``SELECT ... FOR UPDATE SKIP LOCKED``. A second runner gets ``busy``.
* Each batch (one history page or one list page) is written in a single
  transaction together with the cursor. A crash leaves the cursor where it
  was; the next run re-reads the page and the upserts absorb the repeat.
* Upserts: one ``MailMessage`` per Message-ID, one ``MailboxCopy`` per
  (mailbox, Gmail id) and (mailbox, message). Re-running changes nothing.
* A history 404 sets ``needs_resync``; the next run does a bounded resync.
* 429 and 5xx answers are retried with exponential backoff and jitter.
* ``dry_run`` reads the mailbox and writes only its ``CaptureRun`` and
  ``MailboxAccessLog`` rows (the read itself must be on record).
* Headers only by default. A body is fetched and stored only when the
  mailbox has ``body_mode='body'``, the message matched a company, and no
  headers-only rule or label applies. Unmatched mail never gets a body.

Logging is counts only: no subject, address or name is ever logged.
"""
import hashlib
import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.db.models import DateTimeField, F, Value
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils import timezone

from . import conf
from . import rules as capture_rules
from .gmail_client import (
    QUOTA_UNITS, FakeGmailClient, GmailError, GmailNotFound, GmailRateLimited,
    GmailServerError,
)
from .match import (
    AMBIGUOUS, MALFORMED, MATCHED, SKIP_INTERNAL, SKIP_RULE, UNMATCHED, match_message,
)
from .models import (
    CaptureMailbox, CaptureRun, MailboxAccessLog, MailboxCopy, MailConversation, MailMatch,
    MailMessage, MailParticipant, UnmatchedSender,
)
from .parse import (
    METADATA_HEADERS, extract_body_text, internal_date, is_internal, parse_gmail_message,
)
from .purge import (
    drop_copies, enforce_label_rules, enforce_rules, purge_expired_unmatched, refresh_conversations,
)
from .snapshot import build_snapshot, load_rules


logger = logging.getLogger(__name__)

PAGE_SIZE = 100
LEASE_SECONDS = 15 * 60
MAX_ATTEMPTS = 4
UNMATCHED_TTL = timedelta(days=30)
SUBJECT_FALLBACK_WINDOW = timedelta(days=30)
RESYNC_DEFAULT_WINDOW = timedelta(days=7)
MAX_SAMPLE_SUBJECTS = 3
MAX_MESSAGE_KEYS = 500

KINDS = ('incremental', 'backfill', 'resync')
_ACCESS_PURPOSE = {'incremental': 'poll', 'backfill': 'backfill', 'resync': 'resync'}

COUNT_FIELDS = (
    'listed', 'fetched', 'stored', 'copies_added', 'already_known', 'skipped_internal',
    'skipped_by_rule', 'skipped_system', 'matched', 'ambiguous', 'unmatched', 'purged',
    'malformed', 'errors',
)


@dataclass
class SyncResult:
    outcome: str
    reason: str = ''
    run_id: int = None
    mailbox_id: str = ''
    kind: str = ''
    dry_run: bool = False
    counts: dict = field(default_factory=dict)

    @property
    def disabled(self):
        return self.outcome == 'disabled'


class LeaseLost(Exception):
    """Another runner took the mailbox; this run stops without writing."""


class CaptureRefused(Exception):
    """A real client was offered while capture is switched off."""


def _disabled(reason, mailbox_id='', kind='', dry_run=False):
    return SyncResult(outcome='disabled', reason=reason, mailbox_id=str(mailbox_id or ''),
                      kind=kind, dry_run=dry_run)


def sync_all_enabled(client_factory, kind='incremental', **kwargs):
    """Run ``sync_mailbox`` for every enabled mailbox, one after another."""
    state = conf.capture_state()
    if not state.enabled:
        return [_disabled(state.reason, kind=kind, dry_run=kwargs.get('dry_run', False))]
    ids = list(CaptureMailbox.objects.filter(enabled=True).order_by('email').values_list('pk', flat=True))
    if not ids:
        return [_disabled(conf.DISABLED_NO_MAILBOX, kind=kind, dry_run=kwargs.get('dry_run', False))]
    return [sync_mailbox(pk, client_factory, kind=kind, **kwargs) for pk in ids]


def sync_mailbox(mailbox_id, client_factory, kind='incremental', dry_run=False, since=None,
                 max_messages=None, max_quota_units=None, actor='job:gmail_sync', sleep=None,
                 page_size=PAGE_SIZE, lease_seconds=LEASE_SECONDS, fake_only=False,
                 maintenance=True):
    """Sync one mailbox. ``client_factory(mailbox)`` returns a ``GmailClient``
    and is called only after every switch has been checked.

    ``fake_only`` (used by the self-check) lets the pipeline run while the
    master switch is off, and then only with a ``FakeGmailClient``.
    ``maintenance=False`` skips applying rules to stored mail and expiring the
    queue at the start of the run (the self-check must not touch real rows).
    """
    if kind not in KINDS:
        raise ValueError(f'unknown sync kind {kind!r}')
    state = conf.capture_state()
    if not state.enabled and not fake_only:
        return _disabled(state.reason, mailbox_id, kind, dry_run)
    mailbox = CaptureMailbox.objects.filter(pk=mailbox_id).first()
    if mailbox is None or not mailbox.enabled:
        return _disabled(conf.DISABLED_MAILBOX, mailbox_id, kind, dry_run)
    if not conf.internal_domains():
        return _disabled(conf.DISABLED_NO_DOMAINS, mailbox_id, kind, dry_run)
    client = client_factory(mailbox)
    if not state.enabled and not isinstance(client, FakeGmailClient):
        raise CaptureRefused('capture is switched off; only the fake client may run')
    runner = _Runner(
        mailbox, client, kind=kind, dry_run=dry_run, since=since, max_messages=max_messages,
        max_quota_units=max_quota_units, actor=actor, sleep=sleep or time.sleep,
        page_size=page_size, lease_seconds=lease_seconds, maintenance=maintenance,
    )
    return runner.run()


@dataclass
class _Plan:
    parsed: object
    action: str                       # store | copy | labels | queue | skip
    result: object = None             # MatchResult for store / queue
    conversation_key: str = ''
    message_pk: object = None         # existing MailMessage for copy
    copy_pk: object = None            # existing copy for labels
    body: str = None
    headers_only: bool = False


class _BudgetSpent(Exception):
    pass


class _Runner:
    def __init__(self, mailbox, client, kind, dry_run, since, max_messages, max_quota_units,
                 actor, sleep, page_size, lease_seconds, maintenance=True):
        self.mailbox = mailbox
        self.client = client
        self.kind = kind
        self.dry_run = dry_run
        self.since = since
        self.max_messages = max_messages
        self.max_quota_units = max_quota_units
        self.actor = actor
        self.sleep = sleep
        self.page_size = page_size
        self.lease_seconds = lease_seconds
        self.maintenance = maintenance
        self.token = ''
        self.counts = {name: 0 for name in COUNT_FIELDS}
        self.api_calls = 0
        self.quota_units = 0
        self.bodies_read = 0
        self.messages_read = 0
        self.run_row = None
        self.private_ids = frozenset()
        self.headers_only_ids = frozenset()
        self.rules = ()

    # -- bookkeeping ---------------------------------------------------------
    def _bump(self, name, n=1):
        self.counts[name] += n

    def _call(self, name, *args, **kwargs):
        units_key = 'get_message_full' if name == 'get_message' and kwargs.get('format') == 'full' else name
        fn = getattr(self.client, name)
        for attempt in range(MAX_ATTEMPTS):
            if self.max_quota_units is not None and self.quota_units >= self.max_quota_units:
                raise _BudgetSpent()
            self.api_calls += 1
            self.quota_units += QUOTA_UNITS.get(units_key, 1)
            try:
                return fn(*args, **kwargs)
            except (GmailRateLimited, GmailServerError):
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                delay = min(32.0, 2.0 ** attempt) * (0.5 + random.random() / 2)
                self.sleep(delay)
        raise AssertionError('unreachable')

    def _start_run(self):
        self.run_row = CaptureRun.objects.create(
            mailbox=self.mailbox, kind=self.kind, dry_run=self.dry_run,
            started_at=timezone.now(), history_id_start=self.mailbox.history_id,
        )

    def _finish(self, outcome, error_summary=''):
        now = timezone.now()
        if self.run_row is not None:
            for name, value in self.counts.items():
                setattr(self.run_row, name, value)
            self.run_row.kind = self.kind
            self.run_row.outcome = outcome
            self.run_row.finished_at = now
            self.run_row.quota_units_est = self.quota_units
            self.run_row.error_summary = error_summary[:200]
            self.run_row.history_id_end = (
                CaptureMailbox.objects.filter(pk=self.mailbox.pk).values_list('history_id', flat=True).first()
                or ''
            )
            self.run_row.save()
        if self.api_calls:
            purpose = _ACCESS_PURPOSE.get(self.kind, 'poll')
            MailboxAccessLog.objects.create(
                mailbox=self.mailbox, run=self.run_row, at=now, purpose=purpose, actor=self.actor[:80],
                dry_run=self.dry_run, api_calls=self.api_calls, messages_read=self.messages_read,
            )
            if self.bodies_read:
                MailboxAccessLog.objects.create(
                    mailbox=self.mailbox, run=self.run_row, at=now, purpose='body', actor=self.actor[:80],
                    dry_run=self.dry_run, api_calls=0, messages_read=0, bodies_read=self.bodies_read,
                )
        logger.info(
            'mail capture run=%s mailbox=%s kind=%s dry_run=%s outcome=%s calls=%d %s',
            getattr(self.run_row, 'pk', None), self.mailbox.pk, self.kind, self.dry_run, outcome,
            self.api_calls, ' '.join(f'{k}={v}' for k, v in self.counts.items() if v),
        )
        return SyncResult(
            outcome=outcome, reason=error_summary, run_id=getattr(self.run_row, 'pk', None),
            mailbox_id=str(self.mailbox.pk), kind=self.kind, dry_run=self.dry_run,
            counts=dict(self.counts, api_calls=self.api_calls, quota_units=self.quota_units),
        )

    def _health(self, error=None, needs_resync=None):
        if self.dry_run:
            return
        updates = {}
        if error is None:
            updates.update(last_error='', consecutive_errors=0)
        else:
            updates.update(last_error=error[:200], consecutive_errors=F('consecutive_errors') + 1)
        if needs_resync is not None:
            updates['needs_resync'] = needs_resync
        CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(**updates)

    # -- lease ---------------------------------------------------------------
    def _acquire(self):
        if self.dry_run:
            return True
        with transaction.atomic():
            row = (
                CaptureMailbox.objects.select_for_update(skip_locked=True, no_key=True)
                .filter(pk=self.mailbox.pk).first()
            )
            if row is None:
                return False
            now = timezone.now()
            if row.lease_token and row.lease_expires_at and row.lease_expires_at > now:
                return False
            token = secrets.token_hex(16)
            CaptureMailbox.objects.filter(pk=row.pk).update(
                lease_token=token, lease_expires_at=now + timedelta(seconds=self.lease_seconds),
            )
            self.token = token
            self.mailbox = CaptureMailbox.objects.get(pk=row.pk)
        return True

    def _release(self):
        if self.token:
            CaptureMailbox.objects.filter(pk=self.mailbox.pk, lease_token=self.token).update(
                lease_token='', lease_expires_at=None,
            )
            self.token = ''

    def _lock_for_write(self):
        row = CaptureMailbox.objects.select_for_update(no_key=True).get(pk=self.mailbox.pk)
        if not self.dry_run and row.lease_token != self.token:
            raise LeaseLost()
        return row

    # -- main ----------------------------------------------------------------
    def run(self):
        self._start_run()
        if not self._acquire():
            return self._finish('busy', 'another runner holds this mailbox')
        try:
            if not self.dry_run and self.maintenance:
                purged = enforce_rules()
                self._bump('purged', purged['purged'])
                purge_expired_unmatched(timezone.now())
            self.rules = load_rules()
            self._load_labels()
            if self.kind == 'incremental' and self.mailbox.needs_resync:
                self.kind = 'resync'
            if self.kind == 'incremental':
                outcome = self._incremental()
            elif self.kind == 'resync':
                outcome = self._list_pass(resync=True)
            else:
                outcome = self._list_pass(resync=False)
            self._health(None)
            return self._finish(outcome)
        except GmailNotFound:
            # The history cursor is too old: resync on the next run.
            self._bump('errors')
            self._health('history 404', needs_resync=True)
            return self._finish('resync_needed', 'history id no longer valid')
        except GmailRateLimited as exc:
            self._bump('errors')
            self._health(f'rate limited {exc.status}')
            return self._finish('rate_limited', f'gmail {exc.status}')
        except _BudgetSpent:
            self._health(None)
            return self._finish('ok', 'quota budget spent; stopped early')
        except GmailError as exc:
            self._bump('errors')
            self._health(f'gmail {exc.status}')
            return self._finish('error', f'gmail {exc.status}')
        except LeaseLost:
            return self._finish('busy', 'lease lost to another runner')
        except Exception as exc:
            self._bump('errors')
            self._health(type(exc).__name__)
            self._finish('error', type(exc).__name__)
            raise
        finally:
            self._release()

    def _load_labels(self):
        labels = self._call('list_labels') or []
        by_id = {str(item.get('id')): str(item.get('name', '')) for item in labels}
        self.private_ids = capture_rules.private_label_ids(by_id, self.rules, self.mailbox.pk)
        self.headers_only_ids = capture_rules.headers_only_label_ids(by_id, self.rules, self.mailbox.pk)
        state = {'private': sorted(self.private_ids), 'headers_only': sorted(self.headers_only_ids)}
        if not self.dry_run and (self.mailbox.enforced_label_ids or {}) != state:
            counts = enforce_label_rules(self.mailbox, self.private_ids, self.headers_only_ids)
            self._bump('purged', counts['purged'])
            CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(enforced_label_ids=state)

    # -- incremental -----------------------------------------------------------
    def _incremental(self):
        if not self.mailbox.history_id:
            profile = self._call('get_profile')
            if not self.dry_run:
                with transaction.atomic():
                    self._lock_for_write()
                    CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(
                        history_id=str(profile.get('historyId', '')), last_poll_at=timezone.now(),
                    )
            return 'ok'
        cursor = self.mailbox.history_id
        page_token = None
        fetched_total = 0
        while True:
            resp = self._call(
                'list_history', cursor, page_token=page_token, max_results=self.page_size,
            )
            records = resp.get('history') or []
            added, deleted, label_changes = [], set(), []
            for record in records:
                for item in record.get('messagesAdded') or ():
                    gid = str((item.get('message') or {}).get('id', ''))
                    if gid and gid not in added:
                        added.append(gid)
                for item in record.get('messagesDeleted') or ():
                    gid = str((item.get('message') or {}).get('id', ''))
                    if gid:
                        deleted.add(gid)
                for key, sign in (('labelsAdded', '+'), ('labelsRemoved', '-')):
                    for item in record.get(key) or ():
                        gid = str((item.get('message') or {}).get('id', ''))
                        if gid:
                            label_changes.append((gid, sign, list(item.get('labelIds') or ())))
            to_fetch = [gid for gid in added if gid not in deleted]
            known = set(
                MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=to_fetch)
                .values_list('gmail_id', flat=True)
            )
            self._bump('listed', len(to_fetch))
            self._bump('already_known', len(known))
            to_fetch = [gid for gid in to_fetch if gid not in known]
            if self.max_messages is not None:
                to_fetch = to_fetch[:max(0, self.max_messages - fetched_total)]
            fetched_total += len(to_fetch)
            raws = self._fetch(to_fetch)
            next_token = resp.get('nextPageToken')
            if next_token:
                new_cursor = str(records[-1].get('id')) if records else cursor
            else:
                new_cursor = str(resp.get('historyId') or cursor)
            fetched_ids = {raw.get('id') for raw in raws}
            label_changes = [c for c in label_changes if c[0] not in fetched_ids]
            self._write_batch(
                raws, cursor={'history_id': new_cursor, 'last_poll_at': timezone.now()},
                deleted=deleted, label_changes=label_changes,
            )
            if not next_token:
                break
            if self.max_messages is not None and fetched_total >= self.max_messages:
                break
            page_token = next_token
        return 'ok'

    # -- backfill and resync -----------------------------------------------------
    def _bound(self, resync):
        if resync:
            newest = self.mailbox.newest_internal_date
            if newest is not None:
                return newest - timedelta(days=1)
            if self.mailbox.backfill_since:
                return datetime.combine(self.mailbox.backfill_since, dt_time.min, dt_timezone.utc)
            return timezone.now() - RESYNC_DEFAULT_WINDOW
        since = self.since or self.mailbox.backfill_since
        if since is None:
            raise ValueError('a backfill needs a since date (argument or mailbox.backfill_since)')
        if isinstance(since, datetime):
            return since if since.tzinfo else since.replace(tzinfo=dt_timezone.utc)
        return datetime.combine(since, dt_time.min, dt_timezone.utc)

    def _list_pass(self, resync):
        bound = self._bound(resync)
        new_cursor = None
        if resync or not self.mailbox.history_id:
            # Taken before listing, so nothing that arrives meanwhile is missed.
            new_cursor = str(self._call('get_profile').get('historyId', ''))
        page_token = None
        fetched_total = 0
        first = True
        done = False
        while not done:
            resp = self._call('list_messages', page_token=page_token, max_results=self.page_size)
            ids = [str(m.get('id')) for m in resp.get('messages') or () if m.get('id')]
            self._bump('listed', len(ids))
            known = dict(
                MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=ids)
                .values_list('gmail_id', 'internal_date')
            )
            to_fetch = []
            for gid in ids:
                if gid in known:
                    self._bump('already_known')
                    if known[gid] is not None and known[gid] < bound:
                        done = True
                        break
                    continue
                if self.max_messages is not None and fetched_total + len(to_fetch) >= self.max_messages:
                    done = True
                    break
                to_fetch.append(gid)
            raws = []
            for gid in to_fetch:   # newest first: stop at the first one past the bound
                fetched = self._fetch([gid])
                if not fetched:
                    continue
                parsed_date = _internal(fetched[0])
                if parsed_date is not None and parsed_date < bound:
                    done = True
                    break
                raws.append(fetched[0])
            fetched_total += len(to_fetch)
            page_token = resp.get('nextPageToken')
            if not page_token:
                done = True
            cursor = {}
            if new_cursor and not resync and first and not self.mailbox.history_id:
                cursor['history_id'] = new_cursor
            if resync and done:
                cursor.update(history_id=new_cursor, needs_resync=False)
            if done and not resync:
                cursor['last_full_sync_at'] = timezone.now()
            self._write_batch(raws, cursor=cursor)
            first = False
        return 'ok'

    # -- fetching ------------------------------------------------------------
    def _fetch(self, gmail_ids):
        raws = []
        for gid in gmail_ids:
            try:
                raw = self._call(
                    'get_message', gid, format='metadata', metadata_headers=list(METADATA_HEADERS),
                )
            except GmailNotFound:
                continue  # deleted since it was listed
            self.messages_read += 1
            self._bump('fetched')
            raws.append(raw)
        return raws

    # -- planning ------------------------------------------------------------
    def _plan(self, raws):
        parsed_all = []
        for raw in raws:
            parsed = parse_gmail_message(raw)
            parsed_all.append(parsed)
        parsed_all.sort(key=_sort_key)

        gmail_ids = [p.gmail_id for p in parsed_all]
        existing_copies = dict(
            MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=gmail_ids)
            .values_list('gmail_id', 'pk')
        )
        rfc_ids = [p.message_id for p in parsed_all]
        existing_messages = dict(
            MailMessage.objects.filter(rfc_message_id__in=rfc_ids).values_list('rfc_message_id', 'pk')
        )
        held_here = set(
            MailboxCopy.objects.filter(mailbox=self.mailbox, message__rfc_message_id__in=rfc_ids)
            .values_list('message__rfc_message_id', flat=True)
        )

        plans, to_match = [], []
        planned_rfc = set()
        for parsed in parsed_all:
            decision = capture_rules.copy_decision(parsed.label_ids, self.private_ids)
            if parsed.gmail_id in existing_copies:
                plans.append(_Plan(parsed, 'labels', copy_pk=existing_copies[parsed.gmail_id]))
                self._bump('already_known')
                continue
            if decision == capture_rules.COPY_PRIVATE:
                self._bump('skipped_by_rule')
                continue
            if decision == capture_rules.COPY_SKIP_SYSTEM or parsed.is_bulk:
                self._bump('skipped_system')
                continue
            action = capture_rules.message_rule_action(parsed.addresses(), self.rules, self.mailbox.pk)
            if action in (capture_rules.ACTION_SKIP, capture_rules.ACTION_PRIVATE):
                self._bump('skipped_by_rule')
                continue
            if parsed.message_id in held_here or parsed.message_id in planned_rfc:
                # This mailbox already holds the message under another Gmail id.
                self._bump('already_known')
                continue
            if parsed.message_id in existing_messages:
                plans.append(_Plan(parsed, 'copy', message_pk=existing_messages[parsed.message_id]))
                held_here.add(parsed.message_id)
                continue
            planned_rfc.add(parsed.message_id)
            to_match.append(parsed)

        keys = self._resolve_conversations(to_match)
        snapshot = build_snapshot(to_match, conversation_keys=set(keys.values()), rules=self.rules)
        for parsed in to_match:
            key = keys[parsed.message_id]
            result = match_message(parsed, snapshot, self.mailbox.pk, conversation_key=key)
            headers_only = (
                result.rule_action == capture_rules.ACTION_HEADERS_ONLY
                or bool(set(parsed.label_ids) & self.headers_only_ids)
            )
            if result.decision == MALFORMED:
                self._bump('malformed')
                continue
            if result.decision == SKIP_INTERNAL:
                self._bump('skipped_internal')
                continue
            if result.decision == SKIP_RULE:
                self._bump('skipped_by_rule')
                continue
            if result.decision == UNMATCHED:
                self._bump('unmatched')
                plans.append(_Plan(parsed, 'queue', result=result, conversation_key=key))
                continue
            self._bump('matched' if result.decision == MATCHED else 'ambiguous')
            plans.append(_Plan(parsed, 'store', result=result, conversation_key=key,
                               headers_only=headers_only))
        return plans

    def _resolve_conversations(self, parsed_list):
        """Conversation key per message: an existing conversation that holds a
        message this one replies to, else the RFC key, else (for a reply
        without threading headers) a recent conversation with the same
        subject and a shared external participant."""
        keys = {}
        if not parsed_list:
            return keys
        refs = set()
        for parsed in parsed_list:
            refs.update(parsed.references)
            if parsed.in_reply_to:
                refs.add(parsed.in_reply_to)
        by_message = dict(
            MailMessage.objects.filter(rfc_message_id__in=refs)
            .values_list('rfc_message_id', 'conversation__conversation_key')
        ) if refs else {}
        existing_keys = set(
            MailConversation.objects.filter(
                conversation_key__in={p.conversation_key for p in parsed_list}
            ).values_list('conversation_key', flat=True)
        )
        domains_internal = conf.internal_domains()
        addresses_internal = conf.internal_addresses()
        in_batch = {}
        for parsed in parsed_list:
            key = None
            if parsed.conversation_key in existing_keys:
                key = parsed.conversation_key
            else:
                for ref in [parsed.in_reply_to] + list(reversed(parsed.references)):
                    if not ref:
                        continue
                    key = by_message.get(ref) or in_batch.get(ref)
                    if key:
                        break
            if key is None and parsed.is_reply and not parsed.in_reply_to and not parsed.references \
                    and parsed.subject_normalised:
                key = self._subject_fallback(parsed, domains_internal, addresses_internal)
            key = key or parsed.conversation_key
            keys[parsed.message_id] = key
            in_batch[parsed.message_id] = key
        return keys

    def _subject_fallback(self, parsed, domains_internal, addresses_internal):
        external = [
            a.address for a in parsed.addresses()
            if not is_internal(a, domains_internal, addresses_internal)
        ]
        if not external:
            return None
        when = parsed.sent_at or timezone.now()
        row = (
            MailConversation.objects.filter(
                subject_normalised=parsed.subject_normalised,
                last_message_at__gte=when - SUBJECT_FALLBACK_WINDOW,
                messages__participants__address__in=external,
            ).order_by('-last_message_at').values_list('conversation_key', flat=True).first()
        )
        return row

    # -- writing -------------------------------------------------------------
    def _write_batch(self, raws, cursor=None, deleted=(), label_changes=()):
        plans = self._plan(raws)
        if self.dry_run:
            return
        for plan in plans:
            if plan.action == 'store' and self._wants_body(plan):
                try:
                    full = self._call('get_message', plan.parsed.gmail_id, format='full')
                except GmailNotFound:
                    full = None
                if full is not None:
                    self.bodies_read += 1
                    plan.body = extract_body_text(full.get('payload') or {})
        now = timezone.now()
        with transaction.atomic():
            self._lock_for_write()
            newest = None
            for plan in plans:
                internal = plan.parsed.internal_date
                if internal is not None and (newest is None or internal > newest):
                    newest = internal
                if plan.action == 'labels':
                    self._apply_labels(plan.copy_pk, plan.parsed.label_ids)
                elif plan.action == 'copy':
                    self._add_copy(plan)
                elif plan.action == 'store':
                    self._store(plan, now)
                elif plan.action == 'queue':
                    self._queue(plan.parsed, plan.result.queue_addresses, plan.result.unmatched_reason,
                                plan.result.candidates, now)
            if deleted:
                MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=deleted).delete()
            for gid, sign, label_ids in label_changes:
                copy = MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id=gid).first()
                if copy is None:
                    continue
                labels = list(copy.label_ids or [])
                if sign == '+':
                    labels = list(dict.fromkeys(labels + label_ids))
                else:
                    labels = [x for x in labels if x not in label_ids]
                if set(labels) & self.private_ids:
                    self._bump('purged', drop_copies({copy.pk}))
                    continue
                copy.label_ids = labels
                copy.save(update_fields=['label_ids', 'updated_at'])
            updates = dict(cursor or {})
            if newest is not None:
                current = CaptureMailbox.objects.filter(pk=self.mailbox.pk).values_list(
                    'newest_internal_date', flat=True).first()
                if current is None or newest > current:
                    updates['newest_internal_date'] = newest
            updates['lease_expires_at'] = now + timedelta(seconds=self.lease_seconds)
            CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(**updates)
            self.mailbox.refresh_from_db()

    def _wants_body(self, plan):
        return (
            self.mailbox.body_mode == 'body'
            and plan.result is not None
            and plan.result.decision == MATCHED
            and not plan.headers_only
        )

    def _apply_labels(self, copy_pk, label_ids):
        if set(label_ids) & self.private_ids:
            self._bump('purged', drop_copies({copy_pk}))
            return
        MailboxCopy.objects.filter(pk=copy_pk).update(label_ids=list(label_ids), updated_at=timezone.now())

    def _create_copy(self, message, parsed):
        try:
            with transaction.atomic():
                MailboxCopy.objects.create(
                    message=message, mailbox=self.mailbox, gmail_id=parsed.gmail_id,
                    gmail_thread_id=parsed.gmail_thread_id, label_ids=list(parsed.label_ids),
                    internal_date=parsed.internal_date,
                )
            return True
        except IntegrityError:
            # Same message under another Gmail id in this mailbox, or a repeat.
            existing = MailboxCopy.objects.filter(mailbox=self.mailbox, message=message).first()
            if existing is not None:
                merged = list(dict.fromkeys(list(existing.label_ids or []) + list(parsed.label_ids)))
                if merged != existing.label_ids:
                    existing.label_ids = merged
                    existing.save(update_fields=['label_ids', 'updated_at'])
            return False

    def _add_copy(self, plan):
        message = (
            MailMessage.objects.filter(pk=plan.message_pk).first() if plan.message_pk
            else MailMessage.objects.filter(rfc_message_id=plan.parsed.message_id).first()
        )
        if message is None:
            return
        if self._create_copy(message, plan.parsed):
            self._bump('copies_added')

    def _store(self, plan, now):
        parsed, result = plan.parsed, plan.result
        conversation = self._conversation(plan)
        sender = parsed.from_address
        body = plan.body if plan.body else None
        try:
            with transaction.atomic():
                message = MailMessage.objects.create(
                    rfc_message_id=parsed.message_id,
                    message_id_synthetic=parsed.message_id_synthetic,
                    conversation=conversation,
                    sent_at=parsed.sent_at or now,
                    from_address=sender.address if sender else '',
                    from_name=sender.display_name if sender else '',
                    subject=parsed.subject,
                    direction=result.direction,
                    in_reply_to=parsed.in_reply_to,
                    references=list(parsed.references),
                    has_attachments=parsed.has_attachments,
                    attachments=list(parsed.attachments),
                    body_text=body,
                    body_sha256=hashlib.sha256(body.encode('utf-8')).hexdigest() if body else '',
                    capture_state='body' if body else 'headers',
                    headers_only_rule=plan.headers_only,
                    email_log_id=result.email_log_id,
                )
        except IntegrityError:
            # Stored meanwhile by a runner on another mailbox: just add our copy.
            message = MailMessage.objects.filter(rfc_message_id=parsed.message_id).first()
            if message is not None and self._create_copy(message, parsed):
                self._bump('copies_added')
            return
        internal_domains = conf.internal_domains()
        internal_addresses = conf.internal_addresses()
        participants, seen = [], set()
        for role, item in parsed.participants():
            if (role, item.address) in seen:
                continue
            seen.add((role, item.address))
            participants.append(MailParticipant(
                message=message, role=role, address=item.address,
                display_name=item.display_name, domain=item.domain,
                is_internal=is_internal(item, internal_domains, internal_addresses),
                contact_id=result.contacts.get(item.address),
            ))
        MailParticipant.objects.bulk_create(participants, ignore_conflicts=True)
        self._create_copy(message, parsed)
        for link in result.links:
            try:
                with transaction.atomic():
                    MailMatch.objects.create(
                        message=message, target_type=link.target_type, target_id=str(link.target_id),
                        method=link.method, confidence=link.confidence, status=link.status,
                        detail=link.detail_dict(),
                    )
            except IntegrityError:
                pass
        self._touch_conversation(conversation, message, result)
        self._merge_late_parent(conversation, message)
        for address, company_id in result.new_contact_candidates:
            self._queue(parsed, (address,), 'domain_match', (company_id,), now)
        self._bump('stored')

    def _merge_late_parent(self, conversation, message):
        """A reply captured before the message it answers started a
        conversation keyed by that message's id. Now that the parent is
        here, fold that conversation into the parent's."""
        if conversation.conversation_key == message.rfc_message_id:
            return
        other = (
            MailConversation.objects.select_for_update(no_key=True)
            .filter(conversation_key=message.rfc_message_id).first()
        )
        if other is None or other.pk == conversation.pk:
            return
        target = MailConversation.objects.select_for_update(no_key=True).get(pk=conversation.pk)
        MailMessage.objects.filter(conversation=other).update(conversation=target)
        for row in MailMatch.objects.filter(conversation=other):
            if not MailMatch.objects.filter(
                conversation=target, target_type=row.target_type, target_id=row.target_id,
            ).exists():
                MailMatch.objects.filter(pk=row.pk).update(conversation=target)
        if target.link_state != 'confirmed' and other.link_state == 'confirmed':
            target.company_id, target.link_state = other.company_id, 'confirmed'
            target.link_confirmed_by_id = other.link_confirmed_by_id
            target.link_confirmed_at = other.link_confirmed_at
        elif target.link_state == 'none' and other.link_state in ('auto', 'ambiguous'):
            target.company_id, target.link_state = other.company_id, other.link_state
        target.save()
        other.delete()
        refresh_conversations([target.pk])

    def _conversation(self, plan):
        parsed = plan.parsed
        conversation, _ = MailConversation.objects.get_or_create(
            conversation_key=plan.conversation_key,
            defaults={'subject_normalised': parsed.subject_normalised},
        )
        return conversation

    def _touch_conversation(self, conversation, message, result):
        sent = Value(message.sent_at, output_field=DateTimeField())
        updates = {
            'message_count': F('message_count') + 1,
            'first_message_at': Least(Coalesce('first_message_at', sent), sent),
            'last_message_at': Greatest(Coalesce('last_message_at', sent), sent),
            'updated_at': timezone.now(),
        }
        side = 'last_inbound_at' if message.direction == 'inbound' else 'last_outbound_at'
        updates[side] = Greatest(Coalesce(side, sent), sent)
        MailConversation.objects.filter(pk=conversation.pk).update(**updates)

        row = MailConversation.objects.select_for_update(no_key=True).get(pk=conversation.pk)
        if row.link_state == 'confirmed':
            return
        if result.decision == MATCHED and row.link_state == 'none' and row.company_id is None:
            row.company_id = result.company_id
            row.link_state = 'auto'
            row.save(update_fields=['company', 'link_state', 'updated_at'])
        elif result.decision == AMBIGUOUS and row.link_state == 'none':
            row.link_state = 'ambiguous'
            row.save(update_fields=['link_state', 'updated_at'])

    def _queue(self, parsed, addresses, reason, candidates, now):
        """Upsert unmatched-sender rows. Headers only: address, name, domain,
        counts and up to three subjects."""
        message_key = hashlib.sha256(parsed.message_id.encode('utf-8', 'replace')).hexdigest()[:16]
        seen_at = parsed.sent_at or now
        for item in addresses:
            if not item.address:
                continue
            with transaction.atomic():
                row = UnmatchedSender.objects.select_for_update().filter(address=item.address).first()
                if row is None:
                    try:
                        with transaction.atomic():
                            UnmatchedSender.objects.create(
                                address=item.address, domain=item.domain,
                                display_name=item.display_name, first_seen=seen_at,
                                last_seen=seen_at, message_count=1, message_keys=[message_key],
                                mailboxes=[self.mailbox.email],
                                sample_subjects=[parsed.subject] if parsed.subject else [],
                                candidate_company_ids=[str(c) for c in candidates],
                                reason=reason, expires_at=seen_at + UNMATCHED_TTL,
                            )
                        continue
                    except IntegrityError:
                        row = UnmatchedSender.objects.select_for_update().get(address=item.address)
                if row.status == 'never_log':
                    continue
                changed = False
                if message_key not in (row.message_keys or []):
                    row.message_keys = (list(row.message_keys or []) + [message_key])[-MAX_MESSAGE_KEYS:]
                    row.message_count += 1
                    if parsed.subject and parsed.subject not in row.sample_subjects \
                            and len(row.sample_subjects) < MAX_SAMPLE_SUBJECTS:
                        row.sample_subjects = list(row.sample_subjects) + [parsed.subject]
                    changed = True
                if self.mailbox.email not in (row.mailboxes or []):
                    row.mailboxes = list(row.mailboxes or []) + [self.mailbox.email]
                    changed = True
                for company_id in candidates:
                    if str(company_id) not in row.candidate_company_ids:
                        row.candidate_company_ids = list(row.candidate_company_ids) + [str(company_id)]
                        changed = True
                if seen_at > row.last_seen:
                    row.last_seen = seen_at
                    row.expires_at = seen_at + UNMATCHED_TTL
                    changed = True
                if seen_at < row.first_seen:
                    row.first_seen = seen_at
                    changed = True
                if not row.display_name and item.display_name:
                    row.display_name = item.display_name
                    changed = True
                if changed:
                    row.save()


_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def _sort_key(parsed):
    return parsed.sent_at or parsed.internal_date or _EPOCH


def _internal(raw):
    return internal_date((raw or {}).get('internalDate'))
