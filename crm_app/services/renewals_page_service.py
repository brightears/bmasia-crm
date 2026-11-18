"""Renewals page: the working replacement for a renewal-funnel month tab.

Read-only. Builds on the Renewal Book (``renewal_book_service``): every row
carries the Renewal Book row for the term, so the page and the ``renewal-book``
API / ``renewal_book`` MCP tool agree about the term itself. The book's own
view of the renewal (its ``successor_contract`` / ``successor_status``, the
latest-starting linked contract, and its ``invoices_paid`` /
``outstanding_amount``, the term's own invoices) is moved under ``book`` so a
row gives one answer to "has this renewed?": ``renewal``.

``value`` is the annual price for terms of any length (decision of 19 Nov
2026: every writer stores the yearly figure, and the contract PDF guard holds
it to the per-zone yearly prices), so values are compared directly.

On top of the book this module adds what a renewals person needs:

- one renewal state per term (``derive_renewal_state``), from the term, the
  contracts linked to it (``renewed_from``), their invoices, and unlinked live
  contracts of the same company around its end;
- a "needs attention" reason (``attention_of``);
- the renewal's own value and the change from the current value;
- the funnel's month convention (``funnel_window``) or calendar months;
- a month strip, an "all open" view and a filter by billing entity.

The rule lives here once. The frontend shows ``renewal.state`` / ``label`` /
``summary_bucket`` / ``in_rate`` and never re-derives them.
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
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
PART_PAID = 'part_paid'
PAID = 'paid'
RENEWED_UNLINKED = 'renewed_unlinked'
AUTO_RENEWS = 'auto_renews'
AUTO_UNCONFIRMED = 'auto_unconfirmed'
LIVE_UNLINKED = 'live_unlinked'
LAPSED = 'lapsed'
LOST = 'lost'
PLACEHOLDER = 'placeholder'

# Groups: 'open' (not yet renewed or lost), 'renewed', 'auto' (renews by itself,
# term not ended yet), 'unlinked' (the company has a live term that is not
# linked: probably renewed, not proven), 'lost', 'excluded' (not a real term).
STATES = (
    # key, label, group
    (NOT_STARTED, 'Not started', 'open'),
    (AUTO_UNCONFIRMED, 'Auto-renew, no new term', 'open'),
    (DRAFTED, 'Renewal drafted', 'open'),
    (SENT, 'Sent', 'open'),
    (SIGNED, 'Signed / active', 'renewed'),
    (INVOICED, 'Invoiced', 'renewed'),
    (PART_PAID, 'Part paid', 'renewed'),
    (PAID, 'Paid', 'renewed'),
    (RENEWED_UNLINKED, 'Renewed, not linked', 'renewed'),
    (AUTO_RENEWS, 'Auto-renews', 'auto'),
    (LIVE_UNLINKED, 'Live term not linked', 'unlinked'),
    (LAPSED, 'Expired, not renewed', 'lost'),
    (LOST, 'Cancelled / lost', 'lost'),
    (PLACEHOLDER, 'Placeholder (closed)', 'excluded'),
)
STATE_LABEL = {key: label for key, label, _ in STATES}
STATE_GROUP = {key: group for key, _, group in STATES}

# Contract statuses of a renewal that has been signed (it went live; an Expired
# renewal ran its own term out, a Renewed one was renewed again).
SIGNED_STATUSES = ('Active', 'Renewed', 'Expired')
# Invoice statuses that mean an invoice was issued to the customer.
ISSUED_INVOICE_STATUSES = ('Sent', 'Overdue', 'Paid')
# Statuses of a contract that is live or on its way: a renewal not yet linked.
LIVE_STATUSES = ('Active', 'Sent', 'Draft')
# A term must be closed before a placeholder marker can hide it.
CLOSED_STATUSES = ('Expired', 'Renewed', 'Cancelled')

ATTENTION_REASONS = (
    ('renewed_unlinked', 'Marked Renewed, no renewal linked'),
    ('renewed_link_mid_term', 'Marked Renewed; the linked contract starts mid-term (possible add-on)'),
    ('renewed_link_overlap', 'Marked Renewed; the linked contract overlaps the term, check the dates'),
    ('link_the_renewal', 'The company has a live term that is not linked: link the renewal'),
    ('invoice_refunded', 'Invoice refunded'),
    ('renewed_after_gap', 'Renewed after a gap in service'),
    ('auto_renew_ended', 'Auto-renew set, term ended, no new term recorded'),
    ('ended_nothing_sent', 'Ended, no renewal sent'),
    ('ended_not_signed', 'Ended, renewal not signed'),
    ('ending_soon_nothing_sent', 'Ends within 30 days, no renewal sent'),
)
ATTENTION_LABEL = dict(ATTENTION_REASONS)
ATTENTION_WINDOW_DAYS = 30
GAP_ATTENTION_DAYS = 365

# A linked contract that starts more than 90 days before the term's end (or not
# after the term's start) is not the renewal: it starts mid-term, a possible
# add-on; or, when it is itself a full term at the same value, an overlapping
# term whose dates need checking. One that starts more than 60 days after the
# end still counts as the renewal and is flagged 'late' with its gap: in the
# 16 Nov data 145 of the 159 such links hang off the 2025 placeholder terms
# that the 15 Nov rule 1 linked to the client's real term on purpose. The
# window is the data-quality check's; it also finds unlinked live terms.
RENEWAL_START_BEFORE_END_DAYS = 90
RENEWAL_START_AFTER_END_DAYS = 60
RENEWAL_LINKS = ('renewal', 'late')
LINK_LABEL = {
    'renewal': 'Renewal',
    'late': 'Renewal, starts more than 60 days after the term ended',
    'addon': 'Add-on (lifecycle type)',
    'mid_term': 'Linked contract starts mid-term (possible add-on)',
    'overlap': 'Overlapping term, check the dates',
}

# Placeholders closed by the November corrections (parity rules of 15 Nov), on
# a closed term only: rule 2 adds this exact note line, naming the multi-year
# contract a year-one record repeats (r7_build.py); rule 3 expires a twin
# company's placeholder and leaves only an AuditLog row with class 'R3' and
# op 'mark_expired'.
PLACEHOLDER_NOTE_RE = re.compile(
    r'^Placeholder record \(\d{4}-\d{2}-\d{2} – \d{4}-\d{2}-\d{2}\), multi-year duplicate of \S+ '
    r'\(\d{4}-\d{2}-\d{2} – \d{4}-\d{2}-\d{2}\)\. Kept closed; not a separate term\.$',
    re.MULTILINE,
)
PLACEHOLDER_AUDIT_CLASS = 'R3'
PLACEHOLDER_AUDIT_OP = 'mark_expired'

# The 2025 "Kent stamp" placeholder terms (1 Jan - 31 Dec 2025, project
# decisions of 14 Nov): real records of last year's term, kept as the closed
# previous term. Listed, but never counted as lost or in the rate.
TERM_2025_START, TERM_2025_END = date(2025, 1, 1), date(2025, 12, 31)

ENTITIES = {
    'th': 'BMAsia (Thailand) Co., Ltd.',
    'hk': 'BMAsia Limited',
}
ENTITY_OF_NAME = {name: key for key, name in ENTITIES.items()}

BASES = ('funnel', 'calendar')

# The "all open" view looks this far back and ahead of today's month.
OPEN_MONTHS_BACK = 12
OPEN_MONTHS_AHEAD = 6

# Billing frequencies as the contract form and the quote conversion write them
# (and the older spellings in the data), lower case. Anything else counts as
# annual, which asks the most before "Paid".
BILLING_INSTALMENTS = {
    'annually': 1, 'annual': 1, 'yearly': 1,
    'semi-annually': 2, 'semi-annual': 2, 'biannually': 2, 'bi-annually': 2, 'biannual': 2, 'half-yearly': 2,
    'quarterly': 4,
    'monthly': 12,
}
ONE_TIME_BILLING = {'one-time', 'one time', 'onetime', 'upfront', 'full term', 'full-term'}


@dataclass(frozen=True)
class InvoiceFacts:
    status: str
    amount: Decimal = Decimal('0')
    currency: str = ''


@dataclass(frozen=True)
class TermFacts:
    """The facts about the term that is up for renewal."""
    status: str
    auto_renew: bool = False
    ended: bool = False          # today is after the end date
    placeholder: bool = False    # closed by the November corrections, not a real term
    live_unlinked: bool = False  # the company has a live contract around the end, not linked


@dataclass(frozen=True)
class SuccessorFacts:
    """A contract linked to the term (``renewed_from``)."""
    status: str
    start_date: Optional[date] = None
    lifecycle_type: str = ''
    signed_date: Optional[date] = None
    invoice_state: str = 'none'  # 'none' | 'invoiced' | 'part_paid' | 'paid'
    refunded: bool = False
    link: str = 'renewal'        # 'renewal' | 'late' | 'addon' | 'mid_term' | 'overlap'
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


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def instalments_per_year(billing_frequency):
    """1, 2, 4 or 12 from the billing frequency; None for one-time billing; 1 if unknown."""
    text = (billing_frequency or '').strip().lower()
    if text in ONE_TIME_BILLING:
        return None
    return BILLING_INSTALMENTS.get(text, 1)


def due_so_far(value, billing_frequency, start, end, today):
    """What the customer owes for the renewal by today, before tax ("paid to date" basis).

    ``value`` is the annual price. Invoices are raised in advance, so the first
    instalment is due from the start (or before it). One-time billing: the
    whole value. A term up to 12 months: its value split over its instalments.
    A term over 12 months: an instalment is value / instalments a year.
    """
    value = Decimal(str(value or 0))
    per_year = instalments_per_year(billing_frequency)
    if per_year is None or value <= 0:
        return value
    months = term_months(start, end) or 12
    period = 12 / per_year
    count_in_term = max(1, round(months / period))
    instalment = value / count_in_term if months <= 12 else value / per_year
    if not start or today < start:
        due_count = 1
    else:
        elapsed = (today.year - start.year) * 12 + (today.month - start.month) - (1 if today.day < start.day else 0)
        due_count = min(count_in_term, int(elapsed // period) + 1)
    return (instalment * due_count).quantize(Decimal('0.01'))


def invoice_state_of(invoices: Sequence[InvoiceFacts], due: Decimal, currency: str) -> str:
    """'paid', 'part_paid', 'invoiced' or 'none' for a renewal's invoices.

    Only issued invoices (Sent, Overdue, Paid) in the renewal's currency with a
    non-zero amount count. 'paid' needs every such invoice paid and the paid
    amounts (before tax) to cover what is due so far; some paid is 'part_paid'.
    """
    issued = [i for i in invoices
              if i.status in ISSUED_INVOICE_STATUSES and Decimal(str(i.amount or 0)) > 0
              and (not i.currency or i.currency == currency)]
    if not issued:
        return 'none'
    paid = sum((Decimal(str(i.amount)) for i in issued if i.status == 'Paid'), Decimal('0'))
    if paid <= 0:
        return 'invoiced'
    all_paid = all(i.status == 'Paid' for i in issued)
    if all_paid and paid >= Decimal(str(due or 0)) * Decimal('0.99'):
        return 'paid'
    return 'part_paid'


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def in_renewal_window(term_start, term_end, start):
    """Whether a contract starting on ``start`` can be this term's renewal by date alone."""
    if not start or not term_end:
        return True
    if (term_start and start <= term_start) or start < term_end - timedelta(days=RENEWAL_START_BEFORE_END_DAYS):
        return False
    return start <= term_end + timedelta(days=RENEWAL_START_AFTER_END_DAYS)


def classify_link(term_start, term_end, start, lifecycle_type, *, link_months=None, link_value=None,
                  term_value=None):
    """Whether a linked contract is the renewal, by lifecycle type and by when it starts.

    'mid_term' becomes 'overlap' when the linked contract is itself a full term
    (11 months or more) at the term's value: a second record of a term, not an add-on.
    """
    if lifecycle_type == 'addon':
        return 'addon'
    if not start or not term_end:
        return 'renewal'
    if (term_start and start <= term_start) or start < term_end - timedelta(days=RENEWAL_START_BEFORE_END_DAYS):
        if (link_months and link_months >= 11 and term_value is not None and link_value is not None
                and abs(float(link_value) - float(term_value)) <= max(1.0, 0.01 * abs(float(term_value)))):
            return 'overlap'
        return 'mid_term'
    if start > term_end + timedelta(days=RENEWAL_START_AFTER_END_DAYS):
        return 'late'
    return 'renewal'


_MONEY_RANK = {'paid': 3, 'part_paid': 2, 'invoiced': 1}


def _successor_rank(s: SuccessorFacts):
    # Money before stage: an issued invoice is evidence of the renewal (15 Nov),
    # so a Draft with an invoice outranks a Sent renewal without one.
    if s.status in SIGNED_STATUSES or s.signed_date:
        stage = 3
    elif s.status == 'Sent':
        stage = 2
    else:
        stage = 1
    return (_MONEY_RANK.get(s.invoice_state, 0), stage, s.start_date or date.min)


def pick_successor(successors: Sequence[SuccessorFacts]) -> Optional[SuccessorFacts]:
    """The renewal that counts: most money evidence, then furthest along, then latest start.

    Only links that are the renewal (``RENEWAL_LINKS``) and not Cancelled.
    """
    live = [s for s in successors if s.link in RENEWAL_LINKS and s.status != 'Cancelled']
    if not live:
        return None
    return max(live, key=_successor_rank)


def derive_renewal_state(term: TermFacts, successors: Sequence[SuccessorFacts]) -> RenewalState:
    """Map a term and its linked contracts to one state. The only copy of this rule.

    0. A placeholder closed by the November corrections is not a term.
    1. A Cancelled term is lost, whatever is linked to it.
    2. Otherwise the best live renewal decides: paid, part paid, invoiced,
       signed (Active/Renewed/Expired, or a recorded signed date), sent, drafted.
    3. With no live renewal: a term marked Renewed is "renewed, not linked";
       a term whose renewals were all cancelled is lost (renewal declined);
       otherwise, when the company has a live contract starting around the
       term's end that is not linked, "live term not linked";
       an Expired term lapsed (Expired means lapsed with no successor);
       an auto-renewing term auto-renews until its end date, and after it
       has "auto-renew, no new term"; anything else has not started.
    Linked contracts that are add-ons, start mid-term or overlap the term are
    never the renewal.
    """
    if term.placeholder:
        return RenewalState(PLACEHOLDER, None, 'placeholder')
    if term.status == 'Cancelled':
        return RenewalState(LOST, None, 'term_cancelled')

    renewals = [s for s in successors if s.link in RENEWAL_LINKS]
    best = pick_successor(renewals)
    if best is not None:
        if best.invoice_state == 'paid':
            return RenewalState(PAID, best, 'renewal_paid')
        if best.invoice_state == 'part_paid':
            return RenewalState(PART_PAID, best, 'renewal_part_paid')
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
    if term.live_unlinked:
        return RenewalState(LIVE_UNLINKED, None, 'company_live_term_unlinked')
    if term.status == 'Expired':
        return RenewalState(LAPSED, None, 'term_expired')
    if term.auto_renew:
        if term.ended:
            return RenewalState(AUTO_UNCONFIRMED, None, 'auto_renew_ended')
        return RenewalState(AUTO_RENEWS, None, 'auto_renew')
    return RenewalState(NOT_STARTED, None, 'no_renewal')


def attention_of(state: str, days_from_end: Optional[int], refunded: bool = False,
                 mid_term_link: bool = False, overlap_link: bool = False, recent_gap: bool = False) -> Optional[str]:
    """Why a row needs action now, or None. ``days_from_end`` is today minus the end date."""
    if state == PLACEHOLDER:
        return None
    if state == RENEWED_UNLINKED:
        if overlap_link:
            return 'renewed_link_overlap'
        return 'renewed_link_mid_term' if mid_term_link else 'renewed_unlinked'
    if state == LIVE_UNLINKED:
        return 'link_the_renewal'
    if refunded:
        return 'invoice_refunded'
    if recent_gap:
        return 'renewed_after_gap'
    if state == AUTO_UNCONFIRMED:
        return 'auto_renew_ended'
    if days_from_end is None:
        return None
    if days_from_end > 0 and state in (NOT_STARTED, DRAFTED):
        return 'ended_nothing_sent'
    if days_from_end > 0 and state == SENT:
        return 'ended_not_signed'
    if -ATTENTION_WINDOW_DAYS <= days_from_end <= 0 and state in (NOT_STARTED, DRAFTED):
        return 'ending_soon_nothing_sent'
    return None


def summary_bucket(state: str, never_activated: bool, term_2025: bool = False) -> str:
    """Which total a row counts in: 'open', 'renewed', 'auto', 'unlinked', 'lost', 'history' or 'excluded'.

    A never-activated (Sent) term is not counted as lost; a 2025 placeholder
    term that lapsed is history, not churn.
    """
    group = STATE_GROUP[state]
    if group == 'lost' and never_activated:
        return 'excluded'
    if group == 'lost' and term_2025:
        return 'history'
    return group


def in_rate(state: str, days_from_end: Optional[int], never_activated: bool, term_2025: bool = False) -> bool:
    """Whether the row counts in the renewal rate's denominator.

    Decided terms (renewed or lost) and ended terms that are still open count.
    Open terms still ahead, auto-renewals before their end, terms whose company
    has an unlinked live term, placeholders, 2025 placeholder terms and
    never-activated terms do not.
    """
    group = STATE_GROUP[state]
    if never_activated or term_2025 or group in ('excluded', 'auto', 'unlinked'):
        return False
    if group in ('renewed', 'lost'):
        return True
    return days_from_end is not None and days_from_end > 0


def term_months(start: Optional[date], end: Optional[date]) -> Optional[int]:
    """Months a term covers, rounded: 1 Jan-31 Dec is 12, 15 Mar-14 Mar is 12. None if a date is missing."""
    if not start or not end or end < start:
        return None
    return max(1, round(((end - start).days + 1) / 30.4375))


def value_change(old_value, new_value, same_currency):
    """The renewal's annual value minus the term's, or None across currencies.

    ``value`` is the annual price for any term length, so the two compare directly.
    """
    if new_value is None or not same_currency:
        return None
    return round(float(new_value or 0) - float(old_value or 0), 2)


def gap_days(term_end, renewal_start):
    """Days without a term between the end and the renewal's start (0 when it follows on)."""
    if not term_end or not renewal_start:
        return None
    return max(0, (renewal_start - term_end).days - 1)


# ---------------------------------------------------------------------------
# Months
# ---------------------------------------------------------------------------

def _month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def _shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def funnel_window(year, month):
    """The funnel tab for month N: terms ending from the last day of N-1 to the day before the last day of N.

    A term ending 31 Oct renews on 1 Nov, so it is a November renewal.
    """
    py, pm = _shift_month(year, month, -1)
    return _month_end(py, pm), _month_end(year, month) - timedelta(days=1)


def calendar_window(year, month):
    return date(year, month, 1), _month_end(year, month)


def month_window(year, month, basis):
    return funnel_window(year, month) if basis == 'funnel' else calendar_window(year, month)


def month_of(end_date, basis):
    """(year, month) of the tab a term ending on ``end_date`` belongs to."""
    if basis == 'funnel' and end_date == _month_end(end_date.year, end_date.month):
        return _shift_month(end_date.year, end_date.month, 1)
    return end_date.year, end_date.month


# ---------------------------------------------------------------------------
# Facts from the database (one path for the strip and the table)
# ---------------------------------------------------------------------------

def is_term_2025(contract):
    return contract.start_date == TERM_2025_START and contract.end_date == TERM_2025_END


def is_placeholder(contract, r3_ids):
    """A placeholder closed by the corrections: closed status AND the exact rule-2 note or a rule-3 audit row."""
    if contract.status not in CLOSED_STATUSES:
        return False
    return bool(PLACEHOLDER_NOTE_RE.search(contract.notes or '')) or str(contract.pk) in r3_ids


def _platforms(contract):
    """Products evidenced on the contract itself: service-location platforms and the service type."""
    found = {loc.platform for loc in contract.service_locations.all() if loc.platform in ('beatbreeze', 'soundtrack')}
    st = (contract.service_type or '').lower()
    if 'beat' in st:
        found.add('beatbreeze')
    elif 'soundtrack' in st:
        found.add('soundtrack')
    return found


def live_unlinked_match(term, candidate):
    """Whether ``candidate`` (same company, live, not linked here) looks like this term's renewal.

    It must start in the renewal window, not be another contract's renewal, and
    not name a different property or product than the term.
    """
    if candidate.pk == term.pk or candidate.status not in LIVE_STATUSES:
        return False
    if candidate.renewed_from_id is not None:
        return False
    if not in_renewal_window(term.start_date, term.end_date, candidate.start_date):
        return False
    a, b = (term.property_name or '').strip().lower(), (candidate.property_name or '').strip().lower()
    if a and b and a != b:
        return False
    pa, pb = _platforms(term), _platforms(candidate)
    if pa and pb and not (pa & pb):
        return False
    return True


@dataclass
class Evaluated:
    result: RenewalState
    days: Optional[int]
    attention: Optional[str]
    bucket: str
    in_rate: bool
    never_activated: bool
    is_addon: bool
    term_2025: bool
    successors: list
    facts: list
    refunded: bool
    live_candidates: list
    gap: Optional[int]


def _invoice_facts(contract):
    return [InvoiceFacts(i.status, i.amount, i.currency) for i in contract.invoices.all()]


def _evaluate(contract, today, r3_ids, company_live):
    days = (today - contract.end_date).days if contract.end_date else None
    successors = list(contract.renewals.all())
    facts = []
    for s in successors:
        invoices = _invoice_facts(s)
        facts.append(SuccessorFacts(
            status=s.status,
            start_date=s.start_date,
            lifecycle_type=s.lifecycle_type or '',
            signed_date=s.signed_date,
            invoice_state=invoice_state_of(
                invoices, due_so_far(s.value, s.billing_frequency, s.start_date, s.end_date, today), s.currency),
            refunded=any(i.status == 'Refunded' for i in invoices),
            link=classify_link(contract.start_date, contract.end_date, s.start_date, s.lifecycle_type or '',
                               link_months=term_months(s.start_date, s.end_date), link_value=s.value,
                               term_value=contract.value),
            key=str(s.pk),
        ))
    has_live_link = any(f.link in RENEWAL_LINKS and f.status != 'Cancelled' for f in facts)
    candidates = [] if has_live_link else [
        c for c in company_live.get(contract.company_id, ()) if live_unlinked_match(contract, c)]
    placeholder = is_placeholder(contract, r3_ids)
    term = TermFacts(contract.status, bool(contract.auto_renew), ended=days is not None and days > 0,
                     placeholder=placeholder, live_unlinked=bool(candidates))
    result = derive_renewal_state(term, facts)
    term_2025 = is_term_2025(contract)
    refunded = result.state != PLACEHOLDER and any(f.refunded for f in facts if f.link in RENEWAL_LINKS)
    gap = None
    recent_gap = False
    if result.successor is not None and result.successor.link == 'late':
        gap = gap_days(contract.end_date, result.successor.start_date)
        # The 2025 placeholder terms carry artificial dates: their "gap" is not a gap in service.
        recent_gap = (not term_2025 and result.successor.start_date is not None
                      and result.successor.start_date > today - timedelta(days=GAP_ATTENTION_DAYS))
    attention = attention_of(result.state, days, refunded,
                             mid_term_link=any(f.link == 'mid_term' for f in facts),
                             overlap_link=any(f.link == 'overlap' for f in facts),
                             recent_gap=recent_gap)
    never_activated = contract.status == 'Sent'
    prev = contract.renewed_from
    is_addon = (contract.lifecycle_type or '') == 'addon' or (
        prev is not None and classify_link(prev.start_date, prev.end_date, contract.start_date, '') == 'mid_term')
    return Evaluated(result, days, attention, summary_bucket(result.state, never_activated, term_2025),
                     in_rate(result.state, days, never_activated, term_2025), never_activated, is_addon,
                     term_2025, successors, facts, refunded, candidates, gap)


def _r3_placeholder_ids(contract_ids):
    """Contracts expired as a twin company's placeholder by the corrections (rule 3): AuditLog class R3, op mark_expired."""
    from crm_app.models import AuditLog

    ids = [str(i) for i in contract_ids]
    if not ids:
        return set()
    return set(AuditLog.objects.filter(
        model_name='Contract', action='UPDATE', record_id__in=ids,
        additional_data__class=PLACEHOLDER_AUDIT_CLASS, additional_data__op=PLACEHOLDER_AUDIT_OP,
    ).values_list('record_id', flat=True))


def _company_live_contracts(company_ids):
    """Live (Active, Sent, Draft) contracts of these companies, by company id: one query plus locations."""
    from crm_app.models import Contract

    ids = list(set(company_ids))
    if not ids:
        return {}
    by_company = {}
    for c in (Contract.objects.filter(company_id__in=ids, status__in=LIVE_STATUSES)
              .only('id', 'company_id', 'contract_number', 'status', 'start_date', 'end_date', 'renewed_from_id',
                    'property_name', 'service_type')
              .prefetch_related('service_locations')):
        by_company.setdefault(c.company_id, []).append(c)
    return by_company


_SUCCESSOR_FIELDS = ('id', 'renewed_from_id', 'company_id', 'contract_number', 'status', 'start_date', 'end_date',
                     'value', 'currency', 'billing_frequency', 'lifecycle_type', 'signed_date', 'sent_date')
_INVOICE_FIELDS = ('id', 'contract_id', 'status', 'amount', 'total_amount', 'currency')


def _prefetches():
    from crm_app.models import Contract, Invoice

    invoices = Invoice.objects.only(*_INVOICE_FIELDS)
    return (
        Prefetch('invoices', queryset=invoices),
        Prefetch('renewals', queryset=Contract.objects.only(*_SUCCESSOR_FIELDS)
                 .prefetch_related(Prefetch('invoices', queryset=invoices))),
    )


def _rows_queryset():
    from crm_app.models import Contract

    return (
        Contract.objects
        .select_related('company', 'company__parent_company', 'opportunity__owner', 'renewed_from')
        .prefetch_related('service_locations', *_prefetches())
        .exclude(status='Draft')  # as the Renewal Book: a Draft is not a term
    )


def _strip_queryset():
    """Just what the rule needs, for counting a whole year cheaply."""
    from crm_app.models import Contract

    return (
        Contract.objects
        .only('id', 'company_id', 'status', 'auto_renew', 'start_date', 'end_date', 'value', 'notes',
              'lifecycle_type', 'property_name', 'service_type',
              'renewed_from__start_date', 'renewed_from__end_date')
        .select_related('renewed_from')
        .prefetch_related('service_locations', *_prefetches())
        .exclude(status='Draft')
    )


def _entity_filter(qs, entity):
    if not entity:
        return qs
    name = ENTITIES[entity]
    return qs.filter(Q(billing_entity=name) | Q(billing_entity='', company__billing_entity=name))


def _in_window(qs, start, end):
    return qs.filter(end_date__gte=start, end_date__lte=end)


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

BOOK_RENEWAL_FIELDS = ('successor_contract', 'successor_status', 'invoices_paid', 'outstanding_amount')
PLATFORM_PRODUCT = {'beatbreeze': 'Beat Breeze', 'soundtrack': 'Soundtrack'}


def product_display(book_product, platforms):
    """(product, source) shown on the page.

    The Renewal Book's product (service type, then the company's funnel product)
    stays first. Only where it says 'Other' do the contract's service-location
    platforms decide, since they are contract-level evidence of the product.
    """
    if book_product != 'Other':
        return book_product, 'renewal_book'
    found = sorted({PLATFORM_PRODUCT[p] for p in platforms if p in PLATFORM_PRODUCT})
    if not found:
        return 'Other', 'renewal_book'
    return ' + '.join(found), 'service_locations'


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


def renewals_row(contract, today, r3_ids=frozenset(), company_live=None):
    """The Renewal Book row for ``contract`` (its renewal fields under ``book``) plus ``renewal``."""
    row = _row_of(contract)
    book = {key: row.pop(key) for key in BOOK_RENEWAL_FIELDS}
    ev = _evaluate(contract, today, r3_ids, company_live or {})
    result = ev.result
    chosen = None
    if result.successor is not None:
        chosen = next(s for s in ev.successors if str(s.pk) == result.successor.key)
    months = term_months(contract.start_date, contract.end_date)
    owner, owner_source = _owner_of(contract)

    successor_block = None
    change = None
    if chosen is not None:
        change = value_change(contract.value, chosen.value, chosen.currency == contract.currency)
        successor_block = {
            'contract_id': str(chosen.pk),
            'contract_number': chosen.contract_number,
            'status': chosen.status,
            'start_date': chosen.start_date.isoformat() if chosen.start_date else None,
            'end_date': chosen.end_date.isoformat() if chosen.end_date else None,
            'term_months': term_months(chosen.start_date, chosen.end_date),
            'value': float(chosen.value or 0),
            'currency': chosen.currency,
            'signed_date': chosen.signed_date.isoformat() if chosen.signed_date else None,
            'sent_date': chosen.sent_date.isoformat() if chosen.sent_date else None,
            'invoice_state': result.successor.invoice_state,
            'link': result.successor.link,
            'gap_days': ev.gap,
            'other_company': chosen.company_id != contract.company_id,
        }

    facts_by_key = {f.key: f for f in ev.facts}
    shown_product, product_source = product_display(
        row['product'], [loc.platform for loc in contract.service_locations.all()])
    row.update({
        'book': book,
        'product_display': shown_product,
        'product_source': product_source,
        'property_name': contract.property_name or '',
        'contract_type': contract.contract_type,
        'start_date': contract.start_date.isoformat() if contract.start_date else None,
        'term_months': months,
        'entity': _entity_key(contract),
        'owner': owner,
        'owner_source': owner_source,
        'days_from_end': ev.days,
        'is_addon': ev.is_addon,
        'never_activated': ev.never_activated,
        'term_2025_placeholder': ev.term_2025,
        'renewal': {
            'state': result.state,
            'label': result.label,
            'group': result.group,
            'summary_bucket': ev.bucket,
            'in_rate': ev.in_rate,
            'reason': result.reason,
            'attention': ev.attention,
            'attention_label': ATTENTION_LABEL.get(ev.attention),
            'successor': successor_block,
            'other_linked': [
                {
                    'contract_id': str(s.pk),
                    'contract_number': s.contract_number,
                    'status': s.status,
                    'lifecycle_type': s.lifecycle_type or '',
                    'link': facts_by_key[str(s.pk)].link,
                    'link_label': LINK_LABEL[facts_by_key[str(s.pk)].link],
                }
                for s in ev.successors if chosen is None or s.pk != chosen.pk
            ],
            'live_unlinked': [
                {
                    'contract_id': str(c.pk),
                    'contract_number': c.contract_number,
                    'status': c.status,
                    'start_date': c.start_date.isoformat() if c.start_date else None,
                }
                for c in ev.live_candidates
            ] if result.state == LIVE_UNLINKED else [],
            'value_change': change,
        },
    })
    return row


def _sort_key(row):
    attention = row['renewal']['attention']
    return (0 if attention else 1, row['end_date'] or '9999', row['company'].lower(), row['contract_number'])


STRIP_BUCKETS = ('open', 'renewed', 'auto', 'unlinked', 'lost', 'history')


def _strip(year, basis, entity, today):
    """Counts per month of ``year`` from a light pass (no book rows built)."""
    start, _ = month_window(year, 1, basis)
    _, end = month_window(year, 12, basis)
    contracts = list(_in_window(_entity_filter(_strip_queryset(), entity), start, end))
    r3_ids = _r3_placeholder_ids(c.pk for c in contracts)
    company_live = _company_live_contracts(c.company_id for c in contracts)
    months = {m: {'year': year, 'month': m, 'label': date(year, m, 1).strftime('%b %Y'), 'count': 0,
                  'attention': 0, 'placeholders': 0, **{b: 0 for b in STRIP_BUCKETS}}
              for m in range(1, 13)}
    for c in contracts:
        y, m = month_of(c.end_date, basis)
        if y != year:
            continue
        ev = _evaluate(c, today, r3_ids, company_live)
        cell = months[m]
        if ev.result.state == PLACEHOLDER:
            cell['placeholders'] += 1
            continue
        cell['count'] += 1
        cell['attention'] += 1 if ev.attention else 0
        if ev.bucket in STRIP_BUCKETS:
            cell[ev.bucket] += 1
    return [months[m] for m in range(1, 13)]


def build_renewals_view(*, year, month=None, view='month', entity='', basis='funnel', today=None):
    """The data behind /renewals. Raises ValueError on bad parameters.

    ``view='month'`` returns every non-Draft term of the month's tab: by the
    funnel convention (default) the terms ending from the last day of the
    previous month to the day before the month's last day; by ``calendar``
    the terms ending in the calendar month.
    ``view='open'`` returns, across today's month - 12 to + 6, every term whose
    renewal is still open or that needs attention.
    Both include closed placeholders, marked (the page hides them unless
    asked), and return the 12-month strip for ``year``.
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
    basis = basis or 'funnel'
    if basis not in BASES:
        raise ValueError("basis must be 'funnel' or 'calendar'")
    if view == 'month':
        month = int(month)
        if not 1 <= month <= 12:
            raise ValueError('month must be 1-12')

    if view == 'month':
        start, end = month_window(year, month, basis)
    else:
        sy, sm = _shift_month(today.year, today.month, -OPEN_MONTHS_BACK)
        ey, em = _shift_month(today.year, today.month, OPEN_MONTHS_AHEAD)
        start, end = month_window(sy, sm, basis)[0], month_window(ey, em, basis)[1]
    contracts = list(_in_window(_entity_filter(_rows_queryset(), entity), start, end))
    r3_ids = _r3_placeholder_ids(c.pk for c in contracts)
    company_live = _company_live_contracts(c.company_id for c in contracts)
    rows = [renewals_row(c, today, r3_ids, company_live) for c in contracts]
    if view == 'open':
        rows = [r for r in rows if r['renewal']['state'] == PLACEHOLDER
                or r['renewal']['group'] == 'open' or r['renewal']['attention']]
    rows.sort(key=_sort_key)

    return {
        'as_of': today.isoformat(),
        'view': view,
        'basis': basis,
        'year': year,
        'month': month if view == 'month' else None,
        'month_label': date(year, month, 1).strftime('%B %Y') if view == 'month' else None,
        'entity': entity,
        'window': {'start': start.isoformat(), 'end': end.isoformat()},
        'states': [{'key': k, 'label': label, 'group': g} for k, label, g in STATES],
        'attention_reasons': [{'key': k, 'label': label} for k, label in ATTENTION_REASONS],
        'months': _strip(year, basis, entity, today),
        'count': len(rows),
        'rows': rows,
    }
