"""The review page's small helpers: refusal wording without setting names, and the expiry warning count."""
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client, make_user, token_client


def _field(company, field, value):
    return {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {field: value}, 'evidence_quote': 'as written in the message'}


def test_review_not_configured_names_no_setting_to_non_staff(agent, company):
    proposal = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    person = make_user('plain-person', role='Sales')
    staff = make_user('staff-person', role='Admin')
    type(staff).objects.filter(pk=staff.pk).update(is_staff=True)
    staff.refresh_from_db()
    with override_settings(CHANGE_PROPOSAL_REVIEWER_USERNAMES=[]):
        refused = decide(jwt_client(person), proposal.pk, 'reject', reason='no')
        assert refused.status_code == 403
        assert refused.json()['code'] == 'review_not_configured'
        assert refused.json()['detail'] == 'Reviewing is not set up yet.'
        status = jwt_client(person).get(f'{PROPOSALS}allowlist/').json()
        assert status['review_refusal'] == 'Reviewing is not set up yet.'
        staff_view = decide(jwt_client(staff), proposal.pk, 'reject', reason='no').json()
        assert staff_view['code'] == 'review_not_configured'
        assert 'CHANGE_PROPOSAL_REVIEWER_USERNAMES' in staff_view['detail']


def test_the_list_says_how_many_open_proposals_expire_within_a_week(agent, other_agent, person, company):
    soon, _ = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')
    later, _ = create_proposal(agent, _field(company, 'city', 'Chiang Mai'), via='rest')
    past, _ = create_proposal(agent, _field(company, 'email', 'desk@riverside.example.com'), via='rest')
    done, _ = create_proposal(other_agent, _field(company, 'website', 'https://riverside.example.org'), via='rest')
    now = timezone.now()
    ChangeProposal.objects.filter(pk=soon.pk).update(expires_at=now + timedelta(days=3))
    ChangeProposal.objects.filter(pk=later.pk).update(expires_at=now + timedelta(days=10))
    ChangeProposal.objects.filter(pk=past.pk).update(expires_at=now - timedelta(minutes=1))
    ChangeProposal.objects.filter(pk=done.pk).update(expires_at=now + timedelta(days=2), status='rejected')
    body = jwt_client(person).get(PROPOSALS, {'status': 'rejected'}).json()
    assert body['summary'] == {'open_expiring_within_days': 7, 'open_expiring_count': 1}
    # An agent counts only its own proposals.
    assert token_client(other_agent).get(PROPOSALS).json()['summary']['open_expiring_count'] == 0
