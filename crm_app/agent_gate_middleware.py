"""Phase 1 Stage A: record agent writes made through the REST API (observe only).

Covers every /api/v1/ viewset (many do not inherit BaseModelViewSet). Runs after
the view, when DRF has stored the authenticated user on the Django request, and
only records callers that are listed agent principals. Never blocks or alters the
response. Field names are not captured here (the parsed body lives on DRF's
request object); the MCP tools are the intended agent write path.
"""
from crm_app.services import agent_gate

_REST_VERBS = {'POST': 'create', 'PUT': 'update', 'PATCH': 'update', 'DELETE': 'delete'}


def _collection(url_name):
    name = url_name or ''
    for suffix in ('-detail', '-list'):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


class AgentGateRestObserverMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        verb = _REST_VERBS.get(request.method)
        if verb and request.path.startswith('/api/v1/'):
            user = getattr(request, 'user', None)
            if user is not None and getattr(user, 'is_authenticated', False):
                match = getattr(request, 'resolver_match', None)
                url_name = getattr(match, 'url_name', '') or ''
                agent_gate.observe(
                    tool=f'rest:{url_name}'[:60], verb=verb, collection=_collection(url_name),
                    record_id=(getattr(match, 'kwargs', None) or {}).get('pk', ''), user=user,
                )
        return response
