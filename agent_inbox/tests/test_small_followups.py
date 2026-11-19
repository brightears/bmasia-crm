"""A colliding edit leaves the reviewer's state in the reply too; Google's domains; what the server supports."""
import pytest

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client
from agent_inbox.validation import url_warnings


def test_a_colliding_edit_reports_the_state_the_reviewer_saw(agent, person, company, contact):
    """The refusal's reply and stored row both keep no_duplicate: only the edit collided."""
    proposal = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                       'patch': {'name': 'Lee Unique', 'email': 'lee@riverside.example.com'},
                                       'evidence_quote': 'please add lee@riverside.example.com'}, via='rest')[0]
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    body = decide(client, proposal.pk, 'accept-with-edits', seen_version=seen,
                  edits={'email': 'pat@riverside.example.com'}).json()
    assert body['code'] == 'not_acceptable'
    assert body['target_state'] == 'no_duplicate' and body['target_state_reason'] == ''
    assert body['proposal']['target_state'] == 'no_duplicate'
    assert body['proposal']['seen_version'] == seen
    row = ChangeProposal.objects.get(pk=proposal.pk)
    assert (row.target_state, row.target_changed_at) == ('no_duplicate', None)


@pytest.mark.parametrize('url', [
    'https://www.google.mv/x', 'https://www.google.lk/x', 'https://www.google.ae/x', 'https://www.google.com.sa/x',
    'https://www.google.com.qa/x', 'https://www.google.com.kw/x', 'https://www.google.com.bh/x',
    'https://www.google.com.om/x', 'https://www.google.com.bn/x', 'https://www.google.com.np/x',
    'https://www.google.com.bd/x',
])
def test_googles_domains_for_the_maldives_sri_lanka_the_gulf_and_south_asia(url):
    assert url_warnings('source_url', url, 'other') == []


@pytest.mark.parametrize('url', ['https://google.evil.ae/x', 'https://google.com.de/x', 'https://google.mv.example/x'])
def test_unrelated_google_named_hosts_still_warn(url):
    assert [w['code'] for w in url_warnings('source_url', url, 'other')] == ['url_lookalike_host']


def test_the_allowlist_says_what_the_server_supports(person):
    data = jwt_client(person).get(f'{PROPOSALS}allowlist/').json()
    assert data['supports'] == ['acknowledge_inactive', 'target_states']
    assert data['target_states'] == {
        'acceptable': ['no_duplicate', 'present'],
        'needs_acknowledgement': {'inactive': 'acknowledge_inactive'},
        'never_acceptable': ['duplicate', 'missing', 'moved'],
    }
