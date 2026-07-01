"""
restore_kent_status — one-off, REVERSIBLE correction of the Kent-2025 calendar-year import that
falsely stamped live contracts as status=Expired / end_date=2025-12-31
(INC-20260622-0e6b59 / e7137c). This is the mechanism Cira is architecturally barred from
(Expired→Active is terminal in her state machine); it is a direct, audited, undoable ORM correction
that runs ONLY against an explicit human-approved list.

Safety model:
  • DRY-RUN by default — prints every intended change and writes nothing.
  • --apply performs the writes inside one transaction AND emits a revert journal (the before-values).
  • Each contract is guarded: it must still be in the Kent shape (status=Expired, end_date=2025-12-31)
    or it is skipped (override with --force). This prevents clobbering anything already corrected.
  • --revert <journal> --apply restores the captured before-values (full undo).

Approved-list schema (list of objects; only the set_* keys you include are applied):
  [
    {"contract_number": "HK-CT26282", "set_status": "Active",
     "set_start_date": "2026-01-01", "set_end_date": "2026-12-31",
     "note": "funnel: Citadines Republique Paris, ASCOTT EU, live 2026"},
    ...
  ]

Usage:
  python manage.py restore_kent_status --list approved.json                  # preview (dry-run)
  python manage.py restore_kent_status --list approved.json --apply          # write + revert journal
  python manage.py restore_kent_status --revert revert-kent-YYYYMMDD-HHMMSS.json --apply   # undo
"""
from __future__ import annotations
import json
import os
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm_app.models import Contract

KENT_END = "2025-12-31"
SETTABLE = {"set_status": "status", "set_end_date": "end_date", "set_start_date": "start_date"}
DATE_FIELDS = {"end_date", "start_date"}


class Command(BaseCommand):
    help = ("Reversibly restore Kent-2025 false-Expired contracts from an approved list "
            "(dry-run by default; --apply writes + emits a revert journal).")

    def add_arguments(self, parser):
        parser.add_argument("--list", help="approved corrections JSON (list of {contract_number|contract_id, set_status, set_end_date, set_start_date, note})")
        parser.add_argument("--revert", help="a revert journal from a prior --apply run (restores the before-values)")
        parser.add_argument("--apply", action="store_true", help="actually write (default: dry-run, writes nothing)")
        parser.add_argument("--force", action="store_true", help="apply even if a contract's current state != the Kent shape")
        parser.add_argument("--journal-dir", default=".", help="directory to write the revert journal into")

    def handle(self, *args, **opts):
        revert_path = opts.get("revert")
        if revert_path:
            items = json.load(open(revert_path))
            self.stdout.write(self.style.WARNING(f"REVERT mode: {len(items)} entries from {revert_path}"))
            self._run(items, apply=opts["apply"], force=True, journal_dir=opts["journal_dir"], is_revert=True)
            return
        list_path = opts.get("list")
        if not list_path:
            self.stderr.write(self.style.ERROR("Provide --list <approved.json>  (or --revert <journal.json>)."))
            return
        items = json.load(open(list_path))
        self.stdout.write(f"Loaded {len(items)} approved corrections from {list_path}")
        self._run(items, apply=opts["apply"], force=opts["force"], journal_dir=opts["journal_dir"], is_revert=False)

    def _resolve(self, item):
        cn, cid = item.get("contract_number"), item.get("contract_id")
        if cn:
            return Contract.objects.get(contract_number=cn)
        return Contract.objects.get(id=cid)

    def _run(self, items, apply, force, journal_dir, is_revert):
        journal, applied, skipped, previewed = [], 0, 0, 0
        with transaction.atomic():
            for item in items:
                ident = item.get("contract_number") or item.get("contract_id")
                try:
                    c = self._resolve(item)
                except Contract.DoesNotExist:
                    self.stderr.write(self.style.ERROR(f"SKIP missing: {ident}"))
                    skipped += 1
                    continue

                # guard: only touch contracts still in the Kent shape (forward corrections only)
                if not is_revert and not force:
                    if not (str(c.status) == "Expired" and str(c.end_date) == KENT_END):
                        self.stderr.write(self.style.WARNING(
                            f"SKIP {c.contract_number}: current status={c.status} end={c.end_date} "
                            f"!= Kent shape (Expired / {KENT_END}); use --force to override"))
                        skipped += 1
                        continue

                before, changes = {}, {}
                for src, dst in SETTABLE.items():
                    val = item.get(src)
                    if val in (None, ""):
                        continue
                    before[dst] = str(getattr(c, dst))
                    changes[dst] = date.fromisoformat(val) if dst in DATE_FIELDS else val
                if not changes:
                    continue

                summary = ", ".join(f"{k}: {before[k]} -> {v}" for k, v in changes.items())
                self.stdout.write(f"[{'APPLY' if apply else 'DRY '}] {c.contract_number} | {c.company.name} | {summary}")
                if apply:
                    for k, v in changes.items():
                        setattr(c, k, v)
                    c.save()
                    journal.append({"contract_number": c.contract_number,
                                    **{f"set_{k}": before[k] for k in changes}})
                    applied += 1
                else:
                    previewed += 1

        if apply and journal and not is_revert:
            jp = os.path.join(journal_dir, f"revert-kent-{timezone.now():%Y%m%d-%H%M%S}.json")
            json.dump(journal, open(jp, "w"), indent=1)
            self.stdout.write(self.style.SUCCESS(f"\nAPPLIED {applied}, skipped {skipped}. Revert journal: {jp}"))
            self.stdout.write(f"Undo with:  python manage.py restore_kent_status --revert {jp} --apply")
        elif apply and is_revert:
            self.stdout.write(self.style.SUCCESS(f"\nREVERTED {applied}, skipped {skipped}."))
        else:
            self.stdout.write(f"\nDRY-RUN complete: {previewed} would change, {skipped} skipped. Add --apply to write.")
