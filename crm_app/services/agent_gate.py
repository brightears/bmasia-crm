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
import re
import uuid

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


_UNKNOWN = object()  # a stored-state lookup failed; never read as permission


class _Uncertain(Exception):
    """Raised when a verdict depends on stored state that could not be read."""


def _canonical_uuid(value):
    """Only canonical UUIDs are stored as record ids; anything else is not an id."""
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None
    return str(parsed) if str(parsed) == str(value).lower() else None


def _key_digest(request_key):
    """Request keys are stored only as a SHA-256 digest (never as caller text)."""
    return 'sha256:' + hashlib.sha256(str(request_key).encode('utf-8')).hexdigest()
# update_record control keys that are not model/serializer fields.
_CONTROL_KEYS = {'contract': {'replace_service_locations'}}
_FIELD_CACHE = {}


def _known_fields(collection):
    """Model + serializer field names for a collection (the only names ever recorded)."""
    if collection not in _FIELD_CACHE:
        from crm_app.mcp import _COLLECTION_MAP, _get_serializer_class
        names = set(_CONTROL_KEYS.get(collection, ()))
        if collection in _COLLECTION_MAP:
            model, serializer_path = _COLLECTION_MAP[collection]
            for model_field in model._meta.get_fields():
                names.add(model_field.name)
                if getattr(model_field, 'attname', None):
                    names.add(model_field.attname)
            try:
                names |= set(_get_serializer_class(serializer_path)().fields)
            except Exception:  # pragma: no cover - serializer needs context
                pass
        _FIELD_CACHE[collection] = frozenset(names)
    return _FIELD_CACHE[collection]


def _current_value(collection, record_id, field_name):
    """Persisted value of one field; None if there is no such record; raises _Uncertain on failure."""
    if not record_id:
        return None
    try:
        from crm_app.mcp import _COLLECTION_MAP
        model = _COLLECTION_MAP[collection][0]
        return model.objects.filter(pk=record_id).values_list(field_name, flat=True).first()
    except Exception as exc:
        raise _Uncertain(f'could not read stored {collection}.{field_name}') from exc


def _is_live_customer(company_id):
    """True/False from the database; raises _Uncertain if it cannot be determined."""
    from crm_app.models import Contract
    if not company_id:
        return False
    if _canonical_uuid(company_id) is None:
        raise _Uncertain('company reference is not a valid id')
    try:
        return Contract.objects.filter(
            company_id=company_id, status__in=policy.LIVE_CONTRACT_STATUSES,
        ).exists()
    except Exception as exc:
        raise _Uncertain('could not read the company\'s contracts') from exc


def _terminal_reasons(label, field_name, terminal, collection, record_id, values):
    """Refuse moving into a terminal state and reopening a record that is already terminal."""
    if field_name not in values:
        return []
    proposed = values.get(field_name)
    normalise = (lambda v: str(v or '').lower()) if label == 'ticket' else (lambda v: v)
    if normalise(proposed) in terminal:
        return [f'{label} {field_name} {proposed} is terminal (Cira-only for this agent)']
    current = _current_value(collection, record_id, field_name)
    if normalise(current) in terminal:
        return [f'reopening a {current} {label} is Cira-only']
    return []


def _condition_reasons(condition, collection, record_id, values, authorization_context=''):
    if condition == 'opportunity_non_terminal':
        return _terminal_reasons('opportunity', 'stage', policy.OPPORTUNITY_TERMINAL,
                                 collection, record_id, values)
    if condition == 'ticket_non_terminal':
        return _terminal_reasons('ticket', 'status', policy.TICKET_TERMINAL,
                                 collection, record_id, values)
    if condition == 'terminal_needs_explicit_authorization':
        if 'stage' not in values:
            return []
        if values.get('stage') in policy.OPPORTUNITY_TERMINAL:
            # Reuse the CRM's own guard so observe verdicts match enforcement
            # (exact kind, source thread, record and patch binding).
            from crm_app.mcp import _guarded_commercial_authorization
            error = _guarded_commercial_authorization(
                collection, record_id, values, authorization_context or '{}')
            return [f'Won/Lost without valid explicit-user authorization: {error}'] if error else []
        current = _current_value(collection, record_id, 'stage')
        if current in policy.OPPORTUNITY_TERMINAL:
            return [f'reopening a {current} opportunity is Cira-only']
        return []
    if condition == 'lead_company_only':
        if collection == 'company':
            candidates = {record_id}
        else:
            existing = _current_value('contact', record_id, 'company_id') if collection == 'contact' else None
            proposed = values.get('company') or values.get('company_id')
            candidates = {str(c) for c in (existing, proposed) if c}
            if existing and proposed and str(existing) != str(proposed) and any(
                    _is_live_customer(c) for c in candidates):
                return ['moving a contact to or from an existing customer is Cira-only']
        if any(_is_live_customer(c) for c in candidates):
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
        unknown_keys = 0
        if verb in (policy.CREATE, policy.UPDATE):
            known = _known_fields(collection)
            fields = sorted(name for name in values if isinstance(name, str) and name in known)[:_MAX_FIELDS]
            unknown_keys = len(values) - len(fields)
        else:
            fields = []  # convert/rene payloads are not field patches; only their digest is kept
        raw_record_id = str(record_id or '')
        record_id = _canonical_uuid(raw_record_id) or ('<invalid>' if raw_record_id else '')
        request_key = _key_digest(request_key) if request_key else ''
        if user is None or not getattr(user, 'is_authenticated', False):
            user = _current_user()
        username = getattr(user, 'username', '') if user else ''
        principal = policy.principal_for_username(username) if user else None
        if tool.startswith('rest:') and principal is None:
            return None  # humans using the CRM website are out of scope
        reasons, gaps, uncertain = [], [], ''
        if user is None:
            decision = 'unauthenticated'
        elif principal is None:
            decision = 'not_agent'
        else:
            reasons, condition = policy.evaluate(principal, verb, collection, fields)
            if not reasons and condition:
                try:
                    if record_id == '<invalid>':
                        raise _Uncertain('record id is not a valid id')
                    if verb != policy.CREATE and not record_id:
                        raise _Uncertain('record id is missing')
                    reasons = _condition_reasons(condition, collection, record_id, values,
                                                 authorization_context=authorization_context)
                except _Uncertain as exc:
                    uncertain = str(exc)
            if unknown_keys:
                reasons.append(f'{unknown_keys} unrecognised field key(s) (not recorded)')
            if tool.startswith('rest:'):
                reasons.append('agent writes via REST will be refused; use the MCP write tools')
            decision = 'would_deny' if reasons else ('uncertain' if uncertain else 'allow')
            if uncertain:
                reasons.append(f'verdict uncertain: {uncertain}')
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
                record_id=record_id[:64],
                fields=fields,
                decision=decision,
                reasons=reasons,
                protocol_gaps=gaps,
                request_key=request_key[:200],
                has_expected_version=bool(expected_version),
                payload_sha256=_digest(values) if values else '',
            )
        return row
    except Exception:
        logger.warning('agent gate observe failed; write proceeds unchanged', exc_info=True)
        return None
