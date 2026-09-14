#!/usr/bin/env python3
"""Private production activity intake and explicit Cira correction outbox.

No CRM credentials, HTTP, model, or direct business writes. Unix credentials
authenticate an account, not factual truth. Exports are observations only.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import sqlite3
import stat
import struct
import sys
import time
import uuid

SOURCES = {'theo', 'lyra', 'riff', 'nina', 'cara', 'bmasia_sales'}
UIDS = {1008: 'theo', 1000: 'lyra', 1007: 'riff', 1004: 'nina'}
ACCOUNTS = {1008: 'theo_ai', 1000: 'bmasia', 1007: 'riff_ai', 1004: 'nina', 1010: 'vera_ai'}
OPERATOR_UID = 1010
SOCKET = '/run/bmasia-agent-production/collector.sock'
STATE = '/opt/vera-hermes/data/runtime/agent-production'
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
FIELDS = {
    'theo': {'contact': {'title', 'department', 'last_contacted'},
             'opportunity': {'stage', 'last_contact_date', 'follow_up_date', 'expected_close_date', 'pain_points', 'decision_criteria'}},
    'lyra': {'contact': {'title', 'department', 'last_contacted'}},
    'riff': {'ticket': {'priority', 'status'}},
    'nina': {'zone': {'notes'}},
    'cara': {'contact': {'title', 'department', 'last_contacted'}},
    'bmasia_sales': {'opportunity': {'stage', 'last_contact_date', 'follow_up_date', 'expected_close_date', 'pain_points', 'decision_criteria'}},
}
COLLECTIONS = {'company', 'contact', 'opportunity', 'ticket', 'zone'}
FATAL_HOLDS = {'SOURCE_COLLECTION_FAILED', 'SOURCE_CONFLICT', 'SOURCE_FUTURE', 'SOURCE_INCOMPLETE',
               'SOURCE_INVALID', 'SOURCE_MISSING', 'SOURCE_PATH_REJECTED', 'SOURCE_RESULT_LIMIT', 'SOURCE_SCHEMA_UNSUPPORTED', 'SOURCE_STALE'}
FACTS = {
    'cara': {'collection_state', 'primary_contact_id', 'assessment_decision', 'account_blocker_count',
             'crm_hold_count', 'packet_blocker_count', 'uncovered_sender_count'},
    'bmasia_sales': {'stage', 'last_contact_date', 'follow_up_date', 'is_active', 'unsubscribed', 'updated_at'},
    'theo': {'state', 'revision', 'source_complete', 'agent_inventory_complete', 'legacy_baseline_complete'},
    'lyra': {'state', 'revision', 'source_complete', 'agent_inventory_complete', 'legacy_baseline_complete'},
    'riff': {'queue_state', 'source_complete', 'agent_inventory_complete', 'legacy_baseline_complete'},
    'nina': {'source_complete', 'agent_inventory_complete', 'legacy_baseline_complete'},
}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('size_limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))


def now():
    return datetime.now(timezone.utc)


def instant(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('invalid_timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('naive_timestamp')
    return result


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('schema_keys')


def identifier(value):
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError('invalid_uuid')


def text_value(value, maximum=200):
    if not isinstance(value, str) or not 0 < len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid_text')


def scalar(value):
    if value is not None and type(value) not in (str, int, float, bool):
        raise ValueError('scalar_required')
    if isinstance(value, str) and len(value) > 2000:
        raise ValueError('scalar_too_long')
    encode(value)


def authorized(source, uid):
    if source not in SOURCES or not (UIDS.get(uid) == source or uid == OPERATOR_UID):
        raise ValueError('source_uid_mismatch')


def validate_export(document, uid, clock):
    required = {'schema', 'source', 'source_authentication', 'exported_at', 'source_observed_at',
                'coverage', 'records', 'export_sha256'}
    exact(document, required)
    if document['schema'] != 'bmasia.agent-production-export.v1':
        raise ValueError('invalid_export_schema')
    authorized(document['source'], uid)
    # Producer claim is retained as metadata only. Actual auth is recorded below.
    text_value(document['source_authentication'])
    if abs((clock - instant(document['exported_at'])).total_seconds()) > 7200:
        raise ValueError('export_outside_import_window')
    if document['source_observed_at'] is not None and instant(document['source_observed_at']) > clock + timedelta(minutes=5):
        raise ValueError('source_future')
    coverage = document['coverage']
    if not isinstance(coverage, dict) or set(coverage) - {'total', 'exported', 'complete', 'unbound', 'failed', 'agent_inventory_complete', 'legacy_baseline_complete'}:
        raise ValueError('invalid_coverage')
    for key in ('total', 'exported', 'unbound', 'failed'):
        if type(coverage.get(key)) is not int or not 0 <= coverage[key] <= MAX_ROWS:
            raise ValueError('invalid_coverage_count')
    if type(coverage.get('complete')) is not bool:
        raise ValueError('invalid_coverage_complete')
    for key in ('agent_inventory_complete', 'legacy_baseline_complete'):
        if key in coverage and type(coverage[key]) is not bool:
            raise ValueError('invalid_inventory_complete')
    rows = document['records']
    if not isinstance(rows, list) or len(rows) > MAX_ROWS or coverage['total'] != len(rows):
        raise ValueError('invalid_rows')
    if coverage['exported'] + coverage['unbound'] + coverage['failed'] != len(rows):
        raise ValueError('coverage_not_partition')
    seen = set()
    observed = []
    failed = unbound = 0
    for row in rows:
        exact(row, {'source_key', 'company_ids', 'record', 'observed_at', 'version_hash', 'facts', 'holds', 'follow_ups'})
        text_value(row['source_key'])
        if row['source_key'] in seen:
            raise ValueError('duplicate_source_key')
        seen.add(row['source_key'])
        if not isinstance(row['company_ids'], list) or len(row['company_ids']) > 100:
            raise ValueError('invalid_companies')
        for company in row['company_ids']:
            identifier(company)
        if row['record'] is not None:
            exact(row['record'], {'collection', 'id'})
            # Historical exporters use plural collection names.
            if row['record']['collection'] not in COLLECTIONS | {'companies', 'contacts', 'opportunities', 'tickets', 'zones'}:
                raise ValueError('invalid_collection')
            identifier(row['record']['id'])
            if not row['company_ids']:
                raise ValueError('bound_record_requires_company')
        if row['observed_at'] is not None:
            timestamp = instant(row['observed_at'])
            if timestamp > clock + timedelta(minutes=5):
                raise ValueError('row_future')
            observed.append(timestamp)
        if row['version_hash'] is not None and not re.fullmatch('[0-9a-fA-F]{64}', row['version_hash']):
            raise ValueError('invalid_version_hash')
        if not isinstance(row['facts'], dict) or set(row['facts']) - FACTS[document['source']]:
            raise ValueError('invalid_facts')
        for key, value in row['facts'].items():
            text_value(key, 80)
            scalar(value)
            if isinstance(value, str):
                text_value(value, 200)
        if not isinstance(row['holds'], list) or len(row['holds']) > 30:
            raise ValueError('invalid_holds')
        for hold in row['holds']:
            if not isinstance(hold, str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,79}', hold):
                raise ValueError('invalid_hold')
        if FATAL_HOLDS.intersection(row['holds']):
            failed += 1
        elif row['record'] is None:
            unbound += 1
        if not isinstance(row['follow_ups'], list) or len(row['follow_ups']) > 100:
            raise ValueError('invalid_followups')
        if row['follow_ups'] and document['source'] != 'cara':
            raise ValueError('source_followups_not_supported')
        for followup in row['follow_ups']:
            exact(followup, {'case_id', 'state', 'due_at', 'owner'})
            for key, value in followup.items():
                text_value(key, 80)
                scalar(value)
                if isinstance(value, str):
                    text_value(value, 120)
            if followup['due_at'] is not None:
                instant(followup['due_at'])
    envelope_observed = instant(document['source_observed_at']) if document['source_observed_at'] else None
    if envelope_observed != (max(observed) if observed else None):
        raise ValueError('source_observed_at_not_row_max')
    if coverage['failed'] != failed or coverage['unbound'] != unbound or coverage['exported'] != len(rows) - failed - unbound:
        raise ValueError('coverage_not_row_partition')
    if digest({k: v for k, v in document.items() if k not in {'exported_at', 'export_sha256'}}) != document['export_sha256']:
        raise ValueError('export_hash_mismatch')


def validate_correction(document, uid, clock):
    exact(document, {'schema', 'source', 'event_id', 'observed_at', 'company_id', 'record',
                     'expected_version', 'changes', 'evidence', 'reason'})
    if document['schema'] != 'bmasia.agent-correction.v1':
        raise ValueError('invalid_correction_schema')
    authorized(document['source'], uid)
    identifier(document['event_id'])
    identifier(document['company_id'])
    observed = instant(document['observed_at'])
    if observed > clock + timedelta(minutes=5) or observed < clock - timedelta(hours=72):
        raise ValueError('correction_stale_or_future')
    instant(document['expected_version'])
    exact(document['record'], {'collection', 'id'})
    identifier(document['record']['id'])
    allowed = FIELDS[document['source']].get(document['record']['collection'], set())
    changes = document['changes']
    if not isinstance(changes, dict) or not changes or set(changes) - allowed:
        raise ValueError('field_outside_source_authority')
    for field, change in changes.items():
        exact(change, {'before', 'after'})
        scalar(change['before'])
        scalar(change['after'])
        if field == 'stage' and change['after'] in {'Closed Won', 'Closed Lost', 'Won', 'Lost'}:
            raise ValueError('commercial_outcome_requires_owner_workflow')
        if field == 'status' and str(change['after']).lower() in {'closed', 'resolved'}:
            raise ValueError('ticket_closure_requires_owner_workflow')
    text_value(document['reason'], 500)
    evidence = document['evidence']
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 10:
        raise ValueError('evidence_required')
    for item in evidence:
        exact(item, {'kind', 'reference', 'sha256'})
        if item['kind'] not in {'email_message', 'ticket_event', 'agent_receipt', 'document'}:
            raise ValueError('invalid_evidence_kind')
        text_value(item['reference'])
        if not isinstance(item['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('invalid_evidence_hash')


class Ledger:
    def __init__(self, directory):
        directory = Path(directory)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('private_owned_state_required')
        self.path = directory / 'production.sqlite3'
        if self.path.is_symlink():
            raise ValueError('database_symlink')
        if not self.path.exists():
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600))
        info = self.path.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('private_owned_database_required')
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS sources(source TEXT PRIMARY KEY, received_at TEXT NOT NULL, peer_uid INTEGER NOT NULL, auth TEXT NOT NULL, export_hash TEXT NOT NULL, metadata TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS observations(source TEXT NOT NULL, source_key TEXT NOT NULL, row_json TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY(source,source_key));
              CREATE TABLE IF NOT EXISTS corrections(source TEXT NOT NULL,event_id TEXT NOT NULL,hash TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,peer_uid INTEGER NOT NULL, PRIMARY KEY(source,event_id));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def submit(self, document, uid, clock=None):
        clock = clock or now()
        if document.get('schema') == 'bmasia.agent-production-export.v1':
            validate_export(document, uid, clock)
            source = document['source']
            metadata = {k: v for k, v in document.items() if k != 'records'}
            with self.connect() as db:
                prior = db.execute('SELECT metadata FROM sources WHERE source=?', (source,)).fetchone()
                if prior:
                    old = json.loads(prior['metadata'])
                    if instant(old['exported_at']) > instant(document['exported_at']):
                        raise ValueError('older_export_replay')
                    if old['exported_at'] == document['exported_at'] and old['export_sha256'] != document['export_sha256']:
                        raise ValueError('same_time_export_conflict')
                    is_failure = document['coverage']['failed'] == len(document['records']) and bool(document['records'])
                    is_empty = not document['records'] and document['coverage']['complete']
                    if not is_failure and not is_empty and old['source_observed_at'] and (not document['source_observed_at'] or instant(old['source_observed_at']) > instant(document['source_observed_at'])):
                        raise ValueError('source_observation_regression')
                db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?)',
                           (source, clock.isoformat(), uid, 'operator_import' if uid == OPERATOR_UID else 'kernel_peer_uid', document['export_sha256'], encode(metadata).decode()))
                # Replace complete snapshots, retain historical rows on an incomplete read.
                if document['coverage']['complete'] and document['coverage']['failed'] == 0:
                    db.execute('DELETE FROM observations WHERE source=?', (source,))
                for row in document['records']:
                    db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?)',
                               (source, row['source_key'], encode(row).decode(), clock.isoformat()))
                db.execute('DELETE FROM observations WHERE last_seen < ?', ((clock - timedelta(days=30)).isoformat(),))
            return {'accepted': True, 'kind': 'observation_only', 'source': source,
                    'rows': len(document['records']), 'coverage': document['coverage'], 'crm_writes': 0}
        validate_correction(document, uid, clock)
        source, event_id, checksum = document['source'], document['event_id'], digest(document)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT hash,state FROM corrections WHERE source=? AND event_id=?', (source, event_id)).fetchone()
            if prior:
                if prior['hash'] != checksum:
                    raise ValueError('event_id_content_conflict')
                return {'accepted': True, 'replay': True, 'state': prior['state'], 'event_id': event_id}
            if db.execute("SELECT count(*) FROM corrections WHERE state IN ('PENDING','PROCESSING')").fetchone()[0] >= 1000:
                raise ValueError('outbox_backpressure')
            conflict = db.execute("SELECT 1 FROM corrections WHERE record_id=? AND state IN ('PENDING','PROCESSING')", (document['record']['id'],)).fetchone()
            state = 'HOLD' if conflict else 'PENDING'
            if conflict:
                db.execute("UPDATE corrections SET state='HOLD',reason='concurrent_source_conflict',updated_at=? WHERE record_id=? AND state='PENDING'", (clock.isoformat(), document['record']['id']))
            db.execute('INSERT INTO corrections VALUES (?,?,?,?,?,?,?,?,?,0,?)',
                       (source, event_id, checksum, document['record']['id'], encode(document).decode(), state,
                        'concurrent_source_conflict' if conflict else None, clock.isoformat(), clock.isoformat(), uid))
        return {'accepted': True, 'state': state, 'event_id': event_id, 'crm_writes': 0}

    def status(self, source=None, clock=None):
        clock = clock or now()
        with self.connect() as db:
            sources = {}
            for name in sorted({source} if source else SOURCES):
                row = db.execute('SELECT * FROM sources WHERE source=?', (name,)).fetchone()
                if not row:
                    sources[name] = {'transport': 'missing'}
                    continue
                metadata = json.loads(row['metadata'])
                age = (clock - instant(row['received_at'])).total_seconds()
                max_age = 10800 if name in {'cara', 'bmasia_sales'} else 900
                sources[name] = {'transport': 'fresh' if age <= max_age else 'stale',
                                 'received_at': row['received_at'], 'authentication': row['auth'],
                                 'source_observed_at': metadata['source_observed_at'], 'coverage': metadata['coverage'],
                                 'evidence_freshness': ('unknown' if not metadata['source_observed_at'] else
                                    'stale' if clock - instant(metadata['source_observed_at']) > timedelta(hours=24) else 'recent'),
                                 'stored_observations': db.execute('SELECT count(*) FROM observations WHERE source=?', (name,)).fetchone()[0]}
            counts = dict(db.execute('SELECT state,count(*) FROM corrections' + (' WHERE source=?' if source else '') + ' GROUP BY state', (source,) if source else ()).fetchall())
            holds = [dict(row) for row in db.execute("SELECT source,event_id,state,reason,updated_at FROM corrections WHERE state IN ('HOLD','PROCESSING')" + (' AND source=?' if source else '') + ' ORDER BY updated_at DESC LIMIT 50', (source,) if source else ())]
        return {'schema': 'bmasia.agent-production-status.v1', 'observed_at': clock.isoformat(),
                'sources': sources, 'corrections': counts, 'attention': holds,
                'exports_are_not_crm_updates': True, 'commercial_and_outbound_authority_unchanged': True}


def receive(connection):
    deadline = time.monotonic() + 10
    def read(length):
        result = bytearray()
        while len(result) < length:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('frame_timeout')
            connection.settimeout(remaining)
            chunk = connection.recv(min(65536, length - len(result)))
            if not chunk:
                raise ValueError('truncated_frame')
            result.extend(chunk)
        return bytes(result)
    length = struct.unpack('!I', read(4))[0]
    if not 0 < length <= MAX_BYTES:
        raise ValueError('frame_size')
    return decode(read(length))


def send(connection, document):
    raw = encode(document)
    if len(raw) > MAX_BYTES:
        raise ValueError('response_size')
    connection.sendall(struct.pack('!I', len(raw)) + raw)


def request(document, path=SOCKET):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(15)
        connection.connect(path)
        send(connection, document)
        return receive(connection)


def serve(state=STATE, path=SOCKET):
    for uid, account in ACCOUNTS.items():
        if pwd.getpwnam(account).pw_uid != uid:
            raise ValueError('account_uid_changed')
    ledger = Ledger(state)
    # RuntimeDirectory is owned by Vera; never unlink a non-socket or symlink.
    target = Path(path)
    if target.exists() or target.is_symlink():
        if not stat.S_ISSOCK(target.lstat().st_mode) or target.stat().st_uid != os.geteuid():
            raise ValueError('socket_path_unsafe')
        target.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(path)
        os.chmod(path, 0o660)
        server.listen(16)
        server.settimeout(1)
        running = True
        def stop(*_):
            nonlocal running
            running = False
        signal.signal(signal.SIGTERM, stop)
        rates = {}
        while running:
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                try:
                    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid not in {*UIDS, OPERATOR_UID}:
                        raise ValueError('peer_not_allowed')
                    minute = int(time.monotonic() / 60)
                    previous, count = rates.get(uid, (minute, 0))
                    count = count + 1 if previous == minute else 1
                    rates[uid] = (minute, count)
                    if count > 60:
                        raise ValueError('rate_limit')
                    document = receive(connection)
                    if document == {'action': 'status'}:
                        result = ledger.status(None if uid == OPERATOR_UID else UIDS[uid])
                    else:
                        result = ledger.submit(document, uid)
                except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
                    reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch('[a-z0-9_]{1,80}', str(exc)) else 'invalid_request'
                    result = {'accepted': False, 'reason': reason}
                try:
                    send(connection, result)
                except OSError:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['serve', 'submit', 'status'])
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    if args.action == 'serve':
        serve()
        return 0
    if args.action == 'status':
        result = request({'action': 'status'})
    else:
        with args.file.open('rb') if args.file else sys.stdin.buffer as stream:
            result = request(decode(stream.read(MAX_BYTES + 1)))
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get('accepted') is False else 0


if __name__ == '__main__':
    raise SystemExit(main())
