"""A contact created from a proposal is inactive, so no sender's default recipients include it.

The senders are the ones on main, unchanged: each picks active contacts only when
no recipients are given. With the proposal contact as the company's only contact,
each sender finds nobody and sends nothing.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.db import connection

from agent_inbox.proposals import NEW_CONTACT_INACTIVE_NOTE, create_proposal
from agent_inbox.tests.conftest import decide, session_client
from crm_app.models import Contact, Contract, Invoice, Quote
from crm_app.services.email_service import EmailService

needs_json_contains = pytest.mark.skipif(
    connection.vendor != 'postgresql', reason='this sender filters a JSON list, which needs PostgreSQL')


@pytest.fixture
def proposal_contact(agent, person, other_company):
    proposal, _ = create_proposal(agent, {
        'kind': 'new_contact', 'company_id': str(other_company.pk),
        'patch': {'name': 'Accounts Desk', 'email': 'ap@hilltop.example.com'},
        'evidence_quote': 'please add ap@hilltop.example.com',
    }, via='rest')
    response = decide(session_client(person), proposal.pk, 'accept')
    assert response.status_code == 200, response.content
    data = response.json()
    assert data['apply_note'] == NEW_CONTACT_INACTIVE_NOTE
    contact = Contact.objects.get(pk=data['created_contact_id'])
    assert contact.email == 'ap@hilltop.example.com'
    return contact


def test_the_contact_is_created_inactive_without_email_settings(proposal_contact):
    flags = {f.name: getattr(proposal_contact, f.name)
             for f in Contact._meta.concrete_fields if f.name.startswith('receives_')}
    assert proposal_contact.is_active is False and proposal_contact.is_primary is False
    assert flags and not any(flags.values())


def _invoice(company):
    return Invoice.objects.create(company=company, invoice_number='INV-PROP-1', amount=Decimal('10'),
                                  total_amount=Decimal('10'), issue_date=date(2026, 11, 1),
                                  due_date=date(2026, 12, 1), receipt_number='RC-PROP-1')


def _contract(company):
    return Contract.objects.create(company=company, contract_number='CT-PROP-1', status='Active',
                                   start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                                   value=Decimal('10'), currency='THB')


def _assert_nobody(result):
    ok, message = result
    assert ok is False and 'No recipients found' in message
    assert mail.outbox == []


@needs_json_contains
def test_invoice_default_recipients_skip_it(proposal_contact, other_company):
    _assert_nobody(EmailService().send_invoice_email(_invoice(other_company).pk))


def test_receipt_default_recipients_skip_it(proposal_contact, other_company):
    _assert_nobody(EmailService().send_receipt_email(_invoice(other_company).pk))


def test_quote_default_recipients_skip_it(proposal_contact, other_company):
    quote = Quote.objects.create(company=other_company, quote_number='QT-PROP-1', valid_from=date(2026, 11, 1),
                                 valid_until=date(2026, 12, 1))
    _assert_nobody(EmailService().send_quote_email(quote.pk))


def test_contract_default_recipients_skip_it(proposal_contact, other_company):
    _assert_nobody(EmailService().send_contract_email(_contract(other_company).pk))


@needs_json_contains
def test_manual_renewal_default_recipients_skip_it(proposal_contact, other_company):
    _assert_nobody(EmailService().send_manual_renewal_reminder(_contract(other_company).pk))


def test_activating_it_is_a_persons_step(proposal_contact):
    proposal_contact.is_active = True
    proposal_contact.save()
    proposal_contact.refresh_from_db()
    # Its email settings stay off until a person turns them on as well.
    assert not proposal_contact.receives_invoice_emails
