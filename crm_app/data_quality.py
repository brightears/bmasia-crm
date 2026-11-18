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
page), and the two checks that need Python (email validation, name normalisation) read their
table once and keep the result for the request.

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
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db.models import (
    Case, CharField, Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value, When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from crm_app.models import Company, Contact, Contract, ContractServiceLocation, ContractZone, Invoice, Quote, Task

SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

# Checks that list contracts read "open" successors in these statuses.
OPEN_CONTRACT_STATUSES = ('Draft', 'Sent', 'Active')
# A task is open until it is Done or Cancelled (On Hold is paused, not finished).
OPEN_TASK_STATUSES = ('To Do', 'In Progress', 'On Hold')
# Invoices the customer has been asked to pay and has not paid.
UNPAID_INVOICE_STATUSES = ('Sent', 'Overdue')

SENT_UNSIGNED_DAYS = 30
DRAFT_STALE_DAYS = 60
ENDING_WINDOW_DAYS = 60


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
    return timezone.make_aware(datetime.combine(day, time.min))


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
    """A check whose rows are one queryset: one query to count, one per page of rows."""
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
    """A check computed in Python from one read of its table, kept for the request."""

    def build(self, ctx):
        """Return every row of the check (dicts as described in the module docstring)."""
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
        if filters and filters.owner_id and filters.owner_id != 'none':
            rows = []  # these records have no owner
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


def latest_renewal(field_name):
    renewals = Contract.objects.filter(renewed_from=OuterRef('pk')).order_by('-start_date', '-created_at')
    return Subquery(renewals.values(field_name)[:1])


def renewal_note(c):
    if getattr(c, 'renewal_number', None):
        return f'renewal {c.renewal_number} is {c.renewal_status}'
    return 'no renewal recorded'


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

    def queryset(self, ctx):
        return (Contract.objects.filter(status='Active', end_date__lt=ctx.today, auto_renew=False)
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(), renewal_number=latest_renewal('contract_number'),
                          renewal_status=latest_renewal('status'))
                .order_by('-end_date', 'contract_number'))

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

    def queryset(self, ctx):
        return (Contract.objects.filter(status='Active', end_date__lt=ctx.today, auto_renew=True)
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(), renewal_number=latest_renewal('contract_number'),
                          renewal_status=latest_renewal('status'))
                .order_by('-end_date', 'contract_number'))

    def describe(self, c, ctx):
        days = (ctx.today - c.end_date).days
        return contract_row(c, f'Auto-renews; end date {fmt_date(c.end_date)} passed {days_ago(days)}; '
                               f'{renewal_note(c)}', c.end_date)


class EndingWithoutSuccessor(QuerysetCheck):
    """Active contracts ending within 60 days with no successor.

    Definition: status Active, end_date from today to today + 60 days inclusive (Bangkok), and
    no successor. A successor is (a) any contract linked through renewed_from, in any status
    (a Cancelled one records a declined renewal, which is an outcome), or (b) another contract
    of the same company in Draft, Sent or Active that starts later and ends later than this
    one (or has no end date) and whose product matches. A parallel contract of the same
    company that ends at the same time or earlier (an add-on, another venue's term) is not a
    successor. Products are labelled as the renewal book does (service_type,
    then the company's contracted_product); a contract whose product cannot be told ("Other")
    matches any product, so an unlabelled draft for the same company still counts as the
    renewal. Auto-renewing contracts are included: the next term still has to be recorded and
    invoiced. Soonest first.
    """
    key = 'contract_ending_no_successor'
    title = 'Contracts ending within 60 days with no renewal'
    why = 'Nobody has started the renewal, and the customer may lapse or be invoiced late.'
    severity = 'high'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        later = (Contract.objects.filter(company_id=OuterRef('company_id'), status__in=OPEN_CONTRACT_STATUSES,
                                         start_date__gt=OuterRef('start_date'))
                 .filter(Q(end_date__isnull=True) | Q(end_date__gt=OuterRef('end_date')))
                 .exclude(pk=OuterRef('pk'))
                 .annotate(successor_product=product_case()))
        return (Contract.objects
                .filter(status='Active', end_date__gte=ctx.today,
                        end_date__lte=ctx.today + timedelta(days=ENDING_WINDOW_DAYS))
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(), product=product_case())
                .filter(~Exists(Contract.objects.filter(renewed_from=OuterRef('pk'))))
                .filter(~Exists(later.filter(Q(successor_product=OuterRef('product')) | Q(successor_product='Other'))))
                .exclude(Q(product='Other') & Exists(later))
                .order_by('end_date', 'contract_number'))

    def describe(self, c, ctx):
        days = (c.end_date - ctx.today).days
        when = 'Ends today' if days == 0 else f'Ends in {plural(days, "day")}'
        extra = '; auto-renews' if c.auto_renew else ''
        return contract_row(c, f'{when} ({fmt_date(c.end_date)}); no renewal drafted{extra}', c.end_date)


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
                .order_by('start_date', 'contract_number'))

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
                .order_by('updated_at', 'contract_number'))

    def describe(self, c, ctx):
        changed = timezone.localdate(c.updated_at)
        days = (ctx.today - changed).days
        fact = f'Last changed {days} days ago ({fmt_date(changed)})'
        if c.start_date and c.start_date < ctx.today:
            fact += f'; its term start {fmt_date(c.start_date)} has passed'
        return contract_row(c, fact, changed)


class NoServiceLocations(QuerysetCheck):
    """Active contracts with no service locations.

    Definition: status Active and no ContractServiceLocation row. Service locations are the
    authoritative record of what the customer is contracted for: they drive the contract PDF
    and the renewal book's zone count, while ContractZone links are the support team's
    Soundtrack-synced zone tracking (research/01 §8.10, renewal_book_service). The fact says
    whether zone links exist. A contract missing both is listed here only, not again under
    ``contract_no_zone_links``.
    """
    key = 'contract_no_service_locations'
    title = 'Active contracts with no service locations'
    why = 'The CRM does not know which venues and zones the customer pays for, so PDFs, renewals and zone counts are guesses.'
    severity = 'medium'
    record_type = 'contract'
    owner_field = 'owner_ref'

    def queryset(self, ctx):
        active_links = (ContractZone.objects.filter(contract=OuterRef('pk'), is_active=True)
                        .values('contract').annotate(n=Count('pk')).values('n'))
        return (Contract.objects.filter(status='Active')
                .filter(~Exists(ContractServiceLocation.objects.filter(contract=OuterRef('pk'))))
                .select_related('company', *CONTRACT_OWNER_RELATED)
                .annotate(owner_ref=contract_owner_ref(),
                          active_links=Coalesce(Subquery(active_links, output_field=IntegerField()), 0))
                .order_by('company__name', 'contract_number'))

    def describe(self, c, ctx):
        if c.active_links:
            fact = f'No service locations; {plural(c.active_links, "active zone link")}'
        else:
            fact = 'No service locations and no zone links'
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
                .order_by('company__name', 'contract_number'))

    def describe(self, c, ctx):
        return contract_row(c, f'{plural(c.locations, "service location")}; no active zone link', c.end_date)


# --- companies and contacts -------------------------------------------------------------

class CompanyWithoutEmailContact(QuerysetCheck):
    """Companies with an Active contract but no contact with an email address.

    Definition: the company has at least one contract in status Active, and none of its own
    contacts is active (Contact.is_active) with an email containing "@". Contacts of a parent
    company are not counted, because renewal, invoice and contract emails go to the company's
    own contacts.
    """
    key = 'company_no_email_contact'
    title = 'Customers with no contact email'
    why = 'Renewal notices, invoices and contracts have nobody to go to.'
    severity = 'medium'
    record_type = 'company'
    company_field = 'pk'

    def queryset(self, ctx):
        active = (Contract.objects.filter(company=OuterRef('pk'), status='Active')
                  .values('company').annotate(n=Count('pk')).values('n'))
        contacts = Contact.objects.filter(company=OuterRef('pk')).values('company').annotate(n=Count('pk')).values('n')
        return (Company.objects
                .filter(Exists(Contract.objects.filter(company=OuterRef('pk'), status='Active')))
                .filter(~Exists(Contact.objects.filter(company=OuterRef('pk'), is_active=True, email__contains='@')))
                .annotate(active_contracts=Subquery(active, output_field=IntegerField()),
                          contact_count=Coalesce(Subquery(contacts, output_field=IntegerField()), 0))
                .order_by('name'))

    def describe(self, co, ctx):
        who = 'no contacts' if not co.contact_count else f'{plural(co.contact_count, "contact")}, none active with an email'
        return row(id=co.pk, record_type='company', label=co.name, link=f'/companies/{co.pk}',
                   fact=f'{plural(co.active_contracts, "Active contract")}; {who}', company=co)


class _CompanyRef:
    """The two fields of a company a row needs, without loading the company."""
    def __init__(self, pk, name):
        self.pk, self.name = pk, name


class ContactEmailProblem(ListCheck):
    """Contacts whose email address is invalid or shared across companies.

    Definition, over active contacts with a non-blank email:
    - invalid: the stored value fails Django's EmailValidator (which also rejects spaces);
      one row per contact;
    - shared: the same address (trimmed, case-insensitive) belongs to active contacts of two
      or more corporate groups, a group being a company together with its parent. The same
      person at a parent and its venues, or at sister venues, is expected and not listed.
      One row per address, linking every company that holds it.
    Contacts have no page of their own, so rows open the company.
    """
    key = 'contact_email_problem'
    title = 'Contact emails that are invalid or shared across customers'
    why = 'Mail to a bad address never arrives, and a shared address sends one customer the documents of another.'
    severity = 'low'
    record_type = 'contact'

    def build(self, ctx):
        validate = EmailValidator()
        contacts = list(Contact.objects.filter(is_active=True).exclude(email='')
                        .values_list('id', 'name', 'email', 'company_id', 'company__name',
                                     'company__parent_company_id')
                        .order_by('company__name', 'name', 'id'))
        invalid, by_address = [], {}
        for pk, name, email, company_id, company_name, parent_id in contacts:
            try:
                validate(email)
            except ValidationError:
                invalid.append(row(id=pk, record_type='contact', label=name or email,
                                   link=f'/companies/{company_id}', company=_CompanyRef(company_id, company_name),
                                   fact=f'Email "{email}" is not a valid address')
                               | {'_company_ids': {str(company_id)}})
                continue
            by_address.setdefault(email.strip().lower(), []).append(
                (pk, name, company_id, company_name, parent_id or company_id))
        shared = []
        for address, holders in sorted(by_address.items()):
            if len({h[4] for h in holders}) < 2:
                continue
            companies = {}
            for _, _, company_id, company_name, _ in holders:
                companies.setdefault(company_id, company_name)
            first_pk, first_name, first_company, first_company_name, _ = holders[0]
            others = [(cid, cname) for cid, cname in companies.items() if cid != first_company]
            shared.append(row(
                id=first_pk, record_type='contact', label=address, link=f'/companies/{first_company}',
                company=_CompanyRef(first_company, first_company_name),
                fact=f'Same email at {plural(len(companies), "company", "companies")}: ' + ', '.join(companies.values()),
                related=[{'label': cname, 'link': f'/companies/{cid}'} for cid, cname in others],
            ) | {'_company_ids': {str(c) for c in companies}})
        return invalid + shared


# Normalised the same way as the names (NFKC splits the Thai SARA AM in จำกัด).
SUFFIX_WORDS = {unicodedata.normalize('NFKC', w).casefold() for w in (
    'co', 'company', 'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'plc', 'llc', 'llp',
    'pte', 'pvt', 'private', 'sdn', 'bhd', 'pt', 'tbk', 'jsc', 'gmbh', 'sa', 'ag', 'bv', 'nv', 'kk',
    'public', 'the', 'hotel', 'hotels', 'บริษัท', 'จำกัด', 'มหาชน',
)}


def normalise_company_name(name):
    """Lower-case letters, digits and marks only, legal-form words (and "hotel") removed at
    either end, the remaining words sorted: "The Lumen Bay Co., Ltd.", "lumen-bay" and
    "Bay Lumen Hotel" all become "bay lumen"."""
    text = unicodedata.normalize('NFKC', name or '').casefold().replace('&', ' and ')
    text = ''.join(ch if unicodedata.category(ch)[0] in 'LNM' else ' ' for ch in text)
    words = text.split()
    while words and words[0] in SUFFIX_WORDS:
        words.pop(0)
    while words and words[-1] in SUFFIX_WORDS:
        words.pop()
    return ' '.join(sorted(words))


class LookalikeCompanyNames(ListCheck):
    """Company records whose names are the same once normalised.

    Definition: two or more companies whose names are equal after Unicode normalisation,
    case folding, replacing "&" with "and", dropping punctuation, removing legal-form words
    (Co, Ltd, Limited, Inc, Pte, Sdn Bhd, PT, the Thai บริษัท / จำกัด / มหาชน, ...) and the
    word "hotel" at the start or end, and ignoring word order ("Ascott Taipei Nangang" and
    "Ascott Nangang Taipei"). Exact matching on that key only: no fuzzy comparison of every
    pair, so spelling variants are not found. One row per group, opening the oldest record
    and linking the others. Keys shorter than 3 letters are ignored.
    """
    key = 'company_lookalike_names'
    title = 'Companies that may be duplicates'
    why = 'Contracts, contacts and history split across two records, so each one looks incomplete.'
    severity = 'low'
    record_type = 'company'

    def build(self, ctx):
        groups = {}
        for pk, name, created in Company.objects.values_list('id', 'name', 'created_at').order_by('created_at', 'name'):
            key = normalise_company_name(name)
            if len(key.replace(' ', '')) >= 3:
                groups.setdefault(key, []).append((pk, name))
        rows = []
        for key, members in groups.items():
            if len(members) < 2:
                continue
            (first_pk, first_name), others = members[0], members[1:]
            rows.append(row(
                id=first_pk, record_type='company', label=first_name, link=f'/companies/{first_pk}',
                company=_CompanyRef(first_pk, first_name),
                fact=f'{plural(len(members), "record")} with the same name: ' + '; '.join(n for _, n in members),
                related=[{'label': n, 'link': f'/companies/{pk}'} for pk, n in others],
            ) | {'_company_ids': {str(pk) for pk, _ in members}})
        rows.sort(key=lambda r: r['label'].casefold())
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
                .order_by('valid_until', 'quote_number'))

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
                .order_by('due_date', 'invoice_number'))

    def describe(self, inv, ctx):
        days = (ctx.today - inv.due_date).days
        return row(id=inv.pk, record_type='invoice', label=inv.invoice_number, link=f'/invoices?open={inv.pk}',
                   fact=f'Due {fmt_date(inv.due_date)}; {plural(days, "day")} overdue', company=inv.company,
                   owner=contract_owner(inv.contract), day=inv.due_date, amount=inv.total_amount,
                   currency=inv.currency)


class TaskOverdue(QuerysetCheck):
    """Open tasks past their due date.

    Definition: status To Do, In Progress or On Hold (open: not Done and not Cancelled) and a
    due date on an earlier Bangkok calendar day than today, so a task due later today is not
    listed yet. The model has no 'Pending' status, and a Cancelled task is never overdue.
    Owner: the person the task is assigned to. Oldest due date first.
    """
    key = 'task_overdue'
    title = 'Overdue tasks'
    why = 'A promised call, email or follow-up did not happen.'
    severity = 'medium'
    record_type = 'task'
    owner_field = 'assigned_to_id'

    def queryset(self, ctx):
        return (Task.objects.filter(status__in=OPEN_TASK_STATUSES, due_date__lt=ctx.start_of_today)
                .select_related('company', 'assigned_to')
                .order_by('due_date', 'title'))

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
