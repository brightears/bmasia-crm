"""Record how each API caller authenticated. Observability only.

Nothing here accepts, refuses or changes a request. After a view has run, the
authentication method is derived from what Django REST framework left on the
request (``request.auth`` and ``request.user``), plus one flag that
``crm_app.mcp_auth`` sets when a token arrived as a query parameter.

The method and the caller's agent principal are added to MCP audit rows and
the agent-gate ledger, and one ``crm_auth`` log line is written per request
that matters for credential housekeeping:

* every authenticated request to ``/mcp/``;
* ``/api/`` requests made with a token-style credential or by an agent principal
  (website logins using JWT or a session are not logged);
* refused requests to either surface that presented a credential.

Log lines name the path without its query string, the auth method, the user,
the principal, the status, the client address and the user agent. They never
contain a credential: tokens are not read here, only the type of credential.
"""
from __future__ import annotations

import ipaddress
import logging

logger = logging.getLogger('crm_app.auth')

# Auth method names (stable strings; they appear in logs and JSON records).
TOKEN_HEADER = 'token_header'
TOKEN_QUERY = 'token_query'
JWT = 'jwt'
SESSION = 'session'
RENE_BEARER = 'rene_bearer'
RENE_MCP = 'rene_mcp'
CARA_BEARER = 'cara_bearer'
ANONYMOUS = 'anonymous'
OTHER = 'other'

TOKEN_STYLE_METHODS = frozenset({TOKEN_HEADER, TOKEN_QUERY, RENE_BEARER, RENE_MCP, CARA_BEARER})

# Protocol gap recorded on agent-gate rows when the credential came in the URL.
CREDENTIAL_IN_URL = 'credential_in_url'

_QUERY_FLAG = '_crm_token_from_query'
_OBSERVED_PREFIXES = ('/mcp', '/api/')
_MAX_UA, _MAX_PATH = 160, 160


def _django_request(request):
    """The underlying Django HttpRequest for a DRF Request, or the request itself."""
    return getattr(request, '_request', None) or request


def mark_query_token(request) -> None:
    """Flag that this request authenticated with a token taken from the query string."""
    try:
        setattr(_django_request(request), _QUERY_FLAG, True)
    except Exception:  # pragma: no cover - read-only request stand-ins
        pass


def auth_method(request) -> str:
    """Name of the credential type that authenticated ``request``; never raises."""
    if request is None:
        return ANONYMOUS
    try:
        user = getattr(request, 'user', None)
        auth = getattr(request, 'auth', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return ANONYMOUS
        from rest_framework.authtoken.models import Token
        if isinstance(auth, Token):
            if getattr(_django_request(request), _QUERY_FLAG, False):
                return TOKEN_QUERY
            return TOKEN_HEADER
        from rest_framework_simplejwt.tokens import Token as JWTToken
        if isinstance(auth, JWTToken):
            return JWT
        from crm_app.rene_auth import RenePhase2MCPCredential, ReneRenewalPrincipal
        if isinstance(auth, RenePhase2MCPCredential):
            return RENE_MCP
        if isinstance(user, ReneRenewalPrincipal):
            return RENE_BEARER
        from crm_app.cara_api import CaraPrincipal
        if isinstance(user, CaraPrincipal):
            return CARA_BEARER
        if auth is None:
            return SESSION
        return OTHER
    except Exception:  # pragma: no cover - never let observability break a request
        logger.debug('auth method could not be determined', exc_info=True)
        return OTHER


def principal_name(user) -> str:
    """The agent-policy principal for a user, or '' for humans and anonymous callers."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return ''
    from crm_app import agent_policy
    principal = agent_policy.principal_for_username(getattr(user, 'username', '') or '')
    return principal.name if principal else ''


def presented_credential(request) -> str:
    """Which kind of credential a request offered: scheme or 'query', never the value."""
    meta = getattr(request, 'META', None) or {}
    header = str(meta.get('HTTP_AUTHORIZATION', '') or '')
    if header:
        scheme = header.split(' ', 1)[0]
        return 'header:' + (scheme if scheme in ('Token', 'Bearer', 'Rene') else 'other')
    query = getattr(request, 'GET', None)
    if query is not None and 'token' in query:
        return 'query'
    return 'none'


def client_ip(meta) -> str:
    forwarded = str(meta.get('HTTP_X_FORWARDED_FOR', '') or '')
    raw = forwarded.split(',')[0].strip() if forwarded else str(meta.get('REMOTE_ADDR', '') or '')
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return '-'


def _clean(value, limit):
    text = str(value or '-').replace('"', "'").replace('\n', ' ').replace('\r', ' ')
    return text[:limit]


def describe(request) -> dict:
    """Auth method and principal for audit records (JSON-safe, no credential)."""
    return {
        'auth_method': auth_method(request),
        'principal': principal_name(getattr(request, 'user', None)) if request is not None else '',
    }


def _should_log(path, method, principal, status, presented):
    if not path.startswith(_OBSERVED_PREFIXES):
        return False
    if method == ANONYMOUS:
        return status in (401, 403) and presented != 'none'
    if path.startswith('/mcp'):
        return True
    return method in TOKEN_STYLE_METHODS or bool(principal)


class AuthObservabilityMiddleware:
    """Write one ``crm_auth`` line for MCP and token-authenticated API requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            path = request.path or ''
            if path.startswith(_OBSERVED_PREFIXES):
                method = auth_method(request)
                user = getattr(request, 'user', None)
                principal = principal_name(user)
                status = getattr(response, 'status_code', 0)
                presented = presented_credential(request)
                if _should_log(path, method, principal, status, presented):
                    username = getattr(user, 'username', '') if method != ANONYMOUS else ''
                    logger.info(
                        'crm_auth path=%s method=%s presented=%s user=%s principal=%s status=%s ip=%s ua="%s"',
                        _clean(path, _MAX_PATH), method, presented, _clean(username, 150),
                        principal or '-', status, client_ip(request.META), _clean(
                            request.META.get('HTTP_USER_AGENT', ''), _MAX_UA),
                    )
        except Exception:  # pragma: no cover - observability must never break a response
            logger.debug('auth observability failed', exc_info=True)
        return response
