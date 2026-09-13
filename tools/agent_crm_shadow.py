#!/usr/bin/env python3
"""Operator-only shadow ledger CLI. No HTTP, model, mail or CRM write client.

The context file is trusted operator/adapter input, not an agent report field.
This CLI does not authenticate agents. Do not expose it as a public endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
from uuid import UUID

# services/__init__.py imports unrelated Django services; load just this pure
# module so the operator CLI cannot initialize Django or its CRM connections.
_spec = importlib.util.spec_from_file_location(
    "agent_shadow_core", Path(__file__).resolve().parents[1] / "crm_app/services/agent_shadow.py")
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
ShadowLedger, canonical_hash = _core.ShadowLedger, _core.canonical_hash


def load_json(path):
    with Path(path).open("rb") as stream:
        content = stream.read(32769)
    if len(content) > 32768:
        raise ValueError("Input file exceeds 32 KiB")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(content, object_pairs_hook=unique_keys,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def markdown(report):
    """Plain, escaped code-block review: untrusted text never becomes HTML."""
    return ("# BMAsia agent CRM — shadow review\n\n"
            "No customer record changes, outbound messages or model calls. "
            "A proposal is not an applied update. Missing reports are unknown, not healthy.\n\n"
            "```json\n" + json.dumps(report, indent=2, sort_keys=True).replace("`", "\\u0060")
            + "\n```\n")


def synthetic_cases(now):
    """Four fake source owners, replay, collision and deliberately bad evidence."""
    specs = [
        ("theo", "opportunities", "follow_up_date", None, now.date().isoformat()),
        ("lyra", "contacts", "title", "", "Synthetic operations manager"),
        ("riff", "tickets", "priority", "medium", "high"),
        ("nina", "zones", "notes", "", "Synthetic relaxed evening programme"),
    ]
    for index, (agent, collection, field, before, after) in enumerate(specs, 1):
        observed = (now - timedelta(minutes=5)).isoformat()
        evidence_hash = canonical_hash({"synthetic_source": agent})
        report = {
            "schema": "bmasia.agent-report.v1", "event_id": str(UUID(int=index)),
            "reporter": agent, "observed_at": observed,
            "record": {"collection": collection, "id": str(UUID(int=100 + index))},
            "changes": [{"field": field, "before": before, "after": after}],
            "evidence": [{"kind": "agent_receipt", "reference": "synthetic:" + agent,
                          "sha256": evidence_hash}],
            "follow_up": {"owner": agent, "due_at": (now - timedelta(minutes=1)).isoformat(),
                          "reason": "Synthetic follow-up review"},
        }
        context = {
            "schema": "bmasia.agent-shadow-context.v1", "sender": agent,
            "request_id": "synthetic-" + agent, "report_sha256": canonical_hash(report),
            "verified_evidence_sha256": [evidence_hash], "verified": True,
            "environment": "synthetic",
        }
        snapshot = {**report["record"], "observed_at": now.isoformat(),
                    "updated_at": observed, "fields": {field: before}}
        yield report, context, snapshot


def run_demo(directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    now = datetime.now(timezone.utc)
    ledger = ShadowLedger(directory / "shadow.sqlite3")
    receipts = []
    cases = list(synthetic_cases(now))
    for report, context, snapshot in cases:
        receipts.append(ledger.ingest(report, context, snapshot, now=now))
        receipts.append(ledger.ingest(report, context, snapshot, now=now))
        collision = json.loads(json.dumps(report))
        collision["changes"][0]["after"] = "Synthetic conflicting revision"
        changed_context = {**context, "report_sha256": canonical_hash(collision)}
        receipts.append(ledger.ingest(collision, changed_context, snapshot, now=now))
    unverified, context, snapshot = cases[0]
    unverified = {**unverified, "event_id": str(UUID(int=999)), "follow_up": None}
    context = {**context, "verified": False, "verified_evidence_sha256": [],
               "report_sha256": canonical_hash(unverified)}
    receipts.append(ledger.ingest(unverified, context, snapshot, now=now))
    review = ledger.report(now=now)
    result = {"exercise": "synthetic_only", "running_candidate_app": False,
              "receipts": receipts, "review": review}
    for name, data in (("receipts.json", result), ("fixtures.json", cases)):
        with (directory / name).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
    (directory / "REVIEW.md").write_text(markdown(review), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="New isolated synthetic exercise; no CRM access")
    demo.add_argument("--directory", required=True)
    ingest = commands.add_parser("ingest", help="Trusted local operator only, shadow append")
    ingest.add_argument("--ledger", required=True)
    ingest.add_argument("--report", required=True)
    ingest.add_argument("--context", required=True)
    ingest.add_argument("--snapshot", required=True)
    review = commands.add_parser("report", help="Read ledger, no business actions")
    review.add_argument("--ledger", required=True)
    review.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = run_demo(args.directory)
        elif args.command == "ingest":
            result = ShadowLedger(args.ledger).ingest(
                load_json(args.report), load_json(args.context), load_json(args.snapshot))
        else:
            # Reporting must not silently create an empty ledger at a misspelt path.
            if not Path(args.ledger).is_file():
                raise ValueError("Ledger does not exist")
            result = ShadowLedger(args.ledger).report()
            if args.format == "markdown":
                print(markdown(result))
                return 0
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        # Only bounded local validation errors; never dump input or credentials.
        print(json.dumps({"status": "rejected", "error": str(exc), "crm_writes": 0}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
