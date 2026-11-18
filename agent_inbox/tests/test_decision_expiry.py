"""Every decision treats a proposal past its expiry as expired, as accept always did."""
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from agent_inbox import proposals as svc
from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client, seen_of


def _phone(company, value='+66 2 111 2222', **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'new number'}
    body.update(extra)
    return body



# ------------------------------------------------------------------ expiry on every decision


def _due(*proposals, at=None):
    ChangeProposal.objects.filter(pk__in=[p.pk for p in proposals]).update(
        expires_at=at or timezone.now() - timedelta(seconds=1))


def test_reject_of_an_expired_proposal_stores_expired(agent, person, company):
    proposal, _ = create_proposal(agent, _phone(company), via='rest')
    _due(proposal)
    response = decide(jwt_client(person), proposal.pk, 'reject', reason='stale')
    assert (response.status_code, response.json()['code']) == (409, 'expired')
    proposal.refresh_from_db()
    assert proposal.status == 'expired' and proposal.reviewer_id is None


def test_bulk_reject_skips_and_stores_expired_proposals(agent, other_agent, person, company):
    due, _ = create_proposal(agent, _phone(company), via='rest')
    fresh, _ = create_proposal(other_agent, _phone(company, value='+66 2 222 2222'), via='rest')
    items = [{'id': str(due.pk), 'seen_version': seen_of(due.pk)},
             {'id': str(fresh.pk), 'seen_version': seen_of(fresh.pk)}]
    _due(due)
    response = jwt_client(person).post(f'{PROPOSALS}bulk-reject/', {'items': items, 'reason': 'not now'},
                                       format='json')
    assert response.status_code == 200, response.content
    data = response.json()
    assert data['rejected'] == [str(fresh.pk)]
    assert data['skipped'] == [{'id': str(due.pk), 'status': 'expired', 'code': 'expired'}]
    due.refresh_from_db()
    fresh.refresh_from_db()
    assert (due.status, fresh.status) == ('expired', 'rejected')


def test_reopen_of_an_expired_proposal_stores_expired(agent, person, company):
    proposal, _ = create_proposal(agent, _phone(company), via='rest')
    _due(proposal)
    response = decide(jwt_client(person), proposal.pk, 'reopen', note='again')
    assert (response.status_code, response.json()['code']) == (409, 'expired')
    proposal.refresh_from_db()
    assert proposal.status == 'expired'


def test_an_expired_twin_does_not_block_a_reopen(agent, other_agent, person, company):
    first, _ = create_proposal(agent, _phone(company), via='rest')
    assert decide(jwt_client(person), first.pk, 'reject', reason='no').status_code == 200
    twin = ChangeProposal.objects.create(**{
        field.name: getattr(first, field.name) for field in ChangeProposal._meta.concrete_fields
        if field.name not in ('id', 'status', 'reviewer', 'reviewer_username', 'reviewed_at', 'decision_note',
                              'history')
    }, status='proposed', history=[])
    _due(twin)
    response = decide(jwt_client(person), first.pk, 'reopen', note='worth another look')
    assert response.status_code == 200, response.content
    twin.refresh_from_db()
    first.refresh_from_db()
    assert (first.status, twin.status) == ('proposed', 'expired')


@pytest.mark.parametrize('action, extra', [('accept', {}), ('reject', {'reason': 'no'}),
                                           ('reopen', {'note': 'again'})])
def test_the_expiry_instant_itself_counts_as_expired(agent, person, company, action, extra):
    proposal, _ = create_proposal(agent, _phone(company), via='rest')
    instant = timezone.now().replace(microsecond=0) + timedelta(days=1)
    _due(proposal, at=instant)
    seen = seen_of(proposal.pk)
    with mock.patch('django.utils.timezone.now', return_value=instant):
        response = decide(jwt_client(person), proposal.pk, action, seen_version=seen, **extra)
    assert (response.status_code, response.json()['code']) == (409, 'expired')
    proposal.refresh_from_db()
    assert proposal.status == 'expired'


def test_one_microsecond_before_the_expiry_the_decision_goes_through(agent, person, company):
    proposal, _ = create_proposal(agent, _phone(company), via='rest')
    instant = timezone.now().replace(microsecond=0) + timedelta(days=1)
    _due(proposal, at=instant)
    seen = seen_of(proposal.pk)
    with mock.patch('django.utils.timezone.now', return_value=instant - timedelta(microseconds=1)):
        response = decide(jwt_client(person), proposal.pk, 'reject', seen_version=seen, reason='no')
    assert response.status_code == 200, response.content


def test_effective_status_and_the_filter_at_the_instant(agent, company):
    proposal, _ = create_proposal(agent, _phone(company), via='rest')
    instant = timezone.now().replace(microsecond=0) + timedelta(days=1)
    _due(proposal, at=instant)
    proposal.refresh_from_db()
    rows = ChangeProposal.objects.all()
    with mock.patch('django.utils.timezone.now', return_value=instant - timedelta(microseconds=1)):
        assert svc.effective_status(proposal) == 'proposed'
        assert svc.with_effective_status(rows, ['proposed']).count() == 1
        assert svc.with_effective_status(rows, ['expired']).count() == 0
    with mock.patch('django.utils.timezone.now', return_value=instant):
        assert svc.effective_status(proposal) == 'expired'
        assert svc.with_effective_status(rows, ['proposed']).count() == 0
        assert svc.with_effective_status(rows, ['expired']).count() == 1
