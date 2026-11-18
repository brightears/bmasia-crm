"""The MCP server offers the inbox tools, collections and instructions only while switched on."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings

import crm_app.mcp  # noqa: F401 - registers the tool definitions
from agent_inbox import mcp_tools
from mcp_server.djangomcp import global_mcp_server as server

INBOX_TOOLS = {'log_activity', 'propose_change', 'list_proposals'}
REPO = Path(__file__).resolve().parents[2]


def surface():
    """Everything an MCP client is shown: tools in order with their texts, and the instructions."""
    tools = [(tool.name, tool.description, json.dumps(tool.parameters, sort_keys=True))
             for tool in server._tool_manager.list_tools()]
    return tools, server._mcp_server.instructions


def query_description():
    return server._tool_manager.get_tool('query_data_collections').description


@pytest.fixture
def switches():
    def apply(activity, proposals):
        overrides = override_settings(AGENT_ACTIVITY_WRITES_ENABLED=activity, CHANGE_PROPOSALS_ENABLED=proposals)
        overrides.enable()
        applied.append(overrides)
        mcp_tools.sync()
    applied = []
    yield apply
    for overrides in reversed(applied):
        overrides.disable()
    mcp_tools.sync()


def test_off_means_nothing_is_offered(switches):
    switches(False, False)
    tools, instructions = surface()
    assert not INBOX_TOOLS & {name for name, _, _ in tools}
    assert 'Activity log and change proposals' not in instructions
    assert "'activity' collection" not in query_description()
    assert "'changeproposal' collection" not in query_description()


def test_on_then_off_restores_exactly_the_same_surface(switches):
    switches(False, False)
    before = surface()
    switches(True, True)
    tools, instructions = surface()
    assert INBOX_TOOLS <= {name for name, _, _ in tools}
    assert instructions.startswith(before[1].strip())
    assert 'Activity log and change proposals' in instructions
    assert "'activity' collection" in query_description()
    assert "'changeproposal' collection" in query_description()
    switches(False, False)
    assert surface() == before


def test_each_switch_controls_its_own_part(switches):
    switches(True, False)
    names = {name for name, _, _ in surface()[0]}
    assert 'log_activity' in names and not {'propose_change', 'list_proposals'} & names
    assert "'activity' collection" in query_description()
    assert "'changeproposal' collection" not in query_description()
    switches(False, True)
    names = {name for name, _, _ in surface()[0]}
    assert {'propose_change', 'list_proposals'} <= names and 'log_activity' not in names
    assert "'changeproposal' collection" in query_description()
    assert "'activity' collection" not in query_description()


def test_the_proposal_tool_keeps_direct_corrections_with_update_record(switches):
    switches(True, True)
    description = server._tool_manager.get_tool('propose_change').description
    assert 'Never applied automatically' in description
    assert 'Keep using update_record for changes you are already allowed to make' in description
    assert 'Do not call update_record' not in description


def _tool_names_in_a_fresh_process(env_overrides):
    env = {**os.environ, 'SECRET_KEY': os.environ.get('SECRET_KEY', 'test-only'), **env_overrides}
    for name in ('AGENT_ACTIVITY_WRITES_ENABLED', 'CHANGE_PROPOSALS_ENABLED'):
        if name not in env_overrides:
            env.pop(name, None)
    code = (
        'import django, json; django.setup(); '
        'from mcp_server.djangomcp import global_mcp_server as s; '
        'print(json.dumps(sorted(t.name for t in s._tool_manager.list_tools())))'
    )
    result = subprocess.run([sys.executable, '-c', code], cwd=REPO, env={**env, 'DJANGO_SETTINGS_MODULE':
                            'bmasia_crm.settings'}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    return set(json.loads(result.stdout.strip().splitlines()[-1]))


@pytest.mark.slow
def test_the_environment_switches_are_all_a_deploy_needs():
    off = _tool_names_in_a_fresh_process({})
    on = _tool_names_in_a_fresh_process({'AGENT_ACTIVITY_WRITES_ENABLED': 'True', 'CHANGE_PROPOSALS_ENABLED': 'True'})
    assert not INBOX_TOOLS & off
    assert on - off == INBOX_TOOLS
