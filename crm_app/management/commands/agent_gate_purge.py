"""Retention for the agent-gate ledger (AgentRequest).

    python manage.py agent_gate_purge                  # dry-run: count rows older than 180 days
    python manage.py agent_gate_purge --days 180 --execute

Rows hold no customer values (field names, ids, digests, reason codes only);
180 days keeps two full renewal cycles of evidence for policy review.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from crm_app.models import AgentRequest

MIN_DAYS = 30


class Command(BaseCommand):
    help = 'Delete AgentRequest rows older than --days (dry-run unless --execute).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180)
        parser.add_argument('--execute', action='store_true')

    def handle(self, *args, **options):
        days = options['days']
        if days < MIN_DAYS:
            raise CommandError(f'--days must be at least {MIN_DAYS}')
        cutoff = timezone.now() - timedelta(days=days)
        old = AgentRequest.objects.filter(created_at__lt=cutoff)
        count = old.count()
        if not options['execute']:
            self.stdout.write(f'[DRY-RUN] {count} AgentRequest rows older than {days} days (before {cutoff:%Y-%m-%d}).')
            return
        deleted, _ = old.delete()
        self.stdout.write(f'Deleted {deleted} AgentRequest rows older than {days} days.')
