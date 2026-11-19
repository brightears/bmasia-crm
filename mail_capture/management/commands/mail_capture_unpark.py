"""Unpark messages that failed three times, so the next run retries them.

Changes only ``CaptureFailure`` rows (parked off, attempts back to 0); it
reads no mailbox and calls no Gmail API. Output is counts only.
"""
from django.core.management.base import BaseCommand, CommandError

from mail_capture.models import CaptureFailure, CaptureMailbox


class Command(BaseCommand):
    help = 'Unpark failed mail-capture messages so the next run retries them.'

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument('--mailbox', help='Mailbox address')
        target.add_argument('--all', action='store_true', help='Every mailbox')
        parser.add_argument('--dry-run', action='store_true', help='Only count')

    def handle(self, *args, **options):
        rows = CaptureFailure.objects.filter(parked=True)
        if options['mailbox']:
            mailbox = CaptureMailbox.objects.filter(email=options['mailbox'].strip().lower()).first()
            if mailbox is None:
                raise CommandError('no such capture mailbox')
            rows = rows.filter(mailbox=mailbox)
        count = rows.count()
        if options['dry_run']:
            self.stdout.write(f'parked messages: {count} (dry run, nothing changed)')
            return
        rows.update(parked=False, attempts=0)
        self.stdout.write(f'unparked messages: {count}; the next run of each mailbox retries them')
