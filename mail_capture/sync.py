"""The sync engine: reads one mailbox through a ``GmailClient`` and stores
what the matcher accepts.

Entry points are ``sync_mailbox`` and ``sync_all_enabled``. Both return
"capture disabled" before creating a client while the master switch is off,
while our own domains are not configured soundly, or when the mailbox (or
every mailbox) is not enabled.

Guarantees (research/11 B.7 "Idempotency and ordering", plus the PR-A review):

* One runner per mailbox: a lease on the ``CaptureMailbox`` row, taken with
  ``SELECT ... FOR UPDATE SKIP LOCKED`` and checked before every write.
* Each page (one history page or one list page) is written in a single
  transaction together with the cursor. Inside it, every message has its own
  savepoint: a message the database still refuses is recorded in
  ``CaptureFailure`` (Gmail id and error class only), counted, and skipped,
  and the cursor moves on. Failed messages are retried on later runs and
  parked after ``MAX_MESSAGE_ATTEMPTS``.
* One mailbox never stops the others: ``sync_all_enabled`` records a
  failure on that mailbox's run and carries on.
* The cursor never passes a message that was not processed: a run cut short
  by ``max_messages`` or by its quota budget stops at the last history record
  it finished and reports ``partial``.
* Upserts: one ``MailMessage`` per Message-ID, one ``MailboxCopy`` per
  (mailbox, Gmail id) and (mailbox, message). Re-running changes nothing.
* A history 404 sets ``needs_resync``; the next run does a bounded resync,
  which also re-reads the labels of copies it already holds inside the window
  (a private label added during the gap is enforced) and drops copies Gmail
  no longer lists there.
* Gmail's clock: retention, the queue expiry and the conversation clocks use
  Gmail's internal date. Direction comes from Gmail's SENT label.
* ``dry_run`` reads the mailbox and writes only its ``CaptureRun`` and
  ``MailboxAccessLog`` rows (the read itself must be on record).
* Every run that reads anything writes its access-log row before the first
  Gmail call and updates it at the end.
* Headers only by default. A body is fetched and stored only when the
  mailbox has ``body_mode='body'``, the message matched a company, and no
  headers-only rule or label applies. Unmatched mail never gets a body.

Logging is counts only: no subject, address or name is ever logged.
"""
import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta, timezone as dt_timezone

import hashlib

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
    CaptureFailure, CaptureMailbox, CaptureRun, MailboxAccessLog, MailboxCopy, MailConversation,
    MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from .parse import (
    METADATA_HEADERS, attachment_metadata, clean, domain_in, extract_body_text, internal_date,
    is_internal, parse_gmail_message,
)
from .purge import (
    drop_copies, enforce_label_rules, enforce_rules, message_key, purge_expired_unmatched,
    purged_token, refresh_conversations, scrub_queue,
)
from .snapshot import build_snapshot, load_rules, resolve_crm_sent


logger = logging.getLogger(__name__)

PAGE_SIZE = 100
LEASE_SECONDS = 15 * 60
MAX_ATTEMPTS = 4
MAX_MESSAGE_ATTEMPTS = 3
MAX_FAILED_IDS = 100
UNMATCHED_TTL = timedelta(days=30)
SUBJECT_FALLBACK_WINDOW = timedelta(days=30)
RESYNC_DEFAULT_WINDOW = timedelta(days=7)
MAX_SAMPLES = 3
MAX_MESSAGE_KEYS = 500

KINDS = ('incremental', 'backfill', 'resync')
_ACCESS_PURPOSE = {'incremental': 'poll', 'backfill': 'backfill', 'resync': 'resync'}

COUNT_FIELDS = (
    'listed', 'fetched', 'stored', 'copies_added', 'already_known', 'skipped_internal',
    'skipped_by_rule', 'skipped_system', 'matched', 'ambiguous', 'unmatched', 'purged',
    'malformed', 'failed', 'parked', 'errors',
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


# Changes whenever the deployed code changes (Render sets RENDER_GIT_COMMIT);
# ENGINE_VERSION covers local runs and is raised when this engine changes.
ENGINE_VERSION = 'mail_capture-2'


def code_version():
    import os
    return (os.environ.get('RENDER_GIT_COMMIT') or ENGINE_VERSION)[:80]


def is_message_data_error(exc):
    """Only errors about this message's data may fail just that message:
    the database refusing a value or a constraint, a validation error, a text
    encoding error. Anything else (a bug in the code, a lost connection, a
    timeout) is not the message's fault and must stop the run instead."""
    from django.core.exceptions import ValidationError
    from django.db import DataError
    if isinstance(exc, (DataError, IntegrityError, ValidationError, UnicodeError)):
        return True
    # psycopg2 refuses NUL characters with a plain ValueError.
    return isinstance(exc, ValueError) and 'NUL (0x00)' in str(exc)


class LeaseLost(Exception):
    """Another runner took the mailbox; this run stops without writing."""


class CaptureRefused(Exception):
    """A real client was offered while capture is switched off."""


def _disabled(reason, mailbox_id='', kind='', dry_run=False):
    return SyncResult(outcome='disabled', reason=reason, mailbox_id=str(mailbox_id or ''),
                      kind=kind, dry_run=dry_run)


def sync_all_enabled(client_factory, kind='incremental', **kwargs):
    """Run ``sync_mailbox`` for every enabled mailbox, one after another.
    A failure in one mailbox is recorded on that mailbox and does not stop
    the others."""
    state = conf.capture_state()
    dry_run = kwargs.get('dry_run', False)
    if not state.enabled:
        return [_disabled(state.reason, kind=kind, dry_run=dry_run)]
    ids = list(CaptureMailbox.objects.filter(enabled=True).order_by('email').values_list('pk', flat=True))
    if not ids:
        return [_disabled(conf.DISABLED_NO_MAILBOX, kind=kind, dry_run=dry_run)]
    results = []
    for pk in ids:
        try:
            results.append(sync_mailbox(pk, client_factory, kind=kind, **kwargs))
        except Exception as exc:  # recorded on its run by sync_mailbox or the runner
            logger.warning('mail capture mailbox=%s failed: %s', pk, type(exc).__name__)
            results.append(SyncResult(outcome='error', reason=type(exc).__name__,
                                      mailbox_id=str(pk), kind=kind, dry_run=dry_run))
    return results


def _record_setup_failure(mailbox, kind, dry_run, exc):
    """The client could not be created: record it on a run of its own."""
    now = timezone.now()
    run = CaptureRun.objects.create(
        mailbox=mailbox, kind=kind, dry_run=dry_run, started_at=now, finished_at=now,
        outcome='error', errors=1, error_summary=f'client: {type(exc).__name__}'[:200],
    )
    if not dry_run:
        CaptureMailbox.objects.filter(pk=mailbox.pk).update(
            last_error=f'client: {type(exc).__name__}'[:200],
            consecutive_errors=F('consecutive_errors') + 1,
        )
    return run


def sync_mailbox(mailbox_id, client_factory, kind='incremental', dry_run=False, since=None,
                 max_messages=None, max_quota_units=None, actor='job:gmail_sync', sleep=None,
                 page_size=PAGE_SIZE, lease_seconds=LEASE_SECONDS, fake_only=False,
                 maintenance=True, rules=None):
    """Sync one mailbox. ``client_factory(mailbox)`` returns a ``GmailClient``
    and is called only after every switch has been checked.

    ``fake_only`` (the self-check) lets the pipeline run while the master
    switch is off, and then only with a factory from
    ``gmail_client.fake_factory``: the factory is checked before it is called.
    ``maintenance=False`` skips applying rules to stored mail and expiring the
    queue; ``rules`` replaces the rules from the table (the self-check uses
    neither, so real rows and real rules cannot affect it).
    """
    if kind not in KINDS:
        raise ValueError(f'unknown sync kind {kind!r}')
    state = conf.capture_state()
    if not state.enabled:
        if not fake_only:
            return _disabled(state.reason, mailbox_id, kind, dry_run)
        if not getattr(client_factory, 'fake_only_factory', False):
            raise CaptureRefused('capture is switched off; only a fake_factory may be used')
    mailbox = CaptureMailbox.objects.filter(pk=mailbox_id).first()
    if mailbox is None or not mailbox.enabled:
        return _disabled(conf.DISABLED_MAILBOX, mailbox_id, kind, dry_run)
    domains = conf.domains_state()
    if not domains.enabled:
        return _disabled(domains.reason, mailbox_id, kind, dry_run)
    try:
        client = client_factory(mailbox)
    except Exception as exc:
        run = _record_setup_failure(mailbox, kind, dry_run, exc)
        logger.warning('mail capture run=%s mailbox=%s client failed: %s', run.pk, mailbox.pk,
                       type(exc).__name__)
        raise
    if not state.enabled and not isinstance(client, FakeGmailClient):
        raise CaptureRefused('capture is switched off; only the fake client may run')
    runner = _Runner(
        mailbox, client, kind=kind, dry_run=dry_run, since=since, max_messages=max_messages,
        max_quota_units=max_quota_units, actor=actor, sleep=sleep or time.sleep,
        page_size=page_size, lease_seconds=lease_seconds, maintenance=maintenance, rules=rules,
    )
    return runner.run()


@dataclass
class _Plan:
    parsed: object
    action: str                       # store | copy | labels | queue
    result: object = None             # MatchResult for store / queue
    conversation_key: str = ''
    message_pk: object = None         # existing MailMessage for copy
    copy_pk: object = None            # existing copy for labels
    body: str = None
    headers_only: bool = False
    count_as: str = ''                # counted only once the plan is written
    attachments: list = None          # from format=full when the body was read


class _BudgetSpent(Exception):
    pass


class _Stop(Exception):
    """Fetching stopped early (max_messages or budget); write what we have."""


class _Runner:
    def __init__(self, mailbox, client, kind, dry_run, since, max_messages, max_quota_units,
                 actor, sleep, page_size, lease_seconds, maintenance=True, rules=None):
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
        self.rules_override = rules
        self.token = ''
        self.counts = {name: 0 for name in COUNT_FIELDS}
        self.page = None              # counts of the page being written
        self.api_calls = 0
        self.quota_units = 0
        self.bodies_read = 0
        self.messages_read = 0
        self.fetched_total = 0
        self.partial = False
        self.failed_ids = []
        self.run_row = None
        self.access_row = None
        # Label ids that block NEW capture (every label rule, confirmed or not,
        # plus the built-in CRM private label) ...
        self.block_ids = frozenset()
        self.headers_only_block_ids = frozenset()
        # ... and those that may remove or strip mail already stored (the
        # built-in label and confirmed label rules only).
        self.private_ids = frozenset()
        self.headers_only_ids = frozenset()
        self.rules = ()

    # -- bookkeeping ---------------------------------------------------------
    def _bump(self, name, n=1):
        target = self.page if self.page is not None else self.counts
        target[name] = target.get(name, 0) + n

    def _call(self, name, *args, **kwargs):
        units_key = name
        if name == 'get_message' and kwargs.get('format') in ('full', 'minimal'):
            units_key = f'get_message_{kwargs["format"]}'
        fn = getattr(self.client, name)
        for attempt in range(MAX_ATTEMPTS):
            if self.max_quota_units is not None and self.quota_units >= self.max_quota_units:
                raise _BudgetSpent()
            if self.access_row is None:
                self._open_access_log()
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

    def _open_access_log(self):
        """Written before the first Gmail call, so a run that dies is on record."""
        self.access_row = MailboxAccessLog.objects.create(
            mailbox=self.mailbox, run=self.run_row, at=timezone.now(),
            purpose=_ACCESS_PURPOSE.get(self.kind, 'poll'), actor=self.actor[:80],
            dry_run=self.dry_run,
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
            self.run_row.failed_gmail_ids = self.failed_ids[:MAX_FAILED_IDS]
            self.run_row.error_summary = error_summary[:200]
            self.run_row.history_id_end = (
                CaptureMailbox.objects.filter(pk=self.mailbox.pk).values_list('history_id', flat=True).first()
                or ''
            )
            self.run_row.save()
        if self.access_row is not None:
            MailboxAccessLog.objects.filter(pk=self.access_row.pk).update(
                purpose=_ACCESS_PURPOSE.get(self.kind, 'poll'), finished_at=now,
                api_calls=self.api_calls, messages_read=self.messages_read,
                bodies_read=self.bodies_read,
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
                purged = enforce_rules(actor=self.actor)
                self._bump('purged', purged['messages'])
                purge_expired_unmatched(timezone.now())
            self.rules = load_rules() if self.rules_override is None else tuple(self.rules_override)
            self._load_labels()
            if self.kind == 'incremental' and self.mailbox.needs_resync:
                self.kind = 'resync'
            self._retry_failures()
            if self.kind == 'incremental':
                self._incremental()
            elif self.kind == 'resync':
                self._list_pass(resync=True)
            else:
                self._list_pass(resync=False)
            self._health(None)
            if self.partial:
                return self._finish('partial', 'stopped early; continues next run')
            if self.counts.get('failed') or self.counts.get('parked'):
                return self._finish('ok_with_failures',
                                    f"{self.counts.get('failed', 0)} failed, "
                                    f"{self.counts.get('parked', 0)} parked")
            return self._finish('ok')
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
            return self._finish('partial', 'quota budget spent; continues next run')
        except GmailError as exc:
            self._bump('errors')
            self._health(f'gmail {exc.status}')
            return self._finish('error', f'gmail {exc.status}')
        except LeaseLost:
            return self._finish('busy', 'lease lost to another runner')
        except Exception as exc:
            self._bump('errors')
            try:
                self._health(type(exc).__name__)
                self._finish('error', type(exc).__name__)
            except Exception:
                # The connection may be unusable (an error outside our own
                # transactions); keep the original error, which is what matters.
                logger.warning('mail capture run=%s could not record its error',
                               getattr(self.run_row, 'pk', None))
            raise
        finally:
            try:
                self._release()
            except Exception:
                logger.warning('mail capture run=%s could not release its lease',
                               getattr(self.run_row, 'pk', None))

    def _load_labels(self):
        labels = self._call('list_labels') or []
        by_id = {str(item.get('id')): str(item.get('name', '')) for item in labels if isinstance(item, dict)}
        mb = self.mailbox.pk
        self.block_ids = capture_rules.private_label_ids(by_id, self.rules, mb)
        self.headers_only_block_ids = capture_rules.headers_only_label_ids(by_id, self.rules, mb)
        self.private_ids = capture_rules.private_label_ids(by_id, self.rules, mb, confirmed_only=True)
        self.headers_only_ids = capture_rules.headers_only_label_ids(by_id, self.rules, mb, confirmed_only=True)
        # Which of this mailbox's label ids carry each label rule's name: the
        # admin preview counts stored copies with them before confirmation.
        rule_names = {r.value.strip().lower() for r in self.rules if r.kind == 'label'}
        rule_labels = {
            name: sorted(i for i, label in by_id.items() if label.strip().lower() == name)
            for name in sorted(rule_names)
        }
        state = {'private': sorted(self.private_ids), 'headers_only': sorted(self.headers_only_ids)}
        stored = dict(self.mailbox.enforced_label_ids or {})
        if self.dry_run:
            return
        if {k: stored.get(k) for k in state} != state:
            counts = enforce_label_rules(self.mailbox, self.private_ids, self.headers_only_ids,
                                         actor=self.actor)
            self._bump('purged', counts['messages'])
        if stored != dict(state, rule_labels=rule_labels):
            CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(
                enforced_label_ids=dict(state, rule_labels=rule_labels))

    # -- failures ------------------------------------------------------------
    def _retry_failures(self):
        """Messages that failed before get another chance, then are parked.
        Parked messages are retried again once the code version changes."""
        if self.dry_run:
            return
        CaptureFailure.objects.filter(mailbox=self.mailbox, parked=True).exclude(
            code_version=code_version()).update(parked=False, attempts=0)
        gids = list(CaptureFailure.objects.filter(mailbox=self.mailbox, parked=False)
                    .order_by('first_failed_at').values_list('gmail_id', flat=True)[:self.page_size])
        if not gids:
            return
        raws, gone = [], []
        for gid in gids:
            raw = self._fetch_one(gid)
            if raw is None:
                gone.append(gid)
            else:
                raws.append(raw)
        if gone:
            CaptureFailure.objects.filter(mailbox=self.mailbox, gmail_id__in=gone).delete()
        if raws:
            self._write_batch(raws, retry=True)

    def _record_failure(self, gmail_id, exc):
        now = timezone.now()
        error = type(exc).__name__[:80]
        row = CaptureFailure.objects.filter(mailbox=self.mailbox, gmail_id=gmail_id).first()
        if row is None:
            CaptureFailure.objects.create(mailbox=self.mailbox, gmail_id=gmail_id, error=error,
                                          first_failed_at=now, last_failed_at=now,
                                          code_version=code_version())
        else:
            row.attempts += 1
            row.error = error
            row.last_failed_at = now
            row.code_version = code_version()
            if row.attempts >= MAX_MESSAGE_ATTEMPTS:
                row.parked = True
                self._bump('parked')
            row.save(update_fields=['attempts', 'error', 'last_failed_at', 'parked', 'code_version'])
        self._bump('failed')
        if gmail_id not in self.failed_ids:
            self.failed_ids.append(gmail_id)
        logger.warning('mail capture run=%s mailbox=%s message failed: %s',
                       getattr(self.run_row, 'pk', None), self.mailbox.pk, error)

    # -- incremental -----------------------------------------------------------
    def _incremental(self):
        if not self.mailbox.history_id:
            profile = self._call('get_profile')
            if not self.dry_run:
                with transaction.atomic():
                    self._lock_for_write()
                    CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(
                        history_id=clean(profile.get('historyId'), 32), last_poll_at=timezone.now(),
                    )
            return
        cursor = self.mailbox.history_id
        page_token = None
        while True:
            resp = self._call('list_history', cursor, page_token=page_token, max_results=self.page_size)
            records = [r for r in (resp.get('history') or []) if isinstance(r, dict)]
            next_token = resp.get('nextPageToken')
            done_records, raws, stopped = self._fetch_history_page(records)
            if stopped:
                # Stop at the last record finished; never pass an unread message.
                new_cursor = clean(done_records[-1].get('id'), 32) if done_records else cursor
            elif next_token:
                new_cursor = clean(records[-1].get('id'), 32) if records else cursor
            else:
                new_cursor = clean(resp.get('historyId') or cursor, 32)
            deleted, label_changes = self._changes(done_records, {raw.get('id') for raw in raws})
            self._write_batch(
                raws, cursor={'history_id': new_cursor, 'last_poll_at': timezone.now()},
                deleted=deleted, label_changes=label_changes,
            )
            if stopped:
                self.partial = True
                return
            if not next_token:
                return
            page_token = next_token  # page tokens continue from the same start id

    def _fetch_history_page(self, records):
        """Fetch the messages added in ``records``, record by record. Returns
        the records fully handled, the messages fetched for them, and whether
        fetching stopped early (max_messages or the quota budget)."""
        added_anywhere = set()
        deleted = set()
        for record in records:
            for item in record.get('messagesDeleted') or ():
                gid = clean((item.get('message') or {}).get('id', ''), 64)
                if gid:
                    deleted.add(gid)
        wanted = []
        for record in records:
            for item in record.get('messagesAdded') or ():
                gid = clean((item.get('message') or {}).get('id', ''), 64)
                if gid and gid not in added_anywhere and gid not in deleted:
                    added_anywhere.add(gid)
                    wanted.append(gid)
        known = set(
            MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=wanted)
            .values_list('gmail_id', flat=True)
        )
        self._bump('listed', len(wanted))
        self._bump('already_known', len(known))
        done, raws, fetched = [], [], set()
        for record in records:
            ids = [
                clean((item.get('message') or {}).get('id', ''), 64)
                for item in record.get('messagesAdded') or ()
            ]
            for gid in ids:
                if not gid or gid in known or gid in deleted or gid in fetched:
                    continue
                if self.max_messages is not None and self.fetched_total >= self.max_messages:
                    return done, raws, True
                try:
                    raw = self._fetch_one(gid)
                except _BudgetSpent:
                    return done, raws, True
                fetched.add(gid)
                self.fetched_total += 1
                if raw is not None:
                    raws.append(raw)
            done.append(record)
        return done, raws, False

    def _changes(self, records, fetched_ids):
        deleted, label_changes = set(), []
        for record in records:
            for item in record.get('messagesDeleted') or ():
                gid = clean((item.get('message') or {}).get('id', ''), 64)
                if gid:
                    deleted.add(gid)
            for key, sign in (('labelsAdded', '+'), ('labelsRemoved', '-')):
                for item in record.get(key) or ():
                    gid = clean((item.get('message') or {}).get('id', ''), 64)
                    if gid and gid not in fetched_ids:
                        labels = [clean(x, 64) for x in (item.get('labelIds') or ())[:100]]
                        label_changes.append((gid, sign, labels))
        return deleted, label_changes

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
            new_cursor = clean(self._call('get_profile').get('historyId', ''), 32)
        page_token = None
        first = True
        done = False
        listed_in_window = set()
        complete = False
        while not done:
            resp = self._call('list_messages', page_token=page_token, max_results=self.page_size)
            ids = [clean(m.get('id'), 64) for m in resp.get('messages') or ()
                   if isinstance(m, dict) and m.get('id')]
            self._bump('listed', len(ids))
            known = dict(
                MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=ids)
                .values_list('gmail_id', 'internal_date')
            )
            raws, relabel = [], []
            stopped = False
            for gid in ids:
                if gid in known:
                    self._bump('already_known')
                    when = known[gid]
                    if when is not None and when < bound:
                        done = complete = True
                        break
                    listed_in_window.add(gid)
                    if resync:
                        relabel.append(gid)
                    continue
                if self.max_messages is not None and self.fetched_total >= self.max_messages:
                    done = stopped = True
                    break
                try:
                    raw = self._fetch_one(gid)
                except _BudgetSpent:
                    done = stopped = True
                    break
                self.fetched_total += 1
                if raw is None:
                    continue
                when = internal_date(raw.get('internalDate'))
                if when is not None and when < bound:
                    done = complete = True
                    break
                listed_in_window.add(gid)
                raws.append(raw)
            label_changes = []
            if relabel and not stopped:
                label_changes = self._reread_labels(relabel)
            page_token = resp.get('nextPageToken')
            if not page_token and not done:
                done = complete = True
            cursor = {}
            if new_cursor and not resync and first and not self.mailbox.history_id:
                cursor['history_id'] = new_cursor
            deleted = set()
            if resync and done and complete:
                cursor.update(history_id=new_cursor, needs_resync=False)
                deleted = self._vanished_in_window(bound, listed_in_window)
            if done and complete and not resync:
                cursor['last_full_sync_at'] = timezone.now()
            self._write_batch(raws, cursor=cursor, deleted=deleted, label_changes=label_changes)
            first = False
            if stopped:
                self.partial = True

    def _reread_labels(self, gids):
        """Current labels of copies we hold (format=minimal), as changes."""
        changes = []
        for gid in gids:
            try:
                raw = self._call('get_message', gid, format='minimal')
            except GmailNotFound:
                continue
            self.messages_read += 1
            labels = [clean(x, 64) for x in (raw.get('labelIds') or ())[:100]]
            changes.append((gid, '=', labels))
        return changes

    def _vanished_in_window(self, bound, listed):
        """Copies inside the resync window that Gmail no longer lists."""
        held = MailboxCopy.objects.filter(mailbox=self.mailbox, internal_date__gte=bound) \
            .values_list('gmail_id', flat=True)
        return {gid for gid in held if gid not in listed}

    # -- fetching ------------------------------------------------------------
    def _fetch_one(self, gid):
        try:
            raw = self._call('get_message', gid, format='metadata', metadata_headers=list(METADATA_HEADERS))
        except GmailNotFound:
            return None  # deleted since it was listed
        self.messages_read += 1
        self._bump('fetched')
        return raw if isinstance(raw, dict) else None

    # -- planning ------------------------------------------------------------
    def _plan(self, raws):
        parsed_all = [parse_gmail_message(raw) for raw in raws]
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
            decision = capture_rules.copy_decision(parsed.label_ids, self.block_ids)
            if parsed.gmail_id in existing_copies:
                plans.append(_Plan(parsed, 'labels', copy_pk=existing_copies[parsed.gmail_id]))
                self._bump('already_known')
                continue
            if decision == capture_rules.COPY_PRIVATE:
                self._bump('skipped_by_rule')
                if set(parsed.label_ids) & self.private_ids:
                    # Its queue samples (from earlier, unlabelled sightings) go too,
                    # but only for the built-in label or a confirmed rule.
                    plans.append(_Plan(parsed, 'scrub'))
                continue
            if decision == capture_rules.COPY_SKIP_SYSTEM or parsed.is_bulk:
                self._bump('skipped_system')
                continue
            action = capture_rules.message_rule_action(parsed.addresses(), self.rules, self.mailbox.pk)
            if action in capture_rules.DROP_ACTIONS:
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
            result = match_message(parsed, snapshot, self.mailbox.pk, conversation_key=key,
                                   sent=parsed.sent_label)
            headers_only = (
                result.rule_action == capture_rules.ACTION_HEADERS_ONLY
                or bool(set(parsed.label_ids) & self.headers_only_block_ids)
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
                plans.append(_Plan(parsed, 'queue', result=result, conversation_key=key,
                                   count_as='unmatched'))
                continue
            plans.append(_Plan(parsed, 'store', result=result, conversation_key=key,
                               headers_only=headers_only,
                               count_as='matched' if result.decision == MATCHED else 'ambiguous'))
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
        candidates = {p.conversation_key for p in parsed_list}
        candidates |= {purged_token(k) for k in list(candidates)}
        existing_keys = set(
            MailConversation.objects.filter(conversation_key__in=candidates)
            .values_list('conversation_key', flat=True)
        )
        domains_internal = conf.internal_domains()
        addresses_internal = conf.internal_addresses()
        in_batch = {}
        for parsed in parsed_list:
            key = None
            if parsed.conversation_key in existing_keys:
                key = parsed.conversation_key
            elif purged_token(parsed.conversation_key) in existing_keys:
                key = purged_token(parsed.conversation_key)
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
        return (
            MailConversation.objects.filter(
                subject_normalised=parsed.subject_normalised,
                last_message_at__gte=when - SUBJECT_FALLBACK_WINDOW,
                messages__participants__address__in=external,
            ).order_by('-last_message_at').values_list('conversation_key', flat=True).first()
        )

    # -- writing -------------------------------------------------------------
    def _write_batch(self, raws, cursor=None, deleted=(), label_changes=(), retry=False):
        """Plan and write one page. Its counts join the run's only if the page
        committed (or, in a dry run, was planned)."""
        self.page = {}
        ok = False
        try:
            plans = self._plan(raws)
            if self.dry_run:
                for plan in plans:
                    if plan.count_as:
                        self._bump(plan.count_as)
                ok = True
                return
            for plan in plans:
                if plan.action == 'store' and self._wants_body(plan):
                    try:
                        full = self._call('get_message', plan.parsed.gmail_id, format='full')
                    except GmailNotFound:
                        full = None
                    if isinstance(full, dict):
                        self.bodies_read += 1
                        payload = full.get('payload') or {}
                        plan.body = extract_body_text(payload) or None
                        plan.attachments = attachment_metadata(payload, plan.parsed.gmail_id)
            self._write_plans(plans, cursor, deleted, label_changes, retry)
            ok = True
        finally:
            page, self.page = self.page, None
            if ok and page:
                for name, value in page.items():
                    self.counts[name] = self.counts.get(name, 0) + value

    def _write_plans(self, plans, cursor, deleted, label_changes, retry):
        now = timezone.now()
        with transaction.atomic():
            self._lock_for_write()
            newest = None
            queue_ops = []
            succeeded = []
            for plan in plans:
                try:
                    with transaction.atomic():
                        self._apply(plan, now, queue_ops)
                except Exception as exc:
                    if not is_message_data_error(exc):
                        raise   # a code, connection or timeout error: abort, cursor unmoved
                    self._record_failure(plan.parsed.gmail_id, exc)
                    continue
                succeeded.append(plan.parsed.gmail_id)
                if plan.count_as:
                    self._bump(plan.count_as)
                internal = plan.parsed.internal_date
                if plan.action in ('store', 'copy', 'labels') and internal is not None \
                        and (newest is None or internal > newest):
                    newest = internal
            # Queue rows are locked in address order so two runners never deadlock.
            queue_ops.sort(key=lambda op: op[1].address)
            queue_failed = set()
            for parsed, item, reason, candidates in queue_ops:
                try:
                    with transaction.atomic():
                        self._queue_one(parsed, item, reason, candidates, now)
                except Exception as exc:
                    if not is_message_data_error(exc):
                        raise
                    if parsed.gmail_id not in queue_failed:
                        queue_failed.add(parsed.gmail_id)
                        self._record_failure(parsed.gmail_id, exc)
            succeeded = [gid for gid in succeeded if gid not in queue_failed]
            if succeeded:
                CaptureFailure.objects.filter(mailbox=self.mailbox, gmail_id__in=succeeded).delete()
            if deleted:
                copies = set(MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id__in=deleted)
                             .values_list('pk', flat=True))
                self._bump('purged', drop_copies(copies, 'gmail_deleted', self.mailbox, self.actor)['messages'])
            for gid, sign, label_ids in label_changes:
                self._label_change(gid, sign, label_ids)
            updates = dict(cursor or {})
            if newest is not None:
                current = CaptureMailbox.objects.filter(pk=self.mailbox.pk).values_list(
                    'newest_internal_date', flat=True).first()
                if current is None or newest > current:
                    updates['newest_internal_date'] = newest
            updates['lease_expires_at'] = now + timedelta(seconds=self.lease_seconds)
            CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(**updates)
            self.mailbox.refresh_from_db()

    def _apply(self, plan, now, queue_ops):
        if plan.action == 'labels':
            self._apply_labels(plan.copy_pk, plan.parsed.label_ids)
        elif plan.action == 'copy':
            self._add_copy(plan)
        elif plan.action == 'store':
            self._store(plan, now, queue_ops)
        elif plan.action == 'queue':
            for item in plan.result.queue_addresses:
                queue_ops.append((plan.parsed, item, plan.result.unmatched_reason, plan.result.candidates))
        elif plan.action == 'scrub':
            # A private copy of a message we never stored: its queue samples go.
            scrub_queue({message_key(plan.parsed.message_id)}, self.mailbox.email)

    def _label_change(self, gid, sign, label_ids):
        copy = MailboxCopy.objects.filter(mailbox=self.mailbox, gmail_id=gid).first()
        if copy is None:
            if sign in ('+', '=') and set(label_ids) & self.private_ids:
                # Private label on mail we never stored (unmatched): fetch the
                # headers once to find its queue samples, then remove them.
                try:
                    raw = self._fetch_one(gid)
                except _BudgetSpent:
                    raw = None
                if raw is not None:
                    parsed = parse_gmail_message(raw)
                    scrub_queue({message_key(parsed.message_id)}, self.mailbox.email)
            return
        labels = list(copy.label_ids or [])
        if sign == '+':
            labels = list(dict.fromkeys(labels + label_ids))
        elif sign == '-':
            labels = [x for x in labels if x not in label_ids]
        else:
            labels = list(label_ids)
        if set(labels) & (self.private_ids | capture_rules.DROP_ON_LABEL):
            reason = 'label' if set(labels) & self.private_ids else 'gmail_deleted'
            self._bump('purged', drop_copies({copy.pk}, reason, self.mailbox, self.actor)['messages'])
            return
        if labels != copy.label_ids:
            copy.label_ids = labels
            copy.save(update_fields=['label_ids', 'updated_at'])
            if 'SENT' in labels:
                self._upgrade_direction(copy.message_id)

    def _wants_body(self, plan):
        return (
            self.mailbox.body_mode == 'body'
            and plan.result is not None
            and plan.result.decision == MATCHED
            and not plan.headers_only
        )

    def _apply_labels(self, copy_pk, label_ids):
        if set(label_ids) & (self.private_ids | capture_rules.DROP_ON_LABEL):
            self._bump('purged', drop_copies({copy_pk}, 'label', self.mailbox, self.actor)['messages'])
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
            internal = plan.parsed.internal_date
            if internal is not None and internal < message.sent_at:
                MailMessage.objects.filter(pk=message.pk).update(sent_at=internal)
                refresh_conversations([message.conversation_id])
            if plan.parsed.sent_label:
                self._upgrade_direction(message.pk, plan.parsed)

    def _upgrade_direction(self, message_pk, parsed=None):
        """A copy with SENT proves the message went out from a captured
        mailbox: make it outbound, link it to the CRM's EmailLog if any, and
        recompute the conversation's clocks."""
        message = MailMessage.objects.filter(pk=message_pk).first()
        if message is None or message.direction == 'outbound':
            return
        updates = {'direction': 'outbound'}
        if parsed is not None and message.email_log_id is None:
            row = resolve_crm_sent(parsed)
            if row is not None:
                updates['email_log_id'] = row.pk
        MailMessage.objects.filter(pk=message_pk).update(**updates)
        refresh_conversations([message.conversation_id])

    def _store(self, plan, now, queue_ops):
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
                    claimed_date=parsed.claimed_date,
                    from_address=sender.address if sender else '',
                    from_name=sender.display_name if sender else '',
                    subject=parsed.subject,
                    direction=result.direction,
                    flags=self._message_flags(parsed, result),
                    in_reply_to=parsed.in_reply_to,
                    references=list(parsed.references),
                    has_attachments=bool(plan.attachments if plan.attachments is not None
                                         else parsed.attachments),
                    attachments=list(plan.attachments if plan.attachments is not None
                                     else parsed.attachments),
                    body_text=body,
                    body_sha256=hashlib.sha256(body.encode('utf-8')).hexdigest() if body else '',
                    capture_state='body' if body else 'headers',
                    headers_only_rule=plan.headers_only,
                    email_log_id=result.email_log_id,
                )
        except IntegrityError:
            # Stored meanwhile by a runner on another mailbox: just add our copy.
            message = MailMessage.objects.filter(rfc_message_id=parsed.message_id).first()
            if message is None:
                raise
            if self._create_copy(message, parsed):
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
        # A recipient found only by the overflow scan is kept when it matched
        # a contact (role unknown between To and Cc: recorded as cc).
        for item in getattr(parsed, 'overflow', ()) or ():
            contact_id = result.contacts.get(item.address)
            if contact_id and ('cc', item.address) not in seen and ('to', item.address) not in seen:
                seen.add(('cc', item.address))
                participants.append(MailParticipant(
                    message=message, role='cc', address=item.address, display_name='',
                    domain=item.domain, is_internal=False, contact_id=contact_id,
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
            queue_ops.append((parsed, address, 'domain_match', (company_id,)))
        self._bump('stored')

    def _message_flags(self, parsed, result):
        """Parser flags, plus ``dkim_pass_internal`` when a From that claims an
        internal sender is backed by Gmail's own DKIM verdict for one of our
        domains (a hint for a later unanswered-clock rule; it changes nothing
        here: direction still needs the SENT label)."""
        flags = set(parsed.flags)
        if result.direction == 'claimed_internal':
            internal = conf.internal_domains()
            sender_domain = parsed.from_address.domain if parsed.from_address else ''
            for domain in parsed.dkim_pass_domains:
                if (domain_in(domain, internal) and sender_domain
                        and (sender_domain == domain or sender_domain.endswith('.' + domain))):
                    flags.add('dkim_pass_internal')
                    break
        return sorted(flags)

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
        target.is_mixed = target.is_mixed or other.is_mixed or (
            bool(target.company_id and other.company_id) and target.company_id != other.company_id
        )
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
        # claimed_internal feeds only the hint field, never last_outbound_at.
        side = {'inbound': 'last_inbound_at', 'outbound': 'last_outbound_at',
                'claimed_internal': 'last_claimed_internal_at'}.get(message.direction)
        if side:
            updates[side] = Greatest(Coalesce(side, sent), sent)
        MailConversation.objects.filter(pk=conversation.pk).update(**updates)

        row = MailConversation.objects.select_for_update(no_key=True).get(pk=conversation.pk)
        changed = []
        companies = set(result.companies or ()) | ({result.company_id} if result.company_id else set())
        companies = {str(c) for c in companies if c}
        if row.company_id and companies - {str(row.company_id)} and not row.is_mixed:
            row.is_mixed = True
            changed.append('is_mixed')
        elif len(companies) > 1 and not row.is_mixed:
            row.is_mixed = True
            changed.append('is_mixed')
        if row.link_state != 'confirmed':
            if result.decision == MATCHED and row.link_state == 'none' and row.company_id is None:
                row.company_id = result.company_id
                row.link_state = 'auto'
                changed += ['company', 'link_state']
            elif result.decision == AMBIGUOUS and row.link_state == 'none':
                row.link_state = 'ambiguous'
                changed.append('link_state')
        if changed:
            row.save(update_fields=sorted(set(changed)) + ['updated_at'])

    def _queue_one(self, parsed, item, reason, candidates, now):
        """Upsert one unmatched-sender row. Headers only: address, name,
        domain, counts and up to three subjects, each with its message key and
        mailbox. Times come from Gmail's internal date, never the Date header."""
        if not item.address:
            return
        key = message_key(parsed.message_id)
        mailbox = self.mailbox.email
        seen_at = parsed.internal_date or now
        if seen_at > now + timedelta(days=1):
            seen_at = now
        sample = {'k': key, 'm': mailbox, 's': parsed.subject} if parsed.subject else None
        row = UnmatchedSender.objects.select_for_update().filter(address=item.address).first()
        if row is None:
            try:
                with transaction.atomic():
                    UnmatchedSender.objects.create(
                        address=item.address, domain=item.domain, display_name=item.display_name,
                        first_seen=seen_at, last_seen=seen_at, message_count=1,
                        message_keys=[[key, mailbox]], mailboxes=[mailbox],
                        samples=[sample] if sample else [],
                        candidate_company_ids=[str(c) for c in candidates],
                        reason=reason, expires_at=seen_at + UNMATCHED_TTL,
                    )
                return
            except IntegrityError:
                row = UnmatchedSender.objects.select_for_update().get(address=item.address)
        if row.status == 'never_log':
            return
        pairs = [list(p) for p in (row.message_keys or []) if isinstance(p, (list, tuple)) and len(p) == 2]
        changed = False
        if [key, mailbox] not in pairs:
            pairs = (pairs + [[key, mailbox]])[-MAX_MESSAGE_KEYS:]
            row.message_keys = pairs
            row.message_count = len({p[0] for p in pairs})
            row.mailboxes = sorted({p[1] for p in pairs})
            # A sample never outlives its key: when the oldest key is rotated
            # out, its subject goes too, so a later purge can always find it.
            kept = {p[0] for p in pairs}
            samples = [s for s in (row.samples or []) if isinstance(s, dict) and s.get('k') in kept]
            if sample and not any(s.get('k') == key for s in samples) and len(samples) < MAX_SAMPLES:
                samples = samples + [sample]
            row.samples = samples
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
