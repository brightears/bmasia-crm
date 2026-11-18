"""The list endpoints answer byte for byte as before, with a fixed number of queries.

The frontend and the agents read these lists field by field. The expected bodies in
golden/list_endpoints/ were produced by the code before the query-count work
(origin/main at 9c5087e), from the invented dataset in list_endpoint_fixture.py,
read at a fixed moment. Field order, types, number formatting, null versus missing
and date formats must all stay as they are.

The query-count tests read the same list with one row and with every row: the number
of queries must not grow with the rows.
"""
import json
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app.tests.list_endpoint_fixture import READ_AT, build_list_dataset, uid

pytestmark = pytest.mark.django_db

GOLDEN_DIR = Path(__file__).parent / 'golden' / 'list_endpoints'
GOLDEN_COMPANIES = 7

# name -> URL. Every list sorts by values that are unique in the dataset.
GOLDEN_CASES = {
    'companies': '/api/v1/companies/?page_size=100',
    'companies_search': '/api/v1/companies/?search=Testco%2000&page_size=5',
    'companies_parents': '/api/v1/companies/?is_corporate_parent=true&page_size=100',
    'company_detail': f'/api/v1/companies/{uid("company", 1)}/',
    'contracts': '/api/v1/contracts/?page_size=100',
    'contracts_page2': '/api/v1/contracts/?page=2&page_size=3',
    'contracts_company': f'/api/v1/contracts/?company={uid("company", 5)}&page_size=1000',
    'contracts_search': '/api/v1/contracts/?search=Testco&page_size=5',
    'contract_detail': f'/api/v1/contracts/{uid("contract", 1)}/',
    'contract_detail_master': f'/api/v1/contracts/{uid("contract", 51)}/',
    'zones': '/api/v1/zones/?page_size=1000',
    'zones_company': f'/api/v1/zones/?company={uid("company", 3)}&page_size=200',
    'zone_detail': f'/api/v1/zones/{uid("zone", 30)}/',
    'tickets': '/api/v1/tickets/?page_size=100',
    'ticket_detail': f'/api/v1/tickets/{uid("ticket", 3)}/',
    'notes': '/api/v1/notes/?page_size=100',
    'quotes': '/api/v1/quotes/?page_size=100',
    'quote_detail': f'/api/v1/quotes/{uid("quote", 2)}/',
    'opportunities': '/api/v1/opportunities/?page_size=1000',
    'contacts': '/api/v1/contacts/?page_size=1000',
    'invoices': '/api/v1/invoices/?page_size=100',
    'tasks': '/api/v1/tasks/?page_size=1000',
    'renewal_book': '/api/v1/contracts/renewal-book/?year=2027&month=3',
}


def read_golden_bodies():
    """Build the dataset and read every golden URL at the fixed moment."""
    admin = build_list_dataset(GOLDEN_COMPANIES)
    client = APIClient()
    client.force_authenticate(admin)
    bodies = {}
    with freeze_time(READ_AT):
        for name, url in GOLDEN_CASES.items():
            response = client.get(url)
            assert response.status_code == 200, (name, response.status_code)
            bodies[name] = response.content.decode('utf-8')
    return bodies


def golden_path(name):
    """The expected body; a database-specific copy wins where the old code differed.

    The old code sums money in the database, and SQLite returns those sums as floats:
    an outstanding amount reads "320.350000000000" there and "320.35" on PostgreSQL.
    Those bodies are kept per database, so both stay pinned exactly.
    """
    specific = GOLDEN_DIR / connection.vendor / f'{name}.json'
    return specific if specific.exists() else GOLDEN_DIR / f'{name}.json'


def test_list_and_detail_bodies_are_unchanged():
    bodies = read_golden_bodies()
    for name, body in bodies.items():
        expected = golden_path(name).read_text(encoding='utf-8')
        # Parsed first for a readable difference, then byte for byte.
        assert json.loads(body) == json.loads(expected), name
        assert body == expected, name


# name -> (URL without page_size, rows in the dataset, most queries allowed).
QUERY_CASES = {
    'companies': ('/api/v1/companies/', 7, 9),
    'contracts': ('/api/v1/contracts/', 21, 12),
    'tickets': ('/api/v1/tickets/', 7, 7),
    'zones': ('/api/v1/zones/', 9, 3),
    'notes': ('/api/v1/notes/', 14, 2),
    'quotes': ('/api/v1/quotes/', 7, 7),
    # Lists that were already flat before the query-count work.
    'contacts': ('/api/v1/contacts/', 21, 2),
    'invoices': ('/api/v1/invoices/', 21, 3),
    'tasks': ('/api/v1/tasks/', 14, 4),
}


def test_prefetched_current_link_matches_the_query_on_ties():
    """The list's in-memory choice of a zone's current link follows the query's ORDER BY,
    down to the link id when status and both start dates are equal."""
    from datetime import date
    from decimal import Decimal
    import uuid

    from crm_app.models import Company, Contract, ContractZone, Zone
    from crm_app.services.list_querysets import zone_links_prefetch

    company = Company.objects.create(name='Tieco', billing_entity='BMAsia Limited')
    zone = Zone.objects.create(company=company, name='Tie zone')
    same_day = date(2026, 5, 1)
    for n, (status, start, link_start) in enumerate([
        ('Draft', same_day, same_day),
        ('Draft', same_day, same_day),
        ('Sent', same_day, same_day),
        ('Draft', date(2026, 6, 1), same_day),
    ]):
        contract = Contract.objects.create(
            company=company, contract_number=f'HK-CT8{n:04d}', status=status,
            start_date=start, value=Decimal('1.00'),
        )
        # Ids chosen so that creation order and id order differ.
        ContractZone.objects.create(
            id=uuid.UUID(int=(9 << 96) | (7 - n)), contract=contract, zone=zone,
            start_date=link_start, is_active=True,
        )
    for drop in [None, 'HK-CT80003', 'HK-CT80000']:
        links = ContractZone.objects.filter(zone=zone)
        if drop:
            links.filter(contract__contract_number=drop).update(is_active=False)
        queried = Zone.objects.get(pk=zone.pk).get_current_link()
        prefetched = Zone.objects.prefetch_related(zone_links_prefetch()).get(pk=zone.pk)
        assert prefetched.get_current_link().pk == queried.pk, drop


def _queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200
    return len(ctx.captured_queries), response.json()


@pytest.mark.parametrize('name', sorted(QUERY_CASES))
def test_list_query_count_does_not_grow_with_rows(name):
    url, rows, most = QUERY_CASES[name]
    admin = build_list_dataset(GOLDEN_COMPANIES)
    client = APIClient()
    client.force_authenticate(admin)
    client.get(f'{url}?page_size=1')  # warm caches outside the count

    # The second row, not the first: company 000 has no zones, so its page would
    # skip the zone prefetches and look cheaper than an ordinary row.
    one, one_body = _queries(client, f'{url}?page=2&page_size=1')
    every, every_body = _queries(client, f'{url}?page_size=1000')

    assert len(one_body['results']) == 1
    assert len(every_body['results']) == rows
    # A one-row page can be a query or two cheaper: Django skips a nested prefetch
    # when the rows have nothing to nest (a draft contract has no invoices).
    assert one <= every <= one + 2, (name, one, every)
    assert every <= most, (name, every)
