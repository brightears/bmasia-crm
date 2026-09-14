#!/usr/bin/env python3
"""Bounded, read-only import of operator-selected CRM source observations.

This is deliberately an importer, not an authenticated CRM client.  It never
uses credentials, calls a network service, or mutates either source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

SCOPE_SCHEMA = "bmasia.live-pilot-scope.v1"
OUTPUT_SCHEMA = "bmasia.crm-source-observations.v1"
AUTHENTICATION = "operator_import_not_process_attestation"
SALES_ROOT = Path("/Users/norbert/Documents/Projects/BMAsia Sales/data/reports")
CARA_DB = Path("/Users/norbert/Library/Application Support/BMAsia Customer Success/outreach/contexts.sqlite3")
MAX_JSON_SOURCE_BYTES = 4 * 1024 * 1024
MAX_SCOPE_BYTES = 64 * 1024
MAX_CASES = 25
MAX_SIGNAL_ITEMS = 1000
MAX_SCOPE_AGE = timedelta(days=7)
OBSERVATION_NAMESPACE = uuid.UUID("a1b51d58-221d-5f07-873e-315cd95d536f")
COLLECTIONS = {"contacts", "opportunities"}
HOLD_LABELS = {"CRM_HOLD", "ASSESSMENT_BLOCKED", "UNRESOLVED_BLOCKER", "FOLLOW_UP_DUE", "SOURCE_RUNTIME_HEALTH_UNVERIFIED", "NEEDS_ATTENTION", "WAITING"}


class ScopeError(ValueError):
    pass


class SourceError(RuntimeError):
    pass


def _utc_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(UTC)


def _parse_aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ScopeError(f"{label} must be an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScopeError(f"{label} must be an aware ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ScopeError(f"{label} must be an aware ISO timestamp")
    return parsed.astimezone(UTC)


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ScopeError(f"{label} must be a UUID")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ScopeError(f"{label} must be a UUID") from exc


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_scope(scope: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Validate all scope fields before callers touch a requested source."""
    if not isinstance(scope, dict) or set(scope) != {"schema", "scope_id", "expires_at", "accounts"}:
        raise ScopeError("scope must contain exactly schema, scope_id, expires_at, accounts")
    if scope["schema"] != SCOPE_SCHEMA:
        raise ScopeError("unsupported scope schema")
    scope_id = _uuid(scope["scope_id"], "scope_id")
    current = _utc_now(now)
    expires_at = _parse_aware(scope["expires_at"], "expires_at")
    if expires_at <= current or expires_at > current + MAX_SCOPE_AGE:
        raise ScopeError("scope expiry must be in the next seven days")
    accounts = scope["accounts"]
    if not isinstance(accounts, list) or not accounts or len(accounts) > 10:
        raise ScopeError("accounts must contain one to ten entries")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in accounts:
        if not isinstance(item, dict) or set(item) != {"source", "company_id", "record", "source_path"}:
            raise ScopeError("each account has an invalid shape")
        source = item["source"]
        if source not in {"cara", "bmasia_sales"}:
            raise ScopeError("source must be cara or bmasia_sales")
        company_id = _uuid(item["company_id"], "company_id")
        record = item["record"]
        if not isinstance(record, dict) or set(record) != {"collection", "id"}:
            raise ScopeError("record has an invalid shape")
        collection = record["collection"]
        if collection not in COLLECTIONS:
            raise ScopeError("record collection is invalid")
        record_id = _uuid(record["id"], "record.id")
        source_path = item["source_path"]
        if not isinstance(source_path, str) or not os.path.isabs(source_path):
            raise ScopeError("source_path must be absolute")
        key = (source, company_id, collection, record_id)
        if key in seen:
            raise ScopeError("duplicate account scope entry")
        seen.add(key)
        normalized.append({"source": source, "company_id": company_id, "collection": collection, "record_id": record_id, "source_path": source_path})
    return {"schema": SCOPE_SCHEMA, "scope_id": scope_id, "expires_at": expires_at, "accounts": normalized}


def _safe_regular_file(path: Path, root: Path, *, suffix: str | None = None, max_bytes: int | None = None) -> None:
    try:
        resolved = path.resolve(strict=True)
        root_resolved = root.resolve(strict=True)
        stat = path.lstat()
    except OSError as exc:
        raise SourceError("SOURCE_MISSING") from exc
    if path.is_symlink() or not path.is_file() or resolved.parent != root_resolved:
        raise SourceError("SOURCE_PATH_REJECTED")
    if suffix and resolved.suffix != suffix:
        raise SourceError("SOURCE_PATH_REJECTED")
    if stat.st_uid != os.geteuid() or (max_bytes is not None and stat.st_size > max_bytes):
        raise SourceError("SOURCE_PATH_REJECTED")


def _timestamp(value: Any, *, now: datetime) -> str:
    try:
        parsed = _parse_aware(value, "source created_at")
    except ScopeError as exc:
        raise SourceError("SOURCE_INVALID") from exc
    if parsed > now:
        raise SourceError("SOURCE_FUTURE")
    if parsed < now - MAX_SCOPE_AGE:
        raise SourceError("SOURCE_STALE")
    return parsed.isoformat()


def _source_failure(item: Mapping[str, str], code: str) -> dict[str, Any]:
    return {"source": item["source"], "company_id": item["company_id"], "record": {"collection": item["collection"], "id": item["record_id"]}, "status": "FAILED", "error_code": code}


def _sales_observation(item: Mapping[str, str], *, sales_root: Path, now: datetime) -> dict[str, Any]:
    if item["collection"] != "opportunities":
        raise SourceError("SOURCE_RECORD_UNSUPPORTED")
    path = Path(item["source_path"])
    _safe_regular_file(path, sales_root, suffix=".json", max_bytes=MAX_JSON_SOURCE_BYTES)
    raw = path.read_bytes()
    try:
        document = _strict_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SourceError("SOURCE_INVALID") from exc
    if not isinstance(document, dict):
        raise SourceError("SOURCE_INVALID")
    crm = document.get("crm_context")
    if not isinstance(crm, dict) or crm.get("complete") != "TRUE" or not isinstance(crm.get("records"), list):
        raise SourceError("SOURCE_INCOMPLETE")
    companies = [record for record in crm["records"] if isinstance(record, dict) and record.get("record_type") == "company" and str(record.get("record_id")) == item["company_id"]]
    opportunities = [record for record in crm["records"] if isinstance(record, dict) and record.get("record_type") == "opportunity" and str(record.get("record_id")) == item["record_id"] and str(record.get("company_id")) == item["company_id"]]
    if not companies or not opportunities:
        raise SourceError("SOURCE_ID_MISMATCH")
    if len(companies) != 1 or len(opportunities) != 1:
        raise SourceError("SOURCE_DUPLICATE")
    opportunity = opportunities[0]
    context_hash = document.get("context_hash")
    if not isinstance(context_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", context_hash):
        raise SourceError("SOURCE_INVALID")
    observed = _timestamp(document.get("created_at"), now=now)
    facts = _sales_facts(opportunity)
    return _observation(item, observed, context_hash, facts, [], [], hashlib.sha256(raw).hexdigest())


def _strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))


def _sales_facts(opportunity: Mapping[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for name in ("stage", "last_contact_date", "follow_up_date"):
        if name not in opportunity:
            continue
        value = opportunity[name]
        if value is None:
            facts[name] = None
            continue
        if not isinstance(value, str) or len(value) > 200:
            raise SourceError("SOURCE_INVALID")
        if name.endswith("_date"):
            try:
                value = datetime.fromisoformat(value).date().isoformat()
            except ValueError as exc:
                raise SourceError("SOURCE_INVALID") from exc
        elif not value.strip():
            raise SourceError("SOURCE_INVALID")
        facts[name] = value
    return facts


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _cara_observation(item: Mapping[str, str], *, cara_db: Path, now: datetime) -> dict[str, Any]:
    path = Path(item["source_path"])
    _safe_regular_file(path, cara_db.parent)
    if path.resolve() != cara_db.resolve():
        raise SourceError("SOURCE_PATH_REJECTED")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"accounts", "packets", "settings"}.issubset(tables):
            raise SourceError("SOURCE_SCHEMA_UNSUPPORTED")
        account_columns = _columns(connection, "accounts")
        packet_columns = _columns(connection, "packets")
        if not {"account_id", "last_collected_at", "collection_state", "blockers_json"}.issubset(account_columns) or not {"account_id", "packet_sha256", "collected_at", "packet_json", "assessment_json"}.issubset(packet_columns):
            raise SourceError("SOURCE_SCHEMA_UNSUPPORTED")
        # Cara does not own opportunity IDs.  A scope can import only a contact
        # that the current packet proves as primary; selecting JSON scalars
        # keeps raw packet/message fields out of this process entirely.
        if item["collection"] != "contacts":
            raise SourceError("SOURCE_RECORD_UNSUPPORTED")
        accounts = connection.execute(
            "SELECT a.account_id, a.last_collected_at, a.collection_state, "
            "json_extract(p.packet_json, '$.crm.primary_contact_id'), "
            "json_extract(p.packet_json, '$.observed_at'), p.packet_sha256, p.collected_at, "
            "CASE WHEN a.blockers_json IS NULL OR NOT json_valid(a.blockers_json) "
            "OR json_type(a.blockers_json) != 'array' THEN NULL "
            f"WHEN json_array_length(a.blockers_json) BETWEEN 0 AND {MAX_SIGNAL_ITEMS} "
            "THEN json_array_length(a.blockers_json) ELSE NULL END, "
            "CASE WHEN json_type(p.packet_json, '$.crm.holds') != 'array' THEN NULL "
            f"WHEN json_array_length(p.packet_json, '$.crm.holds') BETWEEN 0 AND {MAX_SIGNAL_ITEMS} "
            "THEN json_array_length(p.packet_json, '$.crm.holds') ELSE NULL END, "
            "CASE WHEN json_type(p.packet_json, '$.blockers') != 'array' THEN NULL "
            f"WHEN json_array_length(p.packet_json, '$.blockers') BETWEEN 0 AND {MAX_SIGNAL_ITEMS} "
            "THEN json_array_length(p.packet_json, '$.blockers') ELSE NULL END, "
            "CASE WHEN json_type(p.packet_json, '$.uncovered_bmasia_senders') != 'array' THEN NULL "
            f"WHEN json_array_length(p.packet_json, '$.uncovered_bmasia_senders') BETWEEN 0 AND {MAX_SIGNAL_ITEMS} "
            "THEN json_array_length(p.packet_json, '$.uncovered_bmasia_senders') ELSE NULL END, "
            "json_extract(p.assessment_json, '$.decision') "
            "FROM accounts a JOIN packets p ON p.account_id=a.account_id "
            "WHERE a.account_id=? LIMIT 2",
            (item["company_id"],),
        ).fetchall()
        if not accounts:
            raise SourceError("SOURCE_ID_MISMATCH")
        if len(accounts) != 1:
            raise SourceError("SOURCE_DUPLICATE")
        account = accounts[0]
        if str(account[3] or "") != item["record_id"]:
            raise SourceError("SOURCE_ID_MISMATCH")
        observed = _timestamp(account[4] or account[6] or account[1], now=now)
        packet_hash = str(account[5])
        if not re.fullmatch(r"[0-9a-fA-F]{64}", packet_hash):
            raise SourceError("SOURCE_INVALID")
        cases = connection.execute(
            "SELECT json_extract(value, '$.case_id'), json_extract(value, '$.state'), "
            "json_extract(value, '$.next_follow_up_at'), json_extract(value, '$.owner') "
            "FROM settings WHERE key LIKE 'historical-case:%' "
            "AND json_extract(value, '$.account_id')=? ORDER BY key LIMIT 26",
            (account[0],),
        ).fetchall()
        if len(cases) > MAX_CASES:
            raise SourceError("SOURCE_RESULT_LIMIT")
        follow_ups, follow_up_holds = _cara_follow_ups(cases, now=now)
        holds = _fixed_holds(account[7], account[8], account[9], account[11], account[10])
        holds.extend(follow_up_holds)
        holds.append("SOURCE_RUNTIME_HEALTH_UNVERIFIED")
        facts = {"primary_contact_id": str(account[3]), "packet_hash": packet_hash, "assessment_decision": _safe_decision(account[11]), "uncovered_sender_count": account[10] if isinstance(account[10], int) and account[10] >= 0 else None}
        metadata = {"account_id": account[0], "last_collected_at": account[1], "collection_state": account[2], "packet_hash": packet_hash, "observed_at": observed, "cases": [list(row) for row in cases]}
        return _observation(item, observed, packet_hash, facts, sorted(set(holds)), follow_ups, _json_hash(metadata))
    except sqlite3.Error as exc:
        raise SourceError("SOURCE_INVALID") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass


def _safe_code(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 80 or not value.replace("_", "").replace("-", "").isalnum():
        return None
    return value


def _safe_decision(value: Any) -> str | None:
    code = _safe_code(value)
    if code is None:
        return "UNKNOWN" if value is not None else None
    normalized = code.upper()
    return normalized if normalized in {"BLOCKED", "HOLD", "NEEDS_ATTENTION", "WAITING", "PASS", "CLEAR", "UNKNOWN"} else "UNKNOWN"


def _cara_follow_ups(rows: list[tuple[Any, ...]], *, now: datetime) -> tuple[list[dict[str, Any]], list[str]]:
    follow_ups: list[dict[str, Any]] = []
    holds: set[str] = set()
    allowed_states = {"OPEN", "CLOSED", "WAITING", "PENDING", "COMPLETE"}
    allowed_owners = {"production": "Production", "keith": "Keith", "norbert": "Norbert", "scott": "Scott"}
    for row in rows:
        case_id = row[0]
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", case_id):
            holds.add("NEEDS_ATTENTION")
            continue
        state = _safe_code(row[1])
        owner_code = _safe_code(row[3])
        if state not in allowed_states:
            state = "UNKNOWN"
            holds.add("NEEDS_ATTENTION")
        owner = allowed_owners.get(owner_code.casefold()) if owner_code is not None else None
        if owner is None:
            owner = "UNKNOWN"
            holds.add("NEEDS_ATTENTION")
        due_at = _canonical_due_at(row[2])
        if row[2] is not None and due_at is None:
            holds.add("NEEDS_ATTENTION")
        if due_at is not None and state in {"OPEN", "WAITING", "PENDING"} and datetime.fromisoformat(due_at) <= now:
            holds.add("FOLLOW_UP_DUE")
        if state == "WAITING":
            holds.add("WAITING")
        follow_ups.append({"case_id": case_id, "state": state, "due_at": due_at, "owner": owner})
    return follow_ups, sorted(holds)


def _canonical_due_at(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        if "T" not in value:
            return None
        return _parse_aware(value, "case due_at").isoformat()
    except (ScopeError, ValueError):
        return None


def _fixed_holds(raw_holds: Any, raw_blockers: Any, packet_blockers: Any, decision: Any, senders: Any) -> list[str]:
    labels: set[str] = set()
    for raw, label in ((raw_holds, "UNRESOLVED_BLOCKER"), (raw_blockers, "CRM_HOLD"), (packet_blockers, "UNRESOLVED_BLOCKER")):
        if not isinstance(raw, int) or isinstance(raw, bool) or raw != 0:
            labels.add(label)
    if isinstance(decision, str) and decision.upper() in {"BLOCKED", "HOLD"}:
        labels.add("ASSESSMENT_BLOCKED")
    if isinstance(decision, str) and decision.upper() in {"NEEDS_ATTENTION", "WAITING"}:
        labels.add(decision.upper())
    if not isinstance(senders, int) or isinstance(senders, bool) or senders != 0:
        labels.add("UNRESOLVED_BLOCKER")
    return sorted(labels & HOLD_LABELS)


def _observation(item: Mapping[str, str], observed: str, version_hash: str, facts: dict[str, Any], holds: list[str], follow_ups: list[dict[str, Any]], payload_hash: str) -> dict[str, Any]:
    stable = {"source": item["source"], "company_id": item["company_id"], "record": {"collection": item["collection"], "id": item["record_id"]}, "source_observed_at": observed, "source_version_hash": version_hash, "facts": facts, "holds": holds, "follow_ups": follow_ups, "source_payload_sha256": payload_hash}
    stable["observation_id"] = str(uuid.uuid5(OBSERVATION_NAMESPACE, json.dumps(stable, sort_keys=True, separators=(",", ":"))))
    stable["source_authentication"] = AUTHENTICATION
    return stable


def extract_scope(scope: Any, *, now: datetime | None = None, sales_root: Path = SALES_ROOT, cara_db: Path = CARA_DB) -> dict[str, Any]:
    current = _utc_now(now)
    valid = validate_scope(scope, now=current)
    observations: list[dict[str, Any]] = []
    for item in valid["accounts"]:
        try:
            observation = _sales_observation(item, sales_root=sales_root, now=current) if item["source"] == "bmasia_sales" else _cara_observation(item, cara_db=cara_db, now=current)
        except SourceError as exc:
            observation = _source_failure(item, str(exc))
        observations.append(observation)
    return {"schema": OUTPUT_SCHEMA, "scope_id": valid["scope_id"], "imported_at": current.isoformat(), "observations": observations}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", required=True, help="absolute JSON scope file")
    args = parser.parse_args(argv)
    try:
        scope_path = Path(args.scope)
        if not scope_path.is_absolute() or scope_path.is_symlink():
            raise ScopeError("scope path must be an absolute regular file")
        stat = scope_path.stat()
        if not scope_path.is_file() or stat.st_size > MAX_SCOPE_BYTES:
            raise ScopeError("scope path must be a bounded regular file")
        scope = _strict_json(scope_path.read_bytes())
        print(json.dumps(extract_scope(scope), sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, ScopeError):
        print(json.dumps({"schema": OUTPUT_SCHEMA, "status": "REJECTED", "error_code": "SCOPE_REJECTED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
