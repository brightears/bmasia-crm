"""/dashboard/stats/ answers every role, and the Admin, Sales and Finance answers are unchanged.

Tech and Music users used to get a 500: the role branch filtered tasks on a `department`
field that Task no longer has (it was removed as unused on 2026-02-10). A task's team is
now the role of the person it is assigned to, so those roles see the tasks assigned to
them or to anyone with the same role, and the companies those tasks belong to.

The Admin, Sales and Finance bodies in golden/dashboard_stats_roles/ were produced by the
code before this fix, from the dataset below, read at a fixed moment, and are compared byte
for byte. Regenerate them (REGENERATE_DASHBOARD_ROLE_GOLDENS=1, PostgreSQL first, then
SQLite) only from the code before an intended, reviewed change to these answers.
"""
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import connection
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app.models import Company, Contract, Invoice, Opportunity, Task, User

pytestmark = pytest.mark.django_db

GOLDEN_DIR = Path(__file__).parent / 'golden' / 'dashboard_stats_roles'
READ_AT = '2026-11-18T03:00:00Z'
UNCHANGED = {
    'admin': ('a-admin', '/api/v1/dashboard/stats/'),
    'admin_limited': ('a-admin', '/api/v1/dashboard/stats/?billing_entity=BMAsia%20Limited'),
    'sales': ('s-one', '/api/v1/dashboard/stats/'),
    'finance': ('f-one', '/api/v1/dashboard/stats/'),
}


def _uid(kind, n):
    return uuid.UUID(int=(kind << 96) | n)


def build_role_dataset():
    """Invented records; every value a figure sorts or sums by is unique or explicit."""
    with freeze_time(datetime(2026, 6, 1, 2, 0, tzinfo=dt_timezone.utc)) as frozen:
        users = {}
        for n, (username, role) in enumerate([
            ('a-admin', 'Admin'), ('s-one', 'Sales'), ('s-two', 'Sales'), ('f-one', 'Finance'),
            ('t-one', 'Tech'), ('t-two', 'Tech'), ('m-one', 'Music'),
        ]):
            users[username] = User.objects.create(id=_uid(61, n), username=username, role=role,
                                                  first_name=username[:1].upper(), last_name='Example')
        companies = []
        for n in range(7):
            companies.append(Company.objects.create(
                id=_uid(62, n), name=f'Roleco {n}',
                billing_entity='BMAsia Limited' if n % 2 == 0 else 'BMAsia (Thailand) Co., Ltd.'))
            frozen.tick(timedelta(seconds=1))
        overdue = datetime(2026, 11, 10, 2, 0, tzinfo=dt_timezone.utc)
        # (company, assignee, creator, status, due)
        for n, (company, assignee, creator, status, due) in enumerate([
            (0, 't-one', 'a-admin', 'To Do', overdue),
            (1, 't-two', 'a-admin', 'In Progress', overdue + timedelta(hours=1)),
            (2, 'm-one', 'a-admin', 'To Do', overdue + timedelta(hours=2)),
            (3, 's-one', 't-one', 'To Do', overdue + timedelta(hours=3)),   # created by Tech
            (4, None, 'a-admin', 'To Do', overdue + timedelta(hours=4)),
            (5, 't-one', 'a-admin', 'Done', overdue + timedelta(hours=5)),
            (6, 't-one', 'a-admin', 'To Do', datetime(2026, 11, 25, tzinfo=dt_timezone.utc)),
        ]):
            Task.objects.create(
                id=_uid(63, n), company=companies[company], title=f'Role task {n}',
                assigned_to=users[assignee] if assignee else None, created_by=users[creator],
                status=status, due_date=due, priority=['Low', 'Medium', 'High'][n % 3])
            frozen.tick(timedelta(seconds=1))
        for n, (owner, stage, value) in enumerate([
            ('s-one', 'Contacted', '1000.00'), ('s-one', 'Won', '2000.00'),
            ('s-two', 'Quotation Sent', '3000.00'), ('s-two', 'Lost', '4000.00'),
            (None, 'Contract Sent', '5000.00'),
        ]):
            Opportunity.objects.create(
                id=_uid(64, n), company=companies[n], name=f'Role deal {n}', stage=stage,
                owner=users[owner] if owner else None, expected_value=Decimal(value),
                actual_close_date=date(2026, 11, 2) if stage in ('Won', 'Lost') else None)
            frozen.tick(timedelta(seconds=1))
        for n in range(4):
            Contract.objects.create(
                id=_uid(65, n), company=companies[n], contract_number=f'HK-CT2{n:04d}',
                status='Active', is_active=True, start_date=date(2026, 11, 2) + timedelta(days=n),
                end_date=date(2026, 12, 10) + timedelta(days=n), value=Decimal(f'{100 + n}.50'),
                currency='USD' if n % 2 == 0 else 'THB')
            Invoice.objects.create(
                id=_uid(66, n), company=companies[n], invoice_number=f'HK-INV2{n:04d}',
                status='Sent', issue_date=date(2026, 9, 1) + timedelta(days=n),
                due_date=date(2026, 10, 1) + timedelta(days=n), amount=Decimal('50.00'),
                total_amount=Decimal('50.00'), currency='USD' if n % 2 == 0 else 'THB')
            frozen.tick(timedelta(seconds=1))
    return users


def _get(users, username, url):
    client = APIClient()
    client.force_authenticate(users[username])
    with freeze_time(READ_AT):
        return client.get(url)


def _golden_path(name):
    specific = GOLDEN_DIR / connection.vendor / f'{name}.json'
    return specific if specific.exists() else GOLDEN_DIR / f'{name}.json'


def test_admin_sales_and_finance_answers_are_unchanged():
    users = build_role_dataset()
    bodies = {}
    for name, (username, url) in UNCHANGED.items():
        response = _get(users, username, url)
        assert response.status_code == 200, name
        bodies[name] = response.content.decode('utf-8')
    if os.environ.get('REGENERATE_DASHBOARD_ROLE_GOLDENS') == '1':
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        for name, body in bodies.items():
            if connection.vendor == 'postgresql':
                (GOLDEN_DIR / f'{name}.json').write_text(body, encoding='utf-8')
            else:
                specific = GOLDEN_DIR / connection.vendor / f'{name}.json'
                if body == (GOLDEN_DIR / f'{name}.json').read_text(encoding='utf-8'):
                    specific.unlink(missing_ok=True)
                else:
                    specific.parent.mkdir(exist_ok=True)
                    specific.write_text(body, encoding='utf-8')
        pytest.skip('golden bodies regenerated; review the JSON diff')
    for name, body in bodies.items():
        expected = _golden_path(name).read_text(encoding='utf-8')
        assert json.loads(body) == json.loads(expected), name
        assert body == expected, name


@pytest.mark.parametrize('username, overdue, companies', [
    # Overdue: its own open task and the other Tech user's. Companies: every company with
    # a task of the team, done or not yet due included (0, 1, 5 and 6).
    ('t-one', 2, 4),
    ('t-two', 2, 4),
    ('m-one', 1, 1),   # the Music task only
])
def test_tech_and_music_see_their_teams_tasks(username, overdue, companies):
    users = build_role_dataset()
    response = _get(users, username, '/api/v1/dashboard/stats/')
    assert response.status_code == 200
    body = response.json()
    assert body['overdue_tasks'] == overdue
    assert body['total_companies'] == companies
    # Everything that is not about tasks is the same as for Admin.
    admin = _get(users, 'a-admin', '/api/v1/dashboard/stats/').json()
    for key in ('active_opportunities', 'active_contracts', 'contracts_value', 'overdue_invoices',
                'pending_renewals', 'revenue_trend', 'pipeline_stages'):
        assert body[key] == admin[key], key
