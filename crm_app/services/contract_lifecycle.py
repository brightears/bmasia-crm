"""Contract lifecycle rule: close the renewed predecessor when its successor goes live.

Rule: when a contract becomes Active and its ``renewed_from`` predecessor belongs
to the same company and is Active or Expired, the predecessor becomes Renewed
(``is_active=False``) in the same transaction, with an AuditLog UPDATE row that
records the real before/after values. (Expired was added with the zone hand-over:
a term that has a successor is Renewed, whatever it was called before; the
corrections command's create_successor has done the same since format v2.)

The predecessor is never touched in any other status (Draft, Sent, Cancelled),
nor when it belongs to another company, and only the direct ``renewed_from``
predecessor is considered. Those cases are reported
through the return value so callers can surface them. There is deliberately no
date-based expiry here: whether a past-end contract is over is a business call.

Zone hand-over: in the same transaction, every zone the successor actively
holds is handed over. The predecessor's active link to that zone is closed with
``end_date`` = the day before the successor starts (never before the link's own
start) and ``is_active`` False. Zones the successor does not hold stay open on
the predecessor and are listed in the audit row as ``zones_not_taken_over`` for
a human to confirm. Zone status is not touched. Links of Expired contracts are
never touched by date: a contract that merely runs out keeps its links.

Callers: ``ContractSerializer.create``/``update`` (REST and MCP writes) and the
``close_renewed_predecessors`` backfill command.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

# Outcomes reported by close_renewed_predecessor().
CLOSED = 'closed'
CLOSABLE = ('Active', 'Expired')
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
    # Zone hand-over (only when outcome is CLOSED): journal rows of the closed
    # predecessor links, and the predecessor's zones the successor does not hold.
    zone_links_closed: tuple = ()
    zones_not_taken_over: tuple = ()

    @property
    def closed(self):
        return self.outcome == CLOSED


def _iso(value):
    return value.isoformat() if value is not None else None


def handover_end_date(link_start, successor_start):
    """The day before the successor starts, never before the link's own start."""
    if successor_start is None:
        end = timezone.now().date()
    else:
        end = successor_start - timedelta(days=1)
    return max(end, link_start) if link_start else end


def hand_over_zone_links(predecessor, successor, *, dry_run=False):
    """Close the predecessor's active links to zones the successor actively holds.

    Must run inside a transaction. Returns ``(rows, zones_not_taken_over)``:
    ``rows`` are journal-ready dicts ``{id, zone_id, before, after,
    other_active_links}`` where before/after hold ``end_date`` and
    ``is_active``, and ``other_active_links`` lists the ids of every other link
    that was active on the zone at that moment (the successor's among them), so
    a revert can tell whether the zone has been linked anywhere new since. With
    ``dry_run`` the rows describe what would be written and nothing is written.
    """
    from crm_app.models import ContractZone

    held = set(ContractZone.objects.filter(contract=successor, is_active=True).values_list('zone_id', flat=True))
    links = list(ContractZone.objects.select_for_update()
                 .filter(contract=predecessor, is_active=True).order_by('pk'))
    rows, kept = [], set()
    for link in links:
        if link.zone_id not in held:
            kept.add(str(link.zone_id))
            continue
        end = handover_end_date(link.start_date, successor.start_date)
        others = sorted(str(pk) for pk in ContractZone.objects.filter(zone_id=link.zone_id, is_active=True)
                        .exclude(pk=link.pk).values_list('pk', flat=True))
        rows.append({
            'id': str(link.pk), 'zone_id': str(link.zone_id),
            'before': {'end_date': _iso(link.end_date), 'is_active': True},
            'after': {'end_date': end.isoformat(), 'is_active': False},
            'other_active_links': others,
        })
        if not dry_run:
            ContractZone.objects.filter(pk=link.pk, is_active=True).update(
                end_date=end, is_active=False, updated_at=timezone.now())
    return tuple(rows), tuple(sorted(kept))


def handed_over_links_state(rows):
    """'after' | 'before' | 'changed' for journalled hand-over rows.

    'after' also requires that no link other than those recorded at hand-over
    time has become active on the zone since: reopening the predecessor's link
    would otherwise give the zone a link it never had together with the new one.
    """
    from crm_app.models import ContractZone

    if not rows:
        return 'after'
    current = {str(l.pk): l for l in ContractZone.objects.filter(pk__in=[r['id'] for r in rows])}
    def matches(row, side):
        link = current.get(row['id'])
        return link is not None and _iso(link.end_date) == row[side]['end_date'] \
            and link.is_active == row[side]['is_active']
    if all(matches(r, 'before') for r in rows):
        return 'before'
    if not all(matches(r, 'after') for r in rows):
        return 'changed'
    for r in rows:
        active = set(str(pk) for pk in ContractZone.objects.filter(zone_id=r['zone_id'], is_active=True)
                     .values_list('pk', flat=True))
        if not active <= set(r.get('other_active_links', [])):
            return 'changed'
    return 'after'


def reopen_handed_over_links(rows):
    """Restore journalled hand-over rows to their before values."""
    from datetime import date
    from crm_app.models import ContractZone

    for r in rows:
        before = r['before']
        ContractZone.objects.filter(pk=r['id']).update(
            end_date=date.fromisoformat(before['end_date']) if before['end_date'] else None,
            is_active=before['is_active'], updated_at=timezone.now())


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
        if predecessor.status not in CLOSABLE:
            return PredecessorClosure(PREDECESSOR_NOT_ACTIVE, **result)
        if dry_run:
            rows, kept = hand_over_zone_links(predecessor, current, dry_run=True)
            return PredecessorClosure(CLOSED, zone_links_closed=rows, zones_not_taken_over=kept, **result)

        before = {'status': predecessor.status, 'is_active': predecessor.is_active}
        # A queryset update, not save(): Contract.save() can mint a document
        # number as a side effect. updated_at is bumped explicitly so guarded
        # (optimistic-concurrency) writers holding the old version are refused.
        Contract.objects.filter(pk=predecessor.pk).update(
            status='Renewed', is_active=False, updated_at=timezone.now(),
        )
        predecessor.refresh_from_db(fields=['status', 'is_active'])
        after = {'status': predecessor.status, 'is_active': predecessor.is_active}
        rows, kept = hand_over_zone_links(predecessor, current)
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
                'zone_links_closed': [{'id': r['id'], 'zone_id': r['zone_id'], 'end_date': r['after']['end_date']}
                                      for r in rows],
                'zones_not_taken_over': list(kept),
                'timestamp': timezone.now().isoformat(),
            },
        )
        return PredecessorClosure(CLOSED, audit_log_id=str(audit.pk), zone_links_closed=rows,
                                  zones_not_taken_over=kept, **result)
