import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("production", ROOT / "tools" / "agent_crm_production.py")
production = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(production)

NOW = datetime(2026, 9, 14, 6, tzinfo=UTC)
COMPANY = "550e8400-e29b-41d4-a716-446655440000"
RECORD = "354d0392-e578-49e7-b239-1cf8113c42cf"


def make_row(*, key="work:one", companies=None, record=None, observed=None, facts=None, holds=None, follow_ups=None):
    return {
        "source_key": key,
        "company_ids": [COMPANY] if companies is None else companies,
        "record": record,
        "observed_at": (observed or (NOW - timedelta(minutes=5))).isoformat() if observed is not False else None,
        "version_hash": "a" * 64,
        "facts": facts or {},
        "holds": holds or [],
        "follow_ups": follow_ups or [],
    }


def make_export(source="theo", *, rows=None, exported=None, complete=False, coverage=None):
    rows = [make_row(facts={"state": "OPEN", "revision": 1, "source_complete": True, "agent_inventory_complete": False, "legacy_baseline_complete": False}, record=None)] if rows is None else rows
    fatal = production.FATAL_HOLDS
    failed = sum(bool(set(row["holds"]) & fatal) for row in rows)
    unbound = sum(row["record"] is None and not set(row["holds"]) & fatal for row in rows)
    document = {
        "schema": "bmasia.agent-production-export.v1",
        "source": source,
        "source_authentication": "operator_snapshot_set_collector",
        "exported_at": (exported or NOW).isoformat(),
        "source_observed_at": max((row["observed_at"] for row in rows if row["observed_at"]), default=None),
        "coverage": coverage or {"total": len(rows), "exported": len(rows) - failed - unbound, "complete": complete, "unbound": unbound, "failed": failed},
        "records": rows,
    }
    document["export_sha256"] = production.digest({key: value for key, value in document.items() if key not in {"exported_at", "export_sha256"}})
    return document


def make_correction(*, source="theo", event_id=None, record_id=RECORD, after="Director"):
    return {
        "schema": "bmasia.agent-correction.v1",
        "source": source,
        "event_id": event_id or str(uuid.uuid4()),
        "observed_at": (NOW - timedelta(minutes=1)).isoformat(),
        "company_id": COMPANY,
        "record": {"collection": "contact", "id": record_id},
        "expected_version": (NOW - timedelta(hours=1)).isoformat(),
        "changes": {"title": {"before": "Manager", "after": after}},
        "evidence": [{"kind": "agent_receipt", "reference": "receipt-1", "sha256": "b" * 64}],
        "reason": "Explicit correction request with independent validation pending",
    }


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)
        os.chmod(self.state, 0o700)
        self.ledger = production.Ledger(self.state)

    def tearDown(self):
        self.temp.cleanup()

    def test_uid_binding_and_operator_import_are_distinct(self):
        document = make_export("theo")
        with self.assertRaisesRegex(ValueError, "source_uid_mismatch"):
            self.ledger.submit(document, 1000, NOW)
        accepted = self.ledger.submit(document, production.OPERATOR_UID, NOW)
        self.assertTrue(accepted["accepted"])
        with self.ledger.connect() as db:
            stored = db.execute("SELECT peer_uid,auth FROM sources WHERE source='theo'").fetchone()
        self.assertEqual((stored["peer_uid"], stored["auth"]), (production.OPERATOR_UID, "operator_import"))

    def test_export_timestamp_replay_conflict_and_source_regression(self):
        first = make_export("theo")
        self.ledger.submit(first, 1008, NOW)
        replay = self.ledger.submit(first, 1008, NOW + timedelta(minutes=1))
        self.assertTrue(replay["accepted"])
        conflict = json.loads(json.dumps(first))
        conflict["records"][0]["facts"]["revision"] = 2
        conflict["export_sha256"] = production.digest({key: value for key, value in conflict.items() if key not in {"exported_at", "export_sha256"}})
        with self.assertRaisesRegex(ValueError, "same_time_export_conflict"):
            self.ledger.submit(conflict, 1008, NOW + timedelta(minutes=1))
        older_observed = make_export("theo", rows=[make_row(observed=NOW - timedelta(hours=1), facts={"state": "OPEN"})], exported=NOW + timedelta(minutes=2))
        with self.assertRaisesRegex(ValueError, "source_observation_regression"):
            self.ledger.submit(older_observed, 1008, NOW + timedelta(minutes=2))
        stale_transport = make_export("theo", exported=NOW - timedelta(hours=3))
        with self.assertRaisesRegex(ValueError, "export_outside_import_window"):
            production.validate_export(stale_transport, 1008, NOW)

    def test_same_max_observation_with_changed_older_content_is_allowed(self):
        first = make_export("theo")
        self.ledger.submit(first, 1008, NOW)
        changed = json.loads(json.dumps(first))
        changed["exported_at"] = (NOW + timedelta(minutes=1)).isoformat()
        changed["records"][0]["facts"]["revision"] = 9
        changed["export_sha256"] = production.digest({key: value for key, value in changed.items() if key not in {"exported_at", "export_sha256"}})
        accepted = self.ledger.submit(changed, 1008, NOW + timedelta(minutes=1))
        self.assertTrue(accepted["accepted"])

    def test_complete_empty_and_incomplete_failure_have_safe_replacement_semantics(self):
        bound = make_row(record={"collection": "contacts", "id": RECORD}, facts={"state": "OPEN"})
        self.ledger.submit(make_export("theo", rows=[bound], complete=True), 1008, NOW)
        failed = make_export("theo", rows=[make_row(key="failure:source", companies=[], record=None, observed=False, holds=["SOURCE_MISSING"])], exported=NOW + timedelta(minutes=1), complete=False)
        self.ledger.submit(failed, 1008, NOW + timedelta(minutes=1))
        with self.ledger.connect() as db:
            keys = {row[0] for row in db.execute("SELECT source_key FROM observations WHERE source='theo'")}
        self.assertEqual(keys, {"work:one", "failure:source"})
        empty = make_export("theo", rows=[], exported=NOW + timedelta(minutes=2), complete=True)
        self.ledger.submit(empty, 1008, NOW + timedelta(minutes=2))
        with self.ledger.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations WHERE source='theo'").fetchone()[0], 0)

    def test_row_future_envelope_max_and_coverage_are_verified(self):
        future = make_export("theo", rows=[make_row(observed=NOW + timedelta(hours=1), facts={"state": "OPEN"})])
        with self.assertRaisesRegex(ValueError, "future"):
            production.validate_export(future, 1008, NOW)
        mismatch = make_export("theo")
        mismatch["source_observed_at"] = (NOW - timedelta(hours=1)).isoformat()
        mismatch["export_sha256"] = production.digest({key: value for key, value in mismatch.items() if key not in {"exported_at", "export_sha256"}})
        with self.assertRaisesRegex(ValueError, "source_observed_at_not_row_max"):
            production.validate_export(mismatch, 1008, NOW)
        wrong_partition = make_export("theo")
        wrong_partition["coverage"] = {"total": 1, "exported": 1, "complete": True, "unbound": 0, "failed": 0}
        wrong_partition["export_sha256"] = production.digest({key: value for key, value in wrong_partition.items() if key not in {"exported_at", "export_sha256"}})
        with self.assertRaisesRegex(ValueError, "coverage_not_row_partition"):
            production.validate_export(wrong_partition, 1008, NOW)

    def test_bound_record_requires_company_and_wrong_company_shape_fails_closed(self):
        missing = make_export("theo", rows=[make_row(companies=[], record={"collection": "contacts", "id": RECORD}, facts={"state": "OPEN"})])
        with self.assertRaisesRegex(ValueError, "bound_record_requires_company"):
            production.validate_export(missing, 1008, NOW)
        invalid = make_export("theo", rows=[make_row(companies=["not-a-uuid"], record={"collection": "contacts", "id": RECORD}, facts={"state": "OPEN"})])
        with self.assertRaises(ValueError):
            production.validate_export(invalid, 1008, NOW)

    def test_fact_and_followup_privacy_allowlists(self):
        prose = make_export("theo", rows=[make_row(facts={"notes": "full email body private@example.test"})])
        with self.assertRaisesRegex(ValueError, "invalid_facts"):
            production.validate_export(prose, 1008, NOW)
        followup = make_export("theo", rows=[make_row(facts={"state": "OPEN"}, follow_ups=[{"case_id": "case-1", "state": "OPEN", "due_at": NOW.isoformat(), "owner": "Production"}])])
        with self.assertRaisesRegex(ValueError, "source_followups_not_supported"):
            production.validate_export(followup, 1008, NOW)
        cara_followup = make_export("cara", rows=[make_row(facts={"collection_state": "COLLECTED"}, follow_ups=[{"case_id": "case-1", "state": "WAITING", "due_at": (NOW - timedelta(hours=1)).isoformat(), "owner": "Keith"}])])
        production.validate_export(cara_followup, production.OPERATOR_UID, NOW)

    def test_decode_size_duplicate_and_nonfinite_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "size_limit"):
            production.decode(b" " * (production.MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "duplicate_key"):
            production.decode(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            production.decode(b'{"a":NaN}')

    def test_status_separates_transport_from_evidence_freshness(self):
        old = make_export("theo", rows=[make_row(observed=NOW - timedelta(days=2), facts={"state": "OPEN"}, holds=["SOURCE_STALE"])])
        self.ledger.submit(old, 1008, NOW)
        status = self.ledger.status("theo", NOW + timedelta(minutes=1))["sources"]["theo"]
        self.assertEqual(status["transport"], "fresh")
        self.assertEqual(status["evidence_freshness"], "stale")

    def test_correction_replay_content_conflict_and_concurrent_record_hold(self):
        first = make_correction()
        accepted = self.ledger.submit(first, 1008, NOW)
        self.assertEqual(accepted["state"], "PENDING")
        replay = self.ledger.submit(first, 1008, NOW)
        self.assertTrue(replay["replay"])
        changed = json.loads(json.dumps(first))
        changed["changes"]["title"]["after"] = "VP"
        with self.assertRaisesRegex(ValueError, "event_id_content_conflict"):
            self.ledger.submit(changed, 1008, NOW)
        second = make_correction(event_id=str(uuid.uuid4()))
        held = self.ledger.submit(second, 1008, NOW)
        self.assertEqual(held["state"], "HOLD")
        with self.ledger.connect() as db:
            rows = db.execute("SELECT state,reason,peer_uid FROM corrections ORDER BY event_id").fetchall()
        self.assertTrue(all(row["state"] == "HOLD" and row["reason"] == "concurrent_source_conflict" and row["peer_uid"] == 1008 for row in rows))
        with self.assertRaisesRegex(ValueError, "source_uid_mismatch"):
            self.ledger.submit(make_correction(source="lyra"), 1008, NOW)


if __name__ == "__main__":
    unittest.main()
