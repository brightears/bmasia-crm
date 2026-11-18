"""One read-only timeline per company: every recorded interaction, newest first.

``GET /api/v1/companies/<id>/timeline/`` merges events from many tables (notes,
tasks, CRM email, client-care touches, quotes, contracts, invoices,
opportunities, tickets and the audit log) into one typed, paged list. Nothing
here writes, sends or calls out.

How it works
------------
* Every source is an adapter registered in ``registry``. A source answers two
  questions for one company and one set of filters: "give me your newest
  ``limit`` events older than this cursor" (``fetch``) and "how many visible
  events do you have, per actor" (``facet_rows``). Each is **one query**.
* The merge step (``build_page``) never needs to know what a source is. It asks
  every active source for a batch, sorts by ``(occurred_at, id)`` descending
  and cuts at the oldest point every source has fully covered. When rows render
  to nothing (a save that changed no visible field), it reads on for a bounded
  number of extra rounds (``EXTRA_ROUNDS``), so a page is full unless the
  history is exhausted. A page costs 31 queries for an Admin in the usual case
  (one per source, four label maps, the company) and at most
  ``(1 + EXTRA_ROUNDS) * (sources + 3) + 5`` when it must read on.
* Ties: two events at the same instant are ordered by their id
  (``"<source key>:<pk>"``). Source keys are ``[a-z_]`` words, so comparing two
  ids from different sources is decided by the keys alone, and SQL can apply the
  same rule (``pk < cursor pk`` within a source). The cursor carries the full
  ``(occurred_at, id)`` of the last event, so new events arriving between two
  page loads never shift or repeat a later page.
* Some lifecycle facts are stored as dates without a time (``Contract.sent_date``,
  ``Invoice.paid_date``…). They are shown with ``precision: "date"`` and placed at
  the end of that day in the CRM's time zone, a later stage later (``day_order``);
  no time of day is invented.
* Visibility: every source lists the viewsets that serve its data today
  (``RowSource.visibility``) and keeps only the rows their own ``get_queryset``
  shows the same user (``TimelineContext.visibility_q``). Search and counts go
  through the same rows. The audit sources need the /audit-logs/ permission.

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
        actor_field = 'recorded_by'
        search_fields = ('summary',)
        record_paths = {'contact': 'contact', 'contract': 'contract'}
        visibility = (('agent_inbox.api.ActivityViewSet', 'pk'),)

        def to_event(self, row, ctx):
            return self.event(row, ctx, type='activity_' + row.kind, title=row.summary, ...)

    timeline.registry.register(AgentActivitySource())

Duties of every adapter (the timeline cannot do these for it):

* Show no more than the source's own API shows the same user: list its viewset
  in ``visibility``, or narrow rows in ``extra_q``. Search fields and ``detail``
  must not reach text the viewer may not read.
* ``ctx.is_agent`` is True when the viewer is an agent account
  (``is_agent_account``). Every agent is Admin today, so admin checks do not
  keep anything from agents; an adapter that must withhold text from agents
  checks ``ctx.is_agent`` itself.
* Agent activities (PR 58, ``agent_inbox.Activity``): leave out voided rows
  (``extra_q``: ``is_void=False``); when ``ctx.is_agent`` and the row was not
  recorded by the viewer, put neither ``body`` nor participants into ``detail``
  or ``extra``; search the summary only.
* Captured mail (PR 59, ``mail_capture``): keep only messages with a copy in a
  mailbox the viewer may see (team mailboxes, or their own), decided by the same
  rule as the capture API; never put bodies or addresses into ``detail`` for
  viewers who may not read them. To stop CRM-sent email showing twice, the
  ``EmailLogSource`` needs an ``~Exists`` on captured mail by ``email_log`` that
  uses that same visibility (a change to this module, not an adapter).
* Return ``None`` from ``to_event`` for a row that should not show, rather than
  filtering in Python elsewhere; the merge and the extra rounds handle it. If
  rows can render to nothing, override ``facet_rows`` so counts match the page
  (``AuditSource.facet_rows`` is the model).
* Add the category to ``CATEGORIES`` and the frontend's ``CATEGORY_LABELS``, and
  raise ``QUERIES_PER_PAGE`` in the tests by one.

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

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import CharField, Count, Exists, OuterRef, Q, TextField, Value
from django.db.models.functions import Cast, Coalesce, Replace
from django.utils import timezone
from django.utils.functional import cached_property

from crm_app.models import (
    AuditLog, CareTouch, Company, Contact, Contract, EmailLog, Invoice, Note, Opportunity,
    OpportunityActivity, Quote, QuoteActivity, Task, TaskComment, Ticket, TicketComment, User,
)

TITLE_MAX = 200
DETAIL_MAX = 1000
VALUE_MAX = 200
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SEARCH_LENGTH = 200
# Dates and cursor times outside these years are refused (they cannot be converted safely).
MIN_YEAR, MAX_YEAR = 1900, 9998
# When rows render to nothing (a save that changed no visible field), a page keeps
# reading: at most EXTRA_ROUNDS more rounds, each asking only the sources that
# still have rows for up to EXTRA_ROUND_LIMIT more. If the page is still short
# after that, the response says has_more with a cursor and the next request
# carries on from there.
EXTRA_ROUNDS = 3
EXTRA_ROUND_LIMIT = 250
# Date-only facts sit at the very end of their day (CRM time zone), so they read
# above that day's timed events, and a later stage sits later within the day
# (sent < signed, sent < accepted, issued < paid).
DAY_SLOTS = 10

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
# The viewset that serves each record type: a record it hides gives an empty timeline.
RECORD_VIEWSETS = {
    'contract': 'crm_app.views.ContractViewSet', 'quote': 'crm_app.views.QuoteViewSet',
    'contact': 'crm_app.views.ContactViewSet', 'opportunity': 'crm_app.views.OpportunityViewSet',
    'ticket': 'crm_app.views.TicketViewSet', 'task': 'crm_app.views.TaskViewSet',
    'invoice': 'crm_app.views.InvoiceViewSet',
}

_KEY_RE = re.compile(r'^[a-z][a-z_]*$')
_CURSOR_PK_RE = re.compile(r'^[A-Za-z0-9-]{1,64}$')
_SECRET_KEY = re.compile(r'password|passwd|secret|token|api_?key|credential|smtp', re.IGNORECASE)


# ---------------------------------------------------------------- small helpers


def local_midnight(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_default_timezone())


def local_date(moment: datetime) -> date:
    return timezone.localtime(moment, timezone.get_default_timezone()).date()


def day_anchor(day: date, order: int = 0) -> datetime:
    """Where a date-only fact sits: the end of its day, one microsecond step per stage."""
    return local_midnight(day + timedelta(days=1)) - timedelta(microseconds=DAY_SLOTS - order)


def _cap(text: Any, limit: int) -> str:
    text = '' if text is None else str(text)
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def _extra_agent_usernames() -> frozenset:
    from django.conf import settings
    raw = getattr(settings, 'AGENT_INBOX_AGENT_USERNAMES', ()) or ()
    if isinstance(raw, str):
        raw = raw.split(',')
    return frozenset(str(name).strip().lower() for name in raw if str(name).strip())


def is_agent_account(user) -> bool:
    """Whether an account belongs to an agent rather than a person.

    The one rule the timeline uses, both to label actors and for
    ``TimelineContext.is_agent``. It is the rule of the agent gate and of the
    agent inbox (PR 58, ``agent_inbox.policy.is_agent_account``): the CRM
    username is an agent principal in ``crm_app.agent_policy`` (cira, vera,
    theo, lyra, riff, nina, cara, sales, ruby), or is listed in the
    AGENT_INBOX_AGENT_USERNAMES setting. The CRM stores nothing else that tells
    an agent account from a person's, so those usernames are reserved for agents.
    """
    if user is None or not getattr(user, 'is_authenticated', True):
        return False
    from crm_app.agent_policy import principal_for_username
    username = str(getattr(user, 'username', '') or '').strip().lower()
    return bool(username) and (
        principal_for_username(username) is not None or username in _extra_agent_usernames())


def actor_for_user(user) -> dict | None:
    """Display name for a user or agent. Never an email address and never a fragment of one."""
    if user is None:
        return None
    username = str(getattr(user, 'username', '') or '').strip()
    if is_agent_account(user):
        from crm_app.agent_policy import principal_for_username
        principal = principal_for_username(username)
        name = principal.name if principal is not None else username
        return {'id': str(user.pk), 'name': name.capitalize(), 'kind': 'agent'}
    full = (user.get_full_name() or '').strip()
    # A full name holding an address ("Mo <mo@…>") falls back to the username.
    name = full if full and '@' not in full else username
    if '@' in name:  # a username that is itself an address: its local part
        name = name.split('@', 1)[0]
    return {'id': str(user.pk), 'name': name or 'Unknown user', 'kind': 'user'}


SYSTEM_ACTOR = {'id': None, 'name': 'CRM', 'kind': 'system'}
# An audit row written by a signed-in user (REST or MCP) whose account was deleted since.
DELETED_USER = {'id': None, 'name': 'Deleted user', 'kind': 'user'}
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
        key, _, pk = event_id.partition(':')
        if (timezone.is_naive(moment) or not _KEY_RE.match(key) or not _CURSOR_PK_RE.match(pk)
                or not MIN_YEAR <= moment.year <= MAX_YEAR):
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


def _list_request(user):
    """A blank GET request for ``user``: what a viewset sees on a plain list call."""
    from django.http import HttpRequest
    from rest_framework.request import Request
    http = HttpRequest()
    http.method = 'GET'
    http.user = user
    request = Request(http)
    request.user = user
    return request


def viewset_queryset(viewset_path: str, user):
    """The rows the viewset at ``viewset_path`` lets ``user`` list: its own get_queryset, unchanged."""
    from django.utils.module_loading import import_string
    view = import_string(viewset_path)()
    view.request = _list_request(user)
    view.args, view.kwargs, view.action, view.format_kwarg = (), {}, 'list', None
    return view.get_queryset()


def restricts(queryset) -> bool:
    """Whether a viewset's queryset narrows its table at all (for Admin it usually does not)."""
    return bool(queryset.query.where)


class TimelineContext:
    """Per-request state shared by all sources: company, viewer, filters, label maps.

    Visibility: each source narrows its rows with the get_queryset of the
    viewset that already serves that data (``RowSource.visibility``), called for
    the same user, so the timeline never shows a row the regular API hides from
    them; search and counts go through the same rows. ``is_admin`` is the
    /audit-logs/ permission check itself. ``is_agent`` says the viewer is an
    agent account (``is_agent_account``); every agent is Admin today, so a
    source that must keep bodies from agents checks ``is_agent`` itself.
    """

    def __init__(self, company: Company, user, filters: Filters):
        self.company = company
        self.user = user
        self.filters = filters
        self._maps: dict[str, dict] = {}
        self._viewset_qs: dict[str, Any] = {}

    @cached_property
    def is_admin(self) -> bool:
        """Can read the audit log: the permission check of /audit-logs/ itself."""
        from crm_app.permissions import RoleBasedPermission
        from crm_app.views import AuditLogViewSet
        return bool(RoleBasedPermission().has_permission(_list_request(self.user), AuditLogViewSet()))

    @cached_property
    def is_agent(self) -> bool:
        return is_agent_account(self.user)

    def visible(self, viewset_path: str):
        if viewset_path not in self._viewset_qs:
            self._viewset_qs[viewset_path] = viewset_queryset(viewset_path, self.user)
        return self._viewset_qs[viewset_path]

    def visibility_q(self, viewset_path: str, lookup: str = 'pk') -> Q:
        """Rows whose ``lookup`` points at a row that viewset shows this user; no filter when it shows all."""
        qs = self.visible(viewset_path)
        if not restricts(qs):
            return Q()
        return Q(**{f'{lookup}__in': qs.order_by().values('pk')})

    @cached_property
    def hidden_opportunity_ids(self) -> frozenset:
        """This company's opportunities that /opportunities/ hides from the viewer; links to them are dropped."""
        qs = self.visible('crm_app.views.OpportunityViewSet')
        if not restricts(qs):
            return frozenset()
        shown = qs.filter(company_id=self.company.pk).order_by().values('pk')
        return frozenset(str(pk) for pk in Opportunity.objects.filter(company_id=self.company.pk)
                         .exclude(pk__in=shown).values_list('pk', flat=True))

    def record_hidden(self) -> bool:
        """Whether the ``record`` filter names a record its own endpoint hides from the viewer."""
        return self._record_hidden

    @cached_property
    def _record_hidden(self) -> bool:
        f = self.filters
        if not f.record_type:
            return False
        qs = self.visible(RECORD_VIEWSETS[f.record_type])
        return restricts(qs) and not qs.filter(pk=f.record_id).exists()

    def opportunity_link(self, opportunity_id, label):
        if not opportunity_id or str(opportunity_id) in self.hidden_opportunity_ids:
            return None
        return _link('opportunity', opportunity_id, label)

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
        """``[(actor user id or None, count), …]`` of visible events, for every filter except type and actor."""
        raise NotImplementedError

    def valid_cursor_pk(self, pk: str) -> bool:
        """Whether ``pk`` can be the id part of one of this source's events (checked before any query)."""
        return True


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
    #: (viewset dotted path, lookup from the row to that viewset's model) pairs. A row
    #: shows only if each listed viewset shows the viewer the row it points at.
    visibility: tuple = ()
    #: For date-only sources: the stage within the day (see DAY_SLOTS).
    day_order = 0

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
        return day_anchor(value, self.day_order) if self.is_date else value

    def valid_cursor_pk(self, pk):
        try:
            self.model._meta.pk.to_python(pk)
        except (ValidationError, ValueError, TypeError):
            return False
        return True

    def event_id(self, row) -> str:
        return f'{self.key}:{row.pk}'

    def event(self, row, ctx, **kwargs) -> TimelineEvent:
        kwargs.setdefault('category', self.category)
        kwargs.setdefault('precision', 'date' if self.is_date else 'datetime')
        return TimelineEvent(id=self.event_id(row), occurred_at=self.occurred_at(row), **kwargs)

    def base_queryset(self, ctx):
        qs = self.model._default_manager.filter(**{self.company_path: ctx.company.pk})
        for viewset_path, lookup in self.visibility:
            qs = qs.filter(ctx.visibility_q(viewset_path, lookup))
        return qs

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
            anchor = day_anchor(day, self.day_order)
            q = Q(**{f'{tf}__lt': day})
            if cursor.occurred_at > anchor:
                return q | Q(**{tf: day})
            if cursor.occurred_at == anchor and tie is not None:
                return q | (Q(**{tf: day}) & tie)
            return q
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
    # NoteViewSet hides other people's private notes from non-Admins.
    visibility = (('crm_app.views.NoteViewSet', 'pk'),)

    def extra_q(self, ctx):
        return ~_AUTO_EMAIL_NOTE

    def to_event(self, row, ctx):
        label = row.get_note_type_display()
        links = [_link('contact', row.contact_id, row.contact.name)] if row.contact_id else []
        return self.event(
            row, ctx, type='note', title=row.title or f'{label} note', detail=row.text,
            actor=actor_for_user(row.author), links=links,
            extra={'note_type': row.note_type, 'note_type_label': label, 'priority': row.priority,
                   'is_private': row.is_private},
        )


def _task_links(task, ctx) -> list:
    links = [_link('task', task.pk, task.title)]
    if task.related_contract_id:
        links.append(_link('contract', task.related_contract_id, task.related_contract.contract_number))
    if task.related_opportunity_id:
        opp = ctx.opportunity_link(task.related_opportunity_id, task.related_opportunity.name)
        if opp:
            links.append(opp)
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
    visibility = (('crm_app.views.TaskViewSet', 'pk'),)

    def to_event(self, row, ctx):
        assignee = actor_for_user(row.assigned_to)
        return self.event(
            row, ctx, type='task_created', title=f'Task created: {row.title}', detail=row.description,
            actor=actor_for_user(row.created_by), links=_task_links(row, ctx),
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
            row, ctx, type='task_completed', title=f'Task completed: {row.title}', links=_task_links(row, ctx),
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
    # Comments are read through /tasks/<id>/comments/, so the task's visibility applies.
    visibility = (('crm_app.views.TaskViewSet', 'task'),)

    def to_event(self, row, ctx):
        return self.event(
            row, ctx, type='task_comment', title=f'Comment on task: {row.task.title}', detail=row.comment,
            actor=actor_for_user(row.user), links=_task_links(row.task, ctx),
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
    visibility = (('crm_app.views.EmailLogViewSet', 'pk'),)

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
            # A contact already shows as a link; otherwise say who it went to.
            detail='' if row.contact_id else (f'To {recipient}' if recipient else ''),
            actor=SYSTEM_ACTOR, links=links,
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
    # Read today through /companies/<id>/care-touches/: whoever can open the company.
    visibility = (('crm_app.views.CompanyViewSet', 'company'),)

    def to_event(self, row, ctx):
        kind = row.get_kind_display()
        links = [_link('contact', row.contact_id, row.contact.name)] if row.contact_id else []
        return self.event(
            row, ctx, type='care_touch', title=row.summary or kind, actor=CARE_ACTOR, links=links,
            extra={'kind': row.kind, 'kind_label': kind, 'outcome': row.outcome,
                   'outcome_label': row.get_outcome_display()},
        )


# ---------------------------------------------------------------- quotes


def _quote_links(quote, ctx) -> list:
    links = [_link('quote', quote.pk, quote.quote_number)]
    if quote.opportunity_id:
        opp = ctx.opportunity_link(quote.opportunity_id, quote.opportunity.name)
        if opp:
            links.append(opp)
    return links


_QUOTE_RECORDS = {'quote': 'pk', 'opportunity': 'opportunity', 'contact': 'contact'}
_QUOTE_VISIBILITY = (('crm_app.views.QuoteViewSet', 'pk'),)


class QuoteCreatedSource(RowSource):
    key = 'quote_created'
    category = 'quote'
    model = Quote
    actor_field = 'created_by'
    search_fields = ('quote_number',)
    record_paths = _QUOTE_RECORDS
    select_related = ('created_by', 'opportunity')
    visibility = _QUOTE_VISIBILITY

    def to_event(self, row, ctx):
        return self.event(
            row, ctx, type='quote_created', title=f'Quote {row.quote_number} created',
            actor=actor_for_user(row.created_by), links=_quote_links(row, ctx),
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
    # Quote activity is read nested in /quotes/<id>/.
    visibility = (('crm_app.views.QuoteViewSet', 'quote'),)

    def extra_q(self, ctx):
        return Q(activity_type__in=list(_QUOTE_ACTIVITY_TITLES))

    def to_event(self, row, ctx):
        type_, title = _QUOTE_ACTIVITY_TITLES[row.activity_type]
        return self.event(
            row, ctx, type=type_, title=title.format(n=row.quote.quote_number),
            actor=actor_for_user(row.user), links=_quote_links(row.quote, ctx),
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
    visibility = _QUOTE_VISIBILITY
    activity_type = ''
    event_type = ''
    title = ''

    def __init__(self, key, field_name, activity_type, event_type, title, day_order=0):
        self.key, self.time_field = key, field_name
        self.activity_type, self.event_type, self.title = activity_type, event_type, title
        self.day_order = day_order

    def extra_q(self, ctx):
        logged = QuoteActivity.objects.filter(quote_id=OuterRef('pk'), activity_type=self.activity_type)
        return Q(**{f'{self.time_field}__isnull': False}) & ~Q(Exists(logged))

    def to_event(self, row, ctx):
        return self.event(row, ctx, type=self.event_type, title=self.title.format(n=row.quote_number),
                          links=_quote_links(row, ctx), extra={'money': _money(row.total_value, row.currency)})


# ---------------------------------------------------------------- contracts, invoices


def _contract_links(contract) -> list:
    return [_link('contract', contract.pk, contract.contract_number)]


_CONTRACT_RECORDS = {'contract': 'pk', 'opportunity': 'opportunity', 'quote': 'quote'}
_CONTRACT_VISIBILITY = (('crm_app.views.ContractViewSet', 'pk'),)


class ContractCreatedSource(RowSource):
    key = 'contract_created'
    category = 'contract'
    model = Contract
    search_fields = ('contract_number', 'renewed_from__contract_number')
    # A renewal's creation also shows on the term it continues.
    record_paths = {**_CONTRACT_RECORDS, 'contract': ('pk', 'renewed_from')}
    select_related = ('renewed_from',)
    visibility = _CONTRACT_VISIBILITY

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
    visibility = _CONTRACT_VISIBILITY

    def __init__(self, key, field_name, event_type, title, audited_status=None, day_order=0):
        self.key, self.time_field, self.event_type, self.title = key, field_name, event_type, title
        self.audited_status = audited_status
        self.day_order = day_order

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
    visibility = (('crm_app.views.InvoiceViewSet', 'pk'),)

    def __init__(self, key, field_name, event_type, title, q, day_order=0):
        self.key, self.time_field, self.event_type, self.title, self._q = key, field_name, event_type, title, q
        self.day_order = day_order

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
    # OpportunityViewSet shows a Sales user only their own opportunities.
    visibility = (('crm_app.views.OpportunityViewSet', 'pk'),)

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
    # Its own endpoint's rule, and the opportunity's: the event names the opportunity,
    # which /opportunities/ may hide (a Sales user sees only their own).
    visibility = (('crm_app.views.OpportunityActivityViewSet', 'pk'),
                  ('crm_app.views.OpportunityViewSet', 'opportunity'))

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
    visibility = (('crm_app.views.TicketViewSet', 'pk'),)

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
    visibility = (('crm_app.views.TicketViewSet', 'pk'),)

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
    visibility = (('crm_app.views.TicketCommentViewSet', 'pk'), ('crm_app.views.TicketViewSet', 'ticket'))

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
# Amounts with no currency of their own (Opportunity has no currency field): shown as plain numbers.
_NUMBER_FIELDS = {
    'Opportunity': {'expected_value'},
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


def _norm(f, value):
    """A value as compared to decide whether a field really changed."""
    if value in (None, '', [], {}):
        return None
    if f is not None and f.get_internal_type() == 'BooleanField':
        return value in (True, 'true', 'True', 1)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def changed_keys(model_name: str, changes) -> list[str]:
    """The visible fields a saved row really changed, sorted.

    Pure, so the page and the counts make the same decision: hidden and secret
    fields never count, and neither do fields a writer listed with the same
    value before and after.
    """
    if not isinstance(changes, dict) or model_name not in _FIELD_META:
        return []
    meta = _FIELD_META[model_name]
    collections = _COLLECTIONS.get(model_name, {})
    out = []
    for key, value in changes.items():
        if key in collections:
            pair = _change_pair(value)
            if pair is None or _norm(None, pair[0]) != _norm(None, pair[1]):
                out.append(key)
            continue
        f = meta.get(key)
        pair = _change_pair(value)
        if f is None or pair is None:
            continue
        if _norm(f, pair[0]) != _norm(f, pair[1]):
            out.append(key)
    return sorted(out)


def audit_row_visible(model_name: str, action: str, changes) -> bool:
    """Whether an audit row in scope renders to an event (same rule as AuditSource.to_event)."""
    if action in ('CREATE', 'DELETE'):
        return True
    return bool(changed_keys(model_name, changes))


def _deleted_or_system(additional: dict):
    """The actor of an audit row with no user: a deleted person, or the system itself."""
    # REST writes record the view, MCP writes say via=mcp; both come from a signed-in user.
    if additional.get('view') or additional.get('via') == 'mcp':
        return DELETED_USER
    return SYSTEM_ACTOR


class AuditSource(RowSource):
    """Field changes and status changes on the company and its contacts, contracts,
    quotes and opportunities: one event per save, as the audit log stores it.

    Only Admin sees these, as on ``/audit-logs/``.
    """

    model = AuditLog
    time_field = 'timestamp'
    actor_field = 'user'
    admin_only = True  # ctx.is_admin is the /audit-logs/ permission check itself
    select_related = ('user',)
    visibility = (('crm_app.views.AuditLogViewSet', 'pk'),)

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
        qs = AuditLog.objects.filter(self._scope_q(ctx), self._mode_q())
        for viewset_path, lookup in self.visibility:
            qs = qs.filter(ctx.visibility_q(viewset_path, lookup))
        return qs

    def facet_rows(self, ctx):
        """Counts of rows that render to an event, decided row by row with ``audit_row_visible``.

        One streamed query over this company's audit rows in scope (the cost grows
        with that history; it runs only when counts are asked for).
        """
        qs = self.filtered(ctx, with_actor=False)
        if qs is None:
            return []
        counts: dict[str | None, int] = {}
        rows = qs.order_by().values_list('model_name', 'action', 'changes', 'user_id')
        for model_name, action, changes, user_id in rows.iterator(chunk_size=2000):
            if audit_row_visible(model_name, action, changes):
                key = str(user_id) if user_id else None
                counts[key] = counts.get(key, 0) + 1
        return list(counts.items())

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

    def _currencies(self, row, ctx, changes) -> tuple[str, str]:
        """(currency before, currency after) for money in this save.

        A save that changed the currency gives each side its own. Otherwise the
        record's current currency, or '' when unknown (shown without a currency).
        """
        current = ''
        if row.model_name == 'Contract':
            current = (ctx.contracts.get(row.record_id) or {}).get('currency') or ''
        elif row.model_name == 'Quote':
            current = (ctx.quotes.get(row.record_id) or {}).get('currency') or ''
        pair = _change_pair(changes.get('currency')) if 'currency' in changes else None
        if pair is not None:
            return (str(pair[0] or ''), str(pair[1] or ''))
        return (current, current)

    def _changes(self, row, ctx) -> list:
        model_name = row.model_name
        meta = _FIELD_META.get(model_name, {})
        collections = _COLLECTIONS.get(model_name, {})
        money = _MONEY_FIELDS.get(model_name, set())
        numbers = _NUMBER_FIELDS.get(model_name, set())
        changes = row.changes if isinstance(row.changes, dict) else {}
        old_currency, new_currency = self._currencies(row, ctx, changes)
        out = []
        for key in changed_keys(model_name, changes):
            if key in collections:
                out.append({'field': key, 'label': collections[key], 'kind': 'collection',
                            'old': None, 'new': None})
                continue
            f = meta[key]
            old, new = _change_pair(changes[key])
            label = re.sub(r'([a-z])(\d)', r'\1 \2', str(f.verbose_name))  # "address line1" -> "address line 1"
            label = label[:1].upper() + label[1:]
            if f.is_relation:
                old_l, new_l = self._ref_label(f, old, ctx), self._ref_label(f, new, ctx)
                if (old and not old_l) or (new and not new_l):
                    out.append({'field': key, 'label': label, 'kind': 'opaque', 'old': None, 'new': None})
                else:
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
            elif key in numbers:
                kind = 'number'
            else:
                kind = 'text'
            entry = {'field': key, 'label': label, 'kind': kind,
                     'old': self._render_value(f, old, ctx, kind), 'new': self._render_value(f, new, ctx, kind)}
            if kind == 'money':
                entry['currency'] = new_currency
                entry['old_currency'] = old_currency
            out.append(entry)
        return out

    def to_event(self, row, ctx):
        label, link_type = self._record_label(row, ctx)
        links = [_link(link_type, row.record_id, label)] if link_type and row.action != 'DELETE' else []
        additional = row.additional_data if isinstance(row.additional_data, dict) else {}
        actor = actor_for_user(row.user) or _deleted_or_system(additional)
        if not audit_row_visible(row.model_name, row.action, row.changes):
            return None  # a save that changed nothing visible
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
        QuoteDateSource('quote_sent_date', 'sent_date', 'Sent', 'quote_sent', 'Quote {n} sent', day_order=1),
        QuoteDateSource('quote_accepted_date', 'accepted_date', 'Accepted', 'quote_accepted',
                        'Quote {n} accepted', day_order=2),
        QuoteDateSource('quote_rejected_date', 'rejected_date', 'Rejected', 'quote_declined',
                        'Quote {n} declined', day_order=2),
        QuoteDateSource('quote_expired_date', 'expired_date', 'Expired', 'quote_expired', 'Quote {n} expired',
                        day_order=3),
        ContractCreatedSource(),
        ContractDateSource('contract_sent', 'sent_date', 'contract_sent', 'Contract {n} sent',
                           audited_status='Sent', day_order=1),
        ContractDateSource('contract_signed', 'signed_date', 'contract_signed', 'Contract {n} signed', day_order=2),
        InvoiceDateSource('invoice_issued', 'issue_date', 'invoice_issued', 'Invoice {n} issued',
                          ~Q(status='Draft'), day_order=1),
        InvoiceDateSource('invoice_paid', 'paid_date', 'invoice_paid', 'Invoice {n} paid',
                          Q(paid_date__isnull=False), day_order=2),
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
    """One page of events, newest first, merged from every active source.

    Each round asks every source that may still hold rows for its next batch
    below the current position. The cut-off is the highest point down to which
    every such source has been read completely; only events at or above it are
    certain to be in the right place. Rows that render to nothing (a save that
    changed no visible field) can leave a round short, so the page reads on, up
    to EXTRA_ROUNDS more rounds of up to EXTRA_ROUND_LIMIT rows. If it is still
    short after that, it returns what it has with ``has_more`` and the cut-off as
    the cursor: ``has_more`` means older history is still unread, and an empty
    page with ``has_more`` is possible only after that many unseen rows.
    """
    sources = [s for s in (sources if sources is not None else registry.sources()) if s.active(ctx)]
    if ctx.record_hidden():
        sources = []
    open_sources = sources       # sources that may still hold rows below the position
    pool: list = []              # events read but not yet delivered
    page: list = []
    position = cursor
    cutoff = None
    for round_no in range(1 + EXTRA_ROUNDS):
        limit = page_size if round_no == 0 else max(page_size, EXTRA_ROUND_LIMIT)
        floors, still_open = [], []
        for source in open_sources:
            result = source.fetch(ctx, position, limit)
            pool.extend(result.events)
            if result.complete_until is not None:
                floors.append(result.complete_until)
                still_open.append(source)
        open_sources = still_open
        # Below the highest floor, some source may still hold events it did not return.
        cutoff = max(floors) if floors else None
        pool.sort(key=lambda e: e.sort_key, reverse=True)
        ready = [e for e in pool if cutoff is None or e.sort_key >= cutoff]
        need = page_size - len(page)
        page.extend(ready[:need])
        if len(ready) >= need:
            # With no cut-off every source is exhausted and the whole pool was ready.
            more = len(ready) > need or cutoff is not None
            next_cursor = Cursor(*page[-1].sort_key) if more and page else None
            break
        if cutoff is None:
            next_cursor = None   # every source is exhausted and everything was delivered
            break
        # Everything at or above the cut-off is delivered. Keep what lies below it only
        # from sources that are done; the open ones are read again from the cut-off.
        open_keys = {s.key for s in open_sources}
        pool = [e for e in pool if e.sort_key < cutoff and e.id.partition(':')[0] not in open_keys]
        position = Cursor(*cutoff)
    else:
        next_cursor = Cursor(*cutoff)  # out of rounds: everything at or above the cut-off is delivered
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
    hidden = ctx.record_hidden()
    for source in registry.sources():
        if hidden or not source.available(ctx):
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
