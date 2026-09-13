"""Dependency-free, append-only shadow assessment ledger.

This module deliberately never imports CRM models.  Assessments are advisory
only: every returned receipt says ``crm_writes: 0`` and ``mode: shadow``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import stat
import uuid

REPORTERS = {"theo", "lyra", "riff", "nina"}
EVIDENCE_KINDS = {"email_message", "ticket_event", "agent_receipt", "document"}
ALLOWED = {
    "theo": {"opportunities": {"stage", "last_contact_date", "follow_up_date", "expected_close_date", "pain_points", "decision_criteria"},
             "contacts": {"title", "department", "last_contacted"}},
    "lyra": {"contacts": {"title", "department", "last_contacted"}},
    "riff": {"tickets": {"status", "priority"}},
    "nina": {"zones": {"notes"}},
}
FIELD_OWNERS = {}
for _reporter, _collections in ALLOWED.items():
    for _collection, _fields in _collections.items():
        for _field in _fields:
            FIELD_OWNERS.setdefault(_collection, {}).setdefault(_field, set()).add(_reporter)
FIELD_OWNERS = {c: {f: frozenset(v) for f, v in fields.items()} for c, fields in FIELD_OWNERS.items()}
FORBIDDEN = {"amount", "value", "price", "currency", "legal_name", "identity", "contract", "invoice", "quote", "sent", "activation", "zone_name", "name"}
SCALARS = (str, int, float, bool, type(None))


def canonical_hash(obj):
    """SHA-256 of canonical JSON; suitable for trusted adapter bindings."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                     allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _iso(value, label):
    if not isinstance(value, str):
        raise ValueError("%s must be ISO timestamp" % label)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("%s must be ISO timestamp" % label) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("%s must be timezone aware" % label)
    return parsed.astimezone(dt.timezone.utc)


def _uuid(value, label):
    if not isinstance(value, str):
        raise ValueError("%s must be UUID" % label)
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError("%s must be UUID" % label) from exc


def _exact(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError("%s has missing or unknown keys" % label)


def _scalar(value):
    return isinstance(value, SCALARS) and not isinstance(value, (list, dict)) and (not isinstance(value, float) or math.isfinite(value))


def validate_report(report):
    """Validate the narrow public report envelope (without altering its hash)."""
    _exact(report, {"schema", "event_id", "reporter", "observed_at", "record", "changes", "evidence", "follow_up"}, "report")
    if report["schema"] != "bmasia.agent-report.v1" or not isinstance(report["reporter"], str) or report["reporter"] not in REPORTERS:
        raise ValueError("invalid report schema or reporter")
    try:
        encoded = json.dumps(report, ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ValueError("report is not JSON-safe") from exc
    if len(encoded) > 32768:
        raise ValueError("report exceeds 32KB")
    _uuid(report["event_id"], "event_id")
    _iso(report["observed_at"], "observed_at")
    _exact(report["record"], {"collection", "id"}, "record")
    if not isinstance(report["record"]["collection"], str) or report["record"]["collection"] not in FIELD_OWNERS:
        raise ValueError("invalid collection")
    _uuid(report["record"]["id"], "record.id")
    if not isinstance(report["changes"], list) or len(report["changes"]) > 20:
        raise ValueError("changes must contain at most 20 entries")
    if not isinstance(report["evidence"], list) or not report["evidence"] or len(report["evidence"]) > 20:
        raise ValueError("evidence must contain 1-20 entries")
    fields_seen = set()
    for change in report["changes"]:
        _exact(change, {"field", "before", "after"}, "change")
        field = change["field"]
        if not isinstance(field, str) or not field.isidentifier() or field != field.lower():
            raise ValueError("change field must be lowercase identifier")
        if field in fields_seen:
            raise ValueError("duplicate change field")
        fields_seen.add(field)
        if not _scalar(change["before"]) or not _scalar(change["after"]):
            raise ValueError("change values must be scalars")
    for evidence in report["evidence"]:
        _exact(evidence, {"kind", "reference", "sha256"}, "evidence")
        if not isinstance(evidence["kind"], str) or evidence["kind"] not in EVIDENCE_KINDS or not isinstance(evidence["reference"], str) or not 0 < len(evidence["reference"].strip()) <= 200:
            raise ValueError("invalid evidence")
        if not isinstance(evidence["sha256"], str) or len(evidence["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in evidence["sha256"]):
            raise ValueError("invalid evidence sha256")
    follow = report["follow_up"]
    if follow is not None:
        _exact(follow, {"owner", "due_at", "reason"}, "follow_up")
        if not isinstance(follow["owner"], str) or follow["owner"] not in REPORTERS or not isinstance(follow["reason"], str) or not 0 < len(follow["reason"].strip()) <= 240:
            raise ValueError("invalid follow_up")
        _iso(follow["due_at"], "follow_up.due_at")
    if not report["changes"] and follow is None:
        raise ValueError("report needs a change or follow_up")
    return report


def _context(context, report):
    _exact(context, {"schema", "sender", "request_id", "report_sha256", "verified_evidence_sha256", "verified", "environment"}, "context")
    if context["schema"] != "bmasia.agent-shadow-context.v1" or not isinstance(context["environment"], str) or context["environment"] not in {"synthetic", "shadow"}:
        raise ValueError("invalid context")
    if not isinstance(context["sender"], str) or context["sender"] not in REPORTERS or not isinstance(context["request_id"], str) or not 0 < len(context["request_id"].strip()) <= 200:
        raise ValueError("invalid context sender/request")
    if context["sender"] != report["reporter"]:
        raise ValueError("context sender does not bind reporter")
    if context["report_sha256"] != canonical_hash(report):
        raise ValueError("context report hash mismatch")
    values = context["verified_evidence_sha256"]
    if not isinstance(values, list) or len(values) > 20 or any(not isinstance(x, str) or len(x) != 64 or any(c not in "0123456789abcdef" for c in x) for x in values) or not isinstance(context["verified"], bool):
        raise ValueError("invalid context verification")


def _snapshot(snapshot, report, now):
    _exact(snapshot, {"collection", "id", "observed_at", "updated_at", "fields"}, "snapshot")
    if snapshot["collection"] != report["record"]["collection"] or _uuid(snapshot["id"], "snapshot.id") != _uuid(report["record"]["id"], "record.id"):
        raise ValueError("snapshot record binding mismatch")
    observed, updated = _iso(snapshot["observed_at"], "snapshot.observed_at"), _iso(snapshot["updated_at"], "snapshot.updated_at")
    if observed > now or updated > now or now - observed > dt.timedelta(hours=24):
        raise ValueError("snapshot is stale or future dated")
    if updated > observed:
        raise ValueError("snapshot updated_at is later than its observation")
    if observed < _iso(report["observed_at"], "report.observed_at"):
        raise ValueError("snapshot predates the report; read the record again")
    if not isinstance(snapshot["fields"], dict) or any(not isinstance(k, str) or not _scalar(v) for k, v in snapshot["fields"].items()):
        raise ValueError("invalid snapshot fields")
    return observed


def _field_value_valid(collection, field, value):
    """Model-shaped values; false means manual review, never an automatic pass."""
    if value is None:
        return field in {"last_contacted", "last_contact_date", "follow_up_date", "expected_close_date"}
    if field in {"title", "department"}:
        return isinstance(value, str) and len(value) <= 100
    if field == "last_contacted":
        try:
            _iso(value, field)
            return True
        except ValueError: return False
    if field in {"last_contact_date", "follow_up_date", "expected_close_date"}:
        try:
            dt.date.fromisoformat(value)
            return isinstance(value, str) and len(value) == 10
        except (TypeError, ValueError): return False
    if field == "stage": return value in {"Contacted", "Quotation Sent", "Contract Sent", "Won", "Lost"}
    if field in {"pain_points", "decision_criteria", "notes"}: return isinstance(value, str) and len(value) <= 4000
    if field == "status": return value in {"new", "assigned", "in_progress", "pending", "resolved", "closed"}
    if field == "priority": return value in {"low", "medium", "high", "urgent"}
    return False


def assess_report(report, context, snapshot, now=None):
    """Assess a report without writing CRM. Invalid trusted bindings raise ValueError."""
    validate_report(report)
    _context(context, report)
    now = (now or dt.datetime.now(dt.timezone.utc))
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    now = now.astimezone(dt.timezone.utc)
    if _iso(report["observed_at"], "observed_at") > now:
        raise ValueError("report observed_at is future dated")
    seen = _snapshot(snapshot, report, now)
    hashes = [x["sha256"] for x in report["evidence"]]
    source_verified = bool(context["verified"]) and all(x in context["verified_evidence_sha256"] for x in hashes)
    base = {"report_hash": canonical_hash(report), "evidence_hashes": hashes, "environment": context["environment"], "source_verification": source_verified, "mode": "shadow", "crm_writes": 0,
            "customer_record_mutation": False, "customer_outbound": False, "model_invoked": False,
            "freshness": {"snapshot_observed_at": seen.isoformat(), "age_seconds": int((now-seen).total_seconds())}, "reasons": [], "field_changes": []}
    if not source_verified:
        base.update(outcome="needs_source_verification", status="needs_source_verification", reasons=["trusted context has not verified every evidence hash"])
        return base
    if now - _iso(report["observed_at"], "observed_at") > dt.timedelta(hours=24):
        base.update(outcome="manual_review", status="manual_review", reasons=["report observation is over 24 hours old"])
        return base
    forbidden, conflict, changed = False, False, False
    allowed = ALLOWED.get(report["reporter"], {}).get(report["record"]["collection"], set())
    for item in report["changes"]:
        field = item["field"]
        status = "ready"
        if field not in allowed or field in FORBIDDEN:
            forbidden, status = True, "manual_review"
        elif field not in snapshot["fields"]:
            conflict, status = True, "snapshot_field_unknown"
        elif snapshot["fields"][field] != item["before"]:
            conflict, status = True, "before_mismatch"
        elif not _field_value_valid(report["record"]["collection"], field, item["after"]):
            forbidden, status = True, "manual_review"
        elif item["before"] == item["after"]:
            status = "no_change"
        else:
            changed = True
        base["field_changes"].append({"field": field, "before": item["before"],
                                      "current_present": field in snapshot["fields"],
                                      "current": snapshot["fields"].get(field),
                                      "after": item["after"], "status": status})
    if forbidden:
        outcome, reason = "manual_review", "field is outside agent authority or protected"
    elif conflict:
        outcome, reason = "conflict", "snapshot value differs from report before value"
    elif report["changes"] and not changed and report["follow_up"] is None:
        outcome, reason = "no_change", "all requested values already match"
    else:
        outcome, reason = "ready_for_cira_review", "advisory report is source-verified"
    base.update(outcome=outcome, status=outcome, reasons=[reason])
    return base


class ShadowLedger:
    """Append-only SQLite event ledger.  It never applies its assessments."""
    def __init__(self, path):
        self.path = os.fspath(path)
        if os.path.islink(self.path):
            raise ValueError("ledger path may not be a symlink")
        parent = os.path.dirname(os.path.abspath(self.path))
        if not os.path.isdir(parent):
            raise ValueError("ledger parent does not exist")
        if os.stat(parent).st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ValueError("ledger parent must be private")
        self._init()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _init(self):
        exists = os.path.exists(self.path)
        if not exists:
            # Do not briefly expose a new ledger with permissive default mode.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, stat.S_IRUSR | stat.S_IWUSR)
            os.close(fd)
        db = self._connect()
        try:
            marker = db.execute("PRAGMA application_id").fetchone()[0]
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            allowed_tables = {"shadow_events", "shadow_receipts", "shadow_meta", "shadow_attempts"}
            if (marker not in (0, 1112756048) or not tables.issubset(allowed_tables)):
                raise ValueError("refusing non-shadow SQLite database")
            if exists and tables and marker != 1112756048:
                raise ValueError("refusing unmarked existing SQLite database")
            db.execute("CREATE TABLE IF NOT EXISTS shadow_events (reporter TEXT NOT NULL,event_id TEXT NOT NULL,report_hash TEXT NOT NULL,semantic_hash TEXT NOT NULL,record_collection TEXT NOT NULL,record_id TEXT NOT NULL,report_json TEXT NOT NULL,context_json TEXT NOT NULL,snapshot_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(reporter,event_id))")
            db.execute("CREATE TABLE IF NOT EXISTS shadow_receipts (receipt_id TEXT PRIMARY KEY,reporter TEXT NOT NULL,event_id TEXT NOT NULL,outcome TEXT NOT NULL,receipt_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(reporter,event_id))")
            db.execute("CREATE TABLE IF NOT EXISTS shadow_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS shadow_attempts (receipt_id TEXT PRIMARY KEY,reporter TEXT NOT NULL,event_id TEXT NOT NULL,attempt_key TEXT NOT NULL,outcome TEXT NOT NULL,report_json TEXT NOT NULL,context_json TEXT NOT NULL,receipt_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(reporter,event_id,attempt_key))")
            db.execute("PRAGMA application_id=1112756048")  # BMAS
        finally:
            db.close()
        if os.path.exists(self.path):
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    @staticmethod
    def _attempt(db, report, context, original, now, outcome, reason):
        """Immutable, idempotent exception receipt with bounded provenance."""
        report_hash = canonical_hash(report)
        attempt_key = canonical_hash({"report_hash": report_hash, "outcome": outcome, "reason": reason})
        reporter, event_id = report["reporter"], str(uuid.UUID(report["event_id"]))
        previous = db.execute(
            "SELECT receipt_json FROM shadow_attempts WHERE reporter=? AND event_id=? AND attempt_key=?",
            (reporter, event_id, attempt_key)).fetchone()
        if previous:
            receipt = json.loads(previous[0])
            receipt["replay"] = True
            return receipt
        verified = context["verified"] and all(e["sha256"] in context["verified_evidence_sha256"]
                                               for e in report["evidence"])
        receipt = {
            "receipt_id": str(uuid.uuid4()), "reporter": reporter, "event_id": event_id,
            "outcome": outcome, "status": outcome, "reasons": [reason],
            "report_hash": report_hash, "mode": "shadow", "crm_writes": 0,
            "environment": context["environment"], "request_id": context["request_id"],
            "original_receipt_id": original["receipt_id"], "source_verification": verified,
            "customer_record_mutation": False, "customer_outbound": False, "model_invoked": False,
            "replay": False, "recorded_at": now.isoformat(),
        }
        db.execute("INSERT INTO shadow_attempts VALUES (?,?,?,?,?,?,?,?,?)",
                   (receipt["receipt_id"], reporter, event_id, attempt_key, outcome,
                    json.dumps(report, sort_keys=True), json.dumps(context, sort_keys=True),
                    json.dumps(receipt, sort_keys=True), now.isoformat()))
        return receipt

    def ingest(self, report, context, snapshot, now=None):
        # Bind the untrusted envelope to its local trusted adapter before any
        # lookup.  Snapshot freshness is intentionally assessed only for new
        # events so an exact retry remains reproducible after time passes.
        validate_report(report)
        _context(context, report)
        now = now or dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone aware")
        now = now.astimezone(dt.timezone.utc)
        reporter, event_id = report["reporter"], str(uuid.UUID(report["event_id"]))
        report_hash = canonical_hash(report)
        semantic = canonical_hash({k: report[k] for k in ("reporter", "record", "changes", "evidence", "follow_up")})
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            stored_environment = db.execute("SELECT value FROM shadow_meta WHERE key='environment'").fetchone()
            if stored_environment and stored_environment[0] != context["environment"]:
                db.rollback()
                raise ValueError("ledger may not mix synthetic and shadow environments")
            if not stored_environment:
                db.execute("INSERT INTO shadow_meta VALUES ('environment',?)", (context["environment"],))
            old = db.execute("SELECT e.report_hash,r.receipt_json FROM shadow_events e JOIN shadow_receipts r USING(reporter,event_id) WHERE e.reporter=? AND e.event_id=?", (reporter, event_id)).fetchone()
            if old:
                original = json.loads(old[1])
                if old[0] != report_hash:
                    receipt = self._attempt(db, report, context, original, now, "conflict",
                                            "event id collision with changed payload")
                    db.commit()
                    return receipt
                verified = context["verified"] and all(e["sha256"] in context["verified_evidence_sha256"]
                                                       for e in report["evidence"])
                if original["source_verification"] and not verified:
                    receipt = self._attempt(db, report, context, original, now, "needs_source_verification",
                                            "trusted evidence verification was downgraded on replay")
                    db.commit()
                    return receipt
                receipt = original
                receipt["replay"] = True
                db.commit()
                return receipt
            assessment = assess_report(report, context, snapshot, now)
            prior = None
            if assessment["outcome"] in {"ready_for_cira_review", "no_change"}:
                prior = db.execute("SELECT r.receipt_id FROM shadow_events e JOIN shadow_receipts r USING(reporter,event_id) WHERE e.semantic_hash=? AND r.outcome IN ('ready_for_cira_review','no_change')", (semantic,)).fetchone()
            if prior:
                assessment["outcome"] = "duplicate"
                assessment["status"] = "duplicate"
                assessment["reasons"] = ["semantic duplicate of prior event"]
                assessment["semantic_duplicate_of"] = prior[0]
            elif assessment["outcome"] == "ready_for_cira_review":
                rows = db.execute("SELECT e.report_json FROM shadow_events e JOIN shadow_receipts r USING(reporter,event_id) WHERE record_collection=? AND record_id=? AND r.outcome='ready_for_cira_review'", (report["record"]["collection"], str(uuid.UUID(report["record"]["id"])))).fetchall()
                proposed = {x["field"]: x["after"] for x in report["changes"]}
                for (raw,) in rows:
                    for old_change in json.loads(raw)["changes"]:
                        if old_change["field"] in proposed and old_change["after"] != proposed[old_change["field"]]:
                            assessment["outcome"] = "conflict"
                            assessment["status"] = "conflict"
                            assessment["reasons"] = ["unresolved cross-event proposed value conflict"]
                            break
                    if assessment["outcome"] == "conflict": break
            receipt = dict(assessment, receipt_id=str(uuid.uuid4()), request_id=context["request_id"], reporter=reporter, event_id=event_id, replay=False, recorded_at=now.isoformat())
            db.execute("INSERT INTO shadow_events VALUES (?,?,?,?,?,?,?,?,?,?)", (reporter,event_id,assessment["report_hash"],semantic,report["record"]["collection"],str(uuid.UUID(report["record"]["id"])),json.dumps(report, sort_keys=True),json.dumps(context, sort_keys=True),json.dumps(snapshot, sort_keys=True),now.isoformat()))
            db.execute("INSERT INTO shadow_receipts VALUES (?,?,?,?,?,?)", (receipt["receipt_id"],reporter,event_id,receipt["outcome"],json.dumps(receipt, sort_keys=True),now.isoformat()))
            db.commit()
            return receipt
        except Exception:
            if db.in_transaction: db.rollback()
            raise
        finally: db.close()

    def report(self, now=None):
        now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
        db = self._connect()
        try:
            rows = [json.loads(x[0]) for x in db.execute("SELECT receipt_json FROM shadow_receipts")]
        finally: db.close()
        outcomes, agents, overdue, latest = {}, {agent: 0 for agent in REPORTERS}, [], None
        per_agent = {agent: {"events": 0, "latest_source_observed": None, "lag_seconds": None} for agent in REPORTERS}
        for row in rows:
            outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
            agents[row["reporter"]] = agents.get(row["reporter"], 0) + 1
            # Follow-up and source observation come from the immutable event.
        exceptions = [{"receipt_id": r["receipt_id"], "reporter": r["reporter"], "event_id": r["event_id"], "reason": r["reasons"][0]} for r in rows
                      if r["outcome"] in {"conflict", "manual_review", "needs_source_verification"}]
        # Read immutable reports only to calculate due dates; no CRM data is touched.
        db = self._connect()
        try:
            environment_row = db.execute("SELECT value FROM shadow_meta WHERE key='environment'").fetchone()
            for raw, outcome, receipt_id in db.execute("SELECT e.report_json,r.outcome,r.receipt_id FROM shadow_events e JOIN shadow_receipts r USING(reporter,event_id)"):
                report = json.loads(raw)
                follow = report.get("follow_up")
                observed = _iso(report["observed_at"], "observed_at").isoformat()
                if latest is None or observed > latest: latest = observed
                item = per_agent[report["reporter"]]
                item["events"] += 1
                if item["latest_source_observed"] is None or observed > item["latest_source_observed"]:
                    item["latest_source_observed"] = observed
                if follow and outcome == "ready_for_cira_review" and _iso(follow["due_at"], "due_at") < now:
                    overdue.append({"receipt_id": receipt_id, "reporter": report["reporter"],
                                    "record": report["record"], **follow})
            collision_attempts = 0
            exception_attempts = 0
            for (raw,) in db.execute("SELECT receipt_json FROM shadow_attempts"):
                row = json.loads(raw)
                outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
                exception_attempts += 1
                collision_attempts += int(row["outcome"] == "conflict")
                exceptions.append({"receipt_id": row["receipt_id"], "reporter": row["reporter"],
                                   "event_id": row["event_id"], "reason": row["reasons"][0]})
        finally: db.close()
        for item in per_agent.values():
            if item["latest_source_observed"]:
                item["lag_seconds"] = int((now - _iso(item["latest_source_observed"], "observed_at")).total_seconds())
        return {"mode": "shadow", "environment": environment_row[0] if environment_row else None,
                "crm_writes": 0, "customer_record_mutation": False, "customer_outbound": False,
                "model_invoked": False, "healthy": None, "no_data": not bool(rows),
                "total_events": len(rows), "collision_attempts": collision_attempts,
                "exception_attempts": exception_attempts,
                "outcomes": outcomes, "agents": agents, "per_agent": per_agent,
                "overdue_followups": len(overdue), "overdue_items": overdue,
                "exceptions": exceptions, "latest_source_observed": latest}
