#!/usr/bin/env python3
"""Read-only, metadata-only exports from the four audited native runtimes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "bmasia.agent-production-export.v1"
AUTHENTICATION = "operator_snapshot_set_collector"
MAX = 5000
MAX_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
PATHS = {
    "theo": Path("/opt/theo-hermes/data/runtime/client-activity/activity.sqlite3"),
    "lyra": Path("/home/bmasia/.bmasia-client-activity/activity.sqlite3"),
    "riff": Path("/opt/riff-hermes/data/runtime/riff-events"),
    "nina": Path("/home/nina/nina-agent/data/workstream/nina.md"),
}
FAILURE_NAMESPACE = uuid.UUID("7fe7ecf7-ab21-5ea2-bf36-fc62a56083a2")
FATAL_HOLDS = {
    "SOURCE_CONFLICT", "SOURCE_FUTURE", "SOURCE_INCOMPLETE", "SOURCE_INVALID",
    "SOURCE_MISSING", "SOURCE_PATH_REJECTED", "SOURCE_RESULT_LIMIT",
    "SOURCE_SCHEMA_UNSUPPORTED", "SOURCE_STALE",
}
SAFE_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
HEX_HASH = re.compile(r"[0-9a-fA-F]{64}")


class ExportError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def strict_json(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))


def uid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except ValueError:
        return None


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def _stable_failure(source: str, identity: str) -> str:
    return "failure:" + str(uuid.uuid5(FAILURE_NAMESPACE, source + ":" + identity))


def row(
    key: str,
    companies: Iterable[str] = (),
    record: Mapping[str, str] | None = None,
    observed: datetime | None = None,
    version: str | None = None,
    facts: Mapping[str, Any] | None = None,
    holds: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "source_key": key,
        "company_ids": sorted(set(companies)),
        "record": dict(record) if record is not None else None,
        "observed_at": iso(observed),
        "version_hash": version.lower() if isinstance(version, str) and HEX_HASH.fullmatch(version) else None,
        "facts": dict(facts or {}),
        "holds": sorted(set(holds)),
        "follow_ups": [],
    }


def failure(source: str, code: str, identity: str = "source") -> dict[str, Any]:
    return row(_stable_failure(source, identity), holds=[code])


def _coverage(records: list[dict[str, Any]], *, complete: bool) -> dict[str, Any]:
    failed = sum(bool(set(item["holds"]) & FATAL_HOLDS) for item in records)
    unbound = sum(item["record"] is None and not set(item["holds"]) & FATAL_HOLDS for item in records)
    return {
        "total": len(records), "exported": len(records) - failed - unbound,
        "complete": complete, "unbound": unbound, "failed": failed,
        "agent_inventory_complete": False,
        "legacy_baseline_complete": False,
    }


def document(source: str, records: list[dict[str, Any]], now: datetime, *, complete: bool) -> dict[str, Any]:
    if len(records) > MAX:
        raise ExportError("SOURCE_RESULT_LIMIT")
    observed = [item["observed_at"] for item in records if item["observed_at"]]
    result = {
        "schema": SCHEMA, "source": source, "source_authentication": AUTHENTICATION,
        "exported_at": iso(now), "source_observed_at": max(observed) if observed else None,
        "coverage": _coverage(records, complete=complete),
        "records": sorted(records, key=lambda item: item["source_key"]),
    }
    result["export_sha256"] = digest({key: value for key, value in result.items() if key not in {"exported_at", "export_sha256"}})
    if len(canon(result)) + 1 > MAX_BYTES:
        raise ExportError("EXPORT_SIZE_LIMIT")
    return result


def _safe_file(path: Path, *, maximum: int | None = None) -> Path:
    try:
        resolved = path.resolve(strict=True)
        info = path.lstat()
    except OSError as exc:
        raise ExportError("SOURCE_MISSING") from exc
    limit = MAX_SOURCE_BYTES if maximum is None else maximum
    if path.is_symlink() or not path.is_file() or info.st_uid != os.geteuid() or info.st_size > limit:
        raise ExportError("SOURCE_PATH_REJECTED")
    return resolved


def _time_holds(observed: datetime | None, now: datetime) -> list[str]:
    if observed is None:
        return ["SOURCE_INVALID"]
    if observed > now + timedelta(minutes=5):
        return ["SOURCE_FUTURE"]
    if observed < now - timedelta(hours=24):
        return ["SOURCE_STALE"]
    return []


def activity(source: str, path: Path, now: datetime) -> dict[str, Any]:
    try:
        resolved = _safe_file(path)
        connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            columns = {str(item[1]) for item in connection.execute("PRAGMA table_info(work)")}
            required = {"task_key", "source", "source_sha256", "state", "companies", "created_at", "updated_at", "revision"}
            if not required.issubset(columns):
                raise ExportError("SOURCE_SCHEMA_UNSUPPORTED")
            source_rows = connection.execute(
                "SELECT task_key,source,source_sha256,state,companies,created_at,updated_at,revision "
                "FROM work ORDER BY task_key LIMIT ?", (MAX + 1,),
            ).fetchall()
        finally:
            connection.close()
        if len(source_rows) > MAX:
            raise ExportError("SOURCE_RESULT_LIMIT")
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, (task_key, _origin, version, state, companies, created, updated, revision) in enumerate(source_rows):
            holds = {"UNBOUND_CRM_RECORD"}
            # Task keys can contain customer-controlled prose.  A deterministic
            # digest is stable without disclosing the key.
            source_key = "work:" + hashlib.sha256(str(task_key).encode()).hexdigest()
            if not isinstance(task_key, str) or not task_key:
                holds.add("SOURCE_INVALID")
            if source_key in seen:
                holds.add("SOURCE_CONFLICT")
                source_key = _stable_failure(source, "duplicate:" + digest([source_key, index]))
            seen.add(source_key)
            try:
                parsed_companies = strict_json(companies.encode()) if isinstance(companies, str) else None
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                parsed_companies = None
            normalized_companies: list[str] = []
            if not isinstance(parsed_companies, list) or len(parsed_companies) > 100:
                holds.add("SOURCE_INVALID")
            else:
                for company in parsed_companies:
                    normalized = uid(company)
                    if normalized is None:
                        holds.add("SOURCE_INVALID")
                    else:
                        normalized_companies.append(normalized)
            observed = stamp(updated) or stamp(created)
            holds.update(_time_holds(observed, now))
            normalized_version = version.lower() if isinstance(version, str) and HEX_HASH.fullmatch(version) else None
            if normalized_version is None:
                holds.add("SOURCE_INVALID")
            if not isinstance(state, str) or not SAFE_CODE.fullmatch(state):
                state_fact = "UNKNOWN"
                holds.add("SOURCE_INVALID")
            else:
                state_fact = state
            if type(revision) is not int or revision < 0:
                revision_fact = 0
                holds.add("SOURCE_INVALID")
            else:
                revision_fact = revision
            facts = {
                "state": state_fact, "revision": revision_fact,
                "source_complete": True, "agent_inventory_complete": False,
                "legacy_baseline_complete": False,
            }
            records.append(row(source_key, normalized_companies, None, observed, normalized_version, facts, holds))
        return document(source, records, now, complete=True)
    except sqlite3.Error:
        return document(source, [failure(source, "SOURCE_INVALID")], now, complete=False)
    except ExportError as exc:
        return document(source, [failure(source, str(exc))], now, complete=False)


def nina_export(source: str, path: Path, now: datetime) -> dict[str, Any]:
    try:
        resolved = _safe_file(path)
        info = resolved.stat()
        observed = datetime.fromtimestamp(info.st_mtime, UTC)
        holds = {"UNBOUND_CRM_RECORD", *_time_holds(observed, now)}
        facts = {"source_complete": True, "agent_inventory_complete": False, "legacy_baseline_complete": False}
        record = row("workstream:nina", observed=observed, version=hashlib.sha256(resolved.read_bytes()).hexdigest(), facts=facts, holds=holds)
        return document(source, [record], now, complete=True)
    except ExportError as exc:
        return document(source, [failure(source, str(exc))], now, complete=False)
    except OSError:
        return document(source, [failure(source, "SOURCE_INVALID")], now, complete=False)


def _safe_queue_files(path: Path) -> list[tuple[str, Path]]:
    try:
        root = path.resolve(strict=True)
        root_info = path.lstat()
    except OSError as exc:
        raise ExportError("SOURCE_MISSING") from exc
    parent_owner_ok = root_info.st_uid == os.geteuid() or (
        root_info.st_uid == 0
        and not stat.S_IMODE(root_info.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
    )
    if path.is_symlink() or not path.is_dir() or not parent_owner_ok:
        raise ExportError("SOURCE_PATH_REJECTED")
    files: list[tuple[str, Path]] = []
    for state in ("pending", "processing", "completed", "failed"):
        directory = root / state
        if not directory.exists():
            continue
        directory_info = directory.lstat()
        if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root or directory_info.st_uid != os.geteuid():
            raise ExportError("SOURCE_PATH_REJECTED")
        for item in sorted(directory.glob("*.json"), key=lambda value: value.name):
            info = item.lstat()
            if item.is_symlink() or not item.is_file() or item.resolve().parent != directory.resolve() or info.st_uid != os.geteuid() or info.st_size > MAX_SOURCE_BYTES:
                raise ExportError("SOURCE_PATH_REJECTED")
            files.append((state, item))
            if len(files) > MAX:
                raise ExportError("SOURCE_RESULT_LIMIT")
    return files


def riff_export(source: str, path: Path, now: datetime) -> dict[str, Any]:
    try:
        selected: dict[str, tuple[datetime, dict[str, Any]]] = {}
        failures: list[dict[str, Any]] = []
        files = _safe_queue_files(path)
        for state, item in files:
            raw = item.read_bytes()
            identity = hashlib.sha256(item.name.encode()).hexdigest()
            try:
                payload = strict_json(raw)
                if not isinstance(payload, dict):
                    raise ValueError("invalid_payload")
                event = payload.get("event_id") or payload.get("event_key")
                if not isinstance(event, str) or not SAFE_CODE.fullmatch(event):
                    event = str(uuid.uuid5(FAILURE_NAMESPACE, "riff:event:" + identity))
                    invalid_event = True
                else:
                    invalid_event = False
                # Queue event identifiers are operationally stable but may be
                # human-authored; digest them before crossing the boundary.
                source_key = "event:" + hashlib.sha256(event.encode()).hexdigest()
                observed = stamp(payload.get("received_at"))
                if observed is None and type(payload.get("received_at_unix")) in (int, float):
                    try:
                        observed = datetime.fromtimestamp(payload["received_at_unix"], UTC)
                    except (OverflowError, OSError, ValueError):
                        observed = None
                holds = {"QUEUE_LIFECYCLE_NOT_BUSINESS_STATE", *_time_holds(observed, now)}
                if invalid_event:
                    holds.add("SOURCE_INVALID")
                company = uid(payload.get("company_id"))
                record_id = uid(payload.get("record_id"))
                collection = payload.get("collection")
                valid_collection = collection in {"contacts", "opportunities", "tickets", "zones"}
                bound = company is not None and record_id is not None and valid_collection
                if not bound:
                    holds.add("UNBOUND_CRM_RECORD")
                    if any(payload.get(key) is not None for key in ("company_id", "record_id", "collection")):
                        holds.add("SOURCE_INVALID")
                record = {"collection": collection, "id": record_id} if bound else None
                facts = {
                    "queue_state": state, "source_complete": True,
                    "agent_inventory_complete": False, "legacy_baseline_complete": False,
                }
                candidate = row(source_key, [company] if company else [], record, observed, hashlib.sha256(raw).hexdigest(), facts, holds)
                ordering = observed or datetime.fromtimestamp(item.stat().st_mtime, UTC)
                prior = selected.get(source_key)
                if prior is None or ordering > prior[0]:
                    if prior is not None:
                        candidate["holds"] = sorted(set(candidate["holds"]) | {"SOURCE_CONFLICT"})
                    selected[source_key] = (ordering, candidate)
                elif candidate != prior[1]:
                    prior[1]["holds"] = sorted(set(prior[1]["holds"]) | {"SOURCE_CONFLICT"})
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                failures.append(failure(source, "SOURCE_INVALID", "file:" + identity))
        records = [value[1] for value in selected.values()] + failures
        # A genuinely empty queue is a complete, empty snapshot, not a source
        # failure.  This permits the ledger to retire old queue observations.
        return document(source, records, now, complete=True)
    except ExportError as exc:
        return document(source, [failure(source, str(exc))], now, complete=False)
    except OSError:
        return document(source, [failure(source, "SOURCE_INVALID")], now, complete=False)


def export(source: str, now: datetime | None = None, path: Path | None = None) -> dict[str, Any]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    selected_path = Path(path) if path is not None else PATHS[source]
    if source in {"theo", "lyra"}:
        return activity(source, selected_path, current)
    if source == "nina":
        return nina_export(source, selected_path, current)
    if source == "riff":
        return riff_export(source, selected_path, current)
    raise ExportError("SOURCE_UNSUPPORTED")


def _write_private(path: Path, payload: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise ExportError("OUTPUT_PATH_REJECTED")
    parent = path.parent.resolve(strict=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-native-export-", dir=parent)
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


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=PATHS, required=True)
    parser.add_argument("--output")
    args = parser.parse_args(arguments)
    try:
        result = export(args.source)
        payload = canon(result) + b"\n"
        if args.output:
            output = Path(args.output)
            if not output.is_absolute():
                raise ExportError("OUTPUT_PATH_REJECTED")
            _write_private(output, payload)
            receipt = {"schema": SCHEMA, "source": args.source, "export_sha256": result["export_sha256"], "coverage": result["coverage"]}
            print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        else:
            sys.stdout.buffer.write(payload)
        return 0
    except (OSError, ExportError):
        print(json.dumps({"schema": SCHEMA, "source": args.source, "status": "REJECTED", "error_code": "EXPORT_REJECTED"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
