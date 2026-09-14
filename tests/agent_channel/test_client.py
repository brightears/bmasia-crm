from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CLIENT = load_module("agent_channel_client", "deploy/agent-shadow/client.py")
FIXTURES = load_module(
    "agent_channel_fixtures", "deploy/agent-shadow/make_synthetic_fixtures.py",
)
NOW = dt.datetime(2026, 9, 14, 4, 30, tzinfo=dt.timezone.utc)


class FakeSocket:
    def __init__(self, response=None, failure=None):
        self.response = bytearray(response or b"")
        self.failure = failure
        self.timeouts = []
        self.connected = []
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, path):
        self.connected.append(path)
        if self.failure:
            raise self.failure

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        # Deliberately fragment responses to exercise exact framed reads.
        size = min(size, 3)
        value = bytes(self.response[:size])
        del self.response[:size]
        return value


def indexed_bundle():
    bundle = FIXTURES.generate_bundle(NOW)
    return bundle, {entry["name"]: entry for entry in bundle["reports"]}


class FixtureTests(unittest.TestCase):
    def test_bundle_has_exact_fake_variants_and_hash_bindings(self):
        bundle, entries = indexed_bundle()
        self.assertEqual(bundle["schema"], "bmasia.agent-channel-fixtures.v1")
        self.assertEqual(bundle["environment"], "synthetic")
        self.assertEqual(bundle["generated_at"], NOW.isoformat())
        self.assertEqual(len(entries), 12)
        self.assertEqual(
            [entry["name"] for entry in bundle["reports"]],
            [
                "theo-valid", "lyra-valid", "riff-valid", "nina-valid",
                "theo-collision", "lyra-collision", "riff-collision", "nina-collision",
                "theo-unverified", "lyra-unverified", "riff-unverified", "nina-unverified",
            ],
        )

        for agent in ("theo", "lyra", "riff", "nina"):
            valid = entries[agent + "-valid"]
            collision = entries[agent + "-collision"]
            unverified = entries[agent + "-unverified"]
            self.assertEqual(valid["report"]["event_id"], collision["report"]["event_id"])
            self.assertNotEqual(valid["report"]["event_id"], unverified["report"]["event_id"])
            self.assertEqual(
                {item["report"]["record"]["id"] for item in (valid, collision, unverified)},
                {valid["report"]["record"]["id"]},
            )
            self.assertEqual(valid["snapshot_fields"], {
                valid["report"]["changes"][0]["field"]:
                valid["report"]["changes"][0]["before"],
            })
            self.assertEqual(valid["report"]["follow_up"], None)
            self.assertEqual(
                dt.datetime.fromisoformat(valid["report"]["observed_at"]),
                NOW - dt.timedelta(minutes=5),
            )

            evidence = valid["report"]["evidence"][0]
            expected_reference = "synthetic:channel:%s:v1" % agent
            expected_text = "Synthetic channel fixture for %s; no customer data." % agent
            self.assertEqual(evidence["reference"], expected_reference)
            self.assertEqual(bundle["evidence"][expected_reference], expected_text)
            self.assertEqual(
                evidence["sha256"], hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(collision["report"]["evidence"], valid["report"]["evidence"])

            missing = unverified["report"]["evidence"][0]
            self.assertNotIn(missing["reference"], bundle["evidence"])
            self.assertNotEqual(missing["sha256"], evidence["sha256"])

    def test_bundle_is_stable_for_same_generation_instant(self):
        self.assertEqual(FIXTURES.generate_bundle(NOW), FIXTURES.generate_bundle(NOW))

    def test_expected_change_values(self):
        _, entries = indexed_bundle()
        self.assertEqual(entries["theo-valid"]["report"]["changes"][0], {
            "field": "follow_up_date", "before": None, "after": "2026-09-14",
        })
        self.assertEqual(entries["theo-collision"]["report"]["changes"][0]["after"], "2026-09-15")
        self.assertEqual(entries["lyra-valid"]["report"]["changes"][0]["after"], "Synthetic manager")
        self.assertEqual(entries["riff-valid"]["report"]["changes"][0]["after"], "high")
        self.assertEqual(entries["nina-valid"]["report"]["changes"][0]["after"], "Synthetic relaxed evening")

    def test_private_new_directory_and_canonical_report_files(self):
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent) / "fixtures"
            bundle = FIXTURES.write_bundle(target, NOW)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((target / "reports").stat().st_mode), 0o700)
            for entry in bundle["reports"]:
                path = target / "reports" / (entry["name"] + ".json")
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(path.read_bytes(), CLIENT.canonical_bytes(entry["report"]))
            self.assertEqual(stat.S_IMODE((target / "registry.json").stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                FIXTURES.write_bundle(target, NOW)


class ClientTests(unittest.TestCase):
    def setUp(self):
        _, entries = indexed_bundle()
        self.report = copy.deepcopy(entries["theo-valid"]["report"])

    def framed_response(self, response):
        raw = json.dumps(response, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return struct.pack("!I", len(raw)) + raw

    def test_round_trip_uses_one_framed_report_and_five_second_timeout(self):
        fake = FakeSocket(self.framed_response({"outcome": "accepted", "crm_writes": 0}))
        with mock.patch.object(CLIENT.os, "getuid", return_value=1008), mock.patch.object(
            CLIENT.socket, "socket", return_value=fake,
        ) as socket_factory:
            result = CLIENT.submit_report(self.report, "/tmp/fake.sock")
        self.assertEqual(result["outcome"], "accepted")
        socket_factory.assert_called_once_with(CLIENT.socket.AF_UNIX, CLIENT.socket.SOCK_STREAM)
        self.assertEqual(fake.timeouts, [5])
        self.assertEqual(fake.connected, ["/tmp/fake.sock"])
        payload = CLIENT.canonical_bytes(self.report)
        self.assertEqual(fake.sent, [struct.pack("!I", len(payload)) + payload])
        self.assertNotIn(b"context", payload)
        self.assertNotIn(b"snapshot", payload)

    def test_submit_helper_rejects_unknown_uid_and_reporter_mismatch_before_socket(self):
        with mock.patch.object(CLIENT.os, "getuid", return_value=501), mock.patch.object(
            CLIENT.socket, "socket",
        ) as socket_factory:
            with self.assertRaisesRegex(ValueError, "not authorized"):
                CLIENT.submit_report(self.report)
            socket_factory.assert_not_called()
        with mock.patch.object(CLIENT.os, "getuid", return_value=1000), mock.patch.object(
            CLIENT.socket, "socket",
        ) as socket_factory:
            with self.assertRaisesRegex(ValueError, "does not match"):
                CLIENT.submit_report(self.report)
            socket_factory.assert_not_called()

    def test_only_exact_canonical_report_bytes_are_accepted(self):
        raw = CLIENT.canonical_bytes(self.report)
        self.assertEqual(CLIENT.parse_report_bytes(raw), self.report)
        with self.assertRaisesRegex(ValueError, "canonical"):
            CLIENT.parse_report_bytes(json.dumps(self.report, indent=2).encode("utf-8"))
        with self.assertRaisesRegex(ValueError, "unknown keys"):
            report_with_context = {**self.report, "context": {"sender": "theo"}}
            CLIENT.parse_report_bytes(CLIENT.canonical_bytes(report_with_context))

    def test_duplicate_keys_nonfinite_and_oversize_are_rejected(self):
        duplicate = CLIENT.canonical_bytes(self.report).replace(
            b'{"changes":', b'{"schema":"bmasia.agent-report.v1","changes":', 1,
        )
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            CLIENT.parse_report_bytes(duplicate)
        nonfinite = CLIENT.canonical_bytes(self.report).replace(b'"after":"2026-09-14"', b'"after":NaN')
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            CLIENT.parse_report_bytes(nonfinite)
        with self.assertRaisesRegex(ValueError, "32 KiB"):
            CLIENT.parse_report_bytes(b" " * (CLIENT.MAX_REPORT_BYTES + 1))

    def test_oversize_response_is_rejected_without_body_read(self):
        fake = FakeSocket(struct.pack("!I", CLIENT.MAX_RESPONSE_BYTES + 1))
        with mock.patch.object(CLIENT.os, "getuid", return_value=1008), mock.patch.object(
            CLIENT.socket, "socket", return_value=fake,
        ):
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                CLIENT.submit_report(self.report)
        self.assertEqual(len(fake.sent), 1)

    def test_transport_failure_is_not_retried(self):
        fake = FakeSocket(failure=TimeoutError("synthetic timeout"))
        with mock.patch.object(CLIENT.os, "getuid", return_value=1008), mock.patch.object(
            CLIENT.socket, "socket", return_value=fake,
        ) as socket_factory:
            with self.assertRaises(TimeoutError):
                CLIENT.submit_report(self.report)
        socket_factory.assert_called_once()
        self.assertEqual(fake.connected, [CLIENT.DEFAULT_SOCKET])
        self.assertEqual(fake.timeouts, [CLIENT.TIMEOUT_SECONDS])
        self.assertEqual(fake.sent, [])

    def test_exit_code_requires_outcome_accepted_or_replayed(self):
        self.assertEqual(CLIENT._exit_code({"outcome": "accepted"}), 0)
        self.assertEqual(CLIENT._exit_code({"outcome": "replayed"}), 0)
        self.assertEqual(CLIENT._exit_code({"status": "accepted"}), 2)
        self.assertEqual(CLIENT._exit_code({"outcome": "rejected"}), 2)


if __name__ == "__main__":
    unittest.main()
