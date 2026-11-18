"""Read-only REST surface for the Renewals page (/renewals in the app).

GET /api/v1/renewals/?year=2026&month=11[&entity=th|hk][&basis=funnel|calendar]
GET /api/v1/renewals/?view=open&year=2026[&entity=th|hk][&basis=funnel|calendar]

basis=funnel (default): the tab for month N holds terms ending from the last day
of N-1 to the day before the last day of N, as the renewal funnel sheets do.

Signed-in users only (the project default). It reads; it never writes. The
Renewal Book endpoint and MCP tool are unchanged; each row here embeds the
Renewal Book row for the term. See ``services/renewals_page_service.py``.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app.services.renewals_page_service import build_renewals_view


class RenewalsView(APIView):
    def get(self, request):
        params = request.query_params
        today = timezone.localdate()
        view = params.get('view') or 'month'
        for name in ('year', 'month'):
            raw = params.get(name)
            if raw and not raw.strip().isdigit():
                return self._bad(f'{name} must be a whole number')
        try:
            data = build_renewals_view(
                year=params.get('year') or today.year,
                month=params.get('month') or (today.month if view == 'month' else None),
                view=view,
                entity=params.get('entity') or '',
                basis=params.get('basis') or 'funnel',
                today=today,
            )
        except (TypeError, ValueError) as exc:
            return self._bad(str(exc))
        response = Response(data)
        response['Cache-Control'] = 'private, no-store'
        return response

    @staticmethod
    def _bad(message):
        return Response(
            {'error': message, 'example': '/api/v1/renewals/?year=2026&month=11&entity=th'},
            status=status.HTTP_400_BAD_REQUEST,
        )
