"""Print the data-quality check counts (read-only).

    python manage.py data_quality_report            # a table, most severe first
    python manage.py data_quality_report --json     # the same as JSON, for a nightly job
    python manage.py data_quality_report --rows 3   # also list the first rows of each check

Reads only; writes nothing, sends nothing. The checks and their definitions live in
crm_app/data_quality.py.
"""
import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from crm_app import data_quality as dq


class Command(BaseCommand):
    help = 'Print the data-quality check counts (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='Print JSON instead of a table.')
        parser.add_argument('--rows', type=int, default=0, help='Also show the first N rows of each check.')
        parser.add_argument('--today', help='Evaluate as of this Bangkok date (YYYY-MM-DD) instead of today.')

    def handle(self, *args, **options):
        today = None
        if options['today']:
            try:
                today = date.fromisoformat(options['today'])
            except ValueError:
                raise CommandError('--today must be YYYY-MM-DD')
        if options['rows'] < 0:
            raise CommandError('--rows must be 0 or more')
        ctx = dq.Context(today=today)
        checks = dq.summary(ctx, rows_per_check=options['rows'])
        if options['json']:
            payload = {'today': ctx.today.isoformat(), 'total': sum(c['count'] for c in checks), 'checks': [
                {k: c[k] for k in ('key', 'title', 'severity', 'record_type', 'count')}
                | ({'rows': c['rows']} if options['rows'] else {})
                for c in checks]}
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
            return
        width = max(len(c['key']) for c in checks)
        self.stdout.write(f'Data quality as of {dq.fmt_date(ctx.today)} (Bangkok)')
        self.stdout.write(f'{"check".ljust(width)}  {"severity":8}  {"count":>6}  title')
        for c in checks:
            self.stdout.write(f'{c["key"].ljust(width)}  {c["severity"]:8}  {c["count"]:>6}  {c["title"]}')
            for r in c['rows']:
                self.stdout.write(f'{"":{width}}    - {r["label"]} | {r["company_name"] or ""} | {r["fact"]}')
        self.stdout.write(f'{"total".ljust(width)}  {"":8}  {sum(c["count"] for c in checks):>6}')
