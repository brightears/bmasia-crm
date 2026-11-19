"""Read enabled capture mailboxes through the Gmail API.

    manage.py gmail_sync --check (--mailbox ADDRESS | --all-mailboxes)
    manage.py gmail_sync --incremental (--mailbox ADDRESS | --all-mailboxes) [--dry-run] [--max-messages N]
    manage.py gmail_sync --backfill --since YYYY-MM-DD --mailbox ADDRESS [--dry-run] [--max-messages N]
    manage.py gmail_sync --skip-once GMAIL_ID --mailbox ADDRESS --by NAME --reason TEXT [--force]
    manage.py gmail_sync --clear-attention --mailbox ADDRESS --by NAME --reason TEXT

A reading form needs ``--mailbox`` (one mailbox) or, deliberately,
``--all-mailboxes``: a run never fans out to every enabled mailbox by
omission. ``--check`` first prints ``enabled mailboxes: ...`` from the table
(no Gmail call), so an operator can see that only the intended mailbox is on.

Every reading form prints "capture disabled" and stops, before any credential
or client is made, while ``GOOGLE_CAPTURE_ENABLED`` is off, while
``CAPTURE_INTERNAL_DOMAINS`` is unsound, or while no mailbox is enabled.
``--check`` calls ``users.getProfile`` per mailbox (1 quota unit) and prints
the address, the message total and the history id; it stores nothing but its
access-log row. Output is counts only otherwise. No cron runs this; each use
on production needs a go-ahead.

``--skip-once`` and ``--clear-attention`` write to the database only (no
Gmail call): who, when and why are recorded, and the mailbox's "needs
attention" flag (and any backoff) is cleared so the next run starts again.
``--skip-once`` skips that message for good. It refuses an id that is neither
named on the mailbox's last failed run nor has a recorded failure, unless
``--force`` is given (recorded on the skip).

Exit codes (the most severe wins when several mailboxes run):

    0  ok: every mailbox ended ok, partial (stopped at --max-messages or the
       budget; continues next run) or resync_needed (the next run resyncs);
       also "capture disabled" while GOOGLE_CAPTURE_ENABLED is off
    1  run error: a run ended error, or the client could not be made
    2  bad arguments: wrong or missing options, or a --mailbox that is
       unknown, not enabled, or on GOOGLE_CAPTURE_NEVER_MAILBOXES
    3  auth error: authentication or permission refused (see the hint)
    4  temporary problem: rate limited, Gmail or the token endpoint
       unavailable, or backing off after one of these (deferred); a later run
       continues
    5  ok with failures: some messages failed or were parked
    6  needs attention: a mailbox stopped after repeated failed runs
    7  busy: another run holds the mailbox
    8  not configured: capture is on but cannot run (CAPTURE_INTERNAL_DOMAINS
       unsound, no mailbox enabled, GOOGLE_CAPTURE_CREDENTIALS_MODE off or
       invalid)
"""
import re
import sys
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from mail_capture import conf
from mail_capture.models import CaptureMailbox, CaptureSkip, MailboxAccessLog


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_RATE_LIMITED = 4
EXIT_OK_WITH_FAILURES = 5
EXIT_NEEDS_ATTENTION = 6
EXIT_BUSY = 7
EXIT_NOT_CONFIGURED = 8

# Most severe first: with several mailboxes the command exits with the first
# of these that any mailbox produced.
SEVERITY = (EXIT_USAGE, EXIT_AUTH, EXIT_NOT_CONFIGURED, EXIT_ERROR, EXIT_NEEDS_ATTENTION,
            EXIT_RATE_LIMITED, EXIT_BUSY, EXIT_OK_WITH_FAILURES, EXIT_OK)

OUTCOME_EXIT = {
    'ok': EXIT_OK,
    'partial': EXIT_OK,
    'resync_needed': EXIT_OK,
    'ok_with_failures': EXIT_OK_WITH_FAILURES,
    'rate_limited': EXIT_RATE_LIMITED,
    'unavailable': EXIT_RATE_LIMITED,
    'deferred': EXIT_RATE_LIMITED,
    'auth_error': EXIT_AUTH,
    'needs_attention': EXIT_NEEDS_ATTENTION,
    'busy': EXIT_BUSY,
    'disabled': EXIT_NOT_CONFIGURED,
    'error': EXIT_ERROR,
}

GMAIL_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

EXIT_HELP = """exit codes: 0 ok (also 'capture disabled' while GOOGLE_CAPTURE_ENABLED is off);
1 run error; 2 bad arguments (including an unknown, disabled or never-listed --mailbox,
or neither --mailbox nor --all-mailboxes); 3 auth error; 4 temporary problem (rate limited,
unavailable, or backing off); 5 ok with failures; 6 needs attention; 7 busy (another run
holds the mailbox); 8 not configured. With several mailboxes the most severe wins."""


def worst(codes):
    codes = set(codes) or {EXIT_OK}
    return next(code for code in SEVERITY if code in codes)


class Command(BaseCommand):
    help = 'Read enabled capture mailboxes through the Gmail API (refuses while capture is off).'

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.epilog = EXIT_HELP
        return parser

    def add_arguments(self, parser):
        what = parser.add_mutually_exclusive_group()
        what.add_argument('--check', action='store_true', help='Profile per mailbox; stores nothing')
        what.add_argument('--incremental', action='store_true', help='Read new history')
        what.add_argument('--backfill', action='store_true', help='Read back to --since')
        what.add_argument('--skip-once', metavar='GMAIL_ID',
                          help='Record a deliberate skip of one message (needs --mailbox, --by, --reason)')
        what.add_argument('--clear-attention', action='store_true',
                          help='Let a mailbox marked "needs attention" run again (needs --mailbox, --by, --reason)')
        parser.add_argument('--mailbox', help='One mailbox address')
        parser.add_argument('--all-mailboxes', action='store_true',
                            help='Every enabled mailbox (must be asked for explicitly)')
        parser.add_argument('--force', action='store_true',
                            help='--skip-once of an id with no recorded failure (recorded on the skip)')
        parser.add_argument('--since', help='Backfill start date, YYYY-MM-DD')
        parser.add_argument('--dry-run', action='store_true', help='Read and count; store nothing')
        parser.add_argument('--max-messages', type=int, help='Stop after this many messages')
        parser.add_argument('--by', help='Who decides (--skip-once, --clear-attention)')
        parser.add_argument('--reason', help='Why (--skip-once, --clear-attention)')

    # -- exits -----------------------------------------------------------------
    def _exit(self, code, message=None, err=False):
        if message:
            (self.stderr if err else self.stdout).write(message)
        if code:
            sys.exit(code)
        return None

    def _usage(self, message):
        return self._exit(EXIT_USAGE, message, err=True)

    # -- main --------------------------------------------------------------------
    def handle(self, *args, **options):
        if options['skip_once'] is not None or options['clear_attention']:
            return self._person_action(options)
        state = conf.capture_state()
        if not state.enabled:
            # Only the master switch being off is a normal, quiet state.
            code = EXIT_OK if state.reason == conf.DISABLED_FLAG else EXIT_NOT_CONFIGURED
            return self._exit(code, f'capture disabled: {state.reason}')
        if not (options['check'] or options['incremental'] or options['backfill']):
            return self._usage('choose one of --check, --incremental or --backfill')
        if options['max_messages'] is not None and options['max_messages'] < 1:
            return self._usage('--max-messages must be 1 or more')
        if options['mailbox'] and options['all_mailboxes']:
            return self._usage('give either --mailbox or --all-mailboxes, not both')
        if not options['mailbox'] and not options['all_mailboxes']:
            return self._usage('name one mailbox with --mailbox (or, deliberately, --all-mailboxes)')
        kind = 'incremental' if options['incremental'] else 'backfill'
        since = None
        if options['backfill']:
            if not options['since']:
                return self._usage('--backfill needs --since YYYY-MM-DD')
            try:
                since = date.fromisoformat(options['since'])
            except ValueError:
                return self._usage('--since must be YYYY-MM-DD')
            if not options['mailbox']:
                return self._usage('--backfill reads one mailbox at a time: add --mailbox')
        mailboxes = self._mailboxes(options['mailbox'])
        from mail_capture import credentials
        current = credentials.mode()
        if current != 'off' and current not in credentials.MODES:
            return self._exit(EXIT_NOT_CONFIGURED,
                              'capture not configured: GOOGLE_CAPTURE_CREDENTIALS_MODE must be off, '
                              'keyless or key_file')
        if current == 'off':
            return self._exit(EXIT_NOT_CONFIGURED,
                              'capture not configured: GOOGLE_CAPTURE_CREDENTIALS_MODE is off')
        if options['check']:
            return self._exit(self._check(mailboxes))
        return self._exit(self._sync(mailboxes, kind, since, options))

    def _mailboxes(self, address):
        from mail_capture.credentials import never_mailboxes
        never = never_mailboxes()
        if address:
            email = address.strip().lower()
            mailbox = CaptureMailbox.objects.filter(email=email).first()
            if mailbox is None:
                self._usage(f'no capture mailbox {email}')
            if not mailbox.enabled:
                self._usage(f'mailbox {email} is not enabled')
            if email in never:
                self._usage(f'mailbox {email} is on GOOGLE_CAPTURE_NEVER_MAILBOXES')
            return [mailbox]
        mailboxes = []
        for mailbox in CaptureMailbox.objects.filter(enabled=True).order_by('email'):
            if mailbox.email in never:
                self.stdout.write(f'{mailbox.email}: skipped (on GOOGLE_CAPTURE_NEVER_MAILBOXES)')
                continue
            mailboxes.append(mailbox)
        if not mailboxes:
            self._exit(EXIT_NOT_CONFIGURED, f'capture disabled: {conf.DISABLED_NO_MAILBOX}')
        return mailboxes

    def _sync(self, mailboxes, kind, since, options):
        from mail_capture import google_client
        from mail_capture.sync import sync_mailbox
        codes = []
        for mailbox in mailboxes:
            try:
                result = sync_mailbox(
                    mailbox.pk, google_client.client_for, kind=kind, since=since,
                    dry_run=options['dry_run'], max_messages=options['max_messages'],
                    actor='job:gmail_sync',
                )
            except Exception as exc:
                self.stdout.write(f'{mailbox.email}: error ({type(exc).__name__})')
                codes.append(EXIT_ERROR)
                continue
            counts = ' '.join(f'{k}={v}' for k, v in sorted(result.counts.items()) if v)
            line = f'{mailbox.email}: {result.outcome} {counts}'.rstrip()
            if result.outcome not in ('ok',) and result.reason:
                line += f' ({result.reason})'
            self.stdout.write(line)
            codes.append(OUTCOME_EXIT.get(result.outcome, EXIT_ERROR))
        return worst(codes)

    def _check(self, mailboxes):
        from mail_capture import google_client
        from mail_capture.credentials import CredentialsMisconfigured, CredentialsRefused
        from mail_capture.gmail_client import GmailAuthError, GmailRateLimited, GmailServerError
        from mail_capture.sync import is_credential_error
        codes = []
        enabled = list(CaptureMailbox.objects.filter(enabled=True).order_by('email').values_list('email', flat=True))
        self.stdout.write(f"enabled mailboxes: {', '.join(enabled) or 'none'}")
        for mailbox in mailboxes:
            log = MailboxAccessLog.objects.create(
                mailbox=mailbox, at=timezone.now(), purpose='check', actor='job:gmail_sync --check')
            try:
                client = google_client.client_for(mailbox)
                profile = client.get_profile()
            except Exception as exc:
                MailboxAccessLog.objects.filter(pk=log.pk).update(finished_at=timezone.now())
                if isinstance(exc, GmailAuthError) and exc.transient:
                    self.stdout.write(f'{mailbox.email}: unavailable {exc.code}: {exc.hint}')
                    codes.append(EXIT_RATE_LIMITED)
                elif isinstance(exc, GmailAuthError):
                    self.stdout.write(f'{mailbox.email}: auth_error {exc.code}: {exc.hint}')
                    CaptureMailbox.objects.filter(pk=mailbox.pk).update(
                        auth_problem=f'auth {exc.code}: {exc.hint}'[:200])
                    codes.append(EXIT_AUTH)
                elif isinstance(exc, CredentialsMisconfigured) or is_credential_error(exc):
                    detail = str(exc) if isinstance(exc, CredentialsMisconfigured) else type(exc).__name__
                    self.stdout.write(f'{mailbox.email}: auth_error credentials: {detail}')
                    codes.append(EXIT_AUTH)
                elif isinstance(exc, CredentialsRefused):
                    self.stdout.write(f'{mailbox.email}: not configured: {exc}')
                    codes.append(EXIT_NOT_CONFIGURED)
                elif isinstance(exc, (GmailRateLimited, GmailServerError)):
                    self.stdout.write(f'{mailbox.email}: unavailable (gmail {exc.status})')
                    codes.append(EXIT_RATE_LIMITED)
                else:
                    self.stdout.write(f'{mailbox.email}: error ({type(exc).__name__})')
                    codes.append(EXIT_ERROR)
                continue
            MailboxAccessLog.objects.filter(pk=log.pk).update(finished_at=timezone.now(), api_calls=1)
            self.stdout.write(f"{mailbox.email}: messages {profile.get('messagesTotal')}, "
                              f"history id {profile.get('historyId')}")
            # A token was made and accepted: a recorded auth problem is over.
            CaptureMailbox.objects.filter(pk=mailbox.pk).exclude(auth_problem='').update(auth_problem='')
            fresh = CaptureMailbox.objects.get(pk=mailbox.pk)
            if fresh.needs_attention:
                self.stdout.write(f'{mailbox.email}: needs attention: {fresh.attention_reason} '
                                  '(gmail_sync --skip-once or --clear-attention)')
                codes.append(EXIT_NEEDS_ATTENTION)
            elif fresh.last_error:
                self.stdout.write(f'{mailbox.email}: last error: {fresh.last_error} '
                                  f'({fresh.consecutive_errors} in a row)')
            if fresh.retry_not_before and fresh.retry_not_before > timezone.now():
                self.stdout.write(f'{mailbox.email}: runs back off until '
                                  f'{fresh.retry_not_before:%Y-%m-%d %H:%M:%S} UTC')
            codes.append(EXIT_OK)
        return worst(codes)

    # -- a person's decisions ------------------------------------------------------
    def _person_action(self, options):
        if not options['mailbox']:
            return self._usage('--skip-once and --clear-attention need --mailbox')
        who = (options['by'] or '').strip()
        why = (options['reason'] or '').strip()
        if not who or not why:
            return self._usage('say who decides and why: --by NAME --reason TEXT')
        email = options['mailbox'].strip().lower()
        mailbox = CaptureMailbox.objects.filter(email=email).first()
        if mailbox is None:
            return self._usage(f'no capture mailbox {email}')
        from mail_capture.sync import clear_attention
        actor = f'person:{who}'[:80]
        if options['clear_attention']:
            clear_attention(mailbox, actor, why)
            return self._exit(EXIT_OK, f'{email}: needs attention cleared; the next run starts again')
        gmail_id = options['skip_once'].strip()
        if not GMAIL_ID.match(gmail_id):
            return self._usage('--skip-once takes a Gmail message id (letters, digits, - and _)')
        from mail_capture.models import CaptureFailure, CaptureRun
        last_failed = (CaptureRun.objects.filter(mailbox=mailbox).exclude(error_gmail_id='')
                       .order_by('-started_at').values_list('error_gmail_id', flat=True).first())
        known = gmail_id == last_failed or CaptureFailure.objects.filter(mailbox=mailbox, gmail_id=gmail_id).exists()
        if not known and not options['force']:
            named = f' (the last failed run names {last_failed})' if last_failed else ''
            return self._usage(f'gmail id {gmail_id} has no recorded failure on {email}{named}: nothing was '
                               'skipped. A skip drops the message for good; add --force to skip it anyway.')
        CaptureSkip.objects.create(mailbox=mailbox, gmail_id=gmail_id, actor=actor, reason=why[:200],
                                   forced=not known)
        clear_attention(mailbox, actor, f'skip once {gmail_id}{" (forced)" if not known else ""}: {why}')
        return self._exit(EXIT_OK, f'{email}: gmail id {gmail_id} will be skipped for good on the next run'
                                   f'{" (forced)" if not known else ""}; needs attention cleared')
