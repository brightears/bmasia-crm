"""Change proposals: storing them, and a person's accept / reject decision.

Storing a proposal never changes the target record. Accepting one applies it
through the guarded MCP write path (``crm_app.mcp.update_record`` with
``expected_version`` and ``expected_values``, or ``create_record`` for a new
contact or task), run as the reviewer, inside one transaction with the
proposal's own update. The AuditLog row that path writes is tagged with the
proposal id. A refused or failed apply writes nothing to the target.
"""
from __future__ import annotations

import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from agent_inbox import policy
from agent_inbox.models import (
    APPLY_ERROR_MAX, DECISION_NOTE_MAX, EVIDENCE_QUOTE_MAX, FINGERPRINT_BLOCKING_STATUSES,
    MODEL_NAME_MAX, PATCH_VALUE_MAX, PROPOSER_KIND_CHOICES, RATIONALE_MAX, SOURCE_REF_MAX,
    SOURCE_SYSTEM_CHOICES, SOURCE_URL_MAX, Activity, ChangeProposal,
)
from agent_inbox.validation import (
    ServiceError, bad, batch_field, choice, has_control, optional_uuid, payload_sha256,
    quote_occurs_in, strict_object, text_field, token_field, unprocessable, url_field, uuid_value,
)

PROPOSAL_KEYS = frozenset({
    'kind', 'target_collection', 'target_id', 'company_id', 'patch',
    'evidence_quote', 'evidence_source_system', 'evidence_source_ref', 'evidence_source_url',
    'activity_id', 'rationale', 'proposer_kind', 'model', 'prompt_version', 'confidence', 'batch_key',
})
MULTILINE_FIELDS = frozenset({'notes', 'description'})
BULK_REJECT_MAX = 200
RECORD_CHANGED_DETAIL = (
    'The record changed after this proposal was made. Nothing was applied; the current values '
    'were re-read. Review them and accept again if the change is still right.'
)


def _not_enabled():
    return ServiceError(403, 'not_enabled', policy.PROPOSALS_DISABLED_DETAIL)


def _plain(value):
    return json.loads(json.dumps(value, default=str))


def _collection(collection):
    from crm_app.mcp import _COLLECTION_MAP, _get_serializer_class

    model, path = _COLLECTION_MAP[collection]
    return model, _get_serializer_class(path)


def _same(serializer_class, key, current, proposed):
    from crm_app.mcp import _guarded_field_equal

    field = serializer_class().fields.get(key)
    if current in (None, '') and proposed in (None, ''):
        return True
    return _guarded_field_equal(field, current, proposed)


def _same_version(left, right):
    from crm_app.mcp import _guarded_version

    a, b = _guarded_version(left), _guarded_version(right)
    return a is not None and a == b


def expire_due():
    """Mark open proposals past their expiry as expired. Returns the number changed."""
    now = timezone.now()
    return ChangeProposal.objects.filter(status='proposed', expires_at__lte=now).update(
        status='expired', updated_at=now,
    )


# ------------------------------------------------------------------ the patch


def _clean_value(key, value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise bad(f'patch.{key} must be a string or null')
    value = value.replace('\r\n', '\n').replace('\r', '\n').strip()
    if len(value) > PATCH_VALUE_MAX:
        raise bad(f'patch.{key} must be at most {PATCH_VALUE_MAX} characters')
    if has_control(value, allow_newlines=key in MULTILINE_FIELDS):
        raise bad(f'patch.{key} contains control characters')
    return value


def _check_fields(kind, collection, keys):
    allowed = policy.allowed_fields(kind, collection)
    blocked = sorted(set(keys) - allowed)
    if blocked:
        raise unprocessable(
            'field_not_allowed',
            f'A {kind} proposal on {collection} may not change: {", ".join(blocked)}. '
            f'Allowed: {", ".join(sorted(allowed)) or "nothing"}.',
            blocked_fields=blocked, allowed_fields=sorted(allowed),
        )


def _clean_patch(kind, collection, patch):
    if not isinstance(patch, dict) or not patch:
        raise bad('patch must be a non-empty object of field -> proposed value')
    _check_fields(kind, collection, patch)
    cleaned = {key: _clean_value(key, value) for key, value in patch.items()}
    if kind == 'note' and not cleaned.get('notes'):
        raise bad('patch.notes must carry the text to append')
    missing = sorted(policy.PROPOSAL_REQUIRED_FIELDS.get(kind, frozenset()) - {
        key for key, value in cleaned.items() if value
    })
    if missing:
        raise bad(f'A {kind} proposal needs: {", ".join(missing)}')
    return cleaned


def _join_notes(current, text):
    current = (current or '').rstrip()
    return f'{current}{policy.NOTE_SEPARATOR}{text}' if current else text


def _serializer_check(serializer):
    if not serializer.is_valid():
        raise unprocessable('invalid_value', 'The proposed values do not pass the record\'s validation',
                            errors=_plain(serializer.errors))


def _check_task_relations(company, patch):
    from crm_app.models import Contact, Contract, Opportunity

    for key, model in (('related_contact', Contact), ('related_contract', Contract),
                       ('related_opportunity', Opportunity)):
        value = patch.get(key)
        if not value:
            continue
        pk = uuid_value(value, f'patch.{key}')
        obj = model.objects.filter(pk=pk).only('pk', 'company_id').first()
        if obj is None or obj.company_id != company.pk:
            raise unprocessable('wrong_company', f'patch.{key} is not a record of this company')


def _fingerprint(kind, collection, target_id, company_id, patch):
    if kind == 'new_contact':
        basis = {'kind': kind, 'company': str(company_id), 'email': (patch.get('email') or '').lower()}
    elif kind == 'note':
        basis = {'kind': kind, 'collection': collection, 'target': target_id, 'text': patch['notes']}
    elif kind == 'task':
        basis = {'kind': kind, 'company': str(company_id), 'patch': patch}
    else:
        basis = {'kind': kind, 'collection': collection, 'target': target_id, 'patch': patch}
    return payload_sha256({'v': 1, **basis})


# ------------------------------------------------------------------ create


def _resolve_target(body, kind):
    from crm_app.models import Company

    collections = policy.collections_for(kind)
    collection = body.get('target_collection') or (collections[0] if len(collections) == 1 else None)
    if collection not in collections:
        raise unprocessable(
            'collection_not_allowed',
            f'A {kind} proposal targets one of: {", ".join(collections)}. '
            'Contracts, quotes and invoices cannot be changed through proposals.',
        )
    company_id = optional_uuid(body, 'company_id')
    if kind in policy.CREATE_KINDS:
        if body.get('target_id'):
            raise bad(f'A {kind} proposal creates a record; leave target_id empty')
        company = Company.objects.filter(pk=company_id).first() if company_id else None
        if company is None:
            raise unprocessable('unknown_record', 'company_id is required and must exist')
        return collection, '', None, company
    target_uuid = uuid_value(body.get('target_id'), 'target_id')
    model, _ = _collection(collection)
    instance = model.objects.filter(pk=target_uuid).first()
    if instance is None:
        raise unprocessable('unknown_record', f'{collection} {target_uuid} does not exist')
    company = instance if collection == 'company' else instance.company
    if company_id and company_id != company.pk:
        raise unprocessable('wrong_company', 'company_id does not match the target record')
    return collection, str(target_uuid), instance, company


def _evidence(body, proposer_kind, company):
    quote = text_field(body, 'evidence_quote', EVIDENCE_QUOTE_MAX, multiline=True)
    if proposer_kind in policy.EVIDENCE_REQUIRED_KINDS and not quote:
        raise unprocessable(
            'evidence_required',
            'evidence_quote is required: copy the exact words from the source that support the change',
        )
    activity = None
    activity_id = optional_uuid(body, 'activity_id')
    if activity_id:
        activity = Activity.objects.filter(pk=activity_id).first()
        if activity is None:
            raise unprocessable('unknown_record', 'activity_id does not exist')
        if activity.is_void:
            raise unprocessable('activity_void', 'activity_id refers to a voided activity')
        if activity.company_id != company.pk:
            raise unprocessable('wrong_company', 'activity_id belongs to another company')
    verified = False
    if activity is not None and activity.body:
        if quote and not quote_occurs_in(quote, activity.body):
            raise unprocessable(
                'quote_not_verbatim',
                'evidence_quote does not occur verbatim in the referenced activity body',
            )
        verified = bool(quote)
    system = body.get('evidence_source_system') or (activity.source_system if activity else '')
    systems = [value for value, _ in SOURCE_SYSTEM_CHOICES]
    if system not in [''] + systems:
        raise bad('evidence_source_system must be one of: ' + ', '.join(systems))
    values = {
        'evidence_quote': quote,
        'evidence_verified': verified,
        'evidence_source_system': system,
        'evidence_source_ref': token_field(body, 'evidence_source_ref', SOURCE_REF_MAX)
        or (activity.source_ref if activity else ''),
        'evidence_source_url': url_field(body, 'evidence_source_url', SOURCE_URL_MAX)
        or (activity.source_url if activity else ''),
        'activity': activity,
    }
    return values


def _proposer_kind(body, user):
    is_agent = policy.is_agent_account(user)
    kind = body.get('proposer_kind') or ('agent' if is_agent else 'human')
    choice({'proposer_kind': kind}, 'proposer_kind', PROPOSER_KIND_CHOICES)
    if is_agent and kind not in policy.AGENT_PROPOSER_KINDS:
        raise ServiceError(403, 'proposer_kind_not_allowed', 'An agent account proposes as agent or ai')
    return kind


def _confidence(body):
    value = body.get('confidence')
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise bad('confidence must be a number from 0 to 1')
    return float(value)


def _existing_outcome(fingerprint, user):
    existing = ChangeProposal.objects.filter(
        fingerprint=fingerprint, status__in=FINGERPRINT_BLOCKING_STATUSES,
    ).first()
    if existing is None:
        return None
    if existing.status == 'proposed' and existing.proposer_id == getattr(user, 'pk', None):
        return existing
    code, detail = {
        'proposed': ('duplicate_open', 'The same change is already waiting for review'),
        'rejected': ('previously_rejected', 'The same change was rejected before and is not raised again'),
        'accepted': ('already_applied', 'The same change was already accepted'),
        'edited': ('already_applied', 'The same change was already accepted'),
    }[existing.status]
    raise ServiceError(409, code, detail, existing_proposal_id=str(existing.pk), existing_status=existing.status)


def create_proposal(user, body, *, via):
    """Store one proposal. Returns (proposal, replayed). Raises ServiceError."""
    if not policy.proposals_enabled():
        raise _not_enabled()
    if user is None or not getattr(user, 'is_authenticated', False):
        raise ServiceError(401, 'not_authenticated', 'Authentication required')
    strict_object(body, PROPOSAL_KEYS, required=('kind', 'patch'))
    expire_due()
    kind = body.get('kind')
    if kind not in policy.APPLICABLE_KINDS:
        raise unprocessable(
            'kind_not_allowed',
            f'kind must be one of: {", ".join(sorted(policy.APPLICABLE_KINDS))} (link and other are not enabled)',
        )
    proposer_kind = _proposer_kind(body, user)
    collection, target_id, instance, company = _resolve_target(body, kind)
    patch = _clean_patch(kind, collection, body.get('patch'))
    evidence = _evidence(body, proposer_kind, company)
    rationale = text_field(body, 'rationale', RATIONALE_MAX, multiline=True)
    model_name = text_field(body, 'model', MODEL_NAME_MAX)
    prompt_version = text_field(body, 'prompt_version', MODEL_NAME_MAX)
    confidence = _confidence(body)
    batch_key = batch_field(body)

    _, serializer_class = _collection(collection)
    current_values, expected_version = {}, ''
    if instance is not None:
        current = _plain(serializer_class(instance).data)
        current_values = {key: current.get(key) for key in patch}
        expected_version = str(current.get('updated_at') or '')
        if kind == 'field_update':
            if all(_same(serializer_class, key, current_values[key], value) for key, value in patch.items()):
                raise unprocessable('no_change', 'The record already has these values')
            _serializer_check(serializer_class(instance, data=patch, partial=True))
        else:
            joined = _join_notes(current_values.get('notes'), patch['notes'])
            _serializer_check(serializer_class(instance, data={'notes': joined}, partial=True))
    else:
        if kind == 'task':
            _check_task_relations(company, patch)
        _serializer_check(serializer_class(data={'company': str(company.pk), **patch}))

    fingerprint = _fingerprint(kind, collection, target_id, company.pk, patch)
    replayed = _existing_outcome(fingerprint, user)
    if replayed is not None:
        return replayed, True

    since = timezone.now() - timedelta(hours=24)
    cap = policy.proposal_daily_cap()
    if ChangeProposal.objects.filter(proposer=user, created_at__gte=since).count() >= cap:
        raise ServiceError(429, 'daily_cap', f'Daily proposal cap of {cap} reached for this proposer')

    try:
        with transaction.atomic():
            proposal = ChangeProposal.objects.create(
                company=company,
                target_collection=collection,
                target_id=target_id,
                kind=kind,
                patch=patch,
                current_values=current_values,
                expected_version=expected_version,
                rationale=rationale,
                proposer=user,
                proposer_username=str(user.username)[:150],
                proposer_kind=proposer_kind,
                proposed_via=via,
                model=model_name,
                prompt_version=prompt_version,
                confidence=confidence,
                fingerprint=fingerprint,
                batch_key=batch_key,
                expires_at=timezone.now() + timedelta(days=policy.proposal_expiry_days()),
                **evidence,
            )
            if kind == 'field_update':
                _supersede_older(proposal)
    except IntegrityError:
        replayed = _existing_outcome(fingerprint, user)
        if replayed is not None:
            return replayed, True
        raise
    return proposal, False


def _supersede_older(proposal):
    """An open field update for exactly the same fields of the same record is replaced."""
    keys = set(proposal.patch)
    older = ChangeProposal.objects.select_for_update().filter(
        status='proposed', kind='field_update', target_collection=proposal.target_collection,
        target_id=proposal.target_id,
    ).exclude(pk=proposal.pk)
    for row in older:
        if set(row.patch or {}) == keys:
            row.status = 'superseded'
            row.superseded_by = proposal
            row.save(update_fields=['status', 'superseded_by', 'updated_at'])


# ------------------------------------------------------------------ decisions


class _Refusal(Exception):
    """An apply that was refused; the proposal's own state change is kept."""

    def __init__(self, error):
        super().__init__(error.detail)
        self.error = error


def _require_reviewer(request):
    if not policy.proposals_enabled():
        raise _not_enabled()
    refusal = policy.review_refusal(request)
    if refusal:
        raise ServiceError(403, 'human_review_required', refusal)


def _as_reviewer(request, call):
    """Run a crm_app.mcp write tool with the reviewer as the authenticated caller."""
    from mcp_server.djangomcp import django_request_ctx

    token = django_request_ctx.set(request)
    try:
        return call()
    finally:
        django_request_ctx.reset(token)


def _tool_outcome(text):
    """('ok', data) | ('invalid', errors) | ('changed', msg) | ('error', msg) from a write tool's reply."""
    if text.startswith('Validation errors:'):
        try:
            return 'invalid', json.loads(text[len('Validation errors:'):])
        except ValueError:
            return 'invalid', text
    if text.startswith('Error:'):
        return 'error', text[len('Error:'):].strip()
    try:
        data = json.loads(text)
    except ValueError:
        return 'error', text
    if not isinstance(data, dict):
        return 'error', text
    error = data.get('error')
    if data.get('updated') is True or (data.get('id') and not error and data.get('created', True) is not False):
        return 'ok', data
    error = str(error or 'the write tool refused the change')
    if 'Stale expected_version' in error or 'Expected values no longer match' in error:
        return 'changed', error
    return 'error', error


def _final_patch(proposal, body, with_edits):
    applied = dict(proposal.patch)
    if not with_edits:
        return applied
    edits = body.get('edits') or {}
    drop = body.get('drop_fields') or []
    if not isinstance(edits, dict) or not isinstance(drop, list) or not all(isinstance(k, str) for k in drop):
        raise bad('edits must be an object and drop_fields a list of field names')
    if not edits and not drop:
        raise bad('accept-with-edits needs edits or drop_fields')
    outside = sorted((set(edits) | set(drop)) - set(proposal.patch))
    if outside:
        raise unprocessable('edit_not_allowed', 'Edits may change or drop only fields in the proposal: '
                            + ', '.join(outside))
    for key in drop:
        applied.pop(key, None)
    for key, value in edits.items():
        applied[key] = _clean_value(key, value)
    required = policy.PROPOSAL_REQUIRED_FIELDS.get(proposal.kind, frozenset())
    if not applied or any(not applied.get(key) for key in required):
        raise bad('Nothing applicable is left after the edits')
    if proposal.kind == 'note' and not applied.get('notes'):
        raise bad('The note text cannot be empty')
    return applied


def _mark_decided(proposal, request, note):
    proposal.reviewer = request.user
    proposal.reviewer_username = str(request.user.username)[:150]
    proposal.reviewed_at = timezone.now()
    proposal.decision_note = note


def _tag_audit(model_name, record_id, before_ids, proposal, request):
    from crm_app.models import AuditLog

    rows = list(AuditLog.objects.filter(model_name=model_name, record_id=str(record_id))
                .exclude(pk__in=before_ids))
    if len(rows) != 1:
        raise RuntimeError(f'expected one audit row for the applied proposal, found {len(rows)}')
    row = rows[0]
    row.additional_data = {
        **(row.additional_data or {}),
        'change_proposal_id': str(proposal.pk),
        'change_proposal_kind': proposal.kind,
        'change_proposal_proposer': proposal.proposer_username,
        'applied_via': 'change_proposal',
    }
    row.save(update_fields=['additional_data'])
    return row


def _record_changed(proposal, serializer_class, current):
    proposal.current_values = {key: current.get(key) for key in proposal.patch}
    proposal.expected_version = str(current.get('updated_at') or '')
    proposal.target_changed_at = timezone.now()
    proposal.last_apply_error = RECORD_CHANGED_DETAIL[:APPLY_ERROR_MAX]
    if proposal.kind == 'field_update' and all(
        _same(serializer_class, key, current.get(key), value) for key, value in proposal.patch.items()
    ):
        proposal.status = 'superseded'
        proposal.last_apply_error = 'The record already has the proposed values.'
    proposal.save()
    return ServiceError(
        409, 'record_changed', RECORD_CHANGED_DETAIL, status=proposal.status,
        current_values=proposal.current_values, expected_version=proposal.expected_version,
    )


def _apply(request, proposal, applied):
    """Apply ``applied`` to the target as the reviewer. Returns the write tool's data or raises _Refusal."""
    from crm_app.mcp import create_record, update_record
    from crm_app.models import AuditLog

    model, serializer_class = _collection(proposal.target_collection)
    if proposal.kind in policy.UPDATE_KINDS:
        instance = model.objects.select_for_update().filter(pk=proposal.target_id).first()
        if instance is None:
            proposal.status = 'failed'
            proposal.last_apply_error = 'The target record no longer exists.'
            proposal.save()
            raise _Refusal(ServiceError(409, 'target_missing', proposal.last_apply_error))
        current = _plain(serializer_class(instance).data)
        changed = not _same_version(current.get('updated_at'), proposal.expected_version) or any(
            not _same(serializer_class, key, current.get(key), proposal.current_values.get(key))
            for key in proposal.patch
        )
        if changed:
            raise _Refusal(_record_changed(proposal, serializer_class, current))
        if proposal.kind == 'note':
            data = {'notes': _join_notes(proposal.current_values.get('notes'), applied['notes'])}
        else:
            data = applied
        expected = {key: proposal.current_values.get(key) for key in data}
        record_id = proposal.target_id
        before = set(AuditLog.objects.filter(model_name=model.__name__, record_id=record_id)
                     .values_list('pk', flat=True))
        reply = _as_reviewer(request, lambda: update_record(
            proposal.target_collection, record_id, json.dumps(data),
            expected_version=proposal.expected_version, expected_values=json.dumps(expected),
        ))
    else:
        before = set()
        data = {'company': str(proposal.company_id), **applied}
        reply = _as_reviewer(request, lambda: create_record(proposal.target_collection, json.dumps(data)))
        record_id = None

    outcome, detail = _tool_outcome(reply)
    if outcome == 'changed':
        instance = model.objects.get(pk=proposal.target_id)
        raise _Refusal(_record_changed(proposal, serializer_class, _plain(serializer_class(instance).data)))
    if outcome == 'invalid':
        proposal.last_apply_error = json.dumps(detail, default=str)[:APPLY_ERROR_MAX]
        proposal.save()
        raise _Refusal(unprocessable(
            'invalid_value', 'The record refused the values; edit or reject the proposal', errors=_plain(detail),
        ))
    if outcome == 'error':
        proposal.status = 'failed'
        proposal.last_apply_error = str(detail)[:APPLY_ERROR_MAX]
        proposal.save()
        raise _Refusal(unprocessable('apply_refused', proposal.last_apply_error))
    record_id = record_id or str(detail['id'])
    audit = _tag_audit(model.__name__, record_id, before, proposal, request)
    return record_id, audit, detail


def accept(request, proposal_id, body, *, with_edits=False):
    """Accept a proposal (optionally with edits) and apply it. Returns (proposal, tool_reply)."""
    _require_reviewer(request)
    allowed = {'note', 'edits', 'drop_fields'} if with_edits else {'note'}
    strict_object(body, allowed)
    note = text_field(body, 'note', DECISION_NOTE_MAX, multiline=True)
    refused = None
    with transaction.atomic():
        proposal = ChangeProposal.objects.select_for_update().filter(pk=proposal_id).first()
        if proposal is None:
            raise ServiceError(404, 'not_found', 'Proposal not found')
        if proposal.status != 'proposed':
            raise ServiceError(409, 'not_open', f'Proposal is {proposal.status}', status=proposal.status)
        try:
            if proposal.expires_at <= timezone.now():
                proposal.status = 'expired'
                proposal.save()
                raise _Refusal(ServiceError(409, 'expired', 'Proposal has expired', status='expired'))
            applied = _final_patch(proposal, body, with_edits)
            # The allowlist is checked again: it may have narrowed since the proposal was made.
            _check_fields(proposal.kind, proposal.target_collection, applied)
            record_id, audit, reply = _apply(request, proposal, applied)
        except _Refusal as refusal:
            # The proposal's own bookkeeping (expired, failed, refreshed values) is
            # committed; the target record was not written.
            refused = refusal.error
        else:
            proposal.status = 'edited' if applied != proposal.patch else 'accepted'
            proposal.applied_patch = applied
            proposal.applied_record_id = str(record_id)
            proposal.applied_audit_id = audit.pk
            proposal.last_apply_error = ''
            _mark_decided(proposal, request, note)
            proposal.save()
    if refused is not None:
        raise refused
    return proposal, reply


def reject(request, proposal_id, body):
    _require_reviewer(request)
    strict_object(body, {'reason'}, required=('reason',))
    reason = text_field(body, 'reason', DECISION_NOTE_MAX, required=True, multiline=True)
    with transaction.atomic():
        proposal = ChangeProposal.objects.select_for_update().filter(pk=proposal_id).first()
        if proposal is None:
            raise ServiceError(404, 'not_found', 'Proposal not found')
        if proposal.status != 'proposed':
            raise ServiceError(409, 'not_open', f'Proposal is {proposal.status}', status=proposal.status)
        proposal.status = 'rejected'
        _mark_decided(proposal, request, reason)
        proposal.save()
    return proposal


def bulk_reject(request, body):
    """Reject open proposals by id list or batch_key. Others are reported, not changed."""
    _require_reviewer(request)
    strict_object(body, {'ids', 'batch_key', 'reason'}, required=('reason',))
    reason = text_field(body, 'reason', DECISION_NOTE_MAX, required=True, multiline=True)
    ids, batch_key = body.get('ids'), batch_field(body)
    if bool(ids) == bool(batch_key):
        raise bad('Give either ids or batch_key')
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > BULK_REJECT_MAX:
            raise bad(f'ids must be a list of at most {BULK_REJECT_MAX} proposal ids')
        ids = [uuid_value(value, 'ids[]') for value in ids]
    with transaction.atomic():
        rows = ChangeProposal.objects.select_for_update()
        rows = list(rows.filter(pk__in=ids) if ids is not None else rows.filter(batch_key=batch_key))
        if len(rows) > BULK_REJECT_MAX:
            raise bad(f'More than {BULK_REJECT_MAX} proposals match; narrow the selection')
        rejected, skipped = [], []
        for proposal in rows:
            if proposal.status != 'proposed':
                skipped.append({'id': str(proposal.pk), 'status': proposal.status})
                continue
            proposal.status = 'rejected'
            _mark_decided(proposal, request, reason)
            proposal.save()
            rejected.append(str(proposal.pk))
    found = {str(row.pk) for row in rows}
    not_found = sorted(str(value) for value in (ids or []) if str(value) not in found)
    return {'rejected': rejected, 'skipped': skipped, 'not_found': not_found}

