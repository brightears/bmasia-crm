"""Verify Theo's root-attested contract-send receipt at the CRM write boundary.

This module validates an attestation, not the underlying Gmail or Chat data.
The protected Theo signer and Cira's forwarder own those independent checks.
"""

import base64
import binascii
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SIGNING_PREFIX = b'BMASIA-CONTRACT-SEND-RECEIPT-v1\n'
# Nonsecret Ed25519 public DER independently matched to Theo's root-owned
# public-only copy. Rotation requires a reviewed code change and redeploy.
PRODUCTION_PUBLIC_DER_B64 = 'MCowBQYDK2VwAyEA7rK8OiAUUhvFv+S5+dPGeKIot+BB6D8Hc6c44WRYD5A='
PRODUCTION_KEY_ID = '9dfca0f4ad7c73d934a3fff148401a7e220a7cbd580c67d2af247aec098ec138'
MAX_PAYLOAD_BYTES = 8192
_HEX_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_B64U = re.compile(r'[A-Za-z0-9_-]+\Z')
_FINAL_NUMBER = re.compile(r'(?:HK|TH)-CT[0-9]{5,}\Z')
_UTC_SECONDS = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')
_EVIDENCE_KEYS = frozenset({
    'gmail_raw_mime_sha256', 'approval_sha256', 'review_sha256',
    'recipient_set_sha256', 'body_sha256', 'frozen_pdf_sha256',
})
_PAYLOAD_KEYS = frozenset({
    'domain', 'schema_version', 'issuer', 'audience', 'key_id',
    'issued_at', 'expires_at', 'nonce', 'request_key', 'proposal_id',
    'proposal_hash', 'review_message_name', 'approval_message_name',
    'gmail_provider_message_id', 'gmail_internal_date_ms', 'evidence',
    'record_id', 'contract_number', 'expected_version', 'before', 'patch',
})


class ReceiptVerificationError(ValueError):
    """Fail closed without revealing receipt or key material to MCP clients."""


def _object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptVerificationError('duplicate receipt key')
        result[key] = value
    return result


def _reject_constant(_value):
    raise ReceiptVerificationError('non-finite receipt value')


def _decode_b64u(value, *, max_encoded):
    if not isinstance(value, str) or not value or len(value) > max_encoded or not _B64U.fullmatch(value):
        raise ReceiptVerificationError('invalid receipt encoding')
    try:
        decoded = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ReceiptVerificationError('invalid receipt encoding') from exc
    if base64.urlsafe_b64encode(decoded).rstrip(b'=').decode('ascii') != value:
        raise ReceiptVerificationError('non-canonical receipt encoding')
    return decoded


def _utc_second(value):
    if not isinstance(value, str) or not _UTC_SECONDS.fullmatch(value):
        raise ReceiptVerificationError('invalid receipt time')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReceiptVerificationError('invalid receipt time') from exc


def _opaque(value, *, max_len):
    return (
        isinstance(value, str) and 1 <= len(value) <= max_len
        and all(0x20 <= ord(char) <= 0x7e for char in value)
        and value.strip() == value
    )


def _canonical_uuid(value, *, version=None):
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value and (version is None or parsed.version == version)


def _load_pinned_public_key(key_id):
    configured = PRODUCTION_PUBLIC_DER_B64
    if not configured:
        raise ReceiptVerificationError('receipt public key is not configured')
    try:
        der = base64.b64decode(configured, validate=True)
        if base64.b64encode(der).decode('ascii') != configured:
            raise ValueError('non-canonical public key encoding')
        if key_id != PRODUCTION_KEY_ID or hashlib.sha256(der).hexdigest() != PRODUCTION_KEY_ID:
            raise ValueError('public key ID mismatch')
        public_key = serialization.load_der_public_key(der)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ReceiptVerificationError('receipt public key is invalid') from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise ReceiptVerificationError('receipt public key must be Ed25519')
    return public_key


def verify_signed_contract_send_context(
    context, *, record_id, fields, before, expected_version, now=None,
):
    """Return verified payload/digest, or reject before any CRM mutation."""
    if not isinstance(context, dict) or set(context) != {'kind', 'receipt'}:
        raise ReceiptVerificationError('signed receipt context shape is invalid')
    if context['kind'] != 'signed_contract_send_bookkeeping':
        raise ReceiptVerificationError('signed receipt context kind is invalid')
    receipt = context['receipt']
    if not isinstance(receipt, dict) or set(receipt) != {'payload_b64u', 'signature_b64u'}:
        raise ReceiptVerificationError('signed receipt envelope shape is invalid')
    payload_bytes = _decode_b64u(receipt['payload_b64u'], max_encoded=11000)
    signature = _decode_b64u(receipt['signature_b64u'], max_encoded=100)
    if len(payload_bytes) > MAX_PAYLOAD_BYTES or len(signature) != 64:
        raise ReceiptVerificationError('signed receipt size is invalid')
    try:
        payload = json.loads(
            payload_bytes.decode('ascii'), object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
        canonical = json.dumps(
            payload, sort_keys=True, separators=(',', ':'),
            ensure_ascii=True, allow_nan=False,
        ).encode('ascii')
    except (UnicodeDecodeError, ValueError, TypeError, OverflowError) as exc:
        raise ReceiptVerificationError('signed receipt payload is invalid JSON') from exc
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_KEYS or canonical != payload_bytes:
        raise ReceiptVerificationError('signed receipt payload is non-canonical or incomplete')
    if (payload['domain'] != 'bmasia.contract-send.v1'
            or type(payload['schema_version']) is not int or payload['schema_version'] != 1
            or payload['issuer'] != 'theo-root-attestor'
            or payload['audience'] != 'bmasia-crm-guarded-update'):
        raise ReceiptVerificationError('signed receipt purpose is invalid')
    key_id = payload['key_id']
    if not isinstance(key_id, str) or not _HEX_SHA256.fullmatch(key_id):
        raise ReceiptVerificationError('signed receipt key ID is invalid')

    issued = _utc_second(payload['issued_at'])
    expires = _utc_second(payload['expires_at'])
    now = now or datetime.now(timezone.utc)
    if (expires <= issued or expires - issued > timedelta(minutes=15)
            or issued - now > timedelta(minutes=1) or now >= expires):
        raise ReceiptVerificationError('signed receipt is not currently valid')
    if not _canonical_uuid(payload['nonce'], version=4):
        raise ReceiptVerificationError('signed receipt nonce is invalid')
    proposal_id = payload['proposal_id']
    if not _opaque(proposal_id, max_len=128) or not re.fullmatch(r'[A-Za-z0-9._:-]+', proposal_id):
        raise ReceiptVerificationError('signed receipt proposal ID is invalid')
    if payload['request_key'] != f'theo:renewal-sent:{proposal_id}' or len(payload['request_key']) > 256:
        raise ReceiptVerificationError('signed receipt request key is invalid')
    if not isinstance(payload['proposal_hash'], str) or not _HEX_SHA256.fullmatch(payload['proposal_hash']):
        raise ReceiptVerificationError('signed receipt proposal hash is invalid')
    for key in ('review_message_name', 'approval_message_name', 'gmail_provider_message_id'):
        if not _opaque(payload[key], max_len=512):
            raise ReceiptVerificationError('signed receipt source reference is invalid')
    evidence = payload['evidence']
    if not isinstance(evidence, dict) or set(evidence) != _EVIDENCE_KEYS or any(
        not isinstance(value, str) or not _HEX_SHA256.fullmatch(value)
        for value in evidence.values()
    ):
        raise ReceiptVerificationError('signed receipt evidence digest is invalid')
    if not _canonical_uuid(payload['record_id']) or payload['record_id'] != str(record_id):
        raise ReceiptVerificationError('signed receipt record ID is invalid')
    number = payload['contract_number']
    if not isinstance(number, str) or not _FINAL_NUMBER.fullmatch(number):
        raise ReceiptVerificationError('signed receipt contract number is invalid')
    if payload['expected_version'] != expected_version or not _opaque(expected_version, max_len=128):
        raise ReceiptVerificationError('signed receipt version binding is invalid')
    if payload['before'] != {'status': 'Draft', 'sent_date': None} or payload['before'] != before:
        raise ReceiptVerificationError('signed receipt before-value binding is invalid')
    patch = payload['patch']
    if (not isinstance(patch, dict) or set(patch) != {'status', 'sent_date'}
            or patch != fields or patch['status'] != 'Sent'):
        raise ReceiptVerificationError('signed receipt patch binding is invalid')
    sent_date = patch['sent_date']
    if not isinstance(sent_date, str):
        raise ReceiptVerificationError('signed receipt sent date is invalid')
    try:
        if date.fromisoformat(sent_date).isoformat() != sent_date:
            raise ValueError('non-canonical date')
    except ValueError as exc:
        raise ReceiptVerificationError('signed receipt sent date is invalid') from exc
    provider_ms = payload['gmail_internal_date_ms']
    if type(provider_ms) is not int or provider_ms < 946684800000 or provider_ms > 4102444800000:
        raise ReceiptVerificationError('signed receipt provider time is invalid')
    provider_time = datetime.fromtimestamp(provider_ms / 1000, tz=timezone.utc)
    if provider_time > issued + timedelta(minutes=1) or provider_time.astimezone(
        ZoneInfo('Asia/Bangkok')
    ).date().isoformat() != sent_date:
        raise ReceiptVerificationError('signed receipt provider date does not match patch')

    public_key = _load_pinned_public_key(key_id)
    signed_bytes = SIGNING_PREFIX + payload_bytes
    try:
        public_key.verify(signature, signed_bytes)
    except InvalidSignature as exc:
        raise ReceiptVerificationError('signed receipt signature is invalid') from exc
    return {
        'payload': payload,
        'receipt_sha256': hashlib.sha256(signed_bytes + signature).hexdigest(),
    }
