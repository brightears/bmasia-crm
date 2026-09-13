import datetime as dt
import importlib.util
import os
import tempfile
import threading
import unittest
import uuid

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "crm_app", "services", "agent_shadow.py")
_SPEC = importlib.util.spec_from_file_location("agent_shadow_core", _PATH)
_CORE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CORE)
ShadowLedger, assess_report = _CORE.ShadowLedger, _CORE.assess_report
canonical_hash, validate_report = _CORE.canonical_hash, _CORE.validate_report

NOW = dt.datetime(2026, 9, 13, 12, tzinfo=dt.timezone.utc)


def sample(**over):
    rec = {"collection": "contacts", "id": str(uuid.uuid4())}
    report = {"schema":"bmasia.agent-report.v1","event_id":str(uuid.uuid4()),"reporter":"lyra","observed_at":NOW.isoformat(),"record":rec,"changes":[{"field":"title","before":"Old","after":"New"}],"evidence":[{"kind":"email_message","reference":"msg-1","sha256":"a"*64}],"follow_up":None}
    report.update(over)
    ctx = {"schema":"bmasia.agent-shadow-context.v1","sender":report["reporter"],"request_id":"r1","report_sha256":canonical_hash(report),"verified_evidence_sha256":["a"*64],"verified":True,"environment":"shadow"}
    snap = {"collection":rec["collection"],"id":rec["id"],"observed_at":NOW.isoformat(),"updated_at":(NOW-dt.timedelta(hours=1)).isoformat(),"fields":{"title":"Old"}}
    return report, ctx, snap


class CoreTests(unittest.TestCase):
    def test_validation_and_hash(self):
        r, _, _ = sample(); self.assertEqual(canonical_hash(r), canonical_hash(dict(r)))
        validate_report(r); r["extra"] = 1
        with self.assertRaises(ValueError): validate_report(r)

    def test_source_and_binding_failures(self):
        r,c,s=sample(); c["verified"] = False
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"], "needs_source_verification")
        r,c,s=sample(); c["sender"]="theo"
        with self.assertRaises(ValueError): assess_report(r,c,s,NOW)
        r,c,s=sample(); c["report_sha256"]="0"*64
        with self.assertRaises(ValueError): assess_report(r,c,s,NOW)

    def test_policy_conflict_no_change_and_stale(self):
        r,c,s=sample(); r["changes"][0]["field"]="contract"; c["report_sha256"]=canonical_hash(r)
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"], "manual_review")
        r,c,s=sample(); s["fields"]["title"]="Other"
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"], "conflict")
        r,c,s=sample(); r["changes"][0]["after"]="Old"; c["report_sha256"]=canonical_hash(r)
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"], "no_change")
        r,c,s=sample(); s["observed_at"]=(NOW-dt.timedelta(hours=25)).isoformat()
        with self.assertRaises(ValueError): assess_report(r,c,s,NOW)

    def test_ledger_replay_collision_semantic_and_overdue(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=ShadowLedger(os.path.join(tmp,"shadow.sqlite")); r,c,s=sample(follow_up={"owner":"lyra","due_at":(NOW-dt.timedelta(days=1)).isoformat(),"reason":"call back"})
            one=ledger.ingest(r,c,s,NOW); self.assertEqual(one["mode"],"shadow"); self.assertEqual(one["crm_writes"],0)
            self.assertTrue(ledger.ingest(r,c,s,NOW)["replay"])
            bad=dict(r); bad["changes"]=[{"field":"title","before":"Old","after":"Else"}]; cb=dict(c); cb["report_sha256"]=canonical_hash(bad)
            self.assertEqual(ledger.ingest(bad,cb,s,NOW)["outcome"], "conflict")
            two=dict(r); two["event_id"]=str(uuid.uuid4()); cc=dict(c); cc["report_sha256"]=canonical_hash(two)
            self.assertEqual(ledger.ingest(two,cc,s,NOW)["outcome"],"duplicate")
            summary=ledger.report(NOW); self.assertEqual(summary["overdue_followups"],1); self.assertFalse(summary["no_data"])

    def test_concurrent_single_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=ShadowLedger(os.path.join(tmp,"shadow.sqlite")); r,c,s=sample(); out=[]
            def go(): out.append(ledger.ingest(r,c,s,NOW))
            threads=[threading.Thread(target=go) for _ in range(2)]
            [x.start() for x in threads]; [x.join() for x in threads]
            self.assertEqual(len(out),2); self.assertEqual(sum(x["replay"] for x in out),1)

    def test_retry_ignores_later_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=ShadowLedger(os.path.join(tmp,"shadow.sqlite")); r,c,s=sample(); ledger.ingest(r,c,s,NOW)
            later=NOW+dt.timedelta(days=2)
            self.assertTrue(ledger.ingest(r,c,s,later)["replay"])

    def test_environment_mixing_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=ShadowLedger(os.path.join(tmp,"shadow.sqlite")); r,c,s=sample(); ledger.ingest(r,c,s,NOW)
            r,c,s=sample(); c["environment"]="synthetic"; c["report_sha256"]=canonical_hash(r)
            with self.assertRaises(ValueError): ledger.ingest(r,c,s,NOW)

    def test_missing_snapshot_field_is_conflict(self):
        r,c,s=sample(); s["fields"]={}
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"],"conflict")

    def test_followup_with_no_change_is_reviewable(self):
        r,c,s=sample(follow_up={"owner":"lyra","due_at":NOW.isoformat(),"reason":"review"}); r["changes"][0]["after"]="Old"; c["report_sha256"]=canonical_hash(r)
        self.assertEqual(assess_report(r,c,s,NOW)["outcome"],"ready_for_cira_review")

    def test_private_parent_and_foreign_db_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            foreign=os.path.join(tmp,"foreign.sqlite")
            import sqlite3; db=sqlite3.connect(foreign); db.execute("create table customer_data (x text)"); db.close()
            with self.assertRaises(ValueError): ShadowLedger(foreign)
            os.chmod(tmp,0o755)
            with self.assertRaises(ValueError): ShadowLedger(os.path.join(tmp,"private.sqlite"))

    def test_record_can_be_older_than_snapshot_observation(self):
        report, context, snapshot = sample()
        snapshot["updated_at"] = (NOW - dt.timedelta(days=30)).isoformat()
        self.assertEqual(assess_report(report, context, snapshot, NOW)["outcome"], "ready_for_cira_review")
        snapshot["updated_at"] = NOW.isoformat()
        snapshot["observed_at"] = (NOW - dt.timedelta(minutes=30)).isoformat()
        with self.assertRaisesRegex(ValueError, "later than"):
            assess_report(report, context, snapshot, NOW)

    def test_future_report_rejected_and_old_report_requires_review(self):
        for hours, expected in ((1, None), (-25, "manual_review")):
            report, context, snapshot = sample(observed_at=(NOW + dt.timedelta(hours=hours)).isoformat())
            if expected:
                self.assertEqual(assess_report(report, context, snapshot, NOW)["outcome"], expected)
            else:
                with self.assertRaises(ValueError):
                    assess_report(report, context, snapshot, NOW)

    def test_collision_retry_has_one_permanent_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            original = ledger.ingest(report, context, snapshot, NOW)
            report["changes"][0]["after"] = "Different"
            context["report_sha256"] = canonical_hash(report)
            collision = ledger.ingest(report, context, snapshot, NOW)
            retry = ledger.ingest(report, context, {}, NOW + dt.timedelta(days=2))
            self.assertEqual(collision["receipt_id"], retry["receipt_id"])
            self.assertTrue(retry["replay"])
            self.assertEqual(collision["original_receipt_id"], original["receipt_id"])
            self.assertEqual(ledger.report(NOW)["collision_attempts"], 1)
            self.assertEqual(ledger.report(NOW)["total_events"], 1)

    def test_missing_verification_not_hidden_by_semantic_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            ledger.ingest(report, context, snapshot, NOW)
            report["event_id"] = str(uuid.uuid4())
            context["report_sha256"] = canonical_hash(report)
            context["verified_evidence_sha256"] = []
            result = ledger.ingest(report, context, snapshot, NOW)
            self.assertEqual(result["outcome"], "needs_source_verification")
            self.assertFalse(result["source_verification"])

    def test_changed_snapshot_not_hidden_by_semantic_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            ledger.ingest(report, context, snapshot, NOW)
            report["event_id"] = str(uuid.uuid4())
            context["report_sha256"] = canonical_hash(report)
            snapshot["fields"]["title"] = "Human correction"
            self.assertEqual(ledger.ingest(report, context, snapshot, NOW)["outcome"], "conflict")

    def test_conflicting_proposal_is_not_applied_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            ledger.ingest(report, context, snapshot, NOW)
            report["event_id"] = str(uuid.uuid4())
            report["changes"][0]["after"] = "Alternative"
            context["report_sha256"] = canonical_hash(report)
            result = ledger.ingest(report, context, snapshot, NOW)
            self.assertEqual(result["outcome"], "conflict")
            self.assertEqual(result["crm_writes"], 0)
            self.assertFalse(result["model_invoked"])

    def test_no_data_and_private_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shadow.sqlite")
            ledger = ShadowLedger(path)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            summary = ledger.report(NOW)
            self.assertTrue(summary["no_data"])
            self.assertIsNone(summary["healthy"])
            self.assertEqual(set(summary["agents"]), {"theo", "lyra", "riff", "nina"})
            link = os.path.join(tmp, "link.sqlite")
            os.symlink(path, link)
            with self.assertRaisesRegex(ValueError, "symlink"):
                ShadowLedger(link)

    def test_snapshot_must_be_at_least_as_recent_as_report(self):
        report, context, snapshot = sample()
        snapshot["observed_at"] = (NOW - dt.timedelta(minutes=30)).isoformat()
        with self.assertRaisesRegex(ValueError, "predates"):
            assess_report(report, context, snapshot, NOW)

    def test_readout_distinguishes_null_missing_and_conflicting_current(self):
        report, context, snapshot = sample()
        for fields, present, current in (({}, False, None), ({"title": None}, True, None),
                                          ({"title": "Human correction"}, True, "Human correction")):
            snapshot["fields"] = fields
            result = assess_report(report, context, snapshot, NOW)
            self.assertEqual(result["outcome"], "conflict")
            self.assertEqual(result["field_changes"][0]["current_present"], present)
            self.assertEqual(result["field_changes"][0]["current"], current)

    def test_verified_replay_cannot_hide_downgraded_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            original = ledger.ingest(report, context, snapshot, NOW)
            context.update(verified=False, verified_evidence_sha256=[], request_id="retry")
            result = ledger.ingest(report, context, {}, NOW)
            self.assertEqual(result["outcome"], "needs_source_verification")
            self.assertFalse(result["source_verification"])
            self.assertEqual(result["original_receipt_id"], original["receipt_id"])
            self.assertEqual(ledger.ingest(report, context, {}, NOW)["receipt_id"], result["receipt_id"])
            self.assertEqual(ledger.report(NOW)["exception_attempts"], 1)

    def test_verification_upgrade_requires_deliberate_new_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ShadowLedger(os.path.join(tmp, "shadow.sqlite"))
            report, context, snapshot = sample()
            context["verified"] = False
            original = ledger.ingest(report, context, snapshot, NOW)
            context["verified"] = True
            self.assertEqual(ledger.ingest(report, context, {}, NOW)["outcome"], "needs_source_verification")
            report["event_id"] = str(uuid.uuid4())
            context["report_sha256"] = canonical_hash(report)
            self.assertEqual(ledger.ingest(report, context, snapshot, NOW)["outcome"], "ready_for_cira_review")

    def test_collision_keeps_attempted_report_and_context(self):
        import json
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shadow.sqlite")
            ledger = ShadowLedger(path)
            report, context, snapshot = sample()
            ledger.ingest(report, context, snapshot, NOW)
            report["changes"][0]["after"] = "Alternative"
            context["report_sha256"] = canonical_hash(report)
            ledger.ingest(report, context, snapshot, NOW)
            with sqlite3.connect(path) as db:
                raw_report, raw_context = db.execute("SELECT report_json,context_json FROM shadow_attempts").fetchone()
            self.assertEqual(json.loads(raw_report), report)
            self.assertEqual(json.loads(raw_context), context)


def _invalid_case(name, edit):
    def test(self):
        report, _, _ = sample(); edit(report)
        with self.assertRaises(ValueError): validate_report(report)
    test.__name__ = name
    return test


for _name, _edit in {
    "test_bad_schema": lambda r: r.__setitem__("schema", "bad"),
    "test_bad_event_uuid": lambda r: r.__setitem__("event_id", "bad"),
    "test_naive_observed": lambda r: r.__setitem__("observed_at", "2026-01-01T00:00:00"),
    "test_unknown_collection": lambda r: r["record"].__setitem__("collection", "users"),
    "test_too_many_changes": lambda r: r.__setitem__("changes", r["changes"] * 21),
    "test_empty_evidence": lambda r: r.__setitem__("evidence", []),
    "test_bad_field": lambda r: r["changes"][0].__setitem__("field", "Bad Field"),
    "test_duplicate_field": lambda r: r.__setitem__("changes", r["changes"] * 2),
    "test_nested_value": lambda r: r["changes"][0].__setitem__("after", {}),
    "test_bad_evidence_kind": lambda r: r["evidence"][0].__setitem__("kind", "raw_mail"),
    "test_bad_evidence_hash": lambda r: r["evidence"][0].__setitem__("sha256", "z" * 64),
    "test_no_action": lambda r: (r.__setitem__("changes", []), r.__setitem__("follow_up", None)),
    "test_bad_followup_owner": lambda r: r.__setitem__("follow_up", {"owner":"cira","due_at":NOW.isoformat(),"reason":"x"}),
    "test_bad_followup_reason": lambda r: r.__setitem__("follow_up", {"owner":"lyra","due_at":NOW.isoformat(),"reason":""}),
    "test_unknown_report_key": lambda r: r.__setitem__("unexpected", True),
    "test_unhashable_reporter": lambda r: r.__setitem__("reporter", {}),
    "test_unhashable_collection": lambda r: r["record"].__setitem__("collection", []),
    "test_unhashable_evidence_kind": lambda r: r["evidence"][0].__setitem__("kind", {}),
}.items():
    setattr(CoreTests, _name, _invalid_case(_name, _edit))
