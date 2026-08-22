"""
Reconcile Kent-2025-import false-Expired contracts.

Background (INC-20260622-0e6b59 / -e7137c, opened by forensics 2026-06):
the 2025 "Kent performance metrics" import created contracts with placeholder
calendar-2025 dates (2025-01-01 -> 2025-12-31) and status=Expired. For live,
actively-renewing accounts this is a FALSE expiry: the contract is really
Active, but because status=Expired it is invisible to renewal tracking. A
read-only sweep (2026-08-22) found 605 such placeholder contracts, 481 of them
on companies that are active with no live contract. This has poisoned the
renewal lists since June because no automated path could reverse the status:
Cira's state-machine refuses Expired->Active, and Vera's tier-3 gate hard-stops
anything touching contract status. This command is that sanctioned, audited,
operator-run correction path.

SAFETY MODEL — read before use:
  * Dry-run by DEFAULT. Nothing is written unless --execute is passed.
  * Scope is a HUMAN-VERIFIED allowlist (--verified-file). Theo confirms each
    contract is LIVE and supplies its real term against renewal/SYB/Gmail
    evidence; that file is the authorization. The command NEVER flips a contract
    that is not explicitly listed.
  * It only ever moves status Expired -> Active (or -> Renewed when a live
    replacement exists), fixes the start/end dates to the verified real term,
    and scrubs the customer-leaking "Imported from Kent..." note. It does not
    touch value, currency, invoices, money, or any other record. It creates and
    deletes nothing.
  * Idempotent: a contract already at the target status+dates is a no-op.
  * Every change writes a Contract UPDATE AuditLog row with before/after.
  * No database migration; pure data correction on an existing field.

Verified-file format (JSON):
    {
      "HK-CT26419": {"start_date": "2026-07-29", "end_date": "2027-07-28"},
      "HK-CT26282": {"start_date": "2026-07-29", "end_date": "2027-07-28",
                     "status": "Active", "note": "invoice HK250169"}
    }
  - status is optional (default "Active"; use "Renewed" if a live replacement
    contract already supersedes this one).
  - start_date/end_date are optional; if omitted the contract's current dates
    are kept (use when only the status needs correcting).

Usage:
    python manage.py reconcile_false_expiry --verified-file verified.json          # dry-run
    python manage.py reconcile_false_expiry --verified-file verified.json --execute
    python manage.py reconcile_false_expiry --verified-file verified.json --execute --limit 10
"""
import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm_app.models import AuditLog, Contract

IMPORT_NOTE_SIGNATURE = "Imported from Kent performance metrics"
ALLOWED_TARGET_STATUSES = {"Active", "Renewed"}
# Only these current statuses may be corrected by this command. It exists to
# reverse a FALSE expiry — never to reactivate a genuinely cancelled contract.
CORRECTABLE_FROM = {"Expired"}


def _parse_date(value, field, cn):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise CommandError(f"{cn}: bad {field} {value!r} (want YYYY-MM-DD)") from exc


class Command(BaseCommand):
    help = "Reconcile Kent-2025-import false-Expired contracts from a human-verified allowlist (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verified-file", required=True,
            help="JSON allowlist {contract_number: {start_date?, end_date?, status?, note?}} of Theo-verified LIVE contracts.",
        )
        parser.add_argument(
            "--execute", action="store_true",
            help="Apply the corrections. Without this flag the command only reports what it would do.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Safety cap: process at most N contracts (0 = no cap).",
        )

    def handle(self, *args, **opts):
        path = opts["verified_file"]
        execute = opts["execute"]
        limit = opts["limit"]

        try:
            with open(path, encoding="utf-8") as fh:
                verified = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"cannot read verified-file {path}: {exc}") from exc
        if not isinstance(verified, dict) or not verified:
            raise CommandError("verified-file must be a non-empty JSON object keyed by contract_number.")

        mode = "EXECUTE" if execute else "DRY-RUN"
        self.stdout.write(f"reconcile_false_expiry [{mode}] — {len(verified)} verified contract(s)")

        planned = skipped = changed = missing = refused = 0

        for cn in sorted(verified):
            if limit and planned >= limit:
                self.stdout.write(f"  … limit {limit} reached; stopping.")
                break
            spec = verified[cn] or {}
            target_status = spec.get("status", "Active")
            if target_status not in ALLOWED_TARGET_STATUSES:
                raise CommandError(f"{cn}: target status {target_status!r} not in {sorted(ALLOWED_TARGET_STATUSES)}")
            new_start = _parse_date(spec.get("start_date"), "start_date", cn)
            new_end = _parse_date(spec.get("end_date"), "end_date", cn)

            qs = list(Contract.objects.filter(contract_number=cn))
            if not qs:
                self.stdout.write(f"  [MISSING] {cn}: no such contract"); missing += 1; continue
            if len(qs) > 1:
                self.stdout.write(f"  [MISSING] {cn}: {len(qs)} contracts share this number — skipping, needs a human"); missing += 1; continue
            c = qs[0]

            # Guard: only correct a FALSE expiry. Never touch a non-Expired or
            # (implicitly) a Cancelled contract via this tool.
            if c.status not in CORRECTABLE_FROM:
                if c.status == target_status:
                    self.stdout.write(f"  [OK] {cn}: already {c.status} — no-op"); skipped += 1
                else:
                    self.stdout.write(f"  [REFUSED] {cn}: current status {c.status!r} is not a correctable false-expiry"); refused += 1
                continue

            before = {"status": c.status, "start_date": str(c.start_date),
                      "end_date": str(c.end_date), "notes": c.notes}
            fields = ["status"]
            c.status = target_status
            if new_start and new_start != c.start_date:
                c.start_date = new_start; fields.append("start_date")
            if new_end and new_end != c.end_date:
                c.end_date = new_end; fields.append("end_date")
            if c.notes and IMPORT_NOTE_SIGNATURE in c.notes:
                c.notes = ""; fields.append("notes")

            after = {"status": c.status, "start_date": str(c.start_date),
                     "end_date": str(c.end_date), "notes": c.notes}
            planned += 1
            self.stdout.write(
                f"  [{'FIX' if execute else 'WOULD-FIX'}] {cn}: "
                f"status {before['status']}->{after['status']}, "
                f"dates {before['start_date']}..{before['end_date']} -> {after['start_date']}..{after['end_date']}"
                + (", note scrubbed" if 'notes' in fields else "")
            )
            if not execute:
                continue

            with transaction.atomic():
                c.save(update_fields=fields)
                AuditLog.objects.create(
                    user=None,
                    action="UPDATE",
                    model_name="Contract",
                    record_id=str(c.id),
                    changes={k: {"from": before[k], "to": after[k]} for k in ("status", "start_date", "end_date", "notes") if before[k] != after[k]},
                    additional_data={
                        "source": "reconcile_false_expiry",
                        "reason": "Kent-2025-import false-Expired correction",
                        "authorization": "Norbert-approved 2026-08-22",
                        "incident": "INC-20260622-0e6b59",
                        "verified_by": "theo",
                        "verified_note": spec.get("note", ""),
                    },
                )
            changed += 1

        self.stdout.write(
            f"\nsummary [{mode}]: planned={planned} changed={changed} "
            f"already-ok={skipped} missing={missing} refused={refused}"
        )
        if not execute and planned:
            self.stdout.write("re-run with --execute to apply.")
