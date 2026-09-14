#!/usr/bin/env python3
"""Exact-ID CRM reads for the operator-reviewed pilot. No write tools exist here.

Run under Vera with its existing configured authorization environment. Never
load another source's credentials. Output is minimized private customer data.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID

ENDPOINT = 'https://bmasia-crm.onrender.com/mcp/'
FIELDS = {'contacts': ('title', 'department', 'last_contacted'),
          'opportunities': ('stage', 'last_contact_date', 'follow_up_date')}
COLLECTIONS = {'contacts': 'contact', 'opportunities': 'opportunity'}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def decode(raw):
    if len(raw.encode('utf-8') if isinstance(raw, str) else raw) > 65536:
        raise ValueError('json_size_limit')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def pipeline(record_id, fields):
    record_id = str(UUID(record_id))
    if set(fields) - {'id', 'name', 'company', 'updated_at', *sum((list(v) for v in FIELDS.values()), [])}:
        raise ValueError('field_outside_projection')
    return [{'$match': {'id': record_id}}, {'$sort': {'id': 1}}, {'$limit': 2},
            {'$project': {'_id': 0, **{field: 1 for field in fields}}}]


def parse_page(result, record_id, fields):
    if result.isError or len(result.content) != 1 or result.content[0].type != 'text':
        raise ValueError('query_response_invalid')
    rows = decode(result.content[0].text)
    if not isinstance(rows, list) or len(rows) > 1:
        raise ValueError('query_result_not_exact')
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict) or row.get('id') != record_id or set(row) - set(fields):
        raise ValueError('query_identity_or_fields_invalid')
    for value in row.values():
        if value is not None and not isinstance(value, (str, bool, int, float)):
            raise ValueError('query_nested_value_refused')
        if isinstance(value, str) and len(value) > 500:
            raise ValueError('query_value_too_long')
    return row


async def collect(session, scope):
    records, companies, seen = [], {}, set()

    async def read_one(collection, record_id, fields):
        result = await session.call_tool('query_data_collections', {
            'collection': collection, 'search_pipeline': pipeline(record_id, fields)})
        return parse_page(result, record_id, fields)

    for account in scope['accounts']:
        company_id = account['company_id']
        collection, record_id = account['collection'], account['record_id']
        identity = (company_id, collection, record_id)
        if identity in seen:
            continue
        seen.add(identity)
        result = {'company': {'id': company_id}, 'collection': collection, 'id': record_id,
                  'observed_at': datetime.now(timezone.utc).isoformat(),
                  'updated_at': None, 'fields': {}, 'status': 'error'}
        try:
            if company_id not in companies:
                companies[company_id] = await read_one('company', company_id, ('id', 'name', 'updated_at'))
            company = companies[company_id]
            fields = ('id', 'company', 'updated_at', *FIELDS[collection])
            row = await read_one(COLLECTIONS[collection], record_id, fields) if company else None
            result.update(company=company or {'id': company_id}, status='missing')
            if row:
                if row.get('company') != company_id or not row.get('updated_at'):
                    raise ValueError('crm_identity_or_version_unverified')
                result.update(status='ok', updated_at=row.get('updated_at'),
                              fields={key: row[key] for key in ('company', *FIELDS[collection]) if key in row})
        except Exception:
            result['status'] = 'error'  # No provider/token/header/body echo.
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
        records.append(result)
    return {'schema': 'bmasia.live-pilot-snapshots.v1', 'scope_id': scope['scope_id'],
            'observed_at': datetime.now(timezone.utc).isoformat(), 'records': records,
            'crm_writes': 0, 'customer_outbound': False}


async def live(scope):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def guard(request):
        if str(request.url) != ENDPOINT or request.method not in {'POST', 'GET'}:
            raise ValueError('transport_outside_read_endpoint')

    def factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth,
                                 follow_redirects=False, trust_env=False,
                                 event_hooks={'request': [guard]})

    authorization = os.environ.get('BMASIA_CRM_AUTHORIZATION')
    if not authorization:
        raise ValueError('existing_vera_authorization_unavailable')
    async with streamablehttp_client(
        ENDPOINT, headers={'Authorization': authorization}, timeout=20,
        sse_read_timeout=25, terminate_on_close=False, httpx_client_factory=factory,
    ) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            return await collect(session, scope)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', required=True)
    args = parser.parse_args()
    try:
        spec = importlib.util.spec_from_file_location('pilot_sources', Path(__file__).with_name('agent_crm_source_observations.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Path(args.scope).open('rb') as stream:
            scope = decode(stream.read(65537))
        scope = module.validate_scope(scope)
        result = asyncio.run(live(scope))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0 if all(row['status'] == 'ok' for row in result['records']) else 2
    except Exception:
        print(json.dumps({'status': 'read_only_snapshot_failed', 'crm_writes': 0}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
