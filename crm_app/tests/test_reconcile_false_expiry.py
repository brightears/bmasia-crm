"""Tests for the reconcile_false_expiry management command."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from crm_app.models import AuditLog, Contract
from crm_app.tests.factories import ContractFactory

PLACEHOLDER_START = date(2025, 1, 1)
PLACEHOLDER_END = date(2025, 12, 31)
REAL_START = date(2026, 7, 29)
REAL_END = date(2027, 7, 28)


def _false_expired(contract_number, notes="Imported from Kent performance metrics 2025"):
    return ContractFactory(
        contract_number=contract_number,
        status="Expired",
        start_date=PLACEHOLDER_START,
        end_date=PLACEHOLDER_END,
        notes=notes,
    )


def _write(tmp_path, mapping):
    p = tmp_path / "verified.json"
    p.write_text(json.dumps(mapping))
    return str(p)


def _run(**kwargs):
    out = StringIO()
    call_command("reconcile_false_expiry", stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.django_db
def test_dry_run_makes_no_change(tmp_path):
    c = _false_expired("HK-CT26419")
    vf = _write(tmp_path, {"HK-CT26419": {"start_date": "2026-07-29", "end_date": "2027-07-28"}})
    out = _run(verified_file=vf)  # no --execute
    assert "WOULD-FIX" in out and "DRY-RUN" in out
    c.refresh_from_db()
    assert c.status == "Expired"
    assert c.start_date == PLACEHOLDER_START
    assert AuditLog.objects.filter(record_id=str(c.id)).count() == 0


@pytest.mark.django_db
def test_execute_fixes_status_dates_notes_and_audits(tmp_path):
    c = _false_expired("HK-CT26419")
    vf = _write(tmp_path, {"HK-CT26419": {"start_date": "2026-07-29", "end_date": "2027-07-28"}})
    _run(verified_file=vf, execute=True)
    c.refresh_from_db()
    assert c.status == "Active"
    assert c.start_date == REAL_START and c.end_date == REAL_END
    assert c.notes == ""  # import note scrubbed
    logs = AuditLog.objects.filter(record_id=str(c.id), model_name="Contract", action="UPDATE")
    assert logs.count() == 1
    ad = logs.first().additional_data
    assert ad["source"] == "reconcile_false_expiry"
    assert logs.first().changes["status"] == {"from": "Expired", "to": "Active"}


@pytest.mark.django_db
def test_idempotent_second_run_is_noop(tmp_path):
    c = _false_expired("HK-CT26419")
    vf = _write(tmp_path, {"HK-CT26419": {"start_date": "2026-07-29", "end_date": "2027-07-28"}})
    _run(verified_file=vf, execute=True)
    out = _run(verified_file=vf, execute=True)
    assert "already Active" in out or "already-ok=1" in out
    assert AuditLog.objects.filter(record_id=str(c.id)).count() == 1  # no second audit row


@pytest.mark.django_db
def test_status_only_correction_keeps_dates(tmp_path):
    # Republique case: dates already fixed earlier, only status needs flipping.
    c = ContractFactory(contract_number="HK-CT26282", status="Expired",
                        start_date=REAL_START, end_date=REAL_END, notes="")
    vf = _write(tmp_path, {"HK-CT26282": {}})  # no dates supplied
    _run(verified_file=vf, execute=True)
    c.refresh_from_db()
    assert c.status == "Active"
    assert c.start_date == REAL_START and c.end_date == REAL_END


@pytest.mark.django_db
def test_contract_not_in_allowlist_is_untouched(tmp_path):
    keep = _false_expired("HK-CT26419")
    other = _false_expired("HK-CT26999")
    vf = _write(tmp_path, {"HK-CT26419": {"start_date": "2026-07-29", "end_date": "2027-07-28"}})
    _run(verified_file=vf, execute=True)
    other.refresh_from_db()
    assert other.status == "Expired"  # not in the list -> never touched
    assert AuditLog.objects.filter(record_id=str(other.id)).count() == 0


@pytest.mark.django_db
def test_refuses_to_reactivate_a_cancelled_contract(tmp_path):
    c = ContractFactory(contract_number="HK-CT26500", status="Cancelled",
                        start_date=PLACEHOLDER_START, end_date=PLACEHOLDER_END)
    vf = _write(tmp_path, {"HK-CT26500": {"start_date": "2026-07-29", "end_date": "2027-07-28"}})
    out = _run(verified_file=vf, execute=True)
    c.refresh_from_db()
    assert c.status == "Cancelled"  # never reactivated
    assert "REFUSED" in out and "refused=1" in out


@pytest.mark.django_db
def test_limit_caps_the_number_processed(tmp_path):
    for n in (1, 2, 3):
        _false_expired(f"HK-CT2650{n}")
    vf = _write(tmp_path, {f"HK-CT2650{n}": {"start_date": "2026-07-29", "end_date": "2027-07-28"} for n in (1, 2, 3)})
    _run(verified_file=vf, execute=True, limit=1)
    fixed = Contract.objects.filter(contract_number__in=["HK-CT26501", "HK-CT26502", "HK-CT26503"], status="Active").count()
    assert fixed == 1
