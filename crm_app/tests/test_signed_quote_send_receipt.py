"""A quote-attestor signature, not an agent assertion, authorizes quote Sent bookkeeping.

Mirrors test_signed_contract_send_receipt.py (Norbert 2026-09-25: same safeguards as contracts).
"""

import base64
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import crm_app.quote_send_receipts as receipt_verifier
from crm_app.mcp import update_record
from crm_app.models import Company, Quote, QuoteSendReceiptUse
from crm_app.quote_send_receipts import SIGNING_PREFIX
from crm_app.serializers import QuoteSerializer

pytestmark = pytest.mark.django_db


def _b64u(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _quote(number='HK-QT269999'):
    company = Company.objects.create(name=f'Signed quote receipt company {number}')
    return Quote.objects.create(
        company=company, quote_number=number, status='Draft',
        valid_from=date(2026, 9, 25), valid_until=date(2026, 10, 25),
    )


def _pin(monkeypatch, key):
    der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_PUBLIC_DER_B64', base64.b64encode(der).decode('ascii'))
    monkeypatch.setattr(receipt_verifier, 'PRODUCTION_KEY_ID', hashlib.sha256(der).hexdigest())
    return hashlib.sha256(der).hexdigest()


def _signed(quote, monkeypatch, *, key=None, pin=True, overrides=None, sign_with=None):
    key = key or Ed25519PrivateKey.generate()
    key_id = _pin(monkeypatch, key) if pin else 'f' * 64
    record = QuoteSerializer(quote).data
    now = datetime.now(timezone.utc).replace(microsecond=0)
    provider_time = now - timedelta(minutes=1)
    sent_date = provider_time.astimezone(ZoneInfo('Asia/Bangkok')).date().isoformat()
    patch = {'status': 'Sent', 'sent_date': sent_date}
    payload = {
        'domain': 'bmasia.quote-send.v1',
        'schema_version': 1,
        'issuer': 'bmasia-quote-attestor',
        'audience': 'bmasia-crm-guarded-update',
        'key_id': key_id,
        'issued_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': (now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'nonce': str(uuid4()),
        'request_key': f'lyra:quote-sent:{quote.pk}',
        'requester': 'lyra',
        'mailbox': 'norbert@bmasiamusic.com',
        'gmail_provider_message_id': 'provider-message-id',
        'gmail_internal_date_ms': int(provider_time.timestamp() * 1000),
        'evidence': {
            'gmail_raw_mime_sha256': '1' * 64,
            'recipient_set_sha256': '2' * 64,
            'quote_pdf_sha256': '3' * 64,
        },
        'record_id': str(quote.pk),
        'quote_number': quote.quote_number,
        'expected_version': record['updated_at'],
        'before': {'status': 'Draft', 'sent_date': None},
        'patch': patch,
    }
    payload.update(overrides or {})
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=True, allow_nan=False).encode('ascii')
    signature = (sign_with or key).sign(SIGNING_PREFIX + payload_bytes)
    context = {'kind': 'signed_quote_send_bookkeeping',
               'receipt': {'payload_b64u': _b64u(payload_bytes), 'signature_b64u': _b64u(signature)}}
    return record, patch, context, key


def _update(quote, record, patch, context, *, version=None, before=None):
    return json.loads(update_record(
        'quote', str(quote.pk), json.dumps(patch),
        expected_version=version or record['updated_at'],
        expected_values=json.dumps(before or {'status': 'Draft', 'sent_date': None}),
        authorization_context=json.dumps(context),
    ))


def test_unguarded_quote_sent_is_refused():
    quote = _quote()
    result = json.loads(update_record('quote', str(quote.pk), json.dumps({'status': 'Sent'})))
    assert result['updated'] is False and 'guarded send authorization' in result['error']
    quote.refresh_from_db()
    assert quote.status == 'Draft' and quote.sent_date is None


def test_guarded_status_only_patch_is_refused():
    quote = _quote()
    record = QuoteSerializer(quote).data
    result = json.loads(update_record('quote', str(quote.pk), json.dumps({'status': 'Sent'}),
                                      expected_version=record['updated_at'],
                                      expected_values=json.dumps({'status': 'Draft'})))
    assert 'outside the approved correction scope' in result['error']


def test_unconfigured_production_key_fails_closed():
    quote = _quote()
    record, patch, context, _ = _signed(quote, _NoPatch(), pin=False)
    result = _update(quote, record, patch, context)
    assert result['updated'] is False and 'not configured' in result['error']
    assert QuoteSendReceiptUse.objects.count() == 0


def test_valid_receipt_records_sent_once_and_replays_idempotently(monkeypatch):
    quote = _quote()
    record, patch, context, _ = _signed(quote, monkeypatch)
    first = _update(quote, record, patch, context)
    quote.refresh_from_db()
    assert quote.status == 'Sent' and quote.sent_date.isoformat() == patch['sent_date']
    assert first.get('already_applied') is not True
    use = QuoteSendReceiptUse.objects.get()
    assert (use.quote_id, use.mailbox, use.quote_number) == (quote.pk, 'norbert@bmasiamusic.com', 'HK-QT269999')
    replay = _update(quote, record, patch, context)
    assert replay['already_applied'] is True and replay['quote_number'] == 'HK-QT269999'
    assert QuoteSendReceiptUse.objects.count() == 1


def test_second_different_receipt_for_same_quote_conflicts(monkeypatch):
    quote = _quote()
    record, patch, context, key = _signed(quote, monkeypatch)
    _update(quote, record, patch, context)
    record2, patch2, context2, _ = _signed(quote, monkeypatch, key=key,
                                          overrides={'expected_version': record['updated_at']})
    result = _update(quote, record, patch2, context2)
    assert result['updated'] is False and 'conflicts' in result['error']
    assert QuoteSendReceiptUse.objects.count() == 1


@pytest.mark.parametrize('overrides, message', [
    ({'mailbox': 'nikki.h@bmasiamusic.com'}, 'sender identity'),
    ({'requester': 'theo'}, 'sender identity'),
    ({'mailbox': 'someone@example.com', 'requester': 'lyra'}, 'sender identity'),
    ({'quote_number': 'HK-QT260001'}, None),
    ({'domain': 'bmasia.contract-send.v1'}, 'purpose'),
    ({'before': {'status': 'Sent', 'sent_date': None}}, 'before-value'),
    ({'request_key': 'lyra:quote-sent:other'}, 'request key'),
])
def test_bindings_fail_closed(monkeypatch, overrides, message):
    quote = _quote()
    record, patch, context, _ = _signed(quote, monkeypatch, overrides=overrides)
    result = _update(quote, record, patch, context)
    assert result['updated'] is False
    if message:
        assert message in result['error']
    quote.refresh_from_db()
    assert quote.status == 'Draft' and QuoteSendReceiptUse.objects.count() == 0


def test_signature_from_another_key_is_refused(monkeypatch):
    quote = _quote()
    record, patch, context, _ = _signed(quote, monkeypatch, sign_with=Ed25519PrivateKey.generate())
    result = _update(quote, record, patch, context)
    assert 'signature is invalid' in result['error']


def test_contract_receipt_cannot_authorize_a_quote(monkeypatch):
    quote = _quote()
    record, patch, context, _ = _signed(quote, monkeypatch)
    context['kind'] = 'signed_contract_send_bookkeeping'
    result = _update(quote, record, patch, context)
    assert 'context kind is invalid' in result['error']


def test_stale_version_is_refused(monkeypatch):
    quote = _quote()
    record, patch, context, _ = _signed(quote, monkeypatch)
    result = _update(quote, record, patch, context, version='2020-01-01T00:00:00.000000Z')
    assert result['updated'] is False
    quote.refresh_from_db()
    assert quote.status == 'Draft'


class _NoPatch:
    """Monkeypatch stand-in that leaves the production (empty) key in place."""

    def setattr(self, *args, **kwargs):  # pragma: no cover - never pins
        raise AssertionError('must not pin a key in this test')
