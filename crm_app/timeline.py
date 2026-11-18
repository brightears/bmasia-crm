"""One read-only timeline per company: every recorded interaction, newest first.

``GET /api/v1/companies/<id>/timeline/`` merges events from many tables (notes,
tasks, CRM email, client-care touches, quotes, contracts, invoices,
opportunities, tickets and the audit log) into one typed, paged list. Nothing
here writes, sends or calls out.

How it works
------------
* Every source is an adapter registered in ``registry``. A source answers two
  questions for one company and one set of filters: "give me your newest
  ``limit`` events older than this cursor" (``fetch``) and "how many events do
  you have, per actor" (``facet_rows``). Each is **one query**, so a page costs
  a fixed number of queries however much history a company has.
* The merge step (``build_page``) never needs to know what a source is. It asks
  every active source for one page, sorts by ``(occurred_at, id)`` descending
  and cuts the page at the oldest point every source has fully covered.
* Ties: two events at the same instant are ordered by their id
  (``"<source key>:<pk>"``). Source keys are ``[a-z_]`` words, so comparing two
  ids from different sources is decided by the keys alone, and SQL can apply the
  same rule (``pk < cursor pk`` within a source). The cursor carries the full
  ``(occurred_at, id)`` of the last event, so new events arriving between two
  page loads never shift or repeat a later page.
* Some lifecycle facts are stored as dates without a time (``Contract.sent_date``,
  ``Invoice.paid_date``…). They are shown with ``precision: "date"`` and placed at
  the start of that day in the CRM's time zone; no time of day is invented.

Adding a source (for example the agent ``Activity`` log or captured mail)
--------------------------------------------------------------------------
Subclass ``RowSource`` for a Django model and register it once, typically in
the app's ``AppConfig.ready()``::

    from crm_app import timeline

    class AgentActivitySource(timeline.RowSource):
        key = 'agent_activity'          # unique, [a-z_]
        category = 'activity'           # a filter chip; add it to CATEGORIES first
        model = Activity
        time_field = 'occurred_at'
        actor_field = 'recorded_by_user'
        search_fields = ('summary',)
        record_paths = {'contact': 'contact', 'contract': 'contract'}

        def to_event(self, row, ctx):
            return self.event(row, ctx, type='activity_' + row.kind, title=row.summary, ...)

    timeline.registry.register(AgentActivitySource())

Captured mail should also make ``EmailLogSource`` skip CRM email that the
capture already holds (same ``message_id``): override ``EmailLogSource.extra_q``
with a ``~Exists(...)`` on the capture table, which keeps it one query.

Anything that is not a model can implement ``TimelineSource`` directly.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from django.db import connection
from django.db.models import CharField, Count, Exists, OuterRef, Q, TextField, Value
from django.db.models.functions import Cast, Coalesce, Replace
from django.utils import timezone

from crm_app.models import (
    AuditLog, CareTouch, Company, Contact, Contract, EmailLog, Invoice, Note, Opportunity,
    OpportunityActivity, Quote, QuoteActivity, Task, TaskComment, Ticket, TicketComment, User,
)

TITLE_MAX = 200
DETAIL_MAX = 1000
VALUE_MAX = 200
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# Filter chips, in display order. A source belongs to exactly one category.
CATEGORIES = {
    'note': 'Notes',
    'task': 'Tasks',
    'email': 'Emails',
    'care': 'Client care',
    'quote': 'Quotes',
    'contract': 'Contracts',
    'invoice': 'Invoices',
    'opportunity': 'Opportunities',
    'ticket': 'Support',
    'change': 'Field changes',
}

# Records an event can be filtered to (``record=<type>:<uuid>``) and linked to.
RECORD_TYPES = ('contract', 'quote', 'contact', 'opportunity', 'ticket', 'task', 'invoice')

_KEY_RE = re.compile(r'^[a-z][a-z_]*$')
_SECRET_KEY = re.compile(r'password|passwd|secret|token|api_?key|credential|smtp', re.IGNORECASE)


# ---------------------------------------------------------------- small helpers


def local_midnight(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_default_timezone())


def local_date(moment: datetime) -> date:
    return timezone.localtime(moment, timezone.get_default_timezone()).date()


def _cap(text: Any, limit: int) -> str:
    text = '' if text is None else str(text)
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def actor_for_user(user) -> dict | None:
    """Display name for a user or agent. Never an email address."""
    if user is None:
        return None
    from crm_app.agent_policy import principal_for_username
    principal = principal_for_username(getattr(user, 'username', ''))
    if principal is not None:
        return {'id': str(user.pk), 'name': principal.name.capitalize(), 'kind': 'agent'}
    name = (user.get_full_name() or '').strip() or (user.username or '').strip() or 'Unknown user'
    if '@' in name:
        name = name.split('@', 1)[0]
    return {'id': str(user.pk), 'name': name, 'kind': 'user'}


SYSTEM_ACTOR = {'id': None, 'name': 'CRM', 'kind': 'system'}
CARE_ACTOR = {'id': None, 'name': 'Client care', 'kind': 'agent'}


def _link(record_type: str, pk, label: str, **extra) -> dict:
    data = {'type': record_type, 'id': str(pk), 'label': _cap(label, 120)}
    data.update({k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in extra.items() if v is not None})
    return data


def _money(amount, currency) -> dict | None:
    if amount is None:
        return None
    return {'amount': str(amount), 'currency': currency or ''}


# ---------------------------------------------------------------- data shapes


@dataclass
class TimelineEvent:
    id: str
    type: str
    category: str
    occurred_at: datetime
    title: str
    precision: str = 'datetime'  # 'datetime' or 'date' (no time of day recorded)
    detail: str = ''
    actor: dict | None = None
    links: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def sort_key(self):
        return (self.occurred_at, self.id)

    def as_dict(self) -> dict:
        data = {
            'id': self.id,
            'type': self.type,
            'category': self.category,
            'occurred_at': timezone.localtime(self.occurred_at, timezone.get_default_timezone()).isoformat(),
            'precision': self.precision,
            'title': _cap(self.title, TITLE_MAX),
            'detail': _cap(self.detail, DETAIL_MAX),
            'actor': self.actor,
            'links': self.links,
            'changes': self.changes,
            'extra': self.extra,
        }
        if self.precision == 'date':
            data['date'] = local_date(self.occurred_at).isoformat()
        return data


@dataclass(frozen=True)
class Cursor:
    occurred_at: datetime
    event_id: str

    @property
    def source_key(self) -> str:
        return self.event_id.partition(':')[0]

    @property
    def source_pk(self) -> str:
        return self.event_id.partition(':')[2]

    def encode(self) -> str:
        raw = json.dumps({'t': self.occurred_at.isoformat(), 'i': self.event_id}, separators=(',', ':'))
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')

    @classmethod
    def decode(cls, token: str) -> 'Cursor':
        try:
            padded = token + '=' * (-len(token) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            moment = datetime.fromisoformat(data['t'])
            event_id = str(data['i'])
        except (ValueError, KeyError, TypeError, binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError('invalid cursor') from exc
        if timezone.is_naive(moment) or ':' not in event_id or not _KEY_RE.match(event_id.partition(':')[0]):
            raise ValueError('invalid cursor')
        return cls(moment, event_id)


@dataclass
class Filters:
    categories: frozenset | None = None  # None = every category
    date_from: date | None = None
    date_to: date | None = None
    record_type: str | None = None
    record_id: str | None = None
    actor_id: str | None = None
    search: str = ''


@dataclass
class SourceResult:
    events: list
    # Key of the oldest row this source scanned when it stopped at its limit:
    # every event of this source newer than or equal to it is in ``events``.
    # None means the source has nothing older.
    complete_until: tuple | None


class TimelineContext:
    """Per-request state shared by all sources: company, viewer, filters, label maps."""

    def __init__(self, company: Company, user, filters: Filters):
        self.company = company
        self.user = user
        self.filters = filters
        self.is_admin = getattr(user, 'role', None) == 'Admin'
        self._maps: dict[str, dict] = {}

    def _load(self, name: str, queryset, label):
        if name not in self._maps:
            self._maps[name] = {str(row['id']): label(row) for row in queryset}
        return self._maps[name]

    @property
    def contacts(self) -> dict:
        return self._load('contacts', Contact.objects.filter(company_id=self.company.pk).values('id', 'name'),
                          lambda r: r['name'])

    @property
    def contracts(self) -> dict:
        return self._load(
            'contracts',
            Contract.objects.filter(company_id=self.company.pk).values('id', 'contract_number', 'currency'),
            lambda r: {'label': r['contract_number'], 'currency': r['currency']},
        )

    @property
    def quotes(self) -> dict:
        return self._load(
            'quotes', Quote.objects.filter(company_id=self.company.pk).values('id', 'quote_number', 'currency'),
            lambda r: {'label': r['quote_number'], 'currency': r['currency']},
        )

    @property
    def opportunities(self) -> dict:
        return self._load('opportunities',
                          Opportunity.objects.filter(company_id=self.company.pk).values('id', 'name'),
                          lambda r: r['name'])


# ---------------------------------------------------------------- source protocol


class TimelineSource:
    """Anything that can contribute events. Subclass RowSource for a Django model."""

    key: str = ''
    category: str = ''
    #: Mirrors the permission of the API that already exposes this data.
    admin_only: bool = False

    def available(self, ctx: TimelineContext) -> bool:
        return ctx.is_admin or not self.admin_only

    def active(self, ctx: TimelineContext) -> bool:
        """Whether this source takes part in the current request."""
        cats = ctx.filters.categories
        return self.available(ctx) and (cats is None or self.category in cats)

    def fetch(self, ctx: TimelineContext, cursor: Cursor | None, limit: int) -> SourceResult:
        raise NotImplementedError

    def facet_rows(self, ctx: TimelineContext) -> list[tuple[str | None, int]]:
        """``[(actor user id or None, count), …]`` for every filter except type and actor."""
        raise NotImplementedError


class RowSource(TimelineSource):
    """One event per row of a model, ordered by one time column."""

    model = None
    time_field = 'created_at'
    is_date = False                 # True when time_field is a DateField
    company_path = 'company'        # lookup from the row to its company id
    actor_field: str | None = None  # user FK naming who did it, for the actor filter
    search_fields: tuple = ()
    #: record type -> lookup path (or tuple of paths, OR-ed) from the row to that record
    record_paths: dict = {}
    select_related: tuple = ()

    # -- hooks -------------------------------------------------------------

    def annotate(self, qs, ctx):
        return qs

    def extra_q(self, ctx) -> Q | None:
        return None

    def prepare(self, rows: list, ctx: TimelineContext) -> None:
        """Batch-load whatever ``to_event`` needs (at most a fixed number of queries)."""

    def to_event(self, row, ctx: TimelineContext) -> TimelineEvent | None:
        raise NotImplementedError

    # -- building blocks ---------------------------------------------------

    def occurred_at(self, row) -> datetime:
        value = getattr(row, self.time_field)
        return local_midnight(value) if self.is_date else value

    def event_id(self, row) -> str:
        return f'{self.key}:{row.pk}'

    def event(self, row, ctx, **kwargs) -> TimelineEvent:
        kwargs.setdefault('category', self.category)
        kwargs.setdefault('precision', 'date' if self.is_date else 'datetime')
        return TimelineEvent(id=self.event_id(row), occurred_at=self.occurred_at(row), **kwargs)

    def base_queryset(self, ctx):
        return self.model._default_manager.filter(**{self.company_path: ctx.company.pk})

    def _record_q(self, ctx) -> Q | None:
        f = ctx.filters
        if not f.record_type:
            return Q()
        paths = self.record_paths.get(f.record_type)
        if not paths:
            return None
        if isinstance(paths, str):
            paths = (paths,)
        q = Q()
        for path in paths:
            q |= Q(**{path: f.record_id})
        return q

    def _date_q(self, ctx) -> Q:
        f, tf, q = ctx.filters, self.time_field, Q()
        if self.is_date:
            if f.date_from:
                q &= Q(**{f'{tf}__gte': f.date_from})
            if f.date_to:
                q &= Q(**{f'{tf}__lte': f.date_to})
        else:
            if f.date_from:
                q &= Q(**{f'{tf}__gte': local_midnight(f.date_from)})
            if f.date_to:
                q &= Q(**{f'{tf}__lt': local_midnight(f.date_to + timedelta(days=1))})
        return q

    def _search_q(self, ctx) -> Q:
        term = ctx.filters.search
        if not term:
            return Q()
        q = Q(pk__in=[])
        for path in self.search_fields:
            q |= Q(**{f'{path}__icontains': term})
        return q

    def filtered(self, ctx, *, with_actor: bool = True):
        """The source's rows for this request, or None when it has nothing to say."""
        record_q = self._record_q(ctx)
        if record_q is None:
            return None
        if with_actor and ctx.filters.actor_id and not self.actor_field:
            return None
        qs = self.annotate(self.base_queryset(ctx), ctx).filter(record_q, self._date_q(ctx), self._search_q(ctx))
        extra = self.extra_q(ctx)
        if extra is not None:
            qs = qs.filter(extra)
        if with_actor and ctx.filters.actor_id:
            qs = qs.filter(**{f'{self.actor_field}_id': ctx.filters.actor_id})
        return qs

    def cursor_q(self, cursor: Cursor) -> Q:
        """Rows whose ``(occurred_at, id)`` sorts strictly before the cursor."""
        tf = self.time_field
        if self.key < cursor.source_key:
            tie = Q()            # same instant: every row of this source sorts before
        elif self.key > cursor.source_key:
            tie = None           # same instant: no row of this source sorts before
        else:
            tie = Q(pk__lt=cursor.source_pk)
        if self.is_date:
            day = local_date(cursor.occurred_at)
            q = Q(**{f'{tf}__lt': day})
            if cursor.occurred_at > local_midnight(day):
                return q | Q(**{tf: day})
            return q | (Q(**{tf: day}) & tie) if tie is not None else q
        q = Q(**{f'{tf}__lt': cursor.occurred_at})
        return q | (Q(**{tf: cursor.occurred_at}) & tie) if tie is not None else q

    def row_key(self, row) -> tuple:
        return (self.occurred_at(row), self.event_id(row))

    def fetch(self, ctx, cursor, limit):
        qs = self.filtered(ctx)
        if qs is None:
            return SourceResult([], None)
        if cursor is not None:
            qs = qs.filter(self.cursor_q(cursor))
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        rows = list(qs.order_by(f'-{self.time_field}', '-pk')[:limit])
        self.prepare(rows, ctx)
        events = [event for event in (self.to_event(row, ctx) for row in rows) if event is not None]
        complete_until = self.row_key(rows[-1]) if len(rows) >= limit else None
        return SourceResult(events, complete_until)

    def facet_rows(self, ctx):
        qs = self.filtered(ctx, with_actor=False)
        if qs is None:
            return []
        if not self.actor_field:
            return [(None, qs.count())]
        rows = qs.order_by().values(f'{self.actor_field}_id').annotate(n=Count('pk'))
        return [(str(r[f'{self.actor_field}_id']) if r[f'{self.actor_field}_id'] else None, r['n']) for r in rows]


class TimelineRegistry:
    def __init__(self):
        self._sources: dict[str, TimelineSource] = {}

    def register(self, source: TimelineSource) -> TimelineSource:
        if not _KEY_RE.match(source.key or ''):
            raise ValueError(f'timeline source key must match [a-z][a-z_]*: {source.key!r}')
        if source.key in self._sources:
            raise ValueError(f'timeline source already registered: {source.key}')
        if source.category not in CATEGORIES:
            raise ValueError(f'unknown timeline category {source.category!r}; add it to CATEGORIES')
        self._sources[source.key] = source
        return source

    def unregister(self, key: str) -> None:
        self._sources.pop(key, None)

    def sources(self) -> list[TimelineSource]:
        return list(self._sources.values())

    def get(self, key: str) -> TimelineSource | None:
        return self._sources.get(key)


registry = TimelineRegistry()


# ---------------------------------------------------------------- notes, tasks


# EmailLog.mark_as_sent also writes a Note for every email it sends; the email
# itself is on the timeline already, so that automatic note is left out.
_AUTO_EMAIL_NOTE = Q(author__isnull=True, note_type='Email', title__startswith='Email sent: ')


class NoteSource(RowSource):
    key = 'note'
    category = 'note'
    model = Note
    actor_field = 'author'
    search_fields = ('title', 'text')
    record_paths = {'contact': 'contact'}
    select_related = ('author', 'contact')

    def extra_q(self, ctx):
        q = ~_AUTO_EMAIL_NOTE
        if not ctx.is_admin:  # same rule as NoteViewSet: others' private notes stay hidden
            q &= Q(is_private=False) | Q(author_id=ctx.user.pk)
        return q

    def to_event(self, row, ctx):
        label = row.get_note_type_display()
        links = [_link('contact', row.contact_id, row.contact.name)] if row.contact_id else []
        return self.event(
            row, ctx, type='note', title=row.title or f'{label} note', detail=row.text,
            actor=actor_for_user(row.author), links=links,
            extra={'note_type': row.note_type, 'note_type_label': label, 'priority': row.priority,
                   'is_private': row.is_private},
        )


def _task_links(task) -> list:
    links = [_link('task', task.pk, task.title)]
    if task.related_contract_id:
        links.append(_link('contract', task.related_contract_id, task.related_contract.contract_number))
    if task.related_opportunity_id:
        links.append(_link('opportunity', task.related_opportunity_id, task.related_opportunity.name))
    if task.related_contact_id:
        links.append(_link('contact', task.related_contact_id, task.related_contact.name))
    return links


_TASK_RECORDS = {'task': 'pk', 'contract': 'related_contract', 'opportunity': 'related_opportunity',
                 'contact': 'related_contact'}


class TaskCreatedSource(RowSource):
    key = 'task_created'
    category = 'task'
    model = Task
    actor_field = 'created_by'
    search_fields = ('title', 'description')
    record_paths = _TASK_RECORDS
    select_related = ('created_by', 'assigned_to', 'related_contract', 'related_opportunity', 'related_contact')

    def to_event(self, row, ctx):
        assignee = actor_for_user(row.assigned_to)
        return self.event(
            row, ctx, type='task_created', title=f'Task created: {row.title}', detail=row.description,
            actor=actor_for_user(row.created_by), links=_task_links(row),
            extra={'status': row.status, 'priority': row.priority, 'task_type': row.task_type,
                   'due_date': row.due_date.isoformat() if row.due_date else None,
                   'assigned_to': assignee['name'] if assignee else None},
        )


class TaskCompletedSource(TaskCreatedSource):
    key = 'task_completed'
    time_field = 'completed_at'
    actor_field = None  # the CRM does not record who marked a task done

    def extra_q(self, ctx):
        return Q(completed_at__isnull=False)

    def to_event(self, row, ctx):
        assignee = actor_for_user(row.assigned_to)
        return self.event(
            row, ctx, type='task_completed', title=f'Task completed: {row.title}', links=_task_links(row),
            extra={'assigned_to': assignee['name'] if assignee else None},
        )


class TaskCommentSource(RowSource):
    key = 'task_comment'
    category = 'task'
    model = TaskComment
    company_path = 'task__company'
    actor_field = 'user'
    search_fields = ('comment', 'task__title')
    record_paths = {'task': 'task', 'contract': 'task__related_contract',
                    'opportunity': 'task__related_opportunity', 'contact': 'task__related_contact'}
    select_related = ('user', 'task', 'task__related_contract', 'task__related_opportunity',
                      'task__related_contact')

    def to_event(self, row, ctx):
        return self.event(
            row, ctx, type='task_comment', title=f'Comment on task: {row.task.title}', detail=row.comment,
            actor=actor_for_user(row.user), links=_task_links(row.task),
        )


# ---------------------------------------------------------------- email, care


class EmailLogSource(RowSource):
    """Email the CRM sent (or tried to send). Bodies are never exposed."""

    key = 'email'
    category = 'email'
    model = EmailLog
    time_field = 'event_time'
    search_fields = ('subject', 'to_email', 'contact__name')
    record_paths = {'contact': 'contact', 'contract': 'contract', 'quote': 'quote', 'invoice': 'invoice'}
    select_related = ('contact', 'contract', 'quote', 'invoice')

    def annotate(self, qs, ctx):
        return qs.annotate(event_time=Coalesce('sent_at', 'created_at'))

    def to_event(self, row, ctx):
        failed = row.status in ('failed', 'bounced')
        pending = row.status == 'pending'
        prefix = 'Email failed' if failed else 'Email queued' if pending else 'Email sent'
        recipient = row.contact.name if row.contact_id else row.to_email
        links = []
        if row.contract_id:
            links.append(_link('contract', row.contract_id, row.contract.contract_number))
        if row.quote_id:
            links.append(_link('quote', row.quote_id, row.quote.quote_number))
        if row.invoice_id:
            links.append(_link('invoice', row.invoice_id, row.invoice.invoice_number,
                               contract_id=row.invoice.contract_id))
        if row.contact_id:
            links.append(_link('contact', row.contact_id, row.contact.name))
        return self.event(
            row, ctx, type='email_failed' if failed else 'email_sent', title=f'{prefix}: {row.subject}',
            detail=f'To {recipient}' if recipient else '', actor=SYSTEM_ACTOR, links=links,
            extra={'email_type': row.email_type, 'email_type_label': row.get_email_type_display(),
                   'status': row.status, 'status_label': row.get_status_display(),
                   'opened_at': row.opened_at.isoformat() if row.opened_at else None},
        )


class CareTouchSource(RowSource):
    """Client-care touches, in the slim shape the care card already shows."""

    key = 'care_touch'
    category = 'care'
    model = CareTouch
    time_field = 'occurred_at'
    search_fields = ('summary',)
    record_paths = {'contact': 'contact'}
    select_related = ('contact',)

    def to_event(self, row, ctx):
        kind = row.get_kind_display()
        links = [_link('contact', row.contact_id, row.contact.name)] if row.contact_id else []
        return self.event(
            row, ctx, type='care_touch', title=row.summary or kind, actor=CARE_ACTOR, links=links,
            extra={'kind': row.kind, 'kind_label': kind, 'outcome': row.outcome,
                   'outcome_label': row.get_outcome_display()},
        )


# ---------------------------------------------------------------- quotes


def _quote_links(quote) -> list:
    links = [_link('quote', quote.pk, quote.quote_number)]
    if quote.opportunity_id:
        links.append(_link('opportunity', quote.opportunity_id, quote.opportunity.name))
    return links


_QUOTE_RECORDS = {'quote': 'pk', 'opportunity': 'opportunity', 'contact': 'contact'}


class QuoteCreatedSource(RowSource):
    key = 'quote_created'
    category = 'quote'
    model = Quote
    actor_field = 'created_by'
    search_fields = ('quote_number',)
    record_paths = _QUOTE_RECORDS
    select_related = ('created_by', 'opportunity')

    def to_event(self, row, ctx):
        return self.event(
            row, ctx, type='quote_created', title=f'Quote {row.quote_number} created',
            actor=actor_for_user(row.created_by), links=_quote_links(row),
            extra={'money': _money(row.total_value, row.currency), 'status': row.status,
                   'quote_type': row.quote_type},
        )


_QUOTE_ACTIVITY_TITLES = {
    'Sent': ('quote_sent', 'Quote {n} sent'),
    'Viewed': ('quote_viewed', 'Quote {n} PDF downloaded'),
    'Accepted': ('quote_accepted', 'Quote {n} accepted'),
    'Rejected': ('quote_declined', 'Quote {n} declined'),
    'Expired': ('quote_expired', 'Quote {n} expired'),
    'Converted': ('quote_converted', 'Quote {n} converted to a contract'),
}


class QuoteActivitySource(RowSource):
    """The quote lifecycle as the quote flows log it, with exact times and who did it.

    'Created' is covered by QuoteCreatedSource (every quote has created_at and
    created_by); 'Updated' is covered by the audit log's field changes.
    """

    key = 'quote_activity'
    category = 'quote'
    model = QuoteActivity
    company_path = 'quote__company'
    actor_field = 'user'
    search_fields = ('quote__quote_number', 'description')
    record_paths = {'quote': 'quote', 'opportunity': 'quote__opportunity', 'contact': 'quote__contact'}
    select_related = ('user', 'quote', 'quote__opportunity')

    def extra_q(self, ctx):
        return Q(activity_type__in=list(_QUOTE_ACTIVITY_TITLES))

    def to_event(self, row, ctx):
        type_, title = _QUOTE_ACTIVITY_TITLES[row.activity_type]
        return self.event(
            row, ctx, type=type_, title=title.format(n=row.quote.quote_number),
            actor=actor_for_user(row.user), links=_quote_links(row.quote),
            extra={'money': _money(row.quote.total_value, row.quote.currency)},
        )


class QuoteDateSource(RowSource):
    """A quote status date with no matching activity row (older or imported quotes)."""

    category = 'quote'
    model = Quote
    is_date = True
    search_fields = ('quote_number',)
    record_paths = _QUOTE_RECORDS
    select_related = ('opportunity',)
    activity_type = ''
    event_type = ''
    title = ''

    def __init__(self, key, field_name, activity_type, event_type, title):
        self.key, self.time_field = key, field_name
        self.activity_type, self.event_type, self.title = activity_type, event_type, title

    def extra_q(self, ctx):
        logged = QuoteActivity.objects.filter(quote_id=OuterRef('pk'), activity_type=self.activity_type)
        return Q(**{f'{self.time_field}__isnull': False}) & ~Q(Exists(logged))

    def to_event(self, row, ctx):
        return self.event(row, ctx, type=self.event_type, title=self.title.format(n=row.quote_number),
                          links=_quote_links(row), extra={'money': _money(row.total_value, row.currency)})


# ---------------------------------------------------------------- contracts, invoices


def _contract_links(contract) -> list:
    return [_link('contract', contract.pk, contract.contract_number)]


_CONTRACT_RECORDS = {'contract': 'pk', 'opportunity': 'opportunity', 'quote': 'quote'}


class ContractCreatedSource(RowSource):
    key = 'contract_created'
    category = 'contract'
    model = Contract
    search_fields = ('contract_number', 'renewed_from__contract_number')
    # A renewal's creation also shows on the term it continues.
    record_paths = {**_CONTRACT_RECORDS, 'contract': ('pk', 'renewed_from')}
    select_related = ('renewed_from',)

    def to_event(self, row, ctx):
        links = _contract_links(row)
        if row.renewed_from_id:
            title = f'Renewal {row.contract_number} created for {row.renewed_from.contract_number}'
            links.append(_link('contract', row.renewed_from_id, row.renewed_from.contract_number))
        else:
            title = f'Contract {row.contract_number} created'
        return self.event(
            row, ctx, type='contract_renewal_created' if row.renewed_from_id else 'contract_created',
            title=title, links=links,
            extra={'money': _money(row.value, row.currency), 'status': row.status,
                   'start_date': row.start_date.isoformat() if row.start_date else None,
                   'end_date': row.end_date.isoformat() if row.end_date else None},
        )


def _audit_record_matches(model_name: str):
    """AuditLog rows of ``model_name`` whose record_id is the outer row's primary key."""
    if connection.vendor == 'sqlite':
        # SQLite stores UUIDs as 32 hex digits; record_id holds the hyphenated form.
        return Q(model_name=model_name) & Q(
            record_id_hex=Cast(OuterRef('pk'), output_field=CharField()))
    return Q(model_name=model_name, record_id=Cast(OuterRef('pk'), output_field=CharField()))


def _audit_rows_for(model_name: str):
    rows = AuditLog.objects.all()
    if connection.vendor == 'sqlite':
        rows = rows.annotate(record_id_hex=Replace('record_id', Value('-'), Value('')))
    return rows.filter(_audit_record_matches(model_name))


def _status_became(value: str) -> Q:
    # AuditLog writers use three shapes for a change: old/new, before/after, from/to.
    return Q(changes__status__new=value) | Q(changes__status__after=value) | Q(changes__status__to=value)


class ContractDateSource(RowSource):
    category = 'contract'
    model = Contract
    is_date = True
    search_fields = ('contract_number',)
    record_paths = _CONTRACT_RECORDS

    def __init__(self, key, field_name, event_type, title, audited_status=None):
        self.key, self.time_field, self.event_type, self.title = key, field_name, event_type, title
        self.audited_status = audited_status

    def extra_q(self, ctx):
        q = Q(**{f'{self.time_field}__isnull': False})
        if self.audited_status and ctx.is_admin:
            # The audit log already shows this status change with its exact time.
            q &= ~Q(Exists(_audit_rows_for('Contract').filter(_status_became(self.audited_status))))
        return q

    def to_event(self, row, ctx):
        return self.event(row, ctx, type=self.event_type, title=self.title.format(n=row.contract_number),
                          links=_contract_links(row), extra={'money': _money(row.value, row.currency)})


def _invoice_links(invoice) -> list:
    links = [_link('invoice', invoice.pk, invoice.invoice_number, contract_id=invoice.contract_id)]
    if invoice.contract_id:
        links.append(_link('contract', invoice.contract_id, invoice.contract.contract_number))
    return links


class InvoiceDateSource(RowSource):
    category = 'invoice'
    model = Invoice
    is_date = True
    search_fields = ('invoice_number',)
    record_paths = {'invoice': 'pk', 'contract': 'contract'}
    select_related = ('contract',)

    def __init__(self, key, field_name, event_type, title, q):
        self.key, self.time_field, self.event_type, self.title, self._q = key, field_name, event_type, title, q

    def extra_q(self, ctx):
        return self._q

    def to_event(self, row, ctx):
        return self.event(row, ctx, type=self.event_type, title=self.title.format(n=row.invoice_number),
                          links=_invoice_links(row), extra={'money': _money(row.total_amount, row.currency)})


# ---------------------------------------------------------------- opportunities, tickets


class OpportunityCreatedSource(RowSource):
    key = 'opportunity_created'
    category = 'opportunity'
    model = Opportunity
    search_fields = ('name',)
    record_paths = {'opportunity': 'pk'}

    def to_event(self, row, ctx):
        return self.event(row, ctx, type='opportunity_created', title=f'Opportunity created: {row.name}',
                          links=[_link('opportunity', row.pk, row.name)],
                          extra={'stage': row.stage})


class OpportunityActivitySource(RowSource):
    key = 'opportunity_activity'
    category = 'opportunity'
    model = OpportunityActivity
    company_path = 'opportunity__company'
    actor_field = 'user'
    search_fields = ('subject', 'description', 'outcome', 'next_steps', 'opportunity__name')
    record_paths = {'opportunity': 'opportunity', 'contact': 'contact'}
    select_related = ('user', 'contact', 'opportunity')

    def to_event(self, row, ctx):
        parts = [row.description]
        if row.outcome:
            parts.append(f'Outcome: {row.outcome}')
        if row.next_steps:
            parts.append(f'Next steps: {row.next_steps}')
        links = [_link('opportunity', row.opportunity_id, row.opportunity.name)]
        if row.contact_id:
            links.append(_link('contact', row.contact_id, row.contact.name))
        label = row.get_activity_type_display()
        return self.event(
            row, ctx, type='opportunity_activity', title=f'{label}: {row.subject}',
            detail='\n\n'.join(p for p in parts if p), actor=actor_for_user(row.user), links=links,
            extra={'activity_type': row.activity_type, 'activity_type_label': label,
                   'duration_minutes': row.duration_minutes},
        )


def _ticket_link(ticket) -> dict:
    return _link('ticket', ticket.pk, ticket.ticket_number)


class TicketOpenedSource(RowSource):
    key = 'ticket_opened'
    category = 'ticket'
    model = Ticket
    actor_field = 'created_by'
    search_fields = ('ticket_number', 'subject', 'description')
    record_paths = {'ticket': 'pk', 'contact': 'contact'}
    select_related = ('created_by',)

    def to_event(self, row, ctx):
        return self.event(row, ctx, type='ticket_opened', title=f'Ticket opened: {row.subject}',
                          detail=row.description, actor=actor_for_user(row.created_by),
                          links=[_ticket_link(row)],
                          extra={'priority': row.priority, 'category': row.category, 'status': row.status})


class TicketMomentSource(RowSource):
    category = 'ticket'
    model = Ticket
    search_fields = ('ticket_number', 'subject')
    record_paths = {'ticket': 'pk', 'contact': 'contact'}

    def __init__(self, key, field_name, event_type, title):
        self.key, self.time_field, self.event_type, self.title = key, field_name, event_type, title

    def extra_q(self, ctx):
        return Q(**{f'{self.time_field}__isnull': False})

    def to_event(self, row, ctx):
        return self.event(row, ctx, type=self.event_type, title=self.title.format(s=row.subject),
                          links=[_ticket_link(row)])


class TicketCommentSource(RowSource):
    key = 'ticket_comment'
    category = 'ticket'
    model = TicketComment
    company_path = 'ticket__company'
    actor_field = 'author'
    search_fields = ('text', 'ticket__ticket_number', 'ticket__subject')
    record_paths = {'ticket': 'ticket', 'contact': 'ticket__contact'}
    select_related = ('author', 'ticket')

    def to_event(self, row, ctx):
        kind = 'Internal note' if row.is_internal else 'Reply'
        return self.event(row, ctx, type='ticket_comment', title=f'{kind} on ticket: {row.ticket.subject}',
                          detail=row.text, actor=actor_for_user(row.author), links=[_ticket_link(row.ticket)],
                          extra={'is_internal': row.is_internal})


# ---------------------------------------------------------------- audit log (field changes)


AUDIT_MODELS = {'Company': Company, 'Contact': Contact, 'Contract': Contract, 'Quote': Quote,
                'Opportunity': Opportunity}

# Saved on every write or kept up by the system; never worth a line on the timeline.
_HIDDEN_FIELDS = {
    '*': {'id', 'created_at', 'updated_at'},
    'Company': {'care_summary_updated_at', 'care_summary_updated_by', 'contracted_synced_at'},
    'Contact': {'last_contacted'},
    # sent_date is set automatically with status Sent, which the timeline shows itself.
    'Contract': {'sent_date', 'first_followup_sent', 'second_followup_sent', 'lifecycle_type_manually_set',
                 'tax_amount', 'total_value'},
    # A quote's status and its status dates are shown from the quote activity log.
    'Quote': {'status', 'sent_date', 'accepted_date', 'rejected_date', 'expired_date',
              'first_followup_sent', 'second_followup_sent', 'subtotal'},
    'Opportunity': {'stage_changed_at'},
}
# Nested lists the serializers write; shown as "Changed line items" without values.
_COLLECTIONS = {
    'Contract': {'line_items': 'Line items', 'service_locations': 'Service locations',
                 'service_items': 'Service package items'},
    'Quote': {'line_items': 'Line items'},
}
_MONEY_FIELDS = {
    'Contract': {'value', 'price_per_zone'},
    'Quote': {'tax_amount', 'discount_amount', 'total_value'},
}


def _field_meta(model_name: str) -> dict:
    """Visible field name -> model field, for one audited model."""
    model = AUDIT_MODELS[model_name]
    hidden = _HIDDEN_FIELDS['*'] | _HIDDEN_FIELDS.get(model_name, set())
    meta = {}
    for f in model._meta.concrete_fields:
        if f.name in hidden or _SECRET_KEY.search(f.name):
            continue
        meta[f.name] = f
        if getattr(f, 'attname', f.name) != f.name:
            meta[f.attname] = f
    return meta


_FIELD_META = {name: _field_meta(name) for name in AUDIT_MODELS}


def visible_keys(model_name: str) -> list[str]:
    return sorted(set(_FIELD_META[model_name]) | set(_COLLECTIONS.get(model_name, {})))


def _change_pair(value):
    """(old, new) from the three shapes AuditLog writers use, or None."""
    if not isinstance(value, dict):
        return None
    for old_key, new_key in (('old', 'new'), ('before', 'after'), ('from', 'to')):
        if old_key in value or new_key in value:
            return value.get(old_key), value.get(new_key)
    return None


def _has_any(keys) -> Q:
    return Q(changes__has_any_keys=list(keys))


def _status_key(model_name):
    return {'Contract': 'status', 'Opportunity': 'stage'}.get(model_name)


class AuditSource(RowSource):
    """Field changes and status changes on the company and its contacts, contracts,
    quotes and opportunities: one event per save, as the audit log stores it.

    Only Admin sees these, as on ``/audit-logs/``.
    """

    model = AuditLog
    time_field = 'timestamp'
    actor_field = 'user'
    admin_only = True
    select_related = ('user',)

    def __init__(self, key, category, mode):
        # mode: 'contract_status' | 'opportunity_stage' | 'change'
        self.key, self.category, self.mode = key, category, mode

    def _scope_q(self, ctx) -> Q:
        f = ctx.filters
        if f.record_type:
            name, ids = {'contract': ('Contract', ctx.contracts), 'quote': ('Quote', ctx.quotes),
                         'contact': ('Contact', ctx.contacts),
                         'opportunity': ('Opportunity', ctx.opportunities)}.get(f.record_type, (None, {}))
            if name is None or f.record_id not in ids:  # only records of this company
                return Q(pk__in=[])
            return Q(model_name=name, record_id=f.record_id)
        q = Q(model_name='Company', record_id=str(ctx.company.pk))
        for name, ids in (('Contact', ctx.contacts), ('Contract', ctx.contracts), ('Quote', ctx.quotes),
                          ('Opportunity', ctx.opportunities)):
            if ids:
                q |= Q(model_name=name, record_id__in=list(ids))
        # Records already deleted through MCP still name their company.
        q |= Q(action='DELETE', model_name__in=['Contact', 'Contract', 'Quote', 'Opportunity'],
               additional_data__deleted__company_id=str(ctx.company.pk))
        return q

    def _mode_q(self) -> Q:
        updates = Q(action='UPDATE')
        if self.mode == 'contract_status':
            return updates & Q(model_name='Contract', changes__has_key='status')
        if self.mode == 'opportunity_stage':
            return updates & Q(model_name='Opportunity', changes__has_key='stage')
        visible = Q(pk__in=[])
        for name in AUDIT_MODELS:
            vq = Q(model_name=name) & _has_any(visible_keys(name))
            status = _status_key(name)
            if status:
                vq &= ~Q(changes__has_key=status)
            visible |= vq
        # Records whose creation has no event of its own, and deletions.
        return (updates & visible) | Q(action='CREATE', model_name__in=['Company', 'Contact']) | Q(
            action='DELETE', model_name__in=['Contact', 'Contract', 'Quote', 'Opportunity'])

    def base_queryset(self, ctx):
        return AuditLog.objects.filter(self._scope_q(ctx), self._mode_q())

    def _record_q(self, ctx):
        f = ctx.filters
        if f.record_type and f.record_type not in ('contract', 'quote', 'contact', 'opportunity'):
            return None
        return Q()  # applied in _scope_q

    def _search_q(self, ctx):
        term = ctx.filters.search
        if not term:
            return Q()
        low = term.lower()
        q = Q(changes_text__icontains=term)
        labels = {'Contact': {k: v for k, v in ctx.contacts.items()},
                  'Contract': {k: v['label'] for k, v in ctx.contracts.items()},
                  'Quote': {k: v['label'] for k, v in ctx.quotes.items()},
                  'Opportunity': ctx.opportunities}
        for name, mapping in labels.items():
            hits = [pk for pk, label in mapping.items() if label and low in label.lower()]
            if hits:
                q |= Q(model_name=name, record_id__in=hits)
        if low in ctx.company.name.lower():
            q |= Q(model_name='Company')
        return q

    def annotate(self, qs, ctx):
        if ctx.filters.search:
            qs = qs.annotate(changes_text=Cast('changes', output_field=TextField()))
        return qs

    # -- rendering ---------------------------------------------------------

    def prepare(self, rows, ctx):
        user_ids = set()
        for row in rows:
            meta = _FIELD_META.get(row.model_name, {})
            for key, value in (row.changes or {}).items() if isinstance(row.changes, dict) else ():
                f = meta.get(key)
                if f is not None and f.is_relation and f.related_model is User:
                    pair = _change_pair(value) or (None, None)
                    user_ids.update(str(v) for v in pair if v)
        valid = []
        for value in user_ids:
            try:
                valid.append(uuid.UUID(value))
            except ValueError:
                continue
        ctx.audit_users = {str(u.pk): actor_for_user(u)['name'] for u in User.objects.filter(pk__in=valid)} \
            if valid else {}

    def _record_label(self, row, ctx) -> tuple[str, str | None]:
        """(label, link type) of the record the row is about."""
        rid = row.record_id
        if row.model_name == 'Company':
            return ctx.company.name, None
        if row.model_name == 'Contact':
            return ctx.contacts.get(rid) or 'a contact', 'contact'
        if row.model_name == 'Contract':
            return (ctx.contracts.get(rid) or {}).get('label') or 'a contract', 'contract'
        if row.model_name == 'Quote':
            return (ctx.quotes.get(rid) or {}).get('label') or 'a quote', 'quote'
        return ctx.opportunities.get(rid) or 'an opportunity', 'opportunity'

    def _ref_label(self, f, value, ctx):
        if value in (None, ''):
            return None
        value = str(value)
        target = f.related_model
        if target is Company:
            return ctx.company.name if value == str(ctx.company.pk) else 'another company'
        if target is Contact:
            return ctx.contacts.get(value)
        if target is Contract:
            return (ctx.contracts.get(value) or {}).get('label')
        if target is Quote:
            return (ctx.quotes.get(value) or {}).get('label')
        if target is Opportunity:
            return ctx.opportunities.get(value)
        if target is User:
            return getattr(ctx, 'audit_users', {}).get(value)
        return None

    def _render_value(self, f, value, ctx, kind):
        if value in (None, '', [], {}):
            return None
        if kind == 'bool':
            return 'Yes' if value in (True, 'true', 'True', 1) else 'No'
        if f is not None and f.choices:
            return _cap(dict(f.flatchoices).get(value, value), VALUE_MAX)
        if isinstance(value, (dict, list)):
            return _cap(json.dumps(value, ensure_ascii=False), VALUE_MAX)
        return _cap(value, VALUE_MAX)

    def _changes(self, row, ctx) -> list:
        model_name = row.model_name
        meta = _FIELD_META.get(model_name, {})
        collections = _COLLECTIONS.get(model_name, {})
        money = _MONEY_FIELDS.get(model_name, set())
        currency = None
        if model_name == 'Contract':
            currency = (ctx.contracts.get(row.record_id) or {}).get('currency')
        elif model_name == 'Quote':
            currency = (ctx.quotes.get(row.record_id) or {}).get('currency')
        out = []
        changes = row.changes if isinstance(row.changes, dict) else {}
        for key in sorted(changes):
            if key in collections:
                out.append({'field': key, 'label': collections[key], 'kind': 'collection',
                            'old': None, 'new': None})
                continue
            f = meta.get(key)
            if f is None:
                continue
            pair = _change_pair(changes[key])
            if pair is None:
                continue
            old, new = pair
            label = str(f.verbose_name)
            label = label[:1].upper() + label[1:]
            if f.is_relation:
                old_l, new_l = self._ref_label(f, old, ctx), self._ref_label(f, new, ctx)
                if (old and not old_l) or (new and not new_l):
                    out.append({'field': key, 'label': label, 'kind': 'opaque', 'old': None, 'new': None})
                elif old_l != new_l:
                    out.append({'field': key, 'label': label, 'kind': 'ref', 'old': old_l, 'new': new_l})
                continue
            internal = f.get_internal_type()
            if internal == 'BooleanField':
                kind = 'bool'
            elif internal == 'DateField':
                kind = 'date'
            elif internal == 'DateTimeField':
                kind = 'datetime'
            elif key in money:
                kind = 'money'
            else:
                kind = 'text'
            entry = {'field': key, 'label': label, 'kind': kind,
                     'old': self._render_value(f, old, ctx, kind), 'new': self._render_value(f, new, ctx, kind)}
            if entry['old'] == entry['new']:
                continue  # some writers list every field they were given, changed or not
            if kind == 'money':
                entry['currency'] = currency or ''
            out.append(entry)
        return out

    def to_event(self, row, ctx):
        label, link_type = self._record_label(row, ctx)
        links = [_link(link_type, row.record_id, label)] if link_type and row.action != 'DELETE' else []
        actor = actor_for_user(row.user) or SYSTEM_ACTOR
        additional = row.additional_data if isinstance(row.additional_data, dict) else {}
        extra = {'model': row.model_name, 'action': row.action}
        reason = additional.get('action') or additional.get('reason')
        if isinstance(reason, str) and reason:
            extra['reason'] = _cap(reason, VALUE_MAX)
        if additional.get('via') == 'mcp':
            extra['via'] = 'mcp'

        if row.action == 'CREATE':
            title = 'Company record created' if row.model_name == 'Company' else f'Contact added: {label}'
            return self.event(row, ctx, type='record_created', title=title, actor=actor, links=links, extra=extra)
        if row.action == 'DELETE':
            deleted = additional.get('deleted') if isinstance(additional.get('deleted'), dict) else {}
            name = (deleted.get('name') or deleted.get('contract_number') or deleted.get('quote_number')
                    or (label if not label.startswith(('a ', 'an ')) else ''))
            title = f'{row.model_name} deleted' + (f': {name}' if name else '')
            return self.event(row, ctx, type='record_deleted', title=title, actor=actor, extra=extra)

        changes = self._changes(row, ctx)
        status_key = _status_key(row.model_name) if self.mode != 'change' else None
        if status_key:
            status = next((c for c in changes if c['field'] == status_key), None)
            others = [c for c in changes if c['field'] != status_key]
            if status is None:
                # The writer listed the status without changing it: an ordinary edit.
                if not others:
                    return None
                return self.event(row, ctx, type='field_change', title=f'{label} updated', actor=actor,
                                  links=links, changes=others, detail=_changes_text(others), extra=extra)
            if self.mode == 'contract_status':
                title = f'Contract {label}: {status["old"] or "—"} → {status["new"] or "—"}'
                type_ = 'contract_status'
            else:
                title = f'Opportunity {label}: {status["old"] or "—"} → {status["new"] or "—"}'
                type_ = 'opportunity_stage'
            extra.update({'old_status': status['old'], 'new_status': status['new']})
            return self.event(row, ctx, type=type_, title=title, actor=actor, links=links, changes=others,
                              detail=_changes_text(others), extra=extra)
        if not changes:
            return None
        names = ', '.join(c['label'].lower() for c in changes[:3]) + (' …' if len(changes) > 3 else '')
        title = f'{label} updated: {names}' if row.model_name != 'Company' else f'Company details updated: {names}'
        return self.event(row, ctx, type='field_change', title=title, actor=actor, links=links, changes=changes,
                          detail=_changes_text(changes), extra=extra)


def _changes_text(changes: list) -> str:
    lines = []
    for c in changes:
        if c['kind'] in ('collection', 'opaque'):
            lines.append(f"Changed {c['label']}")
        else:
            lines.append(f"Changed {c['label']} from {c['old'] or 'empty'} to {c['new'] or 'empty'}")
    return '\n'.join(lines)


# ---------------------------------------------------------------- registration


def _register_defaults():
    for source in (
        NoteSource(),
        TaskCreatedSource(),
        TaskCompletedSource(),
        TaskCommentSource(),
        EmailLogSource(),
        CareTouchSource(),
        QuoteCreatedSource(),
        QuoteActivitySource(),
        QuoteDateSource('quote_sent_date', 'sent_date', 'Sent', 'quote_sent', 'Quote {n} sent'),
        QuoteDateSource('quote_accepted_date', 'accepted_date', 'Accepted', 'quote_accepted',
                        'Quote {n} accepted'),
        QuoteDateSource('quote_rejected_date', 'rejected_date', 'Rejected', 'quote_declined',
                        'Quote {n} declined'),
        QuoteDateSource('quote_expired_date', 'expired_date', 'Expired', 'quote_expired', 'Quote {n} expired'),
        ContractCreatedSource(),
        ContractDateSource('contract_sent', 'sent_date', 'contract_sent', 'Contract {n} sent',
                           audited_status='Sent'),
        ContractDateSource('contract_signed', 'signed_date', 'contract_signed', 'Contract {n} signed'),
        InvoiceDateSource('invoice_issued', 'issue_date', 'invoice_issued', 'Invoice {n} issued',
                          ~Q(status='Draft')),
        InvoiceDateSource('invoice_paid', 'paid_date', 'invoice_paid', 'Invoice {n} paid',
                          Q(paid_date__isnull=False)),
        OpportunityCreatedSource(),
        OpportunityActivitySource(),
        TicketOpenedSource(),
        TicketCommentSource(),
        TicketMomentSource('ticket_resolved', 'resolved_at', 'ticket_resolved', 'Ticket resolved: {s}'),
        TicketMomentSource('ticket_closed', 'closed_at', 'ticket_closed', 'Ticket closed: {s}'),
        AuditSource('audit_contract_status', 'contract', 'contract_status'),
        AuditSource('audit_opportunity_stage', 'opportunity', 'opportunity_stage'),
        AuditSource('audit_change', 'change', 'change'),
    ):
        registry.register(source)


_register_defaults()


# ---------------------------------------------------------------- merge


def build_page(ctx: TimelineContext, cursor: Cursor | None, page_size: int,
               sources: Iterable[TimelineSource] | None = None) -> dict:
    """One page of events, newest first, merged from every active source."""
    sources = [s for s in (sources if sources is not None else registry.sources()) if s.active(ctx)]
    events, floors = [], []
    for source in sources:
        result = source.fetch(ctx, cursor, page_size)
        events.extend(result.events)
        if result.complete_until is not None:
            floors.append(result.complete_until)
    events.sort(key=lambda e: e.sort_key, reverse=True)
    # Below the highest floor, some source may still hold events it did not return.
    cutoff = max(floors) if floors else None
    candidates = [e for e in events if cutoff is None or e.sort_key >= cutoff]
    page = candidates[:page_size]
    if len(page) == page_size and (len(candidates) > page_size or cutoff is not None):
        next_cursor = Cursor(*page[-1].sort_key)
    elif cutoff is not None:
        next_cursor = Cursor(*cutoff)  # everything at or above the cutoff has been delivered
    else:
        next_cursor = None
    return {
        'results': [e.as_dict() for e in page],
        'next_cursor': next_cursor.encode() if next_cursor else None,
        'has_more': next_cursor is not None,
    }


def build_facets(ctx: TimelineContext) -> dict:
    """Counts per filter chip (ignoring the type filter) and per person (ignoring the actor filter)."""
    selected = ctx.filters.categories
    actor = ctx.filters.actor_id
    types = {key: 0 for key in CATEGORIES}
    actor_counts: dict[str, int] = {}
    for source in registry.sources():
        if not source.available(ctx):
            continue
        for actor_id, n in source.facet_rows(ctx):
            if actor is None or actor_id == actor:
                types[source.category] = types.get(source.category, 0) + n
            if actor_id and (selected is None or source.category in selected):
                actor_counts[actor_id] = actor_counts.get(actor_id, 0) + n
    actors = []
    if actor_counts:
        users = {str(u.pk): u for u in User.objects.filter(pk__in=list(actor_counts))}
        for actor_id, n in actor_counts.items():
            user = users.get(actor_id)
            if user is None:
                continue
            actors.append({**actor_for_user(user), 'count': n})
        actors.sort(key=lambda a: (-a['count'], a['name'].lower()))
    return {'types': types, 'actors': actors}
