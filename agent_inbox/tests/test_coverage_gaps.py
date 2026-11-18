"""Behaviour that earlier tests did not pin down."""
import pytest

from agent_inbox.models import Activity, ChangeProposal, ProposalRefusal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, session_client, token_client
from crm_app.models import AuditLog


@pytest.mark.parametrize('kind, patch', [('field_update', {'title': 'Director'}), ('note', {'notes': 'x'})])
def test_company_id_must_match_the_target(agent, contact, other_company, kind, patch):
    response = token_client(agent).post(PROPOSALS, {
        'kind': kind, 'target_collection': 'contact', 'target_id': str(contact.pk),
        'company_id': str(other_company.pk), 'patch': patch, 'evidence_quote': 'q',
    }, format='json')
    assert response.status_code == 422 and response.json()['code'] == 'wrong_company'


def test_an_extra_audit_row_for_the_record_stops_the_accept(agent, person, company, monkeypatch):
    import crm_app.mcp as mcp
    proposal, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'q',
    }, via='rest')
    real = mcp.update_record

    def doubled(*args, **kwargs):
        reply = real(*args, **kwargs)
        AuditLog.objects.create(action='UPDATE', model_name='Company', record_id=str(company.pk))
        return reply

    monkeypatch.setattr(mcp, 'update_record', doubled)
    client = session_client(person)
    client.raise_request_exception = False
    assert decide(client, proposal.pk, 'accept').status_code >= 500
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'
    assert not AuditLog.objects.filter(model_name='Company', record_id=str(company.pk)).exists()
    assert ChangeProposal.objects.get(pk=proposal.pk).status == 'proposed'


@pytest.mark.parametrize('model', [Activity, ChangeProposal, ProposalRefusal])
def test_the_admin_is_read_only(person, model):
    from django.contrib import admin
    from django.test import RequestFactory

    person.is_staff = person.is_superuser = True
    person.save()
    request = RequestFactory().get('/')
    request.user = person
    model_admin = admin.site._registry[model]
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
    assert model_admin.get_actions(request) == {}


def test_malformed_limit_settings_fall_back_to_the_defaults():
    from django.test import override_settings

    from agent_inbox import policy
    with override_settings(CHANGE_PROPOSAL_EXPIRY_DAYS='30d', CHANGE_PROPOSALS_DAILY_CAP='-5',
                           AGENT_ACTIVITY_DAILY_CAP='lots'):
        assert (policy.proposal_expiry_days(), policy.proposal_daily_cap(), policy.activity_daily_cap()) \
            == (30, 200, 2000)
    with override_settings(CHANGE_PROPOSAL_EXPIRY_DAYS=' 7 ', CHANGE_PROPOSALS_DAILY_CAP=10):
        assert (policy.proposal_expiry_days(), policy.proposal_daily_cap()) == (7, 10)


def test_audit_row_of_an_applied_new_contact_says_it_came_from_a_proposal(agent, person, company):
    proposal, _ = create_proposal(agent, {
        'kind': 'new_contact', 'company_id': str(company.pk),
        'patch': {'name': 'Kim Example', 'email': 'kim@riverside.example.com'}, 'evidence_quote': 'q',
    }, via='rest')
    response = decide(session_client(person), proposal.pk, 'accept')
    row = AuditLog.objects.get(pk=response.json()['applied_audit_id'])
    assert row.additional_data['via'] == 'change_proposal'
