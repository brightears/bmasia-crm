"""Read enabled capture mailboxes through the Gmail API.

    manage.py gmail_sync --check [--mailbox ADDRESS]
    manage.py gmail_sync --incremental [--mailbox ADDRESS] [--dry-run] [--max-messages N]
    manage.py gmail_sync --backfill --since YYYY-MM-DD --mailbox ADDRESS [--dry-run] [--max-messages N]

Every form prints "capture disabled" and stops, before any credential or
client is made, while ``GOOGLE_CAPTURE_ENABLED`` is off, while
``CAPTURE_INTERNAL_DOMAINS`` is unsound, or while no mailbox is enabled.
``--check`` calls ``users.getProfile`` per mailbox (1 quota unit) and prints
the address, the message total and the history id; it stores nothing but its
access-log row. Output is counts only otherwise. No cron runs this; each use
on production needs a go-ahead.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mail_capture import conf
from mail_capture.models import CaptureMailbox, MailboxAccessLog


class Command(BaseCommand):
    help = 'Read enabled capture mailboxes through the Gmail API (refuses while capture is off).'

    def add_arguments(self, parser):
        what = parser.add_mutually_exclusive_group()
        what.add_argument('--check', action='store_true', help='Profile per mailbox; stores nothing')
        what.add_argument('--incremental', action='store_true', help='Read new history')
        what.add_argument('--backfill', action='store_true', help='Read back to --since')
        parser.add_argument('--mailbox', help='One mailbox address (default: every enabled mailbox)')
        parser.add_argument('--since', help='Backfill start date, YYYY-MM-DD')
        parser.add_argument('--dry-run', action='store_true', help='Read and count; store nothing')
        parser.add_argument('--max-messages', type=int, help='Stop after this many messages')

    def handle(self, *args, **options):
        state = conf.capture_state()
        if not state.enabled:
            self.stdout.write(f'capture disabled: {state.reason}')
            return
        mailboxes = CaptureMailbox.objects.filter(enabled=True).order_by('email')
        if options['mailbox']:
            mailboxes = mailboxes.filter(email=options['mailbox'].strip().lower())
        mailboxes = list(mailboxes)
        if not mailboxes:
            self.stdout.write(f'capture disabled: {conf.DISABLED_NO_MAILBOX}')
            return
        if options['check']:
            return self._check(mailboxes)
        if not (options['incremental'] or options['backfill']):
            self.stdout.write('choose one of --check, --incremental or --backfill')
            return
        kind = 'incremental' if options['incremental'] else 'backfill'
        since = None
        if kind == 'backfill':
            if not options['since']:
                raise CommandError('--backfill needs --since YYYY-MM-DD')
            try:
                since = date.fromisoformat(options['since'])
            except ValueError:
                raise CommandError('--since must be YYYY-MM-DD') from None
            if not options['mailbox']:
                raise CommandError('--backfill reads one mailbox at a time: add --mailbox')
        from mail_capture import google_client
        from mail_capture.sync import sync_mailbox
        for mailbox in mailboxes:
            try:
                result = sync_mailbox(
                    mailbox.pk, google_client.client_for, kind=kind, since=since,
                    dry_run=options['dry_run'], max_messages=options['max_messages'],
                    actor='job:gmail_sync',
                )
            except Exception as exc:
                self.stdout.write(f'{mailbox.email}: error ({type(exc).__name__})')
                continue
            counts = ' '.join(f'{k}={v}' for k, v in sorted(result.counts.items()) if v)
            self.stdout.write(f'{mailbox.email}: {result.outcome} {counts}'.rstrip())

    def _check(self, mailboxes):
        from mail_capture import google_client
        for mailbox in mailboxes:
            log = MailboxAccessLog.objects.create(
                mailbox=mailbox, at=timezone.now(), purpose='check', actor='job:gmail_sync --check')
            try:
                client = google_client.client_for(mailbox)
                profile = client.get_profile()
            except Exception as exc:
                MailboxAccessLog.objects.filter(pk=log.pk).update(finished_at=timezone.now())
                self.stdout.write(f'{mailbox.email}: error ({type(exc).__name__})')
                continue
            MailboxAccessLog.objects.filter(pk=log.pk).update(finished_at=timezone.now(), api_calls=1)
            self.stdout.write(f"{mailbox.email}: messages {profile.get('messagesTotal')}, "
                              f"history id {profile.get('historyId')}")
