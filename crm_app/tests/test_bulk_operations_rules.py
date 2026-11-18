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
    assert response.status_code == 405
    assert 'error' in response.json()


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


def test_email_templates_are_not_deleted_by_an_api_token():
    template = _template('Token target', 'renewal_30_days')
    response = token_client(_user('template-agent', staff=True)).post('/api/v1/email-templates/bulk_operations/', {
        'action': 'delete', 'ids': [str(template.pk)]}, format='json')
    assert response.json()['results'][0]['code'] == 'not_for_agents'
    assert EmailTemplate.objects.filter(pk=template.pk).exists()


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
    'notes': 'plain', 'tasks': 'plain', 'opportunities': 'plain', 'opportunity-activities': 'plain',
    'campaigns': 'plain', 'vendors': 'plain', 'expense-categories': 'plain', 'recurring-expenses': 'plain',
    'expenses': 'plain', 'ticket-comments': 'plain', 'ticket-attachments': 'plain',
    'kb/article-ratings': 'plain', 'kb/article-relations': 'plain', 'kb/article-attachments': 'plain',
    'kb/ticket-articles': 'plain', 'devices': 'plain', 'client-tech-details': 'plain',
    'contract-documents': 'plain', 'ai-email-drafts': 'plain',
    # Users: staff only (UserViewSet.get_permissions).
    'users': 'staff only',
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
