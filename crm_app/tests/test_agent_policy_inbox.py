"""The agent gate's entries for the activity log and the review queue."""
import pytest


@pytest.mark.parametrize('name', ['cira', 'vera', 'theo', 'lyra', 'riff', 'nina', 'cara', 'sales'])
def test_every_active_agent_may_log_and_propose(name):
    from crm_app import agent_policy
    principal = agent_policy.PRINCIPALS[name]
    for collection in ('activity', 'changeproposal'):
        assert agent_policy.evaluate(principal, agent_policy.CREATE, collection, []) == ([], '')
    assert agent_policy.evaluate(principal, agent_policy.UPDATE, 'changeproposal', [])[0]


def test_the_retired_agent_may_not():
    from crm_app import agent_policy
    assert agent_policy.evaluate(agent_policy.PRINCIPALS['ruby'], agent_policy.CREATE, 'activity', [])[0] == [
        'principal ruby is retired']


def test_existing_policy_is_unchanged():
    from crm_app import agent_policy
    theo, vera = agent_policy.PRINCIPALS['theo'], agent_policy.PRINCIPALS['vera']
    assert agent_policy.evaluate(theo, agent_policy.CREATE, 'company', [])[0] == ['theo may not create company']
    assert agent_policy.evaluate(vera, agent_policy.UPDATE, 'contact', ['title'])[0] == [
        'vera may not update contact']

