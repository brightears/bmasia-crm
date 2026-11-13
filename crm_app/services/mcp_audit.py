"""AuditLog rows for writes made through the MCP endpoint.

Each row is attributed to the authenticated caller behind the MCP token (the
user the transport stores in ``django_request_ctx``), never to a stand-in
admin. Rows use the same shape as ``BaseModelViewSet.log_action`` on the REST
path: ``changes`` maps a field to ``{'old': ..., 'new': ...}`` and
``additional_data`` carries a timestamp plus where the write came from.

Callers write the row inside the same transaction as the change, so a failure
to audit rolls the change back.
"""
from __future__ import annotations

import ipaddress
import re

from django.utils import timezone

from crm_app.models import AuditLog
from crm_app.services import agent_gate

# Field names whose values never go into an audit row. None of the MCP
# collections exposes such a field today; this keeps it that way if one is added.
_SECRET_KEY = re.compile(r'password|passwd|secret|token|api_?key|credential|smtp', re.IGNORECASE)
REDACTED = '[redacted]'

# Natural keys used to identify a deleted record after it is gone.
_SUMMARY_FIELDS = (
    'name', 'title', 'subject', 'outlet_name', 'location_name', 'product_service',
    'contract_number', 'quote_number', 'invoice_number', 'ticket_number', 'article_number',
    'status', 'company_id', 'contract_id', 'quote_id', 'invoice_id',
)


def current_request():
    try:
        from mcp_server.djangomcp import django_request_ctx
    except Exception:  # pragma: no cover - library layout changed
        return None
    return django_request_ctx.get(None)


def caller():
    """The authenticated user behind the current MCP call, or None."""
    return agent_gate._current_user()


def _json_safe(value):
    from crm_app.views import serialize_audit_changes
    return serialize_audit_changes(value)


def _redact(changes):
    if not isinstance(changes, dict):
        return changes
    return {
        key: ({'old': REDACTED, 'new': REDACTED} if _SECRET_KEY.search(str(key)) else value)
        for key, value in changes.items()
    }


def _client_ip(meta):
    forwarded = meta.get('HTTP_X_FORWARDED_FOR') or ''
    raw = forwarded.split(',')[0].strip() if forwarded else meta.get('REMOTE_ADDR') or ''
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def snapshot(serializer_class, instance):
    """JSON-safe serializer representation, as the REST update path compares."""
    return _json_safe(serializer_class(instance).data)


def diff(before, after):
    """Changed representation keys only, as ``BaseModelViewSet.perform_update`` records."""
    return {
        key: {'old': before.get(key), 'new': value}
        for key, value in after.items()
        if before.get(key) != value
    }


def created_fields(representation, applied, supplied):
    """The fields a caller set on create, with the values actually stored."""
    return {
        key: {'old': None, 'new': representation[key] if key in representation else supplied.get(key)}
        for key in applied
    }


def summary(instance):
    """Identifying fields of a record, read before it is deleted."""
    result = {'id': str(instance.pk), 'model': instance.__class__.__name__}
    for name in _SUMMARY_FIELDS:
        value = getattr(instance, name, None)
        if value not in (None, ''):
            result[name] = str(value)
    return result


def record(action, model_name, record_id, *, tool, changes=None, extra=None):
    """Write one AuditLog row for an MCP write. Raises on failure."""
    request = current_request()
    meta = getattr(request, 'META', None) or {}
    additional = {'timestamp': timezone.now().isoformat(), 'via': 'mcp', 'tool': tool}
    if extra:
        additional.update(extra)
    return AuditLog.objects.create(
        user=caller(),
        action=action,
        model_name=str(model_name)[:50],
        record_id=str(record_id)[:100],
        ip_address=_client_ip(meta),
        user_agent=str(meta.get('HTTP_USER_AGENT', '') or ''),
        changes=_json_safe(_redact(changes)) if changes is not None else None,
        additional_data=_json_safe(additional),
    )
