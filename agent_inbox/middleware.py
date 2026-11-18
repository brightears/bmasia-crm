"""Answer 409 when a company delete is blocked by the activity log or the proposal queue.

Activity.company and ChangeProposal.company are PROTECT, so deleting a company
that has either raises ProtectedError, which would otherwise end in a server
error. The two company delete requests (``DELETE /api/v1/companies/{id}/`` and
``POST /api/v1/companies/bulk_operations/``) run in one transaction here, so
nothing they wrote before the refusal (such as audit rows) is kept. Only those
two requests are wrapped or answered; everything else passes through unchanged.

When a project-wide delete guard is in place (one that refuses the delete before
it is attempted and answers protected-record errors itself), this middleware
never acts and can be removed together with its line in settings.MIDDLEWARE.
"""
import re

from django.db import transaction
from django.db.models import ProtectedError
from django.http import JsonResponse

_WRAPPED = (
    ('DELETE', re.compile(r'^/api/v1/companies/[0-9a-fA-F-]{36}/$')),
    ('POST', re.compile(r'^/api/v1/companies/bulk_operations/$')),
)


def _is_company_delete(request):
    return any(request.method == method and pattern.match(request.path) for method, pattern in _WRAPPED)


class InboxProtectedDeleteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _is_company_delete(request):
            return self.get_response(request)
        with transaction.atomic():
            response = self.get_response(request)
            if getattr(request, '_inbox_delete_refused', False) or response.status_code >= 400:
                transaction.set_rollback(True)
        return response

    def process_exception(self, request, exception):
        if not isinstance(exception, ProtectedError) or not _is_company_delete(request):
            return None
        from agent_inbox.models import Activity, ChangeProposal

        protected = list(exception.protected_objects)
        activities = sum(isinstance(obj, Activity) for obj in protected)
        proposals = sum(isinstance(obj, ChangeProposal) for obj in protected)
        if not (activities or proposals):
            return None
        request._inbox_delete_refused = True
        return JsonResponse({
            'error': ('This company has logged activities or change proposals, so it cannot be deleted. '
                      'Set it inactive instead (is_active = false).'),
            'code': 'has_activity_history',
            'activities': activities,
            'change_proposals': proposals,
        }, status=409)
