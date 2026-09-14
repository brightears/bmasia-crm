#!/usr/bin/env python3
"""Pure, bounded local metadata exports for the agent-maintained CRM ledger.

The collectors in this module do not authenticate to either source, invoke a
source workflow, or mutate source state.  They read an operator-owned snapshot
set and emit only allowlisted CRM metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from agent_crm_source_observations import (
    CARA_DB,
    MAX_JSON_SOURCE_BYTES,
    MAX_SCOPE_AGE,
    MAX_SIGNAL_ITEMS,
    SALES_ROOT,
    ScopeError,
    SourceError,
    _fixed_holds,
    _parse_aware,
    _safe_decision,
    _sales_facts,
    _strict_json,
    _utc_now,
)

OUTPUT_SCHEMA = "bmasia.agent-production-export.v1"
AUTHENTICATION = "operator_snapshot_set_collector"
MAX_RECORDS = 5000
MAX_CASES = 1000
MAX_REPORT_FILES = 5000
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
FAILURE_NAMESPACE = uuid.UUID("740a855a-7b05-5ea7-8279-2854636ea68e")
HEX_HASH = re.compile(r"[0-9a-fA-F]{64}")
SAFE_STATE = re.compile(r"[A-Za-z0-9_-]{1,80}")
FATAL_HOLDS = {
    "SOURCE_COLLECTION_FAILED",
    "SOURCE_CONFLICT",
    "SOURCE_FUTURE",
    "SOURCE_INCOMPLETE",
    "SOURCE_INVALID",
    "SOURCE_MISSING",
    "SOURCE_SCHEMA_UNSUPPORTED",
    "SOURCE_STALE",
}
NON_FATAL_SOURCE_HOLDS = {"SOURCE_EVIDENCE_MISSING", "SOURCE_RUNTIME_HEALTH_UNVERIFIED"}


class ExportError(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _uuid_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def _safe_state(value: Any) -> str | None:
    if not isinstance(value, str) or not SAFE_STATE.fullmatch(value):
        return None
    return value.upper()


def _timestamp_status(value: Any, *, now: datetime) -> tuple[str | None, str | None]:
    try:
        parsed = _parse_aware(value, "source timestamp")
    except ScopeError:
        return None, "SOURCE_INVALID"
    if parsed > now:
        return parsed.isoformat(), "SOURCE_FUTURE"
    if parsed < now - MAX_SCOPE_AGE:
        return parsed.isoformat(), "SOURCE_STALE"
    return parsed.isoformat(), None


def _source_key(collection: str, record_id: str) -> str:
    return f"{collection}:{record_id}"


def _failure_key(source: str, identity: str) -> str:
    return f"failure:{uuid.uuid5(FAILURE_NAMESPACE, source + ':' + identity)}"


def _failure_record(source: str, code: str, identity: str) -> dict[str, Any]:
    return {
        "source_key": _failure_key(source, identity),
        "company_ids": [],
        "record": None,
        "observed_at": None,
        "version_hash": None,
        "facts": {},
        "holds": [code],
        "follow_ups": [],
    }


def _record(
    *,
    source_key: str,
    company_ids: Iterable[str],
    record: Mapping[str, str] | None,
    observed_at: str | None,
    version_hash: str | None,
    facts: Mapping[str, Any],
    holds: Iterable[str],
    follow_ups: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "company_ids": sorted(set(company_ids)),
        "record": dict(record) if record is not None else None,
        "observed_at": observed_at,
        "version_hash": version_hash,
        "facts": dict(facts),
        "holds": sorted(set(holds)),
        "follow_ups": list(follow_ups),
    }


def _coverage(records: list[dict[str, Any]], *, complete: bool) -> dict[str, Any]:
    exported = unbound = failed = 0
    for row in records:
        source_failure = any(hold.startswith("SOURCE_") and hold not in NON_FATAL_SOURCE_HOLDS for hold in row["holds"])
        if FATAL_HOLDS.intersection(row["holds"]) or source_failure:
            failed += 1
        elif row["record"] is None:
            unbound += 1
        else:
            exported += 1
    return {"total": len(records), "exported": exported, "complete": complete, "unbound": unbound, "failed": failed}


def _document(source: str, records: list[dict[str, Any]], *, now: datetime, complete: bool) -> dict[str, Any]:
    if len(records) > MAX_RECORDS:
        raise ExportError("SOURCE_RESULT_LIMIT")
    observed = [row["observed_at"] for row in records if row["observed_at"]]
    document: dict[str, Any] = {
        "schema": OUTPUT_SCHEMA,
        "source": source,
        "source_authentication": AUTHENTICATION,
        "exported_at": now.isoformat(),
        "source_observed_at": max(observed) if observed else None,
        "coverage": _coverage(records, complete=complete),
        "records": sorted(records, key=lambda row: row["source_key"]),
    }
    # Collection time is deliberately excluded; repeated reads of identical
    # source state therefore have one stable import identity.
    hash_input = {key: value for key, value in document.items() if key != "exported_at"}
    document["export_sha256"] = _hash(hash_input)
    if len(_canonical_bytes(document)) + 1 > MAX_OUTPUT_BYTES:
        raise ExportError("EXPORT_SIZE_LIMIT")
    return document


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _open_cara(path: Path) -> sqlite3.Connection:
    try:
        resolved = path.resolve(strict=True)
        stat = path.lstat()
    except OSError as exc:
        raise ExportError("SOURCE_MISSING") from exc
    if path.is_symlink() or not path.is_file() or stat.st_uid != os.geteuid():
        raise ExportError("SOURCE_PATH_REJECTED")
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _cara_cases(connection: sqlite3.Connection) -> tuple[dict[str, list[tuple[Any, ...]]], list[dict[str, Any]]]:
    cases: dict[str, list[tuple[Any, ...]]] = {}
    failures: list[dict[str, Any]] = []
    rows = connection.execute(
        "SELECT key, CASE WHEN json_valid(value) THEN json_extract(value,'$.account_id') END, "
        "CASE WHEN json_valid(value) THEN json_extract(value,'$.case_id') END, "
        "CASE WHEN json_valid(value) THEN json_extract(value,'$.state') END, "
        "CASE WHEN json_valid(value) THEN json_extract(value,'$.next_follow_up_at') END, "
        "CASE WHEN json_valid(value) THEN json_extract(value,'$.owner') END, json_valid(value) "
        "FROM settings WHERE key LIKE 'historical-case:%' ORDER BY key LIMIT ?",
        (MAX_CASES + 1,),
    ).fetchall()
    if len(rows) > MAX_CASES:
        raise ExportError("SOURCE_RESULT_LIMIT")
    for key, account_id, case_id, state, due_at, owner, valid in rows:
        identity = hashlib.sha256(str(key).encode()).hexdigest()
        company = _uuid_or_none(account_id)
        if not valid or company is None:
            failures.append(_failure_record("cara", "SOURCE_INVALID", "case:" + identity))
            continue
        cases.setdefault(company, []).append((case_id, state, due_at, owner))
    return cases, failures


def _cara_followups(rows: list[tuple[Any, ...]], *, now: datetime) -> tuple[list[dict[str, Any]], list[str]]:
    follow_ups: list[dict[str, Any]] = []
    holds: set[str] = set()
    allowed_states = {"OPEN", "CLOSED", "WAITING", "PENDING", "COMPLETE", "RESOLVED"}
    owners = {"production": "Production", "keith": "Keith", "norbert": "Norbert", "scott": "Scott"}
    for case_id, raw_state, raw_due, raw_owner in rows:
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", case_id):
            holds.add("NEEDS_ATTENTION")
            continue
        state = _safe_state(raw_state)
        if state not in allowed_states:
            state = "UNKNOWN"
            holds.add("NEEDS_ATTENTION")
        owner = owners.get(raw_owner.casefold()) if isinstance(raw_owner, str) else None
        if owner is None:
            owner = "UNKNOWN"
            holds.add("NEEDS_ATTENTION")
        due_at = None
        if raw_due is not None:
            try:
                # A date has no timezone, so it is not a due instant.
                if not isinstance(raw_due, str) or "T" not in raw_due:
                    raise ScopeError("case due_at must be aware")
                due_at = _parse_aware(raw_due, "case due_at").isoformat()
            except ScopeError:
                holds.add("NEEDS_ATTENTION")
        if due_at is not None and state in {"OPEN", "WAITING", "PENDING"} and datetime.fromisoformat(due_at) <= now:
            holds.add("FOLLOW_UP_DUE")
        if state == "WAITING":
            holds.add("WAITING")
        follow_ups.append({"case_id": case_id, "state": state, "due_at": due_at, "owner": owner})
    return follow_ups, sorted(holds)


def export_cara(*, now: datetime | None = None, cara_db: Path = CARA_DB) -> dict[str, Any]:
    current = _utc_now(now)
    records: list[dict[str, Any]] = []
    complete = False
    try:
        connection = _open_cara(cara_db)
        try:
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"accounts", "packets", "settings"}.issubset(tables):
                raise ExportError("SOURCE_SCHEMA_UNSUPPORTED")
            if not {"account_id", "last_collected_at", "collection_state", "blockers_json"}.issubset(_columns(connection, "accounts")):
                raise ExportError("SOURCE_SCHEMA_UNSUPPORTED")
            if not {"account_id", "packet_sha256", "collected_at", "packet_json", "assessment_json"}.issubset(_columns(connection, "packets")):
                raise ExportError("SOURCE_SCHEMA_UNSUPPORTED")
            account_count = int(connection.execute("SELECT count(*) FROM accounts").fetchone()[0])
            if account_count > MAX_RECORDS:
                raise ExportError("SOURCE_RESULT_LIMIT")
            cases, case_failures = _cara_cases(connection)
            rows = connection.execute(
                "SELECT a.account_id,a.last_collected_at,a.collection_state,"
                "CASE WHEN json_valid(a.blockers_json) AND json_type(a.blockers_json)='array' "
                f"AND json_array_length(a.blockers_json)<={MAX_SIGNAL_ITEMS} THEN json_array_length(a.blockers_json) END,"
                "CASE WHEN json_valid(p.packet_json) THEN json_extract(p.packet_json,'$.crm.primary_contact_id') END,"
                "CASE WHEN json_valid(p.packet_json) THEN json_extract(p.packet_json,'$.observed_at') END,"
                "p.packet_sha256,p.collected_at,"
                "CASE WHEN json_valid(p.packet_json) AND json_type(p.packet_json,'$.crm.holds')='array' "
                f"AND json_array_length(p.packet_json,'$.crm.holds')<={MAX_SIGNAL_ITEMS} THEN json_array_length(p.packet_json,'$.crm.holds') END,"
                "CASE WHEN json_valid(p.packet_json) AND json_type(p.packet_json,'$.blockers')='array' "
                f"AND json_array_length(p.packet_json,'$.blockers')<={MAX_SIGNAL_ITEMS} THEN json_array_length(p.packet_json,'$.blockers') END,"
                "CASE WHEN json_valid(p.packet_json) AND json_type(p.packet_json,'$.uncovered_bmasia_senders')='array' "
                f"AND json_array_length(p.packet_json,'$.uncovered_bmasia_senders')<={MAX_SIGNAL_ITEMS} THEN json_array_length(p.packet_json,'$.uncovered_bmasia_senders') END,"
                "CASE WHEN json_valid(p.assessment_json) THEN json_extract(p.assessment_json,'$.decision') END,"
                "p.rowid,CASE WHEN p.rowid IS NULL THEN NULL ELSE json_valid(p.packet_json) END,"
                "CASE WHEN p.assessment_json IS NULL THEN NULL ELSE json_valid(p.assessment_json) END "
                "FROM accounts a LEFT JOIN packets p ON p.account_id=a.account_id ORDER BY a.account_id"
            ).fetchall()
            manifest = connection.execute(
                "SELECT CASE WHEN json_valid(value) THEN json_extract(value,'$.crm_accounts') END,"
                "CASE WHEN json_valid(value) THEN json_extract(value,'$.crm_book_complete') END "
                "FROM settings WHERE key='last_collection' LIMIT 2"
            ).fetchall()
            complete = len(manifest) == 1 and manifest[0][0] == account_count and manifest[0][1] in (1, True)
        finally:
            connection.close()
        seen: set[str] = set()
        for row in rows:
            company = _uuid_or_none(row[0])
            identity = hashlib.sha256(str(row[0]).encode()).hexdigest()
            if company is None or company in seen:
                records.append(_failure_record("cara", "SOURCE_INVALID" if company is None else "SOURCE_CONFLICT", "account:" + identity))
                continue
            seen.add(company)
            holds = set(_fixed_holds(row[3], row[8], row[9], row[11], row[10]))
            holds.add("SOURCE_RUNTIME_HEALTH_UNVERIFIED")
            state = _safe_state(row[2])
            if state is None:
                holds.add("SOURCE_INVALID")
            elif state == "FAILED":
                holds.add("SOURCE_COLLECTION_FAILED")
            contact = _uuid_or_none(row[4])
            if row[12] is None:
                holds.add("SOURCE_INCOMPLETE")
            elif contact is None:
                holds.add("SOURCE_EVIDENCE_MISSING")
            if row[13] == 0 or row[14] == 0:
                holds.add("SOURCE_INVALID")
            observed, timestamp_hold = _timestamp_status(row[5] or row[7] or row[1], now=current)
            if timestamp_hold:
                holds.add(timestamp_hold)
            packet_hash = str(row[6]).lower() if isinstance(row[6], str) and HEX_HASH.fullmatch(row[6]) else None
            if row[12] is not None and packet_hash is None:
                holds.add("SOURCE_INVALID")
            follow_ups, follow_holds = _cara_followups(cases.pop(company, []), now=current)
            holds.update(follow_holds)
            facts: dict[str, Any] = {}
            if state is not None:
                facts["collection_state"] = state
            if contact is not None:
                facts["primary_contact_id"] = contact
            decision = _safe_decision(row[11])
            if decision is not None:
                facts["assessment_decision"] = decision
            for name, value in (("account_blocker_count", row[3]), ("crm_hold_count", row[8]), ("packet_blocker_count", row[9]), ("uncovered_sender_count", row[10])):
                if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SIGNAL_ITEMS:
                    facts[name] = value
            record = {"collection": "contacts", "id": contact} if contact else None
            records.append(_record(source_key="account:" + company, company_ids=[company], record=record, observed_at=observed, version_hash=packet_hash, facts=facts, holds=holds, follow_ups=follow_ups))
        # Well-formed cases for accounts absent from the account inventory are
        # source-health failures and never invent a CRM binding.
        for company, orphaned in cases.items():
            records.append(_failure_record("cara", "SOURCE_INCOMPLETE", "orphan-case:" + company + ":" + _hash(orphaned)))
        records.extend(case_failures)
    except (sqlite3.Error, ExportError) as exc:
        code = str(exc) if isinstance(exc, ExportError) else "SOURCE_INVALID"
        records = [_failure_record("cara", code, "source")]
        complete = False
    return _document("cara", records, now=current, complete=complete)


def _safe_report_files(root: Path) -> list[Path]:
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ExportError("SOURCE_MISSING") from exc
    if not root.is_dir():
        raise ExportError("SOURCE_MISSING")
    files: list[Path] = []
    # The sorted iterator is the deterministic pagination order.  It is fully
    # consumed up to the hard inventory bound; this is never a sample.
    for path in sorted(root.glob("heartbeat-review-*.json"), key=lambda item: item.name):
        try:
            stat = path.lstat()
            child = path.resolve(strict=True)
        except OSError:
            continue
        if path.is_symlink() or not path.is_file() or child.parent != resolved or stat.st_uid != os.geteuid() or stat.st_size > MAX_JSON_SOURCE_BYTES:
            raise ExportError("SOURCE_PATH_REJECTED")
        files.append(path)
        if len(files) > MAX_REPORT_FILES:
            raise ExportError("SOURCE_RESULT_LIMIT")
    return files


def _sales_candidate(record: Mapping[str, Any], document: Mapping[str, Any], *, now: datetime) -> tuple[tuple[str, str], dict[str, Any]]:
    record_type = record.get("record_type")
    collection = {"contact": "contacts", "opportunity": "opportunities"}.get(record_type)
    if collection is None:
        raise SourceError("SOURCE_RECORD_UNSUPPORTED")
    record_id = _uuid_or_none(record.get("record_id"))
    company = _uuid_or_none(record.get("company_id"))
    if record_id is None or company is None:
        raise SourceError("SOURCE_INVALID")
    observed, timestamp_hold = _timestamp_status(document.get("created_at"), now=now)
    if observed is None:
        raise SourceError(timestamp_hold or "SOURCE_INVALID")
    context_hash = document.get("context_hash")
    if not isinstance(context_hash, str) or not HEX_HASH.fullmatch(context_hash):
        raise SourceError("SOURCE_INVALID")
    facts = _sales_facts(record)
    for name in ("is_active", "unsubscribed"):
        if name in record and record[name] is not None:
            if not isinstance(record[name], bool):
                raise SourceError("SOURCE_INVALID")
            facts[name] = record[name]
    if record.get("updated_at") is not None:
        updated, updated_hold = _timestamp_status(record["updated_at"], now=now)
        if updated_hold in {"SOURCE_INVALID", "SOURCE_FUTURE"}:
            raise SourceError(updated_hold)
        facts["updated_at"] = updated
    holds = {"SOURCE_RUNTIME_HEALTH_UNVERIFIED"}
    if timestamp_hold:
        holds.add(timestamp_hold)
    stable_key = f"{company}:{_source_key(collection, record_id)}"
    return (company, stable_key), {
        "source_key": stable_key,
        "company_ids": [company],
        "record": {"collection": collection, "id": record_id},
        "observed_at": observed,
        "version_hash": context_hash.lower(),
        "facts": facts,
        "holds": sorted(holds),
        "follow_ups": [],
    }


def export_bmasia_sales(*, now: datetime | None = None, sales_root: Path = SALES_ROOT) -> dict[str, Any]:
    current = _utc_now(now)
    selected: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    try:
        files = _safe_report_files(sales_root)
        if not files:
            raise ExportError("SOURCE_MISSING")
        for path in files:
            raw = path.read_bytes()
            # The filename is used only as an internal stable identity for an
            # error row.  Neither it nor the source path is emitted.
            file_identity = hashlib.sha256(path.name.encode()).hexdigest()
            try:
                document = _strict_json(raw)
                if not isinstance(document, dict):
                    raise SourceError("SOURCE_INVALID")
                observed_dt = _parse_aware(document.get("created_at"), "created_at")
                crm = document.get("crm_context")
                if not isinstance(crm, dict) or crm.get("complete") != "TRUE" or not isinstance(crm.get("records"), list):
                    raise SourceError("SOURCE_INCOMPLETE")
                companies = {_uuid_or_none(item.get("record_id")) for item in crm["records"] if isinstance(item, dict) and item.get("record_type") == "company"}
                companies.discard(None)
                supported = [item for item in crm["records"] if isinstance(item, dict) and item.get("record_type") in {"contact", "opportunity"}]
                if not supported:
                    raise SourceError("SOURCE_INCOMPLETE")
                for index, source_record in enumerate(supported):
                    try:
                        key, candidate = _sales_candidate(source_record, document, now=current)
                        if key[0] not in companies:
                            raise SourceError("SOURCE_INCOMPLETE")
                        prior = selected.get(key)
                        if prior is None or observed_dt > prior[0]:
                            selected[key] = (observed_dt, candidate)
                        elif observed_dt == prior[0] and candidate != prior[1]:
                            conflict = dict(candidate)
                            conflict["holds"] = sorted(set(conflict["holds"]) | {"SOURCE_CONFLICT"})
                            selected[key] = (observed_dt, conflict)
                    except (SourceError, ScopeError) as exc:
                        failures.append(_failure_record("bmasia_sales", str(exc), f"record:{file_identity}:{index}"))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ScopeError, SourceError) as exc:
                code = str(exc) if isinstance(exc, SourceError) else "SOURCE_INVALID"
                failures.append(_failure_record("bmasia_sales", code, "file:" + file_identity))
    except ExportError as exc:
        failures = [_failure_record("bmasia_sales", str(exc), "source")]
    records = [item[1] for item in selected.values()] + failures
    # Sealed heartbeat reports are an exact inventory of available evidence,
    # not a manifest of the whole CRM.  Never claim full-portfolio coverage.
    return _document("bmasia_sales", records, now=current, complete=False)


def export_source(source: str, *, now: datetime | None = None, cara_db: Path | None = None, sales_root: Path | None = None) -> dict[str, Any]:
    if source == "cara":
        return export_cara(now=now, cara_db=cara_db or CARA_DB)
    if source == "bmasia_sales":
        return export_bmasia_sales(now=now, sales_root=sales_root or SALES_ROOT)
    raise ExportError("SOURCE_UNSUPPORTED")


def _write_private(path: Path, payload: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise ExportError("OUTPUT_PATH_REJECTED")
    parent = path.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ExportError("OUTPUT_PATH_REJECTED")
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-crm-export-", dir=parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("cara", "bmasia_sales"), required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        document = export_source(args.source)
        payload = _canonical_bytes(document)
        if args.output:
            output = Path(args.output)
            if not output.is_absolute():
                raise ExportError("OUTPUT_PATH_REJECTED")
            _write_private(output, payload + b"\n")
            receipt = {"schema": OUTPUT_SCHEMA, "source": args.source, "export_sha256": document["export_sha256"], "coverage": document["coverage"]}
            print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        else:
            sys.stdout.buffer.write(payload + b"\n")
        return 0
    except (OSError, ExportError):
        print(json.dumps({"schema": OUTPUT_SCHEMA, "source": args.source, "status": "REJECTED", "error_code": "EXPORT_REJECTED"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
