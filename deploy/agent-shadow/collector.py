#!/usr/bin/env python3
"""Authenticated local report collector. This release accepts SYNTHETIC ONLY.

No Django, CRM connection, model, mail, HTTP or producer-supplied context.
Kernel peer credentials authenticate Unix accounts, not people or factual truth.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import socket
import sqlite3
import stat
import struct
import time
import uuid

MAX_REQUEST = 32768
MAX_RESPONSE = 131072
UID_AGENT = {1008: "theo", 1000: "lyra", 1007: "riff", 1004: "nina"}
UID_ACCOUNT = {1008: "theo_ai", 1000: "bmasia", 1007: "riff_ai", 1004: "nina"}
CONFIG_KEYS = {"schema", "environment", "socket_path", "state_directory", "fixture_registry", "core_path"}
SAFE_FLAGS = {"customer_record_mutation": False, "customer_outbound": False,
              "model_invoked": False, "crm_writes": 0, "network_egress": False}


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def decode_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def invalid(_value):
        raise ValueError("nonfinite_json")
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_json") from exc


def trusted_file(path, maximum):
    """Configuration is installed by the operator; peers cannot choose paths."""
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("trusted_file_path_invalid")
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o022:
            raise ValueError("trusted_file_permissions_invalid")
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("trusted_file_too_large")
    return content


def verify_accounts():
    if not hasattr(socket, "SO_PEERCRED"):
        raise ValueError("linux_peer_credentials_required")
    for uid, account in UID_ACCOUNT.items():
        if pwd.getpwnam(account).pw_uid != uid:
            raise ValueError("runtime_uid_changed_revalidate_configuration")


def receive_exact(connection, length, deadline=None):
    chunks = bytearray()
    while len(chunks) < length:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("frame_deadline_exceeded")
            connection.settimeout(remaining)
        piece = connection.recv(length - len(chunks))
        if not piece:
            raise ValueError("truncated_frame")
        chunks.extend(piece)
    return bytes(chunks)


def receive_frame(connection):
    deadline = time.monotonic() + 0.2
    length = struct.unpack("!I", receive_exact(connection, 4, deadline))[0]
    if not 0 < length <= MAX_REQUEST:
        raise ValueError("request_size_invalid")
    return receive_exact(connection, length, deadline)


def send_frame(connection, receipt):
    raw = json_bytes(receipt)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("response_size_invalid")
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def peer_identity(connection):
    return struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                    struct.calcsize("3i")))


class ChannelAudit:
    """Durable metadata and bound synthetic receipt; never stores rejected input."""
    def __init__(self, directory):
        self.path = Path(directory) / "channel-audit.sqlite3"
        if self.path.is_symlink():
            raise ValueError("audit_symlink_refused")
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        with self.connect() as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables - {"channel_receipts", "channel_requests"}:
                raise ValueError("foreign_audit_database_refused")
            db.execute("CREATE TABLE IF NOT EXISTS channel_receipts (receipt_id TEXT PRIMARY KEY, receipt_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS channel_requests (request_id TEXT PRIMARY KEY, peer_uid INTEGER NOT NULL, outcome TEXT NOT NULL, reason TEXT, receipt_id TEXT, received_at TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def record(self, request_id, uid, receipt, now):
        with self.connect() as db:
            # Bounded SYNTHETIC request metadata, not a lifetime denial switch.
            # Immutable bound receipts are kept separately and never rotated.
            db.execute("DELETE FROM channel_requests WHERE rowid IN (SELECT rowid FROM channel_requests ORDER BY rowid DESC LIMIT -1 OFFSET 9999)")
            if receipt.get("receipt_id"):
                db.execute("INSERT OR IGNORE INTO channel_receipts VALUES (?,?)",
                           (receipt["receipt_id"], json_bytes(receipt).decode()))
            db.execute("INSERT INTO channel_requests VALUES (?,?,?,?,?,?)",
                       (request_id, uid, receipt["outcome"], receipt.get("reason"),
                        receipt.get("receipt_id"), now.isoformat()))
        # Both shadow result and this audit commit before the response is sent.

    def summary(self):
        with self.connect() as db:
            counts = dict(db.execute("SELECT outcome,count(*) FROM channel_requests GROUP BY outcome"))
            identities = [dict(zip(("peer_uid", "outcome", "count"), row)) for row in
                          db.execute("SELECT peer_uid,outcome,count(*) FROM channel_requests GROUP BY peer_uid,outcome")]
        return {"outcomes": counts, "identity_results": identities}


class Collector:
    def __init__(self, config):
        if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
            raise ValueError("invalid_configuration")
        if config["schema"] != "bmasia.agent-channel-config.v1" or config["environment"] != "synthetic":
            raise ValueError("only_synthetic_mode_is_implemented")
        for key in CONFIG_KEYS - {"schema", "environment"}:
            if not isinstance(config[key], str) or not Path(config[key]).is_absolute():
                raise ValueError("configuration_paths_must_be_absolute")
        self.config = config
        state = Path(config["state_directory"])
        if state.is_symlink() or not state.is_dir() or state.stat().st_uid != os.geteuid() or state.stat().st_mode & 0o077:
            raise ValueError("state_directory_must_be_private_and_owned")
        trusted_file(config["core_path"], 100000)
        spec = importlib.util.spec_from_file_location("agent_shadow_core", config["core_path"])
        self.core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.core)
        self.fixtures = self._fixtures(config["fixture_registry"])
        self.ledger = self.core.ShadowLedger(state / "shadow.sqlite3")
        self.audit = ChannelAudit(state)
        self.rates = defaultdict(deque)
        self.stopping = False

    def _fixtures(self, path):
        bundle = decode_json(trusted_file(path, 262144))
        expected = {"schema", "environment", "generated_at", "reports", "evidence"}
        if not isinstance(bundle, dict) or set(bundle) != expected or bundle["schema"] != "bmasia.agent-channel-fixtures.v1" or bundle["environment"] != "synthetic":
            raise ValueError("invalid_synthetic_registry")
        self.core._iso(bundle["generated_at"], "generated_at")
        if not isinstance(bundle["reports"], list) or not 1 <= len(bundle["reports"]) <= 32:
            raise ValueError("invalid_registry_report_count")
        if not isinstance(bundle["evidence"], dict) or len(bundle["evidence"]) > 32:
            raise ValueError("invalid_registry_evidence")
        for reference, value in bundle["evidence"].items():
            if not reference.startswith("synthetic:") or not isinstance(value, str) or len(value) > 4096:
                raise ValueError("only_literal_synthetic_evidence_allowed")
        self.evidence = bundle["evidence"]
        self.generated_at = bundle["generated_at"]
        entries = {}
        for entry in bundle["reports"]:
            if not isinstance(entry, dict) or set(entry) != {"name", "report", "snapshot_fields"}:
                raise ValueError("invalid_synthetic_entry")
            self.core.validate_report(entry["report"])
            if any(not e["reference"].startswith("synthetic:") for e in entry["report"]["evidence"]):
                raise ValueError("synthetic_references_required")
            if not isinstance(entry["snapshot_fields"], dict):
                raise ValueError("synthetic_snapshot_required")
            digest = self.core.canonical_hash(entry["report"])
            if digest in entries:
                raise ValueError("duplicate_registry_report")
            entries[digest] = entry
        return entries

    def allow_rate(self, uid):
        bucket = self.rates[uid if uid in UID_AGENT else -1]
        now = time.monotonic()
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= 10:
            return False
        bucket.append(now)
        return True

    def process(self, report, uid, request_id, now):
        """Caller uid comes only from SO_PEERCRED in handle(), never the body."""
        if uid not in UID_AGENT:
            raise ValueError("source_uid_not_allowed")
        if not isinstance(report, dict) or report.get("reporter") != UID_AGENT[uid]:
            raise ValueError("reporter_does_not_match_peer_uid")
        self.core.validate_report(report)
        digest = self.core.canonical_hash(report)
        entry = self.fixtures.get(digest)
        if entry is None:
            # Do not pass unapproved content to the ledger or echo/store it.
            raise ValueError("synthetic_fixture_not_allowlisted")
        verified_hashes = []
        for evidence in report["evidence"]:
            literal = self.evidence.get(evidence["reference"])
            if literal is not None:
                actual = hashlib.sha256(literal.encode("utf-8")).hexdigest()
                if actual == evidence["sha256"]:
                    verified_hashes.append(actual)
        verified = all(e["sha256"] in verified_hashes for e in report["evidence"])
        context = {"schema": "bmasia.agent-shadow-context.v1", "sender": UID_AGENT[uid],
                   "request_id": request_id, "report_sha256": digest, "verified": verified,
                   "verified_evidence_sha256": verified_hashes, "environment": "synthetic"}
        snapshot = {**report["record"], "observed_at": now.isoformat(),
                    "updated_at": self.generated_at, "fields": entry["snapshot_fields"]}
        assessment = self.ledger.ingest(report, context, snapshot, now=now)
        if assessment["outcome"] in {"conflict", "needs_source_verification", "manual_review"}:
            outcome = assessment["outcome"]
        elif assessment["replay"] or assessment["outcome"] == "duplicate":
            outcome = "replayed"
        else:
            outcome = "accepted"
        return {"schema": "bmasia.agent-channel-receipt.v1", "outcome": outcome,
                "assessment": assessment["outcome"], "receipt_id": assessment["receipt_id"],
                "request_id": assessment["request_id"], "reporter": UID_AGENT[uid],
                "authenticated_peer_uid": uid, "authentication": "linux_so_peercred",
                "environment": "synthetic", "event_id": report["event_id"],
                "report_sha256": digest, "verified": verified,
                "verified_evidence_sha256": verified_hashes,
                "replay": assessment["replay"], "recorded_at": assessment["recorded_at"],
                "evidence_meaning": "byte_binding_not_factual_truth", **SAFE_FLAGS}

    def handle(self, connection):
        connection.settimeout(0.2)
        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        uid = -1
        try:
            _pid, uid, _gid = peer_identity(connection)
            if not self.allow_rate(uid):
                raise ValueError("rate_limited")
            if uid not in UID_AGENT:
                raise ValueError("source_uid_not_allowed")
            raw = receive_frame(connection)
            report = decode_json(raw)
            receipt = self.process(report, uid, request_id, now)
        except (ValueError, TypeError, UnicodeError, RecursionError, OSError, struct.error, sqlite3.Error) as exc:
            # Core errors contain validation labels, never source values. Avoid
            # echoing even their free text; retain fixed errors where known.
            known = {"source_uid_not_allowed", "reporter_does_not_match_peer_uid", "synthetic_fixture_not_allowlisted",
                     "request_size_invalid", "truncated_frame", "duplicate_json_key", "nonfinite_json", "invalid_json", "rate_limited"}
            reason = str(exc) if str(exc) in known else "invalid_or_stale_report"
            receipt = {"schema": "bmasia.agent-channel-receipt.v1", "outcome": "rejected",
                       "request_id": request_id, "reason": reason, "authenticated_peer_uid": uid,
                       "environment": "synthetic", **SAFE_FLAGS}
        try:
            # Audit failure is fail-closed: never claim a durable success.
            self.audit.record(request_id, uid, receipt, now)
        except (OSError, sqlite3.Error):
            # The private core may already have committed. Do not claim either
            # successful channel auditing or rollback; retry the identical ID.
            receipt = {"schema": "bmasia.agent-channel-receipt.v1", "outcome": "indeterminate",
                       "reason": "audit_unavailable", "request_id": request_id,
                       "authenticated_peer_uid": uid, "environment": "synthetic", **SAFE_FLAGS}
        try:
            send_frame(connection, receipt)
        except (OSError, ValueError):
            pass  # Committed receipts are available by resubmitting the same report.

    def serve(self):
        path = Path(self.config["socket_path"])
        directory = path.parent
        if not directory.is_dir() or directory.is_symlink() or directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o022:
            raise ValueError("socket_directory_must_be_owned_and_not_shared_writable")
        with (directory / "collector.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
                    raise ValueError("refusing_to_replace_nonowned_socket")
                path.unlink()  # Exact stale socket only, while holding the exclusive service lock.
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path))
                os.chmod(path, 0o660)
                server.listen(16)
                server.settimeout(1)
                print("agent-shadow collector ready; synthetic-only; unix-peer-identity", flush=True)
                while not self.stopping:
                    try:
                        connection, _ = server.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        self.handle(connection)
            path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--status", action="store_true", help="Private operator readback; do not start listener")
    args = parser.parse_args()
    verify_accounts()
    config = decode_json(trusted_file(args.config, 8192))
    collector = Collector(config)
    if args.status:
        print(json.dumps({"environment": "synthetic", "source_uids": UID_AGENT,
                          "channel": collector.audit.summary(), "shadow": collector.ledger.report(), **SAFE_FLAGS}, sort_keys=True))
        return
    def stop(_signum, _frame):
        collector.stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    collector.serve()


if __name__ == "__main__":
    main()
