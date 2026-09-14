#!/usr/bin/env python3
"""Submit one bounded report to the local report-only Unix socket.

The producer sends only ``bmasia.agent-report.v1`` JSON. Kernel peer identity,
trusted context, evidence resolution, and snapshots belong to the collector.
There is deliberately no CRM, HTTP, model, retry, or credential integration.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import socket
import struct
import sys
import uuid


DEFAULT_SOCKET = "/run/bmasia-agent-shadow/collector.sock"
MAX_REPORT_BYTES = 32 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
TIMEOUT_SECONDS = 5
UID_REPORTERS = {1008: "theo", 1000: "lyra", 1007: "riff", 1004: "nina"}
REPORT_KEYS = {
    "schema", "event_id", "reporter", "observed_at", "record", "changes",
    "evidence", "follow_up",
}
REPORTERS = frozenset(UID_REPORTERS.values())
EVIDENCE_KINDS = {"email_message", "ticket_event", "agent_receipt", "document"}
COLLECTIONS = {"opportunities", "contacts", "tickets", "zones"}


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("%s has missing or unknown keys" % label)


def _uuid(value, label):
    if not isinstance(value, str):
        raise ValueError("%s must be UUID" % label)
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("%s must be UUID" % label) from exc


def _iso(value, label):
    if not isinstance(value, str):
        raise ValueError("%s must be ISO timestamp" % label)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("%s must be ISO timestamp" % label) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("%s must be timezone aware" % label)


def _scalar(value):
    return (
        isinstance(value, (str, int, float, bool, type(None)))
        and not isinstance(value, (list, dict))
        and (not isinstance(value, float) or math.isfinite(value))
    )


def validate_report(report):
    """Validate the exact public envelope without importing application code."""
    _exact(report, REPORT_KEYS, "report")
    if report["schema"] != "bmasia.agent-report.v1":
        raise ValueError("invalid report schema")
    if report["reporter"] not in REPORTERS:
        raise ValueError("invalid reporter")
    _uuid(report["event_id"], "event_id")
    _iso(report["observed_at"], "observed_at")

    _exact(report["record"], {"collection", "id"}, "record")
    if report["record"]["collection"] not in COLLECTIONS:
        raise ValueError("invalid collection")
    _uuid(report["record"]["id"], "record.id")

    changes = report["changes"]
    if not isinstance(changes, list) or len(changes) > 20:
        raise ValueError("changes must contain at most 20 entries")
    seen_fields = set()
    for change in changes:
        _exact(change, {"field", "before", "after"}, "change")
        field = change["field"]
        if not isinstance(field, str) or not field.isidentifier() or field != field.lower():
            raise ValueError("change field must be lowercase identifier")
        if field in seen_fields:
            raise ValueError("duplicate change field")
        seen_fields.add(field)
        if not _scalar(change["before"]) or not _scalar(change["after"]):
            raise ValueError("change values must be scalars")

    evidence = report["evidence"]
    if not isinstance(evidence, list) or not evidence or len(evidence) > 20:
        raise ValueError("evidence must contain 1-20 entries")
    for item in evidence:
        _exact(item, {"kind", "reference", "sha256"}, "evidence")
        reference, digest = item["reference"], item["sha256"]
        if (
            item["kind"] not in EVIDENCE_KINDS
            or not isinstance(reference, str)
            or not 0 < len(reference.strip()) <= 200
        ):
            raise ValueError("invalid evidence")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError("invalid evidence sha256")

    follow_up = report["follow_up"]
    if follow_up is not None:
        _exact(follow_up, {"owner", "due_at", "reason"}, "follow_up")
        if (
            follow_up["owner"] not in REPORTERS
            or not isinstance(follow_up["reason"], str)
            or not 0 < len(follow_up["reason"].strip()) <= 240
        ):
            raise ValueError("invalid follow_up")
        _iso(follow_up["due_at"], "follow_up.due_at")
    if not changes and follow_up is None:
        raise ValueError("report needs a change or follow_up")
    return report


def canonical_bytes(report):
    try:
        raw = json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("report is not JSON-safe") from exc
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds 32 KiB")
    return raw


def parse_report_bytes(raw):
    """Accept only canonical UTF-8 JSON bytes for one public report."""
    if not isinstance(raw, bytes):
        raise TypeError("Report must be bytes")
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds 32 KiB")
    try:
        report = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_keys,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("Report must be UTF-8 JSON") from exc
    validate_report(report)
    if canonical_bytes(report) != raw:
        raise ValueError("Report JSON must use canonical bytes")
    return report


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise OSError("Socket closed before complete response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _parse_response(raw):
    try:
        response = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_keys,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("Response must be UTF-8 JSON") from exc
    if not isinstance(response, dict):
        raise ValueError("Response must be a JSON object")
    return response


def submit_report(report, socket_path=DEFAULT_SOCKET):
    """Submit once, binding the claimed reporter to this process's real UID."""
    validate_report(report)
    expected_reporter = UID_REPORTERS.get(os.getuid())
    if expected_reporter is None:
        raise ValueError("Unix account UID is not authorized to submit reports")
    if report["reporter"] != expected_reporter:
        raise ValueError("reporter does not match this Unix account")
    payload = canonical_bytes(report)

    # One connection and one send only. A caller must explicitly retry the
    # same event after an ambiguous transport failure.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(TIMEOUT_SECONDS)
        client.connect(os.fspath(socket_path))
        client.sendall(struct.pack("!I", len(payload)) + payload)
        response_size = struct.unpack("!I", _read_exact(client, 4))[0]
        if response_size > MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds 128 KiB")
        return _parse_response(_read_exact(client, response_size))


def _exit_code(response):
    return 0 if response.get("outcome") in {"accepted", "replayed"} else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument("--report", required=True, help="path to canonical report JSON")
    args = parser.parse_args(argv)
    try:
        with open(args.report, "rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        report = parse_report_bytes(raw)
        response = submit_report(report, args.socket)
        print(json.dumps(
            response, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ))
        return _exit_code(response)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, struct.error) as exc:
        print(json.dumps(
            {"status": "rejected", "error": str(exc), "crm_writes": 0},
            sort_keys=True, separators=(",", ":"),
        ), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
