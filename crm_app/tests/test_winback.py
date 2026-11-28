"""Win-back agent: churn detection, human-only sending, feedback and insights.

Claude is never called: ``winback_service._ask_claude`` is patched in every test that drafts.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from crm_app.models import (
    ChurnInsightReport, Contact, Contract, ContractServiceLocation, EmailLog, WinBackCandidate,
)
from crm_app.services import winback_service
from crm_app.services.winback_service import WinBackError
from crm_app.tests.factories import CompanyFactory, ContactFactory, UserFactory

TODAY = date(2026, 11, 28)
_seq = iter(range(1, 10_000))


def make_contract(company, status='Expired', end=TODAY - timedelta(days=30), service_type='beat_breeze_yearly',
                  start=None, **extra):
    return Contract.objects.create(
        company=company,
        contract_number=f'WB-{next(_seq):05d}',
        contract_type='Annual',
        service_type=service_type,
        status=status,
        start_date=start or (end - timedelta(days=365) if end else TODAY - timedelta(days=365)),
        end_date=end,
        value=Decimal('870.00'),
        currency='USD',
        **extra,
    )


def make_churned(name='Sunset Spa', **kw):
    company = CompanyFactory(name=name)
    contact = ContactFactory(company=company, email=f'gm@{name.lower().replace(" ", "")}.example',
                             is_primary=True)
    contract = make_contract(company, **kw)
    ContractServiceLocation.objects.create(contract=contract, location_name='Lobby', platform='beatbreeze')
    ContractServiceLocation.objects.create(contract=contract, location_name='Spa', platform='beatbreeze')
    return company, contact, contract


DRAFT = {'subject': 'We miss you at Sunset Spa',
         'body_html': '<p>Dear Ann,</p><script>alert(1)</script><p onclick="x()">Hello</p><a href="x">link</a>',
         'personalisation_notes': 'Used 2 zones and spa industry.'}


# ------------------------------------------------------------------ detection

def test_expired_contract_without_successor_is_churn():
    company, contact, contract = make_churned()
    rows = winback_service.find_churned(today=TODAY)
    assert [r['company'] for r in rows] == [company]
    assert rows[0]['product'] == 'beatbreeze'
    assert rows[0]['signal'] == 'expired'


def test_renewed_or_live_customer_is_not_churn():
    company, _, _ = make_churned('Renewed Hotel')
    make_contract(company, status='Active', start=TODAY - timedelta(days=29), end=TODAY + timedelta(days=330))
    company2, _, _ = make_churned('Draft Cafe')
    make_contract(company2, status='Draft', start=TODAY + timedelta(days=5), end=TODAY + timedelta(days=370))
    assert winback_service.find_churned(today=TODAY) == []


def test_window_and_product_filters():
    make_churned('Old Bar', end=TODAY - timedelta(days=400))
    company, _, _ = make_churned('Soundtrack Mall', service_type='soundtrack_essential_yearly')
    assert winback_service.find_churned(today=TODAY, product='beatbreeze') == []
    assert [r['company'] for r in winback_service.find_churned(today=TODAY, product='soundtrack')] == [company]


def test_cancelled_and_lifecycle_churn_count_one_offs_do_not():
    a = CompanyFactory(name='Cancelled Co')
    make_contract(a, status='Cancelled', end=TODAY - timedelta(days=10))
    b = CompanyFactory(name='Churn Record Co')
    make_contract(b, status='Active', end=TODAY - timedelta(days=5), lifecycle_type='churn',
                  lifecycle_effective_date=TODAY - timedelta(days=5))
    c = CompanyFactory(name='Setup Only Co')
    make_contract(c, service_type='one_time_setup')
    names = {r['company'].name: r['signal'] for r in winback_service.find_churned(today=TODAY)}
    assert names == {'Cancelled Co': 'cancelled', 'Churn Record Co': 'lifecycle_churn'}


def test_scan_is_idempotent_and_flags_missing_contact():
    make_churned()
    lonely = CompanyFactory(name='No Contact Ltd')
    make_contract(lonely)
    first = winback_service.scan(today=TODAY)
    assert len(first['created']) == 2
    statuses = {c.company.name: c.status for c in first['created']}
    assert statuses == {'Sunset Spa': 'identified', 'No Contact Ltd': 'needs_contact'}
    spa = WinBackCandidate.objects.get(company__name='Sunset Spa')
    assert spa.zones == 2 and spa.annual_value == Decimal('870.00')
    second = winback_service.scan(today=TODAY)
    assert second['created'] == [] and second['already_listed'] == 2


def test_unsubscribed_contact_is_not_picked():
    company, contact, contract = make_churned()
    contact.unsubscribed = True
    contact.save()
    assert winback_service.pick_contact(company, contract) is None


# --------------------------------------------------------------------- drafting

@mock.patch.object(winback_service, '_ask_claude', return_value=(DRAFT, 'claude-opus-5-5'))
def test_draft_waits_for_review_and_sends_nothing(ask):
    make_churned()
    candidate = winback_service.scan(today=TODAY)['created'][0]
    winback_service.draft_email(candidate)
    candidate.refresh_from_db()
    assert candidate.status == 'pending_review'
    assert candidate.offer == winback_service.default_offer()
    assert '<script' not in candidate.draft_body_html and 'onclick' not in candidate.draft_body_html
    assert '<a' not in candidate.draft_body_html
    assert EmailLog.objects.count() == 0
    prompt = ask.call_args.args[1]
    assert 'Sunset Spa' in prompt and '2 months free' in prompt


def test_context_leaves_out_notes():
    company, _, _ = make_churned()
    company.notes = 'PRIVATE internal note'
    company.save()
    candidate = winback_service.scan(today=TODAY)['created'][0]
    assert 'PRIVATE' not in str(winback_service.build_context(candidate))


# ---------------------------------------------------------------------- the API

def api_for(user, token=False):
    client = APIClient()
    if token:
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=user).key}')
    else:
        client.force_authenticate(user)
    return client


@pytest.fixture
def pending():
    make_churned()
    candidate = winback_service.scan(today=TODAY)['created'][0]
    with mock.patch.object(winback_service, '_ask_claude', return_value=(DRAFT, 'claude-opus-5-5')):
        winback_service.draft_email(candidate)
    return candidate


@mock.patch('crm_app.services.email_service.EmailService.send_email', return_value=(True, 'ok'))
def test_person_approves_and_email_sends_once(send, pending):
    user = UserFactory(role='Sales')
    client = api_for(user)
    url = f'/api/v1/winback-candidates/{pending.id}/approve/'
    resp = client.post(url, {'subject': 'Edited subject', 'body_html': '<p>Edited</p>'}, format='json')
    assert resp.status_code == 200, resp.content
    pending.refresh_from_db()
    assert pending.status == 'sent' and pending.final_subject == 'Edited subject'
    assert pending.reviewer == user
    assert send.call_count == 1
    assert send.call_args.kwargs['email_type'] == 'winback'
    # A second click cannot send again.
    assert client.post(url, {}, format='json').status_code == 400
    assert send.call_count == 1


@mock.patch('crm_app.services.email_service.EmailService.send_email', return_value=(True, 'ok'))
def test_api_token_cannot_send(send, pending):
    resp = api_for(UserFactory(role='Sales'), token=True).post(
        f'/api/v1/winback-candidates/{pending.id}/approve/', {}, format='json')
    assert resp.status_code == 403
    assert send.call_count == 0
    pending.refresh_from_db()
    assert pending.status == 'pending_review'


def test_other_roles_cannot_see_candidates(pending):
    resp = api_for(UserFactory(role='Finance')).get('/api/v1/winback-candidates/')
    assert resp.status_code == 403


@mock.patch('crm_app.services.email_service.EmailService.send_email', return_value=(False, 'SMTP down'))
def test_failed_send_returns_draft_to_review(send, pending):
    resp = api_for(UserFactory(role='Admin')).post(
        f'/api/v1/winback-candidates/{pending.id}/approve/', {}, format='json')
    assert resp.status_code == 400
    pending.refresh_from_db()
    assert pending.status == 'pending_review' and 'SMTP down' in pending.send_error


def test_scan_endpoint_and_skip():
    make_churned()
    client = api_for(UserFactory(role='Sales'))
    with mock.patch.object(winback_service, 'business_today', return_value=TODAY):
        resp = client.post('/api/v1/winback-candidates/scan/', {'product': 'beatbreeze'}, format='json')
    assert resp.status_code == 200 and resp.json()['created'] == 1
    cid = resp.json()['candidates'][0]['id']
    assert client.post(f'/api/v1/winback-candidates/{cid}/skip/', {}, format='json').status_code == 200
    assert WinBackCandidate.objects.get(id=cid).status == 'skipped'


# --------------------------------------------------------------- feedback/insights

FEEDBACK = {'churn_reason': 'price', 'churn_reason_detail': 'Budget cut after renovation.',
            'sentiment': 'neutral', 'win_back_likelihood': 'medium',
            'suggested_next_step': 'Offer a 6-month plan.'}


def test_feedback_is_classified(pending):
    with mock.patch.object(winback_service, '_ask_claude', return_value=(FEEDBACK, 'm')):
        resp = api_for(UserFactory(role='Sales')).post(
            f'/api/v1/winback-candidates/{pending.id}/feedback/',
            {'text': 'Too expensive this year', 'source': 'call'}, format='json')
    assert resp.status_code == 200
    pending.refresh_from_db()
    assert pending.status == 'replied' and pending.churn_reason == 'price'


def test_reply_matches_sent_candidate_by_message_id(pending):
    log = EmailLog.objects.create(company=pending.company, contact=pending.contact, email_type='winback',
                                  from_email='a@b.c', to_email=pending.contact.email, subject='s',
                                  body_html='b', status='sent', message_id='<abc@bmasia>')
    pending.status = 'sent'
    pending.email_log = log
    pending.save()
    assert winback_service.match_reply('<abc@bmasia>', '', 'someone@else.example') == pending
    with mock.patch.object(winback_service, '_ask_claude', return_value=(FEEDBACK, 'm')):
        winback_service.record_feedback(pending, 'We closed the spa', source='email_reply',
                                        message_id='<r1@x>')
    assert '<r1@x>' in pending.reply_message_id


def test_insights_report_saved(pending):
    plan = {'summary': 'One customer left over price.', 'plan_markdown': '## 5-step improvement plan\n1. ...'}
    with mock.patch.object(winback_service, '_ask_claude', return_value=(plan, 'claude-opus-5-5')) as ask:
        report = winback_service.generate_insights(today=TODAY)
    assert report.candidate_count == 1 and ChurnInsightReport.objects.count() == 1
    assert 'churned_customers' in ask.call_args.args[1]


def test_insights_need_candidates():
    with pytest.raises(WinBackError):
        winback_service.generate_insights(today=TODAY)
