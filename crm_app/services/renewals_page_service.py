"""Renewals page: the working replacement for a renewal-funnel month tab.

Read-only. Builds on the Renewal Book (``renewal_book_service``): every row
carries the exact Renewal Book row for the term, unchanged, so the page and the
``renewal-book`` API / ``renewal_book`` MCP tool can never disagree about the
term itself. On top of it this module adds what a renewals person needs in
place of the sheet:

- one renewal state per term (``derive_renewal_state``), from the term, the
  contracts linked to it as its renewal (``renewed_from``), and their invoices;
- a "needs attention" reason (``attention_of``);
- the renewal's own value and the change from the current value
  (``value_change``);
- a month strip with counts per month, an "all open" view, and a filter by
  billing entity (the funnel sheets are split Thailand / International).

The rule lives here once. The frontend shows ``renewal.state`` / ``label`` and
never re-derives it.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from django.db.models import Prefetch, Q
from django.utils import timezone

from crm_app.services.renewal_book_service import _row_of  # one source for the term's book row

# ---------------------------------------------------------------------------
# Renewal states
# ---------------------------------------------------------------------------

NOT_STARTED = 'not_started'
DRAFTED = 'drafted'
SENT = 'sent'
SIGNED = 'signed'
INVOICED = 'invoiced'
PAID = 'paid'
RENEWED_UNLINKED = 'renewed_unlinked'
AUTO_RENEWS = 'auto_renews'
LAPSED = 'lapsed'
LOST = 'lost'

# Groups used for totals: 'open' (not yet renewed or lost), 'renewed', 'auto', 'lost'.
STATES = (
    # key, label, group
    (NOT_STARTED, 'Not started', 'open'),
    (DRAFTED, 'Renewal drafted', 'open'),
    (SENT, 'Sent', 'open'),
    (SIGNED, 'Signed / active', 'renewed'),
    (INVOICED, 'Invoiced', 'renewed'),
    (PAID, 'Paid', 'renewed'),
    (RENEWED_UNLINKED, 'Renewed, not linked', 'renewed'),
    (AUTO_RENEWS, 'Auto-renews', 'auto'),
    (LAPSED, 'Expired, not renewed', 'lost'),
    (LOST, 'Cancelled / lost', 'lost'),
)
STATE_LABEL = {key: label for key, label, _ in STATES}
STATE_GROUP = {key: group for key, _, group in STATES}

# Contract statuses of a renewal that has been signed (it went live; an Expired
# renewal ran its own term out, a Renewed one was renewed again).
SIGNED_STATUSES = ('Active', 'Renewed', 'Expired')
# Invoice statuses that mean an invoice was issued to the customer.
ISSUED_INVOICE_STATUSES = ('Sent', 'Overdue', 'Paid')

ATTENTION_REASONS = (
    ('ended_nothing_sent', 'Ended, no renewal sent'),
    ('ended_not_signed', 'Ended, renewal not signed'),
    ('ending_soon_nothing_sent', 'Ends within 30 days, no renewal sent'),
    ('renewed_unlinked', 'Marked Renewed, no renewal linked'),
)
ATTENTION_LABEL = dict(ATTENTION_REASONS)
ATTENTION_WINDOW_DAYS = 30

ENTITIES = {
    'th': 'BMAsia (Thailand) Co., Ltd.',
    'hk': 'BMAsia Limited',
}
ENTITY_OF_NAME = {name: key for key, name in ENTITIES.items()}

# The "all open" view looks this far back and ahead of today's month.
OPEN_MONTHS_BACK = 12
OPEN_MONTHS_AHEAD = 6


@dataclass(frozen=True)
class TermFacts:
    """The facts about the term that is up for renewal."""
    status: str
    auto_renew: bool = False


@dataclass(frozen=True)
class SuccessorFacts:
    """A contract linked to the term as its renewal (``renewed_from``)."""
    status: str
    start_date: Optional[date] = None
    lifecycle_type: str = ''
    signed_date: Optional[date] = None
    invoice_state: str = 'none'  # 'none' | 'invoiced' | 'paid'
    key: str = field(default='', compare=False)


@dataclass(frozen=True)
class RenewalState:
    state: str
    successor: Optional[SuccessorFacts]
    reason: str

    @property
    def label(self):
        return STATE_LABEL[self.state]

    @property
    def group(self):
        return STATE_GROUP[self.state]


def invoice_state_of(invoice_statuses: Sequence[str]) -> str:
    """'paid' when every issued invoice is paid, 'invoiced' when any is issued, else 'none'.

    Draft, Cancelled and Refunded invoices are not counted as issued.
    """
    issued = [s for s in invoice_statuses if s in ISSUED_INVOICE_STATUSES]
    if not issued:
        return 'none'
    return 'paid' if all(s == 'Paid' for s in issued) else 'invoiced'


def _successor_rank(s: SuccessorFacts):
    if s.status in SIGNED_STATUSES or s.signed_date:
        stage = 3
    elif s.status == 'Sent':
        stage = 2
    else:
        stage = 1
    money = {'paid': 2, 'invoiced': 1}.get(s.invoice_state, 0)
    return (stage, money, s.start_date or date.min)


def pick_successor(successors: Sequence[SuccessorFacts]) -> Optional[SuccessorFacts]:
    """The renewal that counts: furthest along, then latest start. None if no live one.

    Add-on contracts (lifecycle_type 'addon') are not renewals, and Cancelled
    renewals are dead; neither is picked.
    """
    live = [s for s in successors if s.lifecycle_type != 'addon' and s.status != 'Cancelled']
    if not live:
        return None
    return max(live, key=_successor_rank)


def derive_renewal_state(term: TermFacts, successors: Sequence[SuccessorFacts]) -> RenewalState:
    """Map a term and its linked renewals to one state. The only copy of this rule.

    1. A Cancelled term is lost, whatever is linked to it.
    2. Otherwise the furthest-along live renewal decides: paid, invoiced,
       signed (Active/Renewed/Expired, or a recorded signed date), sent, drafted.
       An invoice issued on a renewal that is still Sent or Draft counts
       (decision of 15 Nov 2026: an issued invoice is evidence of the renewal).
    3. With no live renewal: a term marked Renewed is "renewed, not linked";
       a term whose renewals were all cancelled is lost (renewal declined);
       an Expired term lapsed (Expired means lapsed with no successor);
       an auto-renewing term auto-renews; anything else has not started.
    """
    if term.status == 'Cancelled':
        return RenewalState(LOST, None, 'term_cancelled')

    renewals = [s for s in successors if s.lifecycle_type != 'addon']
    best = pick_successor(renewals)
    if best is not None:
        if best.invoice_state == 'paid':
            return RenewalState(PAID, best, 'renewal_paid')
        if best.invoice_state == 'invoiced':
            return RenewalState(INVOICED, best, 'renewal_invoiced')
        if best.status in SIGNED_STATUSES or best.signed_date:
            return RenewalState(SIGNED, best, 'renewal_signed')
        if best.status == 'Sent':
            return RenewalState(SENT, best, 'renewal_sent')
        return RenewalState(DRAFTED, best, 'renewal_drafted')

    if term.status == 'Renewed':
        return RenewalState(RENEWED_UNLINKED, None, 'term_marked_renewed')
    if renewals:  # every renewal was cancelled
        return RenewalState(LOST, None, 'renewal_cancelled')
    if term.status == 'Expired':
        return RenewalState(LAPSED, None, 'term_expired')
    if term.auto_renew:
        return RenewalState(AUTO_RENEWS, None, 'auto_renew')
    return RenewalState(NOT_STARTED, None, 'no_renewal')


def attention_of(state: str, days_from_end: Optional[int]) -> Optional[str]:
    """Why a row needs action now, or None. ``days_from_end`` is today minus the end date."""
    if state == RENEWED_UNLINKED:
        return 'renewed_unlinked'
    if days_from_end is None:
        return None
    if days_from_end > 0 and state in (NOT_STARTED, DRAFTED):
        return 'ended_nothing_sent'
    if days_from_end > 0 and state == SENT:
        return 'ended_not_signed'
    if -ATTENTION_WINDOW_DAYS <= days_from_end <= 0 and state in (NOT_STARTED, DRAFTED):
        return 'ending_soon_nothing_sent'
    return None


def term_months(start: Optional[date], end: Optional[date]) -> Optional[int]:
    """Months a term covers, rounded: 1 Jan-31 Dec is 12, 15 Mar-14 Mar is 12. None if a date is missing."""
    if not start or not end or end < start:
        return None
    return max(1, round(((end - start).days + 1) / 30.4375))


def value_change(old_value, old_months, new_value, new_months, same_currency):
    """(change, basis). basis: 'term' (same length), 'per_year' (lengths differ), or None."""
    if new_value is None or not same_currency:
        return None, None
    old_value, new_value = float(old_value or 0), float(new_value or 0)
    if old_months and new_months and abs(old_months - new_months) > 1:
        per_year = new_value * 12 / new_months - old_value * 12 / old_months
        return round(per_year, 2), 'per_year'
    return round(new_value - old_value, 2), 'term'


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

def _entity_key(contract):
    name = contract.billing_entity or getattr(contract.company, 'billing_entity', '')
    return ENTITY_OF_NAME.get(name)


def _owner_of(contract):
    opp = contract.opportunity
    owner = getattr(opp, 'owner', None) if opp else None
    if owner is not None:
        name = (owner.get_full_name() or owner.username or '').strip()
        if name:
            return name, 'opportunity_owner'
    name = (contract.bmasia_contact_name or '').strip()
    if name:
        return name, 'bmasia_contact'
    return None, None


def _successor_facts(s):
    return SuccessorFacts(
        status=s.status,
        start_date=s.start_date,
        lifecycle_type=s.lifecycle_type or '',
        signed_date=s.signed_date,
        invoice_state=invoice_state_of([i.status for i in s.invoices.all()]),
        key=str(s.pk),
    )


def renewals_row(contract, today):
    """The Renewal Book row for ``contract`` plus the page's ``renewal`` block."""
    row = _row_of(contract)
    successors = list(contract.renewals.all())
    facts = [_successor_facts(s) for s in successors]
    result = derive_renewal_state(TermFacts(contract.status, bool(contract.auto_renew)), facts)
    chosen = None
    if result.successor is not None:
        chosen = next(s for s in successors if str(s.pk) == result.successor.key)
    days = (today - contract.end_date).days if contract.end_date else None
    attention = attention_of(result.state, days)
    months = term_months(contract.start_date, contract.end_date)
    owner, owner_source = _owner_of(contract)

    successor_block = None
    change, basis = None, None
    if chosen is not None:
        chosen_months = term_months(chosen.start_date, chosen.end_date)
        change, basis = value_change(
            contract.value, months, chosen.value, chosen_months, chosen.currency == contract.currency)
        successor_block = {
            'contract_id': str(chosen.pk),
            'contract_number': chosen.contract_number,
            'status': chosen.status,
            'start_date': chosen.start_date.isoformat() if chosen.start_date else None,
            'end_date': chosen.end_date.isoformat() if chosen.end_date else None,
            'term_months': chosen_months,
            'value': float(chosen.value or 0),
            'currency': chosen.currency,
            'signed_date': chosen.signed_date.isoformat() if chosen.signed_date else None,
            'sent_date': chosen.sent_date.isoformat() if chosen.sent_date else None,
            'invoice_state': result.successor.invoice_state,
            'other_company': chosen.company_id != contract.company_id,
        }

    row.update({
        'property_name': contract.property_name or '',
        'contract_type': contract.contract_type,
        'start_date': contract.start_date.isoformat() if contract.start_date else None,
        'term_months': months,
        'entity': _entity_key(contract),
        'owner': owner,
        'owner_source': owner_source,
        'days_from_end': days,
        'renewal': {
            'state': result.state,
            'label': result.label,
            'group': result.group,
            'reason': result.reason,
            'attention': attention,
            'attention_label': ATTENTION_LABEL.get(attention),
            'successor': successor_block,
            'other_linked': [
                {
                    'contract_id': str(s.pk),
                    'contract_number': s.contract_number,
                    'status': s.status,
                    'lifecycle_type': s.lifecycle_type or '',
                }
                for s in successors if chosen is None or s.pk != chosen.pk
            ],
            'value_change': change,
            'value_change_basis': basis,
        },
    })
    return row


def _queryset():
    from crm_app.models import Contract

    return (
        Contract.objects
        .select_related('company', 'company__parent_company', 'opportunity__owner')
        .prefetch_related(
            'service_locations',
            'invoices',
            Prefetch('renewals', queryset=Contract.objects.prefetch_related('invoices')),
        )
        .exclude(status='Draft')  # as the Renewal Book: a Draft is not a term
    )


def _entity_filter(qs, entity):
    if not entity:
        return qs
    name = ENTITIES[entity]
    return qs.filter(Q(billing_entity=name) | Q(billing_entity='', company__billing_entity=name))


def _month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def _shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _sort_key(row):
    attention = row['renewal']['attention']
    return (0 if attention else 1, row['end_date'] or '9999', row['company'].lower(), row['contract_number'])


def _strip(rows, year):
    months = []
    for m in range(1, 13):
        in_month = [r for r in rows if r['end_date'] and int(r['end_date'][5:7]) == m]
        groups = [r['renewal']['group'] for r in in_month]
        months.append({
            'year': year,
            'month': m,
            'label': date(year, m, 1).strftime('%b %Y'),
            'count': len(in_month),
            'attention': sum(1 for r in in_month if r['renewal']['attention']),
            'open': groups.count('open'),
            'renewed': groups.count('renewed'),
            'auto': groups.count('auto'),
            'lost': groups.count('lost'),
        })
    return months


def build_renewals_view(*, year, month=None, view='month', entity='', today=None):
    """The data behind /renewals. Raises ValueError on bad parameters.

    ``view='month'`` returns every non-Draft term ending in year/month.
    ``view='open'`` returns, across today's month - 12 to + 6, every term whose
    renewal is still open (not started, drafted, sent) or that needs attention.
    Both return the 12-month strip for ``year``.
    """
    today = today or timezone.localdate()
    year = int(year)
    if not 2000 <= year <= 2100:
        raise ValueError('year must be between 2000 and 2100')
    if view not in ('month', 'open'):
        raise ValueError("view must be 'month' or 'open'")
    entity = entity or ''
    if entity not in ('',) + tuple(ENTITIES):
        raise ValueError("entity must be 'th' or 'hk'")
    if view == 'month':
        month = int(month)
        if not 1 <= month <= 12:
            raise ValueError('month must be 1-12')

    year_qs = _entity_filter(_queryset(), entity).filter(
        end_date__gte=date(year, 1, 1), end_date__lte=date(year, 12, 31))
    year_rows = [renewals_row(c, today) for c in year_qs]

    if view == 'month':
        rows = [r for r in year_rows if int(r['end_date'][5:7]) == month]
        window = {'start': date(year, month, 1).isoformat(), 'end': _month_end(year, month).isoformat()}
    else:
        sy, sm = _shift_month(today.year, today.month, -OPEN_MONTHS_BACK)
        ey, em = _shift_month(today.year, today.month, OPEN_MONTHS_AHEAD)
        start, end = date(sy, sm, 1), _month_end(ey, em)
        window = {'start': start.isoformat(), 'end': end.isoformat()}
        open_qs = _entity_filter(_queryset(), entity).filter(end_date__gte=start, end_date__lte=end)
        rows = [
            r for r in (renewals_row(c, today) for c in open_qs)
            if r['renewal']['group'] == 'open' or r['renewal']['attention']
        ]
    rows.sort(key=_sort_key)

    return {
        'as_of': today.isoformat(),
        'view': view,
        'year': year,
        'month': month if view == 'month' else None,
        'month_label': date(year, month, 1).strftime('%B %Y') if view == 'month' else None,
        'entity': entity,
        'window': window,
        'states': [{'key': k, 'label': label, 'group': g} for k, label, g in STATES],
        'attention_reasons': [{'key': k, 'label': label} for k, label in ATTENTION_REASONS],
        'months': _strip(year_rows, year),
        'count': len(rows),
        'rows': rows,
    }
