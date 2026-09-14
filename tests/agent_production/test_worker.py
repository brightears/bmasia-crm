import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('worker', ROOT / 'tools/agent_crm_production_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
core = worker.core


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = core.Ledger(self.tmp.name)
        self.doc = {'schema': 'bmasia.agent-correction.v1', 'source': 'lyra',
                    'event_id': '00000000-0000-4000-8000-000000000001',
                    'observed_at': core.now().isoformat(), 'company_id': '00000000-0000-4000-8000-000000000002',
                    'record': {'collection': 'contact', 'id': '00000000-0000-4000-8000-000000000003'},
                    'expected_version': '2026-09-14T00:00:00Z',
                    'changes': {'title': {'before': 'Coordinator', 'after': 'Manager'}},
                    'evidence': [{'kind': 'agent_receipt', 'reference': 'fixture:independently-verified', 'sha256': 'a'*64}],
                    'reason': 'Fixture test only'}
        self.snapshot = {'id': self.doc['record']['id'], 'company': self.doc['company_id'],
                         'updated_at': '2026-09-14T00:00:00+00:00', 'title': 'Coordinator'}

    def state(self):
        with self.ledger.connect() as db:
            return db.execute('SELECT state,reason FROM corrections').fetchone()

    def test_exact_fresh_preconditions_send_and_readback(self):
        self.ledger.submit(self.doc, 1000)
        calls = []
        reads = iter([self.snapshot, {**self.snapshot, 'title': 'Manager'}])
        def sender(payload):
            calls.append(payload)
            return {'ok': True}
        worker.process_one(self.ledger, lambda _: next(reads), sender)
        self.assertEqual(self.state()['state'], 'VERIFIED')
        self.assertEqual(calls[0]['expected_values'], {'title': 'Coordinator'})
        self.assertTrue(calls[0]['correction_intent']['independent_evidence_validation_required'])
        self.assertEqual(calls[0]['correction_intent']['transport'], 'kernel_peer_uid')
        self.assertFalse(worker.process_one(self.ledger, lambda _: self.fail(), sender))

    def test_already_current_never_calls_cira(self):
        self.ledger.submit(self.doc, 1000)
        worker.process_one(self.ledger, lambda _: {**self.snapshot, 'title': 'Manager'}, lambda _: self.fail())
        self.assertEqual(self.state()['state'], 'ALREADY_CURRENT')

    def test_stale_wrong_company_and_before_mismatch_never_send(self):
        for key, value in [('company', '00000000-0000-4000-8000-000000000009'),
                           ('updated_at', '2026-09-14T00:00:01Z'), ('title', 'Director')]:
            self.assertEqual(worker.evaluate(self.doc, {**self.snapshot, key: value})[0], 'HOLD')

    def test_cira_success_without_readback_is_not_success(self):
        self.ledger.submit(self.doc, 1000)
        worker.process_one(self.ledger, lambda _: self.snapshot, lambda _: {'ok': True})
        self.assertEqual(self.state()['state'], 'HOLD')
        self.assertEqual(self.state()['reason'], 'cira_readback_mismatch')

    def test_unconfirmed_response_is_held_not_retried(self):
        self.ledger.submit(self.doc, 1000)
        worker.process_one(self.ledger, lambda _: self.snapshot, lambda _: {'waiting': True})
        self.assertEqual(self.state()['state'], 'HOLD')
        self.assertFalse(worker.process_one(self.ledger, lambda _: self.fail(), lambda _: self.fail()))

    def test_conflict_while_reading_never_sends(self):
        self.ledger.submit(self.doc, 1000)
        def read(_):
            other = copy.deepcopy(self.doc)
            other['event_id'] = '00000000-0000-4000-8000-000000000004'
            self.ledger.submit(other, 1000)
            return self.snapshot
        worker.process_one(self.ledger, read, lambda _: self.fail())
        self.assertEqual(self.state()['state'], 'HOLD')


if __name__ == '__main__':
    unittest.main()
