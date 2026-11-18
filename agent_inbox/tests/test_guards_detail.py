"""Details the broader tests do not pin down: reads never sweep, the refresh never overwrites a
decision, and the company-delete middleware acts only on its two requests."""
from datetime import timedelta

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from agent_inbox.middleware import InboxProtectedDeleteMiddleware
from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal, refresh_snapshots
from agent_inbox.tests.conftest import PROPOSALS, session_client, token_client
from crm_app.models import AuditLog


def phone(company, value='+66 2 111 2222'):
    return {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'our number'}


def _updates(captured):
    return [q['sql'] for q in captured.captured_queries
            if q['sql'].lstrip().upper().startswith('UPDATE') and 'changeproposal' in q['sql']]


# ------------------------------------------------------------------ expiry on reads


def test_reads_show_a_due_proposal_as_expired_without_writing(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    ChangeProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    client = session_client(person)
    with CaptureQueriesContext(connection) as captured:
        listing = client.get(PROPOSALS).json()
        detail = client.get(f'{PROPOSALS}{proposal.pk}/').json()
        open_only = client.get(PROPOSALS, {'status': 'proposed'}).json()
        expired = client.get(PROPOSALS, {'status': 'expired'}).json()
        own = token_client(agent).get(PROPOSALS).json()
    assert _updates(captured) == []
    assert listing['results'][0]['status'] == 'expired' and detail['status'] == 'expired'
    assert open_only['count'] == 0 and expired['count'] == 1 and own['results'][0]['status'] == 'expired'
    assert ChangeProposal.objects.get(pk=proposal.pk).status == 'proposed'


def test_a_write_still_sweeps_due_proposals(agent, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    ChangeProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    create_proposal(agent, phone(company, value='+66 2 333 4444'), via='rest')
    assert ChangeProposal.objects.get(pk=proposal.pk).status == 'expired'


# ------------------------------------------------------------------ the refresh never overwrites a decision


@pytest.mark.parametrize('race', ['decided', 'refreshed'])
def test_a_stale_refresh_does_not_overwrite(agent, company, race):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    stale = ChangeProposal.objects.get(pk=proposal.pk)
    company.phone = '+66 2 555 5555'
    company.save()
    if race == 'decided':
        ChangeProposal.objects.filter(pk=proposal.pk).update(status='rejected')
    else:
        ChangeProposal.objects.filter(pk=proposal.pk).update(expected_version='2000-01-01T00:00:00Z',
                                                             current_values={'phone': 'someone else read'})
    refresh_snapshots([stale])
    row = ChangeProposal.objects.get(pk=proposal.pk)
    if race == 'decided':
        assert row.status == 'rejected' and row.current_values == {'phone': '+66 2 000 0000'}
    else:
        assert row.current_values == {'phone': 'someone else read'}


# ------------------------------------------------------------------ the middleware's two requests


def _run(method, path, writes, status=400):
    def view(request):
        AuditLog.objects.create(action='DELETE', model_name='Company', record_id='probe')
        return HttpResponse(status=status)
    request = getattr(RequestFactory(), method.lower())(path)
    InboxProtectedDeleteMiddleware(view)(request)
    return AuditLog.objects.filter(record_id='probe').exists()


@pytest.mark.parametrize('method, path', [
    ('DELETE', '/api/v1/companies/00000000-0000-0000-0000-000000000001/'),
    ('POST', '/api/v1/companies/bulk_operations/'),
])
def test_a_refused_company_delete_keeps_nothing_it_wrote(method, path):
    assert _run(method, path, writes=True, status=400) is False


@pytest.mark.parametrize('method, path', [
    ('DELETE', '/api/v1/companies/'), ('DELETE', '/api/v1/contacts/00000000-0000-0000-0000-000000000001/'),
    ('POST', '/api/v1/companies/'), ('PATCH', '/api/v1/companies/00000000-0000-0000-0000-000000000001/'),
    ('DELETE', '/api/v1/companies/00000000-0000-0000-0000-000000000001/contacts/'),
    ('GET', '/api/v1/companies/bulk_operations/'),
])
def test_other_requests_are_not_wrapped_or_answered(method, path):
    assert _run(method, path, writes=True, status=400) is True
    request = getattr(RequestFactory(), method.lower())(path)
    middleware = InboxProtectedDeleteMiddleware(lambda r: HttpResponse())
    assert middleware.process_exception(request, ProtectedError('x', set())) is None


def test_a_successful_company_delete_is_kept():
    assert _run('DELETE', '/api/v1/companies/00000000-0000-0000-0000-000000000001/', writes=True,
                status=204) is True
