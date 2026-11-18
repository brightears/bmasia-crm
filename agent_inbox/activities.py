"""Recording and voiding activities (REST and MCP share this module).

Provenance is set by the server: ``recorded_via`` comes from the route the
write arrived on (``ui`` for a person on the website, ``rest`` for an API
token, ``mcp`` for the MCP tool, ``job`` for a background job), never from the
request body. Agent accounts may not claim that a person or the CRM wrote the
text (``source_system`` manual or crm).

One live activity per company and source: a second recorder of the same
``source_ref`` is refused, except that a recorder who is not an agent account
(a capture job or a person) may always record it. The earlier agent row is then
voided and linked to the new one through ``duplicate_of``.
"""
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
    payload_sha256, source_ref_field, strict_object, text_field, url_field,
)

ACTIVITY_KEYS = frozenset({
    'idempotency_key', 'company_id', 'contact_id', 'contract_id', 'quote_id', 'opportunity_id',
    'kind', 'direction', 'occurred_at', 'summary', 'body', 'participants',
    'source_system', 'source_ref', 'source_url',
})
ACTIVITY_REQUIRED = ('idempotency_key', 'company_id', 'kind', 'direction', 'occurred_at', 'summary', 'source_system')
ROUTES = ('rest', 'ui', 'mcp', 'job')
DUPLICATE_REASON = 'Replaced by a captured record of the same source.'


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


def _validated(user, body):
    from crm_app.models import Company, Contact, Contract, Opportunity, Quote

    company_id = optional_uuid(body, 'company_id')
    company = Company.objects.filter(pk=company_id).only('pk').first()
    if company is None:
        raise ServiceError(422, 'unknown_record', 'company_id does not exist')
    source_system = choice(body, 'source_system', SOURCE_SYSTEM_CHOICES)
    if source_system in policy.PERSON_SOURCE_SYSTEMS and policy.is_agent_account(user):
        raise ServiceError(
            422, 'source_not_allowed',
            f'source_system {source_system} is for text a person entered; use agent or the real source',
        )
    return {
        'company': company,
        'contact': _related(Contact, optional_uuid(body, 'contact_id'), 'contact_id', company),
        'contract': _related(Contract, optional_uuid(body, 'contract_id'), 'contract_id', company),
        'quote': _related(Quote, optional_uuid(body, 'quote_id'), 'quote_id', company),
        'opportunity': _related(Opportunity, optional_uuid(body, 'opportunity_id'), 'opportunity_id', company),
        'kind': choice(body, 'kind', ACTIVITY_KIND_CHOICES),
        'direction': choice(body, 'direction', ACTIVITY_DIRECTION_CHOICES),
        'occurred_at': past_datetime(body.get('occurred_at'), 'occurred_at'),
        'summary': text_field(body, 'summary', SUMMARY_MAX, required=True),
        # Bodies are copies of the source and may carry its formatting characters.
        'body': text_field(body, 'body', BODY_MAX, multiline=True, allow_format=True),
        'participants': _participants(body.get('participants')),
        'source_system': source_system,
        'source_ref': source_ref_field(body, 'source_ref', source_system, SOURCE_REF_MAX),
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


def _same_source(values):
    if not values['source_ref']:
        return None
    return Activity.objects.filter(
        company=values['company'], source_system=values['source_system'],
        source_ref=values['source_ref'], is_void=False,
    ).first()


def _source_check(user, key, digest, values):
    """(replayed, displaced): the caller's own stored retry, or an agent row a trusted recorder replaces."""
    other = _same_source(values)
    if other is None:
        return None, None
    # A concurrent retry of the same request may have stored the row in between.
    replayed = _replay(user, key, digest)
    if replayed is not None:
        return replayed, None
    if not policy.is_agent_account(user) and other.recorded_by is not None \
            and policy.is_agent_account(other.recorded_by):
        return None, other
    raise ServiceError(
        409, 'source_already_recorded',
        'This source_ref is already recorded as an activity for this company',
        existing_activity_id=str(other.pk),
    )


def record_activity(user, body, *, via):
    """Store one activity. ``via`` is the route it arrived on. Returns (activity, replayed)."""
    if via not in ROUTES:
        raise ValueError(f'unknown route {via!r}')
    if not policy.activity_writes_enabled():
        raise _not_enabled()
    if user is None or not getattr(user, 'is_authenticated', False):
        raise ServiceError(401, 'not_authenticated', 'Authentication required')
    strict_object(body, ACTIVITY_KEYS, required=ACTIVITY_REQUIRED)
    key = key_field(body)
    digest = payload_sha256(body)

    replayed = _replay(user, key, digest)
    if replayed is not None:
        return replayed, True

    values = _validated(user, body)
    replayed, displaced = _source_check(user, key, digest, values)
    if replayed is not None:
        return replayed, True
    since = timezone.now() - timedelta(hours=24)
    if Activity.objects.filter(recorded_by=user, created_at__gte=since).count() >= policy.activity_daily_cap():
        raise ServiceError(429, 'daily_cap', f'Daily activity cap of {policy.activity_daily_cap()} reached for this user')

    try:
        with transaction.atomic():
            if displaced is not None:
                displaced = Activity.objects.select_for_update().get(pk=displaced.pk)
                displaced.is_void = True
                displaced.void_reason = DUPLICATE_REASON
                displaced.voided_by = user
                displaced.voided_at = timezone.now()
                displaced.save(update_fields=['is_void', 'void_reason', 'voided_by', 'voided_at', 'updated_at'])
            activity = Activity.objects.create(
                **values,
                recorded_by=user,
                recorded_by_username=str(user.username)[:150],
                recorded_via=via,
                idempotency_key=key,
                payload_sha256=digest,
            )
            if displaced is not None:
                displaced.duplicate_of = activity
                displaced.save(update_fields=['duplicate_of', 'updated_at'])
    except IntegrityError:
        # A concurrent request stored the same key (or source) first.
        replayed = _replay(user, key, digest)
        if replayed is None:
            replayed, _ = _source_check(user, key, digest, values)
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
