"""Phase 1 agent gate, Stage A (observe): policy verdicts are recorded, writes are unchanged."""
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from mcp_server.djangomcp import django_request_ctx
from rest_framework.test import APIClient

from crm_app import agent_policy as policy
from crm_app.mcp import create_record, delete_record, update_record
from crm_app.models import AgentRequest, Company, Contact, Contract, Opportunity, Ticket, Zone


@contextmanager
def as_caller(user):
    token = django_request_ctx.set(SimpleNamespace(user=user))
    try:
        yield
    finally:
        django_request_ctx.reset(token)


def _user(username):
    return get_user_model().objects.create_user(
        username=username, email=f'{username}@example.test', password='x', role='Admin',
    )


def _company(name='Gate fixture'):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited')


def _contact(company=None):
    return Contact.objects.create(company=company or _company(), name='Gate contact',
                                  email='gate@example.test', title='Manager')


def _live_contract(company):
    return Contract.objects.create(
        company=company, contract_number='GATE-LIVE-1', start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31), value=Decimal('400.00'), total_value=Decimal('400.00'),
        status='Active',
    )


# ---------------------------------------------------------------- pure policy

def test_policy_default_deny_and_cira_breadth():
    cira = policy.PRINCIPALS['cira']
    assert policy.evaluate(cira, policy.CREATE, 'contract', ['company', 'value']) == ([], '')
    assert policy.evaluate(cira, policy.UPDATE, 'quote', ['status']) == ([], '')
    assert policy.evaluate(cira, policy.CONVERT, 'quote', []) == ([], '')
    assert policy.evaluate(cira, policy.DELETE, 'contact', [])[0] == ['agents may not delete records']
    vera = policy.PRINCIPALS['vera']
    assert policy.evaluate(vera, policy.UPDATE, 'contact', ['title'])[0] == ['vera may not update contact']


def test_policy_field_scopes():
    riff, nina, theo = (policy.PRINCIPALS[n] for n in ('riff', 'nina', 'theo'))
    assert policy.evaluate(riff, policy.UPDATE, 'zone', ['notes', 'platform']) == ([], '')
    assert policy.evaluate(riff, policy.UPDATE, 'zone', ['name'])[0] == ['riff may not set zone.name']
    assert policy.evaluate(riff, policy.UPDATE, 'clienttechdetail', ['company'])[0] == [
        'riff may not set clienttechdetail.company']
    assert policy.evaluate(riff, policy.UPDATE, 'ticket', ['status']) == ([], 'ticket_non_terminal')
    assert policy.evaluate(riff, policy.RESERVE_NUMBER, 'contract', [])[0] == ['reserve_number is Cira-only']
    assert policy.evaluate(nina, policy.UPDATE, 'zone', ['status'])[0] == ['nina may not set zone.status']
    assert policy.evaluate(theo, policy.UPDATE, 'contact', ['title', 'email'])[0] == [
        'theo may not set contact.email']
    assert policy.evaluate(policy.PRINCIPALS['ruby'], policy.UPDATE, 'contact', ['title'])[0] == [
        'principal ruby is retired']


def test_unlisted_username_is_not_an_agent():
    assert policy.principal_for_username('norbert') is None
    assert policy.principal_for_username(' Cira ').name == 'cira'


# ---------------------------------------------------------------- gate via MCP

@pytest.mark.django_db
def test_observe_records_would_deny_but_write_still_happens():
    contact = _contact()
    theo = _user('theo')
    with as_caller(theo):
        result = json.loads(update_record('contact', str(contact.id), json.dumps({'email': 'new@example.test'})))
    contact.refresh_from_db()
    assert contact.email == 'new@example.test'  # Stage A never blocks
    assert result.get('email') == 'new@example.test' or 'id' in result
    row = AgentRequest.objects.get()
    assert (row.principal, row.tool, row.verb, row.collection, row.decision) == (
        'theo', 'update_record', 'update', 'contact', 'would_deny')
    assert row.fields == ['email']
    assert row.reasons == ['theo may not set contact.email']
    assert row.protocol_gaps == ['request_key_missing', 'expected_version_missing', 'expected_values_missing']
    assert row.record_id == str(contact.id)
    assert len(row.payload_sha256) == 64
    assert 'new@example.test' not in json.dumps([row.fields, row.reasons, row.protocol_gaps])


@pytest.mark.django_db
def test_allowed_agent_write_and_expected_version_flag():
    contact = _contact()
    with as_caller(_user('lyra')):
        update_record('contact', str(contact.id), json.dumps({'title': 'GM'}),
                      expected_version='2026-09-25T00:00:00Z')
    row = AgentRequest.objects.get()
    assert row.decision == 'allow' and row.reasons == []
    assert row.has_expected_version is True
    assert row.protocol_gaps == ['request_key_missing', 'expected_values_missing']


@pytest.mark.django_db
def test_sales_lead_rule_blocks_existing_customers_only():
    sales = _user('sales')
    lead, customer = _company('Lead Co'), _company('Customer Co')
    _live_contract(customer)
    with as_caller(sales):
        update_record('company', str(lead.id), json.dumps({'notes': 'warm lead'}))
        update_record('company', str(customer.id), json.dumps({'notes': 'touch'}))
        create_record('opportunity', json.dumps({'company': str(customer.id), 'name': 'Upsell'}))
    rows = {r.record_id or r.collection: r for r in AgentRequest.objects.all()}
    assert rows[str(lead.id)].decision == 'allow'
    assert rows[str(customer.id)].decision == 'would_deny'
    assert 'existing customer' in rows[str(customer.id)].reasons[0]
    assert rows['opportunity'].decision == 'allow'


@pytest.mark.django_db
def test_riff_terminal_ticket_status_is_flagged():
    company = _company()
    ticket = Ticket.objects.create(company=company, subject='Zone offline', description='x')
    with as_caller(_user('riff')):
        update_record('ticket', str(ticket.id), json.dumps({'priority': 'high'}))
        update_record('ticket', str(ticket.id), json.dumps({'status': 'closed'}))
    decisions = list(AgentRequest.objects.order_by('created_at').values_list('decision', flat=True))
    assert decisions == ['allow', 'would_deny']


@pytest.mark.django_db
def test_delete_is_recorded_and_still_performed_in_observe():
    contact = _contact()
    with as_caller(_user('cira')):
        delete_record('contact', str(contact.id))
    assert not Contact.objects.filter(id=contact.id).exists()
    row = AgentRequest.objects.get()
    assert (row.verb, row.decision, row.reasons) == ('delete', 'would_deny', ['agents may not delete records'])


@pytest.mark.django_db
def test_humans_and_unauthenticated_calls_are_labelled_not_gated():
    contact = _contact()
    with as_caller(_user('norbert')):
        update_record('contact', str(contact.id), json.dumps({'title': 'Owner'}))
    update_record('contact', str(contact.id), json.dumps({'title': 'Owner 2'}))  # no request context
    assert sorted(AgentRequest.objects.values_list('decision', flat=True)) == ['not_agent', 'unauthenticated']


@pytest.mark.django_db
@override_settings(AGENT_GATE_MODE='off')
def test_kill_switch_records_nothing():
    contact = _contact()
    with as_caller(_user('theo')):
        update_record('contact', str(contact.id), json.dumps({'email': 'x@example.test'}))
    assert AgentRequest.objects.count() == 0


@pytest.mark.django_db
def test_gate_failure_never_breaks_the_write(monkeypatch):
    contact = _contact()

    def boom(*args, **kwargs):
        raise RuntimeError('ledger down')

    monkeypatch.setattr(AgentRequest.objects, 'create', boom)
    with as_caller(_user('theo')):
        update_record('contact', str(contact.id), json.dumps({'title': 'Still saved'}))
    contact.refresh_from_db()
    assert contact.title == 'Still saved'


# ---------------------------------------------------------------- gate via REST

@pytest.mark.django_db
def test_agent_rest_write_is_recorded_human_rest_write_is_not():
    zone = Zone.objects.create(company=_company(), name='Lobby', platform='soundtrack')
    client = APIClient()
    client.force_authenticate(_user('nina'))
    client.patch(f'/api/v1/zones/{zone.id}/', {'notes': 'evening set'}, format='json')
    client.force_authenticate(_user('keith'))
    client.patch(f'/api/v1/zones/{zone.id}/', {'notes': 'human edit'}, format='json')
    row = AgentRequest.objects.get()
    assert row.principal == 'nina' and row.tool.startswith('rest:')
    assert row.decision == 'would_deny'
    assert row.reasons == ['agent writes via REST will be refused; use the MCP write tools']


# ---------------------------------------------------------------- report command

@pytest.mark.django_db
def test_report_summarises_without_customer_values():
    from io import StringIO
    from django.core.management import call_command

    contact = _contact()
    with as_caller(_user('theo')):
        update_record('contact', str(contact.id), json.dumps({'email': 'secret@example.test'}))
    with as_caller(_user('mystery-sales-bot')):
        update_record('contact', str(contact.id), json.dumps({'title': 'Buyer'}))
    out = StringIO()
    call_command('agent_gate_report', '--json', stdout=out)
    report = json.loads(out.getvalue())
    assert report['total'] == 2
    assert {'who': 'theo', 'decision': 'would_deny', 'n': 1} in report['by_decision']
    assert {'username': 'mystery-sales-bot', 'n': 1} in report['unlisted_mcp_writers']
    assert 'secret@example.test' not in out.getvalue()


# ---------------------------------------------------------------- Vera review (PR #7) fixes

@pytest.mark.django_db
def test_theo_keeps_his_approved_opportunity_scope_but_not_terminal_stages():
    opp = Opportunity.objects.create(company=_company(), name='Renewal 2027', stage='Quotation Sent')
    with as_caller(_user('theo')):
        update_record('opportunity', str(opp.id), json.dumps(
            {'follow_up_date': '2026-10-01', 'pain_points': 'budget freeze'}))
        update_record('opportunity', str(opp.id), json.dumps({'stage': 'Lost'}))
    rows = list(AgentRequest.objects.order_by('created_at'))
    assert rows[0].decision == 'allow'
    assert rows[1].decision == 'would_deny' and 'terminal' in rows[1].reasons[0]


@pytest.mark.django_db
def test_sales_won_lost_needs_the_existing_explicit_user_authorization():
    opp = Opportunity.objects.create(company=_company(), name='New lead', stage='Contract Sent')
    with as_caller(_user('sales')):
        update_record('opportunity', str(opp.id), json.dumps({'stage': 'Won'}))
    first = AgentRequest.objects.get()
    assert first.decision == 'would_deny'
    assert 'explicit-user authorization' in first.reasons[0]
    from crm_app.services import agent_gate
    sales = get_user_model().objects.get(username='sales')
    bogus = json.dumps({'kind': 'explicit_user_commercial'})
    valid = json.dumps({'kind': 'explicit_user_commercial', 'source_thread_id': 'chat-123',
                        'record_id': str(opp.id), 'authorized_changes': {'stage': 'Won'}})
    wrong_record = json.dumps({'kind': 'explicit_user_commercial', 'source_thread_id': 'chat-123',
                               'record_id': str(_company('Other Co').id), 'authorized_changes': {'stage': 'Won'}})
    with as_caller(sales):
        results = [agent_gate.observe(tool='update_record', verb='update', collection='opportunity',
                                      record_id=str(opp.id), data={'stage': 'Won'},
                                      authorization_context=ctx) for ctx in (bogus, wrong_record, valid)]
    assert [r.decision for r in results] == ['would_deny', 'would_deny', 'allow']


def test_cira_policy_is_exhaustive_and_denies_unknown_collections():
    from crm_app.mcp import _COLLECTION_MAP
    cira = policy.PRINCIPALS['cira']
    assert set(_COLLECTION_MAP) == set(policy.CIRA_COLLECTIONS)  # drift guard: review both together
    assert policy.evaluate(cira, policy.CREATE, 'future_sensitive_collection', ['x'])[0] == [
        'cira may not create future_sensitive_collection']
    assert policy.evaluate(cira, policy.UPDATE, 'contract', ['status']) == ([], '')


@pytest.mark.django_db
def test_cara_rest_write_is_observed():
    contact = _contact()
    client = APIClient()
    client.force_authenticate(_user('cara'))
    client.patch(f'/api/v1/contacts/{contact.id}/', {'last_contacted': '2026-09-25T10:00:00Z'}, format='json')
    row = AgentRequest.objects.get()
    assert (row.principal, row.verb, row.collection) == ('cara', 'update', 'contact')


@pytest.mark.django_db
def test_rene_tool_calls_are_observed_even_when_refused():
    from crm_app.mcp import RenePhase2MCPToolset
    toolset = RenePhase2MCPToolset(request=SimpleNamespace(user=_user('cira')))
    reply = toolset.rene_phase2_request('{}')
    assert 'FORBIDDEN' in reply  # boundary unchanged: not the configured exact principal
    row = AgentRequest.objects.get()
    assert (row.principal, row.tool, row.verb, row.decision) == (
        'cira', 'rene_phase2_request', 'rene_request', 'allow')


@pytest.mark.django_db
def test_purge_is_dry_run_by_default_and_respects_minimum():
    from datetime import timedelta
    from io import StringIO
    from django.core.management import CommandError, call_command
    from django.utils import timezone

    old = AgentRequest.objects.create(tool='t', verb='update', decision='allow')
    AgentRequest.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=400))
    AgentRequest.objects.create(tool='t', verb='update', decision='allow')
    out = StringIO()
    call_command('agent_gate_purge', stdout=out)
    assert '[DRY-RUN] 1' in out.getvalue() and AgentRequest.objects.count() == 2
    call_command('agent_gate_purge', '--execute', stdout=StringIO())
    assert AgentRequest.objects.count() == 1
    with pytest.raises(CommandError):
        call_command('agent_gate_purge', '--days', '7')
