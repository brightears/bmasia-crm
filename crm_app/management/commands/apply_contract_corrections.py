"""Apply a reviewed file of contract status corrections, or revert one run.

The file lists contracts whose status the CRM has wrong, with the state each
one is expected to be in now. Three classes of correction exist:

  A  mark renewed      an Active contract whose renewal successor is already
                       Active on the same company becomes Renewed.
  B  activate + renew  a pair: the successor (Sent or Draft) becomes Active and
                       the old term (Active) becomes Renewed.
  C  activate          a Sent contract becomes Active.

SAFETY MODEL
  * Dry-run by DEFAULT. Nothing is written unless --execute is passed.
  * Lines sharing a ``group`` are applied together or not at all, in one
    transaction, with the rows locked (select_for_update). A group is refused,
    with a named reason, when any contract is missing; when its status, start
    date, end date or updated_at differ from the file (timestamps compared as
    instants); when the transition is not Sent->Active, Draft->Active or
    Active->Renewed; when the contracts are on different companies; when a
    contract id appears more than once in the file; or when the write would
    change a contract that is not in the group.
  * Re-running after an execute is a no-op: a group whose contracts are all in
    their target state (with unchanged dates) is reported as already applied.
  * No email is sent and no external service is called. Writes are limited to
    the fields listed under WRITE PATH, plus AuditLog rows.
  * Output names contracts by id and contract number only.

WRITE PATH
  Activation (target Active) does what a REST ``PATCH {"status": "Active"}``
  does through ContractSerializer.update, minus its unrelated validation:
    - a DRAFT-/C-/empty number gets a final HK-CT/TH-CT number from the same
      DocumentSequence, through the collision-safe reservation helper used by
      the review-numbering path (Contract.save() would mint without checking
      for collisions with imported numbers);
    - Contract.save() runs, so updated_at is bumped and the post_save handlers
      run as they would on any save (none acts on Active);
    - is_active becomes True, as ContractSerializer does on a transition to
      Active (renewal Drafts are created with is_active=False); it is
      journalled and audited like any other touched field;
    - sent_date is left as it is (a normal activation leaves it too; a Draft
      activated this way keeps sent_date empty);
    - signed_date is set only when the file gives one and the field is empty;
    - set_renewed_from links the successor to the old term of its pair only
      when the successor has no link yet (a different link refuses the group);
    - the lifecycle rule close_renewed_predecessor() is then called exactly
      once. In a B pair it must close the old term of the pair; in class C it
      must not close anything (a group where it would is refused up front).
  Mark renewed (class A) calls the same lifecycle rule for the existing Active
  successor, so the old term is closed by the same code (queryset update of
  status/is_active, updated_at bump, AuditLog row).
  Every changed contract gets exactly one AuditLog UPDATE row whose
  additional_data carries command, batch_id, group, class and evidence.

FORMAT v2
  A file whose "format" is "contract-corrections/v2" is handled by
  crm_app/services/contract_corrections_v2.py: operations mark_cancelled,
  mark_renewed (status only), set_renewed_from and create_successor, with the
  same safety model (dry-run default, groups all-or-nothing, expected state,
  audit rows, journal, revert, idempotent re-run). Its docstring documents the
  file shape, every refusal and the revert rules. v1 files below are unchanged.

FILE FORMAT v1 (JSON, ids and values only; unknown keys are rejected)
    {
      "format": "contract-corrections/v1",
      "source_pulled_at": "2026-01-01T00:00:00+00:00",      (optional)
      "entries": [
        {
          "contract_id": "<uuid>",
          "class": "A" | "B" | "C",
          "group": "<group key, [A-Za-z0-9:._-], up to 80 chars>",
          "expected": {
            "status": "Sent",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD" | null,
            "updated_at": "<ISO 8601 timestamp with offset>"
          },
          "target_status": "Active" | "Renewed",
          "signed_date": "YYYY-MM-DD" | null,                 (optional, Active only)
          "set_renewed_from": "<uuid>" | null,                (optional, Active only)
          "evidence": "<short reference, e.g. sheet / tab / row N>"
        }
      ]
    }
  Group shapes: A = one Renewed entry; B = one Active and one Renewed entry;
  C = one Active entry. set_renewed_from may only name the Renewed entry of
  the same B group. A malformed file stops the command with a non-zero exit
  before anything is read from the database.

JOURNAL AND REVERT
  --execute requires --journal <path> (a new file). After each applied group
  the journal is rewritten with, per changed contract, its id and the before
  and after values of every field touched, including updated_at.
  --revert <journal> (dry-run by default, --execute to write) restores the
  before values, group by group, only where every contract of the group still
  matches the journal's after values; anything else is reported as skipped.
  A final contract number minted on activation is kept on revert: a final
  number is never handed back (Drafts holding a final number are a normal
  state), and the old DRAFT- number may since have been reused.

Usage:
    python manage.py apply_contract_corrections --file corrections.json
    python manage.py apply_contract_corrections --file corrections.json --only-class C
    python manage.py apply_contract_corrections --file corrections.json --execute \\
        --journal journal.json --actor <username>
    python manage.py apply_contract_corrections --revert journal.json [--execute]
"""
import hashlib
import json
import os
import re
import tempfile
import uuid
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from crm_app.models import AuditLog, Contract
from crm_app.services import contract_corrections_v2 as v2
from crm_app.services.contract_lifecycle import CLOSED, close_renewed_predecessor

COMMAND = 'apply_contract_corrections'
FILE_FORMAT = 'contract-corrections/v1'
JOURNAL_FORMAT = 'contract-corrections-journal/v1'
CLASSES = ('A', 'B', 'C')
ALLOWED_TRANSITIONS = {('Sent', 'Active'), ('Draft', 'Active'), ('Active', 'Renewed')}
TARGET_STATUSES = {'Active', 'Renewed'}
STATUSES = {value for value, _ in Contract.CONTRACT_STATUS_CHOICES}

_TOP_KEYS = {'format', 'source_pulled_at', 'entries'}
_ENTRY_REQUIRED = {'contract_id', 'class', 'group', 'expected', 'target_status', 'evidence'}
_ENTRY_OPTIONAL = {'signed_date', 'set_renewed_from'}
_EXPECTED_KEYS = {'status', 'start_date', 'end_date', 'updated_at'}
_GROUP_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9:._-]{0,79}')
_EVIDENCE_MAX = 300

# Fields this command may change, as recorded in the journal.
JOURNAL_FIELDS = ('status', 'is_active', 'contract_number', 'sent_date', 'signed_date', 'renewed_from')
# Fields a revert restores. contract_number is deliberately absent (see docstring).
REVERT_FIELDS = ('status', 'is_active', 'sent_date', 'signed_date', 'renewed_from')


class _Refused(Exception):
    """A group cannot be applied; the reason is a short name."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Entry:
    index: int
    contract_id: str
    cls: str
    group: str
    exp_status: str
    exp_start: date
    exp_end: Optional[date]
    exp_updated_at: datetime
    target: str
    signed_date: Optional[date]
    set_renewed_from: Optional[str]
    evidence: str


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _malformed(message):
    return CommandError(f'malformed corrections file: {message}')


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


def parse_corrections(data):
    """Validate a decoded corrections file. Returns (entries, duplicate_ids)."""
    if not isinstance(data, dict):
        raise _malformed('top level must be a JSON object')
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise _malformed(f'unknown top-level keys {sorted(unknown)}')
    if data.get('format') != FILE_FORMAT:
        raise _malformed(f'format must be {FILE_FORMAT!r}')
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
        if raw['class'] not in CLASSES:
            raise _malformed(f'{where}: class must be one of {list(CLASSES)}')
        group = raw['group']
        if not isinstance(group, str) or not _GROUP_RE.fullmatch(group):
            raise _malformed(f'{where}: group must match {_GROUP_RE.pattern}')
        expected = raw['expected']
        if not isinstance(expected, dict) or set(expected) != _EXPECTED_KEYS:
            raise _malformed(f'{where}: expected must have exactly {sorted(_EXPECTED_KEYS)}')
        if expected['status'] not in STATUSES:
            raise _malformed(f'{where}: expected.status {expected["status"]!r} is not a contract status')
        target = raw['target_status']
        if target not in TARGET_STATUSES:
            raise _malformed(f'{where}: target_status must be one of {sorted(TARGET_STATUSES)}')
        signed_date = _date(raw.get('signed_date'), f'{where} signed_date', nullable=True)
        set_renewed_from = raw.get('set_renewed_from')
        if set_renewed_from is not None:
            set_renewed_from = _uuid(set_renewed_from, f'{where} set_renewed_from')
        if target != 'Active' and (signed_date or set_renewed_from):
            raise _malformed(f'{where}: signed_date and set_renewed_from apply to Active targets only')
        evidence = raw['evidence']
        if (not isinstance(evidence, str) or not evidence.strip() or len(evidence) > _EVIDENCE_MAX
                or any(ord(ch) < 32 for ch in evidence)):
            raise _malformed(f'{where}: evidence must be a single-line string of 1-{_EVIDENCE_MAX} characters')
        entries.append(Entry(
            index=index, contract_id=contract_id, cls=raw['class'], group=group,
            exp_status=expected['status'],
            exp_start=_date(expected['start_date'], f'{where} expected.start_date'),
            exp_end=_date(expected['end_date'], f'{where} expected.end_date', nullable=True),
            exp_updated_at=_instant(expected['updated_at'], f'{where} expected.updated_at'),
            target=target, signed_date=signed_date, set_renewed_from=set_renewed_from,
            evidence=evidence,
        ))

    for group, members in group_entries(entries).items():
        classes = {e.cls for e in members}
        if len(classes) != 1:
            raise _malformed(f'group {group}: mixes classes {sorted(classes)}')
        cls = classes.pop()
        targets = sorted(e.target for e in members)
        shape = {'A': ['Renewed'], 'B': ['Active', 'Renewed'], 'C': ['Active']}[cls]
        if targets != shape:
            raise _malformed(f'group {group}: class {cls} needs target(s) {shape}, got {targets}')
        renewed_ids = {e.contract_id for e in members if e.target == 'Renewed'}
        for e in members:
            if e.set_renewed_from and e.set_renewed_from not in renewed_ids:
                raise _malformed(
                    f'group {group}: set_renewed_from of {e.contract_id} must name the Renewed entry of its group')

    counts = Counter(e.contract_id for e in entries)
    duplicates = {cid for cid, n in counts.items() if n > 1}
    return entries, duplicates


def group_entries(entries):
    groups = OrderedDict()
    for entry in entries:
        groups.setdefault(entry.group, []).append(entry)
    return groups


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def snapshot(contract):
    """Values of the fields this command may change, JSON-safe."""
    return {
        'status': contract.status,
        'is_active': contract.is_active,
        'contract_number': contract.contract_number,
        'sent_date': _json_value(contract.sent_date),
        'signed_date': _json_value(contract.signed_date),
        'renewed_from': _json_value(contract.renewed_from_id),
        'updated_at': _json_value(contract.updated_at),
    }


def _changes(before, after):
    return {
        key: {'old': before[key], 'new': after[key]}
        for key in JOURNAL_FIELDS if before[key] != after[key]
    }


def _needs_final_number(contract):
    number = contract.contract_number or ''
    return not number or number.startswith(('DRAFT-', 'C-'))


def _write_json_atomic(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    handle, temp_path = tempfile.mkstemp(prefix='.journal-', dir=directory)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write('\n')
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


# --------------------------------------------------------------------------
# command
# --------------------------------------------------------------------------

class Command(BaseCommand):
    COMMAND_NAME = COMMAND
    help = ('Apply a reviewed contract-corrections file (dry-run by default; --execute '
            'with --journal to write), or revert a run from its journal.')

    def add_arguments(self, parser):
        parser.add_argument('--file', help='Corrections file (format in the module docstring).')
        parser.add_argument('--revert', metavar='JOURNAL', help='Revert the changes recorded in this journal.')
        parser.add_argument('--execute', action='store_true',
                            help='Write. Without this flag the command only reports what it would do.')
        parser.add_argument('--journal', help='Path of the revert journal to create (required with --execute).')
        parser.add_argument('--only-class', action='append', dest='only_class',
                            help='Apply only this class (repeatable). Default: all classes. '
                                 'v1 classes are A/B/C; v2 classes are the labels in the file.')
        parser.add_argument('--actor', help='Username the audit rows are attributed to.')

    # ---- entry point -----------------------------------------------------

    def handle(self, *args, **opts):
        if bool(opts['file']) == bool(opts['revert']):
            raise CommandError('pass exactly one of --file or --revert.')
        self.execute_mode = opts['execute']
        self.mode = 'EXECUTE' if self.execute_mode else 'DRY-RUN'
        self.batch_id = str(uuid.uuid4())
        self.actor = self._actor(opts['actor'])
        if opts['revert']:
            if opts['journal'] or opts['only_class']:
                raise CommandError('--journal and --only-class do not apply to --revert.')
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
        data, file_sha256 = self._read_json(opts['file'], 'corrections file')
        is_v2 = isinstance(data, dict) and data.get('format') == v2.FILE_FORMAT_V2
        if is_v2:
            v2.parse_v2(data)  # a malformed file stops here, before any database read
        else:
            entries, duplicates = parse_corrections(data)
            bad = set(opts['only_class'] or []) - set(CLASSES)
            if bad:
                raise CommandError(f'--only-class {sorted(bad)}: v1 classes are {list(CLASSES)}.')
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
        if is_v2:
            return v2.V2Runner(self).apply(
                data, file_sha256, opts, lambda payload: _write_json_atomic(journal_path, payload))

        selected = set(opts['only_class'] or CLASSES)
        groups = group_entries(entries)
        duplicate_groups = {e.group for e in entries if e.contract_id in duplicates}

        self.journal_path = journal_path
        self.journal = {
            'format': JOURNAL_FORMAT, 'command': COMMAND, 'batch_id': self.batch_id,
            'file_sha256': file_sha256, 'started_at': timezone.now().isoformat(),
            'actor': self.actor.username if self.actor else None, 'groups': [],
        }
        if self.execute_mode:
            _write_json_atomic(journal_path, self.journal)

        self.stdout.write(
            f'{COMMAND} [{self.mode}] batch {self.batch_id}: {len(entries)} entries in '
            f'{len(groups)} groups; classes {"/".join(sorted(selected))}')

        tally = {cls: Counter() for cls in CLASSES}
        not_selected = 0
        for group, members in groups.items():
            cls = members[0].cls
            if cls not in selected:
                not_selected += len(members)
                continue
            outcome, rows = self._apply_group(group, members, group in duplicate_groups)
            for entry, number, detail in rows:
                label = {'would_apply': 'WOULD-APPLY', 'applied': 'APPLIED',
                         'already_applied': 'ALREADY-APPLIED'}.get(outcome, f'SKIPPED:{outcome}')
                self.stdout.write(
                    f'  [{label}] {cls} {entry.contract_id} {number or "-"}: '
                    f'{entry.exp_status} -> {entry.target}{"; " + detail if detail else ""}')
                key = outcome if outcome in ('would_apply', 'applied', 'already_applied') else f'skipped:{outcome}'
                tally[cls][key] += 1

        self.stdout.write(f'\nsummary [{self.mode}] batch {self.batch_id}')
        for cls in CLASSES:
            if tally[cls]:
                self.stdout.write(f'  {cls}: ' + ' '.join(f'{k}={v}' for k, v in sorted(tally[cls].items())))
        total = sum(tally.values(), Counter())
        self.stdout.write('  total: ' + (' '.join(f'{k}={v}' for k, v in sorted(total.items())) or 'nothing'))
        if not_selected:
            self.stdout.write(f'  not selected by --only-class: {not_selected} entries')
        if self.execute_mode:
            self.stdout.write(f'journal: {journal_path}')
        elif total.get('would_apply'):
            self.stdout.write('re-run with --execute --journal <path> to apply.')

    def _apply_group(self, group, members, has_duplicate):
        """Returns (outcome, [(entry, contract_number, detail)])."""
        numbers = {}

        def rows(details=None):
            details = details or {}
            return [(e, numbers.get(e.contract_id), details.get(e.contract_id, '')) for e in members]

        numbers.update({
            str(pk): number for pk, number in
            Contract.objects.filter(pk__in=[e.contract_id for e in members]).values_list('pk', 'contract_number')
        })
        if has_duplicate:
            return 'duplicate_contract_id', rows()
        if any((e.exp_status, e.target) not in ALLOWED_TRANSITIONS for e in members):
            return 'transition_not_allowed', rows()

        try:
            with transaction.atomic():
                ids = sorted({e.contract_id for e in members})
                locked = {
                    str(c.pk): c
                    for c in Contract.objects.select_for_update().filter(pk__in=ids).order_by('pk')
                }
                numbers.update({cid: c.contract_number for cid, c in locked.items()})
                state, plan = self._check_group(members, locked)
                if state == 'already_applied':
                    return 'already_applied', rows()
                if not self.execute_mode:
                    return 'would_apply', rows(plan['details'])
                details, journal_rows = self._write_group(group, members, locked, plan)
                numbers.update({cid: c.contract_number for cid, c in locked.items()})
        except _Refused as refused:
            return refused.reason, rows()
        except DatabaseError as exc:
            return f'write_failed({exc.__class__.__name__})', rows()

        # Committed: record it in the journal before moving on.
        self.journal['groups'].append({'group': group, 'class': members[0].cls, 'contracts': journal_rows})
        _write_json_atomic(self.journal_path, self.journal)
        return 'applied', rows(details)

    def _check_group(self, members, locked):
        """Raise _Refused, or return ('already_applied'|'apply', plan)."""
        if any(e.contract_id not in locked for e in members):
            raise _Refused('missing_contract')
        if len({locked[e.contract_id].company_id for e in members}) > 1:
            raise _Refused('different_companies')

        states = []
        for e in members:
            c = locked[e.contract_id]
            dates_ok = c.start_date == e.exp_start and c.end_date == e.exp_end
            link_ok = not e.set_renewed_from or str(c.renewed_from_id) == e.set_renewed_from
            if c.status == e.exp_status and dates_ok and c.updated_at == e.exp_updated_at:
                states.append('expected')
            elif c.status == e.target and dates_ok and link_ok:
                states.append('target')
            elif c.status not in (e.exp_status, e.target):
                raise _Refused('status_changed')
            elif not dates_ok:
                raise _Refused('dates_changed')
            elif c.status == e.target:
                raise _Refused('renewed_from_conflict')
            else:
                raise _Refused('updated_at_changed')
        if all(s == 'target' for s in states):
            return 'already_applied', None
        if any(s == 'target' for s in states):
            raise _Refused('partially_applied')

        activation = next((e for e in members if e.target == 'Active'), None)
        renewal = next((e for e in members if e.target == 'Renewed'), None)
        plan = {'activation': activation, 'renewal': renewal, 'successor_for_a': None, 'details': {}}

        if activation:
            s = locked[activation.contract_id]
            notes = []
            current_link = str(s.renewed_from_id) if s.renewed_from_id else None
            if activation.set_renewed_from and current_link not in (None, activation.set_renewed_from):
                raise _Refused('renewed_from_conflict')
            link = current_link or activation.set_renewed_from
            if renewal:
                if link is None:
                    raise _Refused('pair_not_linked')
                if link != renewal.contract_id:
                    raise _Refused('renewed_from_conflict')
            elif link:
                predecessor = Contract.objects.select_for_update().filter(pk=link).first()
                if predecessor and predecessor.company_id == s.company_id and predecessor.status == 'Active':
                    raise _Refused('would_close_contract_outside_file')
            if _needs_final_number(s):
                notes.append(f'final number reserved (was {s.contract_number or "empty"})')
            if activation.signed_date:
                if s.signed_date is None:
                    notes.append(f'signed_date set {activation.signed_date.isoformat()}')
                elif s.signed_date != activation.signed_date:
                    notes.append('signed_date kept (already set, differs from file)')
            if activation.set_renewed_from and current_link is None:
                notes.append('renewed_from set to old term')
            if not s.is_active:
                notes.append('is_active False -> True')
            plan['details'][activation.contract_id] = '; '.join(notes)

        if renewal:
            o = locked[renewal.contract_id]
            if activation:
                plan['details'][renewal.contract_id] = 'closed by the lifecycle rule when its successor goes Active'
            else:
                successor = (
                    Contract.objects.select_for_update()
                    .filter(renewed_from_id=o.pk, company_id=o.company_id, status='Active')
                    .order_by('start_date', 'created_at', 'id')
                    .first()
                )
                if successor is None:
                    raise _Refused('no_active_successor')
                plan['successor_for_a'] = successor
                plan['details'][renewal.contract_id] = (
                    f'closed by the lifecycle rule for Active successor {successor.pk} {successor.contract_number}')
        return 'apply', plan

    def _audit_meta(self, group, entry):
        return {
            'command': COMMAND, 'batch_id': self.batch_id, 'group': group,
            'class': entry.cls, 'evidence': entry.evidence, 'file_sha256': self.file_sha256,
        }

    def _write_group(self, group, members, locked, plan):
        befores = {cid: snapshot(c) for cid, c in locked.items()}
        activation, renewal = plan['activation'], plan['renewal']

        if activation:
            s = locked[activation.contract_id]
            if _needs_final_number(s):
                from crm_app.services.rene_phase2 import RenePhase2Error, _reserve_final_contract_number
                try:
                    s.contract_number = _reserve_final_contract_number(s)
                except RenePhase2Error:
                    raise _Refused('number_reservation_failed')
            s.status = 'Active'
            s.is_active = True  # same rule as ContractSerializer._mark_live_on_activation
            if activation.signed_date and s.signed_date is None:
                s.signed_date = activation.signed_date
            if activation.set_renewed_from and s.renewed_from_id is None:
                s.renewed_from_id = uuid.UUID(activation.set_renewed_from)
            s.save(update_fields=[
                'status', 'is_active', 'contract_number', 'sent_date', 'signed_date', 'renewed_from',
                'updated_at'])
            s.refresh_from_db()
            after = snapshot(s)
            AuditLog.objects.create(
                user=self.actor, action='UPDATE', model_name='Contract', record_id=str(s.pk),
                changes=_changes(befores[activation.contract_id], after),
                additional_data={
                    **self._audit_meta(group, activation),
                    'action': f'Correction: {activation.exp_status} -> Active',
                    'timestamp': timezone.now().isoformat(),
                },
            )
            closure = close_renewed_predecessor(s, user=self.actor, source=COMMAND)
            if renewal:
                if not (closure.outcome == CLOSED and closure.predecessor_id == renewal.contract_id):
                    raise _Refused(f'rule_did_not_close_old_term({closure.outcome})')
            elif closure.outcome == CLOSED:
                raise _Refused('rule_closed_contract_outside_file')
        else:
            closure = close_renewed_predecessor(plan['successor_for_a'], user=self.actor, source=COMMAND)
            if not (closure.outcome == CLOSED and closure.predecessor_id == renewal.contract_id):
                raise _Refused(f'rule_did_not_close_old_term({closure.outcome})')

        if renewal:
            # One audit row per changed contract: the rule wrote it; add the batch metadata.
            row = AuditLog.objects.get(pk=closure.audit_log_id)
            row.additional_data = {**(row.additional_data or {}), **self._audit_meta(group, renewal)}
            row.save(update_fields=['additional_data'])

        journal_rows, details = [], {}
        for e in members:
            c = locked[e.contract_id]
            c.refresh_from_db()
            before, after = befores[e.contract_id], snapshot(c)
            touched = [f for f in JOURNAL_FIELDS if before[f] != after[f]] + ['updated_at']
            journal_rows.append({
                'contract_id': e.contract_id, 'class': e.cls, 'evidence': e.evidence,
                'before': {f: before[f] for f in touched},
                'after': {f: after[f] for f in touched},
            })
            changes = _changes(before, after)
            details[e.contract_id] = ', '.join(
                f'{f} {v["old"]} -> {v["new"]}' for f, v in changes.items() if f != 'status')
        return details, journal_rows

    # ---- revert ----------------------------------------------------------

    def _handle_revert(self, path):
        journal, _ = self._read_json(path, 'journal')
        if isinstance(journal, dict) and journal.get('format') == v2.JOURNAL_FORMAT_V2:
            return v2.V2Runner(self).revert(journal, path)
        if not isinstance(journal, dict) or journal.get('format') != JOURNAL_FORMAT \
                or not isinstance(journal.get('groups'), list):
            raise CommandError(f'{path} is not a {JOURNAL_FORMAT} journal.')
        reverted_batch = journal.get('batch_id')
        self.stdout.write(f'{COMMAND} revert [{self.mode}] batch {self.batch_id} of applied batch {reverted_batch}')
        tally = Counter()
        for group_row in journal['groups']:
            try:
                group, cls, rows = group_row['group'], group_row['class'], group_row['contracts']
                for row in rows:
                    _uuid(row['contract_id'], 'journal contract_id')
                    if set(row['before']) != set(row['after']) or 'updated_at' not in row['after']:
                        raise KeyError('before/after')
            except (KeyError, TypeError, CommandError) as exc:
                raise CommandError(f'{path}: malformed journal group ({exc}).')
            outcome = self._revert_group(group, cls, rows, reverted_batch)
            for row in rows:
                label = {'would_revert': 'WOULD-REVERT', 'reverted': 'REVERTED',
                         'already_reverted': 'ALREADY-REVERTED'}.get(outcome, f'SKIPPED:{outcome}')
                kept = row['after'].get('contract_number')
                note = f'; final number {kept} kept' if 'contract_number' in row['after'] else ''
                self.stdout.write(
                    f'  [{label}] {cls} {row["contract_id"]}: {row["after"].get("status")} -> '
                    f'{row["before"].get("status")}{note}')
                key = outcome if outcome in ('would_revert', 'reverted', 'already_reverted') else f'skipped:{outcome}'
                tally[f'{cls}:{key}'] += 1
        self.stdout.write(f'\nsummary revert [{self.mode}] batch {self.batch_id}')
        self.stdout.write('  ' + (' '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'nothing'))

    @staticmethod
    def _matches(contract, values):
        current = snapshot(contract)
        for field, value in values.items():
            if field == 'updated_at':
                if contract.updated_at != _instant(value, 'journal updated_at'):
                    return False
            elif current[field] != value:
                return False
        return True

    def _revert_group(self, group, cls, rows, reverted_batch):
        try:
            with transaction.atomic():
                ids = sorted(row['contract_id'] for row in rows)
                locked = {
                    str(c.pk): c
                    for c in Contract.objects.select_for_update().filter(pk__in=ids).order_by('pk')
                }
                if any(row['contract_id'] not in locked for row in rows):
                    return 'missing_contract'
                if all(self._matches(locked[r['contract_id']], r['after']) for r in rows):
                    pass
                elif all(self._matches(locked[r['contract_id']], {
                        f: v for f, v in r['before'].items() if f in REVERT_FIELDS}) for r in rows):
                    return 'already_reverted'
                else:
                    return 'changed_since_apply'
                if not self.execute_mode:
                    return 'would_revert'
                for row in rows:
                    c = locked[row['contract_id']]
                    before = snapshot(c)
                    restore = {f: row['before'][f] for f in REVERT_FIELDS if f in row['before']}
                    update = {}
                    for field, value in restore.items():
                        if field == 'renewed_from':
                            update['renewed_from_id'] = value
                        elif field in ('sent_date', 'signed_date'):
                            update[field] = date.fromisoformat(value) if value else None
                        else:
                            update[field] = value
                    Contract.objects.filter(pk=c.pk).update(**update, updated_at=timezone.now())
                    c.refresh_from_db()
                    AuditLog.objects.create(
                        user=self.actor, action='UPDATE', model_name='Contract', record_id=str(c.pk),
                        changes=_changes(before, snapshot(c)),
                        additional_data={
                            'command': COMMAND, 'mode': 'revert', 'batch_id': self.batch_id,
                            'reverted_batch_id': reverted_batch, 'group': group, 'class': cls,
                            'evidence': row.get('evidence', ''),
                            'action': f'Correction reverted: {before["status"]} -> {c.status}',
                            'timestamp': timezone.now().isoformat(),
                        },
                    )
        except DatabaseError as exc:
            return f'write_failed({exc.__class__.__name__})'
        return 'reverted'
