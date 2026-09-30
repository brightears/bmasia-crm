"""The quote attestor's contract receipt lets Lyra record a norbert@ contract send.

Same safeguards as the quote and Theo contract receipts; its own domain and
signing prefix keep quote and contract receipts from standing in for each other.
"""

import base64
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import crm_app.quote_send_receipts as receipt_verifier
from crm_app.mcp import update_record
from crm_app.models import Company, Contract, ContractSendReceiptUse
from crm_app.serializers import ContractSerializer

pytestmark = pytest.mark.django_db

CONTRACT_PREFIX = b'BMASIA-CONTRACT-SEND-RECEIPT-v1\n'


def _b64u(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _contract(number='HK-CT269999'):
    company = Company.objects.create(name=f'Attested contract company {number}',
                                     billing_entity='BMAsia Limited')
    return Contract.objects.create(
        company=company, contract_number=number, contract_type='Annual', status='Draft',
        start_date=date(2026, 10, 15), end_date=date(2027, 10, 14), currency='USD',
        value=Decimal('520.00'), total_value=Decimal('520.00'),
    )


def _signed(contract, monkeypatch, *, overrides=None, prefix=CONTRACT_PREFIX, kind=None, sign_with=None):
    key = Ed25519PrivateKey.generate()
    der = key.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                        format=serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = hashlib.sha256(der).hexdigest()
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_PUBLIC_DER_B64', base64.b64encode(der).decode('ascii'))
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_KEY_ID', key_id)
    record = ContractSerializer(contract).data
    now = datetime.now(timezone.utc).replace(microsecond=0)
    provider_time = now - timedelta(minutes=1)
    sent_date = provider_time.astimezone(ZoneInfo('Asia/Bangkok')).date().isoformat()
    patch = {'status': 'Sent', 'sent_date': sent_date}
    payload = {
        'domain': 'bmasia.contract-send.v1', 'schema_version': 1,
        'issuer': 'bmasia-quote-attestor', 'audience': 'bmasia-crm-guarded-update',
        'key_id': key_id,
        'issued_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': (now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'nonce': str(uuid4()),
        'request_key': f'lyra:contract-sent:{contract.pk}',
        'requester': 'lyra', 'mailbox': 'norbert@bmasiamusic.com',
        'gmail_provider_message_id': 'provider-message-id',
        'gmail_internal_date_ms': int(provider_time.timestamp() * 1000),
        'evidence': {'gmail_raw_mime_sha256': '1' * 64, 'recipient_set_sha256': '2' * 64,
                     'contract_pdf_sha256': '3' * 64},
        'record_id': str(contract.pk), 'contract_number': contract.contract_number,
        'expected_version': record['updated_at'],
        'before': {'status': 'Draft', 'sent_date': None}, 'patch': patch,
    }
    payload.update(overrides or {})
    data = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')
    signature = (sign_with or key).sign(prefix + data)
    context = {'kind': kind or 'attested_contract_send_bookkeeping',
               'receipt': {'payload_b64u': _b64u(data), 'signature_b64u': _b64u(signature)}}
    return record, patch, context


def _update(contract, record, patch, context):
    return json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=record['updated_at'],
        expected_values=json.dumps({'status': 'Draft', 'sent_date': None}),
        authorization_context=json.dumps(context),
    ))


def test_valid_receipt_records_sent_once_and_keeps_the_number(monkeypatch):
    contract = _contract()
    record, patch, context = _signed(contract, monkeypatch)
    first = _update(contract, record, patch, context)
    assert first['updated'] is True, first
    contract.refresh_from_db()
    assert contract.status == 'Sent' and contract.sent_date.isoformat() == patch['sent_date']
    assert contract.contract_number == 'HK-CT269999'
    use = ContractSendReceiptUse.objects.get()
    assert use.request_key == f'lyra:contract-sent:{contract.pk}'
    replay = _update(contract, record, patch, context)
    assert replay['already_applied'] is True
    assert ContractSendReceiptUse.objects.count() == 1


@pytest.mark.parametrize('overrides, message', [
    ({'mailbox': 'nikki.h@bmasiamusic.com'}, 'sender identity'),
    ({'requester': 'theo'}, 'sender identity'),
    ({'domain': 'bmasia.quote-send.v1'}, 'purpose'),
    ({'contract_number': 'DRAFT-0185'}, 'contract number'),
    ({'request_key': 'lyra:quote-sent:other'}, 'request key'),
    ({'before': {'status': 'Sent', 'sent_date': None}}, 'before-value'),
])
def test_bindings_fail_closed(monkeypatch, overrides, message):
    contract = _contract()
    record, patch, context = _signed(contract, monkeypatch, overrides=overrides)
    result = _update(contract, record, patch, context)
    assert result['updated'] is False
    assert message in result['error']
    contract.refresh_from_db()
    assert contract.status == 'Draft' and not ContractSendReceiptUse.objects.exists()


def test_quote_signing_prefix_cannot_authorize_a_contract(monkeypatch):
    contract = _contract()
    record, patch, context = _signed(contract, monkeypatch, prefix=b'BMASIA-QUOTE-SEND-RECEIPT-v1\n')
    result = _update(contract, record, patch, context)
    assert 'signature is invalid' in result['error']
    contract.refresh_from_db()
    assert contract.status == 'Draft'


def test_quote_receipt_kind_cannot_authorize_a_contract(monkeypatch):
    contract = _contract()
    record, patch, context = _signed(contract, monkeypatch, kind='signed_quote_send_bookkeeping')
    result = _update(contract, record, patch, context)
    assert result['updated'] is False
    assert 'does not apply to contract' in result['error']


def test_draft_numbered_contract_cannot_be_recorded_sent(monkeypatch):
    contract = _contract(number='DRAFT-0185')
    record, patch, context = _signed(contract, monkeypatch)
    result = _update(contract, record, patch, context)
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.status == 'Draft' and contract.contract_number == 'DRAFT-0185'


def test_stale_version_is_refused(monkeypatch):
    contract = _contract()
    record, patch, context = _signed(contract, monkeypatch)
    contract.notes = 'changed elsewhere'
    contract.save()
    result = _update(contract, record, patch, context)
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.status == 'Draft'
