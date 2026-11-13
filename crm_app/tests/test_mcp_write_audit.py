"""Every MCP write leaves exactly one AuditLog row naming the authenticated caller."""
import json
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.http import Http404
from mcp_server.djangomcp import django_request_ctx

from crm_app import mcp
from crm_app.mcp import (
    convert_quote_to_contract, create_record, delete_record, generate_contract_pdf,
    generate_invoice_pdf, generate_proforma_pdf, generate_quote_pdf, update_record,
)
from crm_app.models import (
    AuditLog, Company, Contact, Contract, Invoice, Opportunity, Quote, QuoteLineItem, Task, Ticket,
)
from crm_app.serializers import CompanySerializer, ContractSerializer, OpportunitySerializer
from crm_app.services import mcp_audit
from crm_app.services.rene_phase2_common import rfc3339
from crm_app.views import BaseModelViewSet


def _user(username, role='Sales'):
    user, _ = get_user_model().objects.get_or_create(
        username=username, defaults={'email': f'{username}@example.test', 'role': role},
    )
    return user


@contextmanager
def as_caller(user, **meta):
    request = SimpleNamespace(user=user, META={'REMOTE_ADDR': '10.0.0.7', 'HTTP_USER_AGENT': 'agent-test', **meta})
    token = django_request_ctx.set(request)
    try:
        yield user
    finally:
        django_request_ctx.reset(token)


def _company(name='Audit fixture company'):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited')


def _rows(**filters):
    return list(AuditLog.objects.filter(**filters))


# ------------------------------------------------------------------ create


def test_create_record_writes_one_create_row_attributed_to_caller():
    caller = _user('theo')
    with as_caller(caller):
        result = json.loads(create_record('company', json.dumps({
            'name': 'Audit Create Hotel', 'country': 'Thailand', 'billing_entity': 'BMAsia Limited',
        })))

    rows = _rows(record_id=result['id'])
    assert len(rows) == 1
    row = rows[0]
    assert (row.action, row.model_name, row.user) == ('CREATE', 'Company', caller)
    assert row.changes == {
        'name': {'old': None, 'new': 'Audit Create Hotel'},
        'country': {'old': None, 'new': 'Thailand'},
        'billing_entity': {'old': None, 'new': 'BMAsia Limited'},
    }
    assert row.additional_data['via'] == 'mcp'
    assert row.additional_data['tool'] == 'create_record'
    assert row.ip_address == '10.0.0.7'
    assert row.user_agent == 'agent-test'


def test_create_without_resolvable_caller_is_still_audited():
    result = json.loads(create_record('company', json.dumps({'name': 'No Caller Hotel'})))
    row = AuditLog.objects.get(record_id=result['id'])
    assert row.action == 'CREATE'
    assert row.user is None


def test_failed_audit_rolls_back_the_create(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('audit store unavailable')

    monkeypatch.setattr(mcp_audit.AuditLog.objects, 'create', broken)
    with as_caller(_user('theo')), pytest.raises(RuntimeError):
        create_record('company', json.dumps({'name': 'Rolled Back Hotel'}))
    assert not Company.objects.filter(name='Rolled Back Hotel').exists()


def test_quote_create_fills_created_by_and_ignores_a_supplied_one():
    caller = _user('nikki')
    someone_else = _user('someone-else')
    company = _company()
    with as_caller(caller):
        result = json.loads(create_record('quote', json.dumps({
            'company': str(company.pk), 'quote_number': 'HK-QT269940',
            'valid_from': '2026-11-01', 'valid_until': '2026-12-01',
            'created_by': str(someone_else.pk),
        })))

    assert 'created_by' in result['warning_ignored_keys'], result
    quote = Quote.objects.get(pk=result['id'])
    assert quote.created_by == caller
    assert AuditLog.objects.get(record_id=result['id'], action='CREATE').user == caller


def test_created_by_is_not_overwritten_by_a_later_update():
    creator, editor = _user('nikki'), _user('cira')
    quote = Quote.objects.create(
        company=_company(), quote_number='HK-QT269950', valid_from=date(2026, 11, 1),
        valid_until=date(2026, 12, 1), created_by=creator,
    )
    with as_caller(editor):
        result = json.loads(update_record('quote', str(quote.pk), json.dumps({'notes': 'Edited'})))
    assert result['updated'] is True, result
    quote.refresh_from_db()
    assert quote.created_by == creator


@pytest.mark.parametrize('collection, payload, model', [
    ('task', {'title': 'Audit follow-up', 'due_date': '2026-12-01T09:00:00Z'}, Task),
    ('ticket', {'subject': 'Player offline', 'description': 'Lobby player offline.'}, Ticket),
])
def test_task_and_ticket_create_fill_created_by(collection, payload, model):
    caller = _user('riff')
    payload = {**payload, 'company': str(_company().pk)}
    with as_caller(caller):
        result = json.loads(create_record(collection, json.dumps(payload)))
    assert 'id' in result, result
    assert model.objects.get(pk=result['id']).created_by == caller
    assert AuditLog.objects.get(record_id=result['id'], action='CREATE').user == caller


def test_opportunity_owner_is_never_filled_from_the_caller():
    caller = _user('theo')
    with as_caller(caller):
        result = json.loads(create_record('opportunity', json.dumps({
            'company': str(_company().pk), 'name': 'Audit deal', 'stage': 'Contacted',
        })))
    assert Opportunity.objects.get(pk=result['id']).owner is None
    assert AuditLog.objects.get(record_id=result['id']).user == caller


# ------------------------------------------------------------------ update


def test_unguarded_update_records_real_before_and_after_of_changed_fields_only():
    caller = _user('theo')
    company = Company.objects.create(name='Before Name', city='Bangkok', billing_entity='BMAsia Limited')
    with as_caller(caller):
        result = json.loads(update_record('company', str(company.pk), json.dumps({
            'name': 'After Name', 'city': 'Bangkok',
        })))

    assert result['updated'] is True, result
    row = AuditLog.objects.get(record_id=str(company.pk))
    assert (row.action, row.user) == ('UPDATE', caller)
    assert row.changes['name'] == {'old': 'Before Name', 'new': 'After Name'}
    assert 'city' not in row.changes  # unchanged
    assert row.additional_data['kind'] == 'unguarded_update'


def test_refused_unguarded_update_writes_no_row():
    company = _company()
    with as_caller(_user('theo')):
        result = json.loads(update_record('company', str(company.pk), json.dumps({'nonexistent': 1})))
    assert result['updated'] is False
    assert not AuditLog.objects.filter(record_id=str(company.pk)).exists()


def test_generic_guarded_lane_is_logged_exactly_once():
    caller = _user('theo')
    opportunity = Opportunity.objects.create(company=_company(), name='Guarded deal', stage='Contacted')
    observed = OpportunitySerializer(opportunity).data
    with as_caller(caller):
        result = json.loads(update_record(
            'opportunity', str(opportunity.pk), json.dumps({'notes': 'Called back'}),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'notes': observed['notes']}),
        ))
    assert result['updated'] is True, result
    rows = _rows(record_id=str(opportunity.pk))
    assert len(rows) == 1
    assert rows[0].user == caller
    assert rows[0].additional_data['kind'] == 'guarded_update'


def test_contract_date_lane_is_logged_once_and_now_names_the_caller():
    caller = _user('cira')
    contract = Contract.objects.create(
        company=_company(), contract_number='HK-CT269960', status='Sent',
        start_date=date(2026, 9, 1), end_date=date(2027, 8, 31),
        value=Decimal('100.00'), total_value=Decimal('100.00'),
    )
    observed = ContractSerializer(contract).data
    context = {
        'kind': 'routine_contract_date_correction', 'requested_by': 'lyra',
        'source_reference': 'spaces/AAA/messages/BBB', 'reason': 'Correct the agreed term.',
    }
    with as_caller(caller):
        result = json.loads(update_record(
            'contract', str(contract.pk), json.dumps({'start_date': '2026-10-01'}),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'start_date': observed['start_date']}),
            authorization_context=json.dumps(context),
        ))
    assert result['updated'] is True, result
    rows = _rows(record_id=str(contract.pk))
    assert len(rows) == 1
    assert str(rows[0].pk) == result['audit_log_id']
    assert rows[0].user == caller


def test_identity_correction_lane_is_logged_exactly_once():
    caller = _user('cira')
    company = Company.objects.create(name='Old Identity', billing_entity='BMAsia Limited')
    observed = CompanySerializer(company).data
    changes = {'name': 'New Identity'}
    context = {
        'kind': 'explicit_source_company_correction', 'requested_by': 'nikki',
        'source_reference': 'spaces/test/messages/1', 'record_id': str(company.pk),
        'authorized_changes': changes,
    }
    with as_caller(caller):
        result = json.loads(update_record(
            'company', str(company.pk), json.dumps(changes),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'name': observed['name']}),
            authorization_context=json.dumps(context),
        ))
    assert result['updated'] is True, result
    rows = _rows(record_id=str(company.pk))
    assert len(rows) == 1
    assert str(rows[0].pk) == result['audit_log_id']
    assert rows[0].user == caller


# ------------------------------------------------------------------ delete


def test_delete_is_logged_with_summary_and_cascade_counts():
    caller = _user('cira')
    company = Company.objects.create(name='Delete Me Hotel', billing_entity='BMAsia Limited')
    Contact.objects.create(company=company, name='Contact A', email='a@example.test')
    Contact.objects.create(company=company, name='Contact B', email='b@example.test')
    company_id = str(company.pk)

    with as_caller(caller):
        message = delete_record('company', company_id)

    assert message.startswith('Deleted company')
    assert not Company.objects.filter(pk=company_id).exists()
    row = AuditLog.objects.get(record_id=company_id)
    assert (row.action, row.model_name, row.user) == ('DELETE', 'Company', caller)
    assert row.additional_data['deleted']['id'] == company_id
    assert row.additional_data['deleted']['name'] == 'Delete Me Hotel'
    assert row.additional_data['cascade']['crm_app.Contact'] == 2
    assert row.additional_data['cascade']['crm_app.Company'] == 1


def test_blocked_or_missing_delete_writes_no_row():
    with as_caller(_user('cira')):
        delete_record('company', '00000000-0000-0000-0000-000000000000')
        delete_record('contracttemplate', '1')
    assert not AuditLog.objects.exists()


# ------------------------------------------------------------------ convert


def test_convert_quote_logs_only_when_a_contract_is_created():
    caller = _user('cira')
    company = _company()
    quote = Quote.objects.create(
        company=company, quote_number='HK-QT269970', status='Accepted', currency='USD',
        valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1),
    )
    QuoteLineItem.objects.create(quote=quote, product_service='Soundtrack Your Brand',
                                 description='Lobby', quantity=1, unit_price=Decimal('300.00'))

    with as_caller(caller):
        first = json.loads(convert_quote_to_contract(str(quote.pk), json.dumps({'property_name': 'Main'})))
        second = json.loads(convert_quote_to_contract(str(quote.pk)))

    assert first['already_existed'] is False, first
    assert second['already_existed'] is True
    rows = _rows(model_name='Contract')
    assert len(rows) == 1
    row = rows[0]
    assert (row.action, row.record_id, row.user) == ('CREATE', first['contract_id'], caller)
    assert row.additional_data['source_quote_id'] == str(quote.pk)
    assert row.changes['quote'] == {'old': None, 'new': str(quote.pk)}
    assert row.changes['property_name'] == {'old': None, 'new': 'Main'}


def test_convert_quote_clarification_writes_nothing():
    quote = Quote.objects.create(company=_company(), quote_number='HK-QT269971',
                                 valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1))
    with as_caller(_user('cira')):
        result = json.loads(convert_quote_to_contract(str(quote.pk), json.dumps({'bogus': 1})))
    assert result['error'] == 'clarification_required'
    assert not Contract.objects.exists()
    assert not AuditLog.objects.exists()


# ------------------------------------------------------------------ privacy


def test_secret_like_fields_are_redacted():
    redacted = mcp_audit._redact({
        'smtp_password': {'old': 'a', 'new': 'b'},
        'api_key': {'old': None, 'new': 'k'},
        'name': {'old': 'x', 'new': 'y'},
    })
    assert redacted['smtp_password'] == {'old': '[redacted]', 'new': '[redacted]'}
    assert redacted['api_key'] == {'old': '[redacted]', 'new': '[redacted]'}
    assert redacted['name'] == {'old': 'x', 'new': 'y'}


# ------------------------------------------------------------------ PDF attribution


@pytest.fixture
def seen_users(monkeypatch):
    """Record which user each PDF viewset runs as, without rendering."""
    seen = []

    def get_object(self):
        seen.append(self.request.user)
        raise Http404

    monkeypatch.setattr(BaseModelViewSet, 'get_object', get_object)
    return seen


def _documents():
    company = _company()
    contract = Contract.objects.create(
        company=company, contract_number='DRAFT-9901', status='Draft',
        start_date=date(2026, 11, 1), end_date=date(2027, 10, 31),
        value=Decimal('100.00'), total_value=Decimal('100.00'),
    )
    quote = Quote.objects.create(company=company, quote_number='HK-QT269980',
                                 valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1))
    invoice = Invoice.objects.create(
        company=company, invoice_number='HK-IV-AUDIT-1', status='Draft',
        issue_date=date(2026, 11, 1), due_date=date(2026, 11, 1) + timedelta(days=30),
        amount=Decimal('100.00'), total_amount=Decimal('100.00'), currency='USD',
    )
    return contract, quote, invoice


def test_pdf_tools_run_as_the_authenticated_caller(seen_users):
    _user('first-admin', role='Admin')
    caller = _user('cira', role='Sales')
    contract, quote, invoice = _documents()
    with as_caller(caller):
        generate_contract_pdf(str(contract.pk))
        generate_proforma_pdf(str(contract.pk))
        generate_quote_pdf(str(quote.pk))
        generate_invoice_pdf(str(invoice.pk))
    assert seen_users == [caller] * 4


def test_pdf_tools_fall_back_to_the_system_user_without_a_caller(seen_users):
    admin = _user('first-admin', role='Admin')
    contract, quote, invoice = _documents()
    generate_quote_pdf(str(quote.pk))
    generate_invoice_pdf(str(invoice.pk))
    assert seen_users == [admin, admin]
    assert mcp._pdf_request_user() == admin


def test_non_admin_caller_renders_real_pdfs_without_writing_rows():
    """The viewsets need an authenticated user, not an Admin one."""
    caller = _user('cira', role='Sales')
    contract, quote, invoice = _documents()
    contract.service_locations.create(location_name='Lobby', platform='soundtrack', price=100)
    with as_caller(caller):
        results = [
            json.loads(generate_proforma_pdf(str(contract.pk))),
            json.loads(generate_quote_pdf(str(quote.pk))),
            json.loads(generate_invoice_pdf(str(invoice.pk))),
            json.loads(generate_contract_pdf(str(contract.pk))),
        ]
    for result in results:
        assert 'content_b64' in result, result
    assert not AuditLog.objects.exists()


def test_final_number_reservation_is_audited_once_as_the_caller():
    _user('first-admin', role='Admin')
    caller = _user('cira', role='Sales')
    contract = Contract.objects.create(
        company=Company.objects.create(name='Numbered Hotel', country='Cambodia',
                                       billing_entity='BMAsia Limited'),
        contract_number='DRAFT-9902', contract_type='Annual', status='Draft', is_active=False,
        start_date=date(2026, 10, 15), end_date=date(2027, 10, 14), currency='USD',
        value=Decimal('260.00'), total_value=Decimal('260.00'),
    )
    contract.service_locations.create(location_name='Lobby', platform='beatbreeze', price=260)

    with as_caller(caller):
        first = json.loads(generate_contract_pdf(
            str(contract.pk), expected_version=rfc3339(contract.updated_at), reserve_final_number=True,
        ))
        contract.refresh_from_db()
        retry = json.loads(generate_contract_pdf(
            str(contract.pk), expected_version=rfc3339(contract.updated_at), reserve_final_number=True,
        ))

    assert first['contract_number'].startswith('HK-CT'), first
    assert retry['contract_number'] == first['contract_number']
    rows = _rows(record_id=str(contract.pk), action='UPDATE')
    assert len(rows) == 1
    assert rows[0].user == caller
    assert rows[0].changes == {'contract_number': {'old': 'DRAFT-9902', 'new': first['contract_number']}}
    assert rows[0].additional_data['kind'] == 'final_number_reservation'
