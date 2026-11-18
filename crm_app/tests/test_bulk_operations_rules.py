"""Bulk operations are enabled per record type; single deletes follow the same rules everywhere.

The router walk at the end fails when a viewset or a bulk operation appears without being
classified here, so each new one is decided on purpose.
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from crm_app.models import (
    AuditLog, Company, Contract, ContractTemplate, EmailSequence, EmailTemplate, Invoice, KBArticle, KBCategory,
    SequenceStep, Task, Ticket, TicketComment, TicketKBArticle, User,
)
from crm_app.services.bulk_updates import MAX_BULK_IDS

# --- who calls ------------------------------------------------------------------------------

def _user(username, staff=False):
    return User.objects.create_user(username=username, email=f'{username}@example.com',
                                    password='test-only-password', role='Admin', is_active=True, is_staff=staff)


def token_client(user):
    """An API token holder (agents use these)."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=user).key}')
    return client


def website_client(user):
    """A person signed in to the website (JWT)."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.fixture(params=['token-non-staff', 'token-staff', 'website'])
def caller(request):
    kind = request.param
    if kind == 'website':
        return kind, website_client(_user('person-on-website'))
    return kind, token_client(_user(f'api-{kind}', staff=kind == 'token-staff'))


# --- bulk: off unless a record type enables it --------------------------------------------

BULK_ROUTES = [
    'users', 'companies', 'contacts', 'notes', 'tasks', 'opportunities', 'opportunity-activities',
    'contracts', 'invoices', 'quotes', 'campaigns', 'vendors', 'expense-categories', 'recurring-expenses',
    'expenses',
]


@pytest.mark.parametrize('route', BULK_ROUTES)
@pytest.mark.parametrize('operation', ['delete', 'update_status', 'assign', 'export', 'activate'])
def test_bulk_operations_not_enabled_answer_405(caller, route, operation):
    _kind, client = caller
    data = {'status': 'x'} if operation == 'update_status' else {'assigned_to': 'x'} if operation == 'assign' else {}
    response = client.post(f'/api/v1/{route}/bulk_operations/', {
        'action': operation, 'ids': ['00000000-0000-0000-0000-000000000001'], 'data': data}, format='json')
    # Users: the route's own rules may answer first (403) for callers who may not manage users.
    assert response.status_code in ((403, 405) if route == 'users' else (405,))


def test_nothing_changes_when_bulk_is_refused():
    company = Company.objects.create(name='Bulk Keep Co', billing_entity='BMAsia Limited')
    task = Task.objects.create(company=company, title='Keep me', status='To Do')
    client = token_client(_user('bulk-refused'))
    client.post('/api/v1/tasks/bulk_operations/', {'action': 'update_status', 'ids': [str(task.pk)],
                                                    'data': {'status': 'Done', 'priority': 'Urgent'}}, format='json')
    client.post('/api/v1/tasks/bulk_operations/', {'action': 'delete', 'ids': [str(task.pk)]}, format='json')
    task.refresh_from_db()
    assert task.status == 'To Do'
    assert not AuditLog.objects.exists()


# --- bulk, where enabled: the same rules as single edits -------------------------------------

@pytest.fixture
def invoice_bulk(monkeypatch):
    from crm_app.views import InvoiceViewSet, TaskViewSet
    monkeypatch.setattr(InvoiceViewSet, 'bulk_allowed', frozenset({'update_status', 'delete'}))
    monkeypatch.setattr(TaskViewSet, 'bulk_allowed', frozenset({'assign'}))


def _invoice(number='INV-BULK-1', status='Sent'):
    company, _ = Company.objects.get_or_create(name='Bulk Rules Co', defaults={'billing_entity': 'BMAsia Limited'})
    return Invoice.objects.create(company=company, invoice_number=number, status=status,
                                  issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
                                  amount=Decimal('10'), total_amount=Decimal('10'))


def test_update_status_takes_only_the_status(invoice_bulk):
    invoice = _invoice()
    client = website_client(_user('bulk-person'))
    response = client.post('/api/v1/invoices/bulk_operations/', {
        'action': 'update_status', 'ids': [str(invoice.pk)],
        'data': {'status': 'Overdue', 'total_amount': '0.01'}}, format='json')
    assert response.status_code == 400
    invoice.refresh_from_db()
    assert (invoice.status, invoice.total_amount) == ('Sent', Decimal('10'))


def test_update_status_follows_the_transition_rules_and_audits_each_record(invoice_bulk):
    first, second = _invoice('INV-BULK-A'), _invoice('INV-BULK-B')
    client = website_client(_user('bulk-person'))
    paid = client.post('/api/v1/invoices/bulk_operations/', {
        'action': 'update_status', 'ids': [str(first.pk)], 'data': {'status': 'Paid'}}, format='json')
    assert paid.json()['updated'] == 0
    overdue = client.post('/api/v1/invoices/bulk_operations/', {
        'action': 'update_status', 'ids': [str(first.pk), str(second.pk)], 'data': {'status': 'Overdue'}},
        format='json')
    assert overdue.json()['updated'] == 2
    for invoice in (first, second):
        invoice.refresh_from_db()
        assert invoice.status == 'Overdue'
        assert AuditLog.objects.filter(record_id=str(invoice.pk), action='UPDATE').count() == 1


def test_at_most_200_records_per_call(invoice_bulk):
    client = website_client(_user('bulk-person'))
    ids = [f'00000000-0000-0000-0000-{n:012d}' for n in range(MAX_BULK_IDS + 1)]
    response = client.post('/api/v1/invoices/bulk_operations/', {
        'action': 'update_status', 'ids': ids, 'data': {'status': 'Overdue'}}, format='json')
    assert response.status_code == 400
    assert str(MAX_BULK_IDS) in response.json()['error']


def test_assign_needs_an_active_user(invoice_bulk):
    company = Company.objects.create(name='Assign Co', billing_entity='BMAsia Limited')
    task = Task.objects.create(company=company, title='Assign me')
    client = website_client(_user('bulk-person'))
    gone = _user('left-the-company')
    gone.is_active = False
    gone.save()
    for value in (str(gone.pk), 'not-an-id', None):
        response = client.post('/api/v1/tasks/bulk_operations/', {
            'action': 'assign', 'ids': [str(task.pk)], 'data': {'assigned_to': value}}, format='json')
        assert response.status_code == 400, value
    active = _user('takes-the-task')
    response = client.post('/api/v1/tasks/bulk_operations/', {
        'action': 'assign', 'ids': [str(task.pk)], 'data': {'assigned_to': str(active.pk)}}, format='json')
    assert response.json()['updated'] == 1
    task.refresh_from_db()
    assert task.assigned_to == active


# --- email templates: the one bulk caller in the website -----------------------------------

def _template(name, template_type):
    return EmailTemplate.objects.create(name=name, template_type=template_type, subject='Hello', body_html='<p>Hi</p>',
                                        body_text='Hi')


def test_email_templates_activate_and_deactivate_with_one_audit_row_each():
    first, second = _template('T1', 'renewal_30_days'), _template('T2', 'renewal_14_days')
    client = website_client(_user('template-person'))
    response = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'deactivate', 'ids': [str(first.pk), str(second.pk)]}, format='json')
    assert response.status_code == 200
    assert response.json()['count'] == 2
    assert not EmailTemplate.objects.filter(is_active=True).exists()
    assert AuditLog.objects.filter(model_name='EmailTemplate', action='UPDATE').count() == 2
    client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'activate', 'ids': [str(first.pk)]}, format='json')
    first.refresh_from_db()
    assert first.is_active is True


def test_email_template_bulk_delete_keeps_templates_in_use():
    unused, used = _template('Unused', 'renewal_30_days'), _template('Used', 'renewal_14_days')
    sequence = EmailSequence.objects.create(name='Seq', created_by=_user('seq-owner'))
    SequenceStep.objects.create(sequence=sequence, step_number=1, name='Step', email_template=used)
    client = website_client(_user('template-person'))
    response = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'delete', 'ids': [str(unused.pk), str(used.pk)]}, format='json')
    results = {r['id']: r for r in response.json()['results']}
    assert results[str(unused.pk)]['deleted'] is True
    assert results[str(used.pk)]['deleted'] is False
    assert results[str(used.pk)]['code'] == 'delete_refused'
    assert EmailTemplate.objects.filter(pk=used.pk).exists()


@pytest.mark.parametrize('operation', ['delete', 'deactivate'])
def test_email_templates_are_not_changed_in_bulk_by_an_api_token(operation):
    template = _template('Token target', 'renewal_30_days')
    response = token_client(_user('template-agent', staff=True)).post('/api/v1/email-templates/bulk_operations/', {
        'action': operation, 'ids': [str(template.pk)]}, format='json')
    assert response.status_code == 403
    assert response.json()['code'] == 'not_for_agents'
    template.refresh_from_db()
    assert template.is_active is True


def test_email_template_replies_name_templates():
    first, second = _template('Word A', 'renewal_30_days'), _template('Word B', 'renewal_14_days')
    client = website_client(_user('template-person'))
    activated = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'activate', 'ids': [str(first.pk), str(second.pk)]}, format='json')
    assert activated.json()['message'] == '2 templates activated'
    deleted = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'delete', 'ids': [str(first.pk)]}, format='json')
    assert deleted.json()['message'] == '1 template deleted'


def test_each_record_counts_once_when_an_id_is_repeated():
    template = _template('Twice', 'renewal_30_days')
    client = website_client(_user('template-person'))
    deactivated = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'deactivate', 'ids': [str(template.pk), str(template.pk)]}, format='json')
    assert deactivated.json()['count'] == 1
    assert AuditLog.objects.filter(record_id=str(template.pk), action='UPDATE').count() == 1
    deleted = client.post('/api/v1/email-templates/bulk_operations/', {
        'action': 'delete', 'ids': [str(template.pk), str(template.pk)]}, format='json')
    assert deleted.status_code == 200
    assert deleted.json()['deleted'] == 1
    assert len(deleted.json()['results']) == 1


@pytest.mark.parametrize('operation', ['deactivate', 'delete'])
def test_a_record_removed_during_the_call_is_reported_not_found(monkeypatch, operation):
    from crm_app.views import EmailTemplateViewSet
    first, second = _template('First', 'renewal_30_days'), _template('Second', 'renewal_14_days')
    hook = 'perform_update' if operation == 'deactivate' else 'perform_destroy'
    original = getattr(EmailTemplateViewSet, hook)

    def remove_the_other_one(self, arg):
        EmailTemplate.objects.filter(pk=second.pk).delete()
        return original(self, arg)

    monkeypatch.setattr(EmailTemplateViewSet, hook, remove_the_other_one)
    response = website_client(_user('template-person')).post('/api/v1/email-templates/bulk_operations/', {
        'action': operation, 'ids': [str(first.pk), str(second.pk)]}, format='json')
    assert response.status_code == 200
    results = {r['id']: r for r in response.json()['results']}
    assert results[str(second.pk)]['error'] == 'Not found.'


# --- single deletes of configuration and history records -----------------------------------

def _contract_template(name='Standard'):
    return ContractTemplate.objects.create(name=name, template_type='preamble', content='Text')


@pytest.mark.parametrize('kind', ['token-non-staff', 'token-staff'])
def test_configuration_is_not_deleted_by_an_api_token(kind):
    template = _contract_template()
    client = token_client(_user(f'cfg-{kind}', staff=kind == 'token-staff'))
    response = client.delete(f'/api/v1/contract-templates/{template.pk}/')
    assert response.status_code == 403
    assert response.json()['code'] == 'not_for_agents'
    assert ContractTemplate.objects.filter(pk=template.pk).exists()


def test_a_person_who_also_holds_a_token_works_on_the_website():
    person = _user('person-with-script-token')
    Token.objects.create(user=person)
    template = _template('Unused by person', 'renewal_30_days')
    client = website_client(person)
    assert client.patch(f'/api/v1/email-templates/{template.pk}/', {'subject': 'New'}, format='json').status_code == 200
    assert client.delete(f'/api/v1/email-templates/{template.pk}/').status_code == 204


def test_an_agent_name_on_the_website_counts_as_an_agent():
    template = _template('Agent target', 'renewal_30_days')
    response = website_client(_user('lyra')).delete(f'/api/v1/email-templates/{template.pk}/')
    assert response.status_code == 403
    assert response.json()['code'] == 'not_for_agents'


@pytest.mark.parametrize('route,payload', [
    ('email-templates', {'subject': 'Changed'}),
    ('contract-templates', {'content': 'Changed'}),
])
def test_configuration_is_not_created_or_changed_by_an_api_token(route, payload):
    record = _template('Cfg', 'renewal_30_days') if route == 'email-templates' else _contract_template()
    client = token_client(_user('cfg-agent', staff=True))
    for response in (client.patch(f'/api/v1/{route}/{record.pk}/', payload, format='json'),
                     client.put(f'/api/v1/{route}/{record.pk}/', payload, format='json'),
                     client.post(f'/api/v1/{route}/', payload, format='json')):
        assert response.status_code == 403
        assert response.json()['code'] == 'not_for_agents'
    record.refresh_from_db()
    assert getattr(record, 'subject', getattr(record, 'content', None)) in ('Hello', 'Text')


def test_cira_still_creates_and_updates_contract_templates_but_does_not_delete_them():
    client = token_client(_user('cira'))
    created = client.post('/api/v1/contract-templates/', {
        'name': 'Agent made', 'template_type': 'preamble', 'content': 'Text'}, format='json')
    assert created.status_code == 201
    template_id = created.json()['id']
    assert client.patch(f'/api/v1/contract-templates/{template_id}/', {'content': 'New'},
                        format='json').status_code == 200
    assert client.delete(f'/api/v1/contract-templates/{template_id}/').status_code == 403
    other = token_client(_user('lyra'))
    assert other.patch(f'/api/v1/contract-templates/{template_id}/', {'content': 'x'},
                       format='json').status_code == 403


def test_the_agents_tools_write_contract_templates_only_for_cira():
    import json
    from types import SimpleNamespace

    from mcp_server.djangomcp import django_request_ctx

    from crm_app.mcp import create_record, update_record
    template = _contract_template()
    for username, allowed in (('cira', True), ('lyra', False), ('script-holder', False)):
        token = django_request_ctx.set(SimpleNamespace(user=_user(username), META={}))
        try:
            updated = update_record('contracttemplate', str(template.pk), json.dumps({'content': f'By {username}'}))
            created = create_record('contracttemplate', json.dumps(
                {'name': f'New by {username}', 'template_type': 'preamble', 'content': 'x'}))
        finally:
            django_request_ctx.reset(token)
        assert updated.startswith('Error:') is not allowed, (username, updated)
        assert created.startswith('Error:') is not allowed, (username, created)
    template.refresh_from_db()
    assert template.content == 'By cira'


def test_an_unused_contract_template_is_deleted_by_a_person():
    template = _contract_template()
    assert website_client(_user('cfg-person')).delete(f'/api/v1/contract-templates/{template.pk}/').status_code == 204


def test_a_contract_template_in_use_is_kept_and_the_alternative_works():
    template = _contract_template()
    company = Company.objects.create(name='Template User Co', billing_entity='BMAsia Limited')
    Contract.objects.create(company=company, contract_number='HK-CT-TPL-1', start_date=date(2026, 1, 1),
                            end_date=date(2026, 12, 31), value=Decimal('1'), preamble_template=template)
    client = website_client(_user('cfg-person'))
    response = client.delete(f'/api/v1/contract-templates/{template.pk}/')
    assert response.status_code == 409
    body = response.json()
    assert body['references'] == {'contracts': 1}
    assert client.patch(body['alternative']['path'], body['alternative']['data'], format='json').status_code == 200
    template.refresh_from_db()
    assert template.is_active is False


def test_a_sequence_with_enrolments_is_kept():
    from crm_app.models import Contact, SequenceEnrollment
    owner = _user('seq-owner')
    sequence = EmailSequence.objects.create(name='Seq', created_by=owner)
    company = Company.objects.create(name='Seq Co', billing_entity='BMAsia Limited')
    contact = Contact.objects.create(company=company, name='Enrolled', email='enrolled@example.com')
    SequenceEnrollment.objects.create(sequence=sequence, contact=contact, company=company)
    response = website_client(_user('seq-person')).delete(f'/api/v1/email-sequences/{sequence.pk}/')
    assert response.status_code == 409
    assert response.json()['references'] == {'sequence enrollments': 1}


def test_a_ticket_with_comments_is_kept_but_a_new_one_can_go():
    person = _user('ticket-person')
    company = Company.objects.create(name='Ticket Co', billing_entity='BMAsia Limited')
    worked = Ticket.objects.create(company=company, subject='Zone offline', description='x')
    TicketComment.objects.create(ticket=worked, author=person, text='Restarted the player')
    fresh = Ticket.objects.create(company=company, subject='Typo ticket', description='x')
    client = website_client(person)
    assert client.delete(f'/api/v1/tickets/{worked.pk}/').status_code == 409
    assert client.delete(f'/api/v1/tickets/{fresh.pk}/').status_code == 204


def test_a_kb_article_linked_to_a_ticket_is_kept():
    person = _user('kb-person')
    category = KBCategory.objects.create(name='Players', slug='players')
    article = KBArticle.objects.create(title='Restart a player', slug='restart', content='x', category=category,
                                       author=person)
    company = Company.objects.create(name='KB Co', billing_entity='BMAsia Limited')
    ticket = Ticket.objects.create(company=company, subject='Zone offline', description='x')
    TicketKBArticle.objects.create(ticket=ticket, article=article, linked_by=person)
    response = website_client(person).delete(f'/api/v1/kb/articles/{article.pk}/')
    assert response.status_code == 409
    assert 'ticket' in str(response.json()['references'])


# --- records that carry history ---------------------------------------------------------------

def _company(name='History Co'):
    company, _ = Company.objects.get_or_create(name=name, defaults={'billing_entity': 'BMAsia Limited'})
    return company


def _refused(client, path):
    response = client.delete(path)
    assert response.status_code == 409, response.content
    body = response.json()
    assert body['code'] == 'delete_refused'
    return body


def test_a_campaign_that_was_sent_or_has_recipients_is_kept():
    from crm_app.models import CampaignRecipient, Contact, EmailCampaign
    client = website_client(_user('campaign-person'))
    sent = EmailCampaign.objects.create(name='Sent one', campaign_type='newsletter', status='sent')
    body = _refused(client, f'/api/v1/campaigns/{sent.pk}/')
    assert body['alternative']['data'] == {'status': 'cancelled'}
    listed = EmailCampaign.objects.create(name='With recipients', campaign_type='newsletter')
    contact = Contact.objects.create(company=_company(), name='Reader', email='reader@example.com')
    CampaignRecipient.objects.create(campaign=listed, contact=contact)
    assert _refused(client, f'/api/v1/campaigns/{listed.pk}/')['references'] == {'campaign recipients': 1}
    empty = EmailCampaign.objects.create(name='Empty draft', campaign_type='newsletter')
    assert client.delete(f'/api/v1/campaigns/{empty.pk}/').status_code == 204


def test_an_opportunity_with_activities_is_kept_on_the_website_and_in_the_agents_tool():
    from crm_app.mcp import delete_record
    from crm_app.models import Opportunity, OpportunityActivity
    person = _user('opportunity-person')
    worked = Opportunity.objects.create(company=_company(), name='Worked deal', owner=person)
    OpportunityActivity.objects.create(opportunity=worked, activity_type='Call', subject='Intro', description='x',
                                       user=person)
    body = _refused(website_client(person), f'/api/v1/opportunities/{worked.pk}/')
    assert body['alternative']['data'] == {'stage': 'Lost'}
    assert delete_record('opportunity', str(worked.pk)).startswith('Error: Worked deal cannot be deleted')
    fresh = Opportunity.objects.create(company=_company(), name='Typo deal', owner=person)
    assert website_client(person).delete(f'/api/v1/opportunities/{fresh.pk}/').status_code == 204


def test_contract_documents_are_deleted_by_a_person_only_while_the_contract_is_a_draft():
    from crm_app.models import ContractDocument
    def document(contract_status, number):
        contract = Contract.objects.create(company=_company(), contract_number=number, status=contract_status,
                                           start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), value=Decimal('1'))
        return ContractDocument.objects.create(contract=contract, document_type='generated', title='Doc',
                                               file='contract_documents/doc.pdf')
    person = website_client(_user('document-person'))
    signed = document('Active', 'HK-CT-DOC-1')
    assert 'Draft' in _refused(person, f'/api/v1/contract-documents/{signed.pk}/')['error']
    draft = document('Draft', 'HK-CT-DOC-2')
    agent = token_client(_user('document-agent', staff=True))
    response = agent.delete(f'/api/v1/contract-documents/{draft.pk}/')
    assert (response.status_code, response.json()['code']) == (403, 'not_for_agents')
    assert person.delete(f'/api/v1/contract-documents/{draft.pk}/').status_code == 204


def test_comments_on_a_closed_ticket_are_kept():
    person = _user('closed-ticket-person')
    closed = Ticket.objects.create(company=_company(), subject='Done', description='x', status='closed')
    kept = TicketComment.objects.create(ticket=closed, author=person, text='Fixed')
    open_ticket = Ticket.objects.create(company=_company(), subject='Open', description='x')
    typo = TicketComment.objects.create(ticket=open_ticket, author=person, text='Typo')
    client = website_client(person)
    assert 'closed' in _refused(client, f'/api/v1/ticket-comments/{kept.pk}/')['error']
    assert client.delete(f'/api/v1/ticket-comments/{typo.pk}/').status_code == 204


def test_expenses_that_are_approved_or_paid_are_kept_and_linked_finance_records_too():
    from crm_app.models import ExpenseCategory, ExpenseEntry, RecurringExpense, Vendor
    category = ExpenseCategory.objects.create(name='Hosting', category_type='opex_gna')
    vendor = Vendor.objects.create(name='Hosting vendor')
    client = website_client(_user('expense-person'))
    for status_value in ('approved', 'paid'):
        expense = ExpenseEntry.objects.create(description=f'Bill {status_value}', category=category, vendor=vendor,
                                              amount=Decimal('5'), expense_date=date(2026, 11, 1), status=status_value)
        assert _refused(client, f'/api/v1/expenses/{expense.pk}/')['alternative']['data'] == {'status': 'cancelled'}
    assert _refused(client, f'/api/v1/vendors/{vendor.pk}/')['references'] == {'expense entries': 2}
    draft = ExpenseEntry.objects.create(description='Draft bill', category=category, amount=Decimal('5'),
                                        expense_date=date(2026, 11, 1))
    assert client.delete(f'/api/v1/expenses/{draft.pk}/').status_code == 204
    assert RecurringExpense in __import__('crm_app.services.delete_guards', fromlist=['OWN_PARTS']).OWN_PARTS


def test_a_device_a_zone_uses_is_kept():
    from crm_app.models import Device, Zone
    company = _company()
    device = Device.objects.create(company=company, name='Player 1')
    Zone.objects.create(company=company, name='Lobby', device=device)
    assert _refused(website_client(_user('device-person')), f'/api/v1/devices/{device.pk}/')['references'] == {
        'zones': 1}


def test_a_user_who_created_sequences_is_kept_and_the_reply_names_them():
    leaver = _user('former-colleague')
    EmailSequence.objects.create(name='Their sequence', created_by=leaver)
    staff = _user('staff-person', staff=True)
    body = _refused(website_client(staff), f'/api/v1/users/{leaver.pk}/')
    assert '1 email sequence' in body['error']
    assert body['alternative']['data'] == {'is_active': False}
    assert EmailSequence.objects.filter(name='Their sequence').exists()


def test_configuration_used_by_other_records_without_a_link_is_kept():
    from crm_app.models import CorporatePdfTemplate, SeasonalTriggerDate
    from django.utils import timezone
    client = website_client(_user('cfg-person'))
    group = _company('Group HQ')
    member = Company.objects.create(name='Group Hotel', billing_entity='BMAsia Limited', parent_company=group)
    Contract.objects.create(company=member, contract_number='HK-CT-GRP-1', start_date=date(2026, 1, 1),
                            end_date=date(2026, 12, 31), value=Decimal('1'))
    used = CorporatePdfTemplate.objects.create(company=group, name='Group format')
    assert 'print with it' in _refused(client, f'/api/v1/corporate-pdf-templates/{used.pk}/')['error']
    year = timezone.localdate().year
    EmailSequence.objects.create(name='CNY', sequence_type='auto_seasonal_cny', status='active',
                                 created_by=_user('seq-owner'))
    current = SeasonalTriggerDate.objects.create(holiday_type='auto_seasonal_cny', trigger_date=date(year, 12, 1),
                                                 year=year)
    assert 'seasonal' in _refused(client, f'/api/v1/seasonal-trigger-dates/{current.pk}/')['error']
    past = SeasonalTriggerDate.objects.create(holiday_type='auto_seasonal_cny', trigger_date=date(year - 1, 12, 1),
                                              year=year - 1)
    assert client.delete(f'/api/v1/seasonal-trigger-dates/{past.pk}/').status_code == 204


# --- actions that change many records or reach outside the CRM --------------------------------

def _finance_person(role='Finance'):
    user = _user(f'{role.lower()}-person')
    user.role = role
    user.save()
    return website_client(user)


WEBSITE_ROLE_ROUTES = [
    # (method, path, roles that may)
    ('post', '/api/v1/revenue/classify-contracts/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue/generate-snapshots/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue/initialize/', {'Finance', 'Admin'}),
    ('post', '/api/v1/expense-categories/initialize-defaults/', {'Finance', 'Admin'}),
    ('post', '/api/v1/recurring-expenses/1/generate-entries/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue-recognition/import/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue-recognition/generate/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue-recognition/regenerate/', {'Finance', 'Admin'}),
    ('post', '/api/v1/revenue-recognition/schedules/1/cancel/', {'Finance', 'Admin'}),
    ('patch', '/api/v1/revenue-recognition/schedules/1/update/', {'Finance', 'Admin'}),
    ('get', '/api/v1/invoices/export-quickbooks/', {'Finance', 'Admin'}),
    ('get', '/api/v1/profit-loss/export/pdf/', {'Finance', 'Admin'}),
    ('get', '/api/v1/profit-loss/export/excel/', {'Finance', 'Admin'}),
    ('get', '/api/v1/cash-flow/export/pdf/', {'Finance', 'Admin'}),
    ('get', '/api/v1/cash-flow/export/excel/', {'Finance', 'Admin'}),
    ('get', '/api/v1/balance-sheet/export/pdf/', {'Finance', 'Admin'}),
    ('get', '/api/v1/balance-sheet/export/excel/', {'Finance', 'Admin'}),
    ('get', '/api/v1/revenue-recognition/export/excel/', {'Finance', 'Admin'}),
    ('get', '/api/v1/opportunities/export/pdf/', {'Sales', 'Admin'}),
    ('get', '/api/v1/opportunities/export/sales-performance-pdf/', {'Sales', 'Admin'}),
    ('post', '/api/v1/zones/sync-all/', {'Tech', 'Admin'}),
    ('post', '/api/v1/zones/00000000-0000-0000-0000-000000000001/sync/', {'Tech', 'Admin'}),
    ('delete', '/api/v1/zones/00000000-0000-0000-0000-000000000001/hard-delete/', {'Admin'}),
    ('post', '/api/v1/automation/test-run/', {'Admin'}),
]


@pytest.mark.parametrize('method,path,roles', WEBSITE_ROLE_ROUTES)
def test_bulk_finance_sync_and_export_routes_need_a_person_on_the_website_with_the_role(method, path, roles):
    token = token_client(_user('route-agent', staff=True))
    assert getattr(token, method)(path).status_code == 403
    for role in ('Sales', 'Finance', 'Tech', 'Music'):
        if role in roles:
            continue
        assert getattr(_finance_person(role), method)(path).status_code == 403, role


def test_the_automation_test_run_does_not_send_unless_switched_on(settings, monkeypatch):
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: calls.append(a) or None)
    admin = _finance_person('Admin')
    for value in (False, 'false'):
        response = admin.post('/api/v1/automation/test-run/', {'type': 'renewal', 'dry_run': value}, format='json')
        assert (response.status_code, response.json()['code']) == (403, 'manual_send_disabled')
    assert calls == []
    assert settings.EMAIL_AUTOMATION_MANUAL_SEND_ENABLED is False


def test_zone_hard_delete_is_for_staff_or_admin_on_the_website():
    from crm_app.models import Zone
    zone = Zone.objects.create(company=_company(), name='Gone zone', is_orphaned=True)
    assert token_client(_user('zone-agent', staff=True)).delete(f'/api/v1/zones/{zone.pk}/hard-delete/').status_code == 403
    assert website_client(_user('zone-admin')).delete(f'/api/v1/zones/{zone.pk}/hard-delete/').status_code == 200


# --- every route classified ----------------------------------------------------------------

# Bulk operations each record type offers, and why. Anything else answers 405.
EXPECTED_BULK = {
    'email-templates': {'activate', 'deactivate', 'delete'},  # the Email Templates page
}

# How a single DELETE is decided, per route (crm_app/services/delete_guards.py).
DELETE_RULES = {
    # The five customer records: Draft / unused only, alternative named.
    'companies': 'history', 'contacts': 'history', 'contracts': 'history', 'invoices': 'history',
    'quotes': 'history',
    # Configuration: a person, and only while nothing refers to it.
    'email-templates': 'configuration', 'email-sequences': 'configuration', 'sequence-steps': 'configuration',
    'prospect-sequences': 'configuration', 'contract-templates': 'configuration',
    'corporate-pdf-templates': 'configuration', 'static-documents': 'configuration',
    'seasonal-trigger-dates': 'configuration', 'segments': 'configuration', 'kb/categories': 'configuration',
    'kb/tags': 'configuration',
    # History records: only while nothing refers to them.
    'sequence-enrollments': 'referenced', 'prospect-enrollments': 'referenced', 'tickets': 'referenced',
    'kb/articles': 'referenced', 'zones': 'referenced',
    # Leaf rows nothing else points at; a protecting reference still answers 409.
    'campaigns': 'referenced', 'opportunities': 'referenced', 'vendors': 'referenced',
    'recurring-expenses': 'referenced', 'devices': 'referenced',
    # Their own state decides.
    'campaigns-sent': None, 'expenses': 'not approved or paid', 'ticket-comments': 'open ticket',
    'ticket-attachments': 'open ticket', 'contract-documents': 'a person, Draft contract',
    # Leaf rows nothing else points at; a protecting reference still answers 409.
    'notes': 'plain', 'tasks': 'plain', 'opportunity-activities': 'plain', 'expense-categories': 'plain',
    'kb/article-ratings': 'plain', 'kb/article-relations': 'plain', 'kb/article-attachments': 'plain',
    'kb/ticket-articles': 'plain', 'client-tech-details': 'plain', 'ai-email-drafts': 'plain',
    # Users: staff only (UserViewSet.get_permissions), and not while they own email sequences.
    'users': 'staff only, no sequences',
}
DELETE_RULES.pop('campaigns-sent')

# Every custom action that writes (POST, PUT, PATCH, DELETE), on every router:
# read = changes nothing; own-account = the caller's own sign-in or profile;
# rule = writes, under the rule named; refused = answers 405 unless enabled (bulk_operations).
ACTION_RULES = {
    # agent_inbox (PR 58): a reviewer is a person on the website
    ('activities', 'void'): 'rule: agent_inbox void rules',
    ('change-proposals', 'bulk_reject'): 'rule: reviewer on the website',
    ('change-proposals', 'accept'): 'rule: reviewer on the website',
    ('change-proposals', 'accept_with_edits'): 'rule: reviewer on the website',
    ('change-proposals', 'reject'): 'rule: reviewer on the website',
    ('change-proposals', 'reopen'): 'rule: reviewer on the website',
    # users
    ('users', 'change_password'): 'own-account', ('users', 'me'): 'own-account',
    ('users', 'test_smtp'): 'own-account', ('users', 'update_smtp'): 'own-account',
    ('users', 'upload_avatar'): 'own-account', ('users', 'test_smtp_send'): 'rule: own account or Admin',
    # customer records
    ('tasks', 'comments'): 'rule: task assignee permission',
    ('opportunities', 'advance_stage'): 'rule: serializer',
    ('contracts', 'add_zones'): 'rule: contract zone rules', ('contracts', 'remove_zone'): 'rule: contract zone rules',
    ('contracts', 'update_zones'): 'rule: contract zone rules',
    ('contracts', 'duplicate_for_renewal'): 'rule: creates a Draft',
    ('contracts', 'send'): 'rule: sends one contract', ('contracts', 'send_renewal_notice'): 'rule: sends one notice',
    ('invoices', 'mark_paid'): 'rule: payment service', ('invoices', 'send'): 'rule: invoice status rule',
    ('invoices', 'send_receipt'): 'rule: Paid only',
    ('quotes', 'accept'): 'rule: quote status', ('quotes', 'reject'): 'rule: quote status',
    ('quotes', 'add_attachment'): 'rule: one quote', ('quotes', 'convert_to_contract'): 'rule: creates a Draft',
    ('quotes', 'send'): 'rule: sends one quote',
    # marketing and sequences
    ('campaigns', 'add_recipients'): 'rule: one campaign', ('campaigns', 'pause'): 'rule: campaign status',
    ('campaigns', 'resume'): 'rule: campaign status', ('campaigns', 'schedule'): 'rule: campaign status',
    ('campaigns', 'send'): 'rule: sends one campaign', ('campaigns', 'test'): 'rule: one test email',
    ('email-templates', 'duplicate'): 'rule: configuration, a person',
    ('sequence-enrollments', 'enroll'): 'rule: one enrolment',
    ('sequence-enrollments', 'trigger_send'): 'rule: one step', ('sequence-enrollments', 'unenroll'): 'rule: one',
    ('segments', 'validate_filters'): 'read', ('segments', 'duplicate'): 'rule: configuration, a person',
    ('segments', 'enroll_in_sequence'): 'rule: enrols the segment',
    ('segments', 'recalculate'): 'rule: the segment count',
    ('prospect-sequences', 'enroll'): 'rule: one enrolment',
    ('prospect-enrollments', 'cancel'): 'rule: one', ('prospect-enrollments', 'pause'): 'rule: one',
    ('prospect-enrollments', 'resume'): 'rule: one',
    ('ai-email-drafts', 'approve'): 'rule: one draft', ('ai-email-drafts', 'edit_and_approve'): 'rule: one draft',
    ('ai-email-drafts', 'reject'): 'rule: one draft',
    # support
    ('tickets', 'add_comment'): 'rule: one ticket', ('tickets', 'assign'): 'rule: one ticket',
    ('kb/articles', 'add_attachment'): 'rule: one article', ('kb/articles', 'link_to_ticket'): 'rule: one link',
    ('kb/articles', 'rate'): 'rule: own rating', ('kb/articles', 'record_view'): 'rule: own view',
    ('client-tech-details', 'clone'): 'rule: one copy',
    # zones: music-service sync and hard delete
    ('zones', 'sync_all'): 'rule: staff or Tech on the website', ('zones', 'sync'): 'rule: staff or Tech on the website',
    ('zones', 'hard_delete'): 'rule: staff or Admin on the website, orphaned zones only',
    # finance
    ('revenue', 'classify_contracts'): 'rule: Finance or Admin on the website',
    ('revenue', 'generate_snapshots'): 'rule: Finance or Admin on the website',
    ('revenue', 'initialize'): 'rule: Finance or Admin on the website',
    ('revenue', 'targets'): 'rule: one target',
    ('expense-categories', 'initialize_defaults'): 'rule: Finance or Admin on the website',
    ('recurring-expenses', 'generate_entries'): 'rule: Finance or Admin on the website',
    ('expenses', 'approve'): 'rule: one expense', ('expenses', 'cancel'): 'rule: one expense',
    ('expenses', 'pay'): 'rule: one expense',
    ('revenue-recognition', 'cancel_schedule'): 'rule: Finance or Admin on the website',
    ('revenue-recognition', 'update_schedule'): 'rule: Finance or Admin on the website',
    ('revenue-recognition', 'generate'): 'rule: Finance or Admin on the website',
    ('revenue-recognition', 'import_excel'): 'rule: Finance or Admin on the website',
    ('revenue-recognition', 'regenerate'): 'rule: Finance or Admin on the website',
    # email automation
    ('automation', 'test_run'): 'rule: Admin on the website; sends only when switched on',
}

# Views outside the routers that accept POST, PUT, PATCH or DELETE, by URL name.
VIEW_RULES = {
    'cara-touches': 'rule: Cara credential, switch', 'cara-care-summary': 'rule: Cara credential, switch',
    'auth_login': 'own-account', 'auth_refresh': 'own-account', 'auth_logout': 'own-account',
    'jwt_token_obtain_pair': 'own-account', 'jwt_token_refresh': 'own-account', 'jwt_token_verify': 'read',
    'api_token_auth': 'own-account',
    'admin_send_email': 'rule: staff session', 'admin_send_email_template': 'rule: staff session',
    'admin_send_email_company': 'rule: staff session', 'admin_bulk_email': 'rule: staff session',
    'admin_preview_email': 'read', 'admin_preview_email_template': 'read', 'admin_preview_email_company': 'read',
    'admin_preview_template': 'read', 'admin_send_test_email': 'rule: staff session',
}


def _routes():
    from crm_app.urls import router
    return router.registry


def test_every_viewset_with_delete_is_classified_and_guarded():
    from rest_framework import mixins

    from crm_app.services.delete_guards import GuardedDestroyMixin
    from crm_app.views import BaseModelViewSet
    unclassified, unguarded = [], []
    for prefix, viewset, _basename in _routes():
        if not issubclass(viewset, mixins.DestroyModelMixin):
            continue
        if prefix not in DELETE_RULES:
            unclassified.append(prefix)
        if not issubclass(viewset, (BaseModelViewSet, GuardedDestroyMixin)):
            unguarded.append(prefix)
    assert unclassified == [], 'decide the delete rule for these routes and add them to DELETE_RULES'
    assert unguarded == [], 'single DELETE must go through crm_app/services/delete_guards.destroy_one'


def _all_routers():
    from agent_inbox.urls import router as inbox_router
    from crm_app.urls import router
    return list(router.registry) + list(inbox_router.registry)


def test_every_custom_action_that_writes_is_classified():
    unclassified = []
    for prefix, viewset, _basename in _all_routers():
        for extra in viewset.get_extra_actions():
            if extra.__name__ == 'bulk_operations':
                continue  # EXPECTED_BULK
            methods = {m.lower() for m in extra.mapping}
            if methods & {'post', 'put', 'patch', 'delete'} and (prefix, extra.__name__) not in ACTION_RULES:
                unclassified.append((prefix, extra.__name__))
    assert unclassified == [], 'decide the rule for these actions and add them to ACTION_RULES'


def test_every_view_outside_the_routers_that_writes_is_classified():
    from crm_app.urls import urlpatterns
    unclassified = []
    for pattern in urlpatterns:
        callback = getattr(pattern, 'callback', None)
        if callback is None:  # include(router.urls): walked above
            continue
        view_class = getattr(callback, 'view_class', None) or getattr(callback, 'cls', None)
        actions = getattr(callback, 'actions', None)
        if actions is not None:
            writes = set(actions) & {'post', 'put', 'patch', 'delete'}
        elif view_class is not None:
            writes = {m for m in ('post', 'put', 'patch', 'delete') if hasattr(view_class, m)}
        else:
            writes = {'post'}  # a function view: assume it may write
        if writes and pattern.name not in VIEW_RULES:
            unclassified.append(pattern.name)
    assert unclassified == [], 'decide the rule for these views and add them to VIEW_RULES'


def test_bulk_operations_are_enabled_only_where_classified():
    from crm_app.views import BaseModelViewSet
    found = {}
    for prefix, viewset, _basename in _routes():
        if issubclass(viewset, BaseModelViewSet):
            allowed = set(getattr(viewset, 'bulk_allowed', set()))
            if allowed:
                found[prefix] = allowed
    assert found == EXPECTED_BULK


def test_the_delete_rules_cover_the_configuration_and_history_models():
    from crm_app.services import delete_guards
    for model in (ContractTemplate, EmailSequence, EmailTemplate, KBArticle, KBCategory, Ticket):
        assert model in delete_guards.OWN_PARTS


def test_the_agents_delete_tool_follows_the_same_rules():
    from crm_app.mcp import delete_record
    person = _user('mcp-ticket-person')
    company = Company.objects.create(name='MCP Ticket Co', billing_entity='BMAsia Limited')
    worked = Ticket.objects.create(company=company, subject='Zone offline', description='x')
    TicketComment.objects.create(ticket=worked, author=person, text='Restarted the player')
    fresh = Ticket.objects.create(company=company, subject='Typo ticket', description='x')
    message = delete_record('ticket', str(worked.pk))
    assert message.startswith('Error: Zone offline cannot be deleted')
    assert "update_record('ticket', id, '{\"status\": \"closed\"}')" in message
    assert Ticket.objects.filter(pk=worked.pk).exists()
    assert delete_record('ticket', str(fresh.pk)).startswith('Deleted ticket')
