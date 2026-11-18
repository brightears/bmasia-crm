"""Read-only REST surface for the Renewals page (/renewals in the app).

GET /api/v1/renewals/?year=2026&month=11[&entity=th|hk]
GET /api/v1/renewals/?view=open&year=2026[&entity=th|hk]

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
        try:
            data = build_renewals_view(
                year=params.get('year') or today.year,
                month=params.get('month') or (today.month if view == 'month' else None),
                view=view,
                entity=params.get('entity') or '',
                today=today,
            )
        except (TypeError, ValueError) as exc:
            return Response(
                {'error': str(exc) if isinstance(exc, ValueError) and 'must' in str(exc)
                 else 'year and month must be whole numbers',
                 'example': '/api/v1/renewals/?year=2026&month=11&entity=th'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(data)
        response['Cache-Control'] = 'private, no-store'
        return response
