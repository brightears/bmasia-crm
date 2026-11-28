"""Weekly lead research: find new hotel, retail and QSR openings with Claude.

Proposes leads only (ResearchLead rows with status 'new'); a person approves each
one in the CRM before any company, opportunity or outreach is created.

Off unless LEAD_RESEARCH_ENABLED=true, so deploying the code changes nothing.

    python manage.py research_new_venues                 # default segments/countries
    python manage.py research_new_venues --dry-run       # print leads, save nothing
    python manage.py research_new_venues --segments hotel --countries Thailand --max-leads 5
"""

import os

from django.core.management.base import BaseCommand

from crm_app.services.lead_research_service import (
    DEFAULT_COUNTRIES,
    DEFAULT_SEGMENTS,
    LeadResearchService,
)


def _enabled():
    return os.environ.get('LEAD_RESEARCH_ENABLED', '').strip().lower() in ('1', 'true', 'yes')


class Command(BaseCommand):
    help = 'Find new venue openings and expansions with Claude and queue them as leads for review'

    def add_arguments(self, parser):
        parser.add_argument('--segments', nargs='+', default=DEFAULT_SEGMENTS,
                            choices=['hotel', 'retail', 'qsr', 'fnb', 'other'])
        parser.add_argument('--countries', nargs='+', default=DEFAULT_COUNTRIES)
        parser.add_argument('--max-leads', type=int, default=15)
        parser.add_argument('--dry-run', action='store_true', help='Print the leads; save nothing')
        parser.add_argument('--force', action='store_true', help='Run even when LEAD_RESEARCH_ENABLED is off')

    def handle(self, *args, **options):
        if not (_enabled() or options['force'] or options['dry_run']):
            self.stdout.write('LEAD_RESEARCH_ENABLED is off; nothing to do.')
            return

        max_leads = max(1, min(options['max_leads'], 40))
        run = LeadResearchService().run(
            segments=options['segments'],
            countries=options['countries'],
            max_leads=max_leads,
            dry_run=options['dry_run'],
        )
        if run.status == 'failed':
            self.stderr.write(f'Lead research failed: {run.error_message}')
            return

        self.stdout.write(
            f'Lead research {"(dry run) " if options["dry_run"] else ""}completed: '
            f'{run.leads_proposed} proposed, {run.leads_saved} new, '
            f'{run.duplicates_skipped} already known, {run.web_searches} searches, '
            f'{run.input_tokens} input / {run.output_tokens} output tokens.'
        )
        for lead in run.dry_run_leads:
            self.stdout.write(
                f'- [{lead.score}] {lead.venue_name} ({lead.segment}, {lead.city}, {lead.country}): '
                f'{lead.signal} {lead.source_urls[:1]}'
            )
