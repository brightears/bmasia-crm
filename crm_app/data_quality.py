"""Read-only data-quality checks: the records that are silently wrong or about to be missed.

Each check is a small class in ``CHECKS`` with a stable ``key``, a title, one sentence on why
it matters, a severity and the kind of record it lists. Its rows are described the same way
everywhere (the Today card, the "Needs fixing" page, the CSV export and the
``data_quality_report`` command):

    {id, record_type, label, company_id, company_name, fact, owner_id, owner_name,
     date, amount, currency, link, related}

``fact`` is the sentence that triggered the row ("Ended 23 days ago (26 Oct 2026)"), ``link``
is the frontend path of the record itself, and ``related`` lists further links when one row
stands for several records (duplicate emails, lookalike company names).

Nothing here writes. Every check runs a fixed number of queries whatever the number of rows:
the ORM checks annotate instead of reading per row (one query for the count and one for a
page), and the checks that need Python (successors, email validation, name normalisation)
read their tables once and keep the result for the request. Every ordering ends in the
primary key, so paging is stable on any database and collation.

"Today" is the Bangkok calendar day (``timezone.localdate()``; ``TIME_ZONE`` is Asia/Bangkok).
Statuses follow the model's choices and the lifecycle rule in ``services/contract_lifecycle.py``:
Expired means lapsed with no successor, Renewed means a successor took over, Cancelled is a
recorded end. ``Contract.is_active`` and ``Company.is_active`` are not used: neither can be
trusted yet.

Owners: contracts, companies and invoices have no owner field. A contract's owner is taken
from its opportunity's owner, else from the creator of the quote it came from; an invoice
uses its contract's owner; companies and contacts have none. Most rows will therefore show
no owner until companies get an account manager (gap audit backlog B12).
"""
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db.models import (
    Case, CharField, Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value, When,
)
from django.db.models.functions import Coalesce, Length, Lower, Trim
from django.utils import timezone

from crm_app.models import (
    Company, Contact, Contract, ContractServiceLocation, ContractZone, Invoice, Quote, Task, start_of_local_day,
)

SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

# Statuses in which a contract can be the next term of another.
OPEN_CONTRACT_STATUSES = ('Draft', 'Sent', 'Active')
# Invoices the customer has been asked to pay and has not paid.
UNPAID_INVOICE_STATUSES = ('Sent', 'Overdue')

SENT_UNSIGNED_DAYS = 30
DRAFT_STALE_DAYS = 60
ENDING_WINDOW_DAYS = 60
# An unlinked contract can be the renewal of one that ends on day E only if it starts between
# E - 90 days and E + 60 days (see EndingWithoutSuccessor).
SUCCESSOR_START_BEFORE_END_DAYS = 90
SUCCESSOR_START_AFTER_END_DAYS = 60
# Contracts that are never the next term of a subscription.
ONE_OFF_SERVICE_TYPES = ('one_time_setup', 'consulting', 'maintenance')
ONE_OFF_LIFECYCLE_TYPES = ('addon', 'churn')
ONE_OFF_BILLING = ('one-time', 'one time', 'onetime', 'once')

_email_validator = EmailValidator()
# Addresses that match this pattern and are at most 64 characters long always pass Django's
# EmailValidator (dot-atom local part; domain labels of letters, digits and inner hyphens; a
# letter-only top-level domain of 2+ letters; within 64 characters no label can exceed 63). The
# database sets those aside and Python validates only the rest. The pattern has no bounded
# repeats such as {0,61}: those make PostgreSQL's regex engine about 15 times slower. It ends
# in \Z, which both engines read as the very end (Python's $ also accepts a final newline).
_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
CERTAINLY_VALID_EMAIL = (rf'^{_ATOM}(\.{_ATOM})*@([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+'
                         r'[A-Za-z][A-Za-z]+\Z')
CERTAINLY_VALID_MAX_LENGTH = 64


def certainly_valid_email(prefix=''):
    """A filter for emails the database can vouch for (see CERTAINLY_VALID_EMAIL)."""
    return Q(**{f'{prefix}email__regex': CERTAINLY_VALID_EMAIL}) & Q(**{f'{prefix}email_length__lte': CERTAINLY_VALID_MAX_LENGTH})


# --- small helpers -----------------------------------------------------------------------

def fmt_date(value):
    """'14 Nov 2026', the app's display format."""
    if value is None:
        return ''
    return f'{value.day} {value:%b %Y}'


def plural(n, word, many=None):
    return f'{n} {word}' if n == 1 else f'{n} {many or word + "s"}'


def days_ago(n):
    if n == 0:
        return 'today'
    if n == 1:
        return 'yesterday'
    return f'{n} days ago'


def start_of_day(day):
    """The first instant of a Bangkok calendar day, as an aware datetime."""
    return start_of_local_day(day)


def is_valid_email(value):
    """Django's EmailValidator on the stored value (spaces included make it invalid)."""
    try:
        _email_validator(value)
    except ValidationError:
        return False
    return True


def user_name(user):
    if user is None:
        return None
    return user.get_full_name() or user.username


@dataclass
class Context:
    """What every check needs to know about "now". Built once per request or command run."""
    today: date = None
    cache: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.today is None:
            self.today = timezone.localdate()

    @property
    def start_of_today(self):
        return start_of_day(self.today)


@dataclass
class Filters:
    company_id: str = None
    owner_id: str = None  # a user id, or 'none' for rows without an owner


def product_case():
    """The contract's product as the renewal book labels it (renewal_book_service._product_of):
    from service_type first, then the company's funnel-sourced contracted_product."""
    return Case(
        When(Q(service_type__icontains='beat') | Q(service_type__iexact='lim'), then=Value('Beat Breeze')),
        When(Q(service_type__icontains='sound') | Q(service_type__icontains='syb'), then=Value('Soundtrack')),
        When(company__contracted_product__iexact='beatbreeze', then=Value('Beat Breeze')),
        When(company__contracted_product__iexact='soundtrack', then=Value('Soundtrack')),
        default=Value('Other'),
        output_field=CharField(),
    )


def product_of(service_type, contracted_product):
    """product_case() in Python, for rows already read."""
    st = (service_type or '').strip().lower()
    if 'beat' in st or st == 'lim':
        return 'Beat Breeze'
    if 'sound' in st or 'syb' in st:
        return 'Soundtrack'
    return {'beatbreeze': 'Beat Breeze', 'soundtrack': 'Soundtrack'}.get((contracted_product or '').lower(), 'Other')


def contract_owner_ref(prefix=''):
    """Owner id of a contract: its opportunity's owner, else the creator of its quote."""
    return Coalesce(F(f'{prefix}opportunity__owner_id'), F(f'{prefix}quote__created_by_id'))


def contract_owner(contract):
    if contract is None:
        return None
    if contract.opportunity_id and contract.opportunity.owner_id:
        return contract.opportunity.owner
    if contract.quote_id and contract.quote.created_by_id:
        return contract.quote.created_by
    return None


CONTRACT_OWNER_RELATED = ('opportunity__owner', 'quote__created_by')


# --- the check base classes -------------------------------------------------------------

class Check:
    key = ''
    title = ''
    why = ''
    severity = 'medium'
    record_type = ''

    def meta(self):
        return {'key': self.key, 'title': self.title, 'why': self.why,
                'severity': self.severity, 'record_type': self.record_type}

    def count(self, ctx, filters=None):
        raise NotImplementedError

    def rows(self, ctx, filters=None, offset=0, limit=None):
        raise NotImplementedError


class QuerysetCheck(Check):
    """A check whose rows are one queryset: one query to count, one per page of rows.
    ``queryset`` must order by fields ending in ``pk``."""
    company_field = 'company_id'
    owner_field = None  # an annotation or field holding the owner's user id

    def queryset(self, ctx):
        raise NotImplementedError

    def describe(self, obj, ctx):
        raise NotImplementedError

    def filtered(self, ctx, filters):
        qs = self.queryset(ctx)
        if filters and filters.company_id:
            qs = qs.filter(**{self.company_field: filters.company_id})
        if filters and filters.owner_id:
            if self.owner_field is None:
                return qs.none() if filters.owner_id != 'none' else qs
            if filters.owner_id == 'none':
                qs = qs.filter(**{f'{self.owner_field}__isnull': True})
            else:
                qs = qs.filter(**{self.owner_field: filters.owner_id})
        return qs

    def count(self, ctx, filters=None):
        return self.filtered(ctx, filters).count()

    def rows(self, ctx, filters=None, offset=0, limit=None):
        qs = self.filtered(ctx, filters)
        qs = qs[offset:offset + limit] if limit is not None else qs[offset:]
        return [self.describe(obj, ctx) for obj in qs]


class ListCheck(Check):
    """A check computed in Python from a fixed number of reads, kept for the request.
    ``build`` returns rows in their final, deterministic order, each with ``_company_ids``."""

    def build(self, ctx):
        raise NotImplementedError

    def all_rows(self, ctx):
        cache_key = ('rows', self.key)
        if cache_key not in ctx.cache:
            ctx.cache[cache_key] = self.build(ctx)
        return ctx.cache[cache_key]

    def filtered(self, ctx, filters):
        rows = self.all_rows(ctx)
        if filters and filters.company_id:
            wanted = str(filters.company_id)
            rows = [r for r in rows if wanted in r['_company_ids']]
        if filters and filters.owner_id:
            wanted = None if filters.owner_id == 'none' else str(filters.owner_id)
            rows = [r for r in rows if r['owner_id'] == wanted]
        return rows

    def count(self, ctx, filters=None):
        return len(self.filtered(ctx, filters))

    def rows(self, ctx, filters=None, offset=0, limit=None):
        rows = self.filtered(ctx, filters)
        rows = rows[offset:offset + limit] if limit is not None else rows[offset:]
        return [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]


def row(*, id, record_type, label, link, fact, company=None, owner=None, day=None,
        amount=None, currency=None, related=None):
    return {
        'id': str(id),
        'record_type': record_type,
        'label': label,
        'company_id': str(company.pk) if company is not None else None,
        'company_name': company.name if company is not None else None,
        'fact': fact,
        'owner_id': str(owner.pk) if owner is not None else None,
        'owner_name': user_name(owner),
        'date': day.isoformat() if day else None,
        'amount': str(amount) if amount is not None else None,
        'currency': currency,
        'link': link,
        'related': related or [],
    }


def contract_row(c, fact, day=None):
    return row(id=c.pk, record_type='contract', label=c.contract_number, link=f'/contracts/{c.pk}',
               fact=fact, company=c.company, owner=contract_owner(c), day=day,
               amount=c.value, currency=c.currency)


def latest_renewal(field_name, **filters):
    renewals = (Contract.objects.filter(renewed_from=OuterRef('pk'), **filters)
                .order_by('-start_date', '-created_at', '-pk'))
    return Subquery(renewals.values(field_name)[:1])


def renewal_note(c):
    if getattr(c, 'renewal_number', None):
        return f'renewal {c.renewal_number} is {c.renewal_status}'
    return 'no renewal recorded'


def ends_phrase(c, today):
    days = (c.end_date - today).days
    when = 'Ends today' if days == 0 else f'Ends in {plural(days, "day")}'
    return f'{when} ({fmt_date(c.end_date)})'


# --- contract checks --------------------------------------------------------------------

class ActivePastEnd(QuerysetCheck):
    """Active contracts whose end date has passed.

    Definition: status Active, end_date before today (Bangkok), auto_renew False. A contract
    that ends today is still running and is not listed. Auto-renewing contracts are listed by
    ``contract_auto_renew_past_end`` instead. A renewal linked through renewed_from does not
    remove the row (the old term stays Active only until its successor goes Active, when the
    lifecycle rule marks it Renewed); the fact names the renewal and its state so the reader
    can tell a renewal in progress from a term that simply lapsed. Most recently ended first.
    """
    key = 'contract_active_past_end'
    title = 'Active contracts past their end date'
    why = 'The term is over but the CRM still counts it as live, so renewals, revenue and zone status are wrong.'
    severity = 'high'
    record_type = 'contract'
    owner_field = 'owner_ref'
    auto_renew = False

    def queryset(self, ctx):
        return (Contract.objects.filter(status='Active', end_date__lt=ctx.today, auto_renew=self.auto_renew)
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(), renewal_number=latest_renewal('contract_number'),
                          renewal_status=latest_renewal('status'))
                .order_by('-end_date', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        days = (ctx.today - c.end_date).days
        return contract_row(c, f'Ended {days_ago(days)} ({fmt_date(c.end_date)}); {renewal_note(c)}', c.end_date)


class AutoRenewPastEnd(ActivePastEnd):
    """Active contracts marked auto_renew whose end date has passed.

    Definition: status Active, auto_renew True, end_date before today (Bangkok). The model
    records auto-renewal only as this flag plus renewal_period_months; nothing rolls the end
    date forward, so the term may well still be running, but no new term or end date has been
    recorded. Kept apart from ``contract_active_past_end`` so the flag is never mistaken for a
    lapse, and lower in severity.
    """
    key = 'contract_auto_renew_past_end'
    title = 'Auto-renewing contracts with an end date in the past'
    why = 'The contract renews by itself, but the CRM holds no new term or end date for it.'
    severity = 'low'
    auto_renew = True

    def describe(self, c, ctx):
        days = (ctx.today - c.end_date).days
        return contract_row(c, f'Auto-renews; end date {fmt_date(c.end_date)} passed {days_ago(days)}; '
                               f'{renewal_note(c)}', c.end_date)


class ActiveNoEndDate(QuerysetCheck):
    """Active contracts with no end date.

    Definition: status Active and end_date empty. The model allows an open-ended term, but
    nothing else in the CRM can tell when such a contract must be renewed or has lapsed: the
    past-end and ending-soon checks, the renewal book and Today all work from the end date.
    Each one must be given an end date, or confirmed as open-ended, by a person. With this
    check every Active contract is covered by a term check: an end date before today, from
    today to 60 days ahead, later, or none. Oldest start first.
    """
    key = 'contract_active_no_end_date'
    title = 'Active contracts with no end date'
    why = 'Without an end date the CRM cannot warn before the renewal or notice a lapse.'
    severity = 'low'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        return (Contract.objects.filter(status='Active', end_date__isnull=True)
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref())
                .order_by('start_date', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        return contract_row(c, f'Started {fmt_date(c.start_date)}; no end date recorded', c.start_date)


def _norm_place(value):
    return ' '.join((value or '').casefold().split())


def _property_key(value):
    """A property name compared the way company names are (case, punctuation, accents,
    legal forms and word order ignored); blank when there is none."""
    text = (value or '').strip()
    if not text:
        return ''
    return normalise_company_name(text) or _norm_place(text)


# A linked renewal in these statuses is the next term. Cancelled and Expired ones are not: in
# this business Expired means lapsed with no successor.
SUCCESSOR_LINK_STATUSES = ('Draft', 'Sent', 'Active', 'Renewed')


class EndingWithoutSuccessor(ListCheck):
    """Active contracts ending within 60 days with no successor.

    Definition: status Active, end_date from today to today + 60 days inclusive (Bangkok), and
    no successor. Auto-renewing contracts are included: the next term still has to be recorded
    and invoiced. Soonest end first.

    The row is cleared by
    (a) a contract linked through renewed_from in status Draft, Sent, Active or Renewed. A
        linked renewal that was Cancelled or has Expired does not clear the row (the contract
        is still Active and ending, so someone must decide): the fact says "renewal X was
        cancelled" or "renewal X expired"; or
    (b) an unambiguous unlinked renewal: a contract of the same company, not linked to any
        other contract, that
        - is Draft, Sent or Active, is not a one-off or add-on (service type one-time setup,
          consulting or maintenance; contract type or billing One-time; lifecycle type addon
          or churn; a term ending on or before its start), has the same product as the
          renewal book labels it ("Other" matches any) and ends after this contract's end (or
          has no end date);
        - starts on or after this contract's end date and at most 60 days after it;
        - is at the same place: the same property name, or, when neither contract has a
          property name, at least one shared zone link (zones belong to one venue);
        - has not already cleared another ending contract (a renewal renews one term).
    An unlinked contract that fails only the last three tests, but starts from 90 days before
    the end and is not at a different property, leaves the row listed with "possible renewal:
    X (not linked)": a contract that starts while this one still runs may be an early renewal
    or a mid-term add-on with no lifecycle type; a shared location or zone name ("Lobby") or a
    property name on one side only does not prove the same venue. When both contracts have
    property names and they differ, the candidate is another venue's contract and ignored.
    Every one of these rules can only keep a row listed; a false alarm costs a glance, a
    hidden gap costs a customer.
    """
    key = 'contract_ending_no_successor'
    title = 'Contracts ending within 60 days with no renewal'
    why = 'Nobody has started the renewal, and the customer may lapse or be invoiced late.'
    severity = 'high'
    record_type = 'contract'

    def build(self, ctx):
        window = dict(status='Active', end_date__gte=ctx.today,
                      end_date__lte=ctx.today + timedelta(days=ENDING_WINDOW_DAYS))
        companies = Contract.objects.filter(**window).values('company_id')
        ending = list(
            Contract.objects.filter(**window)
            .select_related('company', *CONTRACT_OWNER_RELATED)
            .annotate(live_renewal=Exists(Contract.objects.filter(renewed_from=OuterRef('pk'),
                                                                  status__in=SUCCESSOR_LINK_STATUSES)),
                      cancelled_renewal=latest_renewal('contract_number', status='Cancelled'),
                      expired_renewal=latest_renewal('contract_number', status='Expired'))
            .order_by('end_date', 'contract_number', 'pk'))
        candidates = list(
            Contract.objects.filter(company_id__in=companies, status__in=OPEN_CONTRACT_STATUSES,
                                    renewed_from__isnull=True)
            .exclude(service_type__in=ONE_OFF_SERVICE_TYPES)
            .exclude(lifecycle_type__in=ONE_OFF_LIFECYCLE_TYPES)
            .exclude(contract_type='One-time')
            .values('id', 'company_id', 'contract_number', 'start_date', 'end_date', 'service_type',
                    'billing_frequency', 'property_name', 'company__contracted_product')
            .order_by('start_date', 'contract_number', 'id'))
        # Zone links are the only place evidence that names one venue; service-location and zone
        # names ("Lobby") repeat across venues and never clear a row.
        zones = {}
        for contract_id, zone_id in (ContractZone.objects.filter(contract__company_id__in=companies)
                                     .values_list('contract_id', 'zone_id')):
            zones.setdefault(contract_id, set()).add(zone_id)
        by_company = {}
        for c in candidates:
            c['property'] = _property_key(c['property_name'])
            by_company.setdefault(c['company_id'], []).append(c)

        used, rows = set(), []
        for e in ending:
            if e.live_renewal:
                continue
            product = product_of(e.service_type, e.company.contracted_product)
            my_property = _property_key(e.property_name)
            possible, cleared = [], False
            for c in by_company.get(e.company_id, ()):
                if c['id'] == e.pk or not self._could_follow(e, c, product):
                    continue
                if my_property and c['property'] and my_property != c['property']:
                    continue  # another venue's contract
                if c['id'] not in used and self._unambiguous(e, c, my_property, zones):
                    used.add(c['id'])
                    cleared = True
                    break
                possible.append(c['contract_number'])
            if cleared:
                continue
            notes = []
            if e.cancelled_renewal:
                notes.append(f'renewal {e.cancelled_renewal} was cancelled')
            if e.expired_renewal:
                notes.append(f'renewal {e.expired_renewal} expired')
            if possible:
                notes.append(f'possible renewal: {", ".join(possible)} (not linked)')
            if not notes:
                notes.append('no renewal drafted')
            if e.auto_renew:
                notes.append('auto-renews')
            rows.append(contract_row(e, f'{ends_phrase(e, ctx.today)}; {"; ".join(notes)}', e.end_date)
                        | {'_company_ids': {str(e.company_id)}})
        return rows

    @staticmethod
    def _could_follow(e, c, product):
        """Could c be e's next term at all? (Window from 90 days before the end.)"""
        start, end = c['start_date'], c['end_date']
        if not (e.end_date - timedelta(days=SUCCESSOR_START_BEFORE_END_DAYS) <= start
                <= e.end_date + timedelta(days=SUCCESSOR_START_AFTER_END_DAYS)):
            return False
        if start <= e.start_date:
            return False
        if end is not None and (end <= e.end_date or end <= start):
            return False
        if (c['billing_frequency'] or '').strip().lower() in ONE_OFF_BILLING:
            return False
        theirs = product_of(c['service_type'], c['company__contracted_product'])
        return theirs == product or 'Other' in (theirs, product)

    @staticmethod
    def _unambiguous(e, c, my_property, zones):
        """Is c certainly e's renewal? Starts on or after e's end, at the same property, or
        with no property on either side and a shared zone link."""
        if c['start_date'] < e.end_date:
            return False
        if my_property or c['property']:
            return my_property == c['property']
        return bool(zones.get(e.pk, set()) & zones.get(c['id'], set()))


class SentNotSigned(QuerysetCheck):
    """Sent contracts whose term started more than 30 days ago.

    Definition: status Sent and start_date earlier than today minus 30 days (Bangkok), so a
    term that started exactly 30 days ago is not listed yet. The start date is used, not the
    sent date, because a contract sent well ahead of its term is not late; the fact shows the
    sent date when one is recorded. Oldest start first.
    """
    key = 'contract_sent_unsigned'
    title = 'Sent contracts not signed 30 days into the term'
    why = 'The customer is being served on a contract that was never signed or never marked Active.'
    severity = 'medium'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        return (Contract.objects
                .filter(status='Sent', start_date__lt=ctx.today - timedelta(days=SENT_UNSIGNED_DAYS))
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref())
                .order_by('start_date', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        days = (ctx.today - c.start_date).days
        sent = f'sent {fmt_date(c.sent_date)}' if c.sent_date else 'no sent date recorded'
        return contract_row(c, f'Term started {days} days ago ({fmt_date(c.start_date)}); {sent}; not signed',
                            c.start_date)


class StaleDraft(QuerysetCheck):
    """Draft contracts nobody has changed for more than 60 days.

    Definition: status Draft and the last change (updated_at, read as a Bangkok calendar day)
    more than 60 days before today; a draft last changed exactly 60 days ago is not listed. The
    last change is used rather than the creation date because a draft being worked on is not
    stale; note that any save, including a bulk correction, counts as a change. The fact also
    says when the draft's term start has already passed. Least recently changed first.
    """
    key = 'contract_draft_stale'
    title = 'Draft contracts untouched for more than 60 days'
    why = 'Old drafts hide whether a renewal is really in progress and clutter the renewal book.'
    severity = 'low'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        cutoff = start_of_day(ctx.today - timedelta(days=DRAFT_STALE_DAYS))
        return (Contract.objects.filter(status='Draft', updated_at__lt=cutoff)
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref())
                .order_by('updated_at', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        changed = timezone.localdate(c.updated_at)
        days = (ctx.today - changed).days
        fact = f'Last changed {days} days ago ({fmt_date(changed)})'
        if c.start_date and c.start_date < ctx.today:
            fact += f'; its term start {fmt_date(c.start_date)} has passed'
        return contract_row(c, fact, changed)


class NoServiceLocations(QuerysetCheck):
    """Active contracts with no service locations.

    Definition: status Active and no ContractServiceLocation row. Service-location rows are
    where the CRM records each venue's product and per-zone price, and where the renewal book
    counts zones. Without them:
    - the renewal book takes the zone count from the company's funnel-sourced
      contracted_zone_count, one figure for all of the company's contracts;
    - the contract PDF falls back to the contract's zone links (views.py
      ``_build_zones_table`` and the zone-count clauses), so a contract with zone links still
      prints its zones, but one with neither has no zone schedule at all.
    The fact says which case applies. A contract missing both is listed here only, not again
    under ``contract_no_zone_links``.
    """
    key = 'contract_no_service_locations'
    title = 'Active contracts with no service locations'
    why = ('Which venues and zones the customer pays for is not recorded on the contract, so the renewal '
           'book falls back to the company-wide zone count.')
    severity = 'medium'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        links = (ContractZone.objects.filter(contract=OuterRef('pk'))
                 .values('contract').annotate(n=Count('pk')).values('n'))
        return (Contract.objects.filter(status='Active')
                .filter(~Exists(ContractServiceLocation.objects.filter(contract=OuterRef('pk'))))
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(),
                          zone_links=Coalesce(Subquery(links, output_field=IntegerField()), 0))
                .order_by('company__name', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        if c.zone_links:
            fact = (f'No service locations; the PDF lists its {plural(c.zone_links, "linked zone")}, '
                    f'the renewal book uses the company-wide zone count')
        else:
            fact = 'No service locations and no zone links: the PDF has no zone schedule'
        return contract_row(c, fact, c.end_date)


class NoZoneLinks(QuerysetCheck):
    """Active contracts that have service locations but no active zone link.

    Definition: status Active, at least one ContractServiceLocation row, and no ContractZone
    link with is_active True. Contracts with no service locations at all are listed by
    ``contract_no_service_locations`` instead.
    """
    key = 'contract_no_zone_links'
    title = 'Active contracts not linked to any music zone'
    why = 'Support cannot see which zones the contract covers, and zone pages may show an older term.'
    severity = 'low'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        locations = (ContractServiceLocation.objects.filter(contract=OuterRef('pk'))
                     .values('contract').annotate(n=Count('pk')).values('n'))
        return (Contract.objects.filter(status='Active')
                .filter(Exists(ContractServiceLocation.objects.filter(contract=OuterRef('pk'))))
                .filter(~Exists(ContractZone.objects.filter(contract=OuterRef('pk'), is_active=True)))
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(),
                          locations=Subquery(locations, output_field=IntegerField()))
                .order_by('company__name', 'contract_number', 'pk'))

    def describe(self, c, ctx):
        return contract_row(c, f'{plural(c.locations, "service location")}; no active zone link', c.end_date)


# --- companies and contacts -------------------------------------------------------------

class _CompanyRef:
    """The two fields of a company a row needs, without loading the company."""
    def __init__(self, pk, name):
        self.pk, self.name = pk, name


class CompanyWithoutEmailContact(ListCheck):
    """Companies with an Active contract but no contact with a valid email address.

    Definition: the company has at least one contract in status Active, and none of its own
    active contacts (Contact.is_active) has an email that passes the same validator as
    ``contact_email_problem`` (so "n/a@" does not count). Unsubscribed contacts still count as
    reachable: whether they want automated mail is a different question from whether the
    company can be written to. Contacts of a parent company are not counted, because renewal,
    invoice and contract emails go to the company's own contacts.
    """
    key = 'company_no_email_contact'
    title = 'Customers with no contact email'
    why = 'Renewal notices, invoices and contracts have nobody to go to.'
    severity = 'medium'
    record_type = 'company'

    def build(self, ctx):
        with_active = Contract.objects.filter(status='Active').values('company_id')
        # Companies with an active contact whose email the database can vouch for are reachable;
        # only the others are read, and their contacts' emails validated in Python.
        vouched = (Contact.objects.filter(company=OuterRef('pk'), is_active=True)
                   .annotate(email_length=Length('email')).filter(certainly_valid_email()))
        suspects = Company.objects.filter(pk__in=with_active).filter(~Exists(vouched))
        active = (Contract.objects.filter(company=OuterRef('pk'), status='Active')
                  .values('company').annotate(n=Count('pk')).values('n'))
        contacts = Contact.objects.filter(company=OuterRef('pk')).values('company').annotate(n=Count('pk')).values('n')
        companies = list(suspects
                         .annotate(active_contracts=Subquery(active, output_field=IntegerField()),
                                   contact_count=Coalesce(Subquery(contacts, output_field=IntegerField()), 0))
                         .values_list('pk', 'name', 'active_contracts', 'contact_count')
                         .order_by('name', 'pk'))
        reachable = {company_id for company_id, email in
                     Contact.objects.filter(company__in=suspects, is_active=True).exclude(email='')
                     .values_list('company_id', 'email').order_by() if is_valid_email(email)}
        rows = []
        for pk, name, active_contracts, contact_count in companies:
            if pk in reachable:
                continue
            who = ('no contacts' if not contact_count
                   else f'{plural(contact_count, "contact")}, none active with a valid email')
            rows.append(row(id=pk, record_type='company', label=name, link=f'/companies/{pk}',
                            fact=f'{plural(active_contracts, "Active contract")}; {who}',
                            company=_CompanyRef(pk, name)) | {'_company_ids': {str(pk)}})
        return rows


def corporate_root(company_id, parents):
    """The top of a company's parent chain. A cycle in the chain is cut at its smallest id, so
    every member of the cycle gets the same root."""
    seen, current = [], company_id
    while current is not None and current not in seen:
        seen.append(current)
        current = parents.get(current)
    if current is None:
        return seen[-1]
    cycle = seen[seen.index(current):]
    return min(cycle, key=str)


class ContactEmailProblem(ListCheck):
    """Contacts whose email address is invalid or shared across companies.

    Definition, over active contacts with a non-blank email:
    - invalid: the stored value fails Django's EmailValidator (which also rejects spaces, so
      "gm@example.com " is listed); one row per contact. The database sets aside addresses of
      a shape that always passes, and Python validates the rest;
    - shared: the same address (trimmed, case-insensitive), valid, held by active contacts of
      two or more corporate groups. A group is a company with everything above it in its
      parent chain (any depth; a cycle is cut). The same person at a head office and its
      venues, or at sister venues, is expected and not listed. One row per address, linking
      every company that holds it; the database finds addresses held by more than one company.
    Contacts have no page of their own, so rows open the company.
    """
    key = 'contact_email_problem'
    title = 'Contact emails that are invalid or shared across customers'
    why = 'Mail to a bad address never arrives, and a shared address sends one customer the documents of another.'
    severity = 'low'
    record_type = 'contact'

    def build(self, ctx):
        live = Contact.objects.filter(is_active=True).exclude(email='')
        rows = []
        for pk, name, email, company_id, company_name in (
                live.annotate(email_length=Length('email')).exclude(certainly_valid_email())
                .values_list('id', 'name', 'email', 'company_id', 'company__name')
                .order_by('company__name', 'name', 'id')):
            if not is_valid_email(email):
                rows.append(row(id=pk, record_type='contact', label=name or email, link=f'/companies/{company_id}',
                                company=_CompanyRef(company_id, company_name),
                                fact=f'Email "{email}" is not a valid address')
                            | {'_company_ids': {str(company_id)}})

        normalised = live.annotate(address=Lower(Trim('email')))
        shared_addresses = list(normalised.order_by().values('address')
                                .annotate(companies=Count('company_id', distinct=True))
                                .filter(companies__gt=1).values_list('address', flat=True))
        # [''] keeps the query (and so the query count) when no address is shared; a blank
        # address never passes validation below.
        holders = list(normalised.filter(address__in=shared_addresses or [''])
                       .values_list('id', 'email', 'address', 'company_id', 'company__name')
                       .order_by('address', 'company__name', 'company_id', 'id'))
        parents = dict(Company.objects.filter(parent_company__isnull=False).values_list('id', 'parent_company_id'))
        by_address = {}
        for pk, email, address, company_id, company_name in holders:
            if is_valid_email(email):
                by_address.setdefault(address, []).append((pk, company_id, company_name))
        for address, members in by_address.items():
            if len({corporate_root(company_id, parents) for _, company_id, _ in members}) < 2:
                continue
            companies = {}
            for _, company_id, company_name in members:
                companies.setdefault(company_id, company_name)
            first_pk, first_company, first_name = members[0]
            rows.append(row(
                id=first_pk, record_type='contact', label=address, link=f'/companies/{first_company}',
                company=_CompanyRef(first_company, first_name),
                fact=f'Same email at {plural(len(companies), "company", "companies")}: ' + ', '.join(companies.values()),
                related=[{'label': n, 'link': f'/companies/{cid}'} for cid, n in companies.items() if cid != first_company],
            ) | {'_company_ids': {str(c) for c in companies}})
        return rows


def _nfkc(word):
    return unicodedata.normalize('NFKC', word).casefold()


# Legal-form words. A run of them at the end of a name is dropped when it holds at least one
# "strong" word; "sa", "public" and "private" are dropped only inside such a run, so "Sa Ninh
# Cosmetics" and "Private Room" keep their words. At the start of a name only the forms that are
# written before the name (PT, บริษัท) or a run of two or more legal words are dropped: "KK" or
# "AG" alone at the start are usually initials ("KK Garden").
STRONG_LEGAL_WORDS = {_nfkc(w) for w in (
    'co', 'company', 'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'plc', 'llc', 'llp',
    'pte', 'pvt', 'sdn', 'bhd', 'pt', 'tbk', 'jsc', 'gmbh', 'ag', 'bv', 'nv', 'kk', 'juristic',
    'บริษัท', 'จำกัด', 'มหาชน', 'นิติบุคคล',
)}
# "Condominium Juristic Person" is the legal form of a Thai condominium; "condominium" and
# "person" alone are ordinary words.
WEAK_LEGAL_WORDS = {'sa', 'public', 'private', 'person', 'condominium'}
# Thai legal words are often written without spaces; they are split off before reading words.
THAI_LEGAL_WORDS = [_nfkc(w) for w in ('บริษัท', 'จำกัด', 'มหาชน')]
LEGAL_WORDS = STRONG_LEGAL_WORDS | WEAK_LEGAL_WORDS
LEADING_LEGAL_FORMS = {_nfkc(w) for w in ('pt', 'บริษัท')}
# A name left with only these words says nothing about which business it is.
GENERIC_WORDS = {'hotel', 'hotels', 'resort', 'resorts', 'spa', 'group', 'holdings', 'restaurant', 'cafe',
                 'bar', 'mall', 'office', 'offices', 'store', 'shop', 'club', 'thailand', 'bangkok'}
_ASCII_WORD_CHARS = frozenset('abcdefghijklmnopqrstuvwxyz0123456789')


def _keep(ch):
    """Letters, digits and combining marks are part of words; everything else separates."""
    return ch in _ASCII_WORD_CHARS or (ch > '\x7f' and unicodedata.category(ch)[0] in 'LNM')


def _strip_legal_run(words, from_end):
    seq = list(reversed(words)) if from_end else list(words)
    run = 0
    while run < len(seq) and seq[run] in LEGAL_WORDS:
        run += 1
    run_words = seq[:run]
    strong = [w for w in run_words if w in STRONG_LEGAL_WORDS]
    if from_end:
        drop = bool(strong)
    else:
        drop = bool(strong) and (run >= 2 or run_words[0] in LEADING_LEGAL_FORMS)
    if drop:
        seq = seq[run:]
    return list(reversed(seq)) if from_end else seq


def _drop_latin_accents(text):
    """'Orvélia' and 'Lönnhaven' read as 'orvelia' and 'lonnhaven'. Only marks on Latin letters go;
    Thai vowel and tone marks are part of the word and stay."""
    if text.isascii():
        return text
    out = []
    for ch in unicodedata.normalize('NFD', text):
        if unicodedata.combining(ch) and out and out[-1].isascii() and out[-1].isalpha():
            continue
        out.append(ch)
    return unicodedata.normalize('NFC', ''.join(out))


def _name_words(name):
    text = _drop_latin_accents(_nfkc(name or ''))
    if any('\u0e00' <= ch <= '\u0e7f' for ch in text):
        for word in THAI_LEGAL_WORDS:
            text = text.replace(word, f' {word} ')
    text = text.replace('&', ' and ')
    text = ''.join(ch if _keep(ch) else ' ' for ch in text)
    words = text.split()
    if words and words[0] == 'the':
        words = words[1:]
    words = _strip_legal_run(words, from_end=False)
    if words and words[0] == 'the':
        words = words[1:]
    words = _strip_legal_run(words, from_end=True)
    # "& Spa" after a resort or hotel adds nothing: "X Resort & Spa" = "X Resort Spa" = "X Resort".
    words = [w for i, w in enumerate(words)
             if not (w == 'spa' and i > 0 and words[i - 1] in ('resort', 'hotel', 'and'))]
    # "and" and "the" are dropped anywhere ("Mall of the X" = "Mall of X"). "Hotel" is kept: word
    # order is ignored, so "Hotel X" = "X Hotel", but "X Hotel" (a property) does not match the
    # bare brand "X", and a group "X Hotels" does not match its property "Hotel X".
    return [w for w in words if w not in ('and', 'the')]


def company_name_keys(name):
    """The two exact keys a company name is compared on: its words sorted (word order ignored)
    and its words joined without spaces (spacing ignored, e.g. Thai names). Empty when the
    name has fewer than 3 letters or digits left, or only generic words ("The Hotel")."""
    words = _name_words(name)
    joined = ''.join(words)
    if len(joined) < 3 or all(w in GENERIC_WORDS for w in words):
        return ()
    return (' '.join(sorted(words)), joined)


def normalise_company_name(name):
    """The word-order-free key of a company name (see company_name_keys)."""
    keys = company_name_keys(name)
    return keys[0] if keys else ''


def names_look_alike(a, b):
    return bool(set(company_name_keys(a)) & set(company_name_keys(b)))


class LookalikeCompanyNames(ListCheck):
    """Company records whose names are the same once normalised.

    Definition: two or more companies that share a name key (company_name_keys). Names are
    compared after Unicode normalisation and case folding, with accents on Latin letters
    removed ("Orvélia" = "Orvelia"), "&" read as "and", punctuation dropped, a run of
    legal-form words at the end (Co, Ltd, Pte, Sdn Bhd, Tbk, Public Company Limited,
    Condominium Juristic Person, the Thai จำกัด / มหาชน, also written without spaces), the
    forms written before a name (PT, บริษัท) or a run of two legal words at the start, and
    "& Spa" after a resort or hotel removed, and "and" and "the" dropped anywhere. "Hotel" is
    kept, so "X Hotel" and "X" are not grouped (but "Hotel X" and "X Hotel" are). "X Resort &
    Spa" and "X Resort" are grouped on purpose: a hotel and its "hotel & spa" are usually one
    customer. Names left with only generic words ("The Hotel") get no key. Two keys are used: the words in sorted order ("Bay
    Lumen Phuket" = "Lumen Bay Phuket") and the words joined without spaces ("Lumen Bay" =
    "LumenBay"). Exact keys only: no fuzzy comparison of every pair, so spelling variants are
    not found. One row per group, opening the oldest record and linking the others.
    """
    key = 'company_lookalike_names'
    title = 'Companies that may be duplicates'
    why = 'Contracts, contacts and history split across two records, so each one looks incomplete.'
    severity = 'low'
    record_type = 'company'

    def build(self, ctx):
        companies = list(Company.objects.values_list('id', 'name').order_by('created_at', 'id'))
        parent = list(range(len(companies)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        first_with_key = {}
        for i, (_, name) in enumerate(companies):
            for key in company_name_keys(name):
                if key in first_with_key:
                    a, b = find(first_with_key[key]), find(i)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
                else:
                    first_with_key[key] = i
        groups = {}
        for i in range(len(companies)):
            groups.setdefault(find(i), []).append(companies[i])
        rows = []
        for members in groups.values():
            if len(members) < 2:
                continue
            (first_pk, first_name), others = members[0], members[1:]
            rows.append(row(
                id=first_pk, record_type='company', label=first_name, link=f'/companies/{first_pk}',
                company=_CompanyRef(first_pk, first_name),
                fact=f'{plural(len(members), "record")} with the same name: ' + '; '.join(n for _, n in members),
                related=[{'label': n, 'link': f'/companies/{pk}'} for pk, n in others],
            ) | {'_company_ids': {str(pk) for pk, _ in members}})
        rows.sort(key=lambda r: (r['label'].casefold(), r['id']))
        return rows


# --- quotes, invoices, tasks ------------------------------------------------------------

class QuoteSentExpired(QuerysetCheck):
    """Sent quotes past their valid-until date with no decision.

    Definition: status Sent, valid_until before today (Bangkok), and no contract created from
    the quote (Contract.quote). A quote that became a contract has its answer even if nobody
    marked it Accepted. Oldest expiry first. Owner: whoever created the quote, else the
    opportunity's owner.
    """
    key = 'quote_sent_expired'
    title = 'Sent quotes that expired without an answer'
    why = 'The customer was never chased, or the outcome was never recorded.'
    severity = 'medium'
    record_type = 'quote'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        return (Quote.objects.filter(status='Sent', valid_until__lt=ctx.today)
                .filter(~Exists(Contract.objects.filter(quote=OuterRef('pk'))))
                .select_related('company', 'created_by', 'opportunity__owner')
                .annotate(owner_ref=Coalesce(F('created_by_id'), F('opportunity__owner_id')))
                .order_by('valid_until', 'quote_number', 'pk'))

    def describe(self, q, ctx):
        days = (ctx.today - q.valid_until).days
        owner = q.created_by or (q.opportunity.owner if q.opportunity_id else None)
        return row(id=q.pk, record_type='quote', label=q.quote_number, link=f'/quotes/{q.pk}',
                   fact=f'Valid until {fmt_date(q.valid_until)} ({days_ago(days)}); still Sent',
                   company=q.company, owner=owner, day=q.valid_until, amount=q.total_value, currency=q.currency)


class InvoiceOverdue(QuerysetCheck):
    """Invoices that are overdue.

    Definition: status Sent or Overdue and due_date before today (Bangkok). This is the
    model's own rule (Invoice.days_overdue: unpaid and past due) limited to invoices actually
    issued and still open: a Draft was never sent, and Paid, Cancelled or Refunded ones are
    settled. Real invoicing runs in QuickBooks, so this list is near-empty. Owner: the
    contract's owner.
    """
    key = 'invoice_overdue'
    title = 'Overdue invoices'
    why = 'Money that should have arrived has not, and nobody may be chasing it.'
    severity = 'high'
    record_type = 'invoice'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        return (Invoice.objects.filter(status__in=UNPAID_INVOICE_STATUSES, due_date__lt=ctx.today)
                .select_related('company', 'contract__opportunity__owner', 'contract__quote__created_by')
                .annotate(owner_ref=contract_owner_ref('contract__'))
                .order_by('due_date', 'invoice_number', 'pk'))

    def describe(self, inv, ctx):
        days = (ctx.today - inv.due_date).days
        return row(id=inv.pk, record_type='invoice', label=inv.invoice_number, link=f'/invoices?open={inv.pk}',
                   fact=f'Due {fmt_date(inv.due_date)}; {plural(days, "day")} overdue', company=inv.company,
                   owner=contract_owner(inv.contract), day=inv.due_date, amount=inv.total_amount,
                   currency=inv.currency)


class TaskOverdue(QuerysetCheck):
    """Open tasks past their due date.

    Definition: the shared rule in crm_app.models (TaskQuerySet.overdue, also behind
    Task.is_overdue, Today and the company dashboard): status To Do, In Progress or On Hold
    (open: not Done and not Cancelled) and a due date on an earlier Bangkok calendar day than
    today, so a task due later today is not listed yet. Owner: the person the task is assigned
    to. Oldest due date first.
    """
    key = 'task_overdue'
    title = 'Overdue tasks'
    why = 'A promised call, email or follow-up did not happen.'
    severity = 'medium'
    record_type = 'task'
    owner_field = 'assigned_to_id'

    def queryset(self, ctx):
        return (Task.objects.overdue(ctx.today)
                .select_related('company', 'assigned_to')
                .order_by('due_date', 'title', 'pk'))

    def describe(self, t, ctx):
        due = timezone.localdate(t.due_date)
        days = (ctx.today - due).days
        status = '' if t.status == 'To Do' else f'; {t.status}'
        return row(id=t.pk, record_type='task', label=t.title, link=f'/tasks/{t.pk}',
                   fact=f'Due {fmt_date(due)} ({days_ago(days)}){status}', company=t.company,
                   owner=t.assigned_to, day=due)


CHECKS = [
    ActivePastEnd(),
    EndingWithoutSuccessor(),
    InvoiceOverdue(),
    SentNotSigned(),
    NoServiceLocations(),
    CompanyWithoutEmailContact(),
    QuoteSentExpired(),
    TaskOverdue(),
    StaleDraft(),
    NoZoneLinks(),
    AutoRenewPastEnd(),
    ActiveNoEndDate(),
    ContactEmailProblem(),
    LookalikeCompanyNames(),
]
CHECKS_BY_KEY = {c.key: c for c in CHECKS}


def summary(ctx=None, filters=None, rows_per_check=5):
    """Every check with its count and first rows, ordered by severity, then count (largest
    first), then the registry order."""
    ctx = ctx or Context()
    result = []
    for position, check in enumerate(CHECKS):
        count = check.count(ctx, filters)
        # Rows are read even when the count is 0, so the number of queries never depends on the data.
        rows = check.rows(ctx, filters, 0, rows_per_check) if rows_per_check else []
        result.append(check.meta() | {'count': count, 'rows': rows, '_position': position})
    result.sort(key=lambda c: (SEVERITY_ORDER[c['severity']], -c['count'], c['_position']))
    for item in result:
        item.pop('_position')
    return result
