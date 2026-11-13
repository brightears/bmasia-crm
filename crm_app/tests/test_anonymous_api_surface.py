"""The set of DRF endpoints an anonymous caller can reach is fixed and explicit.

Every routed DRF view is checked the way DRF itself checks it before the
handler runs: the view's own get_permissions() for the action the route maps
to, evaluated against an anonymous request. Anything that admits the
anonymous request must be listed in ANONYMOUS_ALLOWLIST. A new viewset that
forgets permission_classes is covered by the IsAuthenticated default; one
that sets AllowAny (or an equivalent) on purpose must be added here, so the
decision is reviewed.

Non-DRF Django views (admin, the browsable-API login page, the e-mail open
tracking pixel, the root redirect) are not covered here; they do not use DRF
permissions at all.
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

# (route as written in the URLconf, HTTP method)
ANONYMOUS_ALLOWLIST = {
    # Frontend login / token refresh / logout (logout tolerates expired sessions)
    ("api/v1/auth/login/", "POST"),
    ("api/v1/auth/refresh/", "POST"),
    ("api/v1/auth/logout/", "POST"),
    # simplejwt obtain / refresh / verify
    ("api/v1/jwt/token/", "POST"),
    ("api/v1/jwt/token/refresh/", "POST"),
    ("api/v1/jwt/token/verify/", "POST"),
    # DRF token obtain (legacy route and the root-level route agents use)
    ("api/auth/token/", "POST"),
    ("api-token-auth/", "POST"),
}

# Non-DRF routes that are meant to be reachable without DRF permissions.
# Listed so a reviewer sees them; each one enforces its own access rule.
EXPECTED_NON_DRF_PUBLIC_PREFIXES = (
    "admin/",  # Django admin: its own staff login
    "api-auth/",  # DRF browsable-API session login/logout pages
    "t/<str:token>/",  # e-mail open tracking pixel, called by mail clients
    "",  # root redirect to /admin/
)


def _walk(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern), pattern


def _drf_routes():
    for route, pattern in _walk(get_resolver().url_patterns):
        view_cls = getattr(pattern.callback, "cls", None)
        if view_cls is None or not issubclass(view_cls, APIView):
            continue
        yield route, pattern.callback


def _methods(callback):
    actions = getattr(callback, "actions", None)
    if actions:
        return {method.upper(): action for method, action in actions.items()}
    view_cls = callback.cls
    return {
        method.upper(): None
        for method in view_cls.http_method_names
        if method not in ("options", "head") and hasattr(view_cls, method)
    }


def _admits_anonymous(callback, method, action):
    view = callback.cls(**getattr(callback, "initkwargs", {}))
    django_request = getattr(APIRequestFactory(), method.lower())("/")
    request = Request(django_request)
    request.user = AnonymousUser()
    request.auth = None
    view.request = request
    view.args, view.kwargs, view.format_kwarg = (), {}, None
    view.headers = {}
    if getattr(callback, "actions", None):
        view.action_map = callback.actions
        view.action = action
    return all(p.has_permission(request, view) for p in view.get_permissions())


def _anonymous_drf_endpoints():
    reachable = set()
    for route, callback in _drf_routes():
        for method, action in _methods(callback).items():
            if _admits_anonymous(callback, method, action):
                reachable.add((route, method))
    return reachable


def test_default_permission_is_is_authenticated():
    from rest_framework.permissions import IsAuthenticated

    assert list(api_settings.DEFAULT_PERMISSION_CLASSES) == [IsAuthenticated]


def test_walker_finds_the_api():
    routes = {route for route, _ in _drf_routes()}
    # Sanity check so a broken walker cannot pass the allowlist test vacuously.
    assert len(routes) > 100
    assert "api/v1/auth/me/" in routes
    assert "mcp/" in routes


def test_anonymously_reachable_drf_endpoints_match_allowlist():
    assert _anonymous_drf_endpoints() == ANONYMOUS_ALLOWLIST


@pytest.mark.parametrize(
    "path",
    ["/api/v1/companies/", "/api/v1/contracts/", "/api/v1/", "/mcp/"],
)
def test_representative_endpoints_reject_anonymous(client, path):
    response = client.get(path)

    assert response.status_code in (401, 403)


def test_non_drf_routes_are_the_expected_ones():
    unexpected = []
    for route, pattern in _walk(get_resolver().url_patterns):
        view_cls = getattr(pattern.callback, "cls", None)
        if view_cls is not None and issubclass(view_cls, APIView):
            continue
        if route.startswith("api/admin/"):
            # crm_app.admin_views: every one is @staff_member_required
            assert getattr(pattern.callback, "__module__", "") == "crm_app.admin_views"
            continue
        if route == "" or any(
            prefix and route.startswith(prefix)
            for prefix in EXPECTED_NON_DRF_PUBLIC_PREFIXES
        ):
            continue
        unexpected.append(route)

    assert unexpected == []
