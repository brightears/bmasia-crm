"""Cara care-touch and care-summary writes: auth, switch, validation, idempotency, audit.

Synthetic data only. Runs in the standard CRM suite (SQLite and PostgreSQL).
"""
import hashlib
import json
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from mcp_server.djangomcp import django_request_ctx
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from crm_app import cara_api, cara_care_writes
from crm_app.mcp import update_record
from crm_app.models import AuditLog, CareTouch, Company, Contact, Contract
from crm_app.services.care_touches import revert_backfill_batch

TOKEN = "synthetic_cara_write_test_" + "x" * 32
DIGEST = hashlib.sha256(TOKEN.encode()).hexdigest()
TOUCHES = "/api/v1/cara/touches/"
CAPABILITIES = "/api/v1/cara/capabilities/"
MAILBOX = "care@example.test"
SUMMARY_TEXT = "Synthetic check-in, all fine"


def summary_path(company_id):
    return f"/api/v1/cara/companies/{company_id}/care-summary/"


@pytest.fixture(autouse=True)
def cara_settings():
    with override_settings(
        CARA_CUSTOMER_CARE_TOKEN_SHA256=DIGEST,
        CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT="never",
        CARA_CARE_WRITES_ENABLED=True,
    ):
        yield


def cara(token=TOKEN):
    client = APIClient()
    if token is not None:
        client.credentials(HTTP_AUTHORIZATION="Bearer " + token, HTTP_USER_AGENT="synthetic-agent")
    return client


@pytest.fixture
def company():
    return Company.objects.create(name="Example Hotel")


@pytest.fixture
def contact(company):
    return Contact.objects.create(
        company=company, name="Example Contact", email="contact@example.test", is_primary=True,
    )


def body(company, **overrides):
    data = {
        "idempotency_key": "send:example-0001",
        "company_id": str(company.pk),
        "mailbox": MAILBOX,
        "gmail_thread_id": "thread0001",
        "gmail_message_id": "message0001",
        "occurred_at": (timezone.now() - timedelta(hours=1)).isoformat(),
        "kind": "check_in",
        "outcome": "none",
        "summary": SUMMARY_TEXT,
        "source": "send",
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not ...}


def post(payload, client=None, path=TOUCHES):
    return (client or cara()).post(path, payload, format="json")


def _user(username="website-user"):
    return get_user_model().objects.create_user(
        username=username, email=f"{username}@example.test", password="x", role="Admin",
    )


# ------------------------------------------------------------- auth and switch

def test_writes_disabled_returns_403(company):
    with override_settings(CARA_CARE_WRITES_ENABLED=False):
        response = post(body(company))
        assert response.status_code == 403
        assert response.data["detail"] == "Cara care writes are disabled"
        put = cara().put(summary_path(company.pk), {"care_summary": "x", "expected_updated_at": None}, format="json")
        assert put.status_code == 403
    assert CareTouch.objects.count() == 0


@pytest.mark.parametrize("token", [None, "", "bad", "y" * 64])
def test_missing_or_wrong_bearer_is_401(company, token):
    response = post(body(company), client=cara(token))
    assert response.status_code == 401
    assert CareTouch.objects.count() == 0


def test_drf_token_and_jwt_users_cannot_post(company):
    user = _user()
    token = Token.objects.create(user=user)
    by_token = APIClient()
    by_token.credentials(HTTP_AUTHORIZATION="Token " + token.key)
    assert post(body(company), client=by_token).status_code == 401
    by_jwt = APIClient()
    by_jwt.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user).access_token))
    assert post(body(company), client=by_jwt).status_code == 401
    session = APIClient()
    session.force_login(user)
    assert post(body(company), client=session).status_code == 401
    assert CareTouch.objects.count() == 0


def test_wrong_method_is_refused(company):
    assert cara().get(TOUCHES).status_code in (403, 405)
    assert cara().put(TOUCHES, body(company), format="json").status_code in (403, 405)
    assert cara().post(summary_path(company.pk), {}, format="json").status_code in (403, 405)


def test_responses_are_private_no_store(company):
    response = post(body(company))
    assert response.status_code == 201
    assert response["Cache-Control"] == "no-store, private"
    assert response["X-Content-Type-Options"] == "nosniff"


# ------------------------------------------------------------- validation

def test_unknown_key_and_query_params_are_400(company):
    assert post(body(company, extra="x")).status_code == 400
    assert post(body(company), path=TOUCHES + "?dry_run=1").status_code == 400
    assert CareTouch.objects.count() == 0


def test_contact_of_another_company_is_400(company):
    other = Company.objects.create(name="Other Example Hotel")
    foreign = Contact.objects.create(company=other, name="Other", email="other@example.test")
    response = post(body(company, contact_id=str(foreign.pk)))
    assert response.status_code == 400
    assert "contact_id" in response.data["detail"]


@pytest.mark.parametrize(
    "occurred_at",
    [
        "2026-11-01T10:00:00",  # naive
        "not-a-date",
        "far-future",
    ],
)
def test_naive_invalid_or_far_future_occurred_at_is_400(company, occurred_at):
    if occurred_at == "far-future":
        occurred_at = (timezone.now() + timedelta(minutes=11)).isoformat()
    assert post(body(company, occurred_at=occurred_at)).status_code == 400


def test_small_clock_skew_is_accepted(company):
    occurred = (timezone.now() + timedelta(minutes=5)).isoformat()
    assert post(body(company, occurred_at=occurred)).status_code == 201


@pytest.mark.parametrize("summary", ["line one\nline two", "tab\there", "x" * 501, "sep x"])
def test_bad_summary_is_400(company, summary):
    assert post(body(company, summary=summary)).status_code == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"idempotency_key": "short"},
        {"idempotency_key": "has space key"},
        {"idempotency_key": ...},
        {"company_id": "00000000-0000-0000-0000-000000000001"},
        {"company_id": "not-a-uuid"},
        {"mailbox": "not-an-email"},
        {"kind": "visit"},
        {"outcome": "great"},
        {"source": "manual"},
        {"source": ...},
        {"gmail_message_id": "has space"},
        {"gmail_thread_id": "t" * 65},
        {"summary": 5},
    ],
)
def test_field_validation_is_400(company, overrides):
    assert post(body(company, **overrides)).status_code == 400
    assert CareTouch.objects.count() == 0


def test_backfill_requires_batch_and_send_forbids_it(company):
    assert post(body(company, source="gmail_backfill")).status_code == 400
    assert post(body(company, source="gmail_backfill", backfill_batch="bad batch")).status_code == 400
    assert post(body(company, backfill_batch="batch-1")).status_code == 400
    assert CareTouch.objects.count() == 0


# ------------------------------------------------------------- create and contact side effect

def test_create_moves_last_contacted_forward_only(company, contact):
    before = timezone.now() - timedelta(days=30)
    Contact.objects.filter(pk=contact.pk).update(last_contacted=before)
    occurred = timezone.now() - timedelta(hours=2)
    response = post(body(company, contact_id=str(contact.pk), occurred_at=occurred.isoformat()))
    assert response.status_code == 201
    data = response.data
    assert data["replayed"] is False
    assert data["contact_last_contacted_updated"] is True
    assert data["quarterly_owner"] == "legacy"
    assert data["contact_id"] == str(contact.pk)
    assert data["mailbox"] == MAILBOX
    touch = CareTouch.objects.get()
    assert touch.updated_last_contacted is True
    assert touch.previous_last_contacted == before
    assert touch.recorded_by == "cara"
    contact.refresh_from_db()
    assert contact.last_contacted == occurred

    older = post(body(
        company, idempotency_key="send:example-0002", gmail_message_id="message0002",
        contact_id=str(contact.pk), occurred_at=(occurred - timedelta(days=3)).isoformat(),
    ))
    assert older.status_code == 201
    assert older.data["contact_last_contacted_updated"] is False
    assert older.data["previous_last_contacted"] is None
    contact.refresh_from_db()
    assert contact.last_contacted == occurred


def test_first_check_in_sets_null_last_contacted(company, contact):
    response = post(body(company, contact_id=str(contact.pk)))
    assert response.status_code == 201
    assert response.data["contact_last_contacted_updated"] is True
    touch = CareTouch.objects.get()
    assert touch.previous_last_contacted is None
    contact.refresh_from_db()
    assert contact.last_contacted is not None


def test_client_reply_does_not_move_last_contacted(company, contact):
    response = post(body(company, contact_id=str(contact.pk), kind="client_reply"))
    assert response.status_code == 201
    assert response.data["contact_last_contacted_updated"] is False
    contact.refresh_from_db()
    assert contact.last_contacted is None


def test_backfill_never_changes_the_contact(company, contact):
    response = post(body(
        company, contact_id=str(contact.pk), source="gmail_backfill", backfill_batch="bf:2026-11",
    ))
    assert response.status_code == 201
    assert response.data["contact_last_contacted_updated"] is False
    assert response.data["backfill_batch"] == "bf:2026-11"
    contact.refresh_from_db()
    assert contact.last_contacted is None


def test_optional_fields_can_be_omitted(company):
    payload = body(company, gmail_thread_id=..., gmail_message_id=..., outcome=..., summary=...)
    response = post(payload)
    assert response.status_code == 201
    assert response.data["outcome"] == "none"
    assert response.data["gmail_message_id"] == ""
    # Empty Gmail ids never collide with each other.
    second = post(body(company, idempotency_key="send:example-0003", gmail_thread_id=...,
                       gmail_message_id=..., outcome=..., summary=...))
    assert second.status_code == 201


# ------------------------------------------------------------- idempotency

def test_replay_same_payload_is_200_without_second_row(company, contact):
    payload = body(company, contact_id=str(contact.pk))
    first = post(payload)
    assert first.status_code == 201
    replay = post(payload)
    assert replay.status_code == 200
    assert replay.data["replayed"] is True
    assert replay.data["id"] == first.data["id"]
    assert replay.data["contact_last_contacted_updated"] is True
    assert CareTouch.objects.count() == 1
    assert AuditLog.objects.filter(model_name="CareTouch").count() == 1


def test_same_key_different_payload_is_409(company):
    assert post(body(company)).status_code == 201
    response = post(body(company, summary="Different synthetic line"))
    assert response.status_code == 409
    assert response.data["detail"] == "idempotency_key reused with a different payload"
    assert CareTouch.objects.count() == 1


def test_same_gmail_message_under_another_key_is_409(company):
    first = post(body(company))
    response = post(body(company, idempotency_key="send:example-other"))
    assert response.status_code == 409
    assert response.data["existing_touch_id"] == first.data["id"]
    # The mailbox is compared case-insensitively.
    upper = post(body(company, idempotency_key="send:example-upper", mailbox="CARE@example.test"))
    assert upper.status_code == 409
    assert CareTouch.objects.count() == 1


def test_integrity_error_race_is_resolved_by_re_reading(company):
    payload = body(company)
    assert post(payload).status_code == 201
    real = cara_care_writes._existing_outcome
    calls = {"n": 0}

    def blind_then_real(*args, **kwargs):
        calls["n"] += 1
        return None if calls["n"] <= 2 else real(*args, **kwargs)

    with mock.patch.object(cara_care_writes, "_existing_outcome", side_effect=blind_then_real):
        replay = post(payload)
    assert replay.status_code == 200
    assert replay.data["replayed"] is True
    with mock.patch.object(cara_care_writes, "_existing_outcome", side_effect=blind_then_real):
        calls["n"] = 0
        clash = post(body(company, idempotency_key="send:example-race"))
    assert clash.status_code == 409
    assert CareTouch.objects.count() == 1


# ------------------------------------------------------------- audit

def test_audit_rows_hold_no_summary_or_email(company, contact):
    assert post(body(company, contact_id=str(contact.pk))).status_code == 201
    put = cara().put(summary_path(company.pk),
                     {"care_summary": "Synthetic summary text", "expected_updated_at": None}, format="json")
    assert put.status_code == 200
    rows = list(AuditLog.objects.all())
    assert {(row.action, row.model_name) for row in rows} == {("CREATE", "CareTouch"), ("UPDATE", "Company")}
    for row in rows:
        assert row.user is None
        assert row.ip_address == "127.0.0.1"
        dump = json.dumps([row.changes, row.additional_data, row.record_id])
        assert "@" not in dump
        assert SUMMARY_TEXT not in dump and "Synthetic summary text" not in dump
        assert row.additional_data["auth_method"] == "cara_bearer"
        assert row.additional_data["principal"] == "cara"
    create = AuditLog.objects.get(action="CREATE")
    assert create.additional_data["source"] == "send"
    assert create.additional_data["kind"] == "check_in"
    assert create.additional_data["contact_last_contacted_updated"] is True
    update = AuditLog.objects.get(action="UPDATE")
    assert update.additional_data["field"] == "care_summary"
    assert update.additional_data["length_before"] == 0
    assert update.additional_data["length_after"] == len("Synthetic summary text")


# ------------------------------------------------------------- care summary

def test_care_summary_first_write_then_optimistic_lock(company):
    first = cara().put(summary_path(company.pk),
                       {"care_summary": "Line one\nLine two", "expected_updated_at": None}, format="json")
    assert first.status_code == 200
    assert first.data["company_id"] == str(company.pk)
    assert first.data["care_summary"] == "Line one\nLine two"
    assert first.data["care_summary_updated_by"] == "cara"
    stamp = first.data["care_summary_updated_at"]

    stale = cara().put(summary_path(company.pk),
                       {"care_summary": "Other", "expected_updated_at": None}, format="json")
    assert stale.status_code == 409
    assert stale.data["care_summary_updated_at"] == stamp

    second = cara().put(summary_path(company.pk),
                        {"care_summary": "Updated", "expected_updated_at": stamp}, format="json")
    assert second.status_code == 200
    company.refresh_from_db()
    assert company.care_summary == "Updated"
    assert company.care_summary_updated_by == "cara"

    old = cara().put(summary_path(company.pk),
                     {"care_summary": "Late", "expected_updated_at": stamp}, format="json")
    assert old.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"care_summary": "x" * 2001, "expected_updated_at": None},
        {"care_summary": "tab\there", "expected_updated_at": None},
        {"care_summary": "x"},
        {"care_summary": "x", "expected_updated_at": None, "extra": 1},
        {"care_summary": 5, "expected_updated_at": None},
        {"care_summary": "x", "expected_updated_at": "2026-11-01T10:00:00"},
    ],
)
def test_care_summary_validation_is_400(company, payload):
    assert cara().put(summary_path(company.pk), payload, format="json").status_code == 400
    company.refresh_from_db()
    assert company.care_summary == ""


def test_care_summary_unknown_company_is_404():
    response = cara().put(summary_path("00000000-0000-0000-0000-000000000001"),
                          {"care_summary": "x", "expected_updated_at": None}, format="json")
    assert response.status_code == 404


def test_care_summary_query_params_are_400(company):
    response = cara().put(summary_path(company.pk) + "?x=1",
                          {"care_summary": "x", "expected_updated_at": None}, format="json")
    assert response.status_code == 400


# ------------------------------------------------------------- website and MCP stay read-only

def test_website_patch_cannot_change_care_summary(company):
    Company.objects.filter(pk=company.pk).update(care_summary="Kept", care_summary_updated_by="cara")
    client = APIClient()
    client.force_authenticate(_user())
    response = client.patch(
        f"/api/v1/companies/{company.pk}/",
        {"care_summary": "Overwritten", "care_summary_updated_by": "someone", "phone": "+6600000000"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["care_summary"] == "Kept"
    company.refresh_from_db()
    assert company.care_summary == "Kept"
    assert company.care_summary_updated_by == "cara"
    assert company.phone == "+6600000000"


@contextmanager
def as_caller(user):
    token = django_request_ctx.set(SimpleNamespace(user=user))
    try:
        yield
    finally:
        django_request_ctx.reset(token)


def test_mcp_update_record_cannot_change_care_summary(company):
    Company.objects.filter(pk=company.pk).update(care_summary="Kept")
    with as_caller(_user("cira")):
        update_record("company", str(company.pk), json.dumps({"care_summary": "Overwritten", "city": "Example City"}))
    company.refresh_from_db()
    assert company.care_summary == "Kept"
    assert company.city == "Example City"


def test_care_touches_action_for_logged_in_user(company):
    other = Company.objects.create(name="Other Example Hotel")
    for index in range(22):
        assert post(body(
            company, idempotency_key=f"send:example-{index:04d}", gmail_message_id=f"message-{index}",
            occurred_at=(timezone.now() - timedelta(days=index + 1)).isoformat(),
        )).status_code == 201
    assert post(body(other, idempotency_key="send:other-0001", gmail_message_id="other-1")).status_code == 201
    client = APIClient()
    client.force_authenticate(_user())
    response = client.get(f"/api/v1/companies/{company.pk}/care-touches/")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 20
    assert all(row["company_id"] == str(company.pk) for row in rows)
    assert rows[0]["occurred_at"] > rows[-1]["occurred_at"]
    assert APIClient().get(f"/api/v1/companies/{company.pk}/care-touches/").status_code == 401
    assert client.post(f"/api/v1/companies/{company.pk}/care-touches/", {}, format="json").status_code == 405


# ------------------------------------------------------------- read projection and capabilities

def _active_contract(company, **overrides):
    today = timezone.now().date()
    values = dict(
        company=company, contract_number=f"EXAMPLE-{company.pk}", status="Active",
        start_date=today - timedelta(days=100), end_date=today + timedelta(days=100),
        value=0, contract_type="Annual", service_type="soundtrack_essential_yearly",
    )
    values.update(overrides)
    Contract.objects.bulk_create([Contract(**values)])


def test_projection_contains_care_fields(company, contact):
    _active_contract(company)
    _active_contract(company, contract_number="EXAMPLE-OLD", end_date=date(2020, 1, 1),
                     start_date=date(2019, 1, 1))
    row = cara_api.project_company(company, timezone.now())
    assert row["care_summary"] is None
    assert row["care_summary_updated_at"] is None
    assert row["last_care_touch"] is None
    assert row["last_care_check_in"] is None
    assert sorted(item["current_by_date"] for item in row["contracts"]) == [False, True]
    first_hash = row["evidence_sha256"]

    newest_check_in = timezone.now() - timedelta(days=2)
    post(body(company, contact_id=str(contact.pk), occurred_at=newest_check_in.isoformat()))
    post(body(company, idempotency_key="reply:example-0001", gmail_message_id="reply0001",
              kind="client_reply", outcome="all_good", occurred_at=(timezone.now() - timedelta(hours=1)).isoformat()))
    cara().put(summary_path(company.pk), {"care_summary": "Synthetic", "expected_updated_at": None}, format="json")
    company.refresh_from_db()

    row = cara_api.project_company(company, timezone.now())
    assert row["care_summary"] == "Synthetic"
    assert row["care_summary_updated_at"] is not None
    assert row["last_care_touch"]["kind"] == "client_reply"
    assert row["last_care_touch"]["outcome"] == "all_good"
    assert row["last_care_check_in"]["kind"] == "check_in"
    assert row["last_care_check_in"]["contact_id"] == str(contact.pk)
    assert set(row["last_care_touch"]) == {
        "id", "occurred_at", "kind", "outcome", "source", "contact_id", "mailbox",
        "gmail_thread_id", "summary",
    }
    assert row["evidence_sha256"] != first_hash

    response = cara().get("/api/v1/cara/customer-care/")
    assert response.status_code == 200
    account = response.data["accounts"][0]
    assert account["last_care_check_in"]["id"] == row["last_care_check_in"]["id"]


def test_capabilities_reflect_the_switch():
    with override_settings(CARA_CARE_WRITES_ENABLED=False):
        off = cara().get(CAPABILITIES)
        assert off.status_code == 200
        assert off.data["care_writes_enabled"] is False
        assert off.data["permissions"] == [cara_api.PERMISSION]
        assert off.data["allowed_methods"] == ["GET"]
        assert off.data["allowed_paths"] == [cara_api.CAPABILITY_PATH, cara_api.BOOK_PATH]
    on = cara().get(CAPABILITIES)
    assert on.data["care_writes_enabled"] is True
    assert on.data["permissions"] == [
        cara_api.PERMISSION, "customer_care.touch.write", "customer_care.summary.write",
    ]
    assert on.data["allowed_methods"] == ["GET", "POST", "PUT"]
    assert on.data["allowed_paths"] == [
        cara_api.CAPABILITY_PATH, cara_api.BOOK_PATH,
        "/api/v1/cara/touches/", "/api/v1/cara/companies/{company_id}/care-summary/",
    ]


def test_read_endpoints_stay_get_only_with_writes_enabled(company):
    assert cara().post(CAPABILITIES, {}, format="json").status_code in (403, 405)
    assert cara().post("/api/v1/cara/customer-care/", {}, format="json").status_code in (403, 405)


# ------------------------------------------------------------- revert helper

def test_revert_backfill_batch_dry_run_then_execute(company, contact):
    for index in range(3):
        assert post(body(company, idempotency_key=f"bf:a-{index:04d}", gmail_message_id=f"a-{index}",
                         source="gmail_backfill", backfill_batch="batch-a")).status_code == 201
    assert post(body(company, idempotency_key="bf:b-0001", gmail_message_id="b-1",
                     source="gmail_backfill", backfill_batch="batch-b")).status_code == 201
    assert post(body(company, idempotency_key="send:keep-0001", gmail_message_id="keep-1",
                     contact_id=str(contact.pk))).status_code == 201
    audit_before = AuditLog.objects.count()

    dry = revert_backfill_batch("batch-a")
    assert dry == {"batch": "batch-a", "execute": False, "matched": 3, "deleted": 0}
    assert CareTouch.objects.count() == 5
    assert AuditLog.objects.count() == audit_before

    done = revert_backfill_batch("batch-a", execute=True)
    assert done["deleted"] == 3 and done["matched"] == 3
    assert set(CareTouch.objects.values_list("backfill_batch", flat=True)) == {"batch-b", ""}
    row = AuditLog.objects.get(action="DELETE")
    assert row.model_name == "CareTouch"
    assert row.record_id == "batch:batch-a"
    assert row.additional_data["count"] == 3
    with pytest.raises(ValueError):
        revert_backfill_batch("")
