#!/usr/bin/env python3
"""Create private, fictional fixtures for the report-only Unix socket."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import uuid


SCHEMA = "bmasia.agent-channel-fixtures.v1"
REPORT_SCHEMA = "bmasia.agent-report.v1"
FIXTURE_NAMESPACE = uuid.UUID("902169ca-053f-5137-819f-76237078839c")
SPECS = (
    ("theo", "opportunities", "follow_up_date", None),
    ("lyra", "contacts", "title", ""),
    ("riff", "tickets", "priority", "medium"),
    ("nina", "zones", "notes", ""),
)


def _utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    return value.astimezone(dt.timezone.utc)


def _after_values(agent, now):
    return {
        "theo": (now.date().isoformat(), (now + dt.timedelta(days=1)).date().isoformat()),
        "lyra": ("Synthetic manager", "Synthetic alternate manager"),
        "riff": ("high", "urgent"),
        "nina": ("Synthetic relaxed evening", "Synthetic alternate evening"),
    }[agent]


def _verified_evidence(agent):
    reference = "synthetic:channel:%s:v1" % agent
    text = "Synthetic channel fixture for %s; no customer data." % agent
    return reference, text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unverified_evidence(agent):
    reference = "synthetic:channel:%s:unresolvable:v1" % agent
    text = "Synthetic unresolvable channel fixture for %s; no customer data." % agent
    return reference, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _report(agent, collection, field, before, after, event_id, observed_at, evidence):
    reference, digest = evidence
    return {
        "schema": REPORT_SCHEMA,
        "event_id": str(event_id),
        "reporter": agent,
        "observed_at": observed_at,
        "record": {
            "collection": collection,
            "id": str(uuid.uuid5(FIXTURE_NAMESPACE, "record:%s" % agent)),
        },
        "changes": [{"field": field, "before": before, "after": after}],
        "evidence": [{
            "kind": "agent_receipt", "reference": reference, "sha256": digest,
        }],
        "follow_up": None,
    }


def generate_bundle(now=None):
    """Return four valid, four collision, and four unverified fake reports."""
    now = _utc(now or dt.datetime.now(dt.timezone.utc))
    generated_at = now.isoformat()
    observed_at = (now - dt.timedelta(minutes=5)).isoformat()
    entries = []
    evidence_registry = {}

    # Each ID is deterministic within a generated bundle. A collision reuses
    # the valid ID with different valid content; unverified uses a new ID.
    for variant in ("valid", "collision", "unverified"):
        for agent, collection, field, before in SPECS:
            valid_after, collision_after = _after_values(agent, now)
            valid_event_id = uuid.uuid5(
                FIXTURE_NAMESPACE, "event:%s:%s:valid" % (generated_at, agent),
            )
            if variant == "unverified":
                event_id = uuid.uuid5(
                    FIXTURE_NAMESPACE, "event:%s:%s:unverified" % (generated_at, agent),
                )
                evidence = _unverified_evidence(agent)
                after = valid_after
            else:
                event_id = valid_event_id
                reference, text, digest = _verified_evidence(agent)
                evidence_registry[reference] = text
                evidence = (reference, digest)
                after = valid_after if variant == "valid" else collision_after
            entries.append({
                "name": "%s-%s" % (agent, variant),
                "report": _report(
                    agent, collection, field, before, after, event_id,
                    observed_at, evidence,
                ),
                "snapshot_fields": {field: before},
            })

    return {
        "schema": SCHEMA,
        "environment": "synthetic",
        "generated_at": generated_at,
        "reports": entries,
        "evidence": evidence_registry,
    }


def _json_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write_private(path, value):
    fd = os.open(os.fspath(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(_json_bytes(value))
    os.chmod(path, 0o600)


def write_bundle(directory, now=None):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(directory, 0o700)
    reports_directory = directory / "reports"
    reports_directory.mkdir(mode=0o700)
    os.chmod(reports_directory, 0o700)

    bundle = generate_bundle(now)
    _write_private(directory / "registry.json", bundle)
    for entry in bundle["reports"]:
        _write_private(reports_directory / (entry["name"] + ".json"), entry["report"])
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    try:
        write_bundle(args.directory)
        return 0
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
