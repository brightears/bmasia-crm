import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import agent_crm_local_export as subject
import agent_crm_production as production


NOW = datetime(2026, 9, 14, 6, tzinfo=UTC)
COMPANY_1 = "5f55b8b4-d76a-43c1-ba1c-14d14ee6f6c5"
COMPANY_2 = "69e91389-fb8e-4af8-bd52-ec79535b7e83"
COMPANY_3 = "563e9c0a-1cc6-426a-bcea-070cd0d54ef8"
CONTACT_1 = "db5399fa-a2e0-4da2-8a9f-cb25b6356bfa"
CONTACT_2 = "626f1170-826c-4f7c-b2b9-9752b6c453f4"
OPPORTUNITY = "354d0392-e578-49e7-b239-1cf8113c42cf"


class LocalExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cara = self.root / "contexts.sqlite3"
        self.sales = self.root / "reports"
        self.sales.mkdir()
        self._write_cara()

    def tearDown(self):
        self.temp.cleanup()

    def _write_cara(self):
        db = sqlite3.connect(self.cara)
        db.executescript(
            "CREATE TABLE accounts (account_id TEXT PRIMARY KEY,last_collected_at TEXT,collection_state TEXT NOT NULL,blockers_json TEXT NOT NULL DEFAULT '[]');"
            "CREATE TABLE packets (account_id TEXT PRIMARY KEY,packet_sha256 TEXT NOT NULL,collected_at TEXT NOT NULL,packet_json TEXT,assessment_json TEXT);"
            "CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);"
        )
        rows = [
            (COMPANY_1, CONTACT_1, "COLLECTED", "needs_attention", [], [], [], NOW - timedelta(hours=1)),
            (COMPANY_2, CONTACT_2, "BLOCKED", "clear", [], ["private CRM prose"], [], NOW - timedelta(hours=2)),
            (COMPANY_3, None, "FAILED", None, [], [], [], NOW - timedelta(hours=3)),
        ]
        for index, (company, contact, state, decision, account_holds, crm_holds, packet_holds, observed) in enumerate(rows):
            db.execute("INSERT INTO accounts VALUES (?,?,?,?)", (company, observed.isoformat(), state, json.dumps(account_holds)))
            if contact:
                packet = {
                    "crm": {"primary_contact_id": contact, "holds": crm_holds},
                    "observed_at": observed.isoformat(),
                    "blockers": packet_holds,
                    "uncovered_bmasia_senders": [],
                    "messages": "RAW MAIL secret@example.test",
                }
                db.execute("INSERT INTO packets VALUES (?,?,?,?,?)", (company, str(index + 1) * 64, observed.isoformat(), json.dumps(packet), json.dumps({"decision": decision, "prose": "protected prose"})))
        cases = [
            ("past", COMPANY_1, "WAITING", NOW - timedelta(days=1), "keith"),
            ("future", COMPANY_1, "OPEN", NOW + timedelta(days=1), "Production"),
            ("date-only", COMPANY_1, "OPEN", "2026-09-11", "NORbert"),
        ]
        for case_id, company, state, due, owner in cases:
            value = {"account_id": company, "case_id": case_id, "state": state, "next_follow_up_at": due.isoformat() if isinstance(due, datetime) else due, "owner": owner, "notes": "never export this prose"}
            db.execute("INSERT INTO settings VALUES (?,?)", ("historical-case:" + case_id, json.dumps(value)))
        db.execute("INSERT INTO settings VALUES (?,?)", ("last_collection", json.dumps({"crm_accounts": 3, "crm_book_complete": True, "mail": "not exported"})))
        db.commit()
        db.close()

    def _write_sales(self, name, *, created, records, complete="TRUE", extra=None):
        document = {
            "created_at": created.isoformat(),
            "context_hash": (name[0].lower() if name[0].lower() in "abcdef" else "a") * 64,
            "crm_context": {"complete": complete, "records": records},
            "related_threads": [{"body": "FULL MAIL private@example.test"}],
        }
        if extra:
            document.update(extra)
        path = self.sales / name
        path.write_text(json.dumps(document))
        return path

    def test_cara_full_inventory_semantics_redaction_and_read_only(self):
        before = self.cara.read_bytes()
        result = subject.export_cara(now=NOW, cara_db=self.cara)
        self.assertEqual(self.cara.read_bytes(), before)
        self.assertEqual(result["coverage"], {"total": 3, "exported": 2, "complete": True, "unbound": 0, "failed": 1})
        by_company = {row["company_ids"][0]: row for row in result["records"]}
        first = by_company[COMPANY_1]
        self.assertEqual(first["record"], {"collection": "contacts", "id": CONTACT_1})
        self.assertEqual(first["facts"]["assessment_decision"], "NEEDS_ATTENTION")
        self.assertEqual(first["facts"]["account_blocker_count"], 0)
        self.assertNotIn("CRM_HOLD", first["holds"])
        self.assertIn("FOLLOW_UP_DUE", first["holds"])
        follow = {row["case_id"]: row for row in first["follow_ups"]}
        self.assertEqual(follow["past"]["owner"], "Keith")
        self.assertEqual(follow["date-only"]["owner"], "Norbert")
        self.assertIsNone(follow["date-only"]["due_at"])
        self.assertEqual(follow["future"]["due_at"], (NOW + timedelta(days=1)).isoformat())
        self.assertNotIn("FOLLOW_UP_DUE", by_company[COMPANY_2]["holds"])
        self.assertIn("CRM_HOLD", by_company[COMPANY_2]["holds"])
        serialized = json.dumps(result)
        for forbidden in ("RAW MAIL", "protected prose", "private CRM prose", "secret@example", str(self.cara)):
            self.assertNotIn(forbidden, serialized)

    def test_cara_invalid_row_and_case_are_per_row_failures(self):
        db = sqlite3.connect(self.cara)
        db.execute("UPDATE packets SET packet_json='not-json' WHERE account_id=?", (COMPANY_1,))
        db.execute("INSERT INTO settings VALUES (?,?)", ("historical-case:bad", "not-json"))
        db.commit()
        db.close()
        result = subject.export_cara(now=NOW, cara_db=self.cara)
        self.assertEqual(len(result["records"]), 4)
        account = next(row for row in result["records"] if row["source_key"] == "account:" + COMPANY_1)
        self.assertIn("SOURCE_EVIDENCE_MISSING", account["holds"])
        self.assertIn("SOURCE_INVALID", account["holds"])
        failure = next(row for row in result["records"] if row["source_key"].startswith("failure:"))
        self.assertEqual(failure["holds"], ["SOURCE_INVALID"])
        self.assertEqual(result["coverage"]["failed"], 3)

    def test_cara_missing_source_and_invalid_timestamp_do_not_abort(self):
        missing = subject.export_cara(now=NOW, cara_db=self.root / "absent.sqlite3")
        self.assertEqual(missing["coverage"], {"total": 1, "exported": 0, "complete": False, "unbound": 0, "failed": 1})
        self.assertEqual(missing["records"][0]["holds"], ["SOURCE_MISSING"])
        db = sqlite3.connect(self.cara)
        db.execute("UPDATE packets SET packet_json=json_set(packet_json,'$.observed_at','invalid') WHERE account_id=?", (COMPANY_1,))
        db.commit()
        db.close()
        result = subject.export_cara(now=NOW, cara_db=self.cara)
        bad = next(row for row in result["records"] if row["source_key"] == "account:" + COMPANY_1)
        good = next(row for row in result["records"] if row["source_key"] == "account:" + COMPANY_2)
        self.assertIn("SOURCE_INVALID", bad["holds"])
        self.assertNotIn("SOURCE_INVALID", good["holds"])

    def test_sales_latest_is_chosen_by_data_timestamp_and_is_redacted(self):
        company = {"record_type": "company", "record_id": COMPANY_2, "name": "Secret Hotel"}
        old = {"record_type": "opportunity", "record_id": OPPORTUNITY, "company_id": COMPANY_2, "stage": "Old", "is_active": True, "notes": "private notes"}
        new = {"record_type": "opportunity", "record_id": OPPORTUNITY, "company_id": COMPANY_2, "stage": "New", "is_active": True, "follow_up_date": "2026-09-20", "notes": "private notes"}
        # Names deliberately imply the opposite order.
        self._write_sales("heartbeat-review-z-oldname.json", created=NOW - timedelta(hours=1), records=[company, new])
        self._write_sales("heartbeat-review-a-newname.json", created=NOW - timedelta(hours=2), records=[company, old])
        result = subject.export_bmasia_sales(now=NOW, sales_root=self.sales)
        self.assertEqual(result["coverage"], {"total": 1, "exported": 1, "complete": False, "unbound": 0, "failed": 0})
        row = result["records"][0]
        self.assertEqual(row["facts"], {"stage": "New", "follow_up_date": "2026-09-20", "is_active": True})
        self.assertEqual(row["company_ids"], [COMPANY_2])
        self.assertEqual(row["record"], {"collection": "opportunities", "id": OPPORTUNITY})
        serialized = json.dumps(result)
        for forbidden in ("Secret Hotel", "private notes", "FULL MAIL", "private@example", str(self.sales)):
            self.assertNotIn(forbidden, serialized)

    def test_sales_corrupt_incomplete_stale_and_missing_are_explicit(self):
        company = {"record_type": "company", "record_id": COMPANY_2}
        contact = {"record_type": "contact", "record_id": CONTACT_2, "company_id": COMPANY_2, "is_active": True}
        self._write_sales("heartbeat-review-stale.json", created=NOW - timedelta(days=8), records=[company, contact])
        (self.sales / "heartbeat-review-corrupt.json").write_text('{"created_at":NaN}')
        self._write_sales("heartbeat-review-incomplete.json", created=NOW - timedelta(hours=1), records=[company, contact], complete="FALSE")
        result = subject.export_bmasia_sales(now=NOW, sales_root=self.sales)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["coverage"]["total"], 3)
        self.assertEqual(result["coverage"]["failed"], 3)
        all_holds = {hold for row in result["records"] for hold in row["holds"]}
        self.assertTrue({"SOURCE_STALE", "SOURCE_INVALID", "SOURCE_INCOMPLETE"}.issubset(all_holds))
        empty = self.root / "empty"
        empty.mkdir()
        missing = subject.export_bmasia_sales(now=NOW, sales_root=empty)
        self.assertEqual(missing["records"][0]["holds"], ["SOURCE_MISSING"])

    def test_four_tab_hash_receipt_is_not_a_record_manifest(self):
        # A verified aggregate proves the scan happened, but contains neither
        # exact company/record identities nor per-record facts.  It must never
        # promote coverage to complete or invent ledger rows.
        (self.sales / "daily-latest.json").write_text(json.dumps({
            "completed_at": NOW.isoformat(),
            "payload": {"active_pipeline_mirror_verification": {
                "outcome": "VERIFIED", "tabs": 4, "retained_rows": 115,
                "source_active_rows_sha256": "a" * 64,
            }},
        }))
        result = subject.export_bmasia_sales(now=NOW, sales_root=self.sales)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["coverage"]["exported"], 0)
        self.assertEqual(result["records"][0]["holds"], ["SOURCE_MISSING"])

    def test_sales_equal_timestamp_conflict_and_absent_facts(self):
        company = {"record_type": "company", "record_id": COMPANY_2}
        one = {"record_type": "contact", "record_id": CONTACT_2, "company_id": COMPANY_2, "is_active": True}
        two = {**one, "unsubscribed": False}
        self._write_sales("heartbeat-review-a.json", created=NOW - timedelta(hours=1), records=[company, one])
        self._write_sales("heartbeat-review-b.json", created=NOW - timedelta(hours=1), records=[company, two])
        result = subject.export_bmasia_sales(now=NOW, sales_root=self.sales)
        row = next(row for row in result["records"] if row["record"])
        self.assertIn("SOURCE_CONFLICT", row["holds"])
        self.assertNotIn("last_contact_date", row["facts"])
        self.assertEqual(result["coverage"]["failed"], 1)

    def test_export_hash_ignores_export_time_but_covers_observation_time(self):
        first = subject.export_cara(now=NOW, cara_db=self.cara)
        second = subject.export_cara(now=NOW + timedelta(minutes=1), cara_db=self.cara)
        self.assertNotEqual(first["exported_at"], second["exported_at"])
        self.assertEqual(first["export_sha256"], second["export_sha256"])
        db = sqlite3.connect(self.cara)
        packet = json.loads(db.execute("SELECT packet_json FROM packets WHERE account_id=?", (COMPANY_1,)).fetchone()[0])
        packet["observed_at"] = (NOW - timedelta(minutes=30)).isoformat()
        db.execute("UPDATE packets SET packet_json=? WHERE account_id=?", (json.dumps(packet), COMPANY_1))
        db.commit()
        db.close()
        third = subject.export_cara(now=NOW + timedelta(minutes=1), cara_db=self.cara)
        self.assertNotEqual(first["export_sha256"], third["export_sha256"])

    def test_cli_private_output_and_bounded_receipt(self):
        output = self.root / "export.json"
        stdout = StringIO()
        with patch.object(subject, "CARA_DB", self.cara), redirect_stdout(stdout):
            self.assertEqual(subject.main(["--source", "cara", "--output", str(output)]), 0)
        receipt = json.loads(stdout.getvalue())
        document = json.loads(output.read_text())
        self.assertEqual(receipt["export_sha256"], document["export_sha256"])
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertNotIn(str(self.cara), stdout.getvalue())

    def test_schema_shape_limits_and_no_dangerous_integrations(self):
        result = subject.export_cara(now=NOW, cara_db=self.cara)
        self.assertEqual(set(result), {"schema", "source", "source_authentication", "exported_at", "source_observed_at", "coverage", "records", "export_sha256"})
        self.assertLessEqual(len(json.dumps(result, separators=(",", ":")).encode()), subject.MAX_OUTPUT_BYTES)
        self.assertTrue(all(subject._uuid_or_none(value) for row in result["records"] for value in row["company_ids"]))
        source = (ROOT / "tools" / "agent_crm_local_export.py").read_text()
        for forbidden in ("requests", "httpx", "keyring", "oauth", "subprocess", ".initialize(", "gmail", "send_message"):
            self.assertNotIn(forbidden, source.lower())

    def test_both_local_exports_satisfy_central_contract(self):
        company = {"record_type": "company", "record_id": COMPANY_2}
        opportunity = {"record_type": "opportunity", "record_id": OPPORTUNITY, "company_id": COMPANY_2, "stage": "Open", "is_active": True}
        self._write_sales("heartbeat-review-contract.json", created=NOW - timedelta(minutes=1), records=[company, opportunity])
        for document in (
            subject.export_cara(now=NOW, cara_db=self.cara),
            subject.export_bmasia_sales(now=NOW, sales_root=self.sales),
        ):
            with self.subTest(source=document["source"]):
                production.validate_export(document, production.OPERATOR_UID, NOW)


if __name__ == "__main__":
    unittest.main()
