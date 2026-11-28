"""Find customers who left and (optionally) have Claude draft win-back emails.

Never sends: drafts wait in the CRM's Win-back page until a person approves them.

    python manage.py winback_scan                       # list + create candidates, last 183 days
    python manage.py winback_scan --product beatbreeze --draft --limit 10
    python manage.py winback_scan --dry-run
"""
from django.core.management.base import BaseCommand

from crm_app.models import WinBackCandidate
from crm_app.services import winback_service


class Command(BaseCommand):
    help = 'Find churned customers and optionally draft win-back emails with Claude (never sends).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=winback_service.DEFAULT_WINDOW_DAYS)
        parser.add_argument('--product', default='all', choices=['all', 'beatbreeze', 'soundtrack', 'other'])
        parser.add_argument('--draft', action='store_true', help='Draft emails for new candidates')
        parser.add_argument('--offer', default='', help='Offer text (default WINBACK_DEFAULT_OFFER)')
        parser.add_argument('--limit', type=int, default=20, help='Max drafts per run')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        if opts['dry_run']:
            rows = winback_service.find_churned(window_days=opts['days'], product=opts['product'])
            for row in rows:
                self.stdout.write(f"{row['churned_on']}  {row['product']:<10}  {row['signal']:<16}  "
                                  f"{row['company'].name}")
            self.stdout.write(self.style.SUCCESS(f'{len(rows)} churned customers (dry run, nothing saved)'))
            return

        result = winback_service.scan(window_days=opts['days'], product=opts['product'])
        self.stdout.write(f"New candidates: {len(result['created'])}, already listed: {result['already_listed']}")
        if not opts['draft']:
            return
        queue = WinBackCandidate.objects.filter(status='identified').order_by('-churned_on')
        if opts['product'] != 'all':
            queue = queue.filter(product=opts['product'])
        drafted = 0
        for candidate in queue[:opts['limit']]:
            try:
                winback_service.draft_email(candidate, offer=opts['offer'] or None)
                drafted += 1
            except winback_service.WinBackError as exc:
                self.stderr.write(f'{candidate.company.name}: {exc}')
        self.stdout.write(self.style.SUCCESS(f'Drafted {drafted}; review them on the Win-back page.'))
