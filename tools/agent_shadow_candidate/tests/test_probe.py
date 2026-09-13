import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from probe_candidate import PINNED_COMMIT, probe

CANDIDATE = Path(os.environ["BMASIA_COMPAI_SOURCE"]) if os.environ.get("BMASIA_COMPAI_SOURCE") else None
FIXTURE = ROOT / "synthetic_bmasia_fixture.json"


@unittest.skipUnless(CANDIDATE is not None and CANDIDATE.is_dir(), "Set BMASIA_COMPAI_SOURCE to the pinned candidate clone")
class ProbeTests(unittest.TestCase):
    def copy_candidate(self, directory):
        target = Path(directory) / "candidate"
        shutil.copytree(CANDIDATE, target, ignore=shutil.ignore_patterns("node_modules"))
        return target

    def test_pinned_candidate_has_verified_static_evidence(self):
        report = probe(CANDIDATE, FIXTURE)
        self.assertTrue(report["candidate"]["commit_matches_expected"])
        self.assertTrue(report["candidate"]["source_clean"])
        self.assertTrue(all(item["status"] == "verified_static" for item in report["mapping"]["verified_static"]))
        self.assertTrue(report["fixture"]["round_trip"]["matches_fixture"])
        self.assertEqual([item["record"] for item in report["mapping"]["unsupported"]], ["contract", "invoice", "zone"])

    def test_dirty_source_blocks_verified_status(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            schema = candidate / "packages/db/prisma/schema.prisma"
            schema.write_text(schema.read_text() + "\n")
            report = probe(candidate, FIXTURE, expected_commit=PINNED_COMMIT)
        self.assertTrue(all(item["status"] == "blocked_static" for item in report["mapping"]["verified_static"]))

    def test_missing_field_blocks_only_affected_record(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            schema = candidate / "packages/db/prisma/schema.prisma"
            schema.write_text(schema.read_text().replace("  website     String?\n", "", 1))
            report = probe(candidate, FIXTURE)
        company = next(item for item in report["mapping"]["verified_static"] if item["record"] == "company")
        self.assertEqual(company["status"], "blocked_static")
        self.assertIn("website", company["schema_fields_missing"])

    def test_missing_route_blocks_affected_record(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            router = candidate / "apps/api/src/activities/activities.router.ts"
            router.write_text(router.read_text().replace('restMeta("POST", "/activities", ["Activities"])', 'restMeta("POST", "/removed", ["Activities"])'))
            report = probe(candidate, FIXTURE)
        activity = next(item for item in report["mapping"]["verified_static"] if item["record"] == "activity")
        self.assertEqual(activity["status"], "blocked_static")
        self.assertIn("POST /activities", activity["required_routes_missing"])

    def test_commit_and_fixture_reference_drift_block_status(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            data = json.loads(FIXTURE.read_text())
            data["activity"]["contact_bmasia_id"] = "wrong-id"
            fixture.write_text(json.dumps(data))
            report = probe(CANDIDATE, fixture, expected_commit="0" * 40)
        self.assertFalse(report["candidate"]["commit_matches_expected"])
        self.assertFalse(report["fixture"]["references"]["activity_contact_matches"])
        self.assertTrue(all(item["status"] == "blocked_static" for item in report["mapping"]["verified_static"]))


if __name__ == "__main__":
    unittest.main()
