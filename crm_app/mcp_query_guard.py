"""Fail-closed guard for the MCP query tool at the HTTP layer.

The published-field boundary of ``query_data_collections`` is a wrapper around
a private method of django-mcp-server (``crm_app.mcp_query_help.install``). If
that wrapper is not in place, for example after a library upgrade, this
middleware answers every ``tools/call`` of ``query_data_collections`` on the MCP
endpoint with a fixed refusal instead of letting the library run unchecked.

It relies only on the MCP JSON-RPC message shape and the endpoint path, not on
any library internals. While the boundary is active it does nothing beyond a
path and method comparison.
"""
import json

from django.conf import settings
from django.http import JsonResponse

from crm_app.mcp_query_help import QUERY_UNAVAILABLE_MESSAGE, boundary_active

QUERY_TOOL = 'query_data_collections'


def _endpoint_path():
    return '/' + str(getattr(settings, 'DJANGO_MCP_ENDPOINT', 'mcp')).lstrip('/')


def _refusal(message_id):
    return {
        'jsonrpc': '2.0',
        'id': message_id,
        'result': {'content': [{'type': 'text', 'text': QUERY_UNAVAILABLE_MESSAGE}], 'isError': True},
    }


def _calls_query_tool(message):
    params = message.get('params') if isinstance(message, dict) else None
    return (isinstance(message, dict) and message.get('method') == 'tools/call'
            and isinstance(params, dict) and params.get('name') == QUERY_TOOL)


class MCPQueryGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == _endpoint_path() and not boundary_active():
            try:
                payload = json.loads(request.body or b'null')
            except (ValueError, UnicodeDecodeError):
                payload = None
            messages = payload if isinstance(payload, list) else [payload]
            if any(_calls_query_tool(message) for message in messages):
                if isinstance(payload, list):
                    return JsonResponse([_refusal(m.get('id')) for m in messages if isinstance(m, dict)
                                         and 'id' in m], safe=False)
                return JsonResponse(_refusal(payload.get('id')))
        return self.get_response(request)
