"""Task statuses are To Do, In Progress, Done, Cancelled and On Hold: there is no 'Pending'.

The company dashboard counted open tasks as 'Pending' or 'In Progress' (so To Do tasks were never
counted and never listed as upcoming), and Task.is_overdue counted Cancelled tasks. Invented
names; no Soundtrack account id on the company, so no outside call.
"""
from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app.models import Company, Task, User


@pytest.fixture(autouse=True)
def frozen_clock():
    with freeze_time('2026-11-19T03:00:00+00:00'):
        yield


def at(days):
    return timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=days), time(10)))


@pytest.fixture
def company():
    return Company.objects.create(name='Task Status Test Venue', soundtrack_account_id='')


def task(company, status, due, title):
    return Task.objects.create(company=company, status=status, due_date=due, title=title)


def test_cancelled_and_done_tasks_are_never_overdue(company):
    assert not task(company, 'Cancelled', at(-5), 'Dropped').is_overdue
    assert not task(company, 'Done', at(-5), 'Finished').is_overdue
    assert task(company, 'On Hold', at(-5), 'Paused').is_overdue
    assert task(company, 'To Do', at(-5), 'Late').is_overdue
    assert not task(company, 'To Do', None, 'Undated').is_overdue


def test_company_dashboard_counts_to_do_tasks(company):
    task(company, 'To Do', at(2), 'Upcoming call')
    task(company, 'In Progress', at(3), 'Upcoming meeting')
    task(company, 'Cancelled', at(-2), 'Dropped')
    task(company, 'Done', at(4), 'Already done')
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username='dash.viewer', password='x', role='Admin'))
    data = client.get(f'/api/v1/companies/{company.pk}/dashboard/').json()
    assert data['stats']['open_tasks'] == 2
    assert data['stats']['overdue_tasks'] == 0
    assert {t['title'] for t in data['upcoming_tasks']} == {'Upcoming call', 'Upcoming meeting'}
