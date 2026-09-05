"""Strict CRM-side implementation of the Rene to Cira Phase-2 contract.

This module is intentionally not a general CRUD service.  It accepts only the
canonical ``bmasia.cira.rene.v1`` envelopes, requires human-reviewed policy
records, keeps durable payload-bound receipts, and provides four narrow
effects: prepare a review-only renewal, mark that prepared renewal Sent after
exact Gmail proof, and fill one null renewal date.  Inspection, validation,
verification, and receipt lookup are non-mutating.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from uuid import UUID

from django.db import IntegrityError, transaction
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone
from pypdf import PdfReader

from crm_app.models import (
    Contract,
    ContractLineItem,
    ContractServiceLocation,
    DocumentSequence,
    ReneCiraRequest,
    RenePreparedContract,
    ReneRenewalPolicy,
)
from crm_app.services.rene_phase2_common import (
    canonical_json,
    canonical_sha256,
    contract_version,
    rfc3339,
)


SCHEMA = 'bmasia.cira.rene.v1'
LOOKUP_SCHEMA = 'bmasia.cira.rene.receipt-lookup.v1'
TERMINAL_REJECTION_SCHEMA = 'bmasia.cira.rene.crm-terminal-rejection.v1'
BOUND_ERROR_SCHEMA = 'bmasia.cira.rene.crm-bound-error.v1'
UNBOUND_ERROR_SCHEMA = 'bmasia.cira.rene.crm-uncertain.v1'
AGENT = 'rene'
COLLECTION = 'contract'
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_SOURCE_CANDIDATES = 32
ALLOWED_OPERATIONS = {
    'inspect_renewal_source_candidates',
    'inspect_renewal_source',
    'validate_only',
    'prepare_renewal_contract',
    'verify_prepared_contract',
    'record_prepared_contract_sent',
    'fill_blank_renewal_date',
}
MUTATING_OPERATIONS = {
    'prepare_renewal_contract',
    'record_prepared_contract_sent',
    'fill_blank_renewal_date',
}
TOKEN_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,255}$')
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
FILENAME_RE = re.compile(r'^[^/\\\x00-\x1f\x7f]{1,128}\.pdf$', re.IGNORECASE)
MONEY_RE = re.compile(r'^(?:0|[1-9][0-9]{0,9})\.[0-9]{2}$')
MAX_CONTRACT_MONEY = Decimal('9999999999.99')
MAILBOX_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+$")
RFC_MESSAGE_ID_RE = re.compile(r'^<[^<>\s@]+@[^<>\s@]+>$')
UNRESOLVED_POLICY_ID_PARTS = frozenset(
    {'draft', 'pending', 'placeholder', 'temp', 'temporary', 'unknown', 'unresolved'}
)
FINAL_NUMBER_RULE = 'RESERVE_UNUSED_DOCUMENT_SEQUENCE_BEFORE_PDF'
POST_SEND_RULE = 'PREPARED_TO_SENT_SOURCE_UNCHANGED'
INSPECTION_RETURN_FIELDS = [
    'contract_id',
    'company_id',
    'version',
    'contract_updated_at',
    'evidence_revision',
    'document',
    'terms',
    'term_duration',
    'renewal_start_policy',
    'renewal_end_policy',
    'pricing_structure',
]
SOURCE_CANDIDATE_RETURN_FIELDS = [
    'contract_id',
    'company_id',
    'version',
    'contract_updated_at',
    'evidence_revision',
    'candidates',
]
NATIVE_SIGNED_SOURCE = 'unique_official_signed_document'
NIKKI_CONFIRMED_SOURCE = 'unique_nikki_confirmed_signed_document'


class RenePhase2Error(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class RenePhase2BoundError(RenePhase2Error):
    """A request-bound service result that callers must not replay."""

    def __init__(self, receipt):
        error = receipt.get('error') if isinstance(receipt, dict) else None
        code = error.get('code') if isinstance(error, dict) else 'BOUND_ERROR'
        message = error.get('message') if isinstance(error, dict) else 'request failed safely'
        super().__init__(code, message)
        self.receipt = receipt


def _fail(code, message):
    raise RenePhase2Error(code, message)


def _request_binding(envelope):
    return {
        'request_id': envelope['request_id'],
        'request_key': envelope['request_key'],
        'requesting_agent': AGENT,
        'operation': envelope['verb'],
        'intent_sha256': envelope['intent_sha256'],
    }


def _bound_error_receipt(
    envelope,
    code,
    message,
    *,
    outcome,
    boundary,
    crm_mcp_invoked,
    transaction_committed,
    effect_persisted,
    request_state,
    schema=BOUND_ERROR_SCHEMA,
):
    return {
        'schema': schema,
        **_request_binding(envelope),
        'outcome': outcome,
        'error': {'code': code, 'message': message},
        'effect': {
            'boundary': boundary,
            'crm_mcp_invoked': crm_mcp_invoked,
            'transaction_committed': transaction_committed,
            'effect_persisted': effect_persisted,
            'request_state': request_state,
        },
    }


def _raise_bound_error(envelope, code, message, **kwargs):
    raise RenePhase2BoundError(
        _bound_error_receipt(envelope, code, message, **kwargs)
    )


def _stored_terminal_rejection(record):
    """Return only a structurally exact terminal rollback receipt."""

    receipt = record.receipt
    if not isinstance(receipt, dict) or set(receipt) != {
        'schema', 'request_id', 'request_key', 'requesting_agent', 'operation',
        'intent_sha256', 'outcome', 'error', 'effect',
    }:
        return None
    error = receipt.get('error')
    effect = receipt.get('effect')
    if (
        receipt.get('schema') != TERMINAL_REJECTION_SCHEMA
        or receipt.get('request_id') != record.request_id
        or receipt.get('request_key') != record.request_key
        or receipt.get('requesting_agent') != AGENT
        or receipt.get('operation') != record.operation
        or receipt.get('intent_sha256') != record.intent_sha256
        or receipt.get('outcome') != 'rejected_terminal'
        or not isinstance(error, dict)
        or set(error) != {'code', 'message'}
        or error.get('code') != record.failure_code
        or not isinstance(error.get('message'), str)
        or not error['message']
        or not isinstance(effect, dict)
        or set(effect) != {
            'boundary', 'crm_mcp_invoked', 'transaction_committed',
            'effect_persisted', 'request_state',
        }
        or effect.get('boundary') != 'crm_atomic_rollback'
        or not isinstance(effect.get('crm_mcp_invoked'), bool)
        or effect.get('transaction_committed') is not False
        or effect.get('effect_persisted') is not False
        or effect.get('request_state') != 'failed'
    ):
        return None
    try:
        canonical_json(receipt)
    except (TypeError, ValueError):
        return None
    return receipt


def unbound_error(code, message, *, crm_mcp_invoked):
    """Return an explicit unknown-effect wrapper for an unbound MCP failure."""

    return {
        'schema': UNBOUND_ERROR_SCHEMA,
        'request_id': None,
        'request_key': None,
        'requesting_agent': AGENT,
        'operation': None,
        'intent_sha256': None,
        'outcome': 'uncertain',
        'error': {'code': code, 'message': message},
        'effect': {
            'boundary': 'crm_mcp_dispatch',
            'crm_mcp_invoked': crm_mcp_invoked,
            'transaction_committed': None,
            'effect_persisted': None,
            'request_state': 'unknown',
        },
    }


def _mapping(label, value):
    if not isinstance(value, dict) or not value or any(
        not isinstance(key, str) for key in value
    ):
        _fail('INVALID_SCHEMA', f'{label} must be one non-empty JSON object')
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        _fail('INVALID_SCHEMA', f'{label} must contain canonical JSON values')
    return value


def _exact(label, value, fields):
    raw = _mapping(label, value)
    if set(raw) != set(fields):
        _fail('INVALID_SCHEMA', f'{label} fields differ from the reviewed schema')
    return raw


def _token(label, value):
    if not isinstance(value, str) or TOKEN_RE.fullmatch(value) is None:
        _fail('INVALID_SCHEMA', f'{label} must be one safe token')
    return value


def _reviewed_policy_identifier(label, value):
    identifier = _token(label, value)
    parts = {
        part
        for part in re.split(r'[._:@/+\-]+', identifier.casefold())
        if part
    }
    if parts & UNRESOLVED_POLICY_ID_PARTS:
        _fail('NEEDS_CLARIFICATION', f'{label} is not a reviewed source identity')
    return identifier


def _canonical_uuid(label, value):
    if not isinstance(value, str):
        _fail('INVALID_SCHEMA', f'{label} must be one canonical UUID')
    try:
        canonical = str(UUID(value))
    except (AttributeError, ValueError):
        _fail('INVALID_SCHEMA', f'{label} must be one canonical UUID')
    if value != canonical:
        _fail('INVALID_SCHEMA', f'{label} must be one canonical UUID')
    return canonical


def _sha(label, value):
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        _fail('INVALID_SCHEMA', f'{label} must be one SHA-256 digest')
    return value


def _label(label, value, maximum=160):
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _fail('INVALID_SCHEMA', f'{label} must be one safe label')
    return value


def _filename(value):
    if (
        not isinstance(value, str)
        or value != value.strip()
        or value in {'.', '..'}
        or FILENAME_RE.fullmatch(value) is None
    ):
        _fail('INVALID_SCHEMA', 'desired filename must be one safe PDF basename')
    return value


def _date(label, value):
    if not isinstance(value, str):
        _fail('INVALID_SCHEMA', f'{label} must be YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _fail('INVALID_SCHEMA', f'{label} must be YYYY-MM-DD')
    if parsed.isoformat() != value:
        _fail('INVALID_SCHEMA', f'{label} must be canonical YYYY-MM-DD')
    return parsed


def _timestamp(label, value):
    if not isinstance(value, str) or value != value.strip() or not value:
        _fail('INVALID_SCHEMA', f'{label} must be one canonical timezone timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        _fail('INVALID_SCHEMA', f'{label} must be one canonical timezone timestamp')
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail('INVALID_SCHEMA', f'{label} must include a timezone')
    canonical = parsed.isoformat()
    if value.endswith('Z') and parsed.utcoffset() == timedelta(0):
        canonical = canonical.removesuffix('+00:00') + 'Z'
    if canonical != value:
        _fail('INVALID_SCHEMA', f'{label} must be one canonical timezone timestamp')
    return parsed


def _positive_decimal_id(label, value):
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith('0')
        or len(value) > 19
        or int(value) > 9223372036854775807
    ):
        _fail('INVALID_SCHEMA', f'{label} must be one canonical positive record ID')
    return value


def _decimal(label, value):
    if not isinstance(value, str) or value != value.strip() or not value:
        _fail('INVALID_SCHEMA', f'{label} must be one exact decimal string')
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _fail('INVALID_SCHEMA', f'{label} must be one exact decimal string')
    if not parsed.is_finite():
        _fail('INVALID_SCHEMA', f'{label} must be finite')
    return parsed


def _renewal_amounts(value, tax_rate):
    """Return storage-safe exact CRM money values for one renewal."""

    if not isinstance(value, str) or MONEY_RE.fullmatch(value) is None:
        _fail(
            'INVALID_SCHEMA',
            'renewal price must be positive canonical money with exactly two decimals',
        )
    price = _decimal('renewal price', value)
    if price <= 0 or price > MAX_CONTRACT_MONEY:
        _fail('INVALID_SCHEMA', 'renewal price is outside CRM money bounds')
    if not isinstance(tax_rate, Decimal) or not tax_rate.is_finite() or tax_rate < 0:
        _fail('NEEDS_CLARIFICATION', 'source tax rate is not a non-negative finite value')
    tax_amount = (price * tax_rate / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    total_value = price + tax_amount
    if tax_amount > MAX_CONTRACT_MONEY or total_value > MAX_CONTRACT_MONEY:
        _fail('INVALID_SCHEMA', 'renewal price and tax exceed CRM money bounds')
    return price, tax_amount, total_value


def _versioned_contract(contract, include_status=False):
    value = {
        'contract_id': str(contract.id),
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
        'updated_at': rfc3339(contract.updated_at),
    }
    if include_status:
        value['status'] = contract.status
    return value


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _reviewed_policy(lock=False):
    queryset = ReneRenewalPolicy.objects.filter(scope_key='global')
    if lock:
        queryset = queryset.select_for_update()
    policies = list(queryset[:2])
    if len(policies) != 1 or policies[0].review_status != 'reviewed':
        _fail('NEEDS_CLARIFICATION', 'one reviewed global Rene renewal policy is required')
    policy = policies[0]
    if policy.start_rule not in {'SAME_DAY', 'NEXT_DAY'}:
        _fail('NEEDS_CLARIFICATION', 'renewal start rule is not reviewed')
    if policy.end_rule not in {'INCLUSIVE_MINUS_ONE', 'ANNIVERSARY_DAY'}:
        _fail('NEEDS_CLARIFICATION', 'renewal end rule is not reviewed')
    for name in (
        'start_policy_id',
        'end_policy_id',
        'contract_number_policy_id',
    ):
        _reviewed_policy_identifier(name, getattr(policy, name))
    for name in (
        'start_source_ref',
        'end_source_ref',
        'contract_number_source_ref',
    ):
        _reviewed_policy_identifier(name, getattr(policy, name))
    for name in (
        'start_evidence_sha256',
        'end_evidence_sha256',
        'contract_number_evidence_sha256',
    ):
        _sha(name, getattr(policy, name))
    for name in (
        'start_source_label',
        'end_source_label',
        'contract_number_source_label',
    ):
        _label(name, getattr(policy, name))
    for name in ('start_revision', 'end_revision', 'contract_number_revision'):
        revision = getattr(policy, name)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            _fail('NEEDS_CLARIFICATION', f'{name} must be a positive reviewed revision')
    if policy.contract_number_rule != FINAL_NUMBER_RULE:
        _fail('NEEDS_CLARIFICATION', 'final-number reservation policy is not reviewed')
    return policy


def _reviewed_post_send_policy(policy):
    if (
        policy.post_send_state_semantics_reviewed is not True
        or policy.post_send_rule != POST_SEND_RULE
    ):
        _fail('NEEDS_CLARIFICATION', 'ready_for_review to Sent semantics are not reviewed')
    for name in ('post_send_policy_id', 'post_send_source_ref'):
        _reviewed_policy_identifier(name, getattr(policy, name))
    _sha('post_send_evidence_sha256', policy.post_send_evidence_sha256)
    _label('post_send_source_label', policy.post_send_source_label)
    if (
        isinstance(policy.post_send_revision, bool)
        or not isinstance(policy.post_send_revision, int)
        or policy.post_send_revision < 1
    ):
        _fail(
            'NEEDS_CLARIFICATION',
            'post_send_revision must be a positive reviewed revision',
        )
    return policy


def _policy_dates(contract, policy):
    if contract.end_date is None:
        _fail('NEEDS_CLARIFICATION', 'source contract end_date is blank')
    if (
        isinstance(contract.renewal_period_months, bool)
        or not isinstance(contract.renewal_period_months, int)
        or not 1 <= contract.renewal_period_months <= 120
    ):
        _fail('NEEDS_CLARIFICATION', 'renewal period must be 1 to 120 calendar months')
    start = (
        contract.end_date
        if policy.start_rule == 'SAME_DAY'
        else contract.end_date + timedelta(days=1)
    )
    anniversary = _add_months(start, contract.renewal_period_months)
    end = (
        anniversary - timedelta(days=1)
        if policy.end_rule == 'INCLUSIVE_MINUS_ONE'
        else anniversary
    )
    return start, end


def _read_unique_signed_document(contract, lock=False):
    documents = contract.contract_documents.filter(
        is_official=True, is_signed=True
    ).order_by('id')
    if lock:
        documents = documents.select_for_update()
    documents = list(documents[:2])
    if len(documents) != 1:
        _fail(
            'NEEDS_CLARIFICATION',
            'source contract must have exactly one official signed document',
        )
    document = documents[0]
    if document.signed_date is None:
        _fail('NEEDS_CLARIFICATION', 'official signed document has no signed_date')
    filename = _filename(Path(document.file.name).name)
    try:
        document.file.open('rb')
        content = document.file.read(MAX_PDF_BYTES + 1)
    except (OSError, ValueError):
        _fail('ARTIFACT_UNAVAILABLE', 'official signed document bytes are unavailable')
    finally:
        try:
            document.file.close()
        except Exception:
            pass
    _validate_pdf_bytes(content)
    return document, filename, content


def _confirmed_source(value, contract):
    confirmation = _exact('confirmed source', value, {
        'candidate_receipt',
        'source_contract_id', 'source_company_id', 'expected_document_id',
        'expected_filename', 'expected_pdf_sha256', 'expected_uploaded_at',
        'expected_is_official', 'expected_is_signed', 'expected_record_signed_date',
        'signed_date', 'clarification_id', 'clarification_revision',
        'clarification_request_sha256', 'answer_sha256', 'answer_message_name',
        'answer_sender', 'answer_received_at', 'chat_space', 'chat_thread_name',
        'document_metadata_must_remain_unchanged',
    })
    for name in (
        'source_contract_id', 'source_company_id', 'clarification_id',
        'answer_message_name', 'answer_sender', 'chat_space', 'chat_thread_name',
    ):
        _token(f'confirmed source {name}', confirmation[name])
    _positive_decimal_id(
        'confirmed source expected_document_id', confirmation['expected_document_id']
    )
    _filename(confirmation['expected_filename'])
    _sha('confirmed source PDF hash', confirmation['expected_pdf_sha256'])
    _timestamp('confirmed source upload time', confirmation['expected_uploaded_at'])
    _date('confirmed source signed date', confirmation['signed_date'])
    if confirmation['expected_record_signed_date'] is not None:
        _date(
            'confirmed source record signed date',
            confirmation['expected_record_signed_date'],
        )
    _sha('confirmed source request hash', confirmation['clarification_request_sha256'])
    _sha('confirmed source answer hash', confirmation['answer_sha256'])
    _timestamp('confirmed source answer time', confirmation['answer_received_at'])
    if (
        isinstance(confirmation['clarification_revision'], bool)
        or not isinstance(confirmation['clarification_revision'], int)
        or confirmation['clarification_revision'] < 1
        or confirmation['source_contract_id'] != str(contract.id)
        or confirmation['source_company_id'] != str(contract.company_id)
        or not isinstance(confirmation['expected_is_official'], bool)
        or not isinstance(confirmation['expected_is_signed'], bool)
        or confirmation['document_metadata_must_remain_unchanged'] is not True
    ):
        _fail('INVALID_SCHEMA', 'confirmed source identity or safety binding differs')
    _load_confirmed_candidate(confirmation, contract)
    return confirmation


def _candidate_binding_material(envelope, source):
    return {
        'inspection_request_id': envelope['request_id'],
        'inspection_request_key': envelope['request_key'],
        'inspection_intent_sha256': envelope['intent_sha256'],
        'contract_id': source['contract_id'],
        'company_id': source['company_id'],
        'version': source['version'],
        'contract_updated_at': source['contract_updated_at'],
        'evidence_revision': source['evidence_revision'],
        'candidates': source['candidates'],
    }


def _load_confirmed_candidate(confirmation, contract):
    reference = _exact(
        'confirmed source candidate receipt',
        confirmation['candidate_receipt'],
        {
            'request_id', 'request_key', 'intent_sha256', 'binding_sha256',
            'receipt_binding_sha256',
        },
    )
    _token('candidate receipt request_id', reference['request_id'])
    _token('candidate receipt request_key', reference['request_key'])
    _sha('candidate receipt intent hash', reference['intent_sha256'])
    _sha('candidate receipt binding hash', reference['binding_sha256'])
    _sha('candidate full receipt binding hash', reference['receipt_binding_sha256'])
    record = ReneCiraRequest.objects.filter(
        request_id=reference['request_id'],
        request_key=reference['request_key'],
        intent_sha256=reference['intent_sha256'],
        operation='inspect_renewal_source_candidates',
        state='succeeded',
    ).first()
    if record is None or not isinstance(record.receipt, dict):
        _fail('MISSING_EVIDENCE', 'confirmed source lacks its candidate inspection')
    source = record.receipt.get('source_candidates')
    if (
        record.receipt.get('outcome') != 'source_candidates_inspected'
        or not isinstance(source, dict)
        or set(source) != {
            'contract_id', 'company_id', 'version', 'contract_updated_at',
            'evidence_revision', 'candidates', 'binding_sha256',
        }
        or source.get('binding_sha256') != reference['binding_sha256']
        or _receipt_binding(record.receipt) != reference['receipt_binding_sha256']
        or canonical_sha256(_candidate_binding_material({
            'request_id': reference['request_id'],
            'request_key': reference['request_key'],
            'intent_sha256': reference['intent_sha256'],
        }, source))
        != reference['binding_sha256']
        or source.get('contract_id') != str(contract.id)
        or source.get('company_id') != str(contract.company_id)
        or source.get('version') != contract_version(contract)
        or source.get('contract_updated_at') != rfc3339(contract.updated_at)
    ):
        _fail('EVIDENCE_CHANGED', 'source candidate inspection binding differs')
    candidates = source.get('candidates')
    if (
        not isinstance(candidates, list)
        or len(candidates) > MAX_SOURCE_CANDIDATES
    ):
        _fail('EVIDENCE_CHANGED', 'source candidate inspection list differs')
    selected = {
        'document_id': confirmation['expected_document_id'],
        'filename': confirmation['expected_filename'],
        'pdf_sha256': confirmation['expected_pdf_sha256'],
        'size_bytes': None,
        'uploaded_at': confirmation['expected_uploaded_at'],
        'is_official': confirmation['expected_is_official'],
        'is_signed': confirmation['expected_is_signed'],
        'record_signed_date': confirmation['expected_record_signed_date'],
    }
    matches = []
    observed_ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != set(selected):
            _fail('EVIDENCE_CHANGED', 'source candidate receipt shape differs')
        _positive_decimal_id('candidate document_id', candidate['document_id'])
        _filename(candidate['filename'])
        _sha('candidate PDF hash', candidate['pdf_sha256'])
        _timestamp('candidate upload time', candidate['uploaded_at'])
        if (
            isinstance(candidate['size_bytes'], bool)
            or not isinstance(candidate['size_bytes'], int)
            or not 9 <= candidate['size_bytes'] <= MAX_PDF_BYTES
            or not isinstance(candidate['is_official'], bool)
            or not isinstance(candidate['is_signed'], bool)
        ):
            _fail('EVIDENCE_CHANGED', 'source candidate values differ')
        if candidate['record_signed_date'] is not None:
            _date('candidate record signed date', candidate['record_signed_date'])
        observed_ids.append(int(candidate['document_id']))
        if candidate.get('document_id') == confirmation['expected_document_id']:
            matches.append(candidate)
    if observed_ids != sorted(set(observed_ids)):
        _fail('EVIDENCE_CHANGED', 'source candidates are not uniquely ordered')
    if len(matches) != 1:
        _fail('EVIDENCE_CHANGED', 'confirmed source is not unique in its candidate receipt')
    selected['size_bytes'] = matches[0].get('size_bytes')
    if matches[0] != selected:
        _fail('EVIDENCE_CHANGED', 'confirmed source differs from its candidate receipt')


def _read_confirmed_document(contract, confirmation, lock=False):
    """Read one exact existing PDF and prove its CRM metadata was not changed."""
    documents = contract.contract_documents.filter(
        pk=int(confirmation['expected_document_id'])
    ).order_by('id')
    if lock:
        documents = documents.select_for_update()
    documents = list(documents[:2])
    if len(documents) != 1:
        _fail('EVIDENCE_CHANGED', 'confirmed CRM document no longer exists on this contract')
    document = documents[0]
    before = (
        str(document.id), document.file.name, document.is_official, document.is_signed,
        document.signed_date, rfc3339(document.uploaded_at),
    )
    if (
        str(document.id) != confirmation['expected_document_id']
        or Path(document.file.name).name != confirmation['expected_filename']
        or rfc3339(document.uploaded_at) != confirmation['expected_uploaded_at']
        or document.is_official is not confirmation['expected_is_official']
        or document.is_signed is not confirmation['expected_is_signed']
        or (
            document.signed_date.isoformat()
            if document.signed_date is not None
            else None
        ) != confirmation['expected_record_signed_date']
        or (
        document.signed_date is not None
        and document.signed_date.isoformat() != confirmation['signed_date']
        )
    ):
        _fail('EVIDENCE_CHANGED', 'confirmed source document metadata differs')
    filename = _filename(Path(document.file.name).name)
    try:
        document.file.open('rb')
        content = document.file.read(MAX_PDF_BYTES + 1)
    except (OSError, ValueError):
        _fail('ARTIFACT_UNAVAILABLE', 'confirmed source PDF bytes are unavailable')
    finally:
        try:
            document.file.close()
        except Exception:
            pass
    _validate_pdf_bytes(content)
    if hashlib.sha256(content).hexdigest() != confirmation['expected_pdf_sha256']:
        _fail('EVIDENCE_CHANGED', 'confirmed source PDF bytes differ')
    try:
        document.refresh_from_db()
    except document.__class__.DoesNotExist:
        _fail('EVIDENCE_CHANGED', 'confirmed CRM document changed during inspection')
    after = (
        str(document.id), document.file.name, document.is_official, document.is_signed,
        document.signed_date, rfc3339(document.uploaded_at),
    )
    if before != after or filename != confirmation['expected_filename']:
        _fail('EVIDENCE_CHANGED', 'confirmed source PDF or metadata changed during inspection')
    return document, filename, content


def _validate_pdf_bytes(content):
    if (
        not isinstance(content, bytes)
        or not 9 <= len(content) <= MAX_PDF_BYTES
        or not content.startswith(b'%PDF-')
        or not content.rstrip().endswith(b'%%EOF')
    ):
        _fail('INVALID_ARTIFACT', 'PDF bytes are missing, malformed, or above 10 MiB')


def _read_source_candidate(document):
    before = (
        str(document.id), document.file.name, document.is_official, document.is_signed,
        document.signed_date, rfc3339(document.uploaded_at),
    )
    filename = _filename(Path(document.file.name).name)
    try:
        document.file.open('rb')
        content = document.file.read(MAX_PDF_BYTES + 1)
    except (OSError, ValueError):
        _fail('ARTIFACT_UNAVAILABLE', 'source candidate PDF bytes are unavailable')
    finally:
        try:
            document.file.close()
        except Exception:
            pass
    _validate_pdf_bytes(content)
    try:
        document.refresh_from_db()
    except document.__class__.DoesNotExist:
        _fail('EVIDENCE_CHANGED', 'source candidate changed during inspection')
    after = (
        str(document.id), document.file.name, document.is_official, document.is_signed,
        document.signed_date, rfc3339(document.uploaded_at),
    )
    if before != after or Path(document.file.name).name != filename:
        _fail('EVIDENCE_CHANGED', 'source candidate changed during inspection')
    return {
        'document_id': str(document.id),
        'filename': filename,
        'pdf_sha256': hashlib.sha256(content).hexdigest(),
        'size_bytes': len(content),
        'uploaded_at': rfc3339(document.uploaded_at),
        'is_official': document.is_official,
        'is_signed': document.is_signed,
        'record_signed_date': (
            document.signed_date.isoformat()
            if document.signed_date is not None
            else None
        ),
    }


def _visible_pdf_text(content):
    """Extract bounded visible text from the generated review artifact."""

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 200:
            _fail('PDF_RENDER_BLOCKED', 'review PDF is encrypted or has an unsafe page count')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except RenePhase2Error:
        raise
    except Exception:
        _fail('PDF_RENDER_BLOCKED', 'review PDF visible text could not be verified')
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        _fail('PDF_RENDER_BLOCKED', 'review PDF has no verifiable visible text')
    return text


def _date_markers(value):
    return {
        value.strftime('%d %B %Y'),
        value.strftime('%b %d, %Y'),
        value.strftime('%B %d, %Y'),
    }


def _verify_rendered_contract_terms(content, contract):
    """Prove the customer-visible review PDF contains its sealed CRM terms."""

    text = _visible_pdf_text(content)
    if contract.contract_number not in text:
        _fail('PDF_RENDER_BLOCKED', 'review PDF does not show the final contract number')
    for label, value in (
        ('start date', contract.start_date),
        ('end date', contract.end_date),
    ):
        if value is None or not any(marker in text for marker in _date_markers(value)):
            _fail('PDF_RENDER_BLOCKED', f'review PDF does not show the exact {label}')
    amount = f'{contract.value:,.2f}'
    if amount not in text or contract.currency not in text:
        _fail('PDF_RENDER_BLOCKED', 'review PDF does not show the exact price and currency')
    return text


def _pricing_structure(contract, lock=False):
    line_item_query = ContractLineItem.objects.filter(contract=contract).order_by('id')
    location_query = ContractServiceLocation.objects.filter(
        contract=contract
    ).exclude(price__isnull=True).order_by('id')
    if lock:
        line_item_query = line_item_query.select_for_update()
        location_query = location_query.select_for_update()
    line_items = list(
        line_item_query.values(
            'id', 'quantity', 'unit_price', 'discount_percentage', 'line_total'
        )
    )
    priced_locations = list(
        location_query.values('id', 'price')
    )
    structures = []
    if line_items:
        structures.append('LINE_ITEMS')
    if priced_locations:
        structures.append('SERVICE_LOCATIONS')
    if contract.price_per_zone is not None:
        structures.append('PRICE_PER_ZONE')
    complex_pricing = bool(structures)
    kind = (
        'SIMPLE_TOTAL'
        if not structures
        else structures[0]
        if len(structures) == 1
        else 'MIXED'
    )
    evidence = {
        'contract_id': str(contract.id),
        'contract_total': str(contract.value),
        'price_per_zone': (
            str(contract.price_per_zone) if contract.price_per_zone is not None else None
        ),
        'line_items': [
            {key: str(value) for key, value in row.items()} for row in line_items
        ],
        'priced_service_locations': [
            {key: str(value) for key, value in row.items()} for row in priced_locations
        ],
    }
    return {
        'kind': kind,
        'current_total': str(contract.value),
        'component_count': max(1, len(line_items) + len(priced_locations)),
        'uses_price_per_zone': contract.price_per_zone is not None or bool(priced_locations),
        'mapping_status': (
            'NEEDS_CLARIFICATION' if complex_pricing else 'UNIQUE_SIMPLE_TOTAL'
        ),
        'evidence_sha256': canonical_sha256(evidence),
    }


def _parse_envelope(value):
    envelope = _exact(
        'request envelope',
        value,
        {
            'schema', 'from', 'requesting_agent', 'verb', 'collection',
            'request_id', 'request_key', 'intent_sha256', 'id',
            'expected_version', 'data',
        },
    )
    if (
        envelope['schema'] != SCHEMA
        or envelope['from'] != AGENT
        or envelope['requesting_agent'] != AGENT
        or envelope['collection'] != COLLECTION
    ):
        _fail('FORBIDDEN', 'request is outside Rene contract authority')
    operation = envelope['verb']
    if operation not in ALLOWED_OPERATIONS:
        _fail('FORBIDDEN', 'operation is not allowlisted for Rene')
    for field in ('request_id', 'expected_version'):
        _token(field, envelope[field])
    _canonical_uuid('id', envelope['id'])
    _sha('intent_sha256', envelope['intent_sha256'])
    data = _exact(
        'request data',
        envelope['data'],
        {
            'schema', 'requesting_agent', 'collection', 'operation',
            'target_contract_id', 'expected_version', 'intent',
        },
    )
    if (
        data['schema'] != SCHEMA
        or data['requesting_agent'] != AGENT
        or data['collection'] != COLLECTION
        or data['operation'] != operation
        or data['target_contract_id'] != envelope['id']
        or str(data['expected_version']) != str(envelope['expected_version'])
    ):
        _fail('INVALID_SCHEMA', 'request data identity differs from its envelope')
    _mapping('request intent', data['intent'])
    observed_hash = canonical_sha256(data)
    expected_key = f"rene:{operation}:{envelope['id']}:{observed_hash}"
    if envelope['intent_sha256'] != observed_hash or envelope['request_key'] != expected_key:
        _fail('HASH_MISMATCH', 'request intent hash or key is invalid')
    return envelope


def _receipt_base(envelope, outcome, before, after, artifact=None):
    return {
        'schema': SCHEMA,
        'request_id': envelope['request_id'],
        'request_key': envelope['request_key'],
        'requesting_agent': AGENT,
        'operation': envelope['verb'],
        'intent_sha256': envelope['intent_sha256'],
        'outcome': outcome,
        'before': before,
        'after': after,
        'artifact': artifact,
    }


def _source_candidates_inspection(envelope):
    intent = _exact(
        'source candidate inspection intent',
        envelope['data']['intent'],
        {
            'target_company_id', 'evidence_revision', 'document_scope',
            'maximum_candidates', 'return', 'must_not_mutate',
        },
    )
    if (
        intent['document_scope'] != 'contract_documents'
        or intent['maximum_candidates'] != MAX_SOURCE_CANDIDATES
        or intent['return'] != SOURCE_CANDIDATE_RETURN_FIELDS
        or intent['must_not_mutate'] is not True
        or isinstance(intent['evidence_revision'], bool)
        or not isinstance(intent['evidence_revision'], int)
        or intent['evidence_revision'] < 1
    ):
        _fail('INVALID_SCHEMA', 'source candidate inspection requirements differ')
    _canonical_uuid('source candidate company', intent['target_company_id'])
    contract = Contract.objects.select_related('company').get(pk=envelope['id'])
    before = _versioned_contract(contract)
    if (
        str(contract.company_id) != intent['target_company_id']
        or before['version'] != envelope['expected_version']
    ):
        _fail('VERSION_CONFLICT', 'source contract identity or version changed')
    documents = list(
        contract.contract_documents.order_by('id')[:MAX_SOURCE_CANDIDATES + 1]
    )
    if len(documents) > MAX_SOURCE_CANDIDATES:
        _fail('NEEDS_CLARIFICATION', 'source contract has more than 32 documents')
    before_ids = [str(document.id) for document in documents]
    candidates = [_read_source_candidate(document) for document in documents]
    try:
        contract.refresh_from_db()
    except Contract.DoesNotExist:
        _fail('EVIDENCE_CHANGED', 'source contract changed during candidate inspection')
    after_documents = list(
        contract.contract_documents.order_by('id')[:MAX_SOURCE_CANDIDATES + 1]
    )
    after = _versioned_contract(contract)
    if (
        before != after
        or before_ids != [str(document.id) for document in after_documents]
    ):
        _fail('EVIDENCE_CHANGED', 'source contract documents changed during inspection')
    source = {
        'contract_id': before['contract_id'],
        'company_id': before['company_id'],
        'version': before['version'],
        'contract_updated_at': before['updated_at'],
        'evidence_revision': intent['evidence_revision'],
        'candidates': candidates,
    }
    source['binding_sha256'] = canonical_sha256(
        _candidate_binding_material(envelope, source)
    )
    receipt = _receipt_base(
        envelope,
        'source_candidates_inspected',
        before,
        dict(after),
    )
    receipt['source_candidates'] = source
    return receipt


def _source_inspection(envelope):
    intent = envelope['data']['intent']
    expected_intent = {
        'target_company_id', 'document_selection', 'required_document_count',
        'required_document_flags', 'require_reviewed_renewal_start_policy',
        'require_reviewed_renewal_end_policy', 'require_pricing_structure_evidence',
        'evidence_revision', 'return', 'must_not_mutate',
    }
    selection = intent.get('document_selection')
    if selection == NIKKI_CONFIRMED_SOURCE:
        expected_intent.add('confirmed_source')
    if set(intent) != expected_intent:
        _fail('INVALID_SCHEMA', 'inspection intent fields differ')
    if (
        selection not in {NATIVE_SIGNED_SOURCE, NIKKI_CONFIRMED_SOURCE}
        or intent['required_document_count'] != 1
        or intent['require_reviewed_renewal_start_policy'] is not True
        or intent['require_reviewed_renewal_end_policy'] is not True
        or intent['require_pricing_structure_evidence'] is not True
        or isinstance(intent['evidence_revision'], bool)
        or not isinstance(intent['evidence_revision'], int)
        or intent['evidence_revision'] < 1
        or intent['must_not_mutate'] is not True
    ):
        _fail('INVALID_SCHEMA', 'inspection safety requirements differ')
    contract = Contract.objects.select_related('company').get(pk=envelope['id'])
    if str(contract.company_id) != intent['target_company_id']:
        _fail('IDENTITY_MISMATCH', 'source contract belongs to another company')
    if contract_version(contract) != envelope['expected_version']:
        _fail('VERSION_CONFLICT', 'source contract version changed')
    policy = _reviewed_policy()
    next_start, next_end = _policy_dates(contract, policy)
    confirmation = None
    if selection == NATIVE_SIGNED_SOURCE:
        if (
            intent['required_document_flags'] != {'is_official': True, 'is_signed': True}
            or intent['return'] != INSPECTION_RETURN_FIELDS
        ):
            _fail('INVALID_SCHEMA', 'native signed-source requirements differ')
        document, filename, content = _read_unique_signed_document(contract)
        signed_date = document.signed_date.isoformat()
    else:
        if (
            intent['required_document_flags'] != {'preserve_current_values': True}
            or intent['return'] != [*INSPECTION_RETURN_FIELDS, 'source_confirmation']
        ):
            _fail('INVALID_SCHEMA', 'confirmed-source requirements differ')
        confirmation = _confirmed_source(intent['confirmed_source'], contract)
        document, filename, content = _read_confirmed_document(contract, confirmation)
        signed_date = confirmation['signed_date']
    pricing = _pricing_structure(contract)
    terms = {
        'start_date': contract.start_date.isoformat(),
        'end_date': contract.end_date.isoformat(),
        'price': str(contract.value),
        'currency': contract.currency,
    }
    source = {
        'document_selection': selection,
        'document_count': 1,
        'contract_id': str(contract.id),
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
        'contract_updated_at': rfc3339(contract.updated_at),
        'evidence_revision': intent['evidence_revision'],
        'document': {
            'document_id': str(document.id),
            'filename': filename,
            'pdf_sha256': hashlib.sha256(content).hexdigest(),
            'size_bytes': len(content),
            'is_official': document.is_official,
            'is_signed': document.is_signed,
            'signed_date': signed_date,
            'uploaded_at': rfc3339(document.uploaded_at),
        },
        'terms': terms,
        'term_duration': {
            'kind': 'calendar_months',
            'months': contract.renewal_period_months,
        },
        'renewal_start_policy': {
            'policy_id': policy.start_policy_id,
            'rule': policy.start_rule,
            'evidence_sha256': policy.start_evidence_sha256,
            'source_ref': policy.start_source_ref,
            'source_label': policy.start_source_label,
            'revision': policy.start_revision,
            'review_status': 'reviewed',
            'next_start_date': next_start.isoformat(),
        },
        'renewal_end_policy': {
            'policy_id': policy.end_policy_id,
            'rule': policy.end_rule,
            'evidence_sha256': policy.end_evidence_sha256,
            'source_ref': policy.end_source_ref,
            'source_label': policy.end_source_label,
            'revision': policy.end_revision,
            'review_status': 'reviewed',
            'next_end_date': next_end.isoformat(),
        },
        'pricing_structure': pricing,
    }
    if confirmation is not None:
        source['document']['record_signed_date'] = (
            document.signed_date.isoformat()
            if document.signed_date is not None
            else None
        )
        source['source_confirmation'] = confirmation
    binding_material = {
        'inspection_request_id': envelope['request_id'],
        'inspection_request_key': envelope['request_key'],
        'inspection_intent_sha256': envelope['intent_sha256'],
        'contract_id': source['contract_id'],
        'company_id': source['company_id'],
        'version': source['version'],
        'contract_updated_at': source['contract_updated_at'],
        'evidence_revision': source['evidence_revision'],
        'document': source['document'],
        'terms': terms,
        'term_duration': source['term_duration'],
        'renewal_start_policy': source['renewal_start_policy'],
        'renewal_end_policy': source['renewal_end_policy'],
        'pricing_structure': pricing,
    }
    if confirmation is not None:
        binding_material['document_selection'] = selection
        binding_material['source_confirmation'] = confirmation
    source['binding_sha256'] = canonical_sha256(binding_material)
    identity = _versioned_contract(contract)
    receipt = _receipt_base(envelope, 'inspected', identity, dict(identity))
    receipt['source_inspection'] = source
    return receipt


def _load_inspection(intent, source):
    source = _mapping('source inspection reference', source)
    reference_fields = {
        'request_id', 'request_key', 'intent_sha256', 'binding_sha256',
        'document_id', 'filename', 'contract_updated_at', 'evidence_revision', 'terms',
        'term_duration', 'renewal_start_policy', 'renewal_end_policy', 'pricing_structure',
    }
    if source.get('document_selection') == NIKKI_CONFIRMED_SOURCE:
        reference_fields.update({'document_selection', 'source_confirmation'})
    reference = _exact(
        'source inspection reference',
        source,
        reference_fields,
    )
    record = ReneCiraRequest.objects.filter(
        request_id=reference['request_id'],
        request_key=reference['request_key'],
        intent_sha256=reference['intent_sha256'],
        operation='inspect_renewal_source',
        state='succeeded',
    ).first()
    if record is None or not isinstance(record.receipt, dict):
        _fail('MISSING_EVIDENCE', 'prepare lacks a received source inspection')
    observed = record.receipt.get('source_inspection')
    if not isinstance(observed, dict) or observed.get('binding_sha256') != reference['binding_sha256']:
        _fail('EVIDENCE_CHANGED', 'source inspection binding differs')
    expected_reference = {
        'request_id': record.request_id,
        'request_key': record.request_key,
        'intent_sha256': record.intent_sha256,
        'binding_sha256': observed['binding_sha256'],
        'document_id': observed['document']['document_id'],
        'filename': observed['document']['filename'],
        'contract_updated_at': observed['contract_updated_at'],
        'evidence_revision': observed['evidence_revision'],
        'terms': observed['terms'],
        'term_duration': observed['term_duration'],
        'renewal_start_policy': {
            key: observed['renewal_start_policy'][key]
            for key in (
                'policy_id', 'rule', 'evidence_sha256', 'source_ref', 'source_label',
                'revision', 'next_start_date',
            )
        },
        'renewal_end_policy': {
            key: observed['renewal_end_policy'][key]
            for key in (
                'policy_id', 'rule', 'evidence_sha256', 'source_ref', 'source_label',
                'revision', 'next_end_date',
            )
        },
        'pricing_structure': observed['pricing_structure'],
    }
    if observed.get('source_confirmation') is not None:
        expected_reference['document_selection'] = observed['document_selection']
        expected_reference['source_confirmation'] = observed['source_confirmation']
    if reference != expected_reference:
        _fail('EVIDENCE_CHANGED', 'prepare inspection reference is not exact')
    if intent['source_contract_pdf_sha256'] != observed['document']['pdf_sha256']:
        _fail('EVIDENCE_CHANGED', 'prepare source PDF hash differs')
    return observed


def _validate_prepare(
    envelope,
    lock=False,
    *,
    existing_preparation=None,
):
    intent = _exact(
        'prepare intent',
        envelope['data']['intent'],
        {
            'source_contract_id', 'source_company_id', 'source_contract_pdf_sha256',
            'source_inspection', 'desired_filename', 'renewal_terms',
            'sheet_evidence', 'contract_number_requirements', 'delivery',
        },
    )
    if intent['source_contract_id'] != envelope['id']:
        _fail('IDENTITY_MISMATCH', 'prepare target differs from source contract')
    _sha('source_contract_pdf_sha256', intent['source_contract_pdf_sha256'])
    _filename(intent['desired_filename'])
    if intent['contract_number_requirements'] != {
        'must_be_final_before_pdf': True,
        'must_be_embedded_in_pdf': True,
        'must_remain_unchanged_on_sent': True,
        'require_reviewed_policy': True,
    } or intent['delivery'] != 'return_pdf_for_nikki_review':
        _fail('INVALID_SCHEMA', 'prepare final-number or delivery requirements differ')
    inspection = _load_inspection(intent, intent['source_inspection'])
    contract_query = Contract.objects.select_related('company')
    if lock:
        contract_query = contract_query.select_for_update()
    contract = contract_query.get(pk=envelope['id'])
    if (
        str(contract.company_id) != intent['source_company_id']
        or contract_version(contract) != envelope['expected_version']
        or rfc3339(contract.updated_at) != inspection['contract_updated_at']
    ):
        _fail('VERSION_CONFLICT', 'source contract changed after inspection')
    successor_query = Contract.objects.filter(renewed_from_id=contract.id)
    preparation_query = RenePreparedContract.objects.filter(source_contract_id=contract.id)
    if lock:
        successor_query = successor_query.select_for_update()
        preparation_query = preparation_query.select_for_update()
    if existing_preparation is None:
        successor_conflict = successor_query.exists()
        preparation_conflict = preparation_query.exists()
    else:
        successor_conflict = (
            not successor_query.filter(pk=existing_preparation.contract_id).exists()
            or successor_query.exclude(pk=existing_preparation.contract_id).exists()
        )
        preparation_conflict = (
            not preparation_query.filter(pk=existing_preparation.pk).exists()
            or preparation_query.exclude(pk=existing_preparation.pk).exists()
        )
    if successor_conflict or preparation_conflict:
        _fail(
            'SOURCE_LIFECYCLE_CHANGED',
            'source contract already has a renewal successor; another prepare is forbidden',
        )
    confirmation = inspection.get('source_confirmation')
    if confirmation is None:
        document, filename, content = _read_unique_signed_document(contract, lock=lock)
    else:
        confirmation = _confirmed_source(confirmation, contract)
        document, filename, content = _read_confirmed_document(
            contract, confirmation, lock=lock
        )
    if (
        str(document.id) != inspection['document']['document_id']
        or filename != inspection['document']['filename']
        or hashlib.sha256(content).hexdigest() != inspection['document']['pdf_sha256']
        or document.is_official != inspection['document']['is_official']
        or document.is_signed != inspection['document']['is_signed']
        or (
            confirmation is None
            and document.signed_date.isoformat() != inspection['document']['signed_date']
        )
        or (
            confirmation is not None
            and (
                document.signed_date.isoformat()
                if document.signed_date is not None
                else None
            )
            != inspection['document']['record_signed_date']
        )
    ):
        _fail('EVIDENCE_CHANGED', 'exact source document or current flags changed')
    policy = _reviewed_policy(lock=lock)
    next_start, next_end = _policy_dates(contract, policy)
    for prefix, observed in (
        ('start', inspection['renewal_start_policy']),
        ('end', inspection['renewal_end_policy']),
    ):
        if (
            observed['policy_id'] != getattr(policy, f'{prefix}_policy_id')
            or observed['rule'] != getattr(policy, f'{prefix}_rule')
            or observed['evidence_sha256'] != getattr(policy, f'{prefix}_evidence_sha256')
            or observed['source_ref'] != getattr(policy, f'{prefix}_source_ref')
            or observed['source_label'] != getattr(policy, f'{prefix}_source_label')
            or observed['revision'] != getattr(policy, f'{prefix}_revision')
        ):
            _fail('EVIDENCE_CHANGED', 'reviewed renewal policy changed after inspection')
    if _pricing_structure(contract, lock=lock) != inspection['pricing_structure']:
        _fail('EVIDENCE_CHANGED', 'source pricing structure changed after inspection')
    if inspection['pricing_structure']['mapping_status'] != 'UNIQUE_SIMPLE_TOTAL':
        _fail('NEEDS_CLARIFICATION', 'structured pricing cannot be inferred')
    terms = _exact(
        'renewal terms', intent['renewal_terms'], {'start_date', 'end_date', 'price', 'currency'}
    )
    if (
        _date('renewal start_date', terms['start_date']) != next_start
        or _date('renewal end_date', terms['end_date']) != next_end
        or terms['currency'] != contract.currency
    ):
        _fail('EVIDENCE_CHANGED', 'renewal terms differ from reviewed policies or currency')
    _renewal_amounts(terms['price'], contract.tax_rate)
    sheet = _exact(
        'sheet evidence', intent['sheet_evidence'], {'spreadsheet_id', 'tab', 'row', 'sha256'}
    )
    _token('spreadsheet_id', sheet['spreadsheet_id'])
    _token('sheet tab', sheet['tab'])
    if isinstance(sheet['row'], bool) or not isinstance(sheet['row'], int) or sheet['row'] < 2:
        _fail('INVALID_SCHEMA', 'sheet row must identify one data row')
    _sha('sheet evidence sha256', sheet['sha256'])
    return contract, policy, terms, sheet, inspection


def _render_contract_pdf(contract):
    from crm_app.views import ContractViewSet
    from crm_app.services.contract_service_locations import (
        service_location_pricing_mismatch,
    )

    number = contract.contract_number
    if (
        not isinstance(number, str)
        or not number
        or number.startswith(('DRAFT-', 'C-'))
    ):
        _fail('NUMBER_RESERVATION_BLOCKED', 'review PDF requires one final contract number')
    if service_location_pricing_mismatch(contract):
        _fail('PDF_RENDER_BLOCKED', 'prepared contract pricing does not reconcile')

    # Call the existing renderer directly rather than routing an internal fake
    # request through the public authenticated API.  An anonymous request is
    # attached only so the renderer's VIEW audit helper remains non-mutating.
    request = RequestFactory().get(f'/api/v1/contracts/{contract.id}/pdf/')
    request.user = AnonymousUser()
    view = ContractViewSet()
    view.request = request
    pdf_format = 'standard'
    if contract.preamble_template and contract.preamble_template.pdf_format:
        pdf_format = contract.preamble_template.pdf_format
    elif contract.contract_category:
        pdf_format = contract.contract_category
    if pdf_format == 'corporate_master':
        response = view._generate_master_agreement_pdf(contract)
    elif pdf_format == 'participation':
        response = view._generate_participation_agreement_pdf(contract)
    else:
        response = view._generate_principal_terms_pdf(contract)
    if response.status_code != 200 or not hasattr(response, 'content'):
        _fail('PDF_RENDER_BLOCKED', 'prepared contract PDF could not be rendered safely')
    content = bytes(response.content)
    _validate_pdf_bytes(content)
    _verify_rendered_contract_terms(content, contract)
    if contract.contract_number != number:
        _fail('EVIDENCE_CHANGED', 'contract number changed while rendering the review PDF')
    return content


def _clone_contract(source, contract_number, terms):
    excluded = {
        'id', 'created_at', 'updated_at', 'contract_number', 'status', 'start_date',
        'end_date', 'value', 'currency', 'is_active', 'renewed_from', 'opportunity',
        'quote', 'renewal_notice_sent', 'renewal_notice_date', 'sent_date',
        'first_followup_sent', 'second_followup_sent', 'lifecycle_type',
        'lifecycle_type_manually_set', 'lifecycle_effective_date',
    }
    values = {}
    for field in Contract._meta.concrete_fields:
        if field.primary_key or field.name in excluded:
            continue
        values[field.attname] = getattr(source, field.attname)
    price, tax_amount, total_value = _renewal_amounts(
        terms['price'], source.tax_rate
    )
    values.update(
        {
            'contract_number': contract_number,
            'status': 'Draft',
            'start_date': _date('renewal start_date', terms['start_date']),
            'end_date': _date('renewal end_date', terms['end_date']),
            'value': price,
            'tax_amount': tax_amount,
            'total_value': total_value,
            'currency': terms['currency'],
            'is_active': False,
            'renewed_from_id': source.id,
            'opportunity_id': None,
            'quote_id': None,
            'renewal_notice_sent': False,
            'renewal_notice_date': None,
            'sent_date': None,
            'first_followup_sent': False,
            'second_followup_sent': False,
            'lifecycle_type': 'renewal',
            'lifecycle_type_manually_set': True,
            'lifecycle_effective_date': None,
        }
    )
    prepared = Contract.objects.create(**values)
    prepared.service_items.set(source.service_items.all())
    ContractServiceLocation.objects.bulk_create(
        [
            ContractServiceLocation(
                contract=prepared,
                location_name=row.location_name,
                platform=row.platform,
                custom_service_name=row.custom_service_name,
                sort_order=row.sort_order,
                price=row.price,
            )
            for row in source.service_locations.all()
        ]
    )
    # UNIQUE_SIMPLE_TOTAL explicitly requires no line-item price structure.
    if source.line_items.exists():
        _fail('NEEDS_CLARIFICATION', 'structured line-item pricing cannot be cloned automatically')
    return prepared


def _reserve_final_contract_number(source):
    region = (
        'TH'
        if source.company.billing_entity == 'BMAsia (Thailand) Co., Ltd.'
        else 'HK'
    )
    # Legacy/manual imports can sit ahead of DocumentSequence. Never collide
    # and never fall back to a temporary number; advance under the sequence's
    # own row lock until an unused final customer-visible number is reserved.
    for _ in range(1000):
        number = DocumentSequence.get_next_number(region, 'CT')
        if not Contract.objects.filter(contract_number=number).exists():
            return number
    _fail('NUMBER_RESERVATION_BLOCKED', 'no safe final contract number could be reserved')


def _prepared_mapping(metadata):
    contract = metadata.contract
    return {
        'prepare_request_id': metadata.prepare_request_id,
        'prepare_request_key': metadata.prepare_request_key,
        'prepare_intent_sha256': metadata.prepare_intent_sha256,
        'contract_id': str(contract.id),
        'contract_number': contract.contract_number,
        'contract_number_is_final': True,
        'pdf_contract_number': contract.contract_number,
        'contract_number_policy_id': metadata.contract_number_policy_id,
        'contract_number_policy_evidence_sha256': metadata.contract_number_policy_evidence_sha256,
        'contract_number_policy_source_ref': metadata.contract_number_policy_source_ref,
        'contract_number_policy_source_label': metadata.contract_number_policy_source_label,
        'contract_number_policy_revision': metadata.contract_number_policy_revision,
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
        'state': metadata.state,
        'source_contract_id': str(metadata.source_contract_id),
        'source_contract_version': metadata.source_contract_version,
        'source_contract_updated_at': rfc3339(metadata.source_contract_updated_at),
        'source_contract_status': metadata.source_contract_status,
        'source_inspection_sha256': metadata.source_inspection_sha256,
        'terms_sha256': metadata.terms_sha256,
        'pdf_sha256': metadata.pdf_sha256,
        'source_lifecycle_changed': False,
        'customer_delivery_performed': metadata.state == 'Sent',
    }


def _artifact_descriptor(metadata):
    content = bytes(metadata.pdf_content)
    _validate_pdf_bytes(content)
    if hashlib.sha256(content).hexdigest() != metadata.pdf_sha256:
        _fail('EVIDENCE_CHANGED', 'stored prepared PDF hash changed')
    return {
        'filename': metadata.pdf_filename,
        'sha256': metadata.pdf_sha256,
        'size_bytes': len(content),
    }


def _portable_artifact(metadata):
    content = bytes(metadata.pdf_content)
    descriptor = _artifact_descriptor(metadata)
    return {
        **descriptor,
        'content_base64': base64.b64encode(content).decode('ascii'),
    }


def _execute_prepare(envelope):
    _require_validation(envelope)
    source, policy, terms, sheet, inspection = _validate_prepare(envelope, lock=True)
    before = _versioned_contract(source, include_status=True)
    number = _reserve_final_contract_number(source)
    prepared = _clone_contract(source, number, terms)
    pdf = _render_contract_pdf(prepared)
    metadata = RenePreparedContract.objects.create(
        contract=prepared,
        source_contract=source,
        state='ready_for_review',
        prepare_request_id=envelope['request_id'],
        prepare_request_key=envelope['request_key'],
        prepare_intent_sha256=envelope['intent_sha256'],
        source_inspection_sha256=inspection['binding_sha256'],
        source_contract_version=before['version'],
        source_contract_updated_at=source.updated_at,
        source_contract_status=source.status,
        terms_sha256=canonical_sha256(terms),
        sheet_evidence=sheet,
        pdf_filename=envelope['data']['intent']['desired_filename'],
        pdf_sha256=hashlib.sha256(pdf).hexdigest(),
        pdf_content=pdf,
        contract_number_policy_id=policy.contract_number_policy_id,
        contract_number_policy_rule=policy.contract_number_rule,
        contract_number_policy_evidence_sha256=policy.contract_number_evidence_sha256,
        contract_number_policy_source_ref=policy.contract_number_source_ref,
        contract_number_policy_source_label=policy.contract_number_source_label,
        contract_number_policy_revision=policy.contract_number_revision,
    )
    source.refresh_from_db()
    after = _versioned_contract(source, include_status=True)
    if after != before:
        _fail('SOURCE_LIFECYCLE_CHANGED', 'preparation changed the source contract')
    artifact = _artifact_descriptor(metadata)
    receipt = _receipt_base(envelope, 'prepared', before, after, artifact)
    receipt['prepared_contract'] = _prepared_mapping(metadata)
    return receipt


def _receipt_binding(receipt):
    artifact = receipt.get('artifact')
    bound_artifact = None
    if artifact is not None:
        bound_artifact = {
            'filename': artifact['filename'],
            'sha256': artifact['sha256'],
            'size_bytes': artifact['size_bytes'],
            # Prepare and verify are frozen as portable-PDF operations.  This
            # stays true in the compact journal descriptor and in the MCP wire
            # copy that additionally contains ``content_base64``.
            'portable': receipt.get('operation') in {
                'prepare_renewal_contract', 'verify_prepared_contract',
            },
        }
    source = receipt.get('source_inspection')
    return canonical_sha256(
        {
            'request_id': receipt['request_id'],
            'request_key': receipt['request_key'],
            'requesting_agent': receipt['requesting_agent'],
            'operation': receipt['operation'],
            'intent_sha256': receipt['intent_sha256'],
            'outcome': receipt['outcome'],
            'before': receipt['before'],
            'after': receipt['after'],
            'artifact': bound_artifact,
            'source_inspection_binding_sha256': (
                source.get('binding_sha256') if isinstance(source, dict) else None
            ),
            'prepared_contract': receipt.get('prepared_contract'),
        }
    )


def _prepared_live_state(prepared, gmail_hash=None):
    return {
        'contract_id': prepared['contract_id'],
        'company_id': prepared['company_id'],
        'version': str(prepared['version']),
        'state': prepared['state'],
        'contract_number': prepared['contract_number'],
        'pdf_sha256': prepared['pdf_sha256'],
        'terms_sha256': prepared['terms_sha256'],
        'customer_delivery_performed': prepared['customer_delivery_performed'],
        'gmail_sent_evidence_sha256': gmail_hash,
        'source_contract_id': prepared['source_contract_id'],
        'source_contract_version': str(prepared['source_contract_version']),
        'source_contract_updated_at': prepared['source_contract_updated_at'],
        'source_contract_status': prepared['source_contract_status'],
    }


def _load_prepared(metadata_id, lock=False):
    query = RenePreparedContract.objects.select_related(
        'contract', 'contract__company', 'source_contract'
    )
    if lock:
        query = query.select_for_update()
    try:
        metadata = query.get(contract_id=metadata_id)
    except RenePreparedContract.DoesNotExist:
        _fail('MISSING_EVIDENCE', 'prepared contract identity is unknown')
    return metadata


def _verify_prepared_source_live(metadata, lock=False):
    """Re-run the exact sealed prepare checks against current source evidence."""

    record = ReneCiraRequest.objects.filter(
        request_id=metadata.prepare_request_id,
        request_key=metadata.prepare_request_key,
        intent_sha256=metadata.prepare_intent_sha256,
        operation='prepare_renewal_contract',
        state='succeeded',
    ).first()
    if record is None or not isinstance(record.envelope, dict):
        _fail('MISSING_EVIDENCE', 'prepared contract lacks its exact prepare request')
    envelope = _parse_envelope(record.envelope)
    source, _, terms, sheet, inspection = _validate_prepare(
        envelope,
        lock=lock,
        existing_preparation=metadata,
    )
    if (
        source.id != metadata.source_contract_id
        or inspection['binding_sha256'] != metadata.source_inspection_sha256
        or canonical_sha256(terms) != metadata.terms_sha256
        or sheet != metadata.sheet_evidence
    ):
        _fail('EVIDENCE_CHANGED', 'prepared source evidence differs from preparation')


def _verify_metadata_live(metadata, expected_version, expected_prepared, lock=False):
    contract = metadata.contract
    source = metadata.source_contract
    if contract_version(contract) != expected_version:
        _fail('VERSION_CONFLICT', 'prepared contract version changed')
    if (
        metadata.state != 'ready_for_review'
        or contract.status != 'Draft'
        or metadata.gmail_sent_evidence_sha256 is not None
        or contract.contract_number.startswith('DRAFT-')
    ):
        _fail('EVIDENCE_CHANGED', 'prepared contract is not review-only and unsent')
    if (
        contract_version(source) != metadata.source_contract_version
        or rfc3339(source.updated_at) != rfc3339(metadata.source_contract_updated_at)
        or source.status != metadata.source_contract_status
    ):
        _fail('EVIDENCE_CHANGED', 'source contract changed after preparation')
    _verify_prepared_source_live(metadata, lock=lock)
    policy = _reviewed_policy(lock=lock)
    if (
        metadata.contract_number_policy_id != policy.contract_number_policy_id
        or metadata.contract_number_policy_rule != policy.contract_number_rule
        or metadata.contract_number_policy_evidence_sha256
        != policy.contract_number_evidence_sha256
        or metadata.contract_number_policy_source_ref
        != policy.contract_number_source_ref
        or metadata.contract_number_policy_source_label
        != policy.contract_number_source_label
        or metadata.contract_number_policy_revision
        != policy.contract_number_revision
    ):
        _fail('EVIDENCE_CHANGED', 'reviewed final-number policy changed after preparation')
    prepared = _prepared_mapping(metadata)
    if prepared != expected_prepared:
        _fail('EVIDENCE_CHANGED', 'prepared contract differs from its receipt')
    _portable_artifact(metadata)
    return prepared


def _validate_verify(envelope):
    intent = _exact(
        'verification intent',
        envelope['data']['intent'],
        {
            'verification_nonce', 'prepare_receipt', 'prepared_contract',
            'required_live_state', 'artifact', 'return_portable_pdf',
            'must_not_mutate',
        },
    )
    if (
        intent['verification_nonce'] != envelope['request_id']
        or intent['return_portable_pdf'] is not True
        or intent['must_not_mutate'] is not True
    ):
        _fail('INVALID_SCHEMA', 'verification nonce or safety flags differ')
    reference = _exact(
        'prepare receipt reference',
        intent['prepare_receipt'],
        {'request_id', 'request_key', 'intent_sha256', 'receipt_binding_sha256'},
    )
    record = ReneCiraRequest.objects.filter(
        request_id=reference['request_id'],
        request_key=reference['request_key'],
        intent_sha256=reference['intent_sha256'],
        operation='prepare_renewal_contract',
        state='succeeded',
    ).first()
    if record is None or not isinstance(record.receipt, dict):
        _fail('MISSING_EVIDENCE', 'verification lacks a received prepare receipt')
    if _receipt_binding(record.receipt) != reference['receipt_binding_sha256']:
        _fail('EVIDENCE_CHANGED', 'prepare receipt binding differs')
    if intent['prepared_contract'] != record.receipt.get('prepared_contract'):
        _fail('EVIDENCE_CHANGED', 'verification prepared mapping differs')
    metadata = _load_prepared(envelope['id'])
    prepared = _verify_metadata_live(
        metadata, envelope['expected_version'], intent['prepared_contract']
    )
    if intent['required_live_state'] != _prepared_live_state(prepared):
        _fail('EVIDENCE_CHANGED', 'required live prepared state differs')
    artifact = _exact(
        'verification artifact', intent['artifact'], {'filename', 'sha256', 'size_bytes'}
    )
    if artifact != {
        'filename': metadata.pdf_filename,
        'sha256': metadata.pdf_sha256,
        'size_bytes': len(bytes(metadata.pdf_content)),
    }:
        _fail('EVIDENCE_CHANGED', 'verification artifact differs')
    return metadata, prepared


def _execute_verify(envelope):
    metadata, prepared = _validate_verify(envelope)
    before = _prepared_live_state(prepared)
    receipt = _receipt_base(
        envelope,
        'prepared_contract_verified',
        before,
        dict(before),
        _artifact_descriptor(metadata),
    )
    receipt['prepared_contract'] = prepared
    return receipt


def _validate_gmail_evidence(value, expected_hash):
    evidence = _exact(
        'Gmail Sent evidence',
        value,
        {
            'action_id', 'revision', 'draft_sha256', 'gmail_message_id',
            'gmail_thread_id', 'gmail_internal_date', 'rfc_message_id', 'sent_at',
            'authenticated_mailbox', 'visible_from', 'to', 'cc', 'subject_sha256',
            'plain_body_sha256', 'html_body_sha256', 'attachment', 'reconciliation',
        },
    )
    if evidence['reconciliation'] != 'EXACT_GMAIL_SENT':
        _fail('INVALID_SCHEMA', 'Gmail reconciliation must be exact')
    for name in ('action_id', 'gmail_message_id', 'gmail_thread_id'):
        _token(name, evidence[name])
    if (
        isinstance(evidence['revision'], bool)
        or not isinstance(evidence['revision'], int)
        or evidence['revision'] < 1
    ):
        _fail('INVALID_SCHEMA', 'Gmail revision must be positive')
    for name in ('draft_sha256', 'subject_sha256', 'plain_body_sha256', 'html_body_sha256'):
        _sha(name, evidence[name])
    if (
        not isinstance(evidence['gmail_internal_date'], str)
        or not evidence['gmail_internal_date'].isdigit()
        or not 12 <= len(evidence['gmail_internal_date']) <= 16
        or int(evidence['gmail_internal_date']) <= 0
    ):
        _fail('INVALID_SCHEMA', 'Gmail internalDate is invalid')
    if not isinstance(evidence['rfc_message_id'], str) or RFC_MESSAGE_ID_RE.fullmatch(
        evidence['rfc_message_id']
    ) is None:
        _fail('INVALID_SCHEMA', 'RFC Message-ID is invalid')
    if (
        evidence['authenticated_mailbox'] != 'norbert@bmasiamusic.com'
        or evidence['visible_from'] != 'nikki.h@bmasiamusic.com'
    ):
        _fail('FORBIDDEN', 'Gmail mailbox or visible sender differs')
    try:
        sent_at = datetime.fromisoformat(evidence['sent_at'].replace('Z', '+00:00'))
        internal_ms = int(evidence['gmail_internal_date'])
        internal_at = datetime.fromtimestamp(
            internal_ms // 1000, tz=datetime_timezone.utc
        ).replace(microsecond=(internal_ms % 1000) * 1000)
    except (AttributeError, OSError, OverflowError, TypeError, ValueError):
        _fail('INVALID_SCHEMA', 'Gmail sent_at is invalid')
    if sent_at.tzinfo is None or sent_at.astimezone(datetime_timezone.utc) != internal_at:
        _fail('EVIDENCE_CHANGED', 'Gmail sent_at differs from exact internalDate')
    for name in ('to', 'cc'):
        if not isinstance(evidence[name], list) or any(
            not isinstance(item, str) or MAILBOX_RE.fullmatch(item) is None
            for item in evidence[name]
        ):
            _fail('INVALID_SCHEMA', f'Gmail {name} recipients are invalid')
    if not evidence['to'] or len(evidence['to'] + evidence['cc']) != len(
        {item.casefold() for item in evidence['to'] + evidence['cc']}
    ):
        _fail('INVALID_SCHEMA', 'Gmail recipients are missing or duplicated')
    attachment = _exact(
        'Gmail attachment', evidence['attachment'], {'filename', 'sha256', 'size_bytes'}
    )
    _filename(attachment['filename'])
    _sha('Gmail attachment sha256', attachment['sha256'])
    if (
        isinstance(attachment['size_bytes'], bool)
        or not isinstance(attachment['size_bytes'], int)
        or not 9 <= attachment['size_bytes'] <= MAX_PDF_BYTES
    ):
        _fail('INVALID_SCHEMA', 'Gmail attachment size is invalid')
    _sha('Gmail evidence hash', expected_hash)
    if canonical_sha256(evidence) != expected_hash:
        _fail('HASH_MISMATCH', 'Gmail Sent evidence hash is invalid')
    return evidence


def _validate_record_sent(envelope, lock=False):
    intent = _exact(
        'record-sent intent',
        envelope['data']['intent'],
        {
            'prepared_verification', 'prepared_contract', 'gmail_sent_evidence',
            'gmail_sent_evidence_sha256', 'mutation',
        },
    )
    reference = _exact(
        'prepared verification reference',
        intent['prepared_verification'],
        {'request_id', 'request_key', 'intent_sha256', 'receipt_binding_sha256'},
    )
    record = ReneCiraRequest.objects.filter(
        request_id=reference['request_id'],
        request_key=reference['request_key'],
        intent_sha256=reference['intent_sha256'],
        operation='verify_prepared_contract',
        state='succeeded',
    ).first()
    if record is None or not isinstance(record.receipt, dict):
        _fail('MISSING_EVIDENCE', 'record-sent lacks a received live verification')
    if _receipt_binding(record.receipt) != reference['receipt_binding_sha256']:
        _fail('EVIDENCE_CHANGED', 'live verification receipt binding differs')
    if intent['prepared_contract'] != record.receipt.get('prepared_contract'):
        _fail('EVIDENCE_CHANGED', 'record-sent prepared contract differs')
    gmail = _validate_gmail_evidence(
        intent['gmail_sent_evidence'], intent['gmail_sent_evidence_sha256']
    )
    metadata = _load_prepared(envelope['id'], lock=lock)
    prepared = _verify_metadata_live(
        metadata,
        envelope['expected_version'],
        intent['prepared_contract'],
        lock=lock,
    )
    attachment = gmail['attachment']
    if attachment != {
        'filename': metadata.pdf_filename,
        'sha256': metadata.pdf_sha256,
        'size_bytes': len(bytes(metadata.pdf_content)),
    }:
        _fail('EVIDENCE_CHANGED', 'Gmail attachment differs from live Cira PDF')
    expected_mutation = {
        'field': 'state',
        'from': 'ready_for_review',
        'to': 'Sent',
        'contract_number_must_remain': prepared['contract_number'],
        'source_contract_must_not_change': {
            'contract_id': prepared['source_contract_id'],
            'version': str(prepared['source_contract_version']),
            'updated_at': prepared['source_contract_updated_at'],
            'status': prepared['source_contract_status'],
        },
    }
    if intent['mutation'] != expected_mutation:
        _fail('INVALID_SCHEMA', 'record-sent mutation exceeds the reviewed transition')
    policy = _reviewed_post_send_policy(_reviewed_policy(lock=lock))
    return metadata, prepared, gmail, policy


def _execute_record_sent(envelope):
    _require_validation(envelope)
    metadata, prepared, gmail, policy = _validate_record_sent(envelope, lock=True)
    before = _prepared_live_state(prepared)
    number = metadata.contract.contract_number
    metadata.contract.status = 'Sent'
    metadata.contract.save()
    metadata.contract.refresh_from_db()
    if metadata.contract.contract_number != number:
        _fail('EVIDENCE_CHANGED', 'final contract number changed on Sent')
    metadata.state = 'Sent'
    metadata.gmail_sent_evidence_sha256 = envelope['data']['intent'][
        'gmail_sent_evidence_sha256'
    ]
    metadata.post_send_policy_id = policy.post_send_policy_id
    metadata.post_send_policy_rule = policy.post_send_rule
    metadata.post_send_policy_evidence_sha256 = policy.post_send_evidence_sha256
    metadata.post_send_policy_source_ref = policy.post_send_source_ref
    metadata.post_send_policy_source_label = policy.post_send_source_label
    metadata.post_send_policy_revision = policy.post_send_revision
    metadata.save(
        update_fields=[
            'state', 'gmail_sent_evidence_sha256', 'post_send_policy_id',
            'post_send_policy_rule', 'post_send_policy_evidence_sha256',
            'post_send_policy_source_ref', 'post_send_policy_source_label',
            'post_send_policy_revision', 'updated_at',
        ]
    )
    metadata.source_contract.refresh_from_db()
    if (
        contract_version(metadata.source_contract) != metadata.source_contract_version
        or rfc3339(metadata.source_contract.updated_at)
        != rfc3339(metadata.source_contract_updated_at)
        or metadata.source_contract.status != metadata.source_contract_status
    ):
        _fail('SOURCE_LIFECYCLE_CHANGED', 'post-send bookkeeping changed the source')
    after = _prepared_live_state(
        _prepared_mapping(metadata),
        gmail_hash=metadata.gmail_sent_evidence_sha256,
    )
    if after['version'] == before['version']:
        _fail('EVIDENCE_CHANGED', 'Sent transition did not produce a new draft version')
    return _receipt_base(
        envelope, 'prepared_contract_marked_sent', before, after, None
    )


def _validate_fill(envelope, lock=False):
    intent = _exact(
        'fill intent',
        envelope['data']['intent'],
        {'target_company_id', 'crm_before', 'sheet_evidence', 'mutation'},
    )
    crm_before = _exact(
        'CRM before', intent['crm_before'],
        {'contract_id', 'company_id', 'version', 'end_date'},
    )
    sheet = _exact(
        'sheet evidence', intent['sheet_evidence'],
        {'spreadsheet_id', 'tab', 'row', 'column', 'value', 'sha256'},
    )
    mutation = _exact(
        'fill mutation', intent['mutation'], {'field', 'from', 'to'}
    )
    if (
        intent['target_company_id'] != crm_before['company_id']
        or crm_before['contract_id'] != envelope['id']
        or str(crm_before['version']) != envelope['expected_version']
        or crm_before['end_date'] is not None
        or sheet['column'] != 'E'
        or mutation != {'field': 'end_date', 'from': None, 'to': sheet['value']}
    ):
        _fail('INVALID_SCHEMA', 'fill is not the exact null to Sheet E transition')
    _token('spreadsheet_id', sheet['spreadsheet_id'])
    _token('sheet tab', sheet['tab'])
    if isinstance(sheet['row'], bool) or not isinstance(sheet['row'], int) or sheet['row'] < 2:
        _fail('INVALID_SCHEMA', 'sheet row must identify one data row')
    _sha('sheet evidence sha256', sheet['sha256'])
    renewal_date = _date('Sheet renewal date', sheet['value'])
    contract_query = Contract.objects.select_related('company')
    if lock:
        contract_query = contract_query.select_for_update()
    contract = contract_query.get(pk=envelope['id'])
    if (
        str(contract.company_id) != crm_before['company_id']
        or contract_version(contract) != envelope['expected_version']
    ):
        _fail('VERSION_CONFLICT', 'CRM contract identity or version changed')
    if contract.end_date is not None:
        _fail('CONTRADICTION', 'CRM end_date is no longer blank; overwrite is forbidden')
    return contract, renewal_date


def _execute_fill(envelope):
    _require_validation(envelope)
    contract, renewal_date = _validate_fill(envelope, lock=True)
    before = {
        'contract_id': str(contract.id),
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
        'end_date': None,
    }
    contract.end_date = renewal_date
    contract.save(update_fields=['end_date', 'updated_at'])
    contract.refresh_from_db()
    after = {
        'contract_id': str(contract.id),
        'company_id': str(contract.company_id),
        'version': contract_version(contract),
        'end_date': contract.end_date.isoformat(),
    }
    return _receipt_base(envelope, 'renewal_date_filled', before, after, None)


def _validation_before(proposed):
    operation = proposed['verb']
    if operation == 'prepare_renewal_contract':
        contract, _, _, _, _ = _validate_prepare(proposed)
        return _versioned_contract(contract, include_status=True)
    if operation == 'record_prepared_contract_sent':
        metadata, prepared, _, _ = _validate_record_sent(proposed)
        return _prepared_live_state(prepared)
    if operation == 'fill_blank_renewal_date':
        contract, _ = _validate_fill(proposed)
        return {
            'contract_id': str(contract.id),
            'company_id': str(contract.company_id),
            'version': contract_version(contract),
            'end_date': None,
        }
    _fail('FORBIDDEN', 'validate_only target operation is not allowlisted')


def _execute_validate(envelope):
    intent = _exact(
        'validate-only intent',
        envelope['data']['intent'],
        {
            'target_operation', 'target_request_key', 'target_intent_sha256',
            'target_envelope', 'must_not_mutate',
        },
    )
    if intent['must_not_mutate'] is not True:
        _fail('INVALID_SCHEMA', 'validate_only must_not_mutate is required')
    proposed = _parse_envelope(intent['target_envelope'])
    if (
        proposed['verb'] != intent['target_operation']
        or proposed['request_key'] != intent['target_request_key']
        or proposed['intent_sha256'] != intent['target_intent_sha256']
        or proposed['id'] != envelope['id']
        or proposed['expected_version'] != envelope['expected_version']
    ):
        _fail('HASH_MISMATCH', 'validated target differs from the sealed proposal')
    before = _validation_before(proposed)
    return _receipt_base(envelope, 'validated', before, dict(before), None)


def _require_validation(envelope):
    record = ReneCiraRequest.objects.filter(
        operation='validate_only',
        state='succeeded',
        target_request_key=envelope['request_key'],
        target_intent_sha256=envelope['intent_sha256'],
    ).first()
    if record is None:
        _fail('MISSING_VALIDATION', 'operation lacks its exact successful validate_only receipt')


def _execute(envelope):
    operation = envelope['verb']
    if operation == 'inspect_renewal_source_candidates':
        return _source_candidates_inspection(envelope)
    if operation == 'inspect_renewal_source':
        return _source_inspection(envelope)
    if operation == 'validate_only':
        return _execute_validate(envelope)
    if operation == 'prepare_renewal_contract':
        return _execute_prepare(envelope)
    if operation == 'verify_prepared_contract':
        return _execute_verify(envelope)
    if operation == 'record_prepared_contract_sent':
        return _execute_record_sent(envelope)
    if operation == 'fill_blank_renewal_date':
        return _execute_fill(envelope)
    _fail('FORBIDDEN', 'operation is not allowlisted')


def execute_rene_request(value, *, crm_mcp_invoked=False):
    """Execute or reconcile one exact request without replaying an effect.

    ``crm_mcp_invoked`` is transport evidence, not caller-controlled request
    data.  Only the dedicated MCP adapter sets it true.  A typed operation
    rejection is persisted after the operation transaction rolls back and is
    terminal: the same request can be looked up but can never be reopened.
    """

    if not isinstance(crm_mcp_invoked, bool):
        raise TypeError('crm_mcp_invoked must be a boolean transport fact')

    envelope = _parse_envelope(value)
    envelope_hash = canonical_sha256(envelope)
    target_key = ''
    target_hash = ''
    if envelope['verb'] == 'validate_only':
        target_key = str(envelope['data']['intent'].get('target_request_key', ''))
        target_hash = str(envelope['data']['intent'].get('target_intent_sha256', ''))
    with transaction.atomic():
        journal = None
        by_id = ReneCiraRequest.objects.select_for_update().filter(
            request_id=envelope['request_id']
        ).first()
        if by_id is not None:
            if (
                by_id.request_key != envelope['request_key']
                or by_id.intent_sha256 != envelope['intent_sha256']
                or by_id.canonical_envelope_sha256 != envelope_hash
            ):
                _raise_bound_error(
                    envelope,
                    'REQUEST_ID_COLLISION',
                    'request ID was reused with another payload',
                    outcome='collision',
                    boundary='crm_request_admission',
                    crm_mcp_invoked=crm_mcp_invoked,
                    transaction_committed=False,
                    effect_persisted=False,
                    request_state='collision',
                )
            if by_id.state == 'succeeded' and isinstance(by_id.receipt, dict):
                return by_id.receipt
            terminal = _stored_terminal_rejection(by_id)
            if by_id.state == 'failed' and terminal is not None:
                raise RenePhase2BoundError(terminal)
            _raise_bound_error(
                envelope,
                'REQUEST_PENDING',
                'request was already accepted and cannot be replayed',
                outcome='accepted_or_unknown',
                boundary='crm_request_journal',
                crm_mcp_invoked=crm_mcp_invoked,
                transaction_committed=None,
                effect_persisted=None,
                request_state=by_id.state,
            )
        if journal is None:
            by_key = ReneCiraRequest.objects.select_for_update().filter(
                request_key=envelope['request_key']
            ).first()
            if by_key is not None:
                # The reviewed dedupe contract deliberately treats a content key
                # as the operation identity. A different caller-generated ID
                # must never receive the original ID-bound receipt and must
                # never repeat the effect. Its prior-effect state is unknown to
                # this new identity, even when the original request succeeded.
                if (
                    by_key.intent_sha256 != envelope['intent_sha256']
                    or by_key.operation != envelope['verb']
                ):
                    _raise_bound_error(
                        envelope,
                        'REQUEST_KEY_COLLISION',
                        'request key was reused with another payload',
                        outcome='collision',
                        boundary='crm_request_admission',
                        crm_mcp_invoked=crm_mcp_invoked,
                        transaction_committed=False,
                        effect_persisted=False,
                        request_state='collision',
                    )
                _raise_bound_error(
                    envelope,
                    'REQUEST_KEY_IDENTITY_MISMATCH',
                    'request key belongs to another request ID and cannot be replayed',
                    outcome='existing_request_identity',
                    boundary='crm_request_journal',
                    crm_mcp_invoked=crm_mcp_invoked,
                    transaction_committed=None,
                    effect_persisted=None,
                    request_state=by_key.state,
                )
            try:
                journal = ReneCiraRequest.objects.create(
                    request_id=envelope['request_id'],
                    request_key=envelope['request_key'],
                    intent_sha256=envelope['intent_sha256'],
                    operation=envelope['verb'],
                    envelope=envelope,
                    canonical_envelope_sha256=envelope_hash,
                    state='accepted',
                    target_request_key=target_key,
                    target_intent_sha256=target_hash,
                )
            except IntegrityError:
                _raise_bound_error(
                    envelope,
                    'REQUEST_COLLISION',
                    'request was accepted concurrently',
                    outcome='accepted_or_unknown',
                    boundary='crm_request_admission',
                    crm_mcp_invoked=crm_mcp_invoked,
                    transaction_committed=None,
                    effect_persisted=None,
                    request_state='unknown',
                )
    try:
        with transaction.atomic():
            locked = ReneCiraRequest.objects.select_for_update().get(pk=journal.pk)
            if locked.state != 'accepted':
                _fail('REQUEST_PENDING', 'request is not in executable accepted state')
            receipt = _execute(envelope)
            locked.receipt = receipt
            locked.state = 'succeeded'
            locked.save(update_fields=['receipt', 'state', 'updated_at'])
            return receipt
    except RenePhase2Error as exc:
        terminal = _bound_error_receipt(
            envelope,
            exc.code,
            str(exc),
            schema=TERMINAL_REJECTION_SCHEMA,
            outcome='rejected_terminal',
            boundary='crm_atomic_rollback',
            crm_mcp_invoked=crm_mcp_invoked,
            transaction_committed=False,
            effect_persisted=False,
            request_state='failed',
        )
        updated = ReneCiraRequest.objects.filter(
            pk=journal.pk, state='accepted'
        ).update(
            state='failed',
            failure_code=exc.code,
            receipt=terminal,
            updated_at=timezone.now(),
        )
        if updated != 1:
            _raise_bound_error(
                envelope,
                'REQUEST_PENDING',
                'request state changed while recording a terminal rejection',
                outcome='accepted_or_unknown',
                boundary='crm_request_journal',
                crm_mcp_invoked=crm_mcp_invoked,
                transaction_committed=None,
                effect_persisted=None,
                request_state='unknown',
            )
        raise RenePhase2BoundError(terminal) from exc
    except (Contract.DoesNotExist, RenePreparedContract.DoesNotExist):
        exc = RenePhase2Error('NOT_FOUND', 'target contract was not found')
        terminal = _bound_error_receipt(
            envelope,
            exc.code,
            str(exc),
            schema=TERMINAL_REJECTION_SCHEMA,
            outcome='rejected_terminal',
            boundary='crm_atomic_rollback',
            crm_mcp_invoked=crm_mcp_invoked,
            transaction_committed=False,
            effect_persisted=False,
            request_state='failed',
        )
        updated = ReneCiraRequest.objects.filter(
            pk=journal.pk, state='accepted'
        ).update(
            state='failed',
            failure_code=exc.code,
            receipt=terminal,
            updated_at=timezone.now(),
        )
        if updated != 1:
            _raise_bound_error(
                envelope,
                'REQUEST_PENDING',
                'request state changed while recording a terminal rejection',
                outcome='accepted_or_unknown',
                boundary='crm_request_journal',
                crm_mcp_invoked=crm_mcp_invoked,
                transaction_committed=None,
                effect_persisted=None,
                request_state='unknown',
            )
        raise RenePhase2BoundError(terminal) from exc


def lookup_rene_receipt(value):
    lookup = _exact(
        'receipt lookup',
        value,
        {
            'schema', 'from', 'requesting_agent', 'operation', 'lookup_request_id',
            'original_request_id', 'original_request_key',
            'original_intent_sha256', 'original_operation', 'must_not_mutate',
        },
    )
    if (
        lookup['schema'] != LOOKUP_SCHEMA
        or lookup['from'] != AGENT
        or lookup['requesting_agent'] != AGENT
        or lookup['operation'] != 'receipt_lookup'
        or lookup['must_not_mutate'] is not True
        or lookup['original_operation'] not in ALLOWED_OPERATIONS
    ):
        _fail('FORBIDDEN', 'receipt lookup is outside Rene authority')
    _token('lookup_request_id', lookup['lookup_request_id'])
    _token('original_request_id', lookup['original_request_id'])
    _sha('original_intent_sha256', lookup['original_intent_sha256'])
    record = ReneCiraRequest.objects.filter(
        request_id=lookup['original_request_id'],
        request_key=lookup['original_request_key'],
        intent_sha256=lookup['original_intent_sha256'],
        operation=lookup['original_operation'],
    ).first()
    status = 'not_found'
    receipt = None
    if record is not None and record.state == 'succeeded' and isinstance(record.receipt, dict):
        status = 'found'
        receipt = record.receipt
    elif record is not None and record.state == 'failed':
        terminal = _stored_terminal_rejection(record)
        if terminal is not None:
            status = 'rejected_terminal'
            receipt = terminal
        else:
            status = 'pending'
    elif record is not None:
        status = 'pending'
    return {
        'schema': LOOKUP_SCHEMA,
        'lookup_request_id': lookup['lookup_request_id'],
        'requesting_agent': AGENT,
        'operation': 'receipt_lookup',
        'original_request_id': lookup['original_request_id'],
        'original_request_key': lookup['original_request_key'],
        'original_intent_sha256': lookup['original_intent_sha256'],
        'original_operation': lookup['original_operation'],
        'status': status,
        'receipt': receipt,
    }


def _materialize_receipt_artifact(receipt):
    """Attach PDF bytes to a wire copy without expanding the journal JSON."""

    portable_outcomes = {
        'prepare_renewal_contract': 'prepared',
        'verify_prepared_contract': 'prepared_contract_verified',
    }
    if (
        not isinstance(receipt, dict)
        or portable_outcomes.get(receipt.get('operation')) != receipt.get('outcome')
    ):
        return receipt
    artifact = receipt.get('artifact')
    prepared = receipt.get('prepared_contract')
    if not isinstance(artifact, dict) or not isinstance(prepared, dict):
        _fail('EVIDENCE_CHANGED', 'portable receipt artifact binding is missing')
    if set(artifact) != {'filename', 'sha256', 'size_bytes'}:
        _fail('EVIDENCE_CHANGED', 'stored receipt artifact descriptor differs')
    metadata = _load_prepared(prepared.get('contract_id'))
    if _artifact_descriptor(metadata) != artifact:
        _fail('EVIDENCE_CHANGED', 'stored receipt and prepared PDF artifact differ')
    wire = copy.deepcopy(receipt)
    wire['artifact'] = _portable_artifact(metadata)
    return wire


def materialize_rene_wire_response(value):
    """Materialize portable PDF bytes only for the scoped MCP response."""

    if not isinstance(value, dict):
        return value
    wire = copy.deepcopy(value)
    if wire.get('schema') == LOOKUP_SCHEMA:
        if isinstance(wire.get('receipt'), dict):
            wire['receipt'] = _materialize_receipt_artifact(wire['receipt'])
        return wire
    return _materialize_receipt_artifact(wire)


def safe_error(exc):
    if isinstance(exc, RenePhase2BoundError):
        return exc.receipt
    if isinstance(exc, RenePhase2Error):
        return {'error': {'code': exc.code, 'message': str(exc)}}
    return {'error': {'code': 'INTERNAL_ERROR', 'message': 'Rene operation failed safely'}}
