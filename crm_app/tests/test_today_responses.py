"""The Today page and the dashboard stats answer as before, with a fixed number of queries.

The golden bodies in golden/today/ were produced by the code before the query-count work
on these two endpoints (the PR 65 head merged with main 78cfb3c, which includes the
Today task rules of PR 57), from today_fixture.py, read at a fixed moment, and are
compared byte for byte.

Regenerating them is legitimate only when a change to the answers is intended and
reviewed, and must be done from the code BEFORE that change, in a second worktree or on a
commit that holds only the fixture change, never with git stash (see the procedure in
test_list_endpoint_responses.py; the switch here is REGENERATE_TODAY_GOLDENS=1). They were
last regenerated when the company with only inactive contacts joined the fixture, from the
code before the name-then-id tie-break (a506ace); that company's contacts do not tie.
PostgreSQL writes the common files, SQLite a copy under sqlite/ where its body differs
(opportunities with no expected value sort first on PostgreSQL and last on SQLite, and the
old code sums some money in the database).
"""
import json
import os
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app.tests.today_fixture import READ_AT, build_today_dataset

pytestmark = pytest.mark.django_db

GOLDEN_DIR = Path(__file__).parent / 'golden' / 'today'
GOLDEN_COMPANIES = 6

# name -> (user, URL)
GOLDEN_CASES = {
    'action_center_admin': ('admin', '/api/v1/action-center/'),
    'action_center_sales': ('sales', '/api/v1/action-center/'),
    'dashboard_admin': ('admin', '/api/v1/dashboard/stats/'),
    'dashboard_admin_limited': ('admin', '/api/v1/dashboard/stats/?billing_entity=BMAsia%20Limited'),
    'dashboard_sales': ('sales', '/api/v1/dashboard/stats/'),
}


def _read(cases, n_companies=GOLDEN_COMPANIES):
    admin, sales = build_today_dataset(n_companies)
    clients = {}
    for name, user in (('admin', admin), ('sales', sales)):
        clients[name] = APIClient()
        clients[name].force_authenticate(user)
    bodies = {}
    with freeze_time(READ_AT):
        for name, (who, url) in cases.items():
            response = clients[who].get(url)
            assert response.status_code == 200, (name, response.status_code)
            bodies[name] = response.content.decode('utf-8')
    return bodies


def _golden_path(name):
    specific = GOLDEN_DIR / connection.vendor / f'{name}.json'
    return specific if specific.exists() else GOLDEN_DIR / f'{name}.json'


def _regenerate(bodies):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
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


def test_today_and_dashboard_bodies_are_unchanged():
    bodies = _read(GOLDEN_CASES)
    if os.environ.get('REGENERATE_TODAY_GOLDENS') == '1':
        _regenerate(bodies)
        pytest.skip('golden bodies regenerated; review the JSON diff')
    for name, body in bodies.items():
        expected = _golden_path(name).read_text(encoding='utf-8')
        assert json.loads(body) == json.loads(expected), name
        assert body == expected, name


def test_the_dataset_reaches_every_section():
    """Guard for the golden bodies: each Today section and dashboard branch has rows."""
    body = json.loads(_read({'a': GOLDEN_CASES['action_center_admin']})['a'])
    kinds = {(item['type'], item['urgency']) for item in body['items']}
    assert kinds == {
        ('task', 'overdue'), ('invoice', 'overdue'), ('opportunity', 'overdue'),
        ('task', 'today'), ('invoice', 'today'), ('contract', 'upcoming'),
        ('task', 'upcoming'), ('opportunity', 'upcoming'),
    }
    names = {item['contact_name'] for item in body['items']}
    assert None in names and len(names) > 4


def _count(user_name, url, n_companies, first=0):
    admin, sales = build_today_dataset(n_companies, first)
    client = APIClient()
    client.force_authenticate(admin if user_name == 'admin' else sales)
    with freeze_time(READ_AT):
        client.get(url)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
    assert response.status_code == 200
    return len(ctx.captured_queries)


# name -> (user, URL, queries whatever the number of items)
QUERY_CASES = {
    'action_center_admin': ('admin', '/api/v1/action-center/', 10),
    'action_center_sales': ('sales', '/api/v1/action-center/', 12),
    'dashboard_admin': ('admin', '/api/v1/dashboard/stats/', 46),
    'dashboard_sales': ('sales', '/api/v1/dashboard/stats/', 46),
}


@pytest.mark.parametrize('name', sorted(QUERY_CASES))
def test_query_count_does_not_grow_with_items(name):
    user_name, url, exact = QUERY_CASES[name]
    small = _count(user_name, url, 4)
    connection.queries_log.clear()
    large = _count(user_name, url, 8, first=4)  # now 12 companies, three times the items
    assert large == small, (name, small, large)
    assert large == exact, (name, large)


def test_two_primaries_with_the_same_name_resolve_to_the_lowest_id():
    """Today, the company list and the company page pick the same contact when two active
    primaries share a name: the one with the lowest id (before, the database chose)."""
    import uuid
    from datetime import datetime, timezone as dt_timezone

    from crm_app.models import Company, Contact, Task, User

    admin = User.objects.create(username='tie-admin', role='Admin')
    company = Company.objects.create(name='Tied primaries', billing_entity='BMAsia Limited')
    low, high = uuid.UUID(int=(70 << 96) | 1), uuid.UUID(int=(70 << 96) | 2)
    for pk in (high, low):  # the higher id first, so creation order and id order differ
        Contact.objects.create(id=pk, company=company, name='Same Name', email=f'{pk.int}@example.com',
                               unsubscribe_token=f'tie-{pk.int}')
    Contact.objects.filter(company=company).update(is_primary=True, is_active=True)
    Task.objects.create(company=company, title='Tie task', status='To Do', assigned_to=admin,
                        due_date=datetime(2026, 11, 1, 2, 0, tzinfo=dt_timezone.utc))
    client = APIClient()
    client.force_authenticate(admin)
    with freeze_time(READ_AT):
        today = client.get('/api/v1/action-center/').json()
        listed = client.get('/api/v1/companies/?search=Tied%20primaries').json()['results'][0]
        detail = client.get(f'/api/v1/companies/{company.pk}/').json()
    item = next(i for i in today['items'] if i['title'] == 'Tie task')
    assert item['contact_email'] == f'{low.int}@example.com'
    assert listed['primary_contact']['id'] == str(low)
    assert detail['primary_contact']['id'] == str(low)
