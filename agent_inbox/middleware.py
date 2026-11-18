"""Answer 409 when a company delete is blocked by the activity log or the proposal queue.

Activity.company and ChangeProposal.company are PROTECT, so deleting a company
that has either raises ProtectedError, which would otherwise end in a server
error. The company delete request runs in one transaction here, so nothing it
wrote before the refusal (such as its audit row) is kept. Other requests and
other protected deletes are left to the existing handling.
"""
import re

from django.db import transaction
from django.db.models import ProtectedError
from django.http import JsonResponse

_COMPANY_DELETE = re.compile(r'^/api/v1/companies/[^/]+/$')


class InboxProtectedDeleteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'DELETE' or not _COMPANY_DELETE.match(request.path):
            return self.get_response(request)
        with transaction.atomic():
            response = self.get_response(request)
            if getattr(request, '_inbox_delete_refused', False):
                transaction.set_rollback(True)
        return response

    def process_exception(self, request, exception):
        if not isinstance(exception, ProtectedError) or not _COMPANY_DELETE.match(request.path):
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
