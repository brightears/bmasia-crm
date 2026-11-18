"""One definition of open and overdue tasks (crm_app.models TASK_OPEN_STATUSES and
TaskQuerySet), used by Task.is_overdue, Today, the company dashboard, the dashboard stats and
Needs fixing.

Statuses are To Do, In Progress, Done, Cancelled and On Hold: there is no 'Pending'. Open means
not Done and not Cancelled. Overdue means open and due on an earlier Bangkok day than today.
Invented names; no Soundtrack account id on the company, so no outside call.
"""
from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app import data_quality as dq
from crm_app.models import Company, Task, User


@pytest.fixture(autouse=True)
def frozen_clock():
    # 03:00 UTC is 10:00 in Bangkok on 19 Nov 2026.
    with freeze_time('2026-11-19T03:00:00+00:00'):
        yield


def at(days, hour=10):
    return timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=days), time(hour)))


@pytest.fixture
def company():
    return Company.objects.create(name='Task Status Test Venue', soundtrack_account_id='')


@pytest.fixture
def client():
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username='task.viewer', password='x', role='Admin'))
    return c


def task(company, status, due, title):
    return Task.objects.create(company=company, status=status, due_date=due, title=title)


def test_cancelled_and_done_tasks_are_never_overdue(company):
    assert not task(company, 'Cancelled', at(-5), 'Dropped').is_overdue
    assert not task(company, 'Done', at(-5), 'Finished').is_overdue
    assert task(company, 'On Hold', at(-5), 'Paused').is_overdue
    assert task(company, 'To Do', at(-5), 'Late').is_overdue
    assert not task(company, 'To Do', None, 'Undated').is_overdue


def test_due_earlier_today_is_due_today_not_overdue(company):
    earlier = task(company, 'To Do', at(0, hour=8), 'Due at eight')
    late_yesterday = task(company, 'To Do', at(0, hour=0) - timedelta(seconds=1), 'Due last night')
    assert not earlier.is_overdue
    assert late_yesterday.is_overdue
    assert list(Task.objects.overdue()) == [late_yesterday]
    assert set(Task.objects.open()) == {earlier, late_yesterday}


def test_company_dashboard_uses_the_shared_rule(company, client):
    task(company, 'To Do', at(2), 'Upcoming call')
    task(company, 'In Progress', at(3), 'Upcoming meeting')
    task(company, 'On Hold', at(-3), 'Paused and late')
    task(company, 'Cancelled', at(-2), 'Dropped')
    task(company, 'Done', at(4), 'Already done')
    data = client.get(f'/api/v1/companies/{company.pk}/dashboard/').json()
    assert data['stats']['open_tasks'] == 3
    assert data['stats']['overdue_tasks'] == 1
    assert {t['title'] for t in data['upcoming_tasks']} == {'Upcoming call', 'Upcoming meeting'}


def test_today_and_needs_fixing_count_the_same_overdue_tasks(company, client):
    task(company, 'To Do', at(-1), 'Yesterday')
    task(company, 'On Hold', at(-4), 'Paused and late')
    task(company, 'To Do', at(0, hour=8), 'Earlier today')
    task(company, 'In Progress', at(1), 'Tomorrow')
    task(company, 'To Do', at(5), 'Next week')
    task(company, 'Cancelled', at(-2), 'Dropped')
    items = client.get('/api/v1/action-center/').json()['items']
    by_title = {i['title']: i for i in items if i['type'] == 'task'}
    overdue = {t for t, i in by_title.items() if i['urgency'] == 'overdue'}
    assert overdue == {'Yesterday', 'Paused and late'}
    assert by_title['Yesterday']['time_context'] == '1 day overdue'
    assert by_title['Earlier today']['urgency'] == 'today'
    assert by_title['Earlier today']['time_context'] == 'Due today'
    assert by_title['Tomorrow']['time_context'] == 'Due tomorrow'
    assert by_title['Next week']['urgency'] == 'upcoming'
    assert by_title['Next week']['time_context'] == 'Due in 5 days'
    assert 'Dropped' not in by_title
    assert dq.CHECKS_BY_KEY['task_overdue'].count(dq.Context()) == len(overdue)
    stats = client.get('/api/v1/dashboard/stats/').json()
    assert stats['overdue_tasks'] == len(overdue)


def test_just_after_midnight_in_bangkok(company, client):
    """At 01:30 in Bangkok the UTC date is still yesterday, and a task due at 00:30 today is
    already past the clock: neither may make it overdue anywhere."""
    with freeze_time('2026-11-19T18:30:00+00:00'):  # 01:30 on 20 Nov in Bangkok
        today = timezone.localdate()
        assert str(today) == '2026-11-20'
        start = timezone.make_aware(datetime.combine(today, time(0)))
        task(company, 'To Do', start + timedelta(minutes=30), 'Due at half past midnight')
        task(company, 'To Do', start - timedelta(hours=1), 'Due last night at eleven')
        items = client.get('/api/v1/action-center/').json()['items']
        urgency = {i['title']: (i['urgency'], i['time_context']) for i in items if i['type'] == 'task'}
        assert urgency == {'Due at half past midnight': ('today', 'Due today'),
                           'Due last night at eleven': ('overdue', '1 day overdue')}
        stats = client.get(f'/api/v1/companies/{company.pk}/dashboard/').json()['stats']
        assert (stats['open_tasks'], stats['overdue_tasks']) == (2, 1)
        assert client.get('/api/v1/dashboard/stats/').json()['overdue_tasks'] == 1
        assert dq.CHECKS_BY_KEY['task_overdue'].count(dq.Context()) == 1
        assert [t.title for t in Task.objects.all() if t.is_overdue] == ['Due last night at eleven']
