import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[2] / "tools/agent_crm_shadow.py"
SPEC = importlib.util.spec_from_file_location("agent_shadow_cli", CLI)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CliTests(unittest.TestCase):
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text('{"reporter":"lyra","reporter":"theo"}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                MODULE.load_json(path)

    def test_bounded_inputs_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            for data in ("x" * 32769, '{"value":NaN}'):
                path.write_text(data)
                with self.assertRaises(ValueError):
                    MODULE.load_json(path)

    def test_review_escapes_markdown_fences(self):
        value = MODULE.markdown({"reason": "```<script>alert(1)</script>"})
        self.assertEqual(value.count("```"), 2)

    def test_missing_report_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.sqlite3"
            result = subprocess.run([sys.executable, str(CLI), "report", "--ledger", str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(path.exists())

    def test_demo_four_sources_replays_collisions_and_no_side_effect_clients(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "demo"
            result = subprocess.run([sys.executable, str(CLI), "demo", "--directory", str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["exercise"], "synthetic_only")
            self.assertEqual(len(data["receipts"]), 13)
            self.assertEqual(sum(r.get("replay", False) for r in data["receipts"]), 4)
            self.assertEqual(sum(r["outcome"] == "conflict" for r in data["receipts"]), 4)
            self.assertEqual(data["receipts"][-1]["outcome"], "needs_source_verification")
            for receipt in data["receipts"]:
                self.assertEqual(receipt["crm_writes"], 0)
                self.assertFalse(receipt["customer_record_mutation"])
                self.assertFalse(receipt["customer_outbound"])
                self.assertFalse(receipt["model_invoked"])
            self.assertTrue((target / "REVIEW.md").is_file())
            # Import-time safety: the CLI imports no CRM ORM nor external client.
            self.assertNotIn("django", sys.modules)


if __name__ == "__main__":
    unittest.main()
