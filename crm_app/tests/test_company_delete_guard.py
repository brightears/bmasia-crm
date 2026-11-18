"""REST delete rules (crm_app/services/delete_guards.py), single and bulk.

- Company: only when nothing at all points at it (found from the model metadata).
- Contract, quote, invoice: only a Draft that nothing points at except its own parts.
- Contact: only an unused, non-primary contact.
Every refusal is a 409 with counts per kind and an alternative that works.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from crm_app.models import (
    AuditLog, CareTouch, Company, Contact, Contract, ContractLineItem, Invoice, InvoiceLineItem, Note,
    Opportunity, Quote, QuoteLineItem, Task, User,
)
from crm_app.services.delete_guards import cascading_relation_keys, reference_counts, referencing_relations

# Every relation whose rows a company delete would delete with it, as of this change. The guard
# finds and counts relations by itself; this list only makes a new one visible in review.
KNOWN_COMPANY_CASCADES = [
    'crm_app.CareTouch.company', 'crm_app.ClientTechDetail.company', 'crm_app.Contact.company',
    'crm_app.Contract.company', 'crm_app.CorporatePdfTemplate.company',
    'crm_app.CustomerSegment.static_companies', 'crm_app.Device.company', 'crm_app.DocumentAttachment.company',
    'crm_app.EmailCampaign.company', 'crm_app.EmailLog.company', 'crm_app.Invoice.company', 'crm_app.Note.company',
    'crm_app.Opportunity.company', 'crm_app.Quote.company', 'crm_app.SequenceEnrollment.company',
    'crm_app.Task.company', 'crm_app.Ticket.company', 'crm_app.Zone.company',
]


@pytest.fixture
def user():
    return User.objects.create_user(
        username='delete-tester', email='delete-tester@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _company(name='Keep Me Resort'):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited')


def _contract(company, number='HK-CT-DEL-1', status='Draft', **extra):
    return Contract.objects.create(company=company, contract_number=number, status=status,
                                   start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                                   value=Decimal('100'), **extra)


def _quote(company, number='HK-QT-DEL-1', status='Draft'):
    return Quote.objects.create(company=company, quote_number=number, status=status,
                                valid_from=date(2026, 1, 1), valid_until=date(2026, 2, 1))


def _invoice(company, number='INV-DEL-1', status='Draft', **extra):
    return Invoice.objects.create(company=company, invoice_number=number, status=status,
                                  issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1),
                                  amount=Decimal('100'), total_amount=Decimal('100'), **extra)


def _do_alternative(api, body):
    alt = body['alternative']
    assert alt['method'] == 'PATCH'
    response = api.patch(alt['path'], alt['data'], format='json')
    assert response.status_code == 200, response.data
    return response


# --- companies -----------------------------------------------------------------------------

def test_company_with_contacts_notes_and_an_opportunity_is_not_deleted(api):
    company = _company()
    Contact.objects.create(company=company, name='Buyer', email='buyer@example.com')
    Note.objects.create(company=company, title='Call', text='Called about 12 zones')
    Opportunity.objects.create(company=company, name='12 zones', stage='Contacted', expected_value=Decimal('1'))
    Task.objects.create(company=company, title='Call back')

    response = api.delete(f'/api/v1/companies/{company.pk}/')

    assert response.status_code == 409
    assert response.data['code'] == 'delete_refused'
    assert response.data['references'] == {'contacts': 1, 'notes': 1, 'opportunities': 1, 'tasks': 1}
    assert response.data['error'].startswith('Keep Me Resort cannot be deleted: 1 contact, 1 note, '
                                             '1 opportunity and 1 task refer to it')
    assert Company.objects.filter(pk=company.pk).exists()
    assert not AuditLog.objects.filter(action='DELETE').exists()
    _do_alternative(api, response.data)
    company.refresh_from_db()
    assert company.is_active is False


def test_company_with_care_touches_or_documents_is_not_deleted(api):
    company = _company()
    CareTouch.objects.create(company=company, idempotency_key='care-del-1', mailbox='care@example.com',
                             occurred_at=timezone.now(), kind='check_in', source='send',
                             recorded_by='care-agent', payload_sha256='0' * 64)
    response = api.delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 409
    assert response.data['references'] == {'care touches': 1}


def test_company_with_nothing_attached_can_be_deleted(api):
    company = _company('Typo Duplicate Ltd')
    response = api.delete(f'/api/v1/companies/{company.pk}/')
    assert response.status_code == 204
    assert not Company.objects.filter(pk=company.pk).exists()
    assert AuditLog.objects.filter(action='DELETE', record_id=str(company.pk)).count() == 1


def test_a_parent_company_with_child_companies_is_not_deleted(api):
    parent = _company('Group Parent')
    Company.objects.create(name='Group Child', billing_entity='BMAsia Limited', parent_company=parent)
    response = api.delete(f'/api/v1/companies/{parent.pk}/')
    assert response.status_code == 409
    assert list(response.data['references']) == ['companies linked by parent company']


def test_the_company_guard_queries_every_table_that_points_at_companies():
    """Found from the model metadata: a new relation is counted without changing the guard."""
    company = _company()
    with CaptureQueriesContext(connection) as queries:
        reference_counts(company)
    sql = ' '.join(q['sql'] for q in queries.captured_queries)
    for rel in referencing_relations(Company):
        table = (rel.through._meta.db_table if rel.many_to_many else rel.related_model._meta.db_table)
        assert table in sql, f'{rel} is not counted'


def test_known_cascading_relations_are_listed_for_review():
    """Fails when a new table cascades from Company: check its wording in the refusal, then add it here."""
    assert cascading_relation_keys(Company) == KNOWN_COMPANY_CASCADES


# --- contracts, quotes, invoices ----------------------------------------------------------

def test_draft_contract_with_only_its_own_parts_can_be_deleted(api):
    contract = _contract(_company())
    ContractLineItem.objects.create(contract=contract, description='Zone', quantity=Decimal('1'),
                                    unit_price=Decimal('10'))
    assert api.delete(f'/api/v1/contracts/{contract.pk}/').status_code == 204
    assert not Contract.objects.filter(pk=contract.pk).exists()


@pytest.mark.parametrize('status', ['Sent', 'Active', 'Expired', 'Cancelled'])
def test_contract_past_draft_is_not_deleted_and_cancelling_works(api, status):
    contract = _contract(_company(), status=status)
    response = api.delete(f'/api/v1/contracts/{contract.pk}/')
    assert response.status_code == 409
    assert f'it is {status}; only a Draft can be deleted' in response.data['error']
    assert response.data['alternative']['data'] == {'status': 'Cancelled'}
    _do_alternative(api, response.data)
    contract.refresh_from_db()
    assert contract.status == 'Cancelled'


def test_draft_contract_with_a_successor_or_an_invoice_is_not_deleted(api):
    company = _company()
    predecessor = _contract(company)
    _contract(company, number='HK-CT-DEL-2', renewed_from=predecessor)
    _invoice(company, contract=predecessor)
    response = api.delete(f'/api/v1/contracts/{predecessor.pk}/')
    assert response.status_code == 409
    assert response.data['references'] == {'contracts linked by renewed from': 1, 'invoices': 1}


def test_draft_quote_can_be_deleted_but_a_sent_one_is_rejected_instead(api):
    company = _company()
    draft = _quote(company)
    QuoteLineItem.objects.create(quote=draft, description='Zone', quantity=Decimal('1'), unit_price=Decimal('5'))
    assert api.delete(f'/api/v1/quotes/{draft.pk}/').status_code == 204

    sent = _quote(company, number='HK-QT-DEL-2', status='Sent')
    response = api.delete(f'/api/v1/quotes/{sent.pk}/')
    assert response.status_code == 409
    _do_alternative(api, response.data)
    sent.refresh_from_db()
    assert sent.status == 'Rejected'


def test_quote_converted_to_a_contract_is_not_deleted(api):
    company = _company()
    quote = _quote(company)
    _contract(company, quote=quote)
    response = api.delete(f'/api/v1/quotes/{quote.pk}/')
    assert response.status_code == 409
    assert response.data['references'] == {'contracts': 1}


def test_draft_invoice_can_be_deleted_but_a_sent_one_is_cancelled_instead(api):
    company = _company()
    draft = _invoice(company)
    InvoiceLineItem.objects.create(invoice=draft, description='Zone', quantity=Decimal('1'),
                                   tax_rate=Decimal('0'), unit_price=Decimal('10'), line_total=Decimal('10'))
    assert api.delete(f'/api/v1/invoices/{draft.pk}/').status_code == 204

    sent = _invoice(company, number='INV-DEL-2', status='Sent')
    response = api.delete(f'/api/v1/invoices/{sent.pk}/')
    assert response.status_code == 409
    _do_alternative(api, response.data)
    sent.refresh_from_db()
    assert sent.status == 'Cancelled'


# --- contacts ------------------------------------------------------------------------------

def test_unused_contact_can_be_deleted(api):
    contact = Contact.objects.create(company=_company(), name='Typo Contact', email='typo@example.com')
    assert api.delete(f'/api/v1/contacts/{contact.pk}/').status_code == 204


def test_contact_with_history_is_deactivated_instead(api):
    company = _company()
    contact = Contact.objects.create(company=company, name='Used Contact', email='used@example.com')
    Note.objects.create(company=company, contact=contact, title='Call', text='Spoke')
    response = api.delete(f'/api/v1/contacts/{contact.pk}/')
    assert response.status_code == 409
    assert response.data['references'] == {'notes': 1}
    _do_alternative(api, response.data)
    contact.refresh_from_db()
    assert contact.is_active is False


def test_primary_contact_is_not_deleted(api):
    contact = Contact.objects.create(company=_company(), name='Main Contact', email='main@example.com',
                                     is_primary=True)
    response = api.delete(f'/api/v1/contacts/{contact.pk}/')
    assert response.status_code == 409
    assert "primary contact" in response.data['error']


# --- bulk_operations delete ----------------------------------------------------------------

def _bulk_delete(api, path, ids):
    return api.post(f'/api/v1/{path}/bulk_operations/', {'action': 'delete', 'ids': [str(i) for i in ids]},
                    format='json')


def test_bulk_delete_applies_the_same_rules_record_by_record(api):
    keep = _company('Has History')
    _contract(keep, status='Active')
    _invoice(keep)
    empty = _company('Empty Duplicate')

    response = _bulk_delete(api, 'companies', [keep.pk, empty.pk, '00000000-0000-0000-0000-000000000009'])

    assert response.status_code == 200
    assert response.data['deleted'] == 1
    by_id = {r['id']: r for r in response.data['results']}
    assert by_id[str(keep.pk)]['deleted'] is False
    assert by_id[str(keep.pk)]['code'] == 'delete_refused'
    assert by_id[str(empty.pk)] == {'id': str(empty.pk), 'deleted': True}
    assert by_id['00000000-0000-0000-0000-000000000009']['error'] == 'Not found.'
    assert Company.objects.filter(pk=keep.pk).exists() and Contract.objects.filter(company=keep).exists()
    assert list(AuditLog.objects.filter(action='DELETE').values_list('record_id', flat=True)) == [str(empty.pk)]


@pytest.mark.parametrize('path, make', [
    ('contracts', lambda c: _contract(c, status='Active')),
    ('quotes', lambda c: _quote(c, status='Sent')),
    ('invoices', lambda c: _invoice(c, status='Sent')),
    ('contacts', lambda c: Contact.objects.create(company=c, name='P', email='p@example.com', is_primary=True)),
])
def test_bulk_delete_refuses_what_a_single_delete_refuses(api, path, make):
    record = make(_company())
    response = _bulk_delete(api, path, [record.pk])
    assert response.data['deleted'] == 0
    assert type(record).objects.filter(pk=record.pk).exists()
    assert not AuditLog.objects.filter(action='DELETE').exists()


def test_a_delete_refused_by_a_protecting_key_leaves_no_audit_row(api):
    """perform_destroy writes the audit row and deletes in one transaction."""
    task = Task.objects.create(company=_company(), title='Protected task')
    with mock.patch.object(Task, 'delete', side_effect=ProtectedError('blocked', {task})):
        single = api.delete(f'/api/v1/tasks/{task.pk}/')
        bulk = _bulk_delete(api, 'tasks', [task.pk])
    assert single.status_code == 409 and single.data['code'] == 'protected'
    assert bulk.data['results'][0]['code'] == 'protected'
    assert not AuditLog.objects.filter(action='DELETE').exists()
