"""Isolated Cara customer-care GET projection. No generic CRM authentication.

Deploy alongside the reviewed URL/settings additions. This module never reads
free-text notes, email bodies, remote-access fields, money or attachments.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app.cara_ownership import quarterly_owner
from crm_app.models import Company, EmailLog, RenePreparedContract, SequenceEnrollment

CAPABILITY_PATH = "/api/v1/cara/capabilities/"
BOOK_PATH = "/api/v1/cara/customer-care/"
PERMISSION = "customer_care.quarterly.read"
MAX_ACCOUNTS = 50
MAX_RELATED = 25
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43,128}\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def configured_credential():
    digest = getattr(settings, "CARA_CUSTOMER_CARE_TOKEN_SHA256", "")
    expiry = getattr(settings, "CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT", "")
    try:
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            raise ValueError
        expires = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if expires.tzinfo is None or expires <= datetime.now(UTC):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise AuthenticationFailed("Cara credential unavailable") from None
    return digest, expires.isoformat()


@dataclass(frozen=True)
class CaraPrincipal:
    token_fingerprint_sha256: str
    pk: str = "cara-customer-care-reader"
    username: str = "cara"
    is_authenticated: bool = True
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False


class CaraBearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        value = request.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise AuthenticationFailed("Cara credential required")
        token = value[7:]
        if not TOKEN_RE.fullmatch(token):
            raise AuthenticationFailed("Invalid Cara credential")
        expected, _ = configured_credential()
        actual = hashlib.sha256(token.encode("ascii")).hexdigest()
        if not hmac.compare_digest(expected, actual):
            raise AuthenticationFailed("Invalid Cara credential")
        return CaraPrincipal(actual), None

    def authenticate_header(self, request):
        return "Bearer"


class IsExactCaraReader(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, CaraPrincipal) and request.method == "GET"


class CaraReadView(APIView):
    authentication_classes = (CaraBearerAuthentication,)
    permission_classes = (IsExactCaraReader,)
    http_method_names = ("get",)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class CaraCapabilitiesView(CaraReadView):
    def get(self, request):
        if request.query_params:
            raise ValidationError("Query not allowed")
        digest, expiry = configured_credential()
        return Response(
            {
                "schema": "bmasia.crm.cara.capabilities.v1",
                "subject": "cara",
                "token_fingerprint_sha256": digest,
                "expires_at": expiry,
                "permissions": [PERMISSION],
                "allowed_methods": ["GET"],
                "allowed_paths": [CAPABILITY_PATH, BOOK_PATH],
                "maximum_page_size": MAX_ACCOUNTS,
                "projection_schema": "bmasia.crm.cara.customer-care.v1",
                "quarterly_owner": quarterly_owner(),
                "quarterly_owner_scope": "CRM_QUARTERLY_SENDERS_ONLY",
            }
        )


def _iso(value):
    return value.isoformat() if value is not None else None


def _bounded_rows(query, fields):
    rows = list(query.values(*fields)[: MAX_RELATED + 1])
    complete = len(rows) <= MAX_RELATED
    return rows[:MAX_RELATED], complete


def _plain(rows):
    return [
        {
            key: _iso(value)
            if hasattr(value, "isoformat")
            else str(value)
            if isinstance(value, UUID)
            else value
            for key, value in row.items()
        }
        for row in rows
    ]


def project_company(company, observed_at):
    """Finite metadata projection; incomplete related sets visibly block use."""
    contacts, contacts_complete = _bounded_rows(
        company.contacts.order_by("id"),
        (
            "id",
            "name",
            "email",
            "contact_type",
            "is_primary",
            "is_active",
            "receives_notifications",
            "receives_quarterly_emails",
            "unsubscribed",
            "preferred_language",
            "preferred_contact_method",
            "last_contacted",
            "updated_at",
        ),
    )
    contracts, contracts_complete = _bounded_rows(
        company.contracts.filter(is_active=True, status="Active").order_by("id"),
        (
            "id",
            "contract_type",
            "service_type",
            "status",
            "is_active",
            "start_date",
            "end_date",
            "currency",
            "renewal_period_months",
            "renewal_notice_sent",
            "renewal_notice_date",
            "updated_at",
        ),
    )
    open_tickets = company.tickets.exclude(status__in=["resolved", "closed"])
    tickets, tickets_complete = _bounded_rows(
        open_tickets.order_by("id"),
        (
            "id",
            "status",
            "priority",
            "category",
            "assigned_team",
            "assigned_to_id",
            "contact_id",
            "updated_at",
        ),
    )
    # Counts query the entire relation, independently of the bounded excerpts.
    urgent_count = open_tickets.filter(priority__in=["high", "urgent"]).count()
    active_sequences = SequenceEnrollment.objects.filter(
        Q(company_id=company.pk) | Q(contact__company_id=company.pk),
        status="active",
        sequence__status="active",
    )
    quarterly_motion = active_sequences.filter(
        sequence__sequence_type="auto_quarterly"
    ).exists()
    renewal_motion = active_sequences.filter(
        sequence__sequence_type="auto_renewal"
    ).exists()
    rene_preparing = RenePreparedContract.objects.filter(
        source_contract__company_id=company.pk,
        state="ready_for_review",
    ).exists()
    last_quarterly = (
        EmailLog.objects.filter(
            company_id=company.pk,
            email_type="quarterly",
            sent_at__isnull=False,
        )
        .order_by("-sent_at", "-id")
        .values("id", "sent_at", "status", "contact_id")
        .first()
    )
    today = observed_at.date()
    current_contracts = [
        row
        for row in contracts
        if row["contract_type"] != "One-time"
        and row["start_date"] <= today
        and (row["end_date"] is None or row["end_date"] >= today)
    ]
    primaries = [
        row
        for row in contacts
        if row["is_active"] and (row["is_primary"] or row["contact_type"] == "Primary")
    ]
    holds = []
    if not company.is_active:
        holds.append("COMPANY_STATUS_CONTRADICTS_ACTIVE_SUBSCRIPTION")
    if not current_contracts:
        holds.append("CURRENT_SUBSCRIPTION_NOT_VERIFIED")
    if not contacts_complete or len(primaries) != 1:
        holds.append("PRIMARY_CONTACT_MISSING_OR_AMBIGUOUS")
    if not all((contacts_complete, contracts_complete, tickets_complete)):
        holds.append("RELATED_RECORD_COVERAGE_INCOMPLETE")
    if urgent_count:
        holds.append("OPEN_HIGH_PRIORITY_SUPPORT")
    if quarterly_motion and quarterly_owner() != "cara":
        holds.append("CRM_QUARTERLY_SEQUENCE_ACTIVE")
    if renewal_motion or rene_preparing:
        holds.append("FORMAL_RENEWAL_ACTIVITY_OBSERVED")
    if len(primaries) == 1:
        contact = primaries[0]
        if (
            contact["unsubscribed"]
            or not contact["receives_notifications"]
            or not contact["receives_quarterly_emails"]
        ):
            holds.append("CONTACT_QUARTERLY_EMAILS_DISABLED")
        if contact["preferred_contact_method"] not in ("", "Email"):
            holds.append("PREFERRED_CONTACT_METHOD_NOT_EMAIL")
    evidence = {
        "account_id": str(company.pk),
        "name": company.name,
        "company_is_active": company.is_active,
        "company_updated_at": _iso(company.updated_at),
        "account_state": "ACTIVE_CUSTOMER" if current_contracts else "REVIEW_REQUIRED",
        "contracted_product": company.contracted_product or None,
        "contracted_synced_at": _iso(company.contracted_synced_at),
        "contacts": _plain(contacts),
        "primary_contact_id": str(primaries[0]["id"])
        if len(primaries) == 1 and contacts_complete
        else None,
        "contracts": _plain(contracts),
        "open_tickets": _plain(tickets),
        "open_ticket_count": open_tickets.count(),
        "open_high_priority_ticket_count": urgent_count,
        "crm_quarterly_sequence_active": quarterly_motion,
        "crm_renewal_sequence_active": renewal_motion,
        "rene_preparation_observed": rene_preparing,
        "last_crm_quarterly_log": _plain([last_quarterly])[0]
        if last_quarterly
        else None,
        # Neither CRM absence nor a CRM send receipt establishes other lanes' truth.
        "formal_renewal_activity": "ACTIVE"
        if renewal_motion or rene_preparing
        else "UNKNOWN",
        "cross_lane_coverage": "UNKNOWN",
        "live_service_health": "UNKNOWN",
        "renewal_source": "CRM_REQUIRES_SHEET_RECONCILIATION",
        "coverage": {
            "contacts_complete": contacts_complete,
            "contracts_complete": contracts_complete,
            "open_tickets_complete": tickets_complete,
        },
        "holds": holds,
    }
    digest = hashlib.sha256(
        json.dumps(
            evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return {
        **evidence,
        "evidence_sha256": digest,
        "observed_at": observed_at.isoformat(),
        "source_locator": f"{BOOK_PATH}?company_id={company.pk}",
    }


class CaraCustomerCareView(CaraReadView):
    def get(self, request):
        query = request.query_params
        if any(key not in {"after", "limit", "company_id"} for key in query):
            raise ValidationError("Unknown query parameter")
        if any(len(query.getlist(key)) != 1 for key in query):
            raise ValidationError("Duplicate query parameter")
        if "company_id" in query and "after" in query:
            raise ValidationError("Conflicting query parameters")
        try:
            raw_limit = query.get("limit", str(MAX_ACCOUNTS))
            limit = int(raw_limit)
            if str(limit) != raw_limit or not 1 <= limit <= MAX_ACCOUNTS:
                raise ValueError
            ids = {
                key: str(UUID(query[key]))
                for key in ("after", "company_id")
                if key in query
            }
            if any(ids[key] != query[key] for key in ids):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("Invalid bounded query") from None
        companies = (
            Company.objects.filter(
                contracts__is_active=True, contracts__status="Active"
            )
            .distinct()
            .order_by("id")
        )
        if "after" in ids:
            companies = companies.filter(pk__gt=ids["after"])
        if "company_id" in ids:
            companies = companies.filter(pk=ids["company_id"])
        rows = list(companies[: limit + 1])
        has_more = len(rows) > limit
        now = timezone.now()
        accounts = [project_company(company, now) for company in rows[:limit]]
        return Response(
            {
                "schema": "bmasia.crm.cara.customer-care.v1",
                "subject": "cara",
                "observed_at": now.isoformat(),
                "accounts": accounts,
                "complete": not has_more,
                "next_after": str(rows[limit - 1].pk) if has_more else None,
                "scope": "companies_with_active_contract_records",
                "maximum_page_size": MAX_ACCOUNTS,
                "quarterly_owner": quarterly_owner(),
            }
        )
