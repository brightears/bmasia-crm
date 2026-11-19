"""Links: numeric hosts in any base, look-alike hosts, citing an activity's link; reviewer refusal wording."""
import pytest
from django.contrib.auth import get_user_model

from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import ACTIVITIES, PROPOSALS, activity_body, decide, jwt_client, make_user, \
    token_client
from agent_inbox.validation import checked_url, registrable_domain, url_warnings


def _phone(company, **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'new number'}
    body.update(extra)
    return body


@pytest.mark.parametrize('url', [
    'https://0x7f.0x0.0x0.0x1/x', 'https://1.2.3.0x4/x', 'https://0x7f000001/x', 'https://10.0.0.0X1/x',
    'https://intranet.0x/x', 'https://a.b.017/x',
])
def test_a_host_ending_in_a_number_in_any_base_is_refused(agent, company, url):
    assert checked_url(url)[1] in ('must name a host, not an IP address', 'has a host name that is not a valid domain')
    response = token_client(agent).post(PROPOSALS, _phone(company, evidence_source_system='other',
                                                          evidence_source_ref='ref-1', evidence_source_url=url),
                                        format='json')
    assert response.status_code == 400 and 'evidence_source_url' in response.json()['detail']


@pytest.mark.parametrize('url', ['https://example.com0x1/x', 'https://0xcafe.example/x', 'https://abc.0xg/x'])
def test_hex_looking_labels_elsewhere_are_ordinary_names(url):
    assert checked_url(url)[1] is None


@pytest.mark.parametrize('url, name', [
    ('https://mail.google.com.other.example/mail/u/0/', 'google'),
    ('https://google.com-login.example/x', 'google'),
    ('https://gmail-support.example/x', 'gmail'),
    ('https://outlook-office.example.net/x', 'outlook'),
    ('https://microsoft.account-check.example/x', 'microsoft'),
    ('https://bmasia-crm.other.onrender.com/x', 'bmasia'),
    ('https://bmasia-invoices.example/x', 'bmasia'),
])
def test_a_well_known_name_outside_its_own_domain_is_flagged(url, name):
    warnings = url_warnings('source_url', url, 'other')
    assert [w['code'] for w in warnings] == ['url_lookalike_host']
    assert f'"{name}"' in warnings[0]['detail']


@pytest.mark.parametrize('url', [
    'https://mail.google.com/mail/u/0/#inbox/abc', 'https://chat.google.com/room/1', 'https://drive.google.com/x',
    'https://docs.google.com/spreadsheets/d/1', 'https://calendar.google.com/x', 'https://outlook.office.com/x',
    'https://www.microsoft.com/x', 'https://bmasia-crm.onrender.com/api', 'https://bmasia-crm-frontend.onrender.com/',
    'https://bmasiamusic.com/presentations/x', 'https://officedepot.example/x', 'https://riverside.example.com/x',
])
def test_real_hosts_and_unrelated_names_carry_no_warning(url):
    assert url_warnings('source_url', url, 'other') == []


def test_registrable_domain():
    assert registrable_domain('mail.google.com.other.example') == 'other.example'
    assert registrable_domain('bmasia-crm.onrender.com') == 'bmasia-crm.onrender.com'
    assert registrable_domain('www.hotel.co.th') == 'hotel.co.th'


def test_the_reviewer_sees_the_lookalike_warning(agent, person, company):
    response = token_client(agent).post(ACTIVITIES, activity_body(
        company, source_system='drive', source_ref='', idempotency_key='lookalike-0001',
        source_url='https://mail.google.com.other.example/mail/u/0/#inbox/abc'), format='json')
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    shown = jwt_client(person).get(f'{ACTIVITIES}{activity.pk}/').json()
    assert [w['code'] for w in shown['warnings']] == ['url_lookalike_host']


# ------------------------------------------------------------------ citing an activity


@pytest.mark.parametrize('given', [
    'https://Mail.Google.com:443/mail/u/0/#inbox/abc', 'https://mail.google.com/mail/u/0/#inbox/abc',
])
def test_citing_an_activity_compares_the_checked_links(agent, company, given):
    activity = token_client(agent).post(ACTIVITIES, activity_body(
        company, source_url='https://mail.google.com/mail/u/0/#inbox/abc',
        body='Hello, our new reception number is +66 2 111 2222.'), format='json')
    assert activity.status_code == 201, activity.content
    response = token_client(agent).post(PROPOSALS, _phone(
        company, activity_id=activity.json()['id'], evidence_quote='our new reception number is +66 2 111 2222',
        evidence_source_url=given), format='json')
    assert response.status_code == 201, response.content
    assert ChangeProposal.objects.get().evidence_source_url == 'https://mail.google.com/mail/u/0/#inbox/abc'


def test_citing_an_activity_with_another_link_is_still_a_mismatch(agent, company):
    activity = token_client(agent).post(ACTIVITIES, activity_body(
        company, source_url='https://mail.google.com/mail/u/0/#inbox/abc',
        body='Hello, our new reception number is +66 2 111 2222.'), format='json')
    response = token_client(agent).post(PROPOSALS, _phone(
        company, activity_id=activity.json()['id'], evidence_quote='our new reception number is +66 2 111 2222',
        evidence_source_url='https://mail.google.com/mail/u/0/#inbox/other'), format='json')
    assert (response.status_code, response.json()['code']) == (422, 'evidence_source_mismatch')


# ------------------------------------------------------------------ refusal wording


def test_not_a_reviewer_names_no_setting_to_non_staff(agent, company):
    proposal = create_proposal(agent, _phone(company), via='rest')[0]
    outsider = make_user('not-listed-person')
    refused = decide(jwt_client(outsider), proposal.pk, 'reject', reason='no')
    assert refused.status_code == 403
    assert refused.json() == {'detail': 'Your account is not on the list of reviewers.', 'code': 'not_a_reviewer'}
    assert jwt_client(outsider).get(f'{PROPOSALS}allowlist/').json()['review_refusal'] == \
        'Your account is not on the list of reviewers.'
    staff = make_user('not-listed-staff', role='Admin')
    get_user_model().objects.filter(pk=staff.pk).update(is_staff=True)
    staff.refresh_from_db()
    detail = decide(jwt_client(staff), proposal.pk, 'reject', reason='no').json()
    assert detail['code'] == 'not_a_reviewer' and 'CHANGE_PROPOSAL_REVIEWER_USERNAMES' in detail['detail']
