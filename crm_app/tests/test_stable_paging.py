"""Walking a list's pages returns every row exactly once, even when rows tie on the sort key.

No list ordering used to end on a unique key, so two page queries could order tied rows
differently and the pages duplicated some rows and dropped others (on a review dataset,
/contracts/?ordering=end_date&page_size=1 returned 143 distinct contracts of 154). The
shared paginator now ends every ordering with the primary key (crm_app/pagination.py).
Rows that differ on the requested ordering keep their order; tied rows come in key order.
"""
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from crm_app.models import (
    Company, Contact, Contract, Invoice, Note, Opportunity, Quote, Task, Ticket, User, Zone,
)
from crm_app.pagination import FlexiblePageNumberPagination, with_unique_tiebreak

pytestmark = pytest.mark.django_db

ROWS = 13  # odd, so tie groups straddle every page boundary at sizes 2 and 25 alike
STAMP = datetime(2026, 3, 1, 5, 0, tzinfo=dt_timezone.utc)


def _id(kind, n):
    # Ids deliberately out of creation order.
    return uuid.UUID(int=(kind << 96) | ((n * 7919) % 1000))


def _build_ties():
    admin = User.objects.create(id=_id(40, 0), username='ties-admin', role='Admin')
    for n in range(4):
        User.objects.create(id=_id(40, n + 1), username=f'ties-user-{n}', role='Sales')
    User.objects.update(date_joined=STAMP)
    companies = [Company.objects.create(id=_id(41, n), name=f'Tie company {n:02d}',
                                        industry='Hotels', country='Thailand',
                                        billing_entity='BMAsia Limited')
                 for n in range(ROWS)]
    Company.objects.update(created_at=STAMP, updated_at=STAMP)
    shared = companies[0]
    for n in range(ROWS):
        company = companies[n % 3]
        Contact.objects.create(id=_id(42, n), company=company, name='Same Name',
                               email=f'tie{n}@example.com', unsubscribe_token=f'tie-{n}')
        Contract.objects.create(
            id=_id(43, n), company=company, contract_number=f'HK-CT6{n:04d}', status='Active',
            start_date=date(2025, 1, 1), end_date=date(2026, 1, 1) if n % 4 else date(2027, 1, 1),
            value=Decimal('100.00') if n % 3 else Decimal(f'{n}.00'),
        )
        Invoice.objects.create(
            id=_id(44, n), company=company, invoice_number=f'HK-INV6{n:04d}', status='Sent',
            issue_date=date(2025, 2, 1), due_date=date(2025, 3, 1), amount=Decimal('10.00'),
            total_amount=Decimal('10.00'),
        )
        Quote.objects.create(
            id=_id(45, n), quote_number=f'HK-QT6{n:04d}', company=company, status='Draft',
            valid_from=date(2025, 1, 1), valid_until=date(2025, 12, 1),
        )
        Opportunity.objects.create(
            id=_id(46, n), company=company, name=f'Tie deal {n}', stage='Contacted',
            expected_value=Decimal('500.00'), expected_close_date=date(2026, 1, 1),
        )
        Task.objects.create(id=_id(47, n), company=company, title=f'Tie task {n}', priority='High',
                            due_date=STAMP + timedelta(days=30), status='To Do')
        Note.objects.create(id=_id(48, n), company=company, author=admin, text=f'tie {n}')
        Zone.objects.create(id=_id(49, n), company=shared, name='Same zone')
        Ticket.objects.create(id=_id(50, n), ticket_number=f'TK-6{n:04d}', subject='Tie',
                              description='tie', company=company, priority='medium')
    for model in (Contact, Contract, Invoice, Quote, Opportunity, Task, Note, Zone, Ticket):
        model.objects.update(created_at=STAMP, updated_at=STAMP)
    return admin


def _walk(client, url, size):
    ids, page = [], 1
    while True:
        response = client.get(f'{url}{"&" if "?" in url else "?"}page_size={size}&page={page}')
        assert response.status_code == 200, (url, response.status_code)
        body = response.json()
        ids.extend(row['id'] for row in body['results'])
        if not body['next']:
            return ids, body['count']
        page += 1


# list URL -> orderings to walk (None is the list's default ordering)
WALKS = {
    '/api/v1/users/': [None, 'role', '-date_joined'],
    '/api/v1/companies/': [None, 'industry', '-country', 'created_at'],
    '/api/v1/contacts/': [None, 'name', 'company__name', '-created_at'],
    '/api/v1/contracts/': [None, 'end_date', '-start_date', 'value', 'company__name'],
    '/api/v1/invoices/': [None, 'issue_date', 'due_date', '-total_amount'],
    '/api/v1/quotes/': [None, 'status', 'valid_until', '-created_at'],
    '/api/v1/opportunities/': [None, 'stage', 'expected_value', '-expected_close_date'],
    '/api/v1/tasks/': [None, 'priority', 'status', 'company__name'],
    '/api/v1/notes/': [None, 'priority', 'note_type'],
    '/api/v1/zones/': [None],
    '/api/v1/tickets/': [None, 'priority', 'status', 'due_date'],
}


@pytest.mark.parametrize('url', sorted(WALKS))
def test_every_row_appears_exactly_once_on_every_page_walk(url):
    client = APIClient()
    client.force_authenticate(_build_ties())
    for ordering in WALKS[url]:
        target = f'{url}?ordering={ordering}' if ordering else url
        everything, count = _walk(client, target, 1000)
        assert len(everything) == count
        for size in (1, 2, 25):
            ids, count = _walk(client, target, size)
            assert len(ids) == count == len(set(ids)), (target, size)
            # Same rows in the same order as one big page.
            assert ids == everything, (target, size)


def test_a_requested_ordering_still_decides_for_rows_that_do_not_tie():
    client = APIClient()
    client.force_authenticate(_build_ties())
    ids, _ = _walk(client, '/api/v1/contracts/?ordering=value', 2)
    rows = {str(c.id): c for c in Contract.objects.all()}
    keys = [(rows[i].value, uuid.UUID(i)) for i in ids]
    assert keys == sorted(keys)  # by value, then the key among equal values
    ids, _ = _walk(client, '/api/v1/contracts/?ordering=-end_date', 2)
    keys = [(-rows[i].end_date.toordinal(), uuid.UUID(i)) for i in ids]
    assert keys == sorted(keys)


def _list_querysets(params):
    """Each router list endpoint's queryset, filtered as its list action filters it."""
    from crm_app.urls import router

    user = User.objects.create(username=f'ordering-check-{len(params)}', role='Admin')
    for prefix, viewset, _ in router.registry:
        if not hasattr(viewset, 'list') or not hasattr(viewset, 'get_queryset'):
            continue
        request = Request(APIRequestFactory().get('/', params))
        request.user = user
        view = viewset(request=request, action='list', format_kwarg=None, kwargs={}, args=())
        try:
            queryset = view.filter_queryset(view.get_queryset())
        except AssertionError:
            continue  # a ViewSet without a queryset (dashboard-style endpoints)
        yield prefix, view, queryset


def _ends_on_key(queryset):
    order = list(queryset.query.order_by)
    if not order or not isinstance(order[-1], str):
        return False
    name = order[-1].lstrip('-')
    if name in ('pk', 'id'):
        return True
    try:
        field = queryset.model._meta.get_field(name)
    except Exception:
        return False
    return field.unique and not field.null


def test_every_list_endpoint_pages_through_the_tiebreaking_paginator():
    checked = []
    for prefix, view, queryset in _list_querysets({}):
        assert isinstance(view.paginator, FlexiblePageNumberPagination), prefix
        assert _ends_on_key(with_unique_tiebreak(queryset)), prefix
        checked.append(prefix)
    assert len(checked) > 40, checked


def test_every_requested_ordering_ends_on_the_key():
    for prefix, view, _ in _list_querysets({}):
        from rest_framework.filters import OrderingFilter
        fields = getattr(view, 'ordering_fields', None)
        if not fields or fields == '__all__' or not any(
                issubclass(backend, OrderingFilter) for backend in view.filter_backends):
            continue
        for field in fields:
            for term in (field, f'-{field}'):
                request = Request(APIRequestFactory().get('/', {'ordering': term}))
                request.user = view.request.user
                view.request = request
                queryset = with_unique_tiebreak(view.filter_queryset(view.get_queryset()))
                order = list(queryset.query.order_by)
                assert order[0] == term, (prefix, term, order)
                assert _ends_on_key(queryset), (prefix, term, order)

