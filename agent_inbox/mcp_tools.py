"""Bodies of the MCP tools ``log_activity``, ``propose_change`` and ``list_proposals``,
and their registration.

The tool functions, with the agent-facing descriptions, are defined in
``crm_app/mcp.py``, which hands them to ``configure``. A tool, its query
collection and its server-instruction lines are registered only while the
tool's switch is on; with both switches off the MCP server offers exactly what
it offered before this app existed. Registration follows the settings when
``crm_app.mcp`` is imported at start-up, so turning a switch on in the
environment and restarting is all a deploy needs. ``sync()`` repeats it at run
time (the tests use it to exercise both states).

Every reply is a JSON string; a refusal is
``{"ok": false, "status": <http status>, "code": ..., "detail": ...}``.
"""
from __future__ import annotations

import json
from datetime import timedelta

from django.utils import timezone

from agent_inbox import activities as activity_service
from agent_inbox import proposals as proposal_service
from agent_inbox.models import PROPOSAL_STATUS_CHOICES, ChangeProposal
from agent_inbox.serializers import ActivitySerializer
from agent_inbox.validation import ServiceError, aware_datetime, batch_field
from crm_app.services import agent_gate

LIST_LIMIT_MAX = 100
QUERY_TOOL = 'query_data_collections'

_REGISTRATION = {}


def configure(server, *, tools, toolsets, instructions):
    """Remember what to register (called once by crm_app.mcp) and register what is switched on.

    ``tools``: name -> (function, switch); ``toolsets``: class name -> (factory, switch),
    in publication order; ``instructions``: callable returning the section text or ''.
    """
    _REGISTRATION.update(
        server=server, tools=tools, toolsets=toolsets, instructions=instructions,
        base_instructions=server._mcp_server.instructions,
    )
    sync()


def sync():
    """Make the registered tools, collections and instructions match the switches now."""
    if not _REGISTRATION:
        return
    from mcp_server.query_tool import ModelQueryToolsetMeta

    server = _REGISTRATION['server']
    manager = server._tool_manager
    for name, (function, enabled) in _REGISTRATION['tools'].items():
        present = manager.get_tool(name) is not None
        if enabled() and not present:
            server.tool()(function)
        elif not enabled() and present:
            manager.remove_tool(name)

    registry = ModelQueryToolsetMeta.registry
    wanted = [name for name, (_factory, enabled) in _REGISTRATION['toolsets'].items() if enabled()]
    present = [name for name in _REGISTRATION['toolsets'] if name in registry]
    if wanted != present:
        for name in present:
            registry.pop(name)
        for name in wanted:
            _REGISTRATION['toolsets'][name][0]()
        if manager.get_tool(QUERY_TOOL) is not None:
            _rebuild_query_tool(server)

    base = _REGISTRATION['base_instructions']
    section = _REGISTRATION['instructions']()
    # Same joining as DjangoMCP.append_instructions; nothing is changed when off.
    server._mcp_server.instructions = (base.strip() + '\n\n' + section.strip()) if section else base


def _rebuild_query_tool(server):
    """Rebuild query_data_collections for the current collections, keeping its place in the tool list."""
    from mcp.server.fastmcp.tools.tool_manager import ToolManager
    from mcp_server.query_tool import ModelQueryToolsetMeta, QueryTool

    from crm_app import mcp_query_help

    query_tool = QueryTool()
    for cls in ModelQueryToolsetMeta.registry.values():
        for cached in ('_effective_published_models', '_effective_excluded_fields'):
            if cached in cls.__dict__:
                delattr(cls, cached)
        if (cls.mcp_server or server) is server and cls.model is not None:
            cls.mcp_server = server
            query_tool.add_query_tool_model(cls)
    scratch = ToolManager()
    rebuilt = query_tool._add_tools_to(scratch)[0]
    server._tool_manager._tools[QUERY_TOOL] = rebuilt
    mcp_query_help._BOUNDARIES.clear()

# What an agent sees about its own proposals: enough to learn from the outcome.
OWN_PROPOSAL_FIELDS = (
    'id', 'status', 'kind', 'target_collection', 'target_id', 'company_id', 'patch', 'applied_patch',
    'current_values', 'evidence_quote', 'evidence_verified', 'activity_id', 'rationale', 'confidence',
    'batch_key', 'fingerprint', 'decision_note', 'reviewed_at', 'target_changed_at', 'last_apply_error',
    'applied_record_id', 'superseded_by_id', 'evidence_occurred_at', 'history', 'expires_at', 'created_at',
)


def _reply(data):
    return json.dumps(data, default=str)


def _refusal(exc):
    return _reply({'ok': False, 'status': exc.status, **exc.body()})


def _caller():
    user = agent_gate._current_user()
    if user is None:
        raise ServiceError(401, 'not_authenticated', 'Authentication required')
    return user


def _json_arg(raw, name, default):
    if raw in (None, ''):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise ServiceError(400, 'invalid', f'{name} must be valid JSON') from None


def _without_empty(body):
    return {key: value for key, value in body.items() if value not in (None, '', [], {})}


def log_activity(**arguments):
    agent_gate.observe(tool='log_activity', verb='create', collection='activity',
                       request_key=arguments.get('idempotency_key') or '')
    try:
        user = _caller()
        body = dict(arguments)
        body['participants'] = _json_arg(arguments.get('participants_json'), 'participants_json', [])
        body.pop('participants_json', None)
        activity, replayed = activity_service.record_activity(user, _without_empty(body), via='mcp')
    except ServiceError as exc:
        return _refusal(exc)
    data = ActivitySerializer(activity).data
    return _reply({
        'ok': True, 'replayed': replayed, 'id': str(activity.pk), 'company_id': str(activity.company_id),
        'kind': activity.kind, 'occurred_at': data['occurred_at'], 'is_void': activity.is_void,
    })


def propose_change(**arguments):
    agent_gate.observe(tool='propose_change', verb='create', collection='changeproposal')
    try:
        user = _caller()
        body = dict(arguments)
        body['patch'] = _json_arg(arguments.get('patch_json'), 'patch_json', None)
        body.pop('patch_json', None)
        if body.get('confidence') is not None and body['confidence'] < 0:
            body['confidence'] = None  # the tool's "not given" value
        proposal, replayed = proposal_service.create_proposal(user, _without_empty(body), via='mcp')
    except ServiceError as exc:
        return _refusal(exc)
    return _reply({
        'ok': True, 'replayed': replayed, 'id': str(proposal.pk), 'status': proposal.status,
        'evidence_verified': proposal.evidence_verified, 'expires_at': proposal.expires_at,
        'note': 'Stored for human review. Nothing has been changed; check list_proposals for the outcome.',
    })


def list_proposals(status='', batch_key='', since='', limit=50):
    try:
        user = _caller()
        rows = ChangeProposal.objects.filter(proposer=user)
        if status:
            statuses = [value.strip() for value in status.split(',') if value.strip()]
            valid = {value for value, _ in PROPOSAL_STATUS_CHOICES}
            if not statuses or set(statuses) - valid:
                raise ServiceError(400, 'invalid', 'status must be a comma list of: ' + ', '.join(sorted(valid)))
            rows = proposal_service.with_effective_status(rows, statuses)
        if batch_key:
            rows = rows.filter(batch_key=batch_field({'batch_key': batch_key}))
        if since:
            rows = rows.filter(updated_at__gte=aware_datetime(since, 'since'))
        else:
            rows = rows.filter(updated_at__gte=timezone.now() - timedelta(days=90))
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= LIST_LIMIT_MAX:
            raise ServiceError(400, 'invalid', f'limit must be 1-{LIST_LIMIT_MAX}')
        rows = list(rows.order_by('-updated_at')[:limit])
    except ServiceError as exc:
        return _refusal(exc)
    items = []
    for row in rows:
        item = {name: getattr(row, name) for name in OWN_PROPOSAL_FIELDS}
        item['status'] = proposal_service.effective_status(row)
        # As stored by the last reviewer read or decision: an agent's read never refreshes, advances or flags.
        item['target_state'] = proposal_service.stored_state(row)
        item['target_state_reason'] = proposal_service.target_state_reason(row)
        items.append(item)
    return _reply({'ok': True, 'count': len(items), 'proposals': items})
