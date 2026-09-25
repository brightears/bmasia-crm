"""Phase 1 agent gate — Stage A (observe only).

Every MCP write tool calls ``observe(...)`` once, before doing its work. The gate
identifies the caller from the request the MCP transport stores in
``django_request_ctx``, evaluates ``crm_app.agent_policy`` and appends one
``AgentRequest`` row describing what the policy *would* decide.

Stage A never blocks, alters or delays a write beyond one insert (plus at most one
lookup for conditional rules), and never raises: any failure is logged and
swallowed. ``settings.AGENT_GATE_MODE = 'off'`` disables it entirely.
Design: docs/agent-gate-phase1-design.md.
"""
from __future__ import annotations

import hashlib
import json
import logging

from django.conf import settings
from django.db import transaction

from crm_app import agent_policy as policy

logger = logging.getLogger(__name__)

OBSERVE = 'observe'


def _current_user():
    try:
        from mcp_server.djangomcp import django_request_ctx
    except Exception:  # pragma: no cover - library layout changed
        return None
    request = django_request_ctx.get(None)
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


def _as_dict(data):
    if isinstance(data, dict):
        return data
    if isinstance(data, str) and data.strip():
        try:
            parsed = json.loads(data)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _digest(data) -> str:
    try:
        raw = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
    except (TypeError, ValueError):
        return ''
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _company_id_for(collection, record_id, values):
    from crm_app.models import Contact
    if collection == 'company':
        return record_id or None
    if values.get('company'):
        return values.get('company')
    if collection == 'contact' and record_id:
        return Contact.objects.filter(pk=record_id).values_list('company_id', flat=True).first()
    return None


def _condition_reasons(condition, collection, record_id, values, authorized=False):
    if condition == 'opportunity_non_terminal':
        if values.get('stage') in policy.OPPORTUNITY_TERMINAL:
            return [f"opportunity stage {values['stage']} is terminal (Cira-only for this agent)"]
        return []
    if condition == 'terminal_needs_explicit_authorization':
        if values.get('stage') in policy.OPPORTUNITY_TERMINAL and not authorized:
            return [f"opportunity stage {values['stage']} needs the explicit-user authorization context"]
        return []
    if condition == 'ticket_non_terminal':
        status = str(values.get('status') or '').lower()
        if status in policy.TICKET_TERMINAL:
            return [f'ticket status {status} is terminal (Cira-only)']
        return []
    if condition == 'lead_company_only':
        from crm_app.models import Contract
        company_id = _company_id_for(collection, record_id, values)
        if company_id and Contract.objects.filter(
            company_id=company_id, status__in=policy.LIVE_CONTRACT_STATUSES,
        ).exists():
            return ['existing customer (Active/Sent contract): company/contact changes are Cira-only']
        return []
    return []


_MAX_FIELDS, _MAX_REASONS, _MAX_REASON_CHARS = 200, 20, 300


def _present(raw) -> bool:
    return bool(raw) and str(raw).strip() not in ('', '{}')


def observe(*, tool, verb, collection='', record_id='', data=None, expected_version='',
            expected_values='', authorization_context='', request_key='', user=None):
    """Record the policy verdict for one write attempt. Never raises."""
    mode = str(getattr(settings, 'AGENT_GATE_MODE', OBSERVE) or '').lower()
    if mode != OBSERVE:
        return None
    try:
        from crm_app.models import AgentRequest

        values = _as_dict(data)
        fields = sorted(str(name)[:100] for name in values)[:_MAX_FIELDS]
        if user is None or not getattr(user, 'is_authenticated', False):
            user = _current_user()
        username = getattr(user, 'username', '') if user else ''
        principal = policy.principal_for_username(username) if user else None
        if tool.startswith('rest:') and principal is None:
            return None  # humans using the CRM website are out of scope
        reasons, gaps = [], []
        if user is None:
            decision = 'unauthenticated'
        elif principal is None:
            decision = 'not_agent'
        else:
            reasons, condition = policy.evaluate(principal, verb, collection, fields)
            if not reasons and condition:
                reasons = _condition_reasons(condition, collection, str(record_id or ''), values,
                                             authorized=_present(authorization_context))
            if tool.startswith('rest:'):
                reasons.append('agent writes via REST will be refused; use the MCP write tools')
            decision = 'would_deny' if reasons else 'allow'
            if not request_key:
                gaps.append('request_key_missing')
            if verb == policy.UPDATE and not expected_version:
                gaps.append('expected_version_missing')
            if verb == policy.UPDATE and not _present(expected_values):
                gaps.append('expected_values_missing')
            reasons = [r[:_MAX_REASON_CHARS] for r in reasons[:_MAX_REASONS]]
        with transaction.atomic():  # savepoint: a failed insert never poisons the caller's transaction
            row = AgentRequest.objects.create(
                mode=mode,
                username=username[:150],
                principal=principal.name if principal else '',
                tool=tool[:60],
                verb=verb[:20],
                collection=(collection or '')[:50],
                record_id=str(record_id or '')[:64],
                fields=fields,
                decision=decision,
                reasons=reasons,
                protocol_gaps=gaps,
                request_key=(request_key or '')[:200],
                has_expected_version=bool(expected_version),
                payload_sha256=_digest(values) if values else '',
            )
        return row
    except Exception:
        logger.warning('agent gate observe failed; write proceeds unchanged', exc_info=True)
        return None
