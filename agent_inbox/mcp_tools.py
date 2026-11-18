"""Bodies of the MCP tools ``log_activity``, ``propose_change`` and ``list_proposals``.

The tools themselves are registered in ``crm_app/mcp.py`` (thin wrappers with
the agent-facing descriptions). Every reply is a JSON string; a refusal is
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

# What an agent sees about its own proposals: enough to learn from the outcome.
OWN_PROPOSAL_FIELDS = (
    'id', 'status', 'kind', 'target_collection', 'target_id', 'company_id', 'patch', 'applied_patch',
    'current_values', 'evidence_quote', 'evidence_verified', 'activity_id', 'rationale', 'confidence',
    'batch_key', 'fingerprint', 'decision_note', 'reviewed_at', 'target_changed_at', 'last_apply_error',
    'applied_record_id', 'superseded_by_id', 'expires_at', 'created_at',
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
        proposal_service.expire_due()
        rows = ChangeProposal.objects.filter(proposer=user)
        if status:
            statuses = [value.strip() for value in status.split(',') if value.strip()]
            valid = {value for value, _ in PROPOSAL_STATUS_CHOICES}
            if not statuses or set(statuses) - valid:
                raise ServiceError(400, 'invalid', 'status must be a comma list of: ' + ', '.join(sorted(valid)))
            rows = rows.filter(status__in=statuses)
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
        items.append({name: getattr(row, name) for name in OWN_PROPOSAL_FIELDS})
    return _reply({'ok': True, 'count': len(items), 'proposals': items})
