#!/usr/bin/env python3
"""Pure, bounded comparison of imported agent observations with CRM snapshots.

This module deliberately has no connector, ORM, credential, write, send, or
promotion surface.  Both inputs are operator supplied JSON and are reported as
such; a shared local UID is not evidence of a uniquely authenticated process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

OBSERVATION_SCHEMA = "bmasia.crm-source-observations.v1"
SNAPSHOT_SCHEMA = "bmasia.live-pilot-snapshots.v1"
OUTPUT_SCHEMA = "bmasia.live-pilot-review.v1"
AUTHENTICATION = "operator_import_not_process_attestation"
MAX_RECORDS = 10
MAX_INPUT_BYTES = 1024 * 1024
MAX_SOURCE_AGE = timedelta(hours=24)
COVERAGE_SOURCES = ("theo", "lyra", "riff", "nina", "cara", "bmasia_sales")
FIELDS = {
    "contacts": ("title", "department", "last_contacted"),
    "opportunities": ("stage", "last_contact_date", "follow_up_date"),
}
HOLD_CODES = {
    "CRM_HOLD", "ASSESSMENT_BLOCKED", "UNRESOLVED_BLOCKER", "FOLLOW_UP_DUE",
    "NEEDS_ATTENTION", "WAITING", "SOURCE_STALE", "SOURCE_FUTURE",
    "SOURCE_MISSING", "SOURCE_CONFLICT", "IDENTITY_MISMATCH",
    "SOURCE_RUNTIME_HEALTH_UNVERIFIED", "SNAPSHOT_STALE",
}
SOURCE_ERRORS = {
    'SOURCE_MISSING', 'SOURCE_PATH_REJECTED', 'SOURCE_INVALID',
    'SOURCE_INCOMPLETE', 'SOURCE_ID_MISMATCH', 'SOURCE_RECORD_UNSUPPORTED',
    'SOURCE_SCHEMA_UNSUPPORTED', 'SOURCE_DUPLICATE', 'SOURCE_RESULT_LIMIT',
    'SOURCE_FUTURE', 'SOURCE_STALE',
}


class ReviewError(ValueError):
    pass


def _now(value: datetime | None = None) -> datetime:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReviewError(f"{label}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewError(f"{label}_invalid") from exc
    if parsed.tzinfo is None:
        raise ReviewError(f"{label}_invalid")
    return parsed.astimezone(timezone.utc)


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ReviewError(f"{label}_invalid")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ReviewError(f"{label}_invalid") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _scalar_map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or len(value) > 20:
        raise ReviewError(f"{label}_invalid")
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 80:
            raise ReviewError(f"{label}_invalid")
        if item is not None and not isinstance(item, (str, int, bool)):
            raise ReviewError(f"{label}_invalid")
        if isinstance(item, str) and len(item) > 512:
            raise ReviewError(f"{label}_invalid")
        if isinstance(item, int) and not isinstance(item, bool) and not -(2**53) < item < 2**53:
            raise ReviewError(f"{label}_invalid")
    return dict(value)


def _record(value: Any, label: str) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"collection", "id"}:
        raise ReviewError(f"{label}_invalid")
    collection = value["collection"]
    if not isinstance(collection, str) or collection not in FIELDS:
        raise ReviewError(f"{label}_invalid")
    return collection, _uuid(value["id"], label + "_id")


def _source_observation(value: Any, current: datetime) -> dict[str, Any]:
    required = {"source", "company_id", "record", "source_observed_at", "source_version_hash", "observation_id", "source_authentication", "facts", "holds", "follow_ups", "source_payload_sha256"}
    failure = {"source", "company_id", "record", "status", "error_code"}
    if isinstance(value, dict) and set(value) == failure:
        if value["status"] != "FAILED" or not isinstance(value["source"], str) or value["source"] not in COVERAGE_SOURCES or not isinstance(value["error_code"], str) or value["error_code"] not in SOURCE_ERRORS:
            raise ReviewError("source_failure_invalid")
        company_id = _uuid(value["company_id"], "company_id")
        collection, record_id = _record(value["record"], "record")
        return {"source": value["source"], "company_id": company_id, "collection": collection, "record_id": record_id, "failed": True, "error_code": value["error_code"]}
    if not isinstance(value, dict) or set(value) != required:
        raise ReviewError("observation_shape_invalid")
    if not isinstance(value["source"], str) or value["source"] not in COVERAGE_SOURCES:
        raise ReviewError("observation_source_invalid")
    if value["source_authentication"] != AUTHENTICATION:
        raise ReviewError("observation_authentication_invalid")
    company_id = _uuid(value["company_id"], "company_id")
    collection, record_id = _record(value["record"], "record")
    observation_id = _uuid(value["observation_id"], "observation_id")
    observed = _timestamp(value["source_observed_at"], "source_observed_at")
    if observed > current:
        raise ReviewError("source_future")
    stale = observed < current - MAX_SOURCE_AGE
    for name in ("source_version_hash", "source_payload_sha256"):
        if not isinstance(value[name], str) or len(value[name]) != 64 or any(c not in "0123456789abcdef" for c in value[name]):
            raise ReviewError(name + "_invalid")
    facts = _scalar_map(value["facts"], "facts")
    if not isinstance(value["holds"], list) or any(not isinstance(item, str) or item not in HOLD_CODES for item in value["holds"]) or len(value["holds"]) != len(set(value["holds"])):
        raise ReviewError("holds_invalid")
    if not isinstance(value["follow_ups"], list) or len(value["follow_ups"]) > 25:
        raise ReviewError("follow_ups_invalid")
    follow_ups = []
    for item in value["follow_ups"]:
        if not isinstance(item, dict) or set(item) != {"case_id", "state", "due_at", "owner"} or not all(isinstance(item[key], str) and item[key] for key in ("case_id", "state", "owner")):
            raise ReviewError("follow_up_invalid")
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', item['case_id']) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', item[key]) for key in ('state', 'owner')):
            raise ReviewError('follow_up_invalid')
        due_at = None if item["due_at"] is None else _timestamp(item["due_at"], "follow_up_due_at").isoformat()
        follow_ups.append({"case_id": item["case_id"], "state": item["state"], "due_at": due_at, "owner": item["owner"]})
    holds = set(value["holds"])
    if stale:
        holds.add("SOURCE_STALE")
    return {"source": value["source"], "company_id": company_id, "collection": collection, "record_id": record_id, "observation_id": observation_id, "source_observed_at": observed.isoformat(), "source_version_hash": value["source_version_hash"], "facts": facts, "holds": sorted(holds), "follow_ups": follow_ups, "source_payload_sha256": value["source_payload_sha256"], "source_authentication": AUTHENTICATION, "failed": False, "freshness": "stale" if stale else "current"}


def _snapshot(value: Any, current: datetime) -> dict[str, Any]:
    expected = {"company", "collection", "id", "observed_at", "updated_at", "fields", "status"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ReviewError("snapshot_shape_invalid")
    if value["status"] not in {"ok", "missing", "error"} or value["collection"] not in FIELDS:
        raise ReviewError("snapshot_status_invalid")
    company = value["company"]
    if not isinstance(company, dict) or set(company) not in ({"id"}, {"id", "name", "updated_at"}):
        raise ReviewError("snapshot_company_invalid")
    company_id = _uuid(company["id"], "snapshot_company_id")
    if company.get("name") is not None and not isinstance(company.get("name"), str):
        raise ReviewError("snapshot_company_invalid")
    observed = _timestamp(value["observed_at"], "snapshot_observed_at")
    updated = None if value["updated_at"] is None else _timestamp(value["updated_at"], "snapshot_updated_at")
    company_updated = None if company.get("updated_at") is None else _timestamp(company.get("updated_at"), "snapshot_company_updated_at")
    if observed > current or (updated is not None and updated > current) or (company_updated is not None and company_updated > current):
        raise ReviewError("snapshot_future")
    fields = _scalar_map(value["fields"], "snapshot_fields")
    fk = fields.get("company", "__absent__")
    if isinstance(fk, dict):  # defensive; scalar validation makes this unreachable.
        fk = fk.get("id")
    fk_matches = isinstance(fk, str) and fk == company_id
    return {"company_id": company_id, "company_name": company.get("name"), "company_updated_at": None if company_updated is None else company_updated.isoformat(), "collection": value["collection"], "record_id": _uuid(value["id"], "snapshot_id"), "observed_at": observed.isoformat(), "updated_at": None if updated is None else updated.isoformat(), "fields": fields, "status": value["status"], "fk_matches": fk_matches, "stale": observed < current - MAX_SOURCE_AGE}


def _input(value: Any, schema: str, key: str) -> tuple[str, list[Any]]:
    expected = {"schema", "scope_id", "observed_at", key}
    # The source extractor adds imported_at; it is provenance, not a freshness bypass.
    source_actual = {"schema", "scope_id", "imported_at", key}
    allowed = expected | ({"imported_at"} if key == "observations" else {"crm_writes", "customer_outbound"})
    accepted = (expected, source_actual, allowed) if key == "observations" else (expected, allowed)
    if not isinstance(value, dict) or set(value) not in accepted or value["schema"] != schema:
        raise ReviewError("document_shape_invalid")
    scope_id = _uuid(value["scope_id"], "scope_id")
    _timestamp(value["imported_at"] if key == "observations" and "imported_at" in value else value["observed_at"], "document_observed_at")
    if key == "records" and set(value) == allowed and (value["crm_writes"] != 0 or value["customer_outbound"] is not False):
        raise ReviewError("snapshot_safety_flags_invalid")
    rows = value[key]
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise ReviewError("record_bound_invalid")
    return scope_id, rows


def review(observations_document: Any, snapshots_document: Any, *, now: datetime | None = None) -> dict[str, Any]:
    current = _now(now)
    scope_id, source_rows = _input(observations_document, OBSERVATION_SCHEMA, "observations")
    snapshot_scope, snapshot_rows = _input(snapshots_document, SNAPSHOT_SCHEMA, "records")
    if scope_id != snapshot_scope:
        raise ReviewError("scope_id_mismatch")
    observations: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for raw in source_rows:
        parsed = _source_observation(raw, current)
        if parsed["failed"]:
            observations.append(parsed)
            continue
        digest = _hash(raw)
        previous = seen.get(parsed["observation_id"])
        if previous is None:
            seen[parsed["observation_id"]] = digest
            observations.append(parsed)
        elif previous != digest:
            raise ReviewError("observation_id_conflict")
    snapshots = [_snapshot(raw, current) for raw in snapshot_rows]
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in snapshots:
        identity = (item["company_id"], item["collection"], item["record_id"])
        if identity in index:
            raise ReviewError("snapshot_identity_conflict")
        index[identity] = item
    coverage_states = {name: set() for name in COVERAGE_SOURCES}
    for item in observations:
        if not item["failed"]:
            coverage_states[item["source"]].add("operator_import_stale" if item["freshness"] == "stale" else "operator_import_held" if item["holds"] else "operator_import_observed")
    coverage = {name: "no_live_observation" if not states else next(iter(states)) if len(states) == 1 else "operator_import_mixed" for name, states in coverage_states.items()}
    results = []
    for source in observations:
        if source["failed"]:
            results.append({"source": source["source"], "company_id": source["company_id"], "record": {"collection": source["collection"], "id": source["record_id"]}, "status": "source_failed", "error_code": source["error_code"], "holds": ["SOURCE_MISSING"], "follow_ups": [], "proposed_edits": []})
            continue
        identity = (source["company_id"], source["collection"], source["record_id"])
        snapshot = index.get(identity)
        base = {"source": source["source"], "company_id": source["company_id"], "record": {"collection": source["collection"], "id": source["record_id"]}, "observation_id": source["observation_id"], "source_observed_at": source["source_observed_at"], "source_version_hash": source["source_version_hash"], "source_authentication": AUTHENTICATION, "holds": source["holds"], "follow_ups": source["follow_ups"], "proposed_edits": []}
        if snapshot is None:
            results.append({**base, "status": "missing_current_snapshot", "current": None, "facts": {field: {"source": source["facts"].get(field, "__absent__"), "current": "__missing_snapshot__", "comparison": "unknown"} for field in FIELDS[source["collection"]]}})
            continue
        if snapshot["status"] != "ok":
            results.append({**base, "status": "current_snapshot_" + snapshot["status"], "current": {"observed_at": snapshot["observed_at"], "updated_at": snapshot["updated_at"]}, "facts": {field: {"source": source["facts"].get(field, "__absent__"), "current": "__missing_snapshot__", "comparison": "unknown"} for field in FIELDS[source["collection"]]}})
            continue
        if not snapshot["fk_matches"]:
            results.append({**base, "status": "identity_mismatch", "holds": sorted(set(base["holds"]) | {"IDENTITY_MISMATCH"}), "current": {"company": {"id": snapshot["company_id"]}, "observed_at": snapshot["observed_at"], "updated_at": snapshot["updated_at"]}, "facts": {field: {"source": source["facts"].get(field, "__absent__"), "current": "__identity_mismatch__", "comparison": "unknown"} for field in FIELDS[source["collection"]]}})
            continue
        if snapshot["stale"] or _timestamp(snapshot["observed_at"], "snapshot_observed_at") < _timestamp(source["source_observed_at"], "source_observed_at"):
            results.append({**base, "status": "stale_current_snapshot", "holds": sorted(set(base["holds"]) | {"SNAPSHOT_STALE"}), "current": {"company": {"id": snapshot["company_id"], "name": snapshot["company_name"], "updated_at": snapshot["company_updated_at"]}, "observed_at": snapshot["observed_at"], "updated_at": snapshot["updated_at"]}, "facts": {field: {"source": source["facts"].get(field, "__absent__"), "current": "__stale_snapshot__", "comparison": "unknown"} for field in FIELDS[source["collection"]]}})
            continue
        facts = {}
        for field in FIELDS[source["collection"]]:
            has_source, has_current = field in source["facts"], field in snapshot["fields"]
            source_value = source["facts"].get(field) if has_source else "__absent__"
            current_value = snapshot["fields"].get(field) if has_current else "__absent__"
            facts[field] = {"source": source_value, "current": current_value, "comparison": "agreement" if has_source and has_current and source_value == current_value else "different" if has_source and has_current else "unknown"}
        results.append({**base, "status": "compared", "current": {"company": {"id": snapshot["company_id"], "name": snapshot["company_name"], "updated_at": snapshot["company_updated_at"]}, "observed_at": snapshot["observed_at"], "updated_at": snapshot["updated_at"]}, "facts": facts})
    return {"schema": OUTPUT_SCHEMA, "scope_id": scope_id, "observed_at": current.isoformat(), "read_only": True, "crm_writes": 0, "customer_outbound": False, "automatic_updates_enabled": False, "cira_role": "reviewer_and_document_service", "coverage": coverage, "results": results}


def _load(path: str) -> Any:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size > MAX_INPUT_BYTES:
        raise ReviewError("input_path_invalid")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output = {}
        for key, value in pairs:
            if key in output:
                raise ReviewError("input_json_invalid")
            output[key] = value
        return output
    return json.loads(candidate.read_text("utf-8"), object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ReviewError("input_json_invalid")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--snapshots", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(review(_load(args.observations), _load(args.snapshots)), sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        print(json.dumps({"schema": OUTPUT_SCHEMA, "status": "rejected", "error_code": "REVIEW_REJECTED", "read_only": True, "crm_writes": 0}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
