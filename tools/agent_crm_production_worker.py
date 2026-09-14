#!/usr/bin/env python3
"""Vera outbox worker: exact read/preconditions -> Cira -> exact readback.

Only Cira can mutate CRM. A queue acceptance or Cira's prose is never success.
Evidence hashes authenticate neither truth nor business authority. Cira must
independently resolve evidence and may hold the request for owner clarification.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time

spec = importlib.util.spec_from_file_location('production', Path(__file__).with_name('agent_crm_production.py'))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
ENDPOINT = 'https://bmasia-crm.onrender.com/mcp/'
HELPER = '/home/bmasia/agent-comms/cira-request.py'


def equal(left, right):
    return type(left) is type(right) and left == right


def evaluate(document, snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('id') != document['record']['id'] or snapshot.get('company') != document['company_id']:
        return 'HOLD', 'crm_identity_unverified'
    changes = document['changes']
    if all(field in snapshot and equal(snapshot[field], item['after']) for field, item in changes.items()):
        return 'ALREADY_CURRENT', 'persisted_values_already_current'
    try:
        if core.instant(snapshot.get('updated_at')) != core.instant(document['expected_version']):
            return 'HOLD', 'stale_crm_version'
    except (ValueError, TypeError):
        return 'HOLD', 'crm_version_unverified'
    if any(field not in snapshot or not equal(snapshot[field], item['before']) for field, item in changes.items()):
        return 'HOLD', 'before_value_mismatch'
    return 'READY', 'fresh_bound_preconditions'


async def snapshot(document):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def guard(request):
        if str(request.url) != ENDPOINT or request.method not in {'POST', 'GET'}:
            raise ValueError('transport_outside_read_endpoint')
    def factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth, follow_redirects=False,
                                 trust_env=False, event_hooks={'request': [guard]})
    authorization = os.environ.get('BMASIA_CRM_AUTHORIZATION')
    if not authorization:
        raise ValueError('read_authorization_unavailable')
    async with streamablehttp_client(ENDPOINT, headers={'Authorization': authorization}, timeout=20,
                                    sse_read_timeout=25, terminate_on_close=False, httpx_client_factory=factory) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            async def query(collection, record_id, fields):
                core.identifier(record_id)
                response = await session.call_tool('query_data_collections', {
                    'collection': collection,
                    'search_pipeline': [{'$match': {'id': record_id}}, {'$sort': {'id': 1}}, {'$limit': 2},
                                        {'$project': {'_id': 0, **{key: 1 for key in fields}}}]})
                if response.isError or len(response.content) != 1 or response.content[0].type != 'text':
                    raise ValueError('invalid_crm_response')
                rows = core.decode(response.content[0].text)
                if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('id') != record_id:
                    raise ValueError('exact_crm_record_missing')
                row = rows[0]
                if set(row) - set(fields):
                    raise ValueError('unexpected_crm_fields')
                for value in row.values():
                    core.scalar(value)
                return row
            await query('company', document['company_id'], ('id',))
            return await query(document['record']['collection'], document['record']['id'],
                               ('id', 'company', 'updated_at', *document['changes']))


def cira_payload(document, checksum, peer_uid):
    return {
        'from': 'vera', 'verb': 'update', 'collection': document['record']['collection'],
        'id': document['record']['id'], 'request_key': 'vera:correction:' + checksum,
        'patch': {key: value['after'] for key, value in document['changes'].items()},
        'expected_version': document['expected_version'],
        'expected_values': {key: value['before'] for key, value in document['changes'].items()},
        'correction_intent': {
            'incident_id': document['source'] + ':' + document['event_id'],
            'reason': document['reason'],
            'evidence': [json.dumps(item, sort_keys=True) for item in document['evidence']],
            'company_id': document['company_id'], 'original_source': document['source'],
            'observed_at': document['observed_at'], 'report_sha256': checksum,
            'peer_uid': peer_uid,
            'transport': 'operator_import' if peer_uid == core.OPERATOR_UID else 'kernel_peer_uid',
            'independent_evidence_validation_required': True,
            'guarded_update_required': True,
        },
    }


def submit_cira(payload):
    # Do not forward Vera's CRM credential into a child which does not need it.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/home/vera_ai', 'CIRA_TIMEOUT_SEC': '600'}
    response = subprocess.run(['/usr/bin/python3', '-I', '-B', HELPER], input=core.encode(payload),
                              capture_output=True, timeout=640, env=env, check=False)
    if response.returncode != 0 or len(response.stdout) > 65536:
        raise ValueError('cira_transport_uncertain')
    result = core.decode(response.stdout)
    if not isinstance(result, dict):
        raise ValueError('cira_response_invalid')
    return result


def claim(ledger):
    clock = core.now()
    with ledger.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        # No automatic retry of uncertain writes. Read-back/reconciliation is
        # safe; replaying an LLM write after a transport failure is not required.
        db.execute("UPDATE corrections SET state='HOLD',reason='worker_interrupted_reconcile_required',updated_at=? WHERE state='PROCESSING' AND updated_at<?",
                   (clock.isoformat(), (clock - timedelta(minutes=30)).isoformat()))
        row = db.execute("SELECT * FROM corrections WHERE state='PENDING' ORDER BY created_at LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE corrections SET state='PROCESSING',attempts=attempts+1,updated_at=? WHERE source=? AND event_id=?", (clock.isoformat(), row['source'], row['event_id']))
            return dict(row)


def finish(ledger, row, state, reason):
    with ledger.connect() as db:
        db.execute('UPDATE corrections SET state=?,reason=?,updated_at=? WHERE source=? AND event_id=? AND state=?',
                   (state, reason, core.now().isoformat(), row['source'], row['event_id'], 'PROCESSING'))


def process_one(ledger, reader=None, sender=submit_cira):
    row = claim(ledger)
    if not row:
        return False
    document = core.decode(row['payload'])
    try:
        core.validate_correction(document, row['peer_uid'], core.now())
        read = reader or (lambda doc: asyncio.run(snapshot(doc)))
        current = read(document)
        state, reason = evaluate(document, current)
        if state != 'READY':
            finish(ledger, row, state, reason)
            return True
        # A conflict may arrive while the network read is outstanding.
        with ledger.connect() as db:
            conflicts = db.execute("SELECT count(*) FROM corrections WHERE record_id=? AND event_id!=? AND state IN ('PENDING','PROCESSING','HOLD') AND created_at>=?",
                                   (row['record_id'], row['event_id'], row['created_at'])).fetchone()[0]
        if conflicts:
            finish(ledger, row, 'HOLD', 'concurrent_source_conflict')
            return True
        result = sender(cira_payload(document, row['hash'], row['peer_uid']))
        if result.get('ok') is not True:
            finish(ledger, row, 'HOLD', 'cira_rejected_or_unconfirmed')
            return True
        after = read(document)
        state, reason = evaluate(document, after)
        if state == 'ALREADY_CURRENT':
            finish(ledger, row, 'VERIFIED', 'cira_success_and_exact_readback')
        else:
            finish(ledger, row, 'HOLD', 'cira_readback_mismatch')
    except Exception:
        # Provider/header/payload exceptions must not enter logs or receipts.
        finish(ledger, row, 'HOLD', 'transport_or_validation_unconfirmed')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    ledger = core.Ledger(core.STATE)
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    while running:
        worked = process_one(ledger)
        if args.once:
            return 0
        # At most one new Cira correction per minute; empty polling is free.
        for _ in range(60 if worked else 15):
            if not running:
                break
            time.sleep(1)


if __name__ == '__main__':
    raise SystemExit(main())
