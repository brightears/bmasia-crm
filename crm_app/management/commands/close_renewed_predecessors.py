"""Close Active contracts whose renewal successor is already Active.

Applies the lifecycle rule in crm_app/services/contract_lifecycle.py to existing
data: for every Active contract that has a successor (a contract with
renewed_from = it, on the same company) in status Active, the predecessor
becomes Renewed (is_active=False) with an AuditLog UPDATE row.

SAFETY MODEL:
  * Dry-run by DEFAULT. Nothing is written unless --execute is passed.
  * It only ever moves Active -> Renewed, and only when an Active successor on
    the same company exists. It never touches any other status, value, date or
    record, and creates or deletes nothing except the audit rows.
  * There is NO date-based expiry. Two informational counts (Active contracts
    past end_date with a Sent/Draft successor, and with no successor) are
    printed and never changed: whether those terms are over is a business
    decision (see the "false Expired" history in reconcile_false_expiry.py).
  * Idempotent: a second run finds nothing to do.
  * Output names contracts by ID and contract number only.

Usage:
    python manage.py close_renewed_predecessors            # dry-run
    python manage.py close_renewed_predecessors --execute
"""
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from crm_app.models import Contract
from crm_app.services.contract_lifecycle import close_renewed_predecessor

SOURCE = 'close_renewed_predecessors'


class Command(BaseCommand):
    help = ("Set Active contracts to Renewed when their same-company renewal is Active "
            "(dry-run by default; --execute to write).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute', action='store_true',
            help='Apply the changes. Without this flag the command only reports what it would do.',
        )

    def handle(self, *args, **opts):
        execute = opts['execute']
        mode = 'EXECUTE' if execute else 'DRY-RUN'
        self.stdout.write(f'close_renewed_predecessors [{mode}]')

        # One filter() call, so both conditions apply to the same successor row.
        predecessors = (
            Contract.objects
            .filter(status='Active', renewals__status='Active', renewals__company_id=F('company_id'))
            .distinct()
            .order_by('contract_number', 'id')
        )

        counts = {}
        handled_ids = set()
        for predecessor in predecessors:
            successor = (
                Contract.objects
                .filter(renewed_from=predecessor, company_id=predecessor.company_id, status='Active')
                .order_by('start_date', 'created_at', 'id')
                .first()
            )
            if successor is None:  # changed since the listing query
                counts['changed_concurrently'] = counts.get('changed_concurrently', 0) + 1
                continue
            result = close_renewed_predecessor(successor, source=SOURCE, dry_run=not execute)
            counts[result.outcome] = counts.get(result.outcome, 0) + 1
            pair = (f'{predecessor.contract_number} ({predecessor.pk}); '
                    f'successor {successor.contract_number} ({successor.pk})')
            if result.closed:
                handled_ids.add(predecessor.pk)
                label = 'CLOSED' if execute else 'WOULD-CLOSE'
                self.stdout.write(f'  [{label}] Active -> Renewed: {pair}')
            else:
                self.stdout.write(f'  [SKIPPED:{result.outcome}] {pair}')

        closed = counts.get('closed', 0)
        self.stdout.write(
            f'\nsummary [{mode}]: {"closed" if execute else "would_close"}={closed} '
            + ' '.join(f'{key}={value}' for key, value in sorted(counts.items()) if key != 'closed')
        )

        # Informational only. Nothing below is ever changed by this command.
        today = timezone.localdate()
        past_end = (
            Contract.objects.filter(status='Active', end_date__lt=today)
            .exclude(pk__in=handled_ids)
        )
        with_pending_successor = (
            past_end.filter(renewals__status__in=['Sent', 'Draft'], renewals__company_id=F('company_id'))
            .distinct().count()
        )
        without_successor = past_end.filter(renewals__isnull=True).count()
        self.stdout.write('informational (not changed; no date-based expiry is applied):')
        self.stdout.write(f'  active_past_end_with_sent_or_draft_successor={with_pending_successor}')
        self.stdout.write(f'  active_past_end_without_successor={without_successor}')
        if not execute and closed:
            self.stdout.write('re-run with --execute to apply.')
