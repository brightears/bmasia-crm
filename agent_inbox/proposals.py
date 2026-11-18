"""Change proposals: storing them, and a person's decision on them.

Storing a proposal never changes the target record. Accepting one applies it
through the guarded MCP write path (``crm_app.mcp.update_record`` with
``expected_version`` and ``expected_values``, or ``create_record`` for a new
contact or task), run as the reviewer, inside one transaction with the
proposal's own update. The AuditLog row that path writes is tagged with the
proposal id. A refused or failed apply writes nothing to the target.

Rules a reviewer of this module should know:

- A reviewer is a person signed in to the website who did not make the
  proposal and did not record its evidence (``policy.review_refusal``).
- Every decision carries the ``seen_version`` the API returned with the
  proposal. If the proposal changed since (for example its current values were
  re-read after the record changed), the decision is refused with the fresh
  snapshot and nothing is applied.
- A contact created from a proposal gets every ``receives_*`` email flag off
  and is never primary. A proposal may not change the email of a contact that
  receives invoices or payment emails, is the billing contact or is primary.
- A newer proposal replaces an older open one only when both come from the
  same proposer and the newer one's evidence is not older. Proposals from
  different proposers for the same fields stay open side by side and are
  reported as conflicting.
- An agent account may link only an activity it recorded itself. Any other
  activity gets the same refusal, whatever the quote. Refused attempts count
  towards the proposer's daily cap.
- Only one open proposal per fingerprint. An agent may not raise a decided
  fingerprint again; a person may, and a person may reopen a rejected one.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from agent_inbox import policy
from agent_inbox.models import (
    APPLY_ERROR_MAX, DECIDED_STATUSES, DECISION_NOTE_MAX, EVIDENCE_QUOTE_MAX, MODEL_NAME_MAX, OPEN_STATUS,
    PATCH_VALUE_MAX, PROPOSER_KIND_CHOICES, RATIONALE_MAX, SOURCE_REF_MAX, SOURCE_SYSTEM_CHOICES,
    SOURCE_URL_MAX, Activity, ChangeProposal, ProposalRefusal,
)
from agent_inbox.validation import (
    ServiceError, bad, batch_field, choice, has_control, optional_uuid, past_datetime, payload_sha256,
    quote_occurs_in, source_ref_field, strict_object, text_field, unprocessable, url_field, uuid_value,
)

PROPOSAL_KEYS = frozenset({
    'kind', 'target_collection', 'target_id', 'company_id', 'patch',
    'evidence_quote', 'evidence_source_system', 'evidence_source_ref', 'evidence_source_url',
    'evidence_occurred_at', 'activity_id', 'rationale', 'proposer_kind', 'model', 'prompt_version',
    'confidence', 'batch_key',
})
MULTILINE_FIELDS = frozenset({'notes', 'description'})
BULK_REJECT_MAX = 200
# Contact flags that make a contact a recipient of invoices, receipts or payment emails.
BILLING_RECIPIENT_FLAGS = ('receives_invoice_emails', 'receives_payment_emails')
PERSON_ONLY_EMAIL_DETAIL = (
    'This contact receives invoices or payment emails, or is the billing or primary contact. '
    'A change to its email must be made by a person on the contact page.'
)
RECORD_CHANGED_DETAIL = (
    'The record changed after this proposal was made. Nothing was applied; the current values '
    'were re-read. Review them and accept again if the change is still right.'
)
STALE_VIEW_DETAIL = (
    'This proposal changed since it was loaded. Nothing was done; reload it and decide again.'
)
ACTIVITY_NOT_USABLE_DETAIL = (
    'activity_id must be a live activity of this company whose body you may read: one you recorded, '
    'or one recorded by a capture job or a person and not restricted'
)
# Refusals recorded so they count towards the daily cap.
COUNTED_REFUSAL_STATUSES = frozenset({400, 403, 404, 409, 422})


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


def _iso(value):
    return value.isoformat() if value else None


def expire_due():
    """Mark open proposals past their expiry as expired. Returns the number changed."""
    now = timezone.now()
    return ChangeProposal.objects.filter(status=OPEN_STATUS, expires_at__lte=now).update(
        status='expired', updated_at=now,
    )


# ------------------------------------------------------------------ what the reviewer saw


def seen_version(proposal):
    """Digest of everything a decision is about. Changes whenever any of it changes."""
    return payload_sha256({
        'id': str(proposal.pk), 'status': proposal.status, 'kind': proposal.kind,
        'target': [proposal.target_collection, proposal.target_id], 'patch': proposal.patch,
        'current_values': proposal.current_values, 'expected_version': proposal.expected_version,
        'target_changed_at': _iso(proposal.target_changed_at),
        # Every decision and reopening adds a history entry, so a view loaded
        # before a rejection and reopening no longer matches.
        'decisions': len(proposal.history or []),
    })[:40]


def snapshot(proposal):
    return {
        'id': str(proposal.pk), 'seen_version': seen_version(proposal), 'status': proposal.status,
        'patch': proposal.patch, 'current_values': proposal.current_values,
        'expected_version': proposal.expected_version, 'target_changed_at': _iso(proposal.target_changed_at),
    }


def _check_seen(proposal, body):
    if body.get('seen_version') != seen_version(proposal):
        raise ServiceError(409, 'stale_view', STALE_VIEW_DETAIL, proposal=_plain(snapshot(proposal)))


def _history(proposal, action, request, note):
    proposal.history = [*(proposal.history or []), {
        'action': action, 'by': str(request.user.username)[:150], 'at': timezone.now().isoformat(),
        'note': note,
    }]


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
        raise bad(f'patch.{key} contains control or invisible characters')
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


def _check_task_relations(company_id, patch):
    from crm_app.models import Contact, Contract, Opportunity

    for key, model in (('related_contact', Contact), ('related_contract', Contract),
                       ('related_opportunity', Opportunity)):
        value = patch.get(key)
        if not value:
            continue
        pk = uuid_value(value, f'patch.{key}')
        obj = model.objects.filter(pk=pk).only('pk', 'company_id').first()
        if obj is None or obj.company_id != company_id:
            raise unprocessable('wrong_company', f'patch.{key} is not a record of this company')


def _check_billing_email(contact, keys):
    """Refuse an email change on a contact that receives billing documents."""
    if 'email' not in keys:
        return
    if (any(getattr(contact, flag, False) for flag in BILLING_RECIPIENT_FLAGS)
            or contact.is_primary or contact.contact_type == 'Billing'):
        raise unprocessable('person_only_change', PERSON_ONLY_EMAIL_DETAIL)


_PHONE_PUNCTUATION = re.compile(r'[\s().\-/]')


def _fingerprint_value(key, value):
    """The value as compared for duplicates: spacing, and case where it carries no meaning, ignored."""
    if not isinstance(value, str):
        return value
    text = ' '.join(value.split())
    if key == 'email':
        return text.casefold()
    if key in ('phone', 'mobile'):
        return _PHONE_PUNCTUATION.sub('', text)
    if key in ('website', 'linkedin_url'):
        scheme, sep, rest = text.partition('://')
        host, slash, path = rest.partition('/')
        return (f'{scheme.casefold()}{sep}{host.casefold()}{slash}{path}' if sep else text.casefold()).rstrip('/')
    return text


def _fingerprint(kind, collection, target_id, company_id, patch):
    patch = {key: _fingerprint_value(key, value) for key, value in patch.items()}
    if kind == 'new_contact':
        basis = {'kind': kind, 'company': str(company_id), 'email': patch.get('email') or ''}
    elif kind == 'note':
        basis = {'kind': kind, 'collection': collection, 'target': target_id, 'text': patch['notes']}
    elif kind == 'task':
        basis = {'kind': kind, 'company': str(company_id), 'patch': patch}
    else:
        basis = {'kind': kind, 'collection': collection, 'target': target_id, 'patch': patch}
    return payload_sha256({'v': 2, **basis})


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


def _linked_activity(body, user, company):
    activity_id = optional_uuid(body, 'activity_id')
    if not activity_id:
        return None
    activity = Activity.objects.select_related('recorded_by').filter(pk=activity_id).first()
    if policy.is_agent_account(user):
        # One answer for every activity an agent cannot use, so nothing about
        # other recorders' activities can be learned from the reply.
        if (activity is None or activity.is_void or activity.company_id != company.pk
                or not policy.can_read_activity_body(user, activity)):
            raise unprocessable('activity_not_usable', ACTIVITY_NOT_USABLE_DETAIL)
        return activity
    if activity is None:
        raise unprocessable('unknown_record', 'activity_id does not exist')
    if activity.is_void:
        raise unprocessable('activity_void', 'activity_id refers to a voided activity')
    if activity.company_id != company.pk:
        raise unprocessable('wrong_company', 'activity_id belongs to another company')
    return activity


def _evidence(body, user, proposer_kind, company):
    quote = text_field(body, 'evidence_quote', EVIDENCE_QUOTE_MAX, multiline=True, allow_format=True)
    if proposer_kind in policy.EVIDENCE_REQUIRED_KINDS and not quote:
        raise unprocessable(
            'evidence_required',
            'evidence_quote is required: copy the exact words from the source that support the change',
        )
    activity = _linked_activity(body, user, company)
    systems = [value for value, _ in SOURCE_SYSTEM_CHOICES]
    if activity is not None:
        # The evidence source is the activity's; a different one is refused.
        given = {
            'evidence_source_system': (body.get('evidence_source_system'), activity.source_system),
            'evidence_source_ref': (
                source_ref_field(body, 'evidence_source_ref', activity.source_system, SOURCE_REF_MAX),
                activity.source_ref,
            ),
            'evidence_source_url': (body.get('evidence_source_url'), activity.source_url),
        }
        for key, (value, actual) in given.items():
            if value not in (None, '') and value != actual:
                raise unprocessable('evidence_source_mismatch', f'{key} must match the linked activity')
        if body.get('evidence_occurred_at') not in (None, ''):
            stated = past_datetime(body['evidence_occurred_at'], 'evidence_occurred_at')
            if stated != activity.occurred_at:
                raise unprocessable('evidence_source_mismatch', 'evidence_occurred_at must match the linked activity')
        system, ref, url = activity.source_system, activity.source_ref, activity.source_url
        occurred_at = activity.occurred_at
    else:
        system = body.get('evidence_source_system') or ''
        if system not in [''] + systems:
            raise bad('evidence_source_system must be one of: ' + ', '.join(systems))
        ref = source_ref_field(body, 'evidence_source_ref', system, SOURCE_REF_MAX)
        from agent_inbox.redaction import is_redacted_source
        if ref and is_redacted_source(ref):
            raise ServiceError(409, 'source_redacted',
                               'This source was removed under the mail-capture rules and cannot be cited')
        url = url_field(body, 'evidence_source_url', SOURCE_URL_MAX)
        occurred_at = (past_datetime(body['evidence_occurred_at'], 'evidence_occurred_at')
                       if body.get('evidence_occurred_at') not in (None, '') else None)
    verified = False
    if activity is not None and activity.body and quote:
        if not quote_occurs_in(quote, activity.body):
            raise unprocessable(
                'quote_not_verbatim', 'evidence_quote does not occur verbatim in the referenced activity body',
            )
        verified = True
    return {
        'evidence_quote': quote,
        'evidence_verified': verified,
        'evidence_source_system': system,
        'evidence_source_ref': ref,
        'evidence_source_url': url,
        'evidence_occurred_at': occurred_at,
        'evidence_recorder_is_agent': bool(
            activity is not None and activity.recorded_by is not None
            and policy.is_agent_account(activity.recorded_by)
        ),
        'activity': activity,
    }


def _proposer_kind(body, is_agent):
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


def _existing_outcome(fingerprint, user, is_agent):
    """The caller's own open proposal (a replay), or None; raises for a duplicate."""
    open_row = ChangeProposal.objects.filter(fingerprint=fingerprint, status=OPEN_STATUS).first()
    if open_row is not None:
        if open_row.proposer_id == user.pk:
            return open_row
        extra = {} if is_agent else {'existing_proposal_id': str(open_row.pk)}
        raise ServiceError(409, 'duplicate_open', 'The same change is already waiting for review', **extra)
    if not is_agent:
        return None  # a person may raise a decided change again
    decided = (ChangeProposal.objects.filter(fingerprint=fingerprint, status__in=DECIDED_STATUSES)
               .order_by('-updated_at').first())
    if decided is None:
        return None
    if decided.status == 'rejected':
        raise ServiceError(409, 'previously_rejected',
                           'The same change was rejected before and is not raised again by an agent')
    raise ServiceError(409, 'already_applied', 'The same change was already accepted')


def _check_cap(user):
    since = timezone.now() - timedelta(hours=24)
    cap = policy.proposal_daily_cap()
    used = (ChangeProposal.objects.filter(proposer=user, created_at__gte=since).count()
            + ProposalRefusal.objects.filter(proposer=user, created_at__gte=since).count())
    if used >= cap:
        raise ServiceError(429, 'daily_cap', f'Daily proposal cap of {cap} reached for this proposer '
                                            '(refused attempts count too)')


def create_proposal(user, body, *, via):
    """Store one proposal. Returns (proposal, replayed). Raises ServiceError."""
    if not policy.proposals_enabled():
        raise _not_enabled()
    if user is None or not getattr(user, 'is_authenticated', False):
        raise ServiceError(401, 'not_authenticated', 'Authentication required')
    _check_cap(user)
    try:
        return _create(user, body, via)
    except ServiceError as exc:
        if exc.status in COUNTED_REFUSAL_STATUSES:
            ProposalRefusal.objects.create(proposer=user, code=str(exc.code)[:40])
        raise


def _create(user, body, via):
    strict_object(body, PROPOSAL_KEYS, required=('kind', 'patch'))
    expire_due()
    kind = body.get('kind')
    if kind not in policy.APPLICABLE_KINDS:
        raise unprocessable(
            'kind_not_allowed',
            f'kind must be one of: {", ".join(sorted(policy.APPLICABLE_KINDS))} (link and other are not enabled)',
        )
    is_agent = policy.is_agent_account(user)
    proposer_kind = _proposer_kind(body, is_agent)
    collection, target_id, instance, company = _resolve_target(body, kind)
    patch = _clean_patch(kind, collection, body.get('patch'))
    # Evidence comes before any comparison with the record, so a refusal about
    # the evidence never depends on the record's values.
    evidence = _evidence(body, user, proposer_kind, company)
    rationale = text_field(body, 'rationale', RATIONALE_MAX, multiline=True)
    model_name = text_field(body, 'model', MODEL_NAME_MAX)
    prompt_version = text_field(body, 'prompt_version', MODEL_NAME_MAX)
    confidence = _confidence(body)
    batch_key = batch_field(body)

    _, serializer_class = _collection(collection)
    current_values, expected_version = {}, ''
    if instance is not None:
        if collection == 'contact':
            _check_billing_email(instance, patch)
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
            _check_task_relations(company.pk, patch)
        _serializer_check(serializer_class(data={'company': str(company.pk), **patch}))

    fingerprint = _fingerprint(kind, collection, target_id, company.pk, patch)
    replayed = _existing_outcome(fingerprint, user, is_agent)
    if replayed is not None:
        return replayed, True

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
        replayed = _existing_outcome(fingerprint, user, is_agent)
        if replayed is not None:
            return replayed, True
        raise
    return proposal, False


def _not_older(new, old):
    """Whether evidence dated ``new`` may replace evidence dated ``old`` (unknown never replaces known)."""
    if new is None and old is None:
        return True
    if new is None or old is None:
        return False
    return new >= old


def _supersede_older(proposal):
    """The proposer's own open field update for exactly the same fields is replaced, unless its evidence is newer."""
    keys = set(proposal.patch)
    older = ChangeProposal.objects.select_for_update().filter(
        status=OPEN_STATUS, kind='field_update', target_collection=proposal.target_collection,
        target_id=proposal.target_id, proposer=proposal.proposer,
    ).exclude(pk=proposal.pk)
    for row in older:
        if set(row.patch or {}) == keys and _not_older(proposal.evidence_occurred_at, row.evidence_occurred_at):
            row.status = 'superseded'
            row.superseded_by = proposal
            row.save(update_fields=['status', 'superseded_by', 'updated_at'])


def refresh_snapshots(proposals):
    """Re-read the target's values for open update proposals whose target changed since.

    Reads only each target's version (one query per collection). A proposal is
    written only when its target's version differs from the stored one, and then
    with a conditional update, so concurrent reads cannot overwrite each other or
    a decision in progress. Its seen_version changes with it.
    """
    rows = [p for p in proposals if p.status == OPEN_STATUS and p.kind in policy.UPDATE_KINDS and p.target_id]
    by_collection = {}
    for proposal in rows:
        by_collection.setdefault(proposal.target_collection, []).append(proposal)
    for collection, group in by_collection.items():
        model, serializer_class = _collection(collection)
        versions = dict(model.objects.filter(pk__in={p.target_id for p in group}).values_list('pk', 'updated_at'))
        for proposal in group:
            version = versions.get(_uuid_or_none(proposal.target_id))
            if version is None or _same_version(version.isoformat(), proposal.expected_version):
                continue
            instance = model.objects.filter(pk=proposal.target_id).first()
            if instance is None:
                continue
            current = _plain(serializer_class(instance).data)
            values = {key: current.get(key) for key in proposal.patch}
            new_version = str(current.get('updated_at') or '')
            now = timezone.now()
            updated = ChangeProposal.objects.filter(
                pk=proposal.pk, status=OPEN_STATUS, expected_version=proposal.expected_version,
            ).update(current_values=values, expected_version=new_version, target_changed_at=now, updated_at=now)
            if updated:
                proposal.current_values, proposal.expected_version = values, new_version
                proposal.target_changed_at = proposal.updated_at = now


def _uuid_or_none(value):
    from uuid import UUID
    try:
        return UUID(str(value))
    except ValueError:
        return None


def conflicts_for(proposals):
    """For each open field update: the other open field updates of the same record that share a field."""
    rows = [p for p in proposals if p.status == OPEN_STATUS and p.kind == 'field_update' and p.target_id]
    if not rows:
        return {}
    targets = {(p.target_collection, p.target_id) for p in rows}
    candidates = ChangeProposal.objects.filter(
        status=OPEN_STATUS, kind='field_update', target_id__in={t[1] for t in targets},
    ).only('id', 'target_collection', 'target_id', 'patch', 'proposer_id', 'proposer_username',
           'evidence_occurred_at', 'created_at')
    result = {}
    for p in rows:
        keys = set(p.patch or {})
        result[p.pk] = [
            other for other in candidates
            if other.pk != p.pk and (other.target_collection, other.target_id) == (p.target_collection, p.target_id)
            and keys & set(other.patch or {})
        ]
    return result


# ------------------------------------------------------------------ decisions


class _Refusal(Exception):
    """An apply that was refused; the proposal's own state change is kept."""

    def __init__(self, error):
        super().__init__(error.detail)
        self.error = error


def _require_person(request, proposal=None):
    if not policy.proposals_enabled():
        raise _not_enabled()
    refusal = policy.review_refusal(request, proposal)
    if refusal:
        if refusal == policy.NOT_CONFIGURED_DETAIL:
            code = 'review_not_configured'
        elif refusal == policy.NOT_LISTED_DETAIL:
            code = 'not_a_reviewer'
        elif proposal is not None and policy.review_refusal(request) is None:
            code = 'reviewer_is_party'
        else:
            code = 'human_review_required'
        raise ServiceError(403, code, refusal)


def _locked(proposal_id):
    proposal = ChangeProposal.objects.select_for_update().filter(pk=proposal_id).first()
    if proposal is None:
        raise ServiceError(404, 'not_found', 'Proposal not found')
    return proposal


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
        'via': 'change_proposal',
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
    return ServiceError(409, 'record_changed', RECORD_CHANGED_DETAIL, proposal=_plain(snapshot(proposal)))


def _keep_error(proposal, error):
    proposal.last_apply_error = str(error.detail)[:APPLY_ERROR_MAX]
    proposal.save()
    return _Refusal(error)


def _new_contact_data(company_id, applied):
    """A contact created from a proposal receives no automated or document email and is not primary."""
    from crm_app.serializers import ContactSerializer

    flags = {name: False for name, field in ContactSerializer().fields.items()
             if name.startswith('receives_') and not field.read_only}
    return {'company': str(company_id), **applied, **flags, 'is_primary': False}


def _apply(request, proposal, applied):
    """Apply ``applied`` to the target as the reviewer. Returns the write tool's data or raises _Refusal."""
    from crm_app.mcp import create_record, update_record
    from crm_app.models import AuditLog, Contact

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
        if proposal.target_collection == 'contact':
            try:
                _check_billing_email(instance, applied)
            except ServiceError as error:
                raise _keep_error(proposal, error) from None
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
        if proposal.kind == 'task':
            try:
                _check_task_relations(proposal.company_id, applied)
            except ServiceError as error:
                raise _keep_error(proposal, error) from None
        before = set()
        if proposal.kind == 'new_contact':
            data = _new_contact_data(proposal.company_id, applied)
        else:
            data = {'company': str(proposal.company_id), **applied}
        reply = _as_reviewer(request, lambda: create_record(proposal.target_collection, json.dumps(data)))
        record_id = None

    outcome, detail = _tool_outcome(reply)
    if outcome == 'changed':
        instance = model.objects.get(pk=proposal.target_id)
        raise _Refusal(_record_changed(proposal, serializer_class, _plain(serializer_class(instance).data)))
    if outcome == 'invalid':
        raise _keep_error(proposal, unprocessable(
            'invalid_value', 'The record refused the values; edit or reject the proposal', errors=_plain(detail),
        ))
    if outcome == 'error':
        proposal.status = 'failed'
        proposal.last_apply_error = str(detail)[:APPLY_ERROR_MAX]
        proposal.save()
        raise _Refusal(unprocessable('apply_refused', proposal.last_apply_error))
    record_id = record_id or str(detail['id'])
    if proposal.kind == 'new_contact':
        # Model fields the serializer does not expose follow the same rule.
        flags = {field.name: False for field in Contact._meta.concrete_fields if field.name.startswith('receives_')}
        Contact.objects.filter(pk=record_id).update(**flags, is_primary=False)
    audit = _tag_audit(model.__name__, record_id, before, proposal, request)
    return record_id, audit, detail


def accept(request, proposal_id, body, *, with_edits=False):
    """Accept a proposal (optionally with edits) and apply it. Returns (proposal, tool_reply)."""
    _require_person(request)
    allowed = {'note', 'seen_version', 'edits', 'drop_fields'} if with_edits else {'note', 'seen_version'}
    strict_object(body, allowed, required=('seen_version',))
    note = text_field(body, 'note', DECISION_NOTE_MAX, multiline=True)
    refused = None
    with transaction.atomic():
        proposal = _locked(proposal_id)
        if proposal.status != OPEN_STATUS:
            raise ServiceError(409, 'not_open', f'Proposal is {proposal.status}', status=proposal.status)
        _require_person(request, proposal)
        _check_seen(proposal, body)
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
            _history(proposal, proposal.status, request, note)
            proposal.save()
    if refused is not None:
        raise refused
    return proposal, reply


def reject(request, proposal_id, body):
    _require_person(request)
    strict_object(body, {'reason', 'seen_version'}, required=('reason', 'seen_version'))
    reason = text_field(body, 'reason', DECISION_NOTE_MAX, required=True, multiline=True)
    with transaction.atomic():
        proposal = _locked(proposal_id)
        if proposal.status != OPEN_STATUS:
            raise ServiceError(409, 'not_open', f'Proposal is {proposal.status}', status=proposal.status)
        _require_person(request, proposal)
        _check_seen(proposal, body)
        proposal.status = 'rejected'
        _mark_decided(proposal, request, reason)
        _history(proposal, 'rejected', request, reason)
        proposal.save()
    return proposal


def reopen(request, proposal_id, body):
    """A person reopens a rejected proposal, with a note."""
    _require_person(request)
    strict_object(body, {'note', 'seen_version'}, required=('note', 'seen_version'))
    note = text_field(body, 'note', DECISION_NOTE_MAX, required=True, multiline=True)
    with transaction.atomic():
        proposal = _locked(proposal_id)
        if proposal.status != 'rejected':
            raise ServiceError(409, 'not_rejected', f'Only a rejected proposal can be reopened; this one is '
                                                    f'{proposal.status}', status=proposal.status)
        _require_person(request, proposal)
        _check_seen(proposal, body)
        if ChangeProposal.objects.filter(fingerprint=proposal.fingerprint, status=OPEN_STATUS).exists():
            raise ServiceError(409, 'duplicate_open', 'The same change is already waiting for review')
        _history(proposal, 'reopened', request, note)
        proposal.status = OPEN_STATUS
        proposal.reviewer = None
        proposal.reviewer_username = ''
        proposal.reviewed_at = None
        proposal.decision_note = ''
        proposal.expires_at = timezone.now() + timedelta(days=policy.proposal_expiry_days())
        proposal.save()
    return proposal


def bulk_reject(request, body):
    """Reject open proposals, each named with the seen_version the reviewer saw."""
    _require_person(request)
    strict_object(body, {'items', 'reason'}, required=('items', 'reason'))
    reason = text_field(body, 'reason', DECISION_NOTE_MAX, required=True, multiline=True)
    items = body.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= BULK_REJECT_MAX:
        raise bad(f'items must be a list of 1-{BULK_REJECT_MAX} {{id, seen_version}} objects')
    wanted = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {'id', 'seen_version'}:
            raise bad('each item must be {id, seen_version}')
        wanted[str(uuid_value(item['id'], 'items[].id'))] = item['seen_version']
    rejected, skipped = [], []
    with transaction.atomic():
        rows = {str(row.pk): row for row in ChangeProposal.objects.select_for_update().filter(pk__in=list(wanted))}
        for proposal_id, seen in wanted.items():
            proposal = rows.get(proposal_id)
            if proposal is None:
                continue
            if proposal.status != OPEN_STATUS:
                skipped.append({'id': proposal_id, 'status': proposal.status, 'code': 'not_open'})
                continue
            if policy.review_refusal(request, proposal):
                skipped.append({'id': proposal_id, 'status': proposal.status, 'code': 'reviewer_is_party'})
                continue
            if seen != seen_version(proposal):
                skipped.append({'id': proposal_id, 'status': proposal.status, 'code': 'stale_view',
                                'seen_version': seen_version(proposal)})
                continue
            proposal.status = 'rejected'
            _mark_decided(proposal, request, reason)
            _history(proposal, 'rejected', request, reason)
            proposal.save()
            rejected.append(proposal_id)
    not_found = sorted(proposal_id for proposal_id in wanted if proposal_id not in rows)
    return {'rejected': rejected, 'skipped': skipped, 'not_found': not_found}
