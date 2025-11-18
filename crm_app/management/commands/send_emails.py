"""
Management command to send automated emails
Can be run via cron job or task scheduler
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from crm_app.services.email_service import email_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send automated emails (renewal reminders, payment reminders, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'renewal', 'payment', 'quarterly', 'zone-alerts', 'sequences'],
            default='all',
            help='Type of emails to send'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending emails'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force send even outside business hours'
        )

    def handle(self, *args, **options):
        email_type = options['type']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(f"Starting email send process at {timezone.now()}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No emails will be sent"))
        
        # Check business hours unless forced
        if not force and not email_service.is_business_hours():
            self.stdout.write(self.style.WARNING(
                "Outside business hours. Use --force to send anyway."
            ))
            return
        
        total_results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Send renewal reminders
        if email_type in ['all', 'renewal']:
            self.stdout.write("Sending renewal reminders...")
            if not dry_run:
                results = email_service.send_renewal_reminders()
                self._update_results(total_results, results)
                self.stdout.write(
                    f"Renewal reminders: {results['sent']} sent, "
                    f"{results['failed']} failed"
                )
        
        # Send payment reminders
        if email_type in ['all', 'payment']:
            self.stdout.write("Sending payment reminders...")
            if not dry_run:
                results = email_service.send_payment_reminders()
                self._update_results(total_results, results)
                self.stdout.write(
                    f"Payment reminders: {results['sent']} sent, "
                    f"{results['failed']} failed"
                )
        
        # Send quarterly check-ins
        if email_type in ['all', 'quarterly']:
            self.stdout.write("Sending quarterly check-ins...")
            if not dry_run:
                results = email_service.send_quarterly_checkins()
                self._update_results(total_results, results)
                self.stdout.write(
                    f"Quarterly check-ins: {results['sent']} sent, "
                    f"{results['failed']} failed"
                )

        # Process email sequences
        if email_type in ['all', 'sequences']:
            self.stdout.write("Processing email sequences...")
            if not dry_run:
                results = email_service.process_sequence_steps(max_emails=100)
                self._update_results(total_results, results)
                self.stdout.write(
                    f"Sequence processing: {results['sent']} sent, "
                    f"{results['failed']} failed, "
                    f"{results['skipped']} skipped"
                )
            else:
                try:
                    from crm_app.models import SequenceStepExecution

                    pending_count = SequenceStepExecution.objects.filter(
                        status='scheduled',
                        scheduled_for__lte=timezone.now()
                    ).count()

                    self.stdout.write(f"Would process {pending_count} pending sequence steps")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f"Could not query sequence steps (table may not exist yet): {e}"
                    ))

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\nEmail send complete: {total_results['sent']} sent, "
            f"{total_results['failed']} failed, "
            f"{total_results['skipped']} skipped"
        ))
    
    def _update_results(self, total, new):
        """Update total results with new results"""
        for key in ['sent', 'failed', 'skipped']:
            total[key] += new.get(key, 0)