"""The sync engine: reads one mailbox through a ``GmailClient`` and stores
what the matcher accepts.

Entry points are ``sync_mailbox`` and ``sync_all_enabled`` (which reads every
enabled mailbox, so it must be asked for with ``all_mailboxes=True``). Both return
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
* One message Gmail refuses never stalls the mailbox: 404/410 is skipped and
  counted as ``gone``; a 400 (or another per-item 4xx that is not a rate
  limit or a permission error), or a 5xx repeated on that one id, becomes
  that message's ``CaptureFailure`` (retried on later runs, parked after
  ``MAX_MESSAGE_ATTEMPTS``) and the cursor moves on. A per-item 429 or 403
  rate limit retries only the affected items, with backoff; if Gmail keeps
  refusing, the run stops there, keeps what it finished, and ends
  ``rate_limited``. A 5xx on every item of a batch is an outage: the run
  stops (``error``) with the cursor unmoved.
* Authentication and permission failures end the run at once, without
  retries, with outcome ``auth_error`` and an operator hint naming the likely
  setup step (``gmail_client.AUTH_HINTS``). No token, assertion or key path
  is ever part of it.
* A run that fails on one message records its Gmail id and the exception
  class on the run row. Failures are of three kinds:

  - **message or code errors** (outcome ``error``): after
    ``CAPTURE_ATTENTION_AFTER_ERRORS`` (default 3) such runs in a row the
    mailbox is marked ``needs_attention`` (logged at ERROR) and is not run
    again until a person clears it (admin action, ``gmail_sync --skip-once``
    or ``--clear-attention``) or the code version changes;
  - **temporary failures** (``rate_limited``; ``unavailable``: Gmail 5xx on
    everything, or the token endpoint unreachable): the mailbox backs off
    (``retry_not_before``, 1 minute doubling to 60, or Gmail's Retry-After;
    runs before then end ``deferred`` without a Gmail call) and needs
    attention only after ``CAPTURE_TRANSIENT_ATTENTION_HOURS`` (default 24)
    of nothing but temporary failures;
  - **refused authentication** (``auth_error``): shown at once
    (``auth_problem``, ``gmail_sync --check``), never a reason to stop the
    mailbox. For scheduling it backs off like a temporary failure (so a cron
    does not hammer the token endpoint); the next successful token clears it
    and the backoff.

  ``Retry-After`` is never trusted beyond ``MAX_RETRY_AFTER`` (300 s). A
  person's ``--clear-attention`` or a new code version clears the backoff
  state too.
* Pacing: before every call the engine asks the client's token buckets
  (``QuotaPacer``) for the call's quota units, so a backfill stays under
  Gmail's per-mailbox per-minute quota instead of hitting 429. A real 429
  empties the bucket and backs off, honouring ``Retry-After`` when sent.
* ``max_messages`` and ``max_quota_units`` are never overshot: a batch asks
  for no more ids than remain, and no call starts that the budget cannot pay.

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
    QUOTA_UNITS, FakeGmailClient, GmailAuthError, GmailError, GmailNotFound, GmailRateLimited,
    GmailServerError,
)
from .match import (
    AMBIGUOUS, MALFORMED, MATCHED, SKIP_INTERNAL, SKIP_RULE, UNMATCHED, match_message,
)
from .models import (
    CaptureFailure, CaptureMailbox, CaptureRun, CaptureSkip, MailboxAccessLog, MailboxCopy, MailConversation,
    MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from .parse import (
    METADATA_HEADERS, attachment_metadata, clean, extract_body_text, internal_date,
    is_internal, parse_gmail_message,
)
from .purge import copy_purge_action as capture_rules_copy_action
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
BATCH_SIZE = 50          # messages per Gmail batch request (Gmail allows 100, recommends 50)
UNMATCHED_TTL = timedelta(days=30)
SUBJECT_FALLBACK_WINDOW = timedelta(days=30)
RESYNC_DEFAULT_WINDOW = timedelta(days=7)
MAX_SAMPLES = 3
MAX_MESSAGE_KEYS = 500
# Consecutive 5xx answers to single-message gets (no success between them)
# that are taken as an outage rather than as those messages' failures.
OUTAGE_AFTER = 3
# Backoff after a 429 when Gmail sends no Retry-After: together longer than
# the minute the per-user quota is counted over.
RATE_BACKOFF = (15.0, 30.0, 60.0)
MAX_RETRY_AFTER = 300.0
# Between runs after a temporary failure: 1, 2, 4 ... minutes, at most 60.
TRANSIENT_BACKOFF_MINUTES = (1, 2, 4, 8, 16, 32, 60)

CODE, TRANSIENT, AUTH, RESYNC = 'code', 'transient', 'auth', 'resync'

KINDS = ('incremental', 'backfill', 'resync')
_ACCESS_PURPOSE = {'incremental': 'poll', 'backfill': 'backfill', 'resync': 'resync'}

COUNT_FIELDS = (
    'listed', 'fetched', 'stored', 'copies_added', 'already_known', 'skipped_internal',
    'skipped_by_rule', 'skipped_system', 'matched', 'ambiguous', 'unmatched', 'purged',
    'malformed', 'failed', 'parked', 'errors', 'gone', 'skipped_by_person',
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


# The code version parked messages and the needs-attention flag are tied to.
# On Render it is RENDER_GIT_COMMIT, which changes with every deploy. Elsewhere
# it is ENGINE_VERSION plus a hash of this app's migration files: raise
# ENGINE_VERSION when a fix to the engine should retry parked messages on a
# host without RENDER_GIT_COMMIT (or run mail_capture_unpark --all).
ENGINE_VERSION = 'mail_capture-3'
_LOCAL_VERSION = []


def _migration_state():
    from pathlib import Path
    folder = Path(__file__).resolve().parent / 'migrations'
    names = sorted(p.name for p in folder.glob('[0-9]*.py'))
    return hashlib.sha256('|'.join(names).encode('utf-8')).hexdigest()[:12]


def code_version():
    import os
    commit = os.environ.get('RENDER_GIT_COMMIT', '').strip()
    if commit:
        return commit[:80]
    if not _LOCAL_VERSION:
        _LOCAL_VERSION.append(f'{ENGINE_VERSION}+{_migration_state()}')
    return _LOCAL_VERSION[0][:80]


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


def sync_all_enabled(client_factory, kind='incremental', *, all_mailboxes=False, **kwargs):
    """Run ``sync_mailbox`` for every enabled mailbox, one after another.
    A failure in one mailbox is recorded on that mailbox and does not stop
    the others. Like ``gmail_sync --all-mailboxes``, it reads every enabled
    mailbox, so it refuses unless ``all_mailboxes=True`` is passed on purpose."""
    if all_mailboxes is not True:
        raise ValueError('sync_all_enabled reads every enabled mailbox: pass all_mailboxes=True on purpose')
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


def is_credential_error(exc):
    """A credential that could not be made: a setting is missing or invalid,
    or google.auth refused while building it."""
    from .credentials import CredentialsMisconfigured
    if isinstance(exc, (CredentialsMisconfigured, GmailAuthError)):
        return True
    return any(cls.__module__.startswith('google.auth') for cls in type(exc).__mro__)


def _record_setup_failure(mailbox, kind, dry_run, exc, outcome='error', summary=None):
    """The client could not be created: record it on a run of its own."""
    now = timezone.now()
    summary = (summary or f'client: {type(exc).__name__}')[:200]
    run = CaptureRun.objects.create(
        mailbox=mailbox, kind=kind, dry_run=dry_run, started_at=now, finished_at=now,
        outcome=outcome, errors=1, error_summary=summary, error_class=type(exc).__name__[:80],
    )
    if not dry_run:
        record_health(mailbox.pk, AUTH if outcome == 'auth_error' else CODE, summary)
    return run


def record_health(mailbox_pk, kind=None, error='', needs_resync=None, retry_after=None, reason=None):
    """The mailbox's health after a run. ``kind`` None is a success: every
    counter, the backoff and the auth problem are cleared. Otherwise ``kind``
    is CODE (a message or code error: counts towards needs-attention),
    TRANSIENT (backs off; needs attention only after hours of nothing else),
    AUTH (shown in ``auth_problem``; never stops the mailbox) or RESYNC."""
    now = timezone.now()
    updates = {}
    if needs_resync is not None:
        updates['needs_resync'] = needs_resync
    if kind is None:
        updates.update(last_error='', consecutive_errors=0, attention_errors=0, transient_errors=0,
                       transient_since=None, retry_not_before=None, auth_problem='')
        CaptureMailbox.objects.filter(pk=mailbox_pk).update(**updates)
        return
    updates.update(last_error=error[:200], consecutive_errors=F('consecutive_errors') + 1)
    if kind == CODE:
        updates['attention_errors'] = F('attention_errors') + 1
    elif kind == AUTH:
        # Shown at once; for scheduling it backs off like a temporary failure
        # (no hot loop on the token endpoint under a cron), without the
        # 24-hour attention rule. The next good token clears both.
        updates.update(auth_problem=error[:200], transient_errors=F('transient_errors') + 1)
    elif kind == TRANSIENT:
        updates.update(transient_errors=F('transient_errors') + 1,
                       transient_since=Coalesce(F('transient_since'), Value(now)))
    CaptureMailbox.objects.filter(pk=mailbox_pk).update(**updates)
    if kind == CODE:
        mark_attention_if_due(mailbox_pk, reason or error)
    elif kind in (TRANSIENT, AUTH):
        row = CaptureMailbox.objects.filter(pk=mailbox_pk).values('transient_errors', 'transient_since').first()
        step = TRANSIENT_BACKOFF_MINUTES[min(max(row['transient_errors'], 1), len(TRANSIENT_BACKOFF_MINUTES)) - 1]
        try:
            hinted = min(MAX_RETRY_AFTER, max(0.0, float(retry_after or 0)))   # never trust a huge Retry-After
        except (TypeError, ValueError):
            hinted = 0.0
        wait = max(step * 60.0, hinted)
        CaptureMailbox.objects.filter(pk=mailbox_pk).update(retry_not_before=now + timedelta(seconds=wait))
        hours = conf.transient_attention_hours()
        if kind == TRANSIENT and row['transient_since'] and now - row['transient_since'] >= timedelta(hours=hours):
            mark_attention(mailbox_pk, f'only temporary failures for {hours} hours (last: {error})'[:200],
                           f'{hours} hours of temporary failures')


def mark_attention(mailbox_pk, reason, why):
    marked = CaptureMailbox.objects.filter(pk=mailbox_pk, needs_attention=False).update(
        needs_attention=True, attention_reason=reason[:200], attention_code_version=code_version())
    if marked:
        logger.error('mail capture mailbox=%s needs attention after %s: %s', mailbox_pk, why, reason[:200])
    return bool(marked)


def mark_attention_if_due(mailbox_pk, reason):
    """After CAPTURE_ATTENTION_AFTER_ERRORS runs in a row that failed on a
    message or a code error, the mailbox needs a person: runs stop until it is
    cleared. Logged at ERROR (no alert e-mail). ``reason`` holds an error
    class and a Gmail id at most."""
    threshold = conf.attention_after_errors()
    if not CaptureMailbox.objects.filter(pk=mailbox_pk, attention_errors__gte=threshold).exists():
        return False
    return mark_attention(mailbox_pk, reason, f'{threshold} failed runs')


def clear_attention(mailbox, actor, why):
    """A person cleared the flag (and any backoff): runs may start again. On
    the access log."""
    CaptureMailbox.objects.filter(pk=mailbox.pk).update(
        needs_attention=False, attention_reason='', attention_code_version='', consecutive_errors=0,
        attention_errors=0, transient_errors=0, transient_since=None, retry_not_before=None,
    )
    MailboxAccessLog.objects.create(
        mailbox=mailbox, at=timezone.now(), finished_at=timezone.now(), purpose='config',
        actor=str(actor)[:80], detail={'cleared_attention': True, 'reason': str(why)[:200]},
    )


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
    if mailbox.needs_attention:
        if mailbox.attention_code_version and mailbox.attention_code_version != code_version():
            # New code since the flag was set (a deploy with a fix): try again.
            CaptureMailbox.objects.filter(pk=mailbox.pk).update(
                needs_attention=False, attention_code_version='', consecutive_errors=0, attention_errors=0,
                transient_errors=0, transient_since=None, retry_not_before=None)
            mailbox.refresh_from_db()
            logger.info('mail capture mailbox=%s attention cleared by a new code version', mailbox.pk)
        else:
            return SyncResult(outcome='needs_attention', reason=mailbox.attention_reason,
                              mailbox_id=str(mailbox.pk), kind=kind, dry_run=dry_run)
    if mailbox.retry_not_before and mailbox.retry_not_before > timezone.now():
        return SyncResult(
            outcome='deferred', mailbox_id=str(mailbox.pk), kind=kind, dry_run=dry_run,
            reason=f'backing off after a failure ({mailbox.last_error}) until '
                   f'{mailbox.retry_not_before:%Y-%m-%d %H:%M:%S} UTC'[:200])
    try:
        client = client_factory(mailbox)
    except Exception as exc:
        if is_credential_error(exc):
            from .credentials import CredentialsMisconfigured
            hint = GmailAuthError(getattr(exc, 'code', 'credentials'))
            # CredentialsMisconfigured texts are fixed and name a setting only.
            detail = str(exc) if isinstance(exc, CredentialsMisconfigured) else hint.hint
            summary = f'auth {hint.code}: {detail}'
            run = _record_setup_failure(mailbox, kind, dry_run, exc, outcome='auth_error', summary=summary)
            logger.warning('mail capture run=%s mailbox=%s credential failed: %s', run.pk, mailbox.pk,
                           type(exc).__name__)
            return SyncResult(outcome='auth_error', reason=summary, run_id=run.pk,
                              mailbox_id=str(mailbox.pk), kind=kind, dry_run=dry_run)
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


# A batch item the budget could not pay for a retry: the loop stops there.
_UNPAID = object()


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
        self.current_gid = ''         # the message being worked on (for a run error)
        self.error_gid = ''
        self.error_class = ''
        self.stop_reason = ''         # 'rate_limited' when Gmail kept refusing mid-page
        self.stop_retry_after = None
        self.skips = {}               # gmail id -> CaptureSkip pk, unused skips
        self._skipped_now = set()
        self._fetch_failed = {}       # gmail id -> GmailError, recorded with the page
        self._server_errors_in_row = 0
        self.access_row = None
        # Label ids that block NEW capture (every label rule, confirmed or not,
        # plus the built-in CRM private label) ...
        self.block_ids = frozenset()
        self.headers_only_block_ids = frozenset()
        # ... and those that may remove or strip mail already stored (the
        # built-in label and confirmed label rules only).
        self.private_ids = frozenset()
        self.headers_only_ids = frozenset()
        self.builtin_private_ids = frozenset()
        self.drop_map = {}
        self.strip_map = {}
        self.rules = ()

    # -- bookkeeping ---------------------------------------------------------
    def _bump(self, name, n=1):
        target = self.page if self.page is not None else self.counts
        target[name] = target.get(name, 0) + n

    def _call(self, name, *args, **kwargs):
        """One Gmail call: paced, counted against the budget, retried with
        backoff on 429/rate-limit 403 and 5xx. Authentication and permission
        errors (``GmailAuthError``) and other 4xx are never retried."""
        units = kwargs.pop('_units', None)
        units_key = name
        if name == 'get_message' and kwargs.get('format') in ('full', 'minimal'):
            units_key = f'get_message_{kwargs["format"]}'
        cost = units if units is not None else QUOTA_UNITS.get(units_key, 1)
        fn = getattr(self.client, name)
        for attempt in range(MAX_ATTEMPTS):
            self._pay(cost)
            try:
                return fn(*args, **kwargs)
            except GmailRateLimited as exc:
                self._drain_pace()
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                self.sleep(self._rate_delay(attempt, [exc]))
            except GmailServerError:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                self.sleep(self._server_delay(attempt))
        raise AssertionError('unreachable')

    def _pay(self, cost):
        """Refuse a call the budget cannot pay; wait for the pace; count it."""
        if self.max_quota_units is not None and self.quota_units + cost > self.max_quota_units:
            raise _BudgetSpent()
        if self.access_row is None:
            self._open_access_log()
        pace = getattr(self.client, 'pace', None)
        if pace is not None:
            pace(cost, self.sleep)
        self.api_calls += 1
        self.quota_units += cost

    def _drain_pace(self):
        drain = getattr(self.client, 'drain_pace', None)
        if drain is not None:
            drain()

    @staticmethod
    def _rate_delay(attempt, errors):
        hinted = [e.retry_after for e in errors if getattr(e, 'retry_after', None) is not None]
        if hinted:
            return min(MAX_RETRY_AFTER, max(hinted))
        base = RATE_BACKOFF[min(attempt, len(RATE_BACKOFF) - 1)]
        return base * (0.75 + random.random() / 4)

    @staticmethod
    def _server_delay(attempt):
        return min(32.0, 2.0 ** attempt) * (0.5 + random.random() / 2)

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
            self.run_row.error_gmail_id = (self.error_gid or '')[:64]
            self.run_row.error_class = (self.error_class or '')[:80]
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

    def _health(self, error=None, needs_resync=None, kind=CODE, retry_after=None):
        if self.dry_run:
            return
        if error is None:
            record_health(self.mailbox.pk, None, needs_resync=needs_resync)
            return
        reason = error
        if self.error_class:
            reason = f'{self.error_class}' + (f' on gmail id {self.error_gid}' if self.error_gid else '')
        record_health(self.mailbox.pk, kind, error, needs_resync=needs_resync, retry_after=retry_after,
                      reason=reason)

    def _note_error(self, exc):
        self.error_class = type(exc).__name__
        self.error_gid = self.current_gid

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
            self.skips = dict(CaptureSkip.objects.filter(mailbox=self.mailbox, used_at__isnull=True)
                              .values_list('gmail_id', 'pk'))
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
            if self.stop_reason == 'rate_limited':
                self._bump('errors')
                self._health('rate limited 429', kind=TRANSIENT, retry_after=self.stop_retry_after)
                return self._finish('rate_limited', 'gmail kept rate-limiting; progress kept, continues next run')
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
            self._health('history 404', needs_resync=True, kind=RESYNC)
            return self._finish('resync_needed', 'history id no longer valid')
        except GmailRateLimited as exc:
            self._bump('errors')
            self._health(f'rate limited {exc.status}', kind=TRANSIENT, retry_after=exc.retry_after)
            return self._finish('rate_limited', f'gmail {exc.status}')
        except _BudgetSpent:
            if self.stop_reason == 'rate_limited':
                self._bump('errors')
                self._health('rate limited 429', kind=TRANSIENT, retry_after=self.stop_retry_after)
                return self._finish('rate_limited', 'gmail kept rate-limiting; continues next run')
            self._health(None)
            return self._finish('partial', 'quota budget spent; continues next run')
        except GmailAuthError as exc:
            # Never retried within the run.
            self._bump('errors')
            self.error_class = type(exc).__name__
            summary = f'auth {exc.code}: {exc.hint}'
            if exc.transient:
                self._health(summary, kind=TRANSIENT)
                return self._finish('unavailable', summary)
            self._health(summary, kind=AUTH)
            logger.error('mail capture run=%s mailbox=%s authentication refused: %s',
                         getattr(self.run_row, 'pk', None), self.mailbox.pk, exc.code)
            return self._finish('auth_error', summary)
        except GmailServerError as exc:
            # Gmail failed on everything, even after retries: an outage.
            self._bump('errors')
            self.error_class = type(exc).__name__
            self._health(f'gmail {exc.status}', kind=TRANSIENT)
            return self._finish('unavailable', f'gmail {exc.status}: Gmail unavailable; retried later')
        except GmailError as exc:
            self._bump('errors')
            self._note_error(exc)
            self._health(f'gmail {exc.status}')
            return self._finish('error', f'gmail {exc.status}')
        except LeaseLost:
            return self._finish('busy', 'lease lost to another runner')
        except Exception as exc:
            self._bump('errors')
            self._note_error(exc)
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
        # What may remove stored copies: the built-in label at once, a label
        # rule only for the copies its confirmed preview covered.
        self.builtin_private_ids, self.drop_map, self.strip_map = capture_rules.label_purge_maps(
            by_id, self.rules, mb)
        covered = hashlib.sha256(repr(sorted(
            (label, sorted(ids)) for table in (self.drop_map, self.strip_map) for label, ids in table.items()
        )).encode('utf-8')).hexdigest()[:16]
        state = {'private': sorted(self.private_ids), 'headers_only': sorted(self.headers_only_ids),
                 'covered': covered}
        stored = dict(self.mailbox.enforced_label_ids or {})
        if self.dry_run:
            return
        if {k: stored.get(k) for k in state} != state:
            counts = enforce_label_rules(self.mailbox, self.builtin_private_ids, self.drop_map,
                                         self.strip_map, actor=self.actor)
            self._bump('purged', counts['messages'])
            if counts.get('pending'):
                logger.info('mail capture mailbox=%s label rules: %d stored copies labelled after the '
                            'preview wait for a new preview', self.mailbox.pk, counts['pending'])
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
            if raw is not None:
                raws.append(raw)
            elif gid not in self._fetch_failed:
                gone.append(gid)       # gone from Gmail, or skipped by a person
        if gone:
            CaptureFailure.objects.filter(mailbox=self.mailbox, gmail_id__in=gone).delete()
        if raws or self._fetch_failed or self._skipped_now:
            self._write_batch(raws, retry=True)

    def _record_failure(self, gmail_id, exc):
        now = timezone.now()
        # A Gmail refusal keeps its status and reason code ("gmail 400 badRequest");
        # anything else only its class name.
        error = (str(exc) if isinstance(exc, GmailError) else type(exc).__name__)[:80]
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
        todo = [g for g in wanted if g not in known]
        if self.max_messages is not None:
            todo = todo[:max(0, self.max_messages - self.fetched_total)]
        self._plan_fetch(todo)
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
            self._plan_fetch([g for g in ids if g not in known])
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
            self.current_gid = gid
            try:
                raw = self._call('get_message', gid, format='minimal')
            except GmailNotFound:
                continue
            except (GmailAuthError, GmailRateLimited, GmailServerError):
                raise
            except GmailError as exc:
                self._fetch_failed[gid] = exc   # retried later; its labels are re-read then
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
    def _plan_fetch(self, gids):
        """Announce the ids the next loop will ask for, in order, so a client
        that supports batches can fetch them BATCH_SIZE at a time. Chunks are
        fetched lazily, so a loop that stops early (bound, max_messages, budget)
        never fetches far past where it stopped."""
        self._pending = [g for g in gids if g and g not in self.skips]
        self._pending_set = set(self._pending)
        self._prefetched = {}

    def _fetch_one(self, gid):
        """The message's metadata, or None when it is gone (404/410), skipped
        by a person, or failed on its own (then held in ``_fetch_failed`` and
        recorded with the page). Raises ``_BudgetSpent`` to stop the loop
        (budget, or Gmail still rate-limiting: ``stop_reason``), and run-level
        errors (authentication, an outage) as they are."""
        self.current_gid = gid
        if gid in self.skips:
            self._skipped_now.add(gid)
            self._bump('skipped_by_person')
            return None
        if gid in getattr(self, '_prefetched', {}):
            raw = self._prefetched.pop(gid)
        elif getattr(self.client, 'supports_batch', False) and gid in getattr(self, '_pending_set', ()):
            self._fetch_chunk_from(gid)
            raw = self._prefetched.pop(gid, None)
        else:
            raw = self._get_single(gid)
        if raw is _UNPAID:
            raise _BudgetSpent()
        if isinstance(raw, GmailRateLimited):
            self.stop_reason = 'rate_limited'
            self.stop_retry_after = raw.retry_after
            raise _BudgetSpent()
        if isinstance(raw, GmailError):
            self._fetch_failed[gid] = raw
            return None
        if not isinstance(raw, dict):
            if raw is None:
                self._bump('gone')
            return None
        self._bump('fetched')
        return raw

    def _get_single(self, gid):
        try:
            raw = self._call('get_message', gid, format='metadata', metadata_headers=list(METADATA_HEADERS))
        except GmailNotFound:
            return None  # deleted since it was listed
        except GmailAuthError:
            raise
        except GmailRateLimited as exc:
            return exc
        except GmailServerError as exc:
            # Retried in _call already. A few in a row with no success between
            # them is an outage, not these messages' fault.
            self._server_errors_in_row += 1
            if self._server_errors_in_row >= OUTAGE_AFTER:
                raise
            return exc
        except GmailError as exc:
            return exc   # 400 and the like: this message's failure
        self._server_errors_in_row = 0
        self.messages_read += 1
        return raw

    def _fetch_chunk_from(self, gid):
        """Fetch the next chunk of announced ids in one batch, no more than
        ``max_messages`` and the budget allow. Items Gmail refused for rate or
        5xx are retried on their own with backoff; what is left after that is
        decided per item (see the module docstring)."""
        per = QUOTA_UNITS['get_message']
        size = BATCH_SIZE
        if self.max_messages is not None:
            size = min(size, max(1, self.max_messages - self.fetched_total))
        if self.max_quota_units is not None:
            size = min(size, (self.max_quota_units - self.quota_units) // per)
            if size <= 0:
                raise _BudgetSpent()
        start = self._pending.index(gid)
        chunk = self._pending[start:start + size]
        options = {'format': 'metadata', 'metadata_headers': list(METADATA_HEADERS)}
        result = dict(self._call('get_messages', chunk, _units=per * len(chunk), **options) or {})
        retryable = (GmailRateLimited, GmailServerError)
        again = [g for g in chunk if isinstance(result.get(g), retryable)]
        attempt = 0
        while again and attempt < MAX_ATTEMPTS - 1:
            errors = [result[g] for g in again]
            if any(isinstance(e, GmailRateLimited) for e in errors):
                self._drain_pace()
                delay = self._rate_delay(attempt, errors)
            else:
                delay = self._server_delay(attempt)
            self.sleep(delay)
            try:
                result.update(self._call('get_messages', again, _units=per * len(again), **options) or {})
            except _BudgetSpent:
                for item in again:
                    result[item] = _UNPAID
                break
            again = [g for g in again if isinstance(result.get(g), retryable)]
            attempt += 1
        values = [result.get(item) for item in chunk]
        if len(chunk) > 1 and all(isinstance(v, GmailServerError) for v in values):
            raise values[0]   # every item 5xx, even after retries: Gmail is down
        for item, value in zip(chunk, values):
            self._pending_set.discard(item)
            if isinstance(value, GmailAuthError):
                raise value
            if isinstance(value, dict):
                self.messages_read += 1
            self._prefetched[item] = value

    # -- planning ------------------------------------------------------------
    def _plan(self, raws):
        parsed_all = []
        for raw in raws:
            self.current_gid = clean(raw.get('id', ''), 64)
            parsed_all.append(parse_gmail_message(raw))
        self.current_gid = ''
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
            self.current_gid = parsed.gmail_id
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

        self.current_gid = ''
        keys = self._resolve_conversations(to_match)
        snapshot = build_snapshot(to_match, conversation_keys=set(keys.values()), rules=self.rules)
        for parsed in to_match:
            self.current_gid = parsed.gmail_id
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
        self.current_gid = ''
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
                for gid in self._take_fetch_failures():
                    self._bump('failed')
                    if gid not in self.failed_ids:
                        self.failed_ids.append(gid)
                self._skipped_now.clear()
                ok = True
                return
            kept = []
            for plan in plans:
                if plan.action == 'store' and self._wants_body(plan):
                    self.current_gid = plan.parsed.gmail_id
                    try:
                        full = self._call('get_message', plan.parsed.gmail_id, format='full')
                    except GmailNotFound:
                        full = None
                    except (GmailAuthError, GmailRateLimited, GmailServerError):
                        raise
                    except GmailError as exc:
                        self._fetch_failed[plan.parsed.gmail_id] = exc
                        continue
                    if isinstance(full, dict):
                        self.bodies_read += 1
                        payload = full.get('payload') or {}
                        plan.body = extract_body_text(payload) or None
                        plan.attachments = attachment_metadata(payload, plan.parsed.gmail_id)
                kept.append(plan)
            self._write_plans(kept, cursor, deleted, label_changes, retry)
            self.current_gid = ''
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
                self.current_gid = plan.parsed.gmail_id
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
                self.current_gid = parsed.gmail_id
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
            self.current_gid = ''
            for gid, sign, label_ids in label_changes:
                self._label_change(gid, sign, label_ids)
            self.current_gid = ''
            # Messages Gmail refused on their own: failures, retried later; the
            # cursor moves on with this page.
            for gid, exc in self._take_fetch_failures().items():
                self._record_failure(gid, exc)
            if self._skipped_now:
                CaptureSkip.objects.filter(
                    mailbox=self.mailbox, gmail_id__in=self._skipped_now, used_at__isnull=True,
                ).update(used_at=now)
                for gid in self._skipped_now:
                    self.skips.pop(gid, None)
                self._skipped_now.clear()
            updates = dict(cursor or {})
            if newest is not None:
                current = CaptureMailbox.objects.filter(pk=self.mailbox.pk).values_list(
                    'newest_internal_date', flat=True).first()
                if current is None or newest > current:
                    updates['newest_internal_date'] = newest
            updates['lease_expires_at'] = now + timedelta(seconds=self.lease_seconds)
            CaptureMailbox.objects.filter(pk=self.mailbox.pk).update(**updates)
            self.mailbox.refresh_from_db()

    def _take_fetch_failures(self):
        failed, self._fetch_failed = self._fetch_failed, {}
        return failed

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
        if set(labels) & capture_rules.DROP_ON_LABEL:
            self._bump('purged', drop_copies({copy.pk}, 'gmail_deleted', self.mailbox, self.actor)['messages'])
            return
        if self._copy_action(copy.pk, labels) == 'drop':
            self._bump('purged', drop_copies({copy.pk}, 'label', self.mailbox, self.actor)['messages'])
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

    def _copy_action(self, copy_pk, labels):
        """A stored copy whose labels changed: dropped for the built-in private
        label, or for a confirmed label rule that covered this copy; a copy
        labelled after the rule's preview only waits (counted, logged)."""
        action = capture_rules_copy_action(copy_pk, labels, self.builtin_private_ids, self.drop_map,
                                           self.strip_map)
        if action == 'pending':
            logger.info('mail capture mailbox=%s a stored copy was labelled after its label rule\'s '
                        'preview: it waits for a new preview', self.mailbox.pk)
        return action

    def _apply_labels(self, copy_pk, label_ids):
        if set(label_ids) & capture_rules.DROP_ON_LABEL or self._copy_action(copy_pk, label_ids) == 'drop':
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
        here: direction still needs the SENT label). The signing domain
        (``header.d``) must be exactly one of our domains."""
        flags = set(parsed.flags)
        if result.direction == 'claimed_internal':
            internal = set(conf.internal_domains())
            sender_domain = parsed.from_address.domain if parsed.from_address else ''
            for domain in parsed.dkim_pass_domains:
                if (domain in internal and sender_domain
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
