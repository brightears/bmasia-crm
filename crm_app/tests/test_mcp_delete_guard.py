"""MCP delete_record refuses records whose delete would erase customer history."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from mcp_server.djangomcp import django_request_ctx

from crm_app.mcp import delete_record
from crm_app.models import (
    AuditLog, Company, Contact, Contract, Invoice, Quote, QuoteLineItem, Task,
)


@contextmanager
def as_agent(username='cira'):
    user, _ = get_user_model().objects.get_or_create(
        username=username, defaults={'email': f'{username}@example.test', 'role': 'Admin'},
    )
    request = SimpleNamespace(user=user, META={'REMOTE_ADDR': '10.0.0.7', 'HTTP_USER_AGENT': 'agent-test'})
    token = django_request_ctx.set(request)
    try:
        yield user
    finally:
        django_request_ctx.reset(token)


@pytest.fixture
def company():
    return Company.objects.create(name='Guarded Bay Hotel', billing_entity='BMAsia Limited')


def _records(company):
    contract = Contract.objects.create(
        company=company, contract_number='HK-CT-GUARD-1', status='Active',
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), value=Decimal('100'),
    )
    quote = Quote.objects.create(company=company, quote_number='HK-QT-GUARD-1',
                                 valid_from=date(2026, 1, 1), valid_until=date(2026, 2, 1))
    invoice = Invoice.objects.create(company=company, invoice_number='INV-GUARD-1', issue_date=date(2026, 1, 1),
                                     due_date=date(2026, 2, 1), amount=Decimal('100'), total_amount=Decimal('100'))
    contact = Contact.objects.create(company=company, name='Guard Contact', email='guard@example.test')
    return {'company': company, 'contract': contract, 'quote': quote, 'invoice': invoice, 'contact': contact}


@pytest.mark.parametrize('collection, alternative', [
    ('company', '{"is_active": false}'),
    ('contact', '{"is_active": false}'),
    ('contract', '{"status": "Cancelled"}'),
    ('quote', '{"status": "Rejected"}'),
    ('invoice', '{"status": "Cancelled"}'),
])
def test_history_records_are_not_deleted_and_the_alternative_is_named(company, collection, alternative):
    record = _records(company)[collection]
    with as_agent():
        message = delete_record(collection, str(record.pk))

    assert message.startswith(f'Error: Deleting a {collection} is blocked')
    assert f"update_record('{collection}', id, {alternative})" in message
    assert type(record).objects.filter(pk=record.pk).exists()
    assert Company.objects.filter(pk=company.pk).exists()
    assert not AuditLog.objects.filter(action='DELETE').exists()


def test_refusal_happens_before_looking_the_record_up():
    with as_agent():
        message = delete_record('company', '00000000-0000-0000-0000-000000000000')
    assert 'is blocked' in message


def test_line_items_can_still_be_deleted(company):
    quote = _records(company)['quote']
    line = QuoteLineItem.objects.create(quote=quote, description='Extra zone', quantity=Decimal('1'),
                                        unit_price=Decimal('10'))
    with as_agent() as caller:
        message = delete_record('quotelineitem', str(line.pk))

    assert message.startswith('Deleted quotelineitem')
    assert not QuoteLineItem.objects.filter(pk=line.pk).exists()
    assert Quote.objects.filter(pk=quote.pk).exists()
    row = AuditLog.objects.get(action='DELETE', record_id=str(line.pk))
    assert row.user == caller


def test_tasks_can_still_be_deleted(company):
    task = Task.objects.create(company=company, title='Call back')
    with as_agent():
        assert delete_record('task', str(task.pk)).startswith('Deleted task')
    assert not Task.objects.filter(pk=task.pk).exists()


def test_the_tool_description_names_the_alternatives():
    doc = delete_record.__doc__
    for text in ('company  -> {"is_active": false}', 'contract -> {"status": "Cancelled"}',
                 'quote    -> {"status": "Rejected"}', 'invoice  -> {"status": "Cancelled"}'):
        assert text in doc
