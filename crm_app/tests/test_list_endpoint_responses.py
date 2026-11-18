"""The list endpoints answer as before, with a fixed number of queries.

The frontend and the agents read these lists field by field. Four kinds of check:

1. Golden bodies (golden/list_endpoints/). They were produced by the code before the
   query-count work (origin/main at 9c5087e; the same bodies come from 8c90205), from the
   invented dataset in list_endpoint_fixture.py, read at a fixed moment, and are compared
   byte for byte: field order, types, number formatting, null versus missing, date formats.
   - CHANGED_CASES are the lists and detail pages whose querysets or serializer methods the
     query-count work changed. UNCHANGED_CASES pin lists it did not change (contacts,
     invoices, tasks, renewal book); they guard against side effects only.
   - The bodies also embed serializers the work did not change: companies embed
     ContactSerializer and ZoneSerializer, contracts embed InvoiceSerializer, and so on.
2. A list row equals the detail page of the same record (the detail page still runs the
   per-row code), on a dataset built to trip the list's shortcuts: blank and mixed-case
   currencies, several active contract types, child companies, invoices in every status.
3. Exact query counts for every list (and a one-row page is never cheaper by more than an
   empty nested prefetch), and exact query counts for the detail pages.
4. The list-only data (annotations named _list_*, to_attr prefetches named _prefetched_*)
   is never loaded by any other action.

Adding a field to a serializer that appears in a golden body
------------------------------------------------------------
Add its name to FIELDS_ADDED_SINCE_GOLDENS with a one-line reason. The comparison then
ignores that key wherever it appears, and the rest of each body is still compared byte
for byte. The test refuses a name that already occurs in a golden body, because ignoring
it would hide a change to an existing field; regenerate instead.

Regenerating the golden bodies
------------------------------
Only legitimate when a change to existing values is intended and reviewed, or after a
fixture change. Generate from the code BEFORE your behaviour change (check out main),
never from the code under test, or the test only pins what the new code does:

    git stash / git checkout main        # the code whose answers you want to keep
    REGENERATE_LIST_GOLDENS=1 DATABASE_URL=postgres://... pytest crm_app/tests/test_list_endpoint_responses.py -k bodies
    REGENERATE_LIST_GOLDENS=1 pytest crm_app/tests/test_list_endpoint_responses.py -k bodies   # SQLite, second
    git checkout -                        # back to your change; the test must now pass

PostgreSQL writes the common files; SQLite then writes a copy under sqlite/ only where its
body differs (the old code sums money in the database, and SQLite returns those sums as
floats: "320.350000000000" where PostgreSQL says "320.35"). Review the diff of the JSON
files like any other change.
"""
import json
import os
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from crm_app.tests.list_endpoint_fixture import READ_AT, build_list_dataset, uid

pytestmark = pytest.mark.django_db

GOLDEN_DIR = Path(__file__).parent / 'golden' / 'list_endpoints'
GOLDEN_COMPANIES = 7

# Field name -> why it was added after the golden bodies were made. See the module docstring.
FIELDS_ADDED_SINCE_GOLDENS = {}

# name -> URL. Every list sorts by values that are unique in the dataset.
CHANGED_CASES = {
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
}
# Lists the query-count work did not change; pinned only to catch side effects.
UNCHANGED_CASES = {
    'contacts': '/api/v1/contacts/?page_size=1000',
    'invoices': '/api/v1/invoices/?page_size=100',
    'tasks': '/api/v1/tasks/?page_size=1000',
    'renewal_book': '/api/v1/contracts/renewal-book/?year=2027&month=3',
}
GOLDEN_CASES = {**CHANGED_CASES, **UNCHANGED_CASES}


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def read_golden_bodies(cases=GOLDEN_CASES):
    """Build the dataset and read every golden URL at the fixed moment."""
    client = _client(build_list_dataset(GOLDEN_COMPANIES))
    bodies = {}
    with freeze_time(READ_AT):
        for name, url in cases.items():
            response = client.get(url)
            assert response.status_code == 200, (name, response.status_code)
            bodies[name] = response.content.decode('utf-8')
    return bodies


def golden_path(name, vendor=None):
    """The expected body; a database-specific copy wins where the old code differed."""
    specific = GOLDEN_DIR / (vendor or connection.vendor) / f'{name}.json'
    return specific if specific.exists() else GOLDEN_DIR / f'{name}.json'


def _canonical(value):
    """The renderer's layout (compact, UTF-8); golden bodies round-trip through it."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _without(value, names):
    if isinstance(value, dict):
        return {k: _without(v, names) for k, v in value.items() if k not in names}
    if isinstance(value, list):
        return [_without(v, names) for v in value]
    return value


def _keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value)) if value else set()
    return set()


def _regenerate(bodies):
    """Write the bodies (see the module docstring for when this is legitimate)."""
    if connection.vendor == 'postgresql':
        for name, body in bodies.items():
            (GOLDEN_DIR / f'{name}.json').write_text(body, encoding='utf-8')
        return
    specific_dir = GOLDEN_DIR / connection.vendor
    specific_dir.mkdir(exist_ok=True)
    for name, body in bodies.items():
        specific = specific_dir / f'{name}.json'
        if body == (GOLDEN_DIR / f'{name}.json').read_text(encoding='utf-8'):
            specific.unlink(missing_ok=True)
        else:
            specific.write_text(body, encoding='utf-8')


def _assert_bodies(cases):
    bodies = read_golden_bodies(cases)
    if os.environ.get('REGENERATE_LIST_GOLDENS') == '1':
        _regenerate(bodies)
        pytest.skip('golden bodies regenerated; review the JSON diff')
    added = set(FIELDS_ADDED_SINCE_GOLDENS)
    for name, body in bodies.items():
        expected = golden_path(name).read_text(encoding='utf-8')
        if not added:
            # Parsed first for a readable difference, then byte for byte.
            assert json.loads(body) == json.loads(expected), name
            assert body == expected, name
            continue
        golden = json.loads(expected)
        clash = added & _keys(golden)
        assert not clash, f'{sorted(clash)} already exist in the {name} golden body; regenerate instead'
        assert _canonical(golden) == expected, name
        actual = _without(json.loads(body), added)
        assert actual == golden, name
        assert _canonical(actual) == expected, name


def test_changed_list_and_detail_bodies_are_unchanged():
    _assert_bodies(CHANGED_CASES)


def test_unchanged_list_bodies_are_unchanged():
    _assert_bodies(UNCHANGED_CASES)


# ---------------------------------------------------------------------------
# A list row equals the detail page (the detail page runs the per-row code).
# ---------------------------------------------------------------------------

def _build_tricky():
    """Records built to trip the list's shortcuts. Names, dates and keys are unique, so no
    nested order depends on how the database breaks ties."""
    from crm_app.models import (
        Company, Contact, Contract, ContractServiceLocation, ContractZone, Invoice,
        Opportunity, Ticket, TicketComment, User, Zone,
    )
    with freeze_time(datetime(2026, 2, 1, tzinfo=dt_timezone.utc)) as frozen:
        def tick():
            frozen.tick(1)

        admin = User.objects.create(username='tricky-admin', role='Admin', first_name='Ada')
        parent = Company.objects.create(name='Tricky Parent', billing_entity='BMAsia Limited',
                                        is_corporate_parent=True)
        tick()
        child = Company.objects.create(name='Tricky Child', billing_entity='BMAsia Limited',
                                       parent_company=parent)
        tick()
        Company.objects.create(name='Tricky Empty', billing_entity='BMAsia Limited')
        tick()
        Contact.objects.create(company=parent, name='Pat Primary', email='pat@example.com',
                               is_primary=True)
        tick()
        Opportunity.objects.create(company=parent, name='Open deal', is_active=True)
        Opportunity.objects.create(company=parent, name='Closed deal', is_active=False)
        tick()
        # Active contracts in several currencies, blank included, and two contract types;
        # mixed case sorts differently under a linguistic collation than in Python.
        contracts = []
        for n, (currency, kind, active, status) in enumerate([
            ('USD', 'Annual', True, 'Active'),
            ('thb', 'Monthly', True, 'Active'),
            ('THB', 'Annual', True, 'Expired'),
            ('', 'Monthly', True, 'Active'),
            ('usd', 'One-time', True, 'Draft'),
            ('EUR', 'Annual', False, 'Expired'),
        ]):
            contracts.append(Contract.objects.create(
                company=parent, contract_number=f'HK-CT7{n:04d}', contract_type=kind,
                status=status, is_active=active, currency=currency,
                start_date=date(2025, 1, 1 + n), end_date=date(2026, 12, 1 + n),
                value=Decimal(f'{100 * (n + 1)}.50'),
                contract_category='corporate_master' if n == 0 else 'standard',
                renewed_from=contracts[0] if n == 2 else None,
            ))
            tick()
        Contract.objects.create(
            company=child, contract_number='HK-CT79999', contract_type='Annual', status='Active',
            currency='', start_date=date(2025, 3, 1), value=Decimal('10.00'),
            contract_category='participation', master_contract=contracts[0],
        )
        tick()
        for n, status in enumerate(['Paid', 'Sent', 'Draft', 'Cancelled', 'Refunded', 'Overdue']):
            Invoice.objects.create(
                company=parent, contract=contracts[0], invoice_number=f'HK-INV7{n:04d}',
                status=status, issue_date=date(2025, 2, 1 + n), due_date=date(2025, 3, 1 + n),
                amount=Decimal(f'{10 + n}.10'), tax_amount=Decimal('0.70'),
                discount_amount=Decimal('0.00'), total_amount=Decimal('0'), currency='USD',
            )
            tick()
        ContractServiceLocation.objects.create(contract=contracts[1], location_name='Lobby')
        tick()
        for n in range(3):
            zone = Zone.objects.create(company=parent, name=f'Tricky zone {n}',
                                       status=['online', 'offline', 'pending'][n])
            tick()
            for m, contract in enumerate(contracts[:3 - n]):
                ContractZone.objects.create(contract=contract, zone=zone,
                                            start_date=date(2025, 1 + m, 1 + n),
                                            is_active=m != 1)
                tick()
        ticket = Ticket.objects.create(ticket_number='TK-777', subject='Tricky', description='x',
                                       company=parent, created_by=admin)
        tick()
        for n in range(3):
            TicketComment.objects.create(ticket=ticket, author=admin, text=f'c{n}',
                                         is_internal=n == 2)
            tick()
    return admin


@pytest.mark.parametrize('collection', ['companies', 'contracts', 'zones', 'tickets'])
def test_list_rows_equal_their_detail_pages(collection):
    client = _client(_build_tricky())
    with freeze_time(READ_AT):
        rows = client.get(f'/api/v1/{collection}/?page_size=1000').json()['results']
        assert rows
        for row in rows:
            detail = client.get(f'/api/v1/{collection}/{row["id"]}/').json()
            assert row == detail, (collection, row.get('name') or row.get('contract_number'))
            assert list(row) == list(detail)


def test_currency_entries_follow_the_database_order():
    """The list groups active contracts by currency as the per-row query does, including a
    blank currency labelled USD, in the database's ORDER BY currency (its collation)."""
    from crm_app.models import Company, Contract
    from django.db.models import Sum

    client = _client(_build_tricky())
    parent = Company.objects.get(name='Tricky Parent')
    row = next(r for r in client.get('/api/v1/companies/?page_size=1000').json()['results']
               if r['name'] == 'Tricky Parent')
    expected = [
        {'currency': r['currency'] or 'USD', 'total': f"{r['total']:.2f}"}
        for r in Contract.objects.filter(company=parent, is_active=True)
        .values('currency').annotate(total=Sum('value')).order_by('currency')
    ]
    assert row['active_contract_value_by_currency'] == expected
    assert [entry['currency'] for entry in expected].count('USD') == 2  # '' and 'USD'
    # Two active contracts of two of the types; the newest contract's type comes first.
    assert row['subscription_summary'] == 'One-time, 2 Monthly, 2 Annual'


# ---------------------------------------------------------------------------
# Query counts.
# ---------------------------------------------------------------------------

# name -> (URL without page_size, rows in the dataset, queries for the whole list).
QUERY_CASES = {
    'companies': ('/api/v1/companies/', 7, 8),
    'contracts': ('/api/v1/contracts/', 21, 9),
    'tickets': ('/api/v1/tickets/', 7, 6),
    'zones': ('/api/v1/zones/', 9, 3),
    'notes': ('/api/v1/notes/', 14, 5),
    'quotes': ('/api/v1/quotes/', 7, 7),
    'opportunities': ('/api/v1/opportunities/', 14, 5),
    # Lists that were already flat before the query-count work.
    'contacts': ('/api/v1/contacts/', 21, 2),
    'invoices': ('/api/v1/invoices/', 21, 3),
    'tasks': ('/api/v1/tasks/', 14, 4),
}

# Detail pages run the per-row code; their counts on the golden dataset must not move.
DETAIL_QUERY_CASES = {
    'company_detail': (f'/api/v1/companies/{uid("company", 1)}/', 17),
    'contract_detail': (f'/api/v1/contracts/{uid("contract", 51)}/', 19),
    'zone_detail': (f'/api/v1/zones/{uid("zone", 30)}/', 3),
    'ticket_detail': (f'/api/v1/tickets/{uid("ticket", 3)}/', 8),
    'quote_detail': (f'/api/v1/quotes/{uid("quote", 2)}/', 6),
    'opportunity_detail': (f'/api/v1/opportunities/{uid("opportunity", 30)}/', 4),
    'note_detail': (f'/api/v1/notes/{uid("note", 30)}/', 1),
}


def _queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200
    return len(ctx.captured_queries), response.json()


@pytest.mark.parametrize('name', sorted(QUERY_CASES))
def test_list_query_count_is_fixed(name):
    url, rows, exact = QUERY_CASES[name]
    client = _client(build_list_dataset(GOLDEN_COMPANIES))
    client.get(f'{url}?page_size=1')  # warm caches outside the count

    # The second row, not the first: company 000 has no zones, so its page would
    # skip the zone prefetches and look cheaper than an ordinary row.
    one, one_body = _queries(client, f'{url}?page=2&page_size=1')
    every, every_body = _queries(client, f'{url}?page_size=1000')

    assert len(one_body['results']) == 1
    assert len(every_body['results']) == rows
    assert every == exact, (name, every)
    # A one-row page can be a query or two cheaper: Django skips a nested prefetch
    # when the rows have nothing to nest (a draft contract has no invoices).
    assert one <= every <= one + 2, (name, one, every)


@pytest.mark.parametrize('name', sorted(DETAIL_QUERY_CASES))
def test_detail_query_count_is_unchanged(name):
    url, exact = DETAIL_QUERY_CASES[name]
    client = _client(build_list_dataset(GOLDEN_COMPANIES))
    client.get(url)
    count, _ = _queries(client, url)
    assert count == exact, (name, count)


def _view_queryset(viewset_class, action, user):
    request = Request(APIRequestFactory().get('/'))
    request.user = user
    view = viewset_class()
    view.request, view.action, view.format_kwarg, view.kwargs = request, action, None, {}
    return view.get_queryset()


def _list_only_markers(queryset):
    annotations = [name for name in queryset.query.annotations if name.startswith('_list_')]
    to_attrs = [getattr(lookup, 'to_attr', None) or '' for lookup in queryset._prefetch_related_lookups]
    return annotations + [name for name in to_attrs if name.startswith('_prefetched_')]


@pytest.mark.parametrize('viewset_name', ['CompanyViewSet', 'ContractViewSet', 'ZoneViewSet',
                                          'TicketViewSet'])
def test_only_the_list_action_loads_list_data(viewset_name):
    from crm_app import views
    from crm_app.models import User

    viewset_class = getattr(views, viewset_name)
    user = User.objects.create(username='marker-check', role='Admin')
    assert _list_only_markers(_view_queryset(viewset_class, 'list', user))
    for action in ['retrieve', 'update', 'partial_update', 'destroy', 'create', 'metadata', None]:
        assert not _list_only_markers(_view_queryset(viewset_class, action, user)), action


def test_prefetched_current_link_matches_the_query_on_ties():
    """The list's in-memory choice of a zone's current link follows the query's ORDER BY,
    down to the link id when status and both start dates are equal."""
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
