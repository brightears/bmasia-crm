"""Source and evidence links are checked before they are stored, and old links are read with a warning."""

import pytest

from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.tests.conftest import (
    ACTIVITIES, PROPOSALS, activity_body, jwt_client, token_client,
)
from agent_inbox.validation import checked_url

REFUSED_ANYWHERE = [
    'https://mail.google.com@other.example/mail/u/0/#inbox/abc',
    'https://user:pass@mail.example.com/x',
    'https://user@mail.example.com/x',
    'https://mail.google.com:443@evil.example/x',
    'https://127.0.0.1/x',
    'https://[::1]/x',
    'https://2130706433/x',
    'https://127.1/x',
    'https://localhost/x',
    'https://app.localhost/x',
    'https://intranet/x',
    'https://mail.example.com:8443/x',
    'https://mail.example.com:/x',
    'HTTPS://mail.example.com/x',
    'ftp://mail.example.com/x',
    'https:mail.example.com/x',
    'https://mail_box.example.com/x',
    'https://mail.example.com./x',
    'javascript:alert(1)',
]


def _phone(company, value='+66 2 111 2222', **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'new number'}
    body.update(extra)
    return body


def _post_evidence(agent, company, url, system='other'):
    return token_client(agent).post(PROPOSALS, _phone(
        company, evidence_source_system=system, evidence_source_ref='ref-1', evidence_source_url=url), format='json')


def _post_activity(agent, company, url, system='other', key='link-0001'):
    return token_client(agent).post(ACTIVITIES, activity_body(
        company, source_system=system, source_ref='', idempotency_key=key, source_url=url), format='json')


# ------------------------------------------------------------------ links


@pytest.mark.parametrize('url', REFUSED_ANYWHERE)
def test_unsafe_links_are_refused_for_evidence_and_activities(agent, company, url):
    evidence = _post_evidence(agent, company, url)
    assert evidence.status_code == 400, (url, evidence.content)
    assert 'evidence_source_url' in evidence.json()['detail']
    activity = _post_activity(agent, company, url)
    assert activity.status_code == 400, (url, activity.content)
    assert 'source_url' in activity.json()['detail']
    assert not ChangeProposal.objects.exists() and not Activity.objects.exists()


def test_a_gmail_source_needs_the_gmail_host(agent, company):
    lookalike = 'https://mail.google.com.other.example/mail/u/0/#inbox/abc'
    assert _post_evidence(agent, company, lookalike, system='gmail').status_code == 400
    assert _post_activity(agent, company, lookalike, system='gmail').status_code == 400
    # The same host is an ordinary domain for a source that is not gmail.
    assert _post_activity(agent, company, lookalike, system='other').status_code == 201
    good = 'https://mail.google.com/mail/u/0/#inbox/abc'
    assert _post_evidence(agent, company, good, system='gmail').status_code == 201


def test_the_stored_link_is_rebuilt_from_its_checked_parts(agent, company):
    response = _post_evidence(agent, company, 'https://Mail.Google.COM:443/mail/u/0/?q=1#inbox/abc', system='gmail')
    assert response.status_code == 201, response.content
    stored = ChangeProposal.objects.get().evidence_source_url
    assert stored == 'https://mail.google.com/mail/u/0/?q=1#inbox/abc'
    assert checked_url('http://Example.com:80/a', '') == ('http://example.com/a', None)


def test_a_punycode_host_is_accepted_with_a_warning(agent, person, company):
    response = _post_evidence(agent, company, 'https://xn--mil-goole-6za.example/x')
    assert response.status_code == 201, response.content
    proposal = ChangeProposal.objects.get()
    shown = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert [w['code'] for w in shown['warnings']] == ['url_punycode_host']
    assert shown['warnings'][0]['field'] == 'evidence_source_url'


def test_a_non_ascii_host_is_stored_in_punycode_with_a_warning(agent, person, company):
    response = _post_activity(agent, company, 'https://mаil.example.com/x')  # Cyrillic a
    assert response.status_code == 201, response.content
    activity = Activity.objects.get()
    assert activity.source_url.startswith('https://xn--') and activity.source_url.isascii()
    shown = jwt_client(person).get(f'{ACTIVITIES}{activity.pk}/').json()
    assert [w['code'] for w in shown['warnings']] == ['url_punycode_host']


def test_an_ordinary_link_carries_no_warning(agent, person, company):
    _post_activity(agent, company, 'https://drive.example.com/file/1')
    activity = Activity.objects.get()
    assert jwt_client(person).get(f'{ACTIVITIES}{activity.pk}/').json()['warnings'] == []


def test_old_rows_are_kept_and_read_with_a_warning(agent, person, company):
    _post_activity(agent, company, 'https://drive.example.com/file/1')
    _post_evidence(agent, company, 'https://drive.example.com/file/1')
    old = 'https://mail.google.com@other.example/x'
    Activity.objects.update(source_url=old)
    ChangeProposal.objects.update(evidence_source_url=old)
    activity, proposal = Activity.objects.get(), ChangeProposal.objects.get()
    shown_activity = jwt_client(person).get(f'{ACTIVITIES}{activity.pk}/').json()
    shown_proposal = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert shown_activity['source_url'] == old and shown_proposal['evidence_source_url'] == old
    assert [w['code'] for w in shown_activity['warnings']] == ['url_not_accepted']
    assert [w['code'] for w in shown_proposal['warnings']] == ['url_not_accepted']
    activity.refresh_from_db()
    assert activity.source_url == old  # reading never rewrites the row


def test_the_link_warning_is_hidden_with_the_link(agent, other_agent, company):
    """An agent that may not see another recorder's link does not see its warning either."""
    record = _post_activity(agent, company, 'https://xn--mil-goole-6za.example/x')
    assert record.status_code == 201
    Activity.objects.update(restricted=True)
    shown = token_client(other_agent).get(f'{ACTIVITIES}{record.json()["id"]}/').json()
    assert 'source_url' not in shown and shown['warnings'] == []
