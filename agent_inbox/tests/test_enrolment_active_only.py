"""Prospect auto-enrolment (live when an opportunity is created or a quote is sent) picks active contacts only.

Enrolment queues the first step; it sends nothing. The sequence sender is a
separate, suspended job.
"""
from datetime import date

import pytest
from django.core import mail

from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import decide, jwt_client
from crm_app.models import Contact, Opportunity, ProspectEnrollment, ProspectSequence, ProspectSequenceStep, Quote
from crm_app.services.prospect_enrollment_service import ProspectEnrollmentService, enrolment_contact


@pytest.fixture
def sequences():
    ProspectSequence.objects.all().delete()
    made = {}
    for trigger in ('new_opportunity', 'quote_sent'):
        sequence = ProspectSequence.objects.create(name=f'Test {trigger}', trigger_type=trigger, is_active=True)
        ProspectSequenceStep.objects.create(sequence=sequence, step_number=1, delay_days=0, action_type='email',
                                            email_subject_template='Hello', email_body_template='Hello')
        made[trigger] = sequence
    return made


def _add(company, email, **fields):
    return Contact.objects.create(company=company, name=email.split('@')[0], email=email, **fields)


def _proposal_contact(agent, person, company, email='added@lookalike.example.net'):
    proposal, _ = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                          'patch': {'name': 'Added Person', 'email': email},
                                          'evidence_quote': f'please add {email}'}, via='rest')
    assert decide(jwt_client(person), proposal.pk, 'accept').status_code == 200
    return Contact.objects.get(email=email)


def _enrolled(opportunity):
    return list(ProspectEnrollment.objects.filter(opportunity=opportunity).values_list('contact__email', flat=True))


def test_the_choice_is_primary_if_active_else_the_first_active_contact(company):
    company.contacts.all().delete()
    assert enrolment_contact(company) is None
    _add(company, 'a-gone@example.test', is_active=False)
    primary_gone = _add(company, 'b-primary-gone@example.test', is_primary=True, is_active=False)
    assert enrolment_contact(company) is None
    active = _add(company, 'c-active@example.test')
    assert enrolment_contact(company) == active
    primary = _add(company, 'd-primary@example.test', is_primary=True)
    assert enrolment_contact(company) == primary
    assert enrolment_contact(company, named=primary_gone) == primary  # an inactive named contact is passed over
    assert enrolment_contact(company, named=active) == active


def test_a_contact_created_from_a_proposal_is_never_enrolled(agent, person, company, sequences):
    company.contacts.all().delete()
    added = _proposal_contact(agent, person, company)
    assert added.is_active is False
    owner = person
    opportunity = Opportunity.objects.create(company=company, name='Test deal', owner=owner)
    mail.outbox.clear()
    assert not ProspectEnrollmentService.auto_enroll_new_opportunity(opportunity)
    assert _enrolled(opportunity) == []
    quote = Quote.objects.create(company=company, quote_number='QT-ENROL-1', contact=added, opportunity=opportunity,
                                 valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1))
    assert ProspectEnrollmentService.auto_enroll_quote_sent(quote) == 0
    assert _enrolled(opportunity) == []
    assert mail.outbox == []


def test_an_active_contact_is_enrolled_and_nothing_is_sent(agent, person, company, sequences):
    company.contacts.all().delete()
    _proposal_contact(agent, person, company, email='aaa-first-by-name@lookalike.example.net')
    _add(company, 'gone@example.test', is_primary=True, is_active=False)
    active = _add(company, 'zz-active@example.test')
    opportunity = Opportunity.objects.create(company=company, name='Test deal', owner=person)
    mail.outbox.clear()
    assert ProspectEnrollmentService.auto_enroll_new_opportunity(opportunity) == 1
    assert _enrolled(opportunity) == [active.email]
    assert mail.outbox == []
