"""policy.is_agent_accounts: the batch form of is_agent_account."""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token

from agent_inbox import policy
from agent_inbox.tests.conftest import make_user


def test_is_agent_accounts_gives_the_same_answers_in_one_query(settings, agent, person, company):
    settings.AGENT_INBOX_AGENT_USERNAMES = ['capture-job']
    capture = make_user('capture-job')
    token_holder = make_user('funnel-sheet')
    reviewer_with_token = person  # listed reviewer
    plain = make_user('plain-person')
    for user in (agent, token_holder, reviewer_with_token):
        Token.objects.get_or_create(user=user)

    class Anonymous:
        pk = None
        is_authenticated = False

    users = [agent, capture, token_holder, reviewer_with_token, plain, Anonymous(), None]
    expected = {user.pk: policy.is_agent_account(user) for user in users if user is not None}
    with CaptureQueriesContext(connection) as queries:
        answers = policy.is_agent_accounts(users)
    assert answers == expected
    assert answers[token_holder.pk] is True and answers[reviewer_with_token.pk] is False
    assert answers[agent.pk] is True and answers[capture.pk] is True and answers[plain.pk] is False
    assert len(queries.captured_queries) == 1
    with CaptureQueriesContext(connection) as queries:
        assert policy.is_agent_accounts([agent, capture]) == {agent.pk: True, capture.pk: True}
    assert len(queries.captured_queries) == 0
    assert policy.is_agent_accounts([]) == {}
