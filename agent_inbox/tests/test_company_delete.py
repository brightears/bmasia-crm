"""Deleting a company keeps its activity and decision log: the delete is refused with 409."""
from agent_inbox.activities import record_activity
from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import activity_body, session_client
from crm_app.models import Company


def test_company_with_activities_is_not_deleted_over_rest(agent, person, company):
    record_activity(agent, activity_body(company), via='rest')
    client = session_client(person)
    client.raise_request_exception = False
    response = client.delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 409
    assert response.json()['code'] == 'has_activity_history'
    assert response.json()['activities'] == 1
    assert Company.objects.filter(pk=company.pk).exists()
    assert Activity.objects.filter(company=company).count() == 1
    # The refused delete leaves no audit row behind.
    from crm_app.models import AuditLog
    assert not AuditLog.objects.filter(model_name='Company', record_id=str(company.pk), action='DELETE').exists()


def test_company_with_proposals_is_not_deleted_over_rest(agent, person, company):
    create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                            'patch': {'notes': 'x'}, 'evidence_quote': 'x'}, via='rest')
    client = session_client(person)
    client.raise_request_exception = False
    response = client.delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 409 and response.json()['change_proposals'] == 1
    assert ChangeProposal.objects.filter(company=company).exists()


def test_company_without_history_is_still_deleted(person, other_company):
    response = session_client(person).delete(f'/api/v1/companies/{other_company.pk}/')
    assert response.status_code == 204
    assert not Company.objects.filter(pk=other_company.pk).exists()


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
