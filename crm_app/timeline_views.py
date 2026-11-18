"""Read-only API view for the company timeline (see crm_app/timeline.py).

Every query parameter is checked here, before any query runs: anything the
timeline cannot use is a 400 with a message saying which parameter and why,
never a 500.
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app import timeline
from crm_app.models import Company

MAX_CURSOR_LENGTH = 512
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_SEARCH_WHITESPACE = re.compile(r'[\t\n\r]+')
_ASCII_DIGITS = re.compile(r'^[0-9]{1,4}$')


class TimelineQueryError(ValueError):
    def __init__(self, message: str, param: str):
        super().__init__(message)
        self.param = param


def _uuid(value: str, name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise TimelineQueryError(f'{name} must be a UUID', name)


def _date(value: str, name: str) -> date:
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise TimelineQueryError(f'{name} must be a date (YYYY-MM-DD)', name)
    if not timeline.MIN_YEAR <= day.year <= timeline.MAX_YEAR:
        raise TimelineQueryError(
            f'{name} must be between {timeline.MIN_YEAR} and {timeline.MAX_YEAR}', name)
    return day


def _text(params, name: str) -> str:
    value = params.get(name, '')
    if _CONTROL.search(value):
        raise TimelineQueryError(f'{name} must not contain control characters', name)
    return value


def parse_filters(params) -> tuple[timeline.Filters, timeline.Cursor | None, int, bool]:
    filters = timeline.Filters()

    types = [t.strip() for t in _text(params, 'types').split(',') if t.strip()]
    unknown = sorted(set(types) - set(timeline.CATEGORIES))
    if unknown:
        raise TimelineQueryError(f'unknown types: {", ".join(unknown)[:200]}', 'types')
    if types:
        filters.categories = frozenset(types)

    if params.get('from'):
        filters.date_from = _date(_text(params, 'from'), 'from')
    if params.get('to'):
        filters.date_to = _date(_text(params, 'to'), 'to')
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise TimelineQueryError('from must not be after to', 'from')

    record = _text(params, 'record').strip()
    if record:
        record_type, _, record_id = record.partition(':')
        if record_type not in timeline.RECORD_TYPES:
            raise TimelineQueryError(f'record type must be one of: {", ".join(timeline.RECORD_TYPES)}', 'record')
        filters.record_type = record_type
        filters.record_id = _uuid(record_id, 'record')

    if params.get('actor'):
        filters.actor_id = _uuid(_text(params, 'actor'), 'actor')

    # Tabs and line breaks (a paste) read as spaces; other control characters are refused.
    search = _SEARCH_WHITESPACE.sub(' ', params.get('q', ''))
    if _CONTROL.search(search):
        raise TimelineQueryError('q must not contain control characters', 'q')
    search = search.strip()
    if len(search) > timeline.MAX_SEARCH_LENGTH:
        raise TimelineQueryError(f'q must be at most {timeline.MAX_SEARCH_LENGTH} characters', 'q')
    filters.search = search

    cursor = None
    raw_cursor = _text(params, 'cursor')
    if raw_cursor:
        if len(raw_cursor) > MAX_CURSOR_LENGTH:
            raise TimelineQueryError('invalid cursor', 'cursor')
        try:
            cursor = timeline.Cursor.decode(raw_cursor)
        except ValueError:
            raise TimelineQueryError('invalid cursor', 'cursor')
        source = timeline.registry.get(cursor.source_key)
        if source is not None and not source.valid_cursor_pk(cursor.source_pk):
            raise TimelineQueryError('invalid cursor', 'cursor')

    raw_size = _text(params, 'page_size').strip()
    if raw_size:
        # ASCII digits only: str.isdigit() also accepts "²", which int() refuses.
        if not _ASCII_DIGITS.match(raw_size) or not 1 <= int(raw_size) <= timeline.MAX_PAGE_SIZE:
            raise TimelineQueryError(f'page_size must be a whole number from 1 to {timeline.MAX_PAGE_SIZE}',
                                     'page_size')
        page_size = int(raw_size)
    else:
        page_size = timeline.DEFAULT_PAGE_SIZE

    facets = params.get('facets') in ('1', 'true')
    return filters, cursor, page_size, facets


def visible_company(user, company_id):
    """The company, if /companies/ lets this user open it (its own get_queryset)."""
    shown = timeline.viewset_queryset('crm_app.views.CompanyViewSet', user)
    if timeline.restricts(shown) and not shown.filter(pk=company_id).exists():
        raise Http404
    try:
        return Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        raise Http404


class CompanyTimelineView(APIView):
    """``GET /api/v1/companies/<id>/timeline/``: the company's merged activity, newest first.

    Query parameters (all optional):

    * ``types``: comma-separated categories (``note,task,email,care,quote,contract,
      invoice,opportunity,ticket,change``)
    * ``from`` / ``to``: dates, inclusive, in the CRM's time zone (years 1900-9998)
    * ``record``: ``<type>:<uuid>`` to show one record's events (contract, quote, contact,
      opportunity, ticket, task, invoice)
    * ``actor``: a user id
    * ``q``: free text (at most 200 characters) over what titles and details are made of
    * ``cursor``: ``next_cursor`` from the previous page; ``page_size`` (1-100, default 25)
    * ``facets=1``: also return counts per type and per person

    A parameter the timeline cannot use gives 400 ``{"error": ..., "param": ...}``.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        company = visible_company(request.user, company_id)
        try:
            filters, cursor, page_size, facets = parse_filters(request.query_params)
        except TimelineQueryError as exc:
            return Response({'error': str(exc), 'param': exc.param}, status=400)
        ctx = timeline.TimelineContext(company, request.user, filters)
        data = timeline.build_page(ctx, cursor, page_size)
        if facets:
            data['facets'] = timeline.build_facets(ctx)
        data['categories'] = [{'key': k, 'label': v} for k, v in timeline.CATEGORIES.items()]
        response = Response(data)
        response['Cache-Control'] = 'private, no-store'
        return response
