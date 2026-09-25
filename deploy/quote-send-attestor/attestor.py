#!/usr/bin/env python3
"""Protected verifier for quote sends (Part B of guarded quote Sent bookkeeping).

Runs as root on the core VPS, outside every agent's writable workspace. Callers
are identified by the kernel (SO_PEERCRED), never by what they claim; every
other Unix account is refused (peer_not_allowed):

    bmasia   (Lyra) -> may only attest norbert@bmasiamusic.com sends
    theo_ai  (Theo) -> may only attest nikki.h@bmasiamusic.com sends

A request names one quote and one Gmail message. The attestor reads that exact
message from the caller's own mailbox (read-only token refresh, never written
back) and signs a short-lived receipt only if:

  * the message carries the SENT label and is From the mailbox address;
  * at least one To/Cc recipient is outside bmasiamusic.com;
  * an attached PDF's text contains the quote number (pdftotext);
  * it was sent within the last 90 days.

The CRM (crm_app/quote_send_receipts.py) then binds the receipt to the record,
its number, version, Draft/null before-values and the patch. Norbert decided
(2026-09-25) that the email in the sender's own Sent folder is the proof;
approvals themselves are not attested. No customer content, credential or
provider response is ever logged or returned — only typed refusal reasons.
"""
from __future__ import annotations

import base64
import email
import email.policy
import hashlib
import json
import os
import pwd
import re
import socket
import socketserver
import stat
import struct
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DOMAIN = "bmasia.quote-send.v1"
ISSUER = "bmasia-quote-attestor"
AUDIENCE = "bmasia-crm-guarded-update"
PREFIX = b"BMASIA-QUOTE-SEND-RECEIPT-v1\n"
KEY = Path("/etc/bmasia/quote-send-receipts/private.pem")
PUBLIC = Path("/etc/bmasia/quote-send-receipts/public.der")
SOCKET = Path("/run/bmasia-quote-send-receipt/attestor.sock")
INTERNAL_DOMAIN = "bmasiamusic.com"
MAX_AGE = timedelta(days=90)
RECEIPT_TTL = timedelta(minutes=10)
BANGKOK = ZoneInfo("Asia/Bangkok")

# Unix account -> (requester, mailbox, credential file). Fixed; not caller-selectable.
SENDERS = {
    "bmasia": ("lyra", "norbert@bmasiamusic.com",
               Path("/home/bmasia/.google_workspace_mcp/credentials_norbert/norbert@bmasiamusic.com.json")),
    "theo_ai": ("theo", "nikki.h@bmasiamusic.com",
                Path("/home/theo_ai/.google_workspace_mcp/credentials_nikki/nikki.h@bmasiamusic.com.json")),
}

QUOTE_NUMBER_RE = re.compile(r"^(?:HK|TH)-QT[0-9]{5,}$")
GMAIL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
# CRM updated_at as serialized by the API: UTC "Z" or an explicit offset (e.g. +07:00).
CRM_VERSION_RE = re.compile(r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9](?:\.[0-9]{1,6})?(?:Z|[+-][0-2][0-9]:[0-5][0-9])$")


class Hold(Exception):
    """A typed refusal without business data."""


def require(ok: object, reason: str) -> None:
    if not ok:
        raise Hold(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _regular(path: Path, owner: int | None = None, mode: int | None = None) -> bytes:
    """Read a regular file without following symlinks at any path component."""
    require(path.is_absolute() and all(part not in {".", ".."} for part in path.parts), "path_shape")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory = os.open("/", flags | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = following
        fd = os.open(path.name, flags, dir_fd=directory)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "not_regular")
            if owner is not None:
                require(info.st_uid == owner, "wrong_owner")
            if mode is not None:
                require(stat.S_IMODE(info.st_mode) == mode, "wrong_mode")
            require(info.st_size <= 1024 * 1024, "oversized_file")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                return handle.read(1024 * 1024 + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise Hold("path_open") from exc
    finally:
        os.close(directory)


def validate_request(request: object) -> dict:
    require(isinstance(request, dict)
            and set(request) == {"quote_id", "quote_number", "expected_version", "gmail_message_id"},
            "request_shape")
    try:
        parsed = uuid.UUID(str(request["quote_id"]))
    except (TypeError, ValueError, AttributeError):
        raise Hold("quote_id")
    require(str(parsed) == request["quote_id"], "quote_id")
    require(isinstance(request["quote_number"], str) and QUOTE_NUMBER_RE.fullmatch(request["quote_number"]),
            "quote_number")
    require(isinstance(request["expected_version"], str)
            and CRM_VERSION_RE.fullmatch(request["expected_version"]), "expected_version")
    require(isinstance(request["gmail_message_id"], str)
            and GMAIL_ID_RE.fullmatch(request["gmail_message_id"]), "gmail_message_id")
    return request


# ------------------------------------------------------------------ Gmail

def google_token(credentials_path: Path, owner_uid: int) -> str:
    credentials = json.loads(_regular(credentials_path, owner=owner_uid, mode=0o600))
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type": "refresh_token", "refresh_token": credentials["refresh_token"],
        "client_id": credentials["client_id"], "client_secret": credentials["client_secret"],
    }, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def gmail_json(token: str, path: str, params: dict | None = None) -> dict:
    response = requests.get("https://gmail.googleapis.com/gmail/v1/users/me/" + path,
                            headers={"Authorization": "Bearer " + token}, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    require(isinstance(data, dict), "provider_response")
    return data


def pdf_text(data: bytes) -> str:
    result = subprocess.run(["pdftotext", "-q", "-layout", "-", "-"], input=data,
                            capture_output=True, timeout=30, check=False)
    require(result.returncode == 0, "pdf_unreadable")
    return result.stdout.decode("utf-8", errors="replace")


def verify_sent_message(raw_message: dict, mailbox: str, quote_number: str, now: datetime) -> dict:
    """Pure check of a Gmail format=raw message resource. Returns evidence, or raises Hold."""
    require("SENT" in (raw_message.get("labelIds") or []), "not_in_sent")
    require("DRAFT" not in (raw_message.get("labelIds") or []), "is_draft")
    raw = raw_message.get("raw")
    require(isinstance(raw, str) and len(raw) < 40 * 1024 * 1024, "gmail_raw")
    mime = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    message = email.message_from_bytes(mime, policy=email.policy.default)
    require(len(message.get_all("From", [])) == 1, "from_header")
    sender = parseaddr(str(message["From"]))[1].casefold()
    require(sender == mailbox, "sender_mismatch")
    recipients = sorted({address.casefold() for _, address in
                         getaddresses([str(v) for h in ("To", "Cc") for v in message.get_all(h, [])])
                         if address})
    require(any(not r.endswith("@" + INTERNAL_DOMAIN) for r in recipients), "no_external_recipient")
    try:
        internal_ms = int(raw_message.get("internalDate"))
    except (TypeError, ValueError):
        raise Hold("provider_time")
    sent_at = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc)
    require(sent_at <= now + timedelta(minutes=1) and now - sent_at <= MAX_AGE, "send_time_window")
    matching_pdf = None
    for part in message.iter_attachments():
        filename = (part.get_filename() or "").casefold()
        if part.get_content_type() != "application/pdf" and not filename.endswith(".pdf"):
            continue
        data = part.get_payload(decode=True) or b""
        require(len(data) <= 20 * 1024 * 1024, "attachment_size")
        if quote_number in pdf_text(data):
            matching_pdf = data
            break
    require(matching_pdf is not None, "quote_pdf_not_attached")
    return {
        "internal_ms": internal_ms,
        "sent_date": sent_at.astimezone(BANGKOK).date().isoformat(),
        "evidence": {
            "gmail_raw_mime_sha256": sha(mime),
            "recipient_set_sha256": sha(canonical(recipients)),
            "quote_pdf_sha256": sha(matching_pdf),
        },
    }


def build_payload(request: dict, requester: str, mailbox: str, verified: dict,
                  message_id: str, key_id: str, now: datetime) -> dict:
    stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    issued = now.replace(microsecond=0)
    return {
        "domain": DOMAIN, "schema_version": 1, "issuer": ISSUER, "audience": AUDIENCE,
        "key_id": key_id, "issued_at": stamp(issued), "expires_at": stamp(issued + RECEIPT_TTL),
        "nonce": str(uuid.uuid4()),
        "request_key": f"{requester}:quote-sent:{request['quote_id']}",
        "requester": requester, "mailbox": mailbox,
        "gmail_provider_message_id": message_id,
        "gmail_internal_date_ms": verified["internal_ms"],
        "evidence": verified["evidence"],
        "record_id": request["quote_id"], "quote_number": request["quote_number"],
        "expected_version": request["expected_version"],
        "before": {"status": "Draft", "sent_date": None},
        "patch": {"status": "Sent", "sent_date": verified["sent_date"]},
    }


def sign_receipt(private: Ed25519PrivateKey, payload: dict) -> dict:
    data = canonical(payload)
    require(len(data) <= 8192, "receipt_size")
    signature = private.sign(PREFIX + data)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return {"payload_b64u": encode(data), "signature_b64u": encode(signature)}


def key_material() -> tuple[Ed25519PrivateKey, str]:
    private = serialization.load_pem_private_key(_regular(KEY, owner=0, mode=0o400), password=None)
    require(isinstance(private, Ed25519PrivateKey), "private_key_type")
    public = _regular(PUBLIC, owner=0, mode=0o644)
    expected = private.public_key().public_bytes(
        encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo)
    require(public == expected, "public_key_mismatch")
    return private, sha(public)


def peer_account(connection: socket.socket) -> str:
    creds = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        raise Hold("peer_unknown")


def attest(request: dict, account: str, private: Ed25519PrivateKey, key_id: str) -> dict:
    require(account in SENDERS, "peer_not_allowed")
    requester, mailbox, credentials = SENDERS[account]
    request = validate_request(request)
    token = google_token(credentials, pwd.getpwnam(account).pw_uid)
    profile = gmail_json(token, "profile")
    require(str(profile.get("emailAddress", "")).casefold() == mailbox, "gmail_identity")
    raw_message = gmail_json(token, "messages/" + request["gmail_message_id"], {"format": "raw"})
    now = datetime.now(timezone.utc)
    verified = verify_sent_message(raw_message, mailbox, request["quote_number"], now)
    payload = build_payload(request, requester, mailbox, verified,
                            request["gmail_message_id"], key_id, now)
    return sign_receipt(private, payload)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            self.connection.settimeout(120)
            account = peer_account(self.connection)
            raw = self.rfile.readline(4097)
            require(raw.endswith(b"\n") and len(raw) <= 4096, "request_size")
            receipt = attest(json.loads(raw), account, self.server.private, self.server.key_id)
            result = {"ok": True, "receipt": receipt}
        except Hold as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception as exc:
            # Never log credential, provider response, customer or request content.
            result = {"ok": False, "error": "verification_unavailable", "type": type(exc).__name__}
        self.wfile.write(canonical(result) + b"\n")


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def serve() -> None:
    private, key_id = key_material()
    directory = SOCKET.parent
    require(directory.is_dir() and directory.stat().st_uid == 0, "socket_directory")
    if SOCKET.exists() or SOCKET.is_symlink():
        require(stat.S_ISSOCK(SOCKET.lstat().st_mode) and SOCKET.lstat().st_uid == 0, "socket_path_invalid")
        SOCKET.unlink()
    with Server(str(SOCKET), Handler) as server:
        server.private, server.key_id = private, key_id
        server.slots = threading.BoundedSemaphore(4)
        # Authorization is the kernel peer UID (SENDERS); socket permissions are
        # open so long-running agent sessions need no new group membership.
        os.chmod(SOCKET, 0o666)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    serve()
