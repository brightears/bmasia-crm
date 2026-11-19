"""Every role gets an answer, never a server error, from every read-only API route.

Aggregates such as /dashboard/stats/ branch on the user's role, and a branch that only one
role reaches can break unnoticed (Tech and Music users got a 500 there). This sends one GET
per role to every API route that needs no URL parameter, to every detail route (with the
first record of its model), and to every data-quality check, on a small invented dataset,
and asserts that no answer is a 5xx. 4xx answers (method not allowed, missing parameters,
forbidden) are fine.

Roles: every value User.role allows, a blank role (the model has no blank choice, but the
column accepts one) and an inactive Admin. The network guard keeps every call local.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from crm_app.models import Company, Contact, Contract, Invoice, Opportunity, Task, Ticket, User, Zone

pytestmark = pytest.mark.django_db

SUMMARY_ENDPOINTS = ['/api/v1/dashboard/stats/', '/api/v1/action-center/', '/api/v1/data-quality/']


def _seed():
    owner = User.objects.create(username='every-role-owner', role='Sales', first_name='Owen')
    tech = User.objects.create(username='every-role-tech', role='Tech')
    music = User.objects.create(username='every-role-music', role='Music')
    for i in range(3):
        company = Company.objects.create(name=f'Every role co {i}', billing_entity='BMAsia Limited')
        Contact.objects.create(company=company, name=f'Contact {i}', email=f'every{i}@example.com',
                               is_primary=True)
        Zone.objects.create(company=company, name=f'Zone {i}')
        contract = Contract.objects.create(
            company=company, contract_number=f'HK-CT1{i:04d}', status='Active',
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 20), value=Decimal('100.00'))
        Invoice.objects.create(
            company=company, contract=contract, invoice_number=f'HK-INV1{i:04d}', status='Sent',
            issue_date=date(2026, 9, 1), due_date=date(2026, 10, 1), amount=Decimal('10.00'),
            total_amount=Decimal('10.00'))
        Opportunity.objects.create(company=company, name=f'Deal {i}', stage='Contacted', owner=owner,
                                   expected_value=Decimal('5.00'), follow_up_date=date(2026, 10, 1))
        for assignee in (owner, tech, music, None):
            Task.objects.create(company=company, title=f'Task {i}', assigned_to=assignee,
                                created_by=owner, due_date=datetime(2026, 10, 1, tzinfo=dt_timezone.utc))
        Ticket.objects.create(ticket_number=f'TK-1{i:04d}', subject='Example', description='Example',
                              company=company)


def _patterns(resolver=None, prefix=''):
    for entry in (resolver or get_resolver()).url_patterns:
        if isinstance(entry, URLResolver):
            yield from _patterns(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), getattr(entry.callback, 'cls', None)


def _clean(pattern):
    return pattern.replace('/^', '/').lstrip('^').rstrip('$').replace('\\', '')


def _urls():
    from crm_app.data_quality import CHECKS
    urls = set()
    for pattern, view_class in _patterns():
        route = _clean(pattern)
        if not route.startswith('api/') or 'format' in route:
            continue
        if '<' not in route and '(?P' not in route:
            urls.add('/' + route)
            continue
        rest = route.replace('(?P<pk>[^/.]+)', '', 1)
        queryset = getattr(view_class, 'queryset', None)
        if route.count('(?P<pk>') == 1 and '<' not in rest and '(?P' not in rest and queryset is not None:
            first = queryset.model.objects.order_by('pk').first()
            if first is not None:
                urls.add('/' + route.replace('(?P<pk>[^/.]+)', str(first.pk)))
    urls.update(f'/api/v1/data-quality/{check.key}/' for check in CHECKS)
    return sorted(urls)


def _users():
    users = {role: User.objects.create(username=f'every-role-{role.lower()}-reader', role=role)
             for role, _ in User.ROLE_CHOICES}
    users['(blank role)'] = User.objects.create(username='every-role-blank-reader', role='')
    users['Admin (inactive)'] = User.objects.create(username='every-role-inactive-reader',
                                                    role='Admin', is_active=False)
    return users


def test_no_read_only_route_fails_for_any_role():
    _seed()
    urls = _urls()
    for endpoint in SUMMARY_ENDPOINTS:
        assert endpoint in urls, endpoint
    failures = []
    for label, user in _users().items():
        client = APIClient()
        client.raise_request_exception = False
        client.force_authenticate(user)
        for url in urls:
            status = client.get(url).status_code
            if status >= 500:
                failures.append((url, label, status))
    assert not failures, failures


@pytest.mark.parametrize('endpoint', SUMMARY_ENDPOINTS)
def test_summary_endpoints_answer_every_active_role(endpoint):
    _seed()
    for label, user in _users().items():
        if not user.is_active:
            continue
        client = APIClient()
        client.force_authenticate(user)
        assert client.get(endpoint).status_code == 200, (endpoint, label)
