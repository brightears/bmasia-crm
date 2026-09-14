import importlib.util
import json
import os
import sqlite3
import stat
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("native", ROOT / "tools" / "agent_crm_native_export.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
PRODUCTION_SPEC = importlib.util.spec_from_file_location("production_for_native", ROOT / "tools" / "agent_crm_production.py")
production = importlib.util.module_from_spec(PRODUCTION_SPEC)
PRODUCTION_SPEC.loader.exec_module(production)

NOW = datetime(2026, 9, 14, 6, tzinfo=UTC)
COMPANY = "550e8400-e29b-41d4-a716-446655440000"
RECORD = "354d0392-e578-49e7-b239-1cf8113c42cf"


class NativeExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def activity_db(self, values=None):
        path = self.root / "activity.sqlite3"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE work (task_key TEXT,source TEXT,source_sha256 TEXT,state TEXT,companies TEXT,created_at TEXT,updated_at TEXT,revision INTEGER)")
        for item in values or []:
            db.execute("INSERT INTO work VALUES (?,?,?,?,?,?,?,?)", item)
        db.commit()
        db.close()
        return path

    def work(self, **changes):
        values = {
            "task_key": "customer supplied subject and private@example.test",
            "source": "mail",
            "source_sha256": "a" * 64,
            "state": "OPEN",
            "companies": json.dumps([COMPANY]),
            "created_at": (NOW - timedelta(hours=1)).isoformat(),
            "updated_at": (NOW - timedelta(minutes=30)).isoformat(),
            "revision": 2,
        }
        values.update(changes)
        return tuple(values[key] for key in ("task_key", "source", "source_sha256", "state", "companies", "created_at", "updated_at", "revision"))

    def riff_root(self):
        root = self.root / "riff"
        for name in ("pending", "processing", "completed", "failed"):
            (root / name).mkdir(parents=True)
        return root

    def test_activity_is_full_source_snapshot_but_inventory_baseline_is_incomplete(self):
        path = self.activity_db([self.work()])
        before = path.read_bytes()
        first = native.export("theo", now=NOW, path=path)
        second = native.export("theo", now=NOW + timedelta(minutes=1), path=path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(first["coverage"], {"total": 1, "exported": 0, "complete": True, "unbound": 1, "failed": 0, "agent_inventory_complete": False, "legacy_baseline_complete": False})
        self.assertEqual(first["records"][0]["source_key"], second["records"][0]["source_key"])
        self.assertIn("UNBOUND_CRM_RECORD", first["records"][0]["holds"])
        self.assertTrue(first["records"][0]["facts"]["source_complete"])
        self.assertFalse(first["records"][0]["facts"]["agent_inventory_complete"])
        serialized = json.dumps(first)
        self.assertNotIn("customer supplied subject", serialized)
        self.assertNotIn("private@example", serialized)

    def test_activity_invalid_fields_are_failed_rows_not_missing_source(self):
        bad = self.work(source_sha256="bad", state="private prose with spaces", companies='["not-a-uuid"]', updated_at="bad", revision=-1)
        result = native.export("lyra", now=NOW, path=self.activity_db([bad]))
        row = result["records"][0]
        self.assertIn("SOURCE_INVALID", row["holds"])
        self.assertNotIn("SOURCE_MISSING", row["holds"])
        self.assertEqual(result["coverage"]["failed"], 1)
        self.assertEqual(row["facts"], {"state": "UNKNOWN", "revision": 0, "source_complete": True, "agent_inventory_complete": False, "legacy_baseline_complete": False})

    def test_activity_schema_missing_and_result_limit_are_precise(self):
        missing = native.export("theo", now=NOW, path=self.root / "missing.sqlite3")
        self.assertEqual(missing["records"][0]["holds"], ["SOURCE_MISSING"])
        db_path = self.root / "wrong.sqlite3"
        sqlite3.connect(db_path).close()
        wrong = native.export("theo", now=NOW, path=db_path)
        self.assertEqual(wrong["records"][0]["holds"], ["SOURCE_SCHEMA_UNSUPPORTED"])
        path = self.activity_db([self.work(task_key=str(index)) for index in range(3)])
        with patch.object(native, "MAX", 2):
            limited = native.export("theo", now=NOW, path=path)
        self.assertEqual(limited["records"][0]["holds"], ["SOURCE_RESULT_LIMIT"])

    def test_nina_stable_identity_bounded_private_hash_only(self):
        path = self.root / "nina.md"
        path.write_text("customer email secret@example.test and arbitrary notes")
        os.utime(path, (NOW.timestamp(), NOW.timestamp()))
        first = native.export("nina", now=NOW, path=path)
        path.write_text("different protected prose")
        os.utime(path, ((NOW + timedelta(minutes=1)).timestamp(), (NOW + timedelta(minutes=1)).timestamp()))
        second = native.export("nina", now=NOW + timedelta(minutes=1), path=path)
        self.assertEqual(first["records"][0]["source_key"], "workstream:nina")
        self.assertEqual(second["records"][0]["source_key"], "workstream:nina")
        self.assertNotEqual(first["records"][0]["version_hash"], second["records"][0]["version_hash"])
        self.assertNotIn("secret@example", json.dumps(first))
        link = self.root / "link.md"
        link.symlink_to(path)
        rejected = native.export("nina", now=NOW, path=link)
        self.assertEqual(rejected["records"][0]["holds"], ["SOURCE_PATH_REJECTED"])
        with patch.object(native, "MAX_SOURCE_BYTES", 2):
            oversized = native.export("nina", now=NOW, path=path)
        self.assertEqual(oversized["records"][0]["holds"], ["SOURCE_PATH_REJECTED"])

    def test_riff_empty_is_complete_not_fabricated_failure(self):
        result = native.export("riff", now=NOW, path=self.riff_root())
        self.assertEqual(result["records"], [])
        self.assertEqual(result["coverage"], {"total": 0, "exported": 0, "complete": True, "unbound": 0, "failed": 0, "agent_inventory_complete": False, "legacy_baseline_complete": False})

    def test_riff_received_at_unix_binding_and_privacy(self):
        root = self.riff_root()
        payload = {
            "event_id": "event-1", "received_at_unix": NOW.timestamp() - 60,
            "company_id": COMPANY, "record_id": RECORD, "collection": "tickets",
            "body": "full ticket prose secret@example.test",
        }
        (root / "pending" / "one.json").write_text(json.dumps(payload))
        result = native.export("riff", now=NOW, path=root)
        row = result["records"][0]
        self.assertEqual(row["company_ids"], [COMPANY])
        self.assertEqual(row["record"], {"collection": "tickets", "id": RECORD})
        self.assertEqual(row["facts"]["queue_state"], "pending")
        self.assertNotIn("secret@example", json.dumps(result))
        self.assertEqual(result["coverage"]["exported"], 1)

    def test_riff_wrong_company_corrupt_json_and_duplicate_lifecycle_fail_closed(self):
        root = self.riff_root()
        base = {"event_id": "duplicate", "received_at": (NOW - timedelta(minutes=1)).isoformat(), "company_id": "wrong", "record_id": RECORD, "collection": "tickets"}
        (root / "pending" / "a.json").write_text(json.dumps(base))
        newer = {**base, "received_at": NOW.isoformat(), "company_id": COMPANY}
        (root / "processing" / "b.json").write_text(json.dumps(newer))
        (root / "failed" / "bad.json").write_text('{"event_id":"bad","event_id":"other","received_at":NaN}')
        result = native.export("riff", now=NOW, path=root)
        duplicate = next(row for row in result["records"] if "SOURCE_CONFLICT" in row["holds"])
        self.assertIn("SOURCE_CONFLICT", duplicate["holds"])
        self.assertEqual(duplicate["company_ids"], [COMPANY])
        self.assertTrue(any(row["holds"] == ["SOURCE_INVALID"] for row in result["records"]))
        self.assertEqual(result["coverage"]["failed"], 2)

    def test_riff_nested_symlink_and_future_timestamp_are_rejected(self):
        root = self.riff_root()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "event.json").write_text("{}")
        (root / "processing").rmdir()
        (root / "processing").symlink_to(outside, target_is_directory=True)
        rejected = native.export("riff", now=NOW, path=root)
        self.assertEqual(rejected["records"][0]["holds"], ["SOURCE_PATH_REJECTED"])
        (root / "processing").unlink()
        (root / "processing").mkdir()
        payload = {"event_id": "future", "received_at": (NOW + timedelta(hours=1)).isoformat()}
        (root / "pending" / "future.json").write_text(json.dumps(payload))
        future = native.export("riff", now=NOW, path=root)
        self.assertIn("SOURCE_FUTURE", future["records"][0]["holds"])

    def test_riff_root_owned_nonwritable_parent_is_audited_layout(self):
        root = self.riff_root()
        real_lstat = Path.lstat

        def audited_lstat(path):
            info = real_lstat(path)
            if path == root:
                values = list(info)
                values[stat.ST_UID] = 0
                values[stat.ST_MODE] = stat.S_IFDIR | 0o755
                return os.stat_result(values)
            return info

        with patch.object(Path, "lstat", audited_lstat):
            accepted = native.export("riff", now=NOW, path=root)
        self.assertTrue(accepted["coverage"]["complete"])
        self.assertEqual(accepted["records"], [])

        def writable_lstat(path):
            info = real_lstat(path)
            if path == root:
                values = list(info)
                values[stat.ST_UID] = 0
                values[stat.ST_MODE] = stat.S_IFDIR | 0o775
                return os.stat_result(values)
            return info

        with patch.object(Path, "lstat", writable_lstat):
            rejected = native.export("riff", now=NOW, path=root)
        self.assertEqual(rejected["records"][0]["holds"], ["SOURCE_PATH_REJECTED"])

    def test_export_size_and_private_output_are_enforced(self):
        path = self.activity_db([self.work()])
        with patch.object(native, "MAX_BYTES", 100):
            with self.assertRaises(native.ExportError):
                native.export("theo", now=NOW, path=path)
        output = self.root / "export.json"
        stdout = StringIO()
        with patch.dict(native.PATHS, {"theo": path}), redirect_stdout(stdout):
            self.assertEqual(native.main(["--source", "theo", "--output", str(output)]), 0)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertNotIn(str(path), stdout.getvalue())
        self.assertEqual(json.loads(output.read_text())["source"], "theo")

    def test_all_native_exports_satisfy_central_contract(self):
        activity = self.activity_db([self.work()])
        nina = self.root / "nina.md"
        nina.write_text("private source prose")
        os.utime(nina, ((NOW - timedelta(minutes=1)).timestamp(), (NOW - timedelta(minutes=1)).timestamp()))
        riff = self.riff_root()
        (riff / "pending" / "event.json").write_text(json.dumps({"event_id": "event-1", "received_at": NOW.isoformat()}))
        fixtures = {
            "theo": (1008, activity), "lyra": (1000, activity),
            "riff": (1007, riff), "nina": (1004, nina),
        }
        for source, (peer_uid, path) in fixtures.items():
            with self.subTest(source=source):
                document = native.export(source, now=NOW, path=path)
                production.validate_export(document, peer_uid, NOW)


if __name__ == "__main__":
    unittest.main()
