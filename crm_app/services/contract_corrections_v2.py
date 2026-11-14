"""Contract-corrections file format v2: cancellations, status-only closures,
renewed_from links and created successor terms.

Used by the ``apply_contract_corrections`` management command when the file's
``format`` is ``contract-corrections/v2`` (and by ``--revert`` for a v2
journal). Format v1 (classes A/B/C) is handled by the command module itself
and is unchanged.

OPERATIONS (one per entry, ``op``)

  mark_cancelled     Active/Sent/Draft -> Cancelled, is_active False.
                     Written with Contract.save(), the same path a REST status
                     change takes, so the Contract post_save handler
                     ``handle_contract_termination`` runs. That handler closes
                     every active ContractZone link of the contract (end_date
                     the earlier of today and the contract's end_date, never
                     before the link's start; is_active False) and sets each
                     linked Zone's status
                     to 'cancelled' (Zone.save(update_fields=['status'])). It
                     sends nothing and calls no external service. The command
                     predicts that set before writing, refuses if a zone is
                     also actively linked to a contract that stays live, checks
                     the handler did exactly that, and journals every link and
                     zone so --revert can restore them.
  mark_renewed       Active -> Renewed, is_active False, status only, for a
                     contract whose later term already exists and is Active on
                     the same company (``successor_id``). Same write as the
                     lifecycle rule (queryset update, no save side effects).
  set_renewed_from   Sets the missing ``renewed_from`` link of an existing
                     contract to an earlier contract of the same company
                     (``renewed_from_id``, whose state the entry states in
                     ``renewed_from_expected``). No status change; queryset
                     update.
  create_successor   Creates the current term as a NEW Active contract renewing
                     ``old_contract_id``, then closes the old contract as
                     Renewed: through the lifecycle rule close_renewed_predecessor
                     when it is Active, or with the same write when it is
                     Expired. See CREATE below.
  hand_over_zone_links
                     Link-only repair, no contract field changes. For a Renewed
                     contract (``contract_id``) and its Active renewal
                     (``successor_id``: renewed_from = contract_id, same
                     company), closes the contract's active links to every zone
                     the renewal actively holds, exactly as the lifecycle rule
                     does when a renewal goes Active (end_date = the day before
                     the renewal starts, never before the link's start). With
                     ``copy_missing_links: true`` the contract's other active
                     zones are first linked to the renewal (start_date = the
                     renewal's start), so every zone moves over; refused when
                     such a zone is actively linked to another live contract
                     (zone_shared_with_live_contract). Zones not moved stay open
                     and are reported. Zone status is not touched.
  redate_zone_link_end
                     Link-only repair for a Cancelled contract: every closed
                     link whose end_date equals ``closed_on`` and lies after the
                     contract's end_date gets end_date = the contract's end_date
                     (never before the link's start). Nothing else changes.

GROUPS
  Entries sharing a ``group`` are applied together or not at all, in one
  transaction, after every check of every entry passed. Contracts are locked
  with select_for_update in primary-key order, including every contract an
  entry only refers to (successor_id, renewed_from_id), whose expected state is
  re-checked under the lock. Across the whole file:
    * a contract may be changed by at most one entry (duplicate_contract_id);
    * a contract that one group changes or relies on may not appear in any
      other group (contract_in_two_groups);
    * the new terms planned by create_successor entries may not overlap each
      other for the same company, or a company and a twin listed by either
      entry, whether in one group or in two (planned_terms_overlap).
  The journal entry of a group is written inside the group's transaction,
  before commit, so a crash cannot leave applied changes without revert data.
  When COMMIT itself raises a database error, the server may still have
  committed: the entry is kept, flagged commit_uncertain, and the group is
  reported as COMMIT-UNCERTAIN for an operator to check. Revert is safe either
  way: it checks current state and writes nothing for a group that is not
  there.

REFUSALS (named reasons; nothing in the group is written)
  duplicate_contract_id, contract_in_two_groups, planned_terms_overlap,
  predecessor_changed, journal_write_failed, missing_contract,
  status_changed, dates_changed, updated_at_changed,
  transition_not_allowed, partially_applied,
  zone_shared_with_live_contract, unexpected_side_effect,
  missing_successor, successor_changed, successor_other_company,
  successor_not_active, successor_not_later, successor_renews_other_contract,
  renewed_from_conflict, different_companies, predecessor_not_earlier,
  predecessor_renewed_by_other, predecessor_left_active,
  currency_mismatch, billing_entity_unresolved, new_term_not_later,
  open_renewal_exists, active_renewal_exists, overlapping_contract,
  missing_twin_company, service_location_pricing_mismatch,
  (new_term_not_later: the new term starts before the old one; the same start
  is allowed, for a placeholder whose real term is a longer one),
  number_reservation_failed, rule_did_not_close_old_term(<outcome>),
  no_end_date (redate_zone_link_end on a contract without an end date),
  renewal_has_ended_link_to_zone (hand_over_zone_links with copy_missing_links:
  the renewal already has an ended link to the zone starting on its start date,
  so a new link cannot be stored; a human decides which link is right).

CREATE (create_successor)
  The new contract takes:
    from the old contract: company, billing_entity (blank stays blank, so it
      keeps inheriting the company's issuer), currency (the file must state the
      same currency), tax_rate (tax_amount and total_value are computed as the
      serializer does), contract_type, contract_category, master_contract,
      property_name, soundtrack_account_id, renewal_period_months,
      send_renewal_reminders, show_zone_pricing_detail;
    from the file: start_date, end_date, value, signed_date, billing_frequency
      and auto_renew (null = the old contract's), service_type (null = the old
      contract's), price_per_zone, notes, and the service-location rows;
    fixed: status Active, is_active True, renewed_from = old contract,
      lifecycle_type 'renewal' (lifecycle_type_manually_set True, as the Rene
      renewal clone does), a final HK-CT/TH-CT number from the collision-safe
      reservation helper (never Contract.save()'s unchecked minting).
  Zone links: every zone the old contract actively covers gets a new
  ContractZone link on the new contract (start_date = the new term's start,
  is_active True), as ContractViewSet.duplicate_for_renewal does. The old
  contract's links to those zones are then handed over: closed with end_date =
  the day before the new term starts (never before the link's start), by the
  lifecycle rule for an Active old contract and by the same helper for an
  Expired one, and journalled. A zone that is also linked to another live
  contract is not a refusal here (the zone stays covered by the new term).
  Never copied: contacts, signatories, custom terms, template selections and
  their custom text, payment terms/schedule, discount, quote, opportunity,
  line items, service items.
  Refused when another contract of the company, or of a listed twin company,
  overlaps the new term (Cancelled contracts and the old contract itself
  excepted), when the old contract has a Draft/Sent (or Active) renewal, when
  the old contract changed since the file was made, or when the rows'
  per-zone prices contradict the value (the PDF pricing guard).
  Re-run: an old contract that is Renewed with an Active renewal holding the
  file's dates is reported as already applied.

REVERT
  Per group, only when every contract (and every zone link) still holds the
  journal's after values; otherwise the group is skipped.
    mark_cancelled   restores status, is_active, the zone links' end_date and
                     is_active, and each zone status that is still 'cancelled'
                     (a zone whose status moved since, e.g. by the Soundtrack
                     sync, is left as it is and reported). A released zone that
                     has since been linked to any other contract makes the group
                     changed_since_apply: reactivating the old link would give
                     the zone two active links. Links of other contracts that
                     were already active on the zone before the run (stale
                     links of an already-Cancelled contract) are recorded in
                     the journal and do not block the revert.
    mark_renewed / set_renewed_from   restore the journalled fields.
    hand_over_zone_links   reopens the closed links and deletes the links it
                     created, only while every one of them still holds the
                     journal's after values and no other link has become active
                     on those zones; otherwise changed_since_apply.
    redate_zone_link_end   restores the journalled end dates while the links
                     still hold the after values.
    create_successor DELETES the created contract (and its service-location
                     rows) and restores the old contract, but only while the
                     created contract is untouched: same updated_at, same
                     service-location rows, the copied zone links unchanged
                     and no other row of any kind pointing at it (invoices,
                     documents, other zone links, renewals, tasks, emails,
                     ...). Deleting it removes the copied links with it; the
                     old contract's handed-over links are reopened (journals
                     written before the hand-over existed have none). If one of
                     those links changed since, or its zone gained a new active
                     link, the group is changed_since_apply. For a journal
                     written before the hand-over existed, the group is
                     zone_links_handed_over_since_apply when a later repair
                     (hand_over_zone_links) closed the old term's links to the
                     copied zones: revert that repair journal first. A touched contract is never deleted
                     and never auto-cancelled: the group is skipped as
                     created_contract_touched for a human to decide. The final
                     number is not handed back (a gap in the sequence).
"""
import re
import uuid
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from crm_app.models import (
    AuditLog, Company, Contract, ContractServiceLocation, ContractZone, Zone,
)
from crm_app.services.contract_lifecycle import (
    CLOSED, close_renewed_predecessor, hand_over_zone_links, handed_over_links_state,
    handover_end_date, reopen_handed_over_links,
)

FILE_FORMAT_V2 = 'contract-corrections/v2'
JOURNAL_FORMAT_V2 = 'contract-corrections-journal/v2'
OPS = ('mark_cancelled', 'mark_renewed', 'set_renewed_from', 'create_successor',
       'hand_over_zone_links', 'redate_zone_link_end')
LINK_OPS = ('hand_over_zone_links', 'redate_zone_link_end')
CANCELLABLE = {'Draft', 'Sent', 'Active'}
CREATE_FROM = {'Active', 'Expired'}
STATUSES = {value for value, _ in Contract.CONTRACT_STATUS_CHOICES}
SERVICE_TYPES = {value for value, _ in Contract.SERVICE_TYPE_CHOICES}
PLATFORMS = {value for value, _ in ContractServiceLocation.PLATFORM_CHOICES}

_TOP_KEYS = {'format', 'source_pulled_at', 'entries'}
_COMMON = {'op', 'class', 'group', 'evidence'}
_OP_KEYS = {
    'mark_cancelled': ({'contract_id', 'expected'}, set()),
    'mark_renewed': ({'contract_id', 'expected', 'successor_id', 'successor_expected'}, set()),
    'set_renewed_from': ({'contract_id', 'expected', 'renewed_from_id', 'renewed_from_expected'}, set()),
    'create_successor': ({'old_contract_id', 'old_expected', 'new'}, {'twin_company_ids'}),
    'hand_over_zone_links': ({'contract_id', 'expected', 'successor_id', 'successor_expected'},
                             {'copy_missing_links'}),
    'redate_zone_link_end': ({'contract_id', 'expected', 'closed_on'}, set()),
}
_EXPECTED_KEYS = {'status', 'start_date', 'end_date', 'updated_at'}
_NEW_REQUIRED = {'status', 'start_date', 'end_date', 'value', 'currency', 'service_locations', 'notes'}
_NEW_OPTIONAL = {'signed_date', 'billing_frequency', 'auto_renew', 'service_type', 'price_per_zone'}
_LOC_REQUIRED = {'location_name', 'platform'}
_LOC_OPTIONAL = {'custom_service_name', 'price'}
_GROUP_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9:._-]{0,79}')
_CLASS_RE = re.compile(r'[A-Z][A-Za-z0-9]{0,7}')
_EVIDENCE_MAX = 300
_NOTES_MAX = 1000
_MAX_LOCATIONS = 200

# Fields journalled for an existing contract.
CONTRACT_FIELDS = ('status', 'is_active', 'renewed_from')


class Refused(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Expected:
    status: str
    start: date
    end: Optional[date]
    updated_at: datetime


@dataclass
class NewTerm:
    status: str
    start: date
    end: date
    value: Decimal
    currency: str
    notes: str
    locations: list
    signed_date: Optional[date] = None
    billing_frequency: Optional[str] = None
    auto_renew: Optional[bool] = None
    service_type: Optional[str] = None
    price_per_zone: Optional[Decimal] = None


@dataclass
class EntryV2:
    index: int
    op: str
    cls: str
    group: str
    evidence: str
    contract_id: str                     # the contract this entry changes
    expected: Expected
    successor_id: Optional[str] = None
    successor_expected: Optional[Expected] = None
    renewed_from_id: Optional[str] = None
    renewed_from_expected: Optional[Expected] = None
    twin_company_ids: list = field(default_factory=list)
    new: Optional[NewTerm] = None
    copy_missing_links: bool = False
    closed_on: Optional[date] = None

    @property
    def referenced_ids(self):
        return [i for i in (self.successor_id, self.renewed_from_id) if i]


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _malformed(message):
    return CommandError(f'malformed corrections file: {message}')


def _uuid(value, where):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise _malformed(f'{where}: not a UUID')


def _date(value, where, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise _malformed(f'{where}: want YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _malformed(f'{where}: want YYYY-MM-DD')


def _instant(value, where):
    if not isinstance(value, str):
        raise _malformed(f'{where}: want an ISO 8601 timestamp with offset')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise _malformed(f'{where}: want an ISO 8601 timestamp with offset')
    if parsed.tzinfo is None:
        raise _malformed(f'{where}: timestamp has no UTC offset')
    return parsed


def _money(value, where, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise _malformed(f'{where}: want a decimal string such as "1200.00"')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise _malformed(f'{where}: want a decimal string such as "1200.00"')
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2 or amount >= Decimal('1e10'):
        raise _malformed(f'{where}: want a non-negative amount with at most 2 decimals')
    return amount


def _text(value, where, maximum, single_line=True, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()) or len(value) > maximum:
        raise _malformed(f'{where}: want a string of {0 if allow_empty else 1}-{maximum} characters')
    bad = [ch for ch in value if ord(ch) < 32 and (single_line or ch not in '\n')]
    if bad:
        raise _malformed(f'{where}: control characters are not allowed')
    return value


def _expected(raw, where):
    if not isinstance(raw, dict) or set(raw) != _EXPECTED_KEYS:
        raise _malformed(f'{where}: must have exactly {sorted(_EXPECTED_KEYS)}')
    if raw['status'] not in STATUSES:
        raise _malformed(f'{where}.status {raw["status"]!r} is not a contract status')
    return Expected(
        status=raw['status'],
        start=_date(raw['start_date'], f'{where}.start_date'),
        end=_date(raw['end_date'], f'{where}.end_date', nullable=True),
        updated_at=_instant(raw['updated_at'], f'{where}.updated_at'),
    )


def _keys(raw, required, optional, where):
    if not isinstance(raw, dict):
        raise _malformed(f'{where}: must be an object')
    missing = required - set(raw)
    unknown = set(raw) - required - optional
    if missing:
        raise _malformed(f'{where}: missing keys {sorted(missing)}')
    if unknown:
        raise _malformed(f'{where}: unknown keys {sorted(unknown)}')


def _new_term(raw, where):
    _keys(raw, _NEW_REQUIRED, _NEW_OPTIONAL, where)
    if raw['status'] != 'Active':
        raise _malformed(f'{where}.status: a created successor must be Active')
    start = _date(raw['start_date'], f'{where}.start_date')
    end = _date(raw['end_date'], f'{where}.end_date')
    if end < start:
        raise _malformed(f'{where}: end_date is before start_date')
    if raw['currency'] not in {c for c, _ in Contract.CURRENCY_CHOICES}:
        raise _malformed(f'{where}.currency: not a contract currency')
    service_type = raw.get('service_type')
    if service_type is not None and service_type != '' and service_type not in SERVICE_TYPES:
        raise _malformed(f'{where}.service_type: not a service type')
    billing_frequency = raw.get('billing_frequency')
    if billing_frequency is not None:
        billing_frequency = _text(billing_frequency, f'{where}.billing_frequency', 20)
    auto_renew = raw.get('auto_renew')
    if auto_renew is not None and not isinstance(auto_renew, bool):
        raise _malformed(f'{where}.auto_renew: want true, false or null')
    rows = raw['service_locations']
    if not isinstance(rows, list) or not rows or len(rows) > _MAX_LOCATIONS:
        raise _malformed(f'{where}.service_locations: want 1-{_MAX_LOCATIONS} rows')
    locations = []
    for n, row in enumerate(rows):
        rwhere = f'{where}.service_locations[{n}]'
        _keys(row, _LOC_REQUIRED, _LOC_OPTIONAL, rwhere)
        if row['platform'] not in PLATFORMS:
            raise _malformed(f'{rwhere}.platform: want one of {sorted(PLATFORMS)}')
        custom = row.get('custom_service_name') or ''
        if custom:
            _text(custom, f'{rwhere}.custom_service_name', 200)
        if row['platform'] == 'custom' and not custom:
            raise _malformed(f'{rwhere}: a custom platform row needs custom_service_name')
        locations.append({
            'location_name': _text(row['location_name'], f'{rwhere}.location_name', 200),
            'platform': row['platform'],
            'custom_service_name': custom,
            'price': _money(row.get('price'), f'{rwhere}.price', nullable=True),
            'sort_order': n,
        })
    return NewTerm(
        status='Active', start=start, end=end,
        value=_money(raw['value'], f'{where}.value'),
        currency=raw['currency'],
        notes=_text(raw['notes'], f'{where}.notes', _NOTES_MAX, single_line=False),
        locations=locations,
        signed_date=_date(raw.get('signed_date'), f'{where}.signed_date', nullable=True),
        billing_frequency=billing_frequency,
        auto_renew=auto_renew,
        service_type=service_type,
        price_per_zone=_money(raw.get('price_per_zone'), f'{where}.price_per_zone', nullable=True),
    )


def parse_v2(data):
    """Validate a decoded v2 file. Returns (entries, duplicate_contract_ids)."""
    if not isinstance(data, dict):
        raise _malformed('top level must be a JSON object')
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise _malformed(f'unknown top-level keys {sorted(unknown)}')
    if data.get('format') != FILE_FORMAT_V2:
        raise _malformed(f'format must be {FILE_FORMAT_V2!r}')
    raw_entries = data.get('entries')
    if not isinstance(raw_entries, list) or not raw_entries:
        raise _malformed('entries must be a non-empty list')

    entries = []
    for index, raw in enumerate(raw_entries):
        where = f'entry {index}'
        if not isinstance(raw, dict):
            raise _malformed(f'{where}: must be an object')
        op = raw.get('op')
        if op not in OPS:
            raise _malformed(f'{where}: op must be one of {list(OPS)}')
        required, optional = _OP_KEYS[op]
        _keys(raw, _COMMON | required, optional, where)
        if not isinstance(raw['class'], str) or not _CLASS_RE.fullmatch(raw['class']):
            raise _malformed(f'{where}: class must match {_CLASS_RE.pattern}')
        if not isinstance(raw['group'], str) or not _GROUP_RE.fullmatch(raw['group']):
            raise _malformed(f'{where}: group must match {_GROUP_RE.pattern}')
        evidence = _text(raw['evidence'], f'{where} evidence', _EVIDENCE_MAX)
        common = dict(index=index, op=op, cls=raw['class'], group=raw['group'], evidence=evidence)
        if op == 'create_successor':
            contract_id = _uuid(raw['old_contract_id'], f'{where} old_contract_id')
            twins = raw.get('twin_company_ids', [])
            if not isinstance(twins, list):
                raise _malformed(f'{where} twin_company_ids: want a list of UUIDs')
            entry = EntryV2(
                **common, contract_id=contract_id,
                expected=_expected(raw['old_expected'], f'{where} old_expected'),
                twin_company_ids=sorted({_uuid(t, f'{where} twin_company_ids') for t in twins}),
                new=_new_term(raw['new'], f'{where} new'),
            )
            if entry.new.start < entry.expected.start:
                raise _malformed(f'{where}: the new term must not start before the old term starts')
        else:
            contract_id = _uuid(raw['contract_id'], f'{where} contract_id')
            entry = EntryV2(**common, contract_id=contract_id,
                            expected=_expected(raw['expected'], f'{where} expected'))
            if op in ('mark_renewed', 'hand_over_zone_links'):
                entry.successor_id = _uuid(raw['successor_id'], f'{where} successor_id')
                entry.successor_expected = _expected(raw['successor_expected'], f'{where} successor_expected')
                copy = raw.get('copy_missing_links', False)
                if not isinstance(copy, bool):
                    raise _malformed(f'{where} copy_missing_links: want true or false')
                entry.copy_missing_links = copy
            elif op == 'redate_zone_link_end':
                entry.closed_on = _date(raw['closed_on'], f'{where} closed_on')
            elif op == 'set_renewed_from':
                entry.renewed_from_id = _uuid(raw['renewed_from_id'], f'{where} renewed_from_id')
                entry.renewed_from_expected = _expected(raw['renewed_from_expected'], f'{where} renewed_from_expected')
            if contract_id in entry.referenced_ids:
                raise _malformed(f'{where}: a contract cannot reference itself')
        entries.append(entry)

    for group, members in group_entries(entries).items():
        if len({e.cls for e in members}) != 1:
            raise _malformed(f'group {group}: mixes classes {sorted({e.cls for e in members})}')

    return entries, file_conflicts(entries)


def file_conflicts(entries):
    """{group: reason} for groups refused because of another entry in the file."""
    refused = {}
    changed = Counter(e.contract_id for e in entries)
    for e in entries:
        if changed[e.contract_id] > 1:
            refused[e.group] = 'duplicate_contract_id'
    seen = {}
    for e in entries:
        for cid in (e.contract_id, *e.referenced_ids):
            seen.setdefault(cid, set()).add(e.group)
    for cid, groups in seen.items():
        if len(groups) > 1:
            for g in groups:
                refused.setdefault(g, 'contract_in_two_groups')
    return refused


def planned_overlaps(creates):
    """Keys whose planned new terms overlap: creates = [(key, company_ids, start, end)]."""
    bad = set()
    for i, (g1, c1, s1, e1) in enumerate(creates):
        for g2, c2, s2, e2 in creates[i + 1:]:
            if c1 & c2 and s1 <= e2 and s2 <= e1:
                bad |= {g1, g2}
    return bad


def group_entries(entries):
    groups = OrderedDict()
    for entry in entries:
        groups.setdefault(entry.group, []).append(entry)
    return groups


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    return value


def contract_state(contract):
    return {
        'status': contract.status,
        'is_active': contract.is_active,
        'renewed_from': _iso(contract.renewed_from_id),
        'updated_at': _iso(contract.updated_at),
    }


def _changes(before, after, fields=CONTRACT_FIELDS):
    return {f: {'old': before[f], 'new': after[f]} for f in fields if before[f] != after[f]}


def _check_expected(contract, exp, in_target):
    """Return 'expected' or 'target', or raise Refused."""
    dates_ok = contract.start_date == exp.start and contract.end_date == exp.end
    if contract.status == exp.status and dates_ok and contract.updated_at == exp.updated_at:
        return 'expected'
    if dates_ok and in_target(contract):
        return 'target'
    if contract.status != exp.status:
        raise Refused('status_changed')
    if not dates_ok:
        raise Refused('dates_changed')
    raise Refused('updated_at_changed')


def _overlapping(company_ids, start, end, exclude_ids):
    from django.db.models import Q
    return (
        Contract.objects.filter(company_id__in=company_ids, start_date__lte=end)
        .filter(Q(end_date__gte=start) | Q(end_date__isnull=True))
        .exclude(status='Cancelled')
        .exclude(pk__in=exclude_ids)
    )


def _tax(value, tax_rate):
    tax_amount = (value * tax_rate / Decimal('100')).quantize(Decimal('0.01'))
    return tax_amount, value + tax_amount


def _matching_successor(old, new):
    return (Contract.objects.filter(
        renewed_from_id=old.pk, company_id=old.company_id, status='Active',
        start_date=new.start, end_date=new.end,
    ).order_by('created_at', 'id').first())


def _inbound_rows(contract, own_links=()):
    """Names of relations, other than service locations and the zone links this
    command created (``own_links``), that point at the contract."""
    found = []
    for rel in Contract._meta.related_objects:
        if rel.related_model is ContractServiceLocation:
            continue
        if rel.related_model is ContractZone:
            if ContractZone.objects.filter(contract=contract).exclude(pk__in=list(own_links)).exists():
                found.append(rel.get_accessor_name())
            continue
        accessor = rel.get_accessor_name()
        if rel.one_to_one:
            if rel.related_model.objects.filter(**{rel.field.name: contract}).exists():
                found.append(accessor)
        elif getattr(contract, accessor).exists():
            found.append(accessor)
    for m2m in Contract._meta.many_to_many:
        if m2m.name == 'zones':  # through ContractZone, checked above
            continue
        if getattr(contract, m2m.name).exists():
            found.append(m2m.name)
    return sorted(set(found))


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

class V2Runner:
    """Runs a v2 file or a v2 journal on behalf of the management command."""

    def __init__(self, command):
        self.cmd = command
        self.out = command.stdout

    # ---- apply -------------------------------------------------------------

    def apply(self, data, file_sha256, opts, write_journal):
        entries, conflicts = parse_v2(data)
        self.file_sha256 = file_sha256
        self.write_journal = write_journal
        cmd = self.cmd
        groups = group_entries(entries)
        selected = set(opts.get('only_class') or []) or {e.cls for e in entries}
        creates = [e for e in entries if e.op == 'create_successor']
        old_company = {str(pk): str(co) for pk, co in Contract.objects.filter(
            pk__in=[e.contract_id for e in creates]).values_list('pk', 'company_id')}
        for g in planned_overlaps([
                (e.group, {old_company.get(e.contract_id, e.contract_id), *e.twin_company_ids}, e.new.start, e.new.end)
                for e in creates]):
            conflicts.setdefault(g, 'planned_terms_overlap')

        self.journal = {
            'format': JOURNAL_FORMAT_V2, 'command': cmd.COMMAND_NAME, 'batch_id': cmd.batch_id,
            'file_format': FILE_FORMAT_V2, 'file_sha256': file_sha256,
            'started_at': timezone.now().isoformat(),
            'actor': cmd.actor.username if cmd.actor else None, 'groups': [],
        }
        if cmd.execute_mode:
            write_journal(self.journal)

        self.out.write(
            f'{cmd.COMMAND_NAME} [{cmd.mode}] batch {cmd.batch_id}: {len(entries)} entries in '
            f'{len(groups)} groups ({FILE_FORMAT_V2}); classes {"/".join(sorted(selected))}')

        tally = OrderedDict()
        uncertain = set()
        not_selected = 0
        for group, members in groups.items():
            cls = members[0].cls
            if cls not in selected:
                not_selected += len(members)
                continue
            outcome, rows = self._apply_group(group, members, conflicts.get(group))
            for entry, number, detail in rows:
                label = {'would_apply': 'WOULD-APPLY', 'applied': 'APPLIED',
                         'already_applied': 'ALREADY-APPLIED'}.get(outcome, f'SKIPPED:{outcome}')
                if outcome.startswith('commit_uncertain'):
                    label = f'COMMIT-UNCERTAIN:{outcome}'
                    uncertain.add(group)
                self.out.write(
                    f'  [{label}] {cls} {entry.op} {entry.contract_id} {number or "-"}'
                    f'{": " + detail if detail else ""}')
                key = (outcome if outcome in ('would_apply', 'applied', 'already_applied')
                       else 'commit_uncertain' if outcome.startswith('commit_uncertain') else f'skipped:{outcome}')
                tally.setdefault(f'{cls}/{entry.op}', Counter())[key] += 1

        self.out.write(f'\nsummary [{cmd.mode}] batch {cmd.batch_id}')
        for key, counter in tally.items():
            self.out.write(f'  {key}: ' + ' '.join(f'{k}={v}' for k, v in sorted(counter.items())))
        total = sum(tally.values(), Counter())
        self.out.write('  total: ' + (' '.join(f'{k}={v}' for k, v in sorted(total.items())) or 'nothing'))
        if not_selected:
            self.out.write(f'  not selected by --only-class: {not_selected} entries')
        if cmd.execute_mode:
            self.out.write(f'journal: {cmd.journal_path}')
        if uncertain:
            self.out.write(
                f'WARNING: {len(uncertain)} group(s) hit an error at COMMIT and may or may not have been written: '
                f'{", ".join(sorted(uncertain))}. Check those contracts on the CRM; the journal keeps their '
                f'entries (commit_uncertain) and --revert reverts them only where the change is present.')
        elif total.get('would_apply'):
            self.out.write('re-run with --execute --journal <path> to apply.')

    def _apply_group(self, group, members, conflict):
        numbers = {}

        def rows(details=None):
            details = details or {}
            return [(e, numbers.get(e.contract_id), details.get(e.index, '')) for e in members]

        ids = sorted({e.contract_id for e in members} | {i for e in members for i in e.referenced_ids})
        numbers.update({str(pk): n for pk, n in Contract.objects.filter(pk__in=ids).values_list('pk', 'contract_number')})
        if conflict:
            return conflict, rows()
        for e in members:
            if e.op == 'mark_cancelled' and e.expected.status not in CANCELLABLE:
                return 'transition_not_allowed', rows()
            if e.op == 'mark_renewed' and e.expected.status != 'Active':
                return 'transition_not_allowed', rows()
            if e.op == 'create_successor' and e.expected.status not in CREATE_FROM:
                return 'transition_not_allowed', rows()
            if e.op == 'hand_over_zone_links' and e.expected.status != 'Renewed':
                return 'transition_not_allowed', rows()
            if e.op == 'redate_zone_link_end' and e.expected.status != 'Cancelled':
                return 'transition_not_allowed', rows()
        try:
            with transaction.atomic():
                locked = {str(c.pk): c for c in
                          Contract.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
                if any(e.contract_id not in locked for e in members):
                    raise Refused('missing_contract')
                plans = self._check_group(members, locked)
                if all(p['state'] == 'target' for p in plans.values()):
                    return 'already_applied', rows()
                if any(p['state'] == 'target' for p in plans.values()):
                    raise Refused('partially_applied')
                details = {i: p['detail'] for i, p in plans.items()}
                if not self.cmd.execute_mode:
                    return 'would_apply', rows(details)
                journal_ops = []
                for e in members:
                    journal_ops.append(self._write(group, e, locked, plans[e.index]))
                for e in members:
                    if e.op == 'create_successor':
                        created = journal_ops[members.index(e)]['created']
                        details[e.index] = f'created {created["contract_id"]} {created["contract_number"]}; ' + details[e.index]
                # Journal before commit: a crash after this point leaves either
                # nothing applied (revert then finds the before state) or the
                # changes together with their revert data.
                self.journal['groups'].append({'group': group, 'class': members[0].cls, 'ops': journal_ops})
                try:
                    self.write_journal(self.journal)
                except OSError:
                    self.journal['groups'].pop()
                    raise Refused('journal_write_failed')
        except Refused as refused:
            return refused.reason, rows()
        except DatabaseError as exc:
            if self.journal['groups'] and self.journal['groups'][-1]['group'] == group:
                # The error came at COMMIT: the server may have committed although the
                # client saw an error. Keep the entry, flagged; revert checks current
                # state first, so it writes nothing for a group that did not commit.
                self.journal['groups'][-1]['commit_uncertain'] = True
                self.write_journal(self.journal)
                return f'commit_uncertain({exc.__class__.__name__})', rows(details)
            return f'write_failed({exc.__class__.__name__})', rows()
        return 'applied', rows(details)

    # ---- checks ------------------------------------------------------------

    def _check_group(self, members, locked):
        plans = {}
        for e in members:
            check = getattr(self, f'_check_{e.op}')
            plans[e.index] = check(e, locked[e.contract_id], locked, members)
        # Lifecycle consistency: an Active contract must not end up renewing an
        # Active predecessor that the group leaves Active.
        renewed_in_group = {e.contract_id for e in members if e.op == 'mark_renewed'}
        for e in members:
            if e.op == 'set_renewed_from' and plans[e.index]['state'] == 'expected':
                c, target = locked[e.contract_id], locked[e.renewed_from_id]
                if c.status == 'Active' and target.status == 'Active' and str(target.pk) not in renewed_in_group:
                    raise Refused('predecessor_left_active')
        # Planned new terms of this group must not overlap each other.
        creates = [e for e in members if e.op == 'create_successor' and plans[e.index]['state'] == 'expected']
        if planned_overlaps([(e.index, {str(locked[e.contract_id].company_id), *e.twin_company_ids},
                              e.new.start, e.new.end) for e in creates]):
            raise Refused('planned_terms_overlap')
        # A zone may be released only if no contract that stays live holds it.
        cancelled_in_group = {e.contract_id for e in members if e.op == 'mark_cancelled'}
        for e in members:
            plan = plans[e.index]
            if e.op == 'mark_cancelled' and plan['state'] == 'expected':
                zone_ids = [z for _, z in plan['links']]
                if ContractZone.objects.filter(zone_id__in=zone_ids, is_active=True) \
                        .exclude(contract_id__in=cancelled_in_group).exclude(contract__status='Cancelled').exists():
                    raise Refused('zone_shared_with_live_contract')
        return plans

    def _check_mark_cancelled(self, e, c, locked, members):
        state = _check_expected(c, e.expected, lambda x: x.status == 'Cancelled')
        plan = {'state': state, 'detail': '', 'links': []}
        if state == 'expected':
            links = list(ContractZone.objects.select_for_update().filter(contract=c, is_active=True).order_by('pk'))
            plan['links'] = [(str(l.pk), str(l.zone_id)) for l in links]
            list(Zone.objects.select_for_update().filter(pk__in=[z for _, z in plan['links']]).order_by('pk'))
            plan['detail'] = (f'{c.status} -> Cancelled; is_active {c.is_active} -> False; '
                              f'releases {len(links)} active zone link(s)')
        return plan

    def _check_mark_renewed(self, e, c, locked, members):
        state = _check_expected(c, e.expected, lambda x: x.status == 'Renewed')
        plan = {'state': state, 'detail': ''}
        if state != 'expected':
            return plan
        s = locked.get(e.successor_id)
        if s is None:
            raise Refused('missing_successor')
        try:
            _check_expected(s, e.successor_expected, lambda x: False)
        except Refused:
            raise Refused('successor_changed')
        if s.company_id != c.company_id:
            raise Refused('successor_other_company')
        if s.status != 'Active':
            raise Refused('successor_not_active')
        if not s.start_date > c.start_date:
            raise Refused('successor_not_later')
        linked_in_group = any(m.op == 'set_renewed_from' and m.contract_id == e.successor_id
                              and m.renewed_from_id == e.contract_id for m in members)
        if s.renewed_from_id and str(s.renewed_from_id) != e.contract_id and not linked_in_group:
            raise Refused('successor_renews_other_contract')
        plan['detail'] = (f'Active -> Renewed (status only); later term {s.pk} {s.contract_number}'
                          f'{" linked in this group" if linked_in_group else ""}')
        return plan

    def _check_set_renewed_from(self, e, c, locked, members):
        state = _check_expected(c, e.expected, lambda x: str(x.renewed_from_id) == e.renewed_from_id)
        plan = {'state': state, 'detail': ''}
        if state != 'expected':
            return plan
        target = locked.get(e.renewed_from_id)
        if target is None:
            raise Refused('missing_contract')
        try:
            _check_expected(target, e.renewed_from_expected, lambda x: False)
        except Refused:
            raise Refused('predecessor_changed')
        if c.renewed_from_id is not None:
            raise Refused('renewed_from_conflict')
        if target.company_id != c.company_id:
            raise Refused('different_companies')
        if not target.start_date < c.start_date:
            raise Refused('predecessor_not_earlier')
        if Contract.objects.filter(renewed_from_id=target.pk).exclude(pk=c.pk).exclude(status='Cancelled').exists():
            raise Refused('predecessor_renewed_by_other')
        plan['detail'] = f'renewed_from set to {target.pk} {target.contract_number}; status stays {c.status}'
        return plan

    def _check_create_successor(self, e, c, locked, members):
        new = e.new

        def in_target(x):
            return x.status == 'Renewed' and _matching_successor(x, new) is not None

        state = _check_expected(c, e.expected, in_target)
        plan = {'state': state, 'detail': ''}
        if state != 'expected':
            return plan
        if new.currency != c.currency:
            raise Refused('currency_mismatch')
        from crm_app.services.document_context import document_region
        try:
            document_region(c)
        except ValueError:
            raise Refused('billing_entity_unresolved')
        if new.start < c.start_date:
            raise Refused('new_term_not_later')
        renewals = Contract.objects.select_for_update().filter(renewed_from_id=c.pk).order_by('pk')
        if any(r.status in ('Draft', 'Sent') for r in renewals):
            raise Refused('open_renewal_exists')
        if any(r.status == 'Active' for r in renewals):
            raise Refused('active_renewal_exists')
        if e.twin_company_ids and \
                Company.objects.filter(pk__in=e.twin_company_ids).count() != len(e.twin_company_ids):
            raise Refused('missing_twin_company')
        company_ids = [c.company_id, *e.twin_company_ids]
        if _overlapping(company_ids, new.start, new.end, [c.pk]).exists():
            raise Refused('overlapping_contract')
        if self._pricing_mismatch(new, c):
            raise Refused('service_location_pricing_mismatch')
        links = ContractZone.objects.filter(contract=c, is_active=True).values('zone_id').distinct().count()
        platforms = Counter(loc['platform'] for loc in new.locations)
        closure = 'lifecycle rule' if c.status == 'Active' else 'same write as the lifecycle rule'
        plan['detail'] = (
            f'{c.status} -> Renewed ({closure}); creates Active {new.start.isoformat()}..{new.end.isoformat()} '
            f'with {len(new.locations)} service location(s) '
            f'({", ".join(f"{k} {v}" for k, v in sorted(platforms.items()))})'
            f'{"; copies " + str(links) + " active zone link(s) to the new term" if links else ""}'
            f'{"; hands them over (old links end " + handover_end_date(None, new.start).isoformat() + ")" if links else ""}')
        return plan

    def _check_hand_over_zone_links(self, e, c, locked, members):
        _check_expected(c, e.expected, lambda x: False)
        s = locked.get(e.successor_id)
        if s is None:
            raise Refused('missing_successor')
        try:
            _check_expected(s, e.successor_expected, lambda x: False)
        except Refused:
            raise Refused('successor_changed')
        if s.company_id != c.company_id:
            raise Refused('successor_other_company')
        if str(s.renewed_from_id) != e.contract_id:
            raise Refused('successor_renews_other_contract')
        if s.status != 'Active':
            raise Refused('successor_not_active')
        links = list(ContractZone.objects.select_for_update().filter(contract=c, is_active=True).order_by('pk'))
        held = set(ContractZone.objects.filter(contract=s, is_active=True).values_list('zone_id', flat=True))
        to_close = [l for l in links if l.zone_id in held]
        missing = sorted({l.zone_id for l in links if l.zone_id not in held}, key=str)
        to_copy = missing if e.copy_missing_links else []
        if to_copy and ContractZone.objects.filter(contract=s, zone_id__in=to_copy, start_date=s.start_date).exists():
            # The renewal already has an ended link to such a zone starting on its own start date;
            # a second link with the same start cannot be stored. A human decides which link is right.
            raise Refused('renewal_has_ended_link_to_zone')
        if to_copy and ContractZone.objects.filter(zone_id__in=to_copy, is_active=True) \
                .exclude(contract_id__in=[c.pk, s.pk]).filter(contract__status__in=('Active', 'Sent', 'Draft')).exists():
            raise Refused('zone_shared_with_live_contract')
        plan = {'state': 'expected' if (to_close or to_copy) else 'target', 'detail': ''}
        if plan['state'] == 'expected':
            end = handover_end_date(None, s.start_date).isoformat()
            kept = len(missing) - len(to_copy)
            plan['detail'] = (
                f'renewal {s.pk} {s.contract_number}: '
                f'{"links " + str(len(to_copy)) + " zone(s) to the renewal (start " + s.start_date.isoformat() + "); " if to_copy else ""}'
                f'closes {len(to_close) + len(to_copy)} link(s) of this contract (end {end})'
                f'{"; " + str(kept) + " zone(s) not held by the renewal stay open" if kept else ""}')
        return plan

    def _check_redate_zone_link_end(self, e, c, locked, members):
        _check_expected(c, e.expected, lambda x: False)
        if c.end_date is None:
            raise Refused('no_end_date')
        links = list(ContractZone.objects.select_for_update().filter(
            contract=c, is_active=False, end_date=e.closed_on, end_date__gt=c.end_date).order_by('pk'))
        moves = [(l, max(c.end_date, l.start_date)) for l in links]
        moves = [(l, d) for l, d in moves if d != l.end_date]
        plan = {'state': 'expected' if moves else 'target', 'detail': '', 'moves': moves}
        if moves:
            plan['detail'] = (f'{len(moves)} closed link(s) end {e.closed_on.isoformat()} -> '
                              f'{", ".join(sorted({d.isoformat() for _, d in moves}))}')
        return plan

    @staticmethod
    def _pricing_mismatch(new, old):
        """The PDF guard (service_location_pricing_mismatch) run on the planned contract."""
        from types import SimpleNamespace
        from crm_app.services.contract_service_locations import service_location_pricing_mismatch
        rows = [SimpleNamespace(price=loc['price']) for loc in new.locations]
        planned = SimpleNamespace(
            service_locations=SimpleNamespace(all=lambda: rows),
            show_zone_pricing_detail=old.show_zone_pricing_detail,  # copied from the old contract
            line_items=None,                    # a created successor has no line items
            discount_percentage=Decimal('0'),   # not copied
            price_per_zone=new.price_per_zone,
            value=new.value,
            currency=old.currency,
        )
        return service_location_pricing_mismatch(planned) is not None

    # ---- writes ------------------------------------------------------------

    def _audit(self, action, record_id, changes, group, e, extra=None):
        return AuditLog.objects.create(
            user=self.cmd.actor, action=action, model_name='Contract', record_id=str(record_id),
            changes=changes,
            additional_data={**self._meta(group, e), **(extra or {}), 'timestamp': timezone.now().isoformat()},
        )

    def _meta(self, group, e):
        return {
            'command': self.cmd.COMMAND_NAME, 'batch_id': self.cmd.batch_id, 'group': group,
            'class': e.cls, 'op': e.op, 'evidence': e.evidence, 'file_sha256': self.file_sha256,
            'file_format': FILE_FORMAT_V2,
        }

    def _write(self, group, e, locked, plan):
        return getattr(self, f'_write_{e.op}')(group, e, locked[e.contract_id], locked, plan)

    def _write_mark_cancelled(self, group, e, c, locked, plan):
        before = contract_state(c)
        link_ids = [l for l, _ in plan['links']]
        zone_ids = sorted({z for _, z in plan['links']})
        links_before = {str(l.pk): (l.end_date, l.is_active) for l in ContractZone.objects.filter(pk__in=link_ids)}
        zones_before = {str(z.pk): z.status for z in Zone.objects.filter(pk__in=zone_ids)}
        other_links_before = set(
            ContractZone.objects.filter(zone_id__in=zone_ids).exclude(pk__in=link_ids)
            .values_list('pk', 'is_active', 'end_date'))
        other_by_zone = {}
        for pk, zone_id in ContractZone.objects.filter(zone_id__in=zone_ids).exclude(pk__in=link_ids) \
                .values_list('pk', 'zone_id'):
            other_by_zone.setdefault(str(zone_id), set()).add(str(pk))

        c.status = 'Cancelled'
        c.is_active = False
        # save(): the REST path, so the post_save termination handler runs.
        c.save(update_fields=['status', 'is_active', 'updated_at'])
        c.refresh_from_db()
        after = contract_state(c)

        links_after = {str(l.pk): (l.end_date, l.is_active) for l in ContractZone.objects.filter(pk__in=link_ids)}
        zones_after = {str(z.pk): z.status for z in Zone.objects.filter(pk__in=zone_ids)}
        if any(v[1] for v in links_after.values()) or any(s != 'cancelled' for s in zones_after.values()) \
                or ContractZone.objects.filter(contract=c, is_active=True).exists() \
                or set(ContractZone.objects.filter(zone_id__in=zone_ids).exclude(pk__in=link_ids)
                       .values_list('pk', 'is_active', 'end_date')) != other_links_before:
            raise Refused('unexpected_side_effect')

        zone_rows = [{'id': z, 'before': {'status': zones_before[z]}, 'after': {'status': zones_after[z]},
                      # links of other contracts that were already active on this zone before the
                      # run (e.g. stale links of an already-Cancelled contract); revert ignores them
                      'other_active_links': sorted(str(pk) for pk, active, _ in other_links_before
                                                   if active and str(pk) in other_by_zone.get(z, set()))}
                     for z in zone_ids]
        link_rows = [{'id': l, 'zone_id': dict(plan['links'])[l],
                      'before': {'end_date': _iso(links_before[l][0]), 'is_active': links_before[l][1]},
                      'after': {'end_date': _iso(links_after[l][0]), 'is_active': links_after[l][1]}}
                     for l in link_ids]
        self._audit('UPDATE', c.pk, _changes(before, after), group, e, {
            'action': f'Correction: {before["status"]} -> Cancelled',
            'zone_links_closed': link_ids,
            'zones_marked_cancelled': [z['id'] for z in zone_rows if z['before'] != z['after']],
        })
        return {'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
                'before': before, 'after': after, 'zone_links': link_rows, 'zones': zone_rows}

    def _close_as_renewed(self, c, group, e, action, extra=None):
        before = contract_state(c)
        Contract.objects.filter(pk=c.pk).update(status='Renewed', is_active=False, updated_at=timezone.now())
        c.refresh_from_db()
        after = contract_state(c)
        self._audit('UPDATE', c.pk, _changes(before, after), group, e, {'action': action, **(extra or {})})
        return before, after

    def _write_mark_renewed(self, group, e, c, locked, plan):
        before, after = self._close_as_renewed(
            c, group, e, 'Correction: Active -> Renewed (later term exists)', {'later_term_id': e.successor_id})
        return {'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
                'before': before, 'after': after}

    def _write_set_renewed_from(self, group, e, c, locked, plan):
        before = contract_state(c)
        Contract.objects.filter(pk=c.pk).update(renewed_from_id=e.renewed_from_id, updated_at=timezone.now())
        c.refresh_from_db()
        after = contract_state(c)
        self._audit('UPDATE', c.pk, _changes(before, after), group, e,
                    {'action': 'Correction: renewed_from link set'})
        return {'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
                'before': before, 'after': after}

    def _write_create_successor(self, group, e, old, locked, plan):
        from crm_app.services.rene_phase2 import RenePhase2Error, _reserve_final_contract_number
        new = e.new
        old_before = contract_state(old)
        tax_amount, total_value = _tax(new.value, old.tax_rate)
        contract = Contract(
            company=old.company,
            billing_entity=old.billing_entity,
            currency=old.currency,
            tax_rate=old.tax_rate,
            tax_amount=tax_amount,
            total_value=total_value,
            value=new.value,
            contract_type=old.contract_type,
            contract_category=old.contract_category,
            master_contract_id=old.master_contract_id,
            property_name=old.property_name,
            soundtrack_account_id=old.soundtrack_account_id,
            renewal_period_months=old.renewal_period_months,
            send_renewal_reminders=old.send_renewal_reminders,
            show_zone_pricing_detail=old.show_zone_pricing_detail,
            status='Active',
            is_active=True,
            start_date=new.start,
            end_date=new.end,
            signed_date=new.signed_date,
            billing_frequency=new.billing_frequency if new.billing_frequency is not None else old.billing_frequency,
            auto_renew=new.auto_renew if new.auto_renew is not None else old.auto_renew,
            service_type=new.service_type if new.service_type is not None else old.service_type,
            price_per_zone=new.price_per_zone,
            notes=new.notes,
            renewed_from=old,
            lifecycle_type='renewal',
            lifecycle_type_manually_set=True,
        )
        try:
            contract.contract_number = _reserve_final_contract_number(contract)
        except RenePhase2Error:
            raise Refused('number_reservation_failed')
        contract.save()
        ContractServiceLocation.objects.bulk_create([
            ContractServiceLocation(contract=contract, **loc) for loc in new.locations])
        # Zone links carried over as ContractViewSet.duplicate_for_renewal does; old links untouched.
        zone_ids = sorted({str(z) for z in ContractZone.objects.filter(contract=old, is_active=True)
                           .values_list('zone_id', flat=True)})
        ContractZone.objects.bulk_create([
            ContractZone(contract=contract, zone_id=zone_id, start_date=new.start, is_active=True)
            for zone_id in zone_ids])
        from crm_app.services.contract_service_locations import service_location_pricing_mismatch
        if service_location_pricing_mismatch(contract):
            raise Refused('service_location_pricing_mismatch')

        if old.status == 'Active':
            closure = close_renewed_predecessor(contract, user=self.cmd.actor, source=self.cmd.COMMAND_NAME)
            if not (closure.outcome == CLOSED and closure.predecessor_id == str(old.pk)):
                raise Refused(f'rule_did_not_close_old_term({closure.outcome})')
            handed_over = list(closure.zone_links_closed)
            row = AuditLog.objects.get(pk=closure.audit_log_id)
            row.additional_data = {**(row.additional_data or {}), **self._meta(group, e)}
            row.save(update_fields=['additional_data'])
            old.refresh_from_db()
            old_after = contract_state(old)
        else:
            # The same hand-over the lifecycle rule performs for an Active predecessor.
            rows_closed, kept = hand_over_zone_links(old, contract)
            handed_over = list(rows_closed)
            _, old_after = self._close_as_renewed(
                old, group, e, 'Correction: Expired -> Renewed (current term created)',
                {'successor_id': str(contract.pk), 'successor_contract_number': contract.contract_number,
                 'zone_links_closed': [{'id': r['id'], 'zone_id': r['zone_id'], 'end_date': r['after']['end_date']}
                                       for r in handed_over],
                 'zones_not_taken_over': list(kept)})
        new_zone_ids = list(ContractZone.objects.filter(contract=contract, is_active=True).values_list('zone_id', flat=True))
        if ContractZone.objects.filter(contract=old, is_active=True, zone_id__in=new_zone_ids).exists():
            raise Refused('unexpected_side_effect')  # the old term still holds a zone the new term covers

        contract.refresh_from_db()
        locations = list(contract.service_locations.order_by('sort_order', 'pk'))
        links = list(ContractZone.objects.filter(contract=contract).order_by('pk'))
        self._audit('CREATE', contract.pk, {
            'status': {'old': None, 'new': 'Active'},
            'renewed_from': {'old': None, 'new': str(old.pk)},
            'start_date': {'old': None, 'new': new.start.isoformat()},
            'end_date': {'old': None, 'new': new.end.isoformat()},
            'value': {'old': None, 'new': str(new.value)},
            'service_locations': {'old': 0, 'new': len(locations)},
            'zone_links': {'old': 0, 'new': len(links)},
        }, group, e, {'action': 'Correction: current term created as renewal', 'renews_contract_id': str(old.pk),
                      'zone_links_copied': [str(l.zone_id) for l in links],
                      'old_zone_links_closed': [r['id'] for r in handed_over]})
        return {
            'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
            'before': old_before, 'after': old_after,
            'created': {
                'contract_id': str(contract.pk), 'contract_number': contract.contract_number,
                'renewed_from': str(old.pk), 'status': contract.status,
                'updated_at': _iso(contract.updated_at),
                'service_locations': [{'id': str(l.pk), 'updated_at': _iso(l.updated_at)} for l in locations],
                'zone_links': [{'id': str(l.pk), 'zone_id': str(l.zone_id), 'start_date': _iso(l.start_date)}
                               for l in links],
            },
            'old_zone_links_closed': handed_over,
        }

    def _write_hand_over_zone_links(self, group, e, c, locked, plan):
        s = locked[e.successor_id]
        state = contract_state(c)
        active_before = ContractZone.objects.filter(contract=c, is_active=True).count()
        created = []
        if e.copy_missing_links:
            held = set(ContractZone.objects.filter(contract=s, is_active=True).values_list('zone_id', flat=True))
            zone_ids = sorted({str(z) for z in ContractZone.objects.filter(contract=c, is_active=True)
                               .values_list('zone_id', flat=True) if z not in held})
            for zone_id in zone_ids:
                created.append(ContractZone.objects.create(contract=s, zone_id=zone_id, start_date=s.start_date,
                                                           is_active=True))
        rows_closed, kept = hand_over_zone_links(c, s)
        if not rows_closed:
            raise Refused('unexpected_side_effect')
        created_rows = [{'id': str(l.pk), 'zone_id': str(l.zone_id), 'start_date': _iso(l.start_date)} for l in created]
        self._audit('UPDATE', c.pk, {'zone_links_active': {
            'old': active_before, 'new': ContractZone.objects.filter(contract=c, is_active=True).count()}}, group, e, {
            'action': f'Correction: zone links handed over to renewal {s.contract_number}',
            'successor_id': str(s.pk), 'successor_contract_number': s.contract_number,
            'zone_links_closed': [{'id': r['id'], 'zone_id': r['zone_id'], 'end_date': r['after']['end_date']}
                                  for r in rows_closed],
            'zone_links_created_on_successor': created_rows,
            'zones_not_taken_over': list(kept),
        })
        return {'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
                'successor_id': e.successor_id, 'before': state, 'after': state,
                'zone_links': list(rows_closed), 'links_created': created_rows, 'zones_not_taken_over': list(kept)}

    def _write_redate_zone_link_end(self, group, e, c, locked, plan):
        state = contract_state(c)
        rows = []
        for link, new_end in plan['moves']:
            updated = ContractZone.objects.filter(pk=link.pk, is_active=False, end_date=link.end_date).update(
                end_date=new_end, updated_at=timezone.now())
            if updated != 1:
                raise Refused('unexpected_side_effect')
            rows.append({'id': str(link.pk), 'zone_id': str(link.zone_id),
                         'before': {'end_date': _iso(link.end_date), 'is_active': False},
                         'after': {'end_date': new_end.isoformat(), 'is_active': False}})
        self._audit('UPDATE', c.pk, {}, group, e, {
            'action': 'Correction: closed zone links re-dated to the contract end date',
            'zone_links_redated': [{'id': r['id'], 'zone_id': r['zone_id'], 'old_end_date': r['before']['end_date'],
                                    'new_end_date': r['after']['end_date']} for r in rows],
        })
        return {'op': e.op, 'class': e.cls, 'evidence': e.evidence, 'contract_id': e.contract_id,
                'before': state, 'after': state, 'zone_links': rows}

    # ---- revert ------------------------------------------------------------

    def revert(self, journal, path):
        cmd = self.cmd
        if not isinstance(journal.get('groups'), list):
            raise CommandError(f'{path} is not a {JOURNAL_FORMAT_V2} journal.')
        reverted_batch = journal.get('batch_id')
        self.out.write(f'{cmd.COMMAND_NAME} revert [{cmd.mode}] batch {cmd.batch_id} of applied batch {reverted_batch}')
        tally = Counter()
        for group_row in journal['groups']:
            try:
                group, cls, ops = group_row['group'], group_row['class'], group_row['ops']
                for op in ops:
                    if op['op'] not in OPS:
                        raise KeyError('op')
                    _uuid(op['contract_id'], 'journal contract_id')
                    op['before']['status'], op['after']['updated_at']
            except (KeyError, TypeError, CommandError) as exc:
                raise CommandError(f'{path}: malformed journal group ({exc}).')
            outcome, notes = self._revert_group(group, cls, ops, reverted_batch)
            for op in ops:
                label = {'would_revert': 'WOULD-REVERT', 'reverted': 'REVERTED',
                         'already_reverted': 'ALREADY-REVERTED'}.get(outcome, f'SKIPPED:{outcome}')
                created = op.get('created')
                extra = f'; deletes created {created["contract_id"]} {created["contract_number"]}' if created else ''
                note = notes.get(op['contract_id'], '')
                self.out.write(
                    f'  [{label}] {cls} {op["op"]} {op["contract_id"]}: {op["after"]["status"]} -> '
                    f'{op["before"]["status"]}{extra}{"; " + note if note else ""}')
                key = outcome if outcome in ('would_revert', 'reverted', 'already_reverted') else f'skipped:{outcome}'
                tally[f'{cls}/{op["op"]}:{key}'] += 1
        self.out.write(f'\nsummary revert [{cmd.mode}] batch {cmd.batch_id}')
        self.out.write('  ' + (' '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'nothing'))

    @staticmethod
    def _contract_matches(contract, values):
        current = contract_state(contract)
        for key, value in values.items():
            if key == 'updated_at':
                if contract.updated_at != _instant(value, 'journal updated_at'):
                    return False
            elif current[key] != value:
                return False
        return True

    def _op_state(self, op, locked):
        """'after' | 'before' | 'changed' for one journalled op."""
        c = locked.get(op['contract_id'])
        if c is None:
            return 'changed'
        restorable = {k: v for k, v in op['before'].items() if k != 'updated_at'}
        if op['op'] == 'hand_over_zone_links':
            links = handed_over_links_state(op['zone_links'])
            made = op.get('links_created', [])
            present = {str(l.pk): (str(l.zone_id), _iso(l.start_date), l.is_active, l.end_date)
                       for l in ContractZone.objects.filter(pk__in=[z['id'] for z in made])}
            if links == 'after' and present == {z['id']: (z['zone_id'], z['start_date'], True, None) for z in made}:
                return 'after'
            if links == 'before' and not present:
                return 'before'
            return 'changed'
        if op['op'] == 'redate_zone_link_end':
            current = {str(l.pk): (_iso(l.end_date), l.is_active)
                       for l in ContractZone.objects.filter(pk__in=[r['id'] for r in op['zone_links']])}
            for side in ('after', 'before'):
                if all(current.get(r['id']) == (r[side]['end_date'], r[side]['is_active']) for r in op['zone_links']):
                    return side
            return 'changed'
        if op['op'] == 'create_successor':
            created = op['created']
            exists = Contract.objects.filter(pk=created['contract_id']).first()
            handed = handed_over_links_state(op.get('old_zone_links_closed', []))
            if self._contract_matches(c, op['after']) and exists is not None and handed != 'after':
                return 'changed'  # a handed-over link of the old term changed, or its zone was linked anew
            if 'old_zone_links_closed' not in op and self._contract_matches(c, op['after']) and exists is not None:
                # A journal written before the hand-over existed: the old term's links were left
                # open then. If a later repair (hand_over_zone_links) closed them, deleting the
                # created term would leave those zones with no active link at all.
                copied = {z['zone_id'] for z in op['created'].get('zone_links', [])}
                still_open = {str(z) for z in ContractZone.objects.filter(
                    contract=c, zone_id__in=list(copied), is_active=True).values_list('zone_id', flat=True)}
                if copied - still_open:
                    return 'handed_over_since'
            if exists is None and op.get('old_zone_links_closed') and handed != 'before':
                return 'changed'
            if self._contract_matches(c, op['after']) and exists is not None:
                if exists.updated_at != _instant(created['updated_at'], 'journal updated_at') \
                        or str(exists.renewed_from_id) != created['renewed_from'] or exists.status != created['status']:
                    return 'touched'
                rows = {str(l.pk): l.updated_at for l in exists.service_locations.all()}
                want = {r['id']: _instant(r['updated_at'], 'journal updated_at') for r in created['service_locations']}
                own = created.get('zone_links', [])
                links = {str(l.pk): (str(l.zone_id), _iso(l.start_date), l.is_active, l.end_date)
                         for l in ContractZone.objects.filter(pk__in=[z['id'] for z in own])}
                if links != {z['id']: (z['zone_id'], z['start_date'], True, None) for z in own}:
                    return 'touched'
                if rows != want or _inbound_rows(exists, [z['id'] for z in own]):
                    return 'touched'
                return 'after'
            if exists is None and self._contract_matches(c, restorable):
                return 'before'
            return 'touched' if exists is not None else 'changed'
        if op['op'] == 'mark_cancelled':
            if self._contract_matches(c, op['after']):
                known = [link['id'] for link in op['zone_links']]
                known += [pk for z in op['zones'] for pk in z.get('other_active_links', [])]
                zone_ids = [z['id'] for z in op['zones']]
                if ContractZone.objects.filter(zone_id__in=zone_ids, is_active=True).exclude(pk__in=known).exists():
                    return 'changed'  # linked elsewhere since the run; reactivating would double-link the zone
                for link in op['zone_links']:
                    row = ContractZone.objects.filter(pk=link['id']).first()
                    if row is None or _iso(row.end_date) != link['after']['end_date'] \
                            or row.is_active != link['after']['is_active']:
                        return 'changed'
                return 'after'
            if self._contract_matches(c, restorable):
                return 'before'
            return 'changed'
        if self._contract_matches(c, op['after']):
            return 'after'
        if self._contract_matches(c, restorable):
            return 'before'
        return 'changed'

    def _revert_group(self, group, cls, ops, reverted_batch):
        notes = {}
        try:
            with transaction.atomic():
                ids = sorted({op['contract_id'] for op in ops} |
                             {op['created']['contract_id'] for op in ops if op.get('created')})
                locked = {str(c.pk): c for c in
                          Contract.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
                states = [self._op_state(op, locked) for op in ops]
                if 'handed_over_since' in states:
                    for op, state in zip(ops, states):
                        if state == 'handed_over_since':
                            batches = sorted({a.additional_data.get('batch_id') for a in AuditLog.objects.filter(
                                model_name='Contract', record_id=op['contract_id'],
                                additional_data__op='hand_over_zone_links') if a.additional_data.get('batch_id')})
                            notes[op['contract_id']] = (
                                "the old term's zone links were handed over to the new term after this run; "
                                'revert the zone-link repair first (batch ' + (', '.join(batches) or 'unknown') + ')')
                    return 'zone_links_handed_over_since_apply', notes
                if all(s == 'before' for s in states):
                    return 'already_reverted', notes
                if 'touched' in states:
                    return 'created_contract_touched', notes
                if any(s != 'after' for s in states):
                    return 'changed_since_apply', notes
                if not self.cmd.execute_mode:
                    return 'would_revert', notes
                for op in reversed(ops):
                    notes[op['contract_id']] = self._revert_op(group, cls, op, locked, reverted_batch)
        except DatabaseError as exc:
            return f'write_failed({exc.__class__.__name__})', notes
        return 'reverted', notes

    def _revert_meta(self, group, cls, op, reverted_batch, action):
        return {
            'command': self.cmd.COMMAND_NAME, 'mode': 'revert', 'batch_id': self.cmd.batch_id,
            'reverted_batch_id': reverted_batch, 'group': group, 'class': cls, 'op': op['op'],
            'evidence': op.get('evidence', ''), 'action': action, 'timestamp': timezone.now().isoformat(),
        }

    def _revert_op(self, group, cls, op, locked, reverted_batch):
        note = ''
        if op['op'] in LINK_OPS:
            if op['op'] == 'hand_over_zone_links':
                made = [z['id'] for z in op.get('links_created', [])]
                ContractZone.objects.filter(pk__in=made).delete()
                reopen_handed_over_links(op['zone_links'])
                note = f'{len(op["zone_links"])} zone link(s) reopened' + (
                    f'; {len(made)} link(s) on the renewal removed' if made else '')
            else:
                for r in op['zone_links']:
                    ContractZone.objects.filter(pk=r['id']).update(
                        end_date=date.fromisoformat(r['before']['end_date']), updated_at=timezone.now())
                note = f'{len(op["zone_links"])} zone link end date(s) restored'
            AuditLog.objects.create(
                user=self.cmd.actor, action='UPDATE', model_name='Contract', record_id=op['contract_id'],
                changes={}, additional_data={
                    **self._revert_meta(group, cls, op, reverted_batch, f'Correction reverted: {op["op"]}'),
                    'zone_links': [r['id'] for r in op['zone_links']],
                    'links_removed': [z['id'] for z in op.get('links_created', [])]})
            return note
        if op['op'] == 'create_successor':
            created = Contract.objects.get(pk=op['created']['contract_id'])
            AuditLog.objects.create(
                user=self.cmd.actor, action='DELETE', model_name='Contract', record_id=str(created.pk),
                changes={'contract_number': {'old': created.contract_number, 'new': None}},
                additional_data=self._revert_meta(group, cls, op, reverted_batch,
                                                  'Correction reverted: created term deleted'),
            )
            copied = len(op['created'].get('zone_links', []))
            created.delete()  # cascades to its service-location rows and its copied zone links
            handed = op.get('old_zone_links_closed', [])
            reopen_handed_over_links(handed)
            note = 'final number not reused' + (f'; {copied} copied zone link(s) removed' if copied else '') + (
                f'; {len(handed)} old zone link(s) reopened' if handed else '')
        if op['op'] == 'mark_cancelled':
            for link in op['zone_links']:
                ContractZone.objects.filter(pk=link['id']).update(
                    end_date=date.fromisoformat(link['before']['end_date']) if link['before']['end_date'] else None,
                    is_active=link['before']['is_active'])
            left = []
            for zone in op['zones']:
                if zone['before'] == zone['after']:
                    continue
                updated = Zone.objects.filter(pk=zone['id'], status=zone['after']['status']).update(
                    status=zone['before']['status'])
                if not updated:
                    left.append(zone['id'])
            note = f'{len(op["zone_links"])} zone link(s) restored'
            if left:
                note += f'; {len(left)} zone status(es) changed since apply, left as they are: {", ".join(left)}'
        c = locked[op['contract_id']]
        before = contract_state(c)
        restore = op['before']
        Contract.objects.filter(pk=c.pk).update(
            status=restore['status'], is_active=restore['is_active'],
            renewed_from_id=restore['renewed_from'], updated_at=timezone.now())
        c.refresh_from_db()
        AuditLog.objects.create(
            user=self.cmd.actor, action='UPDATE', model_name='Contract', record_id=str(c.pk),
            changes=_changes(before, contract_state(c)),
            additional_data=self._revert_meta(group, cls, op, reverted_batch,
                                              f'Correction reverted: {before["status"]} -> {c.status}'),
        )
        return note
