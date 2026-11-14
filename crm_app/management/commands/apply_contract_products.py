"""Back-fill contract product and zone rows from a reviewed file, or revert one run.

A contract's product and zones live in its ContractServiceLocation rows: one row
per zone, with a platform (soundtrack / beatbreeze / custom). The contract's
zone count, the PDF zone table and the Renewal Book all count those rows. This
command adds missing rows, corrects the platform of existing rows, and sets
``service_type`` where the reviewed file says so.

SAFETY MODEL
  * Dry-run by DEFAULT. Nothing is written unless --execute is passed.
  * One transaction per contract, with the contract row locked
    (select_for_update). A contract is refused, with a named reason, when it is
    missing; when its status, start date, end date or updated_at differ from
    the file (timestamps compared as instants); when its service_type differs
    from the file; when its existing service-location rows differ from the file
    (count plus a digest of every row, see ROW DIGEST); when a row named in
    ``set_platform`` is not one of its rows; when its id appears more than once
    in the file; when the result would trip the PDF pricing guard
    (services/contract_service_locations.py); or when a Beat Breeze
    service_type would contradict its Player Box line items.
  * Operations are additive only: add rows, change the platform of existing
    rows by id (ids, names, prices and sort order are kept), set service_type.
    Existing rows are never deleted or replaced. contract.value, prices and
    line items are never written.
  * Re-running after an execute is a no-op: a contract already in the file's
    target state is reported as already applied, whatever its updated_at.
  * No email is sent and no external service is called. ContractServiceLocation
    has no save() override and no signal receivers; the contract itself is
    written with a queryset update (service_type, updated_at), so no Contract
    post_save handler runs. Company fields, ContractZone links, Zones and line
    items are not touched.
  * Output names contracts by id and contract number only.

WRITE PATH (per applied contract)
  - new rows: ContractServiceLocation.objects.create(contract, location_name,
    platform, sort_order, custom_service_name='', price=None). price=None means
    the row inherits contract.price_per_zone, exactly as rows entered in the UI;
  - platform changes: row.platform = new; row.save(update_fields=[platform,
    updated_at]). custom_service_name is left as it was;
  - the contract's updated_at is bumped (and service_type set when asked), so
    agents that check a contract version see the change;
  - exactly one AuditLog UPDATE row per contract, with before/after row
    summaries and additional_data {command, batch_id, evidence, file_sha256,
    created_row_ids, platform_changes}.

FILE FORMAT (JSON; unknown keys are rejected)
    {
      "format": "contract-products/v1",
      "source": "<free text, e.g. which proposal file>",          (optional)
      "entries": [
        {
          "contract_id": "<uuid>",
          "evidence": "<single line, up to 1000 characters>",
          "expected": {
            "status": "Active",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD" | null,
            "updated_at": "<ISO 8601 timestamp with offset>",
            "service_type": "",
            "service_locations": {"count": 2, "digest": "<sha256 hex>"}
          },
          "add_locations": [                                        (optional)
            {"location_name": "Lobby", "platform": "soundtrack", "sort_order": 0}
          ],
          "set_platform": [                                         (optional)
            {"id": "<service-location uuid>", "from": "custom", "to": "beatbreeze"}
          ],
          "set_service_type": "soundtrack_unlimited_yearly" | null  (optional)
        }
      ]
    }
  Each entry needs at least one operation; set_service_type must differ from
  expected.service_type, and a set_platform row must currently have its "from". add_locations platforms are
  soundtrack or beatbreeze; names are 1-200 characters without control
  characters other than newline (a newline lists several areas in one zone, as
  the PDF expects). A malformed file stops the command with a non-zero exit
  before anything is read from the database.

ROW DIGEST
  sha256 over the contract's rows sorted by id, one line per row:
  "<id>|<location_name>|<platform>|<custom_service_name>|<sort_order>|<price>",
  lines joined with "\\n", price formatted with two decimals or empty. See
  ``rows_digest``; the parity converter computes the same value from a REST pull.

JOURNAL AND REVERT
  --execute requires --journal <path> (a new file). After each applied contract
  the journal is rewritten with the ids of the rows created, the platform
  changes, service_type before/after, the row digests and updated_at before and
  after.
  --revert <journal> (dry-run by default, --execute to write) deletes only the
  rows that run created, restores changed platforms and service_type, and only
  where the contract's updated_at, service_type and rows still equal the
  journal's after values; anything else is reported as skipped.

Usage:
    python manage.py apply_contract_products --file products.json
    python manage.py apply_contract_products --file products.json --execute \\
        --journal journal.json --actor <username>
    python manage.py apply_contract_products --revert journal.json [--execute]
"""
import hashlib
import json
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

# Shared, side-effect-free helpers. TODO(consolidate): apply_contract_corrections
# is being changed in parallel; move these and the small parsers below into a
# shared module (e.g. crm_app/management/commands/_apply_common.py) afterwards.
from crm_app.management.commands.apply_contract_corrections import (
    _json_value,
    _write_json_atomic,
)
from crm_app.models import AuditLog, Contract, ContractServiceLocation
from crm_app.services.contract_player_boxes import contract_player_box_variant_error
from crm_app.services.contract_service_locations import service_location_pricing_mismatch

COMMAND = 'apply_contract_products'
FILE_FORMAT = 'contract-products/v1'
JOURNAL_FORMAT = 'contract-products-journal/v1'
STATUSES = {value for value, _ in Contract.CONTRACT_STATUS_CHOICES}
SERVICE_TYPES = {value for value, _ in Contract.SERVICE_TYPE_CHOICES}
ADD_PLATFORMS = {'soundtrack', 'beatbreeze'}
SET_PLATFORMS = {'soundtrack', 'beatbreeze'}
FROM_PLATFORMS = {'soundtrack', 'beatbreeze', 'custom'}

_TOP_KEYS = {'format', 'source', 'entries'}
_ENTRY_REQUIRED = {'contract_id', 'evidence', 'expected'}
_ENTRY_OPTIONAL = {'add_locations', 'set_platform', 'set_service_type'}
_EXPECTED_KEYS = {'status', 'start_date', 'end_date', 'updated_at', 'service_type', 'service_locations'}
_EVIDENCE_MAX = 1000
_NAME_MAX = 200  # ContractServiceLocation.location_name max_length
_HEX64 = re.compile(r'[0-9a-f]{64}')


class _Refused(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Entry:
    index: int
    contract_id: str
    evidence: str
    exp_status: str
    exp_start: date
    exp_end: Optional[date]
    exp_updated_at: datetime
    exp_service_type: str
    exp_count: int
    exp_digest: str
    add: List[dict] = field(default_factory=list)
    set_platform: List[dict] = field(default_factory=list)
    set_service_type: Optional[str] = None


# --------------------------------------------------------------------------
# parsing (small copies of the corrections parsers, with this file's wording)
# --------------------------------------------------------------------------

def _malformed(message):
    return CommandError(f'malformed contract-products file: {message}')


def _uuid(value, where):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise _malformed(f'{where}: not a UUID')


def _date(value, where, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise _malformed(f'{where}: want YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _malformed(f'{where}: want YYYY-MM-DD')


def _instant(value, where):
    if not isinstance(value, str):
        raise _malformed(f'{where}: want an ISO 8601 timestamp with offset')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise _malformed(f'{where}: want an ISO 8601 timestamp with offset')
    if parsed.tzinfo is None:
        raise _malformed(f'{where}: timestamp has no UTC offset')
    return parsed


def _single_line(value, maximum):
    return (isinstance(value, str) and value.strip() and len(value) <= maximum
            and not any(ord(ch) < 32 for ch in value))


def _location_name_ok(value):
    return (isinstance(value, str) and value.strip() and len(value) <= _NAME_MAX
            and not any(ord(ch) < 32 and ch != '\n' for ch in value))


def parse_products(data):
    """Validate a decoded file. Returns (entries, duplicate_ids)."""
    if not isinstance(data, dict):
        raise _malformed('top level must be a JSON object')
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise _malformed(f'unknown top-level keys {sorted(unknown)}')
    if data.get('format') != FILE_FORMAT:
        raise _malformed(f'format must be {FILE_FORMAT!r}')
    if 'source' in data and not isinstance(data['source'], str):
        raise _malformed('source must be a string')
    raw_entries = data.get('entries')
    if not isinstance(raw_entries, list) or not raw_entries:
        raise _malformed('entries must be a non-empty list')

    entries = []
    for index, raw in enumerate(raw_entries):
        where = f'entry {index}'
        if not isinstance(raw, dict):
            raise _malformed(f'{where}: must be an object')
        missing = _ENTRY_REQUIRED - set(raw)
        unknown = set(raw) - _ENTRY_REQUIRED - _ENTRY_OPTIONAL
        if missing:
            raise _malformed(f'{where}: missing keys {sorted(missing)}')
        if unknown:
            raise _malformed(f'{where}: unknown keys {sorted(unknown)}')
        contract_id = _uuid(raw['contract_id'], f'{where} contract_id')
        where = f'entry {index} ({contract_id})'
        if not _single_line(raw['evidence'], _EVIDENCE_MAX):
            raise _malformed(f'{where}: evidence must be a single-line string of 1-{_EVIDENCE_MAX} characters')

        expected = raw['expected']
        if not isinstance(expected, dict) or set(expected) != _EXPECTED_KEYS:
            raise _malformed(f'{where}: expected must have exactly {sorted(_EXPECTED_KEYS)}')
        if expected['status'] not in STATUSES:
            raise _malformed(f'{where}: expected.status {expected["status"]!r} is not a contract status')
        if not isinstance(expected['service_type'], str) or (
                expected['service_type'] and expected['service_type'] not in SERVICE_TYPES):
            raise _malformed(f'{where}: expected.service_type must be "" or a service_type choice')
        locs = expected['service_locations']
        if (not isinstance(locs, dict) or set(locs) != {'count', 'digest'}
                or not isinstance(locs['count'], int) or isinstance(locs['count'], bool) or locs['count'] < 0
                or not isinstance(locs['digest'], str) or not _HEX64.fullmatch(locs['digest'])):
            raise _malformed(f'{where}: expected.service_locations must be {{"count": int >= 0, "digest": sha256 hex}}')

        add = raw.get('add_locations', [])
        if not isinstance(add, list):
            raise _malformed(f'{where}: add_locations must be a list')
        clean_add = []
        for j, row in enumerate(add):
            w = f'{where} add_locations[{j}]'
            if not isinstance(row, dict) or set(row) != {'location_name', 'platform', 'sort_order'}:
                raise _malformed(f'{w}: needs exactly location_name, platform, sort_order')
            if not _location_name_ok(row['location_name']):
                raise _malformed(f'{w}: location_name must be 1-{_NAME_MAX} characters without control characters')
            if row['platform'] not in ADD_PLATFORMS:
                raise _malformed(f'{w}: platform must be one of {sorted(ADD_PLATFORMS)}')
            if not isinstance(row['sort_order'], int) or isinstance(row['sort_order'], bool) or row['sort_order'] < 0:
                raise _malformed(f'{w}: sort_order must be an integer >= 0')
            clean_add.append(dict(row))

        setp = raw.get('set_platform', [])
        if not isinstance(setp, list):
            raise _malformed(f'{where}: set_platform must be a list')
        clean_set, seen = [], set()
        for j, row in enumerate(setp):
            w = f'{where} set_platform[{j}]'
            if not isinstance(row, dict) or set(row) != {'id', 'from', 'to'}:
                raise _malformed(f'{w}: needs exactly id, from, to')
            rid = _uuid(row['id'], f'{w} id')
            if rid in seen:
                raise _malformed(f'{w}: row id repeated')
            seen.add(rid)
            if row['from'] not in FROM_PLATFORMS or row['to'] not in SET_PLATFORMS or row['from'] == row['to']:
                raise _malformed(f'{w}: from must be one of {sorted(FROM_PLATFORMS)}, to one of '
                                 f'{sorted(SET_PLATFORMS)}, and they must differ')
            clean_set.append({'id': rid, 'from': row['from'], 'to': row['to']})

        st = raw.get('set_service_type')
        if st is not None and st not in SERVICE_TYPES:
            raise _malformed(f'{where}: set_service_type {st!r} is not a service_type choice')
        if st is not None and st == expected['service_type']:
            raise _malformed(f'{where}: set_service_type equals expected.service_type')
        if not clean_add and not clean_set and st is None:
            raise _malformed(f'{where}: no operation (add_locations, set_platform or set_service_type)')

        entries.append(Entry(
            index=index, contract_id=contract_id, evidence=raw['evidence'],
            exp_status=expected['status'],
            exp_start=_date(expected['start_date'], f'{where} expected.start_date'),
            exp_end=_date(expected['end_date'], f'{where} expected.end_date', nullable=True),
            exp_updated_at=_instant(expected['updated_at'], f'{where} expected.updated_at'),
            exp_service_type=expected['service_type'],
            exp_count=locs['count'], exp_digest=locs['digest'],
            add=clean_add, set_platform=clean_set, set_service_type=st,
        ))
    counts = Counter(e.contract_id for e in entries)
    return entries, {cid for cid, n in counts.items() if n > 1}


# --------------------------------------------------------------------------
# row digest and snapshots
# --------------------------------------------------------------------------

def _price_text(price):
    if price is None or price == '':
        return ''
    try:
        return f'{Decimal(str(price)):.2f}'
    except (InvalidOperation, ValueError):
        return str(price)


def row_line(row_id, location_name, platform, custom_service_name, sort_order, price):
    return '|'.join([str(row_id), location_name or '', platform or '', custom_service_name or '',
                     str(sort_order if sort_order is not None else 0), _price_text(price)])


def rows_digest(rows):
    """rows: iterables of (id, location_name, platform, custom_service_name, sort_order, price)."""
    lines = sorted((row_line(*r) for r in rows), key=lambda line: line.split('|', 1)[0])
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()


def _db_rows(contract):
    return list(ContractServiceLocation.objects.filter(contract=contract).order_by('id'))


def _row_tuple(row):
    return (row.id, row.location_name, row.platform, row.custom_service_name, row.sort_order, row.price)


def rows_summary(rows):
    return {
        'count': len(rows),
        'digest': rows_digest([_row_tuple(r) for r in rows]),
        'by_platform': dict(sorted(Counter(r.platform for r in rows).items())),
    }


class _Rows:
    """Stand-in for a related manager over planned rows (for the pricing guard)."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


# --------------------------------------------------------------------------
# command
# --------------------------------------------------------------------------

class Command(BaseCommand):
    help = ('Back-fill contract service-location rows / service_type from a reviewed file '
            '(dry-run by default; --execute with --journal to write), or revert a run.')

    def add_arguments(self, parser):
        parser.add_argument('--file', help='Contract-products file (format in the module docstring).')
        parser.add_argument('--revert', metavar='JOURNAL', help='Revert the changes recorded in this journal.')
        parser.add_argument('--execute', action='store_true',
                            help='Write. Without this flag the command only reports what it would do.')
        parser.add_argument('--journal', help='Path of the revert journal to create (required with --execute).')
        parser.add_argument('--actor', help='Username the audit rows are attributed to.')

    def handle(self, *args, **opts):
        if bool(opts['file']) == bool(opts['revert']):
            raise CommandError('pass exactly one of --file or --revert.')
        self.execute_mode = opts['execute']
        self.mode = 'EXECUTE' if self.execute_mode else 'DRY-RUN'
        self.batch_id = str(uuid.uuid4())
        self.actor = self._actor(opts['actor'])
        if opts['revert']:
            if opts['journal']:
                raise CommandError('--journal does not apply to --revert.')
            return self._handle_revert(opts['revert'])
        return self._handle_apply(opts)

    def _actor(self, username):
        if not username:
            return None
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'unknown --actor username {username!r}.')
        return user

    @staticmethod
    def _read_json(path, what):
        try:
            with open(path, 'rb') as fh:
                raw = fh.read()
            return json.loads(raw.decode('utf-8')), hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f'cannot read {what} {path}: {exc}') from exc

    # ---- apply -----------------------------------------------------------

    def _handle_apply(self, opts):
        data, file_sha256 = self._read_json(opts['file'], 'contract-products file')
        entries, duplicates = parse_products(data)
        self.file_sha256 = file_sha256
        journal_path = opts['journal']
        if self.execute_mode:
            if not journal_path:
                raise CommandError('--execute requires --journal <path>.')
            if os.path.exists(journal_path):
                raise CommandError(f'journal {journal_path} already exists; choose a new path.')
            if not os.path.isdir(os.path.dirname(os.path.abspath(journal_path))):
                raise CommandError(f'journal directory for {journal_path} does not exist.')
        elif journal_path:
            raise CommandError('--journal is only used with --execute.')
        self.journal_path = journal_path
        self.journal = {
            'format': JOURNAL_FORMAT, 'command': COMMAND, 'batch_id': self.batch_id,
            'file_sha256': file_sha256, 'started_at': timezone.now().isoformat(),
            'actor': self.actor.username if self.actor else None, 'contracts': [],
        }
        if self.execute_mode:
            _write_json_atomic(journal_path, self.journal)

        self.stdout.write(f'{COMMAND} [{self.mode}] batch {self.batch_id}: {len(entries)} entries')
        tally = Counter()
        for entry in entries:
            outcome, number, detail = self._apply_entry(entry, entry.contract_id in duplicates)
            label = {'would_apply': 'WOULD-APPLY', 'applied': 'APPLIED',
                     'already_applied': 'ALREADY-APPLIED'}.get(outcome, f'SKIPPED:{outcome}')
            self.stdout.write(f'  [{label}] {entry.contract_id} {number or "-"}{": " + detail if detail else ""}')
            tally[outcome if outcome in ('would_apply', 'applied', 'already_applied') else f'skipped:{outcome}'] += 1
        self.stdout.write(f'\nsummary [{self.mode}] batch {self.batch_id}')
        self.stdout.write('  total: ' + (' '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'nothing'))
        if self.execute_mode:
            self.stdout.write(f'journal: {journal_path}')
        elif tally.get('would_apply'):
            self.stdout.write('re-run with --execute --journal <path> to apply.')
        return None

    def _apply_entry(self, e, duplicate):
        number = Contract.objects.filter(pk=e.contract_id).values_list('contract_number', flat=True).first()
        if duplicate:
            return 'duplicate_contract_id', number, ''
        try:
            with transaction.atomic():
                c = Contract.objects.select_for_update().filter(pk=e.contract_id).first()
                if c is None:
                    raise _Refused('missing_contract')
                rows = _db_rows(c)
                state = self._check(e, c, rows)
                if state == 'already_applied':
                    return 'already_applied', c.contract_number, ''
                detail = self._describe(e, rows)
                if not self.execute_mode:
                    return 'would_apply', c.contract_number, detail
                journal_row = self._write(e, c, rows)
        except _Refused as refused:
            return refused.reason, number, ''
        except DatabaseError as exc:
            return f'write_failed({exc.__class__.__name__})', number, ''
        self.journal['contracts'].append(journal_row)
        _write_json_atomic(self.journal_path, self.journal)
        return 'applied', c.contract_number, detail

    @staticmethod
    def _describe(e, rows):
        bits = []
        if e.add:
            bits.append('add ' + ', '.join(f'{p}x{n}' for p, n in sorted(Counter(r['platform'] for r in e.add).items())))
        if e.set_platform:
            bits.append(f'platform fix on {len(e.set_platform)} row(s)')
        if e.set_service_type:
            bits.append(f'service_type -> {e.set_service_type}')
        bits.append(f'zones {len(rows)} -> {len(rows) + len(e.add)}')
        return '; '.join(bits)

    @staticmethod
    def _at_expected(e, c, rows):
        return ((c.service_type or '') == e.exp_service_type and len(rows) == e.exp_count
                and rows_digest([_row_tuple(r) for r in rows]) == e.exp_digest)

    @staticmethod
    def _at_target(e, c, rows):
        """Is the contract already in the file's target state (a re-run after an execute)?

        Remove one row per add_locations item (the most recently created row with that name,
        platform and sort order, no price and no custom name), undo the platform fixes in memory,
        and compare what is left with the file's expected count and digest."""
        if c.status != e.exp_status or c.start_date != e.exp_start or c.end_date != e.exp_end:
            return False
        if (c.service_type or '') != (e.set_service_type or e.exp_service_type):
            return False
        if len(rows) != e.exp_count + len(e.add):
            return False
        by_id = {str(r.id): r for r in rows}
        if any(s['id'] not in by_id or by_id[s['id']].platform != s['to'] for s in e.set_platform):
            return False
        pool = sorted(rows, key=lambda r: (r.created_at, str(r.id)), reverse=True)
        fixed_ids = {s['id'] for s in e.set_platform}
        for a in e.add:
            hit = next((r for r in pool if str(r.id) not in fixed_ids and r.location_name == a['location_name']
                        and r.platform == a['platform'] and r.sort_order == a['sort_order']
                        and r.price is None and not r.custom_service_name), None)
            if hit is None:
                return False
            pool.remove(hit)
        undo = {s['id']: s['from'] for s in e.set_platform}
        originals = [(r.id, r.location_name, undo.get(str(r.id), r.platform), r.custom_service_name,
                      r.sort_order, r.price) for r in pool]
        return len(originals) == e.exp_count and rows_digest(originals) == e.exp_digest

    def _check(self, e, c, rows):
        if not self._at_expected(e, c, rows) and self._at_target(e, c, rows):
            return 'already_applied'
        if c.status != e.exp_status:
            raise _Refused('status_changed')
        if c.start_date != e.exp_start or c.end_date != e.exp_end:
            raise _Refused('dates_changed')
        if c.updated_at != e.exp_updated_at:
            raise _Refused('updated_at_changed')
        if (c.service_type or '') != e.exp_service_type:
            raise _Refused('service_type_changed')
        if len(rows) != e.exp_count or rows_digest([_row_tuple(r) for r in rows]) != e.exp_digest:
            raise _Refused('service_locations_changed')
        by_id = {str(r.id): r for r in rows}
        for s in e.set_platform:
            if s['id'] not in by_id:
                raise _Refused('row_not_on_contract')
            if by_id[s['id']].platform != s['from']:
                raise _Refused('platform_differs_from_file')
        # pricing guard on the planned rows (same helper the API and PDF use)
        fixes = {s['id']: s['to'] for s in e.set_platform}
        planned = [SimpleNamespace(price=r.price, platform=fixes.get(str(r.id), r.platform)) for r in rows]
        planned += [SimpleNamespace(price=None, platform=a['platform']) for a in e.add]
        shim = SimpleNamespace(
            service_locations=_Rows(planned), line_items=c.line_items,
            show_zone_pricing_detail=c.show_zone_pricing_detail, discount_percentage=c.discount_percentage,
            price_per_zone=c.price_per_zone, value=c.value, currency=c.currency)
        if service_location_pricing_mismatch(shim):
            raise _Refused('pdf_pricing_guard')
        if e.set_service_type:
            original = c.service_type
            c.service_type = e.set_service_type
            try:
                if contract_player_box_variant_error(c):
                    raise _Refused('player_box_variant')
            finally:
                c.service_type = original
        return 'apply'

    def _write(self, e, c, rows):
        before_rows = rows_summary(rows)
        before = {'updated_at': _json_value(c.updated_at), 'service_type': c.service_type or '',
                  'value': str(c.value), 'service_locations': before_rows}
        by_id = {str(r.id): r for r in rows}
        platform_changes = []
        for s in e.set_platform:
            r = by_id[s['id']]
            platform_changes.append({'id': s['id'], 'old': r.platform, 'new': s['to']})
            r.platform = s['to']
            r.save(update_fields=['platform', 'updated_at'])
        created = []
        for a in e.add:
            r = ContractServiceLocation.objects.create(
                contract=c, location_name=a['location_name'], platform=a['platform'],
                sort_order=a['sort_order'], custom_service_name='', price=None)
            created.append({'id': str(r.id), 'location_name': r.location_name, 'platform': r.platform,
                            'sort_order': r.sort_order})
        update = {'updated_at': timezone.now()}
        if e.set_service_type:
            update['service_type'] = e.set_service_type
        Contract.objects.filter(pk=c.pk).update(**update)
        c.refresh_from_db()
        after_rows = rows_summary(_db_rows(c))
        if str(c.value) != before['value']:
            raise _Refused('value_changed')  # cannot happen (value is never written); rolls back if it does
        if service_location_pricing_mismatch(c):
            raise _Refused('pdf_pricing_guard')
        after = {'updated_at': _json_value(c.updated_at), 'service_type': c.service_type or '',
                 'value': str(c.value), 'service_locations': after_rows}
        changes = {'service_locations': {'old': before_rows, 'new': after_rows}}
        if before['service_type'] != after['service_type']:
            changes['service_type'] = {'old': before['service_type'], 'new': after['service_type']}
        AuditLog.objects.create(
            user=self.actor, action='UPDATE', model_name='Contract', record_id=str(c.pk),
            changes=changes,
            additional_data={
                'command': COMMAND, 'batch_id': self.batch_id, 'evidence': e.evidence,
                'file_sha256': self.file_sha256, 'created_row_ids': [r['id'] for r in created],
                'platform_changes': platform_changes,
                'action': 'Product/zone back-fill', 'timestamp': timezone.now().isoformat(),
            },
        )
        return {'contract_id': e.contract_id, 'contract_number': c.contract_number, 'evidence': e.evidence,
                'created_rows': created, 'platform_changes': platform_changes,
                'before': before, 'after': after}

    # ---- revert ----------------------------------------------------------

    def _handle_revert(self, path):
        journal, _ = self._read_json(path, 'journal')
        if not isinstance(journal, dict) or journal.get('format') != JOURNAL_FORMAT \
                or not isinstance(journal.get('contracts'), list):
            raise CommandError(f'{path} is not a {JOURNAL_FORMAT} journal.')
        reverted_batch = journal.get('batch_id')
        self.stdout.write(f'{COMMAND} revert [{self.mode}] batch {self.batch_id} of applied batch {reverted_batch}')
        tally = Counter()
        for row in journal['contracts']:
            try:
                _uuid(row['contract_id'], 'journal contract_id')
                for r in row['created_rows']:
                    _uuid(r['id'], 'journal created row id')
                for p in row['platform_changes']:
                    _uuid(p['id'], 'journal platform row id')
                    if p['old'] not in {'soundtrack', 'beatbreeze', 'custom'}:
                        raise KeyError('platform')
                for side in ('before', 'after'):
                    row[side]['updated_at'], row[side]['service_type'], row[side]['service_locations']['digest']
            except (KeyError, TypeError, CommandError) as exc:
                raise CommandError(f'{path}: malformed journal row ({exc}).')
            outcome = self._revert_contract(row, reverted_batch)
            label = {'would_revert': 'WOULD-REVERT', 'reverted': 'REVERTED',
                     'already_reverted': 'ALREADY-REVERTED'}.get(outcome, f'SKIPPED:{outcome}')
            self.stdout.write(f'  [{label}] {row["contract_id"]} {row.get("contract_number") or "-"}: '
                              f'remove {len(row["created_rows"])} row(s), restore {len(row["platform_changes"])} '
                              f'platform(s)')
            tally[outcome if outcome in ('would_revert', 'reverted', 'already_reverted') else f'skipped:{outcome}'] += 1
        self.stdout.write(f'\nsummary revert [{self.mode}] batch {self.batch_id}')
        self.stdout.write('  ' + (' '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'nothing'))

    def _revert_contract(self, row, reverted_batch):
        try:
            with transaction.atomic():
                c = Contract.objects.select_for_update().filter(pk=row['contract_id']).first()
                if c is None:
                    return 'missing_contract'
                rows = _db_rows(c)
                summary = rows_summary(rows)
                after, before = row['after'], row['before']
                at_after = (c.updated_at == _instant(after['updated_at'], 'journal updated_at')
                            and (c.service_type or '') == after['service_type']
                            and summary['digest'] == after['service_locations']['digest'])
                if not at_after:
                    if ((c.service_type or '') == before['service_type']
                            and summary['digest'] == before['service_locations']['digest']):
                        return 'already_reverted'
                    return 'changed_since_apply'
                if not self.execute_mode:
                    return 'would_revert'
                created_ids = [r['id'] for r in row['created_rows']]
                ContractServiceLocation.objects.filter(contract=c, id__in=created_ids).delete()
                for p in row['platform_changes']:
                    loc = ContractServiceLocation.objects.get(contract=c, id=p['id'])
                    loc.platform = p['old']
                    loc.save(update_fields=['platform', 'updated_at'])
                Contract.objects.filter(pk=c.pk).update(service_type=before['service_type'],
                                                        updated_at=timezone.now())
                c.refresh_from_db()
                restored = rows_summary(_db_rows(c))
                if restored['digest'] != before['service_locations']['digest']:
                    raise _Refused('restore_mismatch')  # rolls back
                AuditLog.objects.create(
                    user=self.actor, action='UPDATE', model_name='Contract', record_id=str(c.pk),
                    changes={'service_locations': {'old': summary, 'new': restored},
                             **({'service_type': {'old': after['service_type'], 'new': before['service_type']}}
                                if after['service_type'] != before['service_type'] else {})},
                    additional_data={
                        'command': COMMAND, 'mode': 'revert', 'batch_id': self.batch_id,
                        'reverted_batch_id': reverted_batch, 'evidence': row.get('evidence', ''),
                        'deleted_row_ids': created_ids, 'action': 'Product/zone back-fill reverted',
                        'timestamp': timezone.now().isoformat(),
                    },
                )
        except _Refused as refused:
            return refused.reason
        except DatabaseError as exc:
            return f'write_failed({exc.__class__.__name__})'
        return 'reverted'
