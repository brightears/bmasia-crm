"""Summarise the Phase 1 agent-gate observe ledger (read-only).

    python manage.py agent_gate_report                 # last 7 days, text
    python manage.py agent_gate_report --days 14 --json

Prints counts per principal/decision, the policy reasons behind would-deny
verdicts, protocol gaps, and unlisted usernames that wrote through MCP (e.g. to
identify the BMAsia Sales agent's CRM user). Contains no customer values.
"""
import json
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm_app.models import AgentRequest


class Command(BaseCommand):
    help = 'Summarise agent-gate observe data (no customer values).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=max(1, options['days']))
        rows = AgentRequest.objects.filter(created_at__gte=since).values(
            'principal', 'username', 'tool', 'verb', 'collection', 'decision', 'reasons', 'protocol_gaps',
        )
        by_decision, reasons, gaps, writes, unlisted = Counter(), Counter(), Counter(), Counter(), Counter()
        total = 0
        for row in rows.iterator():
            total += 1
            who = row['principal'] or f"user:{row['username'] or '-'}"
            by_decision[(who, row['decision'])] += 1
            writes[(who, row['verb'], row['collection'])] += 1
            for reason in row['reasons'] or []:
                reasons[(who, reason)] += 1
            for gap in row['protocol_gaps'] or []:
                gaps[(who, gap)] += 1
            if row['decision'] == 'not_agent':
                unlisted[row['username']] += 1
        report = {
            'since': since.isoformat(),
            'total': total,
            'by_decision': [{'who': w, 'decision': d, 'n': n} for (w, d), n in sorted(by_decision.items())],
            'writes': [{'who': w, 'verb': v, 'collection': c, 'n': n}
                       for (w, v, c), n in writes.most_common(50)],
            'would_deny_reasons': [{'who': w, 'reason': r, 'n': n} for (w, r), n in reasons.most_common(50)],
            'protocol_gaps': [{'who': w, 'gap': g, 'n': n} for (w, g), n in gaps.most_common()],
            'unlisted_mcp_writers': [{'username': u, 'n': n} for u, n in unlisted.most_common()],
        }
        if options['json']:
            self.stdout.write(json.dumps(report, indent=1))
            return
        self.stdout.write(f"agent gate observe report since {report['since']} — {total} write attempts")
        for section in ('by_decision', 'writes', 'would_deny_reasons', 'protocol_gaps', 'unlisted_mcp_writers'):
            self.stdout.write(f'\n[{section}]')
            for item in report[section]:
                self.stdout.write('  ' + '  '.join(f'{k}={v}' for k, v in item.items()))
