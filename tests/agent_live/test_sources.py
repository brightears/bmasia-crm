import json
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import agent_crm_source_observations as subject


NOW = datetime(2026, 9, 14, 6, tzinfo=UTC)
COMPANY = "5f55b8b4-d76a-43c1-ba1c-14d14ee6f6c5"
OPPORTUNITY = "354d0392-e578-49e7-b239-1cf8113c42cf"
CONTACT = "db5399fa-a2e0-4da2-8a9f-cb25b6356bfa"


def scope(source, path, collection="opportunities", record_id=OPPORTUNITY, expires=NOW + timedelta(hours=1)):
    return {"schema": subject.SCOPE_SCHEMA, "scope_id": str(uuid.uuid4()), "expires_at": expires.isoformat(), "accounts": [{"source": source, "company_id": COMPANY, "record": {"collection": collection, "id": record_id}, "source_path": str(path)}]}


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sales = self.root / "reports"
        self.sales.mkdir()
        self.sales_file = self.sales / "context.json"
        self.write_sales()
        self.cara = self.root / "contexts.sqlite3"
        self.write_cara()

    def tearDown(self):
        self.temp.cleanup()

    def write_sales(self, created_at=None, opportunity_id=OPPORTUNITY):
        self.sales_file.write_text(json.dumps({"created_at": (created_at or (NOW - timedelta(hours=1))).isoformat(), "context_hash": "a" * 64, "crm_context": {"complete": "TRUE", "records": [{"record_type": "company", "record_id": COMPANY}, {"record_type": "opportunity", "record_id": opportunity_id, "company_id": COMPANY, "stage": "Quotation Sent", "last_contact_date": None, "follow_up_date": "2026-09-20"}]}, "injected": "secret@example.test body must never appear"}))

    def write_cara(self):
        db = sqlite3.connect(self.cara)
        db.executescript("CREATE TABLE accounts (account_id TEXT, last_collected_at TEXT, collection_state TEXT, blockers_json TEXT); CREATE TABLE packets (account_id TEXT, packet_sha256 TEXT, collected_at TEXT, packet_json TEXT, assessment_json TEXT); CREATE TABLE settings (key TEXT, value TEXT);")
        db.execute("INSERT INTO accounts VALUES (?,?,?,?)", (COMPANY, (NOW - timedelta(hours=1)).isoformat(), "CURRENT", '["injection<not echoed>"]'))
        packet = {"crm": {"primary_contact_id": CONTACT, "holds": ["secret"], "evidence_sha256": "b" * 64}, "observed_at": (NOW - timedelta(hours=1)).isoformat(), "blockers": ["injection<not echoed>"], "uncovered_bmasia_senders": ["sender@example.test"], "messages": "RAW MAIL NEVER SELECTED"}
        db.execute("INSERT INTO packets VALUES (?,?,?,?,?)", (COMPANY, "b" * 64, (NOW - timedelta(hours=1)).isoformat(), json.dumps(packet), json.dumps({"decision": "BLOCKED", "prose": "malicious prose"})))
        db.execute("INSERT INTO settings VALUES (?,?)", ("historical-case:case-1", json.dumps({"account_id": COMPANY, "case_id": "case-1", "state": "OPEN", "next_follow_up_at": "2026-09-15T07:00:00+00:00", "owner": "Production", "prose": "malicious prose"})))
        db.commit(); db.close()

    def test_sales_exact_match_and_redaction(self):
        result = subject.extract_scope(scope("bmasia_sales", self.sales_file), now=NOW, sales_root=self.sales, cara_db=self.cara)
        observed = result["observations"][0]
        self.assertEqual(observed["facts"]["stage"], "Quotation Sent")
        self.assertEqual(observed["source_authentication"], subject.AUTHENTICATION)
        self.assertNotIn("secret@example.test", json.dumps(result))
        self.assertIsNone(observed["facts"]["last_contact_date"])

    def test_sales_id_mismatch_and_stale_future_are_failures(self):
        result = subject.extract_scope(scope("bmasia_sales", self.sales_file, record_id=str(uuid.uuid4())), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_ID_MISMATCH")
        self.write_sales(created_at=NOW - timedelta(days=8))
        self.assertEqual(subject.extract_scope(scope("bmasia_sales", self.sales_file), now=NOW, sales_root=self.sales, cara_db=self.cara)["observations"][0]["error_code"], "SOURCE_STALE")
        self.write_sales(created_at=NOW + timedelta(minutes=1))
        self.assertEqual(subject.extract_scope(scope("bmasia_sales", self.sales_file), now=NOW, sales_root=self.sales, cara_db=self.cara)["observations"][0]["error_code"], "SOURCE_FUTURE")

    def test_scope_rejects_expiry_and_duplicate_entries_before_reads(self):
        with self.assertRaises(subject.ScopeError):
            subject.extract_scope(scope("bmasia_sales", self.sales_file, expires=NOW), now=NOW, sales_root=self.sales, cara_db=self.cara)
        duplicate = scope("bmasia_sales", self.sales_file)
        duplicate["accounts"].append(dict(duplicate["accounts"][0]))
        with self.assertRaises(subject.ScopeError):
            subject.extract_scope(duplicate, now=NOW, sales_root=self.sales, cara_db=self.cara)
        other_path = self.sales / "other.json"
        other_path.write_text(self.sales_file.read_text())
        duplicate = scope("bmasia_sales", self.sales_file)
        duplicate["accounts"].append({**duplicate["accounts"][0], "source_path": str(other_path)})
        with self.assertRaises(subject.ScopeError):
            subject.validate_scope(duplicate, now=NOW)

    def test_missing_source_is_explicit_failure(self):
        result = subject.extract_scope(scope("bmasia_sales", self.sales / "missing.json"), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_MISSING")

    def test_cara_is_readonly_and_does_not_echo_packet_content(self):
        before = self.cara.read_bytes()
        result = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)
        after = self.cara.read_bytes()
        observation = result["observations"][0]
        self.assertEqual(before, after)
        self.assertEqual(observation["facts"]["primary_contact_id"], CONTACT)
        serialized = json.dumps(result)
        self.assertNotIn("RAW MAIL", serialized)
        self.assertNotIn("malicious prose", serialized)
        self.assertNotIn("injection<", serialized)
        self.assertIn("SOURCE_RUNTIME_HEALTH_UNVERIFIED", observation["holds"])

    def test_cara_empty_arrays_are_not_holds_and_future_followup_is_not_due(self):
        db = sqlite3.connect(self.cara)
        packet = json.loads(db.execute("SELECT packet_json FROM packets").fetchone()[0])
        packet["crm"]["holds"] = []
        packet["blockers"] = []
        packet["uncovered_bmasia_senders"] = []
        db.execute("UPDATE accounts SET blockers_json='[]'")
        db.execute("UPDATE packets SET packet_json=?, assessment_json=?", (json.dumps(packet), json.dumps({"decision": "needs_attention", "prose": "protected prose"})))
        db.commit(); db.close()
        result = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)
        observation = result["observations"][0]
        self.assertNotIn("CRM_HOLD", observation["holds"])
        self.assertNotIn("UNRESOLVED_BLOCKER", observation["holds"])
        self.assertNotIn("FOLLOW_UP_DUE", observation["holds"])
        self.assertEqual(observation["facts"]["assessment_decision"], "NEEDS_ATTENTION")
        self.assertEqual(observation["follow_ups"][0]["owner"], "Production")
        self.assertNotIn("protected prose", json.dumps(result))

    def test_cara_due_requires_aware_past_timestamp_and_unresolved_state(self):
        db = sqlite3.connect(self.cara)
        db.execute("DELETE FROM settings")
        cases = [
            ("historical-case:past", {"account_id": COMPANY, "case_id": "past", "state": "WAITING", "next_follow_up_at": "2026-09-11T06:00:00+00:00", "owner": "keith"}),
            ("historical-case:resolved", {"account_id": COMPANY, "case_id": "resolved", "state": "CLOSED", "next_follow_up_at": "2026-09-11T06:00:00+00:00", "owner": "NORbert"}),
            ("historical-case:date-only", {"account_id": COMPANY, "case_id": "date-only", "state": "OPEN", "next_follow_up_at": "2026-09-11", "owner": "Scott"}),
        ]
        db.executemany("INSERT INTO settings VALUES (?,?)", [(key, json.dumps(value)) for key, value in cases])
        db.execute("UPDATE accounts SET blockers_json='[]'")
        packet = json.loads(db.execute("SELECT packet_json FROM packets").fetchone()[0])
        packet["crm"]["holds"] = []
        packet["blockers"] = []
        packet["uncovered_bmasia_senders"] = []
        db.execute("UPDATE packets SET packet_json=?, assessment_json=?", (json.dumps(packet), json.dumps({"decision": "clear"})))
        db.commit(); db.close()
        observation = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)["observations"][0]
        self.assertIn("FOLLOW_UP_DUE", observation["holds"])
        by_id = {item["case_id"]: item for item in observation["follow_ups"]}
        self.assertEqual(by_id["past"]["owner"], "Keith")
        self.assertEqual(by_id["resolved"]["owner"], "Norbert")
        self.assertIsNone(by_id["date-only"]["due_at"])
        self.assertIn("NEEDS_ATTENTION", observation["holds"])

    def test_invalid_cara_timestamp_fails_only_its_row(self):
        company, contact = str(uuid.uuid4()), str(uuid.uuid4())
        db = sqlite3.connect(self.cara)
        packet = {"crm": {"primary_contact_id": contact, "holds": []}, "observed_at": "invalid", "blockers": [], "uncovered_bmasia_senders": []}
        db.execute("INSERT INTO accounts VALUES (?,?,?,?)", (company, "invalid", "CURRENT", "[]"))
        db.execute("INSERT INTO packets VALUES (?,?,?,?,?)", (company, "c" * 64, "invalid", json.dumps(packet), json.dumps({"decision": "clear"})))
        db.commit(); db.close()
        pilot = scope("cara", self.cara, collection="contacts", record_id=CONTACT)
        pilot["accounts"].append({"source": "cara", "company_id": company, "record": {"collection": "contacts", "id": contact}, "source_path": str(self.cara)})
        result = subject.extract_scope(pilot, now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertNotEqual(result["observations"][0].get("status"), "FAILED")
        self.assertEqual(result["observations"][1]["error_code"], "SOURCE_INVALID")

    def test_scope_cli_rejects_duplicate_nonfinite_and_oversize_json(self):
        scope_file = self.root / "scope.json"
        payloads = [
            '{"schema":"x","schema":"y"}',
            '{"schema":NaN}',
            ' ' * (subject.MAX_SCOPE_BYTES + 1),
        ]
        for payload in payloads:
            with self.subTest(payload=payload[:20]):
                scope_file.write_text(payload)
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(subject.main(["--scope", str(scope_file)]), 2)
                self.assertEqual(json.loads(output.getvalue())["error_code"], "SCOPE_REJECTED")

    def test_sales_rejects_duplicate_json_records_and_preserves_absence(self):
        duplicate = self.sales / "duplicate.json"
        duplicate.write_text('{"created_at":"2026-09-14T05:00:00+00:00","context_hash":"' + "a" * 64 + '","context_hash":"' + "a" * 64 + '","crm_context":{"complete":"TRUE","records":[]}}')
        result = subject.extract_scope(scope("bmasia_sales", duplicate), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_INVALID")
        self.write_sales()
        payload = json.loads(self.sales_file.read_text())
        del payload["crm_context"]["records"][1]["last_contact_date"]
        self.sales_file.write_text(json.dumps(payload))
        result = subject.extract_scope(scope("bmasia_sales", self.sales_file), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertNotIn("last_contact_date", result["observations"][0]["facts"])
        payload["crm_context"]["records"].append(dict(payload["crm_context"]["records"][1]))
        self.sales_file.write_text(json.dumps(payload))
        result = subject.extract_scope(scope("bmasia_sales", self.sales_file), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_DUPLICATE")

    def test_cara_duplicate_packets_and_case_bounds_normalize_without_prose(self):
        db = sqlite3.connect(self.cara)
        packet = json.loads(db.execute("SELECT packet_json FROM packets").fetchone()[0])
        db.execute("INSERT INTO packets VALUES (?,?,?,?,?)", (COMPANY, "c" * 64, (NOW - timedelta(hours=1)).isoformat(), json.dumps(packet), json.dumps({"decision": "WAITING"})))
        db.commit(); db.close()
        result = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_DUPLICATE")
        db = sqlite3.connect(self.cara)
        db.execute("DELETE FROM packets WHERE packet_sha256=?", ("c" * 64,))
        for index in range(2, 28):
            db.execute("INSERT INTO settings VALUES (?,?)", (f"historical-case:{index}", json.dumps({"account_id": COMPANY, "case_id": f"case-{index}", "state": "untrusted prose", "next_follow_up_at": "bad-date", "owner": "unknown owner"})))
        db.commit(); db.close()
        result = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(result["observations"][0]["error_code"], "SOURCE_RESULT_LIMIT")
        db = sqlite3.connect(self.cara)
        db.execute("DELETE FROM settings WHERE key LIKE 'historical-case:%' AND key != 'historical-case:2'")
        db.commit(); db.close()
        result = subject.extract_scope(scope("cara", self.cara, collection="contacts", record_id=CONTACT), now=NOW, sales_root=self.sales, cara_db=self.cara)
        observation = result["observations"][0]
        self.assertIn("NEEDS_ATTENTION", observation["holds"])
        self.assertEqual(observation["follow_ups"][0], {"case_id": "case-2", "state": "UNKNOWN", "due_at": None, "owner": "UNKNOWN"})

    def test_reviewer_fixture_three_cara_holds_and_one_stale_sales_failure(self):
        accounts = []
        db = sqlite3.connect(self.cara)
        for decision in ("BLOCKED", "NEEDS_ATTENTION"):
            company, contact = str(uuid.uuid4()), str(uuid.uuid4())
            packet = {"crm": {"primary_contact_id": contact, "holds": []}, "observed_at": (NOW - timedelta(hours=1)).isoformat(), "blockers": [], "uncovered_bmasia_senders": []}
            db.execute("INSERT INTO accounts VALUES (?,?,?,?)", (company, (NOW - timedelta(hours=1)).isoformat(), "CURRENT", "[]"))
            db.execute("INSERT INTO packets VALUES (?,?,?,?,?)", (company, "d" * 63 + str(len(accounts)), (NOW - timedelta(hours=1)).isoformat(), json.dumps(packet), json.dumps({"decision": decision})))
            accounts.append({"source": "cara", "company_id": company, "record": {"collection": "contacts", "id": contact}, "source_path": str(self.cara)})
        db.commit(); db.close()
        self.write_sales(created_at=NOW - timedelta(days=8))
        accounts.insert(0, {"source": "cara", "company_id": COMPANY, "record": {"collection": "contacts", "id": CONTACT}, "source_path": str(self.cara)})
        accounts.append({"source": "bmasia_sales", "company_id": COMPANY, "record": {"collection": "opportunities", "id": OPPORTUNITY}, "source_path": str(self.sales_file)})
        pilot_scope = {"schema": subject.SCOPE_SCHEMA, "scope_id": str(uuid.uuid4()), "expires_at": (NOW + timedelta(hours=1)).isoformat(), "accounts": accounts}
        result = subject.extract_scope(pilot_scope, now=NOW, sales_root=self.sales, cara_db=self.cara)
        self.assertEqual(len(result["observations"]), 4)
        held = [item for item in result["observations"] if item.get("source") == "cara"]
        self.assertEqual(len(held), 3)
        self.assertTrue(all("SOURCE_RUNTIME_HEALTH_UNVERIFIED" in item["holds"] for item in held))
        self.assertEqual(result["observations"][-1]["error_code"], "SOURCE_STALE")

    def test_no_credential_imports(self):
        source = (ROOT / "tools" / "agent_crm_source_observations.py").read_text()
        for forbidden in ("requests", "httpx", "keyring", "oauth", "subprocess"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
