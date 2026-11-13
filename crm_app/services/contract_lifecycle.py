"""Contract lifecycle rule: close the renewed predecessor when its successor goes live.

Rule: when a contract becomes Active and its ``renewed_from`` predecessor belongs
to the same company and is still Active, the predecessor becomes Renewed
(``is_active=False``) in the same transaction, with an AuditLog UPDATE row that
records the real before/after values.

The predecessor is never touched in any other status (Draft, Sent, Expired,
Cancelled), nor when it belongs to another company. Those cases are reported
through the return value so callers can surface them. There is deliberately no
date-based expiry here: whether a past-end contract is over is a business call.

Callers: ``ContractSerializer.create``/``update`` (REST and MCP writes) and the
``close_renewed_predecessors`` backfill command.
"""
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

# Outcomes reported by close_renewed_predecessor().
CLOSED = 'closed'
ALREADY_RENEWED = 'already_renewed'
NO_PREDECESSOR = 'no_predecessor'
SUCCESSOR_NOT_ACTIVE = 'successor_not_active'
DIFFERENT_COMPANY = 'different_company'
PREDECESSOR_NOT_ACTIVE = 'predecessor_not_active'


@dataclass(frozen=True)
class PredecessorClosure:
    outcome: str
    successor_id: str
    predecessor_id: Optional[str] = None
    predecessor_number: Optional[str] = None
    predecessor_status: Optional[str] = None
    audit_log_id: Optional[str] = None

    @property
    def closed(self):
        return self.outcome == CLOSED


def close_renewed_predecessor(successor, *, user=None, source, dry_run=False):
    """Apply the rule for one successor contract. Idempotent.

    ``successor`` may be a Contract or its primary key. Both rows are re-read
    under ``select_for_update`` so the decision uses committed state, not a
    caller's in-memory copy. With ``dry_run`` nothing is written; the outcome
    says what would happen.
    """
    from crm_app.models import AuditLog, Contract

    successor_id = getattr(successor, 'pk', successor)
    with transaction.atomic():
        # No select_related: PostgreSQL refuses FOR UPDATE on the nullable side
        # of an outer join, and renewed_from is nullable.
        current = Contract.objects.select_for_update().get(pk=successor_id)
        result = dict(successor_id=str(current.pk))
        if current.status != 'Active':
            return PredecessorClosure(SUCCESSOR_NOT_ACTIVE, **result)
        if not current.renewed_from_id:
            return PredecessorClosure(NO_PREDECESSOR, **result)

        predecessor = Contract.objects.select_for_update().get(pk=current.renewed_from_id)
        result.update(
            predecessor_id=str(predecessor.pk),
            predecessor_number=predecessor.contract_number,
            predecessor_status=predecessor.status,
        )
        if predecessor.company_id != current.company_id:
            return PredecessorClosure(DIFFERENT_COMPANY, **result)
        if predecessor.status == 'Renewed':
            return PredecessorClosure(ALREADY_RENEWED, **result)
        if predecessor.status != 'Active':
            return PredecessorClosure(PREDECESSOR_NOT_ACTIVE, **result)
        if dry_run:
            return PredecessorClosure(CLOSED, **result)

        before = {'status': predecessor.status, 'is_active': predecessor.is_active}
        # A queryset update, not save(): Contract.save() can mint a document
        # number as a side effect. updated_at is bumped explicitly so guarded
        # (optimistic-concurrency) writers holding the old version are refused.
        Contract.objects.filter(pk=predecessor.pk).update(
            status='Renewed', is_active=False, updated_at=timezone.now(),
        )
        predecessor.refresh_from_db(fields=['status', 'is_active'])
        after = {'status': predecessor.status, 'is_active': predecessor.is_active}
        audit = AuditLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action='UPDATE',
            model_name='Contract',
            record_id=str(predecessor.pk),
            changes={
                key: {'old': before[key], 'new': after[key]}
                for key in before if before[key] != after[key]
            },
            additional_data={
                'action': 'Predecessor closed: renewal successor became Active',
                'rule': 'renewed_predecessor_closed_on_successor_active',
                'source': source,
                'successor_id': str(current.pk),
                'successor_contract_number': current.contract_number,
                'timestamp': timezone.now().isoformat(),
            },
        )
        return PredecessorClosure(CLOSED, audit_log_id=str(audit.pk), **result)
