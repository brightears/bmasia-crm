from __future__ import annotations

import ast
import hashlib
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from crm_app import cara_api as api
from crm_app.cara_ownership import legacy_quarterly_enabled, quarterly_owner
from crm_app.models import Company, Contact, Contract, EmailLog, Ticket

TOKEN = "synthetic_cara_test_" + "x" * 32
DIGEST = hashlib.sha256(TOKEN.encode()).hexdigest()
FACTORY = APIRequestFactory()


@pytest.fixture(autouse=True)
def credential_settings():
    with override_settings(
        CARA_CUSTOMER_CARE_TOKEN_SHA256=DIGEST,
        CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT=(
            timezone.now() + timedelta(days=7)
        ).isoformat(),
    ):
        yield


def request(view=api.CaraCapabilitiesView, method="get", query=None, token=TOKEN):
    factory = getattr(FACTORY, method)
    req = factory(
        "/api/v1/cara/customer-care/",
        data=query or {},
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    return view.as_view()(req)


def company(name="Synthetic Hotel", active=True, primary_count=1):
    current = Company.objects.create(name=name, is_active=active)
    for index in range(primary_count):
        Contact.objects.create(
            company=current,
            name=f"Synthetic Contact {index}",
            email=f"contact{index}@example.test",
            is_primary=True,
            contact_type="Primary",
        )
    Contract.objects.bulk_create(
        [
            Contract(
                company=current,
                contract_number="SYNTHETIC-" + str(current.id),
                status="Active",
                start_date=timezone.now().date() - timedelta(days=180),
                end_date=timezone.now().date() + timedelta(days=180),
                value=0,
                contract_type="Annual",
                service_type="soundtrack_essential_yearly",
            )
        ]
    )
    return current


def test_capability_is_dedicated_exact_and_no_store():
    response = request()
    assert response.status_code == 200
    assert response.data["subject"] == "cara"
    assert response.data["allowed_methods"] == ["GET"]
    assert response.data["permissions"] == [api.PERMISSION]
    assert response["Cache-Control"] == "no-store, private"
    assert TOKEN not in str(response.data)


@pytest.mark.parametrize("token", ["", "bad", "rene_" + "y" * 48, "a.b.c", "x" * 200])
def test_wrong_principal_does_not_receive_capability(token):
    assert request(token=token).status_code == 401


@pytest.mark.parametrize(
    "method", ["post", "put", "patch", "delete", "head", "options"]
)
def test_non_get_method_cannot_read_or_write(method):
    assert request(method=method).status_code in {403, 405}
    assert request(api.CaraCustomerCareView, method=method).status_code in {403, 405}


def test_generic_session_user_cannot_bypass_dedicated_auth():
    req = FACTORY.get("/api/v1/cara/capabilities/")
    req.user = type("Admin", (), {"is_authenticated": True, "is_superuser": True})()
    assert api.CaraCapabilitiesView.as_view()(req).status_code == 401


def test_expired_or_unconfigured_secret_denied():
    with override_settings(CARA_CUSTOMER_CARE_TOKEN_SHA256=""):
        assert request().status_code == 401
    with override_settings(CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT="2020-01-01T00:00:00Z"):
        assert request().status_code == 401


def test_projection_uses_real_model_preferences_and_excludes_private_data():
    current = company()
    current.notes = "internal private note"
    current.it_notes = "remote-access credentials must never be exposed"
    current.save()
    response = request(api.CaraCustomerCareView)
    assert response.status_code == 200
    assert response.data["complete"] is True
    record = response.data["accounts"][0]
    assert record["account_id"] == str(current.pk)
    assert record["contacts"][0]["receives_quarterly_emails"] is True
    assert record["primary_contact_id"] == record["contacts"][0]["id"]
    assert record["formal_renewal_activity"] == "UNKNOWN"
    assert record["cross_lane_coverage"] == "UNKNOWN"
    assert record["live_service_health"] == "UNKNOWN"
    assert "internal private note" not in str(response.data)
    assert "remote-access" not in str(response.data)
    assert len(record["evidence_sha256"]) == 64


def test_no_primary_guessing_and_opt_out_holds():
    current = company(primary_count=2)
    row = api.project_company(current, timezone.now())
    assert row["primary_contact_id"] is None
    assert "PRIMARY_CONTACT_MISSING_OR_AMBIGUOUS" in row["holds"]
    current.contacts.order_by("id").last().delete()
    current.contacts.update(receives_quarterly_emails=False)
    row = api.project_company(current, timezone.now())
    assert "CONTACT_QUARTERLY_EMAILS_DISABLED" in row["holds"]


def test_critical_ticket_count_is_not_hidden_by_record_cap():
    current = company()
    Ticket.objects.bulk_create(
        [
            Ticket(
                company=current,
                ticket_number=f"SYN-{index}",
                subject="private customer text",
                description="do not expose this body",
                priority="urgent",
                category="technical",
            )
            for index in range(26)
        ]
    )
    row = api.project_company(current, timezone.now())
    assert row["open_ticket_count"] == 26
    assert row["open_high_priority_ticket_count"] == 26
    assert len(row["open_tickets"]) == 25
    assert row["coverage"]["open_tickets_complete"] is False
    assert "OPEN_HIGH_PRIORITY_SUPPORT" in row["holds"]
    assert "do not expose" not in str(row)


def test_latest_crm_quarterly_receipt_is_preserved_not_a_gmail_send_claim():
    current = company()
    EmailLog.objects.bulk_create(
        [
            EmailLog(
                company=current,
                email_type="quarterly",
                from_email="noreply@example.test",
                to_email="contact@example.test",
                subject="private",
                body_text="private",
                body_html="private",
                status="sent",
                sent_at=timezone.now(),
            )
        ]
    )
    row = api.project_company(current, timezone.now())
    assert row["last_crm_quarterly_log"]["status"] == "sent"
    assert "body" not in row["last_crm_quarterly_log"]
    assert row["cross_lane_coverage"] == "UNKNOWN"


def test_paging_does_not_hide_inactive_company_with_active_contract():
    active = [company(f"Synthetic Hotel {index}") for index in range(3)]
    inactive = company("Inactive Company", active=False)
    Company.objects.create(name="Prospect Without Subscription")
    first = request(api.CaraCustomerCareView, query={"limit": "2"})
    assert not first.data["complete"]
    second = request(
        api.CaraCustomerCareView,
        query={"limit": "2", "after": first.data["next_after"]},
    )
    assert second.data["complete"]
    ids = [
        row["account_id"] for row in first.data["accounts"] + second.data["accounts"]
    ]
    assert ids == sorted(str(item.id) for item in [*active, inactive])
    record = api.project_company(inactive, timezone.now())
    assert "COMPANY_STATUS_CONTRADICTS_ACTIVE_SUBSCRIPTION" in record["holds"]


@pytest.mark.parametrize(
    "query",
    [
        {"limit": "51"},
        {"limit": "0"},
        {"limit": "01"},
        {"limit": "-1"},
        {"q": "arbitrary"},
        {"after": "not-a-uuid"},
        {"company_id": "bad"},
        {
            "company_id": "00000000-0000-0000-0000-000000000001",
            "after": "00000000-0000-0000-0000-000000000001",
        },
    ],
)
def test_invalid_or_expansive_queries_denied(query):
    assert request(api.CaraCustomerCareView, query=query).status_code == 400


def test_duplicate_query_values_and_capability_queries_denied():
    assert (
        request(api.CaraCustomerCareView, query={"limit": ["1", "50"]}).status_code
        == 400
    )
    assert request(query={"ignored": "query"}).status_code == 400


def test_exact_company_revalidation_does_not_return_other_accounts():
    current = company("Requested Synthetic Hotel")
    company("Other Synthetic Hotel")
    response = request(api.CaraCustomerCareView, query={"company_id": str(current.pk)})
    assert response.status_code == 200
    assert response.data["complete"] is True
    assert response.data["next_after"] is None
    assert [row["account_id"] for row in response.data["accounts"]] == [str(current.pk)]


def test_contact_and_contract_record_caps_preserve_coverage_gaps():
    current = company(primary_count=26)
    row = api.project_company(current, timezone.now())
    assert len(row["contacts"]) == 25
    assert row["primary_contact_id"] is None
    assert not row["coverage"]["contacts_complete"]
    assert "RELATED_RECORD_COVERAGE_INCOMPLETE" in row["holds"]


def test_stale_active_contract_is_visible_but_not_date_current():
    current = company()
    current.contracts.update(end_date=timezone.now().date() - timedelta(days=1))
    response = request(api.CaraCustomerCareView)
    row = response.data["accounts"][0]
    assert row["account_state"] == "REVIEW_REQUIRED"
    assert "CURRENT_SUBSCRIPTION_NOT_VERIFIED" in row["holds"]


def test_session_or_drf_token_header_is_not_a_cara_credential():
    req = FACTORY.get("/api/v1/cara/capabilities/", HTTP_AUTHORIZATION="Token " + TOKEN)
    assert api.CaraCapabilitiesView.as_view()(req).status_code == 401


@pytest.mark.parametrize("expiry", ["invalid", "2099-01-01T00:00:00", None, 7])
def test_malformed_credential_expiry_denied_without_response_data(expiry):
    with override_settings(CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT=expiry):
        response = request()
        assert response.status_code == 401
        assert TOKEN not in str(response.data)


def test_source_hash_is_stable_across_observation_time_but_changes_with_preferences():
    current = company()
    first = api.project_company(current, timezone.now())
    second = api.project_company(current, timezone.now() + timedelta(seconds=1))
    assert first["evidence_sha256"] == second["evidence_sha256"]
    current.contacts.update(unsubscribed=True)
    third = api.project_company(current, timezone.now())
    assert first["evidence_sha256"] != third["evidence_sha256"]


def test_cara_handover_is_enforced_not_an_expiring_credential_fallback():
    assert quarterly_owner() == "legacy"
    assert legacy_quarterly_enabled()
    with override_settings(CARA_QUARTERLY_OWNER="cara"):
        response = request()
        assert response.data["quarterly_owner"] == "cara"
        assert response.data["quarterly_owner_scope"] == "CRM_QUARTERLY_SENDERS_ONLY"
        assert not legacy_quarterly_enabled()
        with override_settings(
            CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT="2020-01-01T00:00:00Z"
        ):
            assert not legacy_quarterly_enabled()
            assert request().status_code == 401
    with override_settings(CARA_QUARTERLY_OWNER="typo"):
        assert quarterly_owner() == "invalid"
        assert not legacy_quarterly_enabled()


def _source_method(filename, method_name, namespace):
    """Execute the actual patched method, while stopping before business I/O."""
    source = Path(__file__).resolve().parents[2] / "crm_app/services" / filename
    tree = ast.parse(source.read_text())
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    ]
    assert len(candidates) == 1
    tree = ast.Module(body=candidates, type_ignores=[])
    context = {"Dict": dict, "logger": Mock(), **namespace}
    exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), context)
    return context[method_name]


def test_both_legacy_quarterly_entry_points_stop_before_queries_or_enrollment():
    direct = _source_method("email_service.py", "send_quarterly_checkins", {})
    enrollment = _source_method(
        "auto_enrollment_service.py", "process_quarterly_triggers", {}
    )
    with override_settings(CARA_QUARTERLY_OWNER="cara"):
        assert direct(object()) == {
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "held_by_cara": 1,
        }
        assert enrollment(object()) == 0


@pytest.mark.parametrize(
    ("owner", "sequence_type", "held"),
    [
        ("cara", "auto_quarterly", True),
        ("invalid", "auto_quarterly", True),
        ("legacy", "auto_quarterly", False),
        ("cara", "auto_renewal", False),
    ],
)
def test_existing_quarterly_sequence_held_without_changing_formal_renewals(
    owner, sequence_type, held
):
    class StopBeforeBusinessIO(Exception):
        pass

    execution = SimpleNamespace(
        enrollment=SimpleNamespace(
            sequence=SimpleNamespace(sequence_type=sequence_type)
        ),
        attempt_count=0,
        save=Mock(side_effect=StopBeforeBusinessIO),
    )
    model = SimpleNamespace(objects=Mock(), DoesNotExist=LookupError)
    model.objects.select_related.return_value.get.return_value = execution
    execute = _source_method(
        "email_service.py", "execute_sequence_step", {"SequenceStepExecution": model}
    )
    with override_settings(CARA_QUARTERLY_OWNER=owner):
        if held:
            assert execute(object(), "synthetic-id") is False
            assert execution.attempt_count == 0
            execution.save.assert_not_called()
        else:
            with pytest.raises(StopBeforeBusinessIO):
                execute(object(), "synthetic-id")
            assert execution.attempt_count == 1
