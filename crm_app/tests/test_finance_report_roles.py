"""Finance reports and the QuickBooks export answer the Finance and Admin roles only.

Every routed action of the finance report viewsets is checked the way DRF checks it
before the handler runs (the view's own get_permissions() for that action), for each
server role. A few real requests confirm the refusal end to end.
"""
import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from crm_app import views
from crm_app.models import User

FINANCE_VIEWSETS = {
    views.RevenueViewSet,
    views.ARAgingViewSet,
    views.APAgingViewSet,
    views.ProfitLossViewSet,
    views.CashFlowViewSet,
    views.BalanceSheetViewSet,
    views.RevenueRecognitionViewSet,
}
ROLES = ['Admin', 'Finance', 'Sales', 'Tech', 'Music', '']
ALLOWED = {'Admin', 'Finance'}


def _walk(patterns, prefix=''):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern), pattern.callback


def _guarded_endpoints():
    """(route, method, callback, action) for every finance report action and the IIF export."""
    found = []
    for route, callback in _walk(get_resolver().url_patterns):
        cls = getattr(callback, 'cls', None)
        actions = getattr(callback, 'actions', None) or {}
        if cls in FINANCE_VIEWSETS:
            found += [(route, m.upper(), callback, a) for m, a in actions.items()]
        elif cls is views.InvoiceViewSet and actions.get('get') == 'export_quickbooks':
            found.append((route, 'GET', callback, 'export_quickbooks'))
    return found


def _user(role, active=True):
    return User(username=f'role-{role or "blank"}', role=role, is_active=active)


def _admits(callback, method, action, user):
    view = callback.cls(**getattr(callback, 'initkwargs', {}))
    request = Request(getattr(APIRequestFactory(), method.lower())('/'))
    request.user = user
    request.auth = None
    view.request = request
    view.args, view.kwargs, view.format_kwarg = (), {}, None
    view.headers = {}
    view.action_map = callback.actions
    view.action = action
    return all(p.has_permission(request, view) for p in view.get_permissions())


def test_walker_finds_every_finance_viewset_and_the_export():
    endpoints = _guarded_endpoints()
    assert {cb.cls for _, _, cb, _ in endpoints} == FINANCE_VIEWSETS | {views.InvoiceViewSet}
    assert len(endpoints) > 40
    assert any(a == 'export_quickbooks' for _, _, _, a in endpoints)


@pytest.mark.parametrize('role', ROLES)
def test_finance_endpoints_follow_the_role(role):
    wrong = [
        f'{method} {route}'
        for route, method, callback, action in _guarded_endpoints()
        if _admits(callback, method, action, _user(role)) != (role in ALLOWED)
    ]
    assert wrong == []


def test_inactive_finance_user_is_refused():
    route, method, callback, action = _guarded_endpoints()[0]
    assert not _admits(callback, method, action, _user('Finance', active=False))


def test_other_invoice_actions_are_unchanged_for_sales():
    """Sales still lists invoices; only the QuickBooks export moved to Finance and Admin."""
    sales = _user('Sales')
    for route, callback in _walk(get_resolver().url_patterns):
        actions = getattr(callback, 'actions', None) or {}
        if getattr(callback, 'cls', None) is views.InvoiceViewSet and actions.get('get') == 'list':
            assert _admits(callback, 'GET', 'list', sales)
            return
    pytest.fail('invoice list route not found')


@pytest.mark.parametrize('path', [
    '/api/v1/profit-loss/monthly/',
    '/api/v1/ar-aging/summary/',
    '/api/v1/balance-sheet/quarterly/',
    '/api/v1/revenue-recognition/summary/',
    '/api/v1/invoices/export-quickbooks/',
])
@pytest.mark.parametrize('role', ['Sales', 'Tech', 'Music', ''])
def test_requests_from_other_roles_get_403(path, role):
    user = User.objects.create_user(
        username=f'fin-{role or "blank"}', email='fin-test@example.com', password='test-only-password', role=role,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(path)
    assert response.status_code == 403
    assert 'Finance' in str(response.data)
