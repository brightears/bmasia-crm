"""Concurrent identical writes on PostgreSQL: one row, every caller gets the same answer."""
import threading

import pytest
from django.db import connection, connections

from agent_inbox.activities import record_activity
from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, activity_body, session_client

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='row locking needs PostgreSQL'),
]

THREADS = 6


def run_together(target):
    barrier = threading.Barrier(THREADS)
    results, errors = [], []

    def worker():
        try:
            barrier.wait()
            results.append(target())
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert errors == []
    return results


def test_identical_activity_writes_store_one_row(agent, company):
    body = activity_body(company)
    results = run_together(lambda: record_activity(agent, dict(body), via='rest'))
    assert Activity.objects.count() == 1
    stored = Activity.objects.get()
    assert {activity.pk for activity, _ in results} == {stored.pk}
    assert sorted(replayed for _, replayed in results) == [False] + [True] * (THREADS - 1)


def test_identical_proposals_store_one_row(agent, company):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'new number +66 2 111 2222'}
    results = run_together(lambda: create_proposal(agent, dict(body), via='rest'))
    assert ChangeProposal.objects.count() == 1
    assert len({proposal.pk for proposal, _ in results}) == 1
    assert sorted(replayed for _, replayed in results) == [False] + [True] * (THREADS - 1)


def test_concurrent_accepts_apply_once(agent, person, company):
    from crm_app.models import AuditLog
    proposal, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'new number',
    }, via='rest')
    path = f'{PROPOSALS}{proposal.pk}/accept/'
    statuses = run_together(lambda: session_client(person).post(path, {}, format='json').status_code)
    assert sorted(statuses) == [200] + [409] * (THREADS - 1)
    assert AuditLog.objects.filter(model_name='Company', record_id=str(company.pk)).count() == 1
    proposal.refresh_from_db()
    assert proposal.status == 'accepted'
