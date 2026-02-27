"""
Management command to check for prospect replies via IMAP.
Detects replies to prospect sequence emails, classifies them,
and triggers auto-actions (pause enrollment, create tasks, etc.).

Usage:
    python manage.py check_prospect_replies
    python manage.py check_prospect_replies --dry-run
    python manage.py check_prospect_replies --lookback 48
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check IMAP inbox for prospect replies and classify them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Detect and classify replies without taking actions',
        )
        parser.add_argument(
            '--lookback',
            type=int,
            default=24,
            help='Hours to look back for emails (default: 24)',
        )

    def handle(self, *args, **options):
        from crm_app.services.reply_detection_service import ReplyDetectionService

        dry_run = options['dry_run']
        lookback = options['lookback']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no actions will be taken"))

        service = ReplyDetectionService()

        if not service.is_configured:
            self.stdout.write(self.style.ERROR(
                "Reply detection not configured. Set PROSPECT_REPLY_EMAIL and "
                "PROSPECT_REPLY_IMAP_PASSWORD environment variables."
            ))
            return

        self.stdout.write(f"Checking IMAP inbox ({service.reply_email}) for replies...")

        stats = service.check_for_replies(dry_run=dry_run, lookback_hours=lookback)

        self.stdout.write(self.style.SUCCESS(
            f"Done: {stats['detected']} detected, {stats['matched']} matched, "
            f"{stats['classified']} classified, {stats['actions_taken']} actions taken"
        ))
