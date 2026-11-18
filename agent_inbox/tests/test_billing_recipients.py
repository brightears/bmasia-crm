"""Contacts created or re-addressed through proposals never quietly become billing recipients."""
import pytest

from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, session_client, token_client
from crm_app.models import Contact


def test_a_new_contact_receives_no_email_and_is_not_primary(agent, person, company):
    proposal, _ = create_proposal(agent, {
        'kind': 'new_contact', 'company_id': str(company.pk),
        'patch': {'name': 'Accounts Desk', 'email': 'ap@riverside.example.com'},
        'evidence_quote': 'please add ap@riverside.example.com',
    }, via='rest')
    assert decide(session_client(person), proposal.pk, 'accept').status_code == 200
    created = Contact.objects.get(email='ap@riverside.example.com')
    flags = {field.name: getattr(created, field.name)
             for field in Contact._meta.concrete_fields if field.name.startswith('receives_')}
    assert flags and not any(flags.values()), flags
    assert created.is_primary is False


def test_a_new_contact_is_not_primary_even_when_the_company_has_none(agent, person, other_company):
    proposal, _ = create_proposal(agent, {
        'kind': 'new_contact', 'company_id': str(other_company.pk),
        'patch': {'name': 'First Contact', 'email': 'first@hilltop.example.com'}, 'evidence_quote': 'q',
    }, via='rest')
    decide(session_client(person), proposal.pk, 'accept')
    assert Contact.objects.get(email='first@hilltop.example.com').is_primary is False


@pytest.mark.parametrize('flags', [
    {'receives_invoice_emails': True, 'receives_payment_emails': False},
    {'receives_invoice_emails': False, 'receives_payment_emails': True},
    {'receives_invoice_emails': False, 'receives_payment_emails': False, 'is_primary': True},
    {'receives_invoice_emails': False, 'receives_payment_emails': False, 'contact_type': 'Billing'},
])
def test_email_of_a_billing_recipient_is_changed_by_a_person_only(agent, contact, flags):
    Contact.objects.filter(pk=contact.pk).update(**flags)
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'contact', 'target_id': str(contact.pk),
        'patch': {'email': 'pat.new@riverside.example.com'}, 'evidence_quote': 'my new address',
    }, format='json')
    assert response.status_code == 422 and response.json()['code'] == 'person_only_change'
    assert 'contact page' in response.json()['detail']


def test_other_fields_of_a_billing_recipient_may_still_be_proposed(agent, person, contact):
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'contact', 'target_id': str(contact.pk),
        'patch': {'name': 'Pat Example-Lee', 'phone': '+66 81 999 9999', 'title': 'Finance Manager'},
        'evidence_quote': 'Pat Example-Lee, Finance Manager',
    }, format='json')
    assert response.status_code == 201
    assert decide(session_client(person), response.json()['id'], 'accept').status_code == 200


def test_the_rule_is_checked_again_at_accept(agent, person, contact):
    Contact.objects.filter(pk=contact.pk).update(receives_invoice_emails=False, receives_payment_emails=False)
    proposal, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'contact', 'target_id': str(contact.pk),
        'patch': {'email': 'pat.new@riverside.example.com'}, 'evidence_quote': 'q',
    }, via='rest')
    # The contact becomes an invoice recipient without the proposed field changing.
    Contact.objects.filter(pk=contact.pk).update(receives_invoice_emails=True)
    response = decide(session_client(person), proposal.pk, 'accept')
    assert response.status_code == 422 and response.json()['code'] == 'person_only_change'
    contact.refresh_from_db()
    assert contact.email == 'pat@riverside.example.com'
