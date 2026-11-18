"""Recording and voiding activities (REST and MCP share this module)."""
from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from agent_inbox import policy
from agent_inbox.models import (
    ACTIVITY_DIRECTION_CHOICES, ACTIVITY_KIND_CHOICES, BODY_MAX, PARTICIPANT_ADDRESS_MAX,
    PARTICIPANT_NAME_MAX, PARTICIPANT_ROLES, PARTICIPANTS_MAX, REASON_MAX, SOURCE_REF_MAX,
    SOURCE_SYSTEM_CHOICES, SOURCE_URL_MAX, SUMMARY_MAX, Activity,
)
from agent_inbox.validation import (
    ServiceError, bad, choice, key_field, optional_uuid, past_datetime,
    payload_sha256, strict_object, text_field, token_field, url_field,
)

ACTIVITY_KEYS = frozenset({
    'idempotency_key', 'company_id', 'contact_id', 'contract_id', 'quote_id', 'opportunity_id',
    'kind', 'direction', 'occurred_at', 'summary', 'body', 'participants',
    'source_system', 'source_ref', 'source_url', 'recorded_via',
})
ACTIVITY_REQUIRED = ('idempotency_key', 'company_id', 'kind', 'direction', 'occurred_at', 'summary', 'source_system')
# A REST caller may say it is the website or a job; MCP is always 'mcp'.
REST_RECORDED_VIA = ('rest', 'ui', 'job')


def _not_enabled():
    return ServiceError(403, 'not_enabled', policy.ACTIVITY_DISABLED_DETAIL)


def _participants(value):
    if value in (None, ''):
        return []
    if not isinstance(value, list):
        raise bad('participants must be a list of {name, address, role} objects')
    if len(value) > PARTICIPANTS_MAX:
        raise bad(f'participants may list at most {PARTICIPANTS_MAX} people')
    cleaned = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) - {'name', 'address', 'role'}:
            raise bad(f'participants[{index}] must be an object with only name, address and role')
        name = text_field(item, 'name', PARTICIPANT_NAME_MAX)
        address = text_field(item, 'address', PARTICIPANT_ADDRESS_MAX)
        role = item.get('role') or 'other'
        if role not in PARTICIPANT_ROLES:
            raise bad(f'participants[{index}].role must be one of: ' + ', '.join(PARTICIPANT_ROLES))
        if not name and not address:
            raise bad(f'participants[{index}] needs a name or an address')
        cleaned.append({'name': name, 'address': address, 'role': role})
    return cleaned


def _related(model, pk, key, company):
    if pk is None:
        return None
    obj = model.objects.filter(pk=pk).only('pk', 'company_id').first()
    if obj is None:
        raise ServiceError(422, 'unknown_record', f'{key} does not exist')
    if obj.company_id != company.pk:
        raise ServiceError(422, 'wrong_company', f'{key} does not belong to company_id')
    return obj


def _validated(body):
    from crm_app.models import Company, Contact, Contract, Opportunity, Quote

    company_id = optional_uuid(body, 'company_id')
    company = Company.objects.filter(pk=company_id).only('pk').first()
    if company is None:
        raise ServiceError(422, 'unknown_record', 'company_id does not exist')
    summary = text_field(body, 'summary', SUMMARY_MAX, required=True)
    text = text_field(body, 'body', BODY_MAX, multiline=True)
    return {
        'company': company,
        'contact': _related(Contact, optional_uuid(body, 'contact_id'), 'contact_id', company),
        'contract': _related(Contract, optional_uuid(body, 'contract_id'), 'contract_id', company),
        'quote': _related(Quote, optional_uuid(body, 'quote_id'), 'quote_id', company),
        'opportunity': _related(Opportunity, optional_uuid(body, 'opportunity_id'), 'opportunity_id', company),
        'kind': choice(body, 'kind', ACTIVITY_KIND_CHOICES),
        'direction': choice(body, 'direction', ACTIVITY_DIRECTION_CHOICES),
        'occurred_at': past_datetime(body.get('occurred_at'), 'occurred_at'),
        'summary': summary,
        'body': text,
        'participants': _participants(body.get('participants')),
        'source_system': choice(body, 'source_system', SOURCE_SYSTEM_CHOICES),
        'source_ref': token_field(body, 'source_ref', SOURCE_REF_MAX),
        'source_url': url_field(body, 'source_url', SOURCE_URL_MAX),
    }


def _replay(user, key, digest):
    existing = Activity.objects.filter(recorded_by=user, idempotency_key=key).first()
    if existing is None:
        return None
    if existing.payload_sha256 == digest:
        return existing
    raise ServiceError(
        409, 'idempotency_conflict',
        'idempotency_key was already used for a different activity; use a new key for a new activity',
        existing_activity_id=str(existing.pk),
    )


def _source_conflict(user, key, digest, values):
    """Refuse a second live activity for the same source, unless it is this caller's retry."""
    if not values['source_ref']:
        return None
    other = Activity.objects.filter(
        company=values['company'], source_system=values['source_system'],
        source_ref=values['source_ref'], is_void=False,
    ).only('pk').first()
    if other is None:
        return None
    # A concurrent retry of the same request may have stored the row in between.
    replayed = _replay(user, key, digest)
    if replayed is not None:
        return replayed
    raise ServiceError(
        409, 'source_already_recorded',
        'This source_ref is already recorded as an activity for this company',
        existing_activity_id=str(other.pk),
    )


def record_activity(user, body, *, via):
    """Store one activity. Returns (activity, replayed). Raises ServiceError."""
    if not policy.activity_writes_enabled():
        raise _not_enabled()
    if user is None or not getattr(user, 'is_authenticated', False):
        raise ServiceError(401, 'not_authenticated', 'Authentication required')
    allowed = ACTIVITY_KEYS if via != 'mcp' else ACTIVITY_KEYS - {'recorded_via'}
    strict_object(body, allowed, required=ACTIVITY_REQUIRED)
    key = key_field(body)
    recorded_via = 'mcp' if via == 'mcp' else choice(body, 'recorded_via', REST_RECORDED_VIA, default='rest')
    digest = payload_sha256(body)

    replayed = _replay(user, key, digest)
    if replayed is not None:
        return replayed, True

    values = _validated(body)
    replayed = _source_conflict(user, key, digest, values)
    if replayed is not None:
        return replayed, True
    since = timezone.now() - timedelta(hours=24)
    if Activity.objects.filter(recorded_by=user, created_at__gte=since).count() >= policy.activity_daily_cap():
        raise ServiceError(429, 'daily_cap', f'Daily activity cap of {policy.activity_daily_cap()} reached for this user')

    try:
        with transaction.atomic():
            activity = Activity.objects.create(
                **values,
                recorded_by=user,
                recorded_by_username=str(user.username)[:150],
                recorded_via=recorded_via,
                idempotency_key=key,
                payload_sha256=digest,
            )
    except IntegrityError:
        # A concurrent request stored the same key (or source) first.
        replayed = _replay(user, key, digest) or _source_conflict(user, key, digest, values)
        if replayed is not None:
            return replayed, True
        raise
    return activity, False


def void_activity(user, activity_id, body):
    """Mark an activity void with a reason. Only its recorder or a person may do this."""
    if not policy.activity_writes_enabled():
        raise _not_enabled()
    strict_object(body, {'reason'}, required=('reason',))
    reason = text_field(body, 'reason', REASON_MAX, required=True)
    with transaction.atomic():
        activity = Activity.objects.select_for_update().filter(pk=activity_id).first()
        if activity is None:
            raise ServiceError(404, 'not_found', 'Activity not found')
        if policy.is_agent_account(user) and activity.recorded_by_id != user.pk:
            raise ServiceError(403, 'forbidden', 'An agent may void only activities it recorded')
        if activity.is_void:
            raise ServiceError(409, 'already_void', 'Activity is already void')
        activity.is_void = True
        activity.void_reason = reason
        activity.voided_by = user
        activity.voided_at = timezone.now()
        activity.save(update_fields=['is_void', 'void_reason', 'voided_by', 'voided_at', 'updated_at'])
    return activity

