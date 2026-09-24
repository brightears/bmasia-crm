"""A Theo-root signature, not a model assertion, authorizes Sent bookkeeping."""

import base64
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import crm_app.contract_send_receipts as receipt_verifier
from crm_app.contract_send_receipts import SIGNING_PREFIX
from crm_app.mcp import update_record
from crm_app.models import Company, Contract, ContractSendReceiptUse, DocumentSequence
from crm_app.serializers import ContractSerializer


def _b64u(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _contract(number='HK-CT269999'):
    company = Company.objects.create(name=f'Signed receipt test company {number}')
    return Contract.objects.create(
        company=company, contract_number=number,
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('100.00'), total_value=Decimal('100.00'), status='Draft',
    )


def _signed_request(contract, monkeypatch, *, key=None, payload_overrides=None,
                    context_overrides=None, payload_bytes=None, signature=None):
    key = key or Ed25519PrivateKey.generate()
    der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_PUBLIC_DER_B64', base64.b64encode(der).decode('ascii'))
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_KEY_ID', hashlib.sha256(der).hexdigest())
    record = ContractSerializer(contract).data
    now = datetime.now(timezone.utc).replace(microsecond=0)
    provider_time = now - timedelta(minutes=1)
    sent_date = provider_time.astimezone(ZoneInfo('Asia/Bangkok')).date().isoformat()
    patch = {'status': 'Sent', 'sent_date': sent_date}
    proposal_id = 'test-proposal-v1'
    payload = {
        'domain': 'bmasia.contract-send.v1',
        'schema_version': 1,
        'issuer': 'theo-root-attestor',
        'audience': 'bmasia-crm-guarded-update',
        'key_id': hashlib.sha256(der).hexdigest(),
        'issued_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': (now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'nonce': str(uuid4()),
        'request_key': f'theo:renewal-sent:{proposal_id}',
        'proposal_id': proposal_id,
        'proposal_hash': 'a' * 64,
        'review_message_name': 'spaces/review-message',
        'approval_message_name': 'spaces/approval-message',
        'gmail_provider_message_id': 'provider-message-id',
        'gmail_internal_date_ms': int(provider_time.timestamp() * 1000),
        'evidence': {
            'gmail_raw_mime_sha256': '1' * 64,
            'approval_sha256': '2' * 64,
            'review_sha256': '3' * 64,
            'recipient_set_sha256': '4' * 64,
            'body_sha256': '5' * 64,
            'frozen_pdf_sha256': '6' * 64,
        },
        'record_id': str(contract.pk),
        'contract_number': contract.contract_number,
        'expected_version': record['updated_at'],
        'before': {'status': 'Draft', 'sent_date': None},
        'patch': patch,
    }
    payload.update(payload_overrides or {})
    payload_bytes = payload_bytes or json.dumps(
        payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
        allow_nan=False,
    ).encode('ascii')
    signature = signature or key.sign(SIGNING_PREFIX + payload_bytes)
    context = {
        'kind': 'signed_contract_send_bookkeeping',
        'receipt': {
            'payload_b64u': _b64u(payload_bytes),
            'signature_b64u': _b64u(signature),
        },
    }
    context.update(context_overrides or {})
    return record, patch, payload, context, key


def _update(contract, record, patch, context):
    return json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=record['updated_at'],
        expected_values=json.dumps({'status': 'Draft', 'sent_date': None}),
        authorization_context=json.dumps(context),
    ))


@pytest.mark.django_db
def test_signed_receipt_updates_once_without_email_or_new_number(monkeypatch):
    contract = _contract()
    record, patch, payload, context, _ = _signed_request(contract, monkeypatch)
    with mock.patch.object(DocumentSequence, 'get_next_number', side_effect=AssertionError('new number')), \
         mock.patch('crm_app.services.email_service.EmailService.send_contract_email',
                    side_effect=AssertionError('duplicate email')):
        result = _update(contract, record, patch, context)
    contract.refresh_from_db()
    use = ContractSendReceiptUse.objects.get(request_key=payload['request_key'])
    assert result['updated'] is True
    assert result['applied'] == patch
    assert result['contract_number'] == 'HK-CT269999'
    assert result['receipt_sha256'] == use.receipt_sha256
    assert result['post_version'] == use.after_version
    assert contract.status == 'Sent'
    assert contract.sent_date.isoformat() == patch['sent_date']
    assert contract.contract_number == 'HK-CT269999'
    assert ContractSendReceiptUse.objects.count() == 1


@pytest.mark.django_db
def test_exact_replay_is_readback_only_and_changed_state_holds(monkeypatch):
    contract = _contract()
    record, patch, _payload, context, _ = _signed_request(contract, monkeypatch)
    first = _update(contract, record, patch, context)
    replay = _update(contract, record, patch, context)
    assert first['updated'] is True
    assert replay['updated'] is False
    assert replay['already_applied'] is True
    assert ContractSendReceiptUse.objects.count() == 1
    contract.refresh_from_db()
    contract.notes = 'subsequent edit'
    contract.save()
    changed = _update(contract, record, patch, context)
    assert changed['updated'] is False
    assert 'conflicts' in changed['error']


@pytest.mark.django_db
@pytest.mark.parametrize('change', [
    {'domain': 'other'},
    {'audience': 'other'},
    {'issuer': 'other'},
    {'schema_version': True},
    {'nonce': 'not-a-uuid'},
    {'request_key': 'theo:renewal-sent:other'},
    {'contract_number': 'DRAFT-0001'},
    {'before': {'status': 'Sent', 'sent_date': None}},
    {'patch': {'status': 'Sent', 'sent_date': '2020-01-01'}},
    {'evidence': {'gmail_raw_mime_sha256': '0' * 64}},
])
def test_signed_receipt_rejects_wrong_purpose_or_binding(monkeypatch, change):
    contract = _contract()
    record, patch, _payload, context, _ = _signed_request(
        contract, monkeypatch, payload_overrides=change,
    )
    result = _update(contract, record, patch, context)
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.status == 'Draft'
    assert ContractSendReceiptUse.objects.count() == 0


@pytest.mark.django_db
def test_signed_receipt_rejects_tamper_bad_signature_and_unconfigured_key(monkeypatch):
    contract = _contract()
    record, patch, _payload, context, _ = _signed_request(contract, monkeypatch)
    original_signature = context['receipt']['signature_b64u']
    context['receipt']['signature_b64u'] = _b64u(b'\x00' * 64)
    assert _update(contract, record, patch, context)['updated'] is False
    context['receipt']['signature_b64u'] = original_signature
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_PUBLIC_DER_B64', '')
    assert _update(contract, record, patch, context)['updated'] is False
    assert ContractSendReceiptUse.objects.count() == 0


@pytest.mark.django_db
def test_signed_receipt_rejects_expired_and_noncanonical_payload(monkeypatch):
    contract = _contract()
    past = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    record, patch, _payload, context, _ = _signed_request(contract, monkeypatch, payload_overrides={
        'issued_at': past.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': (past + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    })
    assert _update(contract, record, patch, context)['updated'] is False
    record, patch, _payload, context, _ = _signed_request(
        contract, monkeypatch, payload_bytes=b'{"domain":"bmasia.contract-send.v1"}',
    )
    assert _update(contract, record, patch, context)['updated'] is False


@pytest.mark.django_db
def test_signed_receipt_rejects_stale_version_and_date_mismatch(monkeypatch):
    contract = _contract()
    record, patch, _payload, context, _ = _signed_request(contract, monkeypatch)
    contract.notes = 'concurrent edit'
    contract.save()
    assert _update(contract, record, patch, context)['updated'] is False
    contract2 = _contract(number='HK-CT269998')
    record2, patch2, _payload2, context2, _ = _signed_request(
        contract2, monkeypatch,
        payload_overrides={'gmail_internal_date_ms': 946684800000},
    )
    assert _update(contract2, record2, patch2, context2)['updated'] is False
    assert ContractSendReceiptUse.objects.count() == 0


@pytest.mark.django_db
def test_unguarded_mcp_contract_status_date_cannot_bypass_signature():
    contract = _contract()
    result = json.loads(update_record(
        'contract', str(contract.pk), json.dumps({'status': 'Sent', 'sent_date': '2026-09-09'}),
    ))
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.status == 'Draft'
    assert contract.sent_date is None


def test_theo_public_only_synthetic_fixture_verifies_across_implementations(monkeypatch):
    fixture = json.loads(
        Path(__file__).with_name('theo_contract_send_v1_fixture.json').read_text()
    )
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_PUBLIC_DER_B64', fixture['public_der_b64'])
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_KEY_ID', fixture['key_id'])
    context = {'kind': 'signed_contract_send_bookkeeping', 'receipt': fixture['receipt']}
    verified = receipt_verifier.verify_signed_contract_send_context(
        context,
        record_id='00000000-0000-4000-8000-000000000001',
        fields={'status': 'Sent', 'sent_date': '2026-01-01'},
        before={'status': 'Draft', 'sent_date': None},
        expected_version='2025-12-31T23:59:59.000000Z',
        now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
    )
    assert verified['payload']['key_id'] == fixture['key_id']
    assert verified['payload']['request_key'] == 'theo:renewal-sent:aaaaaaaaaaaaaaaaaaaa-v1'
    assert len(verified['receipt_sha256']) == 64
