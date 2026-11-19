"""Deleting a company keeps its activity and decision log.

These tests check the outcome only (409, nothing deleted, no audit row for a delete
that did not happen), so they hold whichever mechanism refuses the delete: this
app's middleware on its own, or a project-wide delete guard.
"""
from agent_inbox.activities import record_activity
from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import activity_body, session_client
from crm_app.models import AuditLog, Company


def _no_delete_audit(*companies):
    return not AuditLog.objects.filter(model_name='Company', action='DELETE',
                                       record_id__in=[str(c.pk) for c in companies]).exists()


def _client(person):
    client = session_client(person)
    client.raise_request_exception = False
    return client


def test_company_with_activities_is_not_deleted_over_rest(agent, person, company):
    record_activity(agent, activity_body(company), via='rest')
    response = _client(person).delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 409
    assert Company.objects.filter(pk=company.pk).exists()
    assert Activity.objects.filter(company=company).count() == 1
    assert _no_delete_audit(company)


def test_company_with_proposals_is_not_deleted_over_rest(agent, person, company):
    create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                            'patch': {'notes': 'x'}, 'evidence_quote': 'x'}, via='rest')
    response = _client(person).delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 409
    assert ChangeProposal.objects.filter(company=company).exists()
    assert _no_delete_audit(company)


def test_bulk_delete_never_deletes_a_company_with_history(agent, person, company, other_company):
    record_activity(agent, activity_body(company), via='rest')
    response = _client(person).post('/api/v1/companies/bulk_operations/', {
        'action': 'delete', 'ids': [str(company.pk), str(other_company.pk)]}, format='json')
    assert Company.objects.filter(pk=company.pk).exists()
    assert Activity.objects.filter(company=company).count() == 1
    assert _no_delete_audit(company)
    if response.status_code in (405, 409):
        # Refused as a whole: nothing deleted and nothing recorded.
        assert Company.objects.filter(pk=other_company.pk).exists()
        assert _no_delete_audit(other_company)
    else:
        # Decided record by record: the company with history is reported as not deleted.
        assert response.status_code == 200
        results = {row['id']: row for row in response.json()['results']}
        assert results[str(company.pk)]['deleted'] is False


def test_company_without_history_is_still_deleted(person, other_company):
    response = session_client(person).delete(f'/api/v1/companies/{other_company.pk}/')
    assert response.status_code == 204
    assert not Company.objects.filter(pk=other_company.pk).exists()


def test_other_requests_pass_through(person, company):
    client = session_client(person)
    assert client.get(f'/api/v1/companies/{company.pk}/').status_code == 200
    assert client.patch(f'/api/v1/companies/{company.pk}/', {'city': 'Hua Hin'}, format='json').status_code == 200


def test_mcp_delete_keeps_the_company_and_its_log(agent, company):
    from types import SimpleNamespace

    from mcp_server.djangomcp import django_request_ctx

    from crm_app.mcp import delete_record

    record_activity(agent, activity_body(company), via='rest')
    token = django_request_ctx.set(SimpleNamespace(user=agent, META={}))
    try:
        try:
            reply = delete_record('company', str(company.pk))
        except Exception as exc:  # the tool layer reports it as a tool error
            reply = f'Error: {exc}'
    finally:
        django_request_ctx.reset(token)
    assert 'Deleted' not in reply
    assert Company.objects.filter(pk=company.pk).exists()
    assert Activity.objects.filter(company=company).count() == 1
