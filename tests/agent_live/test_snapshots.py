import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import agent_crm_pilot_snapshots as subject

COMPANY = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
RECORD = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'


def page(rows):
    return SimpleNamespace(isError=False, content=[SimpleNamespace(type='text', text=json.dumps(rows))])


class SnapshotTests(unittest.TestCase):
    def test_pipeline_exact_id_projection_and_two_row_duplicate_detection(self):
        value = subject.pipeline(RECORD, ['id', 'company', 'stage'])
        self.assertEqual(value[0], {'$match': {'id': RECORD}})
        self.assertEqual(value[2], {'$limit': 2})
        with self.assertRaises(ValueError):
            subject.pipeline(RECORD, ['email'])
        with self.assertRaises(ValueError):
            subject.pipeline('not-uuid', ['id'])

    def test_parse_bounds_identity_and_absent_null_distinction(self):
        row = subject.parse_page(page([{'id': RECORD, 'stage': None}]), RECORD, ['id', 'stage', 'follow_up_date'])
        self.assertIsNone(row['stage'])
        self.assertNotIn('follow_up_date', row)
        for rows in ([{'id': COMPANY}], [{'id': RECORD}, {'id': RECORD}],
                     [{'id': RECORD, 'email': 'private'}], [{'id': RECORD, 'stage': {}}]):
            with self.assertRaises(ValueError):
                subject.parse_page(page(rows), RECORD, ['id', 'stage'])
        self.assertIsNone(subject.parse_page(page([]), RECORD, ['id']))

    def test_json_duplicate_nonfinite_and_oversize_rejected(self):
        for raw in ('{"a":1,"a":2}', '[NaN]', ' ' * 65537):
            with self.assertRaises(ValueError):
                subject.decode(raw)

    def test_only_fixed_read_tool_called_for_validated_flat_scope(self):
        calls = []
        class Session:
            async def call_tool(self, name, arguments):
                calls.append((name, arguments))
                if arguments['collection'] == 'company':
                    return page([{'id': COMPANY, 'name': 'Pilot', 'updated_at': '2026-09-01T00:00:00Z'}])
                return page([{'id': RECORD, 'company': COMPANY, 'updated_at': '2026-09-01T00:00:00Z', 'stage': 'Quotation Sent'}])
        scope = {'scope_id': COMPANY, 'accounts': [{'company_id': COMPANY, 'collection': 'opportunities', 'record_id': RECORD}]}
        result = asyncio.run(subject.collect(Session(), scope))
        self.assertEqual(len(calls), 2)
        self.assertEqual({name for name, _ in calls}, {'query_data_collections'})
        self.assertEqual(result['records'][0]['status'], 'ok')
        self.assertNotIn('follow_up_date', result['records'][0]['fields'])
        self.assertEqual(result['crm_writes'], 0)
        self.assertFalse(result['customer_outbound'])

    def test_errors_are_bounded_redacted_rows(self):
        class Session:
            async def call_tool(self, *_args):
                raise RuntimeError('private token and body must not escape')
        scope = {'scope_id': COMPANY, 'accounts': [{'company_id': COMPANY, 'collection': 'contacts', 'record_id': RECORD}]}
        result = asyncio.run(subject.collect(Session(), scope))
        self.assertEqual(result['records'][0]['status'], 'error')
        self.assertNotIn('private', json.dumps(result))

    def test_wrong_company_and_missing_version_are_not_ok(self):
        for change in ({'company': RECORD}, {'updated_at': None}):
            class Session:
                async def call_tool(self, name, arguments):
                    if arguments['collection'] == 'company':
                        return page([{'id': COMPANY, 'name': 'Pilot'}])
                    return page([{'id': RECORD, 'company': COMPANY,
                                  'updated_at': '2026-09-01T00:00:00Z', **change}])
            account = {'company_id': COMPANY, 'collection': 'contacts', 'record_id': RECORD}
            scope = {'scope_id': COMPANY, 'accounts': [account, account]}
            result = asyncio.run(subject.collect(Session(), scope))
            self.assertEqual(len(result['records']), 1)
            self.assertEqual(result['records'][0]['status'], 'error')


if __name__ == '__main__':
    unittest.main()
