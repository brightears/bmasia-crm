import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import agent_crm_pilot_review as subject

NOW = datetime(2026, 9, 14, 6, tzinfo=timezone.utc)
SCOPE = str(uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
COMPANY = str(uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
RECORD = str(uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
OBSERVATION = str(uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"))


def source(**changes):
    value = {"source": "cara", "company_id": COMPANY, "record": {"collection": "contacts", "id": RECORD}, "source_observed_at": (NOW - timedelta(hours=1)).isoformat(), "source_version_hash": "a" * 64, "observation_id": OBSERVATION, "source_authentication": subject.AUTHENTICATION, "facts": {"title": "GM", "department": None}, "holds": ["WAITING"], "follow_ups": [{"case_id": "case-1", "state": "WAITING", "due_at": (NOW - timedelta(hours=2)).isoformat(), "owner": "production"}], "source_payload_sha256": "b" * 64}
    value.update(changes)
    return value


def snapshot(**changes):
    value = {"company": {"id": COMPANY, "name": "Test Hotel", "updated_at": (NOW - timedelta(minutes=2)).isoformat()}, "collection": "contacts", "id": RECORD, "observed_at": (NOW - timedelta(minutes=1)).isoformat(), "updated_at": (NOW - timedelta(minutes=2)).isoformat(), "fields": {"company": COMPANY, "title": "GM", "department": None, "last_contacted": None}, "status": "ok"}
    value.update(changes)
    return value


def documents(rows=None, snapshots=None):
    return ({"schema": subject.OBSERVATION_SCHEMA, "scope_id": SCOPE, "observed_at": NOW.isoformat(), "observations": rows if rows is not None else [source()]}, {"schema": subject.SNAPSHOT_SCHEMA, "scope_id": SCOPE, "observed_at": NOW.isoformat(), "records": snapshots if snapshots is not None else [snapshot()]})


class ReviewTests(unittest.TestCase):
    def test_compares_allowed_fields_and_never_proposes_edits(self):
        observations, snapshots = documents()
        result = subject.review(observations, snapshots, now=NOW)
        row = result["results"][0]
        self.assertEqual(row["facts"]["title"]["comparison"], "agreement")
        self.assertEqual(row["facts"]["last_contacted"]["source"], "__absent__")
        self.assertEqual(row["facts"]["last_contacted"]["current"], None)
        self.assertEqual(row["proposed_edits"], [])
        self.assertEqual(row["holds"], ["WAITING"])
        self.assertEqual(row["follow_ups"][0]["due_at"], (NOW - timedelta(hours=2)).isoformat())
        self.assertTrue(result["read_only"])
        self.assertEqual(result["crm_writes"], 0)
        self.assertFalse(result["automatic_updates_enabled"])

    def test_identity_and_scope_mismatches_fail_closed(self):
        observations, snapshots = documents(snapshots=[snapshot(id=str(uuid.uuid4()))])
        result = subject.review(observations, snapshots, now=NOW)
        self.assertEqual(result["results"][0]["status"], "missing_current_snapshot")
        bad_observations, good_snapshots = documents()
        bad_observations["scope_id"] = str(uuid.uuid4())
        with self.assertRaisesRegex(subject.ReviewError, "scope_id_mismatch"):
            subject.review(bad_observations, good_snapshots, now=NOW)

    def test_duplicate_is_idempotent_but_changed_same_id_conflicts(self):
        duplicate = source()
        observations, snapshots = documents(rows=[source(), duplicate])
        self.assertEqual(len(subject.review(observations, snapshots, now=NOW)["results"]), 1)
        conflict = source(facts={"title": "Changed"})
        observations, snapshots = documents(rows=[source(), conflict])
        with self.assertRaisesRegex(subject.ReviewError, "observation_id_conflict"):
            subject.review(observations, snapshots, now=NOW)

    def test_stale_retained_future_and_malformed_bindings_fail_closed(self):
        observations, snapshots = documents(rows=[source(source_observed_at=(NOW - timedelta(hours=25)).isoformat())])
        result = subject.review(observations, snapshots, now=NOW)
        self.assertEqual(result["coverage"]["cara"], "operator_import_stale")
        self.assertIn("SOURCE_STALE", result["results"][0]["holds"])
        for observed, code in ((NOW + timedelta(seconds=1), "source_future"),):
            observations, snapshots = documents(rows=[source(source_observed_at=observed.isoformat())])
            with self.assertRaisesRegex(subject.ReviewError, code):
                subject.review(observations, snapshots, now=NOW)
        observations, snapshots = documents(rows=[source(company_id="not-a-uuid")])
        with self.assertRaisesRegex(subject.ReviewError, "company_id_invalid"):
            subject.review(observations, snapshots, now=NOW)

    def test_missing_source_is_unknown_not_healthy(self):
        observations, snapshots = documents(rows=[])
        result = subject.review(observations, snapshots, now=NOW)
        self.assertEqual(result["coverage"]["cara"], "no_live_observation")
        self.assertEqual(result["coverage"]["theo"], "no_live_observation")
        observations, snapshots = documents(rows=[{"source": "cara", "company_id": COMPANY, "record": {"collection": "contacts", "id": RECORD}, "status": "FAILED", "error_code": "SOURCE_MISSING"}])
        result = subject.review(observations, snapshots, now=NOW)
        self.assertEqual(result["coverage"]["cara"], "no_live_observation")
        self.assertEqual(result["results"][0]["status"], "source_failed")

    def test_held_cara_and_protected_facts_cannot_emit_edits(self):
        observations, snapshots = documents(rows=[source(facts={"title": "GM", "primary_contact_id": "protected"}, holds=["WAITING", "NEEDS_ATTENTION"])])
        result = subject.review(observations, snapshots, now=NOW)
        row = result["results"][0]
        self.assertNotIn("primary_contact_id", row["facts"])
        self.assertEqual(row["holds"], ["NEEDS_ATTENTION", "WAITING"])
        self.assertEqual(row["proposed_edits"], [])

    def test_fk_mismatch_and_stale_snapshot_hold_without_comparison(self):
        observations, snapshots = documents(snapshots=[snapshot(fields={"company": str(uuid.uuid4()), "title": "GM"})])
        row = subject.review(observations, snapshots, now=NOW)["results"][0]
        self.assertEqual(row["status"], "identity_mismatch")
        self.assertIn("IDENTITY_MISMATCH", row["holds"])
        observations, snapshots = documents(snapshots=[snapshot(observed_at=(NOW - timedelta(hours=25)).isoformat())])
        row = subject.review(observations, snapshots, now=NOW)["results"][0]
        self.assertEqual(row["status"], "stale_current_snapshot")
        self.assertIn("SNAPSHOT_STALE", row["holds"])

    def test_degraded_snapshot_and_safe_root_flags_are_not_batch_failures(self):
        observations, snapshots = documents(snapshots=[snapshot(company={"id": COMPANY}, updated_at=None, fields={}, status="missing")])
        snapshots["crm_writes"] = 0
        snapshots["customer_outbound"] = False
        row = subject.review(observations, snapshots, now=NOW)["results"][0]
        self.assertEqual(row["status"], "current_snapshot_missing")
        snapshots["crm_writes"] = 1
        with self.assertRaisesRegex(subject.ReviewError, "snapshot_safety_flags_invalid"):
            subject.review(observations, snapshots, now=NOW)

    def test_four_record_integration_fixture_keeps_source_states_separate(self):
        identifiers = [("cara", "contacts"), ("theo", "contacts"), ("lyra", "opportunities"), ("bmasia_sales", "opportunities")]
        rows, snapshots = [], []
        for index, (owner, collection) in enumerate(identifiers):
            company, record = str(uuid.uuid4()), str(uuid.uuid4())
            facts = {"title": "GM"} if collection == "contacts" else {"stage": "Discovery"}
            fields = {"company": company, **facts}
            rows.append(source(source=owner, company_id=company, record={"collection": collection, "id": record}, observation_id=str(uuid.uuid4()), facts=facts, holds=[] if index != 1 else ["WAITING"]))
            snapshots.append(snapshot(company={"id": company, "name": "Pilot", "updated_at": (NOW - timedelta(minutes=2)).isoformat()}, collection=collection, id=record, fields=fields))
        observations, _ = documents(rows=rows, snapshots=snapshots)
        result = subject.review(observations, {"schema": subject.SNAPSHOT_SCHEMA, "scope_id": SCOPE, "observed_at": NOW.isoformat(), "records": snapshots}, now=NOW)
        self.assertEqual(len(result["results"]), 4)
        self.assertEqual(result["coverage"]["cara"], "operator_import_observed")
        self.assertEqual(result["coverage"]["theo"], "operator_import_held")
        self.assertEqual(result["coverage"]["riff"], "no_live_observation")

    def test_actual_extractor_document_shape_accepts_imported_at_without_observed_at(self):
        observations, snapshots = documents()
        observations.pop("observed_at")
        observations["imported_at"] = NOW.isoformat()
        result = subject.review(observations, snapshots, now=NOW)
        self.assertEqual(result["results"][0]["status"], "compared")


if __name__ == "__main__":
    unittest.main()
