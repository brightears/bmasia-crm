from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sqlite3
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


COLLECTOR = load_module("agent_channel_collector_tests", "deploy/agent-shadow/collector.py")
FIXTURES = load_module(
    "agent_channel_fixture_tests", "deploy/agent-shadow/make_synthetic_fixtures.py",
)


class FakeConnection:
    """Small fragmented stream used at the Collector.handle boundary."""

    def __init__(self, incoming=b"", *, send_error=None):
        self.incoming = bytearray(incoming)
        self.send_error = send_error
        self.sent = []
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self, size):
        size = min(size, 5)
        chunk = bytes(self.incoming[:size])
        del self.incoming[:size]
        return chunk

    def sendall(self, value):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(value)

    def response(self):
        if len(self.sent) != 1:
            raise AssertionError("expected exactly one response frame")
        frame = self.sent[0]
        if len(frame) < 4:
            raise AssertionError("response frame is missing its length")
        length = struct.unpack("!I", frame[:4])[0]
        if len(frame[4:]) != length:
            raise AssertionError("response length does not match its frame")
        return COLLECTOR.decode_json(frame[4:])


class DripConnection(FakeConnection):
    def recv(self, size):
        return super().recv(min(size, 1))


def request_frame(value):
    payload = COLLECTOR.json_bytes(value)
    return struct.pack("!I", len(payload)) + payload


class CollectorTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.fixture_directory = self.base / "fixtures"
        self.generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.bundle = FIXTURES.write_bundle(self.fixture_directory, self.generated_at)
        self.registry_path = self.fixture_directory / "registry.json"
        self.registry_path.chmod(0o600)
        self.core_path = self.base / "agent_shadow_core.py"
        self.core_path.write_bytes((ROOT / "crm_app/services/agent_shadow.py").read_bytes())
        self.core_path.chmod(0o600)
        self.entries = {entry["name"]: entry for entry in self.bundle["reports"]}
        self.config = {
            "schema": "bmasia.agent-channel-config.v1",
            "environment": "synthetic",
            "socket_path": str(self.base / "collector.sock"),
            "state_directory": str(self.state),
            "fixture_registry": str(self.registry_path),
            "core_path": str(self.core_path),
        }
        self.collector = COLLECTOR.Collector(self.config)

    def tearDown(self):
        self.temporary.cleanup()

    def handle(self, report, uid, *, connection=None):
        connection = connection or FakeConnection(request_frame(report))
        with mock.patch.object(COLLECTOR, "peer_identity", return_value=(123, uid, 456)):
            self.collector.handle(connection)
        return connection.response()

    def audit_counts(self):
        with sqlite3.connect(self.state / "channel-audit.sqlite3") as database:
            requests = database.execute("SELECT count(*) FROM channel_requests").fetchone()[0]
            receipts = database.execute("SELECT count(*) FROM channel_receipts").fetchone()[0]
        return requests, receipts


class ProcessingTests(CollectorTestCase):
    def test_all_four_uids_accept_replay_collide_and_leave_unverified(self):
        uid_by_agent = {agent: uid for uid, agent in COLLECTOR.UID_AGENT.items()}
        now = self.generated_at + dt.timedelta(minutes=1)
        for agent in ("theo", "lyra", "riff", "nina"):
            with self.subTest(agent=agent):
                uid = uid_by_agent[agent]
                accepted = self.collector.process(
                    self.entries[agent + "-valid"]["report"], uid,
                    "%s-accepted" % agent, now,
                )
                replayed = self.collector.process(
                    self.entries[agent + "-valid"]["report"], uid,
                    "%s-replayed" % agent, now,
                )
                collision = self.collector.process(
                    self.entries[agent + "-collision"]["report"], uid,
                    "%s-collision" % agent, now,
                )
                unverified = self.collector.process(
                    self.entries[agent + "-unverified"]["report"], uid,
                    "%s-unverified" % agent, now,
                )
                self.assertEqual(
                    [accepted["outcome"], replayed["outcome"], collision["outcome"],
                     unverified["outcome"]],
                    ["accepted", "replayed", "conflict", "needs_source_verification"],
                )
                self.assertEqual(accepted["authenticated_peer_uid"], uid)
                self.assertEqual(accepted["reporter"], agent)
                self.assertTrue(accepted["verified"])
                self.assertFalse(unverified["verified"])
                for receipt in (accepted, replayed, collision, unverified):
                    self.assertEqual(receipt["crm_writes"], 0)
                    self.assertFalse(receipt["customer_record_mutation"])
                    self.assertFalse(receipt["customer_outbound"])
                    self.assertFalse(receipt["model_invoked"])
                    self.assertFalse(receipt["network_egress"])

    def test_process_rejects_spoof_and_unknown_uid(self):
        report = self.entries["theo-valid"]["report"]
        now = self.generated_at + dt.timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, "reporter_does_not_match_peer_uid"):
            self.collector.process(report, 1000, "spoof", now)
        with self.assertRaisesRegex(ValueError, "source_uid_not_allowed"):
            self.collector.process(report, 65534, "unknown", now)


class HandlerBoundaryTests(CollectorTestCase):
    def test_spoof_unknown_uid_and_context_injection_are_rejected(self):
        theo = self.entries["theo-valid"]["report"]

        unknown_connection = FakeConnection(request_frame(theo))
        unknown = self.handle(theo, 65534, connection=unknown_connection)
        self.assertEqual(unknown["outcome"], "rejected")
        self.assertEqual(unknown["reason"], "source_uid_not_allowed")
        # An unknown peer is rejected before its body is consumed.
        self.assertEqual(bytes(unknown_connection.incoming), request_frame(theo))

        spoof = self.handle(theo, 1000)
        self.assertEqual(spoof["outcome"], "rejected")
        self.assertEqual(spoof["reason"], "reporter_does_not_match_peer_uid")

        injected = copy.deepcopy(theo)
        injected["context"] = {
            "sender": "theo", "verified": True, "marker": "UNTRUSTED-CONTEXT-MARKER",
        }
        rejected = self.handle(injected, 1008)
        self.assertEqual(rejected["outcome"], "rejected")
        self.assertEqual(rejected["reason"], "invalid_or_stale_report")
        self.assertNotIn("context", rejected)
        self.assertNotIn("UNTRUSTED-CONTEXT-MARKER", json.dumps(rejected))

    def test_unknown_allowlist_payload_body_is_never_persisted(self):
        report = copy.deepcopy(self.entries["lyra-valid"]["report"])
        marker = "UNKNOWN-PAYLOAD-MUST-NOT-PERSIST-94fbc9"
        report["changes"][0]["after"] = marker
        rejected = self.handle(report, 1000)
        self.assertEqual(rejected["outcome"], "rejected")
        self.assertEqual(rejected["reason"], "synthetic_fixture_not_allowlisted")
        self.assertNotIn(marker, json.dumps(rejected))

        with sqlite3.connect(self.state / "channel-audit.sqlite3") as database:
            self.assertEqual(database.execute(
                "SELECT count(*) FROM channel_requests",
            ).fetchone()[0], 1)
            self.assertEqual(database.execute(
                "SELECT count(*) FROM channel_receipts",
            ).fetchone()[0], 0)
            audit_dump = "\n".join(database.iterdump())
        with sqlite3.connect(self.state / "shadow.sqlite3") as database:
            self.assertEqual(database.execute(
                "SELECT count(*) FROM shadow_events",
            ).fetchone()[0], 0)
            shadow_dump = "\n".join(database.iterdump())
        self.assertNotIn(marker, audit_dump)
        self.assertNotIn(marker, shadow_dump)

    def test_oversize_truncation_and_empty_disconnect_do_not_poison_handler(self):
        invalid_frames = (
            (struct.pack("!I", COLLECTOR.MAX_REQUEST + 1), "request_size_invalid"),
            (struct.pack("!I", 20) + b"short", "truncated_frame"),
            (b"", "truncated_frame"),
        )
        for index, (incoming, reason) in enumerate(invalid_frames):
            with self.subTest(reason=reason, index=index):
                connection = FakeConnection(incoming)
                with mock.patch.object(
                    COLLECTOR, "peer_identity", return_value=(123, 1007, 456),
                ):
                    self.collector.handle(connection)
                response = connection.response()
                self.assertEqual(response["outcome"], "rejected")
                self.assertEqual(response["reason"], reason)
                self.assertEqual(connection.timeouts[0], 0.2)
                self.assertTrue(all(0 < timeout <= 0.2 for timeout in connection.timeouts))

        healthy = self.handle(self.entries["riff-valid"]["report"], 1007)
        self.assertEqual(healthy["outcome"], "accepted")
        self.assertEqual(self.audit_counts(), (4, 1))

    def test_response_disconnect_is_swallowed_and_explicit_retry_replays(self):
        report = self.entries["nina-valid"]["report"]
        disconnected = FakeConnection(
            request_frame(report), send_error=BrokenPipeError("synthetic disconnect"),
        )
        with mock.patch.object(COLLECTOR, "peer_identity", return_value=(123, 1004, 456)):
            self.collector.handle(disconnected)
        self.assertEqual(disconnected.sent, [])
        self.assertEqual(self.audit_counts(), (1, 1))

        replay = self.handle(report, 1004)
        self.assertEqual(replay["outcome"], "replayed")
        self.assertTrue(replay["replay"])
        self.assertEqual(self.audit_counts(), (2, 1))

    def test_audit_failure_is_fail_closed_then_retry_recovers(self):
        report = self.entries["theo-valid"]["report"]
        connection = FakeConnection(request_frame(report))
        with mock.patch.object(COLLECTOR, "peer_identity", return_value=(123, 1008, 456)), \
                mock.patch.object(self.collector.audit, "record", side_effect=OSError("full")):
            self.collector.handle(connection)
        rejected = connection.response()
        self.assertEqual(rejected["outcome"], "indeterminate")
        self.assertEqual(rejected["reason"], "audit_unavailable")
        self.assertEqual(rejected["crm_writes"], 0)
        self.assertEqual(self.audit_counts(), (0, 0))

        retry = self.handle(report, 1008)
        self.assertEqual(retry["outcome"], "replayed")
        self.assertTrue(retry["replay"])
        self.assertEqual(self.audit_counts(), (1, 1))

    def test_unknown_uid_rate_bucket_is_bounded_and_does_not_block_known_uid(self):
        report = self.entries["theo-valid"]["report"]
        outcomes = []
        reasons = []
        for uid in range(65000, 65011):
            connection = FakeConnection(request_frame(report))
            with mock.patch.object(COLLECTOR, "peer_identity", return_value=(123, uid, 456)):
                self.collector.handle(connection)
            response = connection.response()
            outcomes.append(response["outcome"])
            reasons.append(response["reason"])
        self.assertEqual(outcomes, ["rejected"] * 11)
        self.assertEqual(reasons[:10], ["source_uid_not_allowed"] * 10)
        self.assertEqual(reasons[10], "rate_limited")

        # Unknown peers share only the -1 bucket. A configured runtime UID has
        # its own allowance and remains healthy.
        accepted = self.handle(report, 1008)
        self.assertEqual(accepted["outcome"], "accepted")

    def test_frame_deadline_is_total_not_reset_by_byte_drip(self):
        connection = DripConnection(struct.pack("!I", 100) + b"x" * 100)
        # Four header bytes arrive just inside the deadline, but the first body
        # byte would begin after it. The collector must not grant a fresh 0.2s.
        clock = iter((100.0, 100.01, 100.05, 100.10, 100.15, 100.201))
        with mock.patch.object(COLLECTOR.time, "monotonic", side_effect=lambda: next(clock)):
            with self.assertRaisesRegex(TimeoutError, "frame_deadline_exceeded"):
                COLLECTOR.receive_frame(connection)
        self.assertEqual(len(connection.incoming), 100)
        self.assertEqual(len(connection.timeouts), 4)
        self.assertGreater(connection.timeouts[0], connection.timeouts[-1])


class ConfigurationAndRestartTests(CollectorTestCase):
    def test_configuration_and_registry_reject_non_synthetic_mode(self):
        wrong_config = {**self.config, "environment": "shadow"}
        with self.assertRaisesRegex(ValueError, "only_synthetic_mode_is_implemented"):
            COLLECTOR.Collector(wrong_config)

        wrong_registry = copy.deepcopy(self.bundle)
        wrong_registry["environment"] = "shadow"
        registry_path = self.base / "non-synthetic-registry.json"
        registry_path.write_bytes(COLLECTOR.json_bytes(wrong_registry))
        registry_path.chmod(0o600)
        config = {**self.config, "fixture_registry": str(registry_path)}
        with self.assertRaisesRegex(ValueError, "invalid_synthetic_registry"):
            COLLECTOR.Collector(config)

    def test_restart_preserves_ledger_and_audit_idempotency(self):
        report = self.entries["lyra-valid"]["report"]
        first = self.handle(report, 1000)
        self.assertEqual(first["outcome"], "accepted")
        first_receipt_id = first["receipt_id"]

        self.collector = COLLECTOR.Collector(self.config)
        second = self.handle(report, 1000)
        self.assertEqual(second["outcome"], "replayed")
        self.assertTrue(second["replay"])
        self.assertEqual(second["receipt_id"], first_receipt_id)
        self.assertEqual(self.audit_counts(), (2, 1))
        summary = self.collector.audit.summary()
        self.assertEqual(summary["outcomes"], {"accepted": 1, "replayed": 1})

    def test_audit_rotates_old_request_metadata_but_retains_receipts(self):
        audit_path = self.state / "channel-audit.sqlite3"
        old_receipt = {
            "receipt_id": "old-receipt", "outcome": "accepted", "reason": None,
        }
        with sqlite3.connect(audit_path) as database:
            database.execute(
                "INSERT INTO channel_receipts VALUES (?,?)",
                ("old-receipt", json.dumps(old_receipt)),
            )
            database.executemany(
                "INSERT INTO channel_requests VALUES (?,?,?,?,?,?)",
                (
                    ("old-%05d" % index, 1008, "accepted", None, "old-receipt",
                     self.generated_at.isoformat())
                    for index in range(10000)
                ),
            )

        new_receipt = {
            "receipt_id": "new-receipt", "outcome": "replayed", "reason": None,
        }
        self.collector.audit.record(
            "new-request", 1008, new_receipt,
            self.generated_at + dt.timedelta(minutes=1),
        )
        with sqlite3.connect(audit_path) as database:
            self.assertEqual(database.execute(
                "SELECT count(*) FROM channel_requests",
            ).fetchone()[0], 10000)
            self.assertIsNone(database.execute(
                "SELECT 1 FROM channel_requests WHERE request_id='old-00000'",
            ).fetchone())
            self.assertEqual(database.execute(
                "SELECT count(*) FROM channel_receipts",
            ).fetchone()[0], 2)
            self.assertEqual(
                {row[0] for row in database.execute("SELECT receipt_id FROM channel_receipts")},
                {"old-receipt", "new-receipt"},
            )


if __name__ == "__main__":
    unittest.main()
