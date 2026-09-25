"""Pure tests for the quote attestor, including a cross-check with the CRM verifier."""
import base64
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import attestor  # noqa: E402
import crm_app.quote_send_receipts as crm_verifier  # noqa: E402  (no Django imports)

NOW = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
QUOTE_ID = str(uuid4())


@pytest.fixture(autouse=True)
def fake_pdftotext(monkeypatch):
    monkeypatch.setattr(attestor, "pdf_text", lambda data: data.decode("latin-1"))


def _message(*, sender="norbert@bmasiamusic.com", to="gm@hotel.example", pdf=b"%PDF quote HK-QT26154 total",
             labels=("SENT",), sent=NOW - timedelta(hours=2)):
    msg = EmailMessage()
    msg["From"] = f"Norbert <{sender}>"
    msg["To"] = to
    msg["Subject"] = "Quotation"
    msg.set_content("Please find the quotation attached.")
    if pdf is not None:
        msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="Quote.pdf")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {"labelIds": list(labels), "raw": raw, "internalDate": str(int(sent.timestamp() * 1000))}


def test_verified_send_evidence_and_bangkok_date():
    verified = attestor.verify_sent_message(_message(), "norbert@bmasiamusic.com", "HK-QT26154", NOW)
    assert verified["sent_date"] == "2026-09-25"
    assert set(verified["evidence"]) == {"gmail_raw_mime_sha256", "recipient_set_sha256", "quote_pdf_sha256"}


@pytest.mark.parametrize("kwargs, reason", [
    ({"labels": ("DRAFT",)}, "not_in_sent"),
    ({"sender": "nikki.h@bmasiamusic.com"}, "sender_mismatch"),
    ({"to": "pom@bmasiamusic.com"}, "no_external_recipient"),
    ({"pdf": None}, "quote_pdf_not_attached"),
    ({"pdf": b"%PDF quote HK-QT26155"}, "quote_pdf_not_attached"),
    ({"sent": NOW - timedelta(days=120)}, "send_time_window"),
])
def test_refusals(kwargs, reason):
    with pytest.raises(attestor.Hold, match=reason):
        attestor.verify_sent_message(_message(**kwargs), "norbert@bmasiamusic.com", "HK-QT26154", NOW)


@pytest.mark.parametrize("request_, reason", [
    ({"quote_id": QUOTE_ID}, "request_shape"),
    ({"quote_id": "not-a-uuid", "quote_number": "HK-QT26154", "expected_version": "2026-09-25T08:00:00Z",
      "gmail_message_id": "abc"}, "quote_id"),
    ({"quote_id": QUOTE_ID, "quote_number": "HK-CT26154", "expected_version": "2026-09-25T08:00:00Z",
      "gmail_message_id": "abc"}, "quote_number"),
    ({"quote_id": QUOTE_ID, "quote_number": "HK-QT26154", "expected_version": "yesterday",
      "gmail_message_id": "abc"}, "expected_version"),
])
def test_request_validation(request_, reason):
    with pytest.raises(attestor.Hold, match=reason):
        attestor.validate_request(request_)


def test_unlisted_unix_account_is_refused():
    with pytest.raises(attestor.Hold, match="peer_not_allowed"):
        attestor.attest({}, "riff_ai", None, "0" * 64)


def test_signed_receipt_is_accepted_by_the_crm_verifier(monkeypatch):
    key = Ed25519PrivateKey.generate()
    der = key.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                        format=serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = hashlib.sha256(der).hexdigest()
    monkeypatch.setattr(crm_verifier, "PRODUCTION_PUBLIC_DER_B64", base64.b64encode(der).decode("ascii"))
    monkeypatch.setattr(crm_verifier, "PRODUCTION_KEY_ID", key_id)
    now = datetime.now(timezone.utc)
    request = {"quote_id": QUOTE_ID, "quote_number": "HK-QT26154",
               "expected_version": "2026-09-25T08:14:37.123456Z", "gmail_message_id": "msg-1"}
    verified = attestor.verify_sent_message(_message(sent=now - timedelta(minutes=5)),
                                            "norbert@bmasiamusic.com", "HK-QT26154", now)
    payload = attestor.build_payload(request, "lyra", "norbert@bmasiamusic.com", verified,
                                     "msg-1", key_id, now)
    receipt = attestor.sign_receipt(key, payload)
    result = crm_verifier.verify_signed_quote_send_context(
        {"kind": "signed_quote_send_bookkeeping", "receipt": receipt},
        record_id=QUOTE_ID, fields=payload["patch"],
        before={"status": "Draft", "sent_date": None},
        expected_version=request["expected_version"],
    )
    assert result["payload"]["quote_number"] == "HK-QT26154"
    assert result["payload"]["request_key"] == f"lyra:quote-sent:{QUOTE_ID}"


@pytest.mark.parametrize("version", ["2026-09-25T10:06:49.661070+07:00", "2026-09-25T03:06:49Z"])
def test_crm_version_formats_are_accepted(version):
    request = {"quote_id": QUOTE_ID, "quote_number": "HK-QT26154",
               "expected_version": version, "gmail_message_id": "abc"}
    assert attestor.validate_request(request) is request
