"""Read-only API view for the company timeline (see crm_app/timeline.py)."""
from __future__ import annotations

import uuid
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app import timeline
from crm_app.models import Company


class TimelineQueryError(ValueError):
    pass


def _uuid(value: str, name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise TimelineQueryError(f'{name} must be a UUID')


def _date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise TimelineQueryError(f'{name} must be a date (YYYY-MM-DD)')


def parse_filters(params) -> tuple[timeline.Filters, timeline.Cursor | None, int, bool]:
    filters = timeline.Filters()

    types = [t.strip() for t in params.get('types', '').split(',') if t.strip()]
    unknown = sorted(set(types) - set(timeline.CATEGORIES))
    if unknown:
        raise TimelineQueryError(f'unknown types: {", ".join(unknown)}')
    if types:
        filters.categories = frozenset(types)

    if params.get('from'):
        filters.date_from = _date(params['from'], 'from')
    if params.get('to'):
        filters.date_to = _date(params['to'], 'to')
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise TimelineQueryError('from must not be after to')

    record = params.get('record', '').strip()
    if record:
        record_type, _, record_id = record.partition(':')
        if record_type not in timeline.RECORD_TYPES:
            raise TimelineQueryError(f'record type must be one of: {", ".join(timeline.RECORD_TYPES)}')
        filters.record_type = record_type
        filters.record_id = _uuid(record_id, 'record id')

    if params.get('actor'):
        filters.actor_id = _uuid(params['actor'], 'actor')

    filters.search = params.get('q', '').strip()[:200]

    cursor = None
    if params.get('cursor'):
        try:
            cursor = timeline.Cursor.decode(params['cursor'])
        except ValueError:
            raise TimelineQueryError('invalid cursor')

    try:
        page_size = int(params.get('page_size', timeline.DEFAULT_PAGE_SIZE))
    except ValueError:
        raise TimelineQueryError('page_size must be a number')
    page_size = max(1, min(page_size, timeline.MAX_PAGE_SIZE))

    facets = params.get('facets') in ('1', 'true')
    return filters, cursor, page_size, facets


class CompanyTimelineView(APIView):
    """``GET /api/v1/companies/<id>/timeline/``: the company's merged activity, newest first.

    Query parameters (all optional):

    * ``types``: comma-separated categories (``note,task,email,care,quote,contract,
      invoice,opportunity,ticket,change``)
    * ``from`` / ``to``: dates, inclusive, in the CRM's time zone
    * ``record``: ``<type>:<uuid>`` to show one record's events (contract, quote, contact,
      opportunity, ticket, task, invoice)
    * ``actor``: a user id
    * ``q``: free text over what the titles and details are made of
    * ``cursor``: ``next_cursor`` from the previous page; ``page_size`` (1-100, default 25)
    * ``facets=1``: also return counts per type and per person
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id)
        try:
            filters, cursor, page_size, facets = parse_filters(request.query_params)
        except TimelineQueryError as exc:
            return Response({'error': str(exc)}, status=400)
        ctx = timeline.TimelineContext(company, request.user, filters)
        data = timeline.build_page(ctx, cursor, page_size)
        if facets:
            data['facets'] = timeline.build_facets(ctx)
        data['categories'] = [{'key': k, 'label': v} for k, v in timeline.CATEGORIES.items()]
        response = Response(data)
        response['Cache-Control'] = 'private, no-store'
        return response
