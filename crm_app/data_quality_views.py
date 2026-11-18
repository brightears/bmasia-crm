"""Read-only API for the data-quality checks in ``crm_app.data_quality``.

GET /api/v1/data-quality/               every check: key, title, why, severity, count, first rows
GET /api/v1/data-quality/<key>/         one check's rows, paged; ?company=, ?owner= (user id or
                                        "none"), ?page=, ?page_size=; ?export=csv for all rows
Same authentication as the rest of the API (the DRF default, IsAuthenticated). GET only.
"""
import csv
import io
import uuid

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app import data_quality as dq

DEFAULT_SUMMARY_ROWS = 5
MAX_SUMMARY_ROWS = 20
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

CSV_COLUMNS = ['check', 'record_type', 'label', 'company', 'fact', 'owner', 'date', 'amount', 'currency',
               'link', 'record_id', 'company_id']


class BadRequest(Exception):
    pass


def _int(request, name, default, low, high):
    raw = request.query_params.get(name)
    if raw in (None, ''):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f'{name} must be a whole number')
    if not low <= value <= high:
        raise BadRequest(f'{name} must be between {low} and {high}')
    return value


def _uuid(request, name, allow_none=False):
    raw = (request.query_params.get(name) or '').strip()
    if not raw:
        return None
    if allow_none and raw == 'none':
        return 'none'
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise BadRequest(f'{name} must be an id' + (' or "none"' if allow_none else ''))


def _filters(request):
    return dq.Filters(company_id=_uuid(request, 'company'), owner_id=_uuid(request, 'owner', allow_none=True))


# A text cell starting with one of these is prefixed with an apostrophe, so no spreadsheet
# reads it as a formula (full-width forms and leading spaces or quotes included).
_CSV_RISKY_START = ('=', '+', '-', '@', '\t', '\r', '\n', ' ', '\u00a0', '"', "'", '\uff1d', '\uff0b', '\uff0d', '\uff20')


def _csv_cell(value):
    """Plain text for spreadsheets: a cell never starts with a formula character."""
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(_CSV_RISKY_START) else text


def _no_store(response):
    response['Cache-Control'] = 'no-store'
    return response


class DataQualitySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rows = _int(request, 'rows', DEFAULT_SUMMARY_ROWS, 0, MAX_SUMMARY_ROWS)
            filters = _filters(request)
        except BadRequest as e:
            return Response({'detail': str(e)}, status=400)
        ctx = dq.Context()
        checks = dq.summary(ctx, filters, rows_per_check=rows)
        return _no_store(Response({
            'today': ctx.today.isoformat(),
            'generated_at': timezone.now().isoformat(),
            'checks': checks,
            'total': sum(c['count'] for c in checks),
            'clear': sum(1 for c in checks if c['count'] == 0),
        }))


class DataQualityCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        check = dq.CHECKS_BY_KEY.get(key)
        if check is None:
            return Response({'detail': 'Unknown check.', 'checks': list(dq.CHECKS_BY_KEY)}, status=404)
        try:
            filters = _filters(request)
            page = _int(request, 'page', 1, 1, 100000)
            page_size = _int(request, 'page_size', DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
        except BadRequest as e:
            return Response({'detail': str(e)}, status=400)
        ctx = dq.Context()
        if (request.query_params.get('export') or '').lower() == 'csv':
            return self._csv(check, ctx, filters)
        count = check.count(ctx, filters)
        rows = check.rows(ctx, filters, (page - 1) * page_size, page_size)
        return _no_store(Response(check.meta() | {
            'today': ctx.today.isoformat(),
            'count': count,
            'page': page,
            'page_size': page_size,
            'rows': rows,
        }))

    def _csv(self, check, ctx, filters):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for r in check.rows(ctx, filters):
            # The amount is a number the server wrote (it may be negative), so it is not escaped.
            writer.writerow([
                *[_csv_cell(v) for v in (check.title, r['record_type'], r['label'], r['company_name'], r['fact'],
                                         r['owner_name'], r['date'])],
                r['amount'] or '',
                *[_csv_cell(v) for v in (r['currency'], r['link'], r['id'], r['company_id'])],
            ])
        response = HttpResponse('﻿' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="needs-fixing-{check.key}-{ctx.today.isoformat()}.csv"'
        return _no_store(response)
