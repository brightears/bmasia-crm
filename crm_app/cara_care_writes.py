"""Cara client-care write endpoints: care touches and the company care summary.

Authentication is the dedicated Cara bearer only (``CaraBearerAuthentication``);
session, JWT and DRF tokens are not accepted here. Every write additionally
requires ``settings.CARA_CARE_WRITES_ENABLED`` (default off). The read views in
``crm_app/cara_api.py`` stay GET-only and are not affected by this module.

* ``POST /api/v1/cara/touches/`` records one append-only ``CareTouch``.
* ``PUT /api/v1/cara/companies/<uuid>/care-summary/`` replaces the company's
  care summary under an optimistic lock.

Audit rows never contain summary text, mailboxes or email addresses.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
from datetime import datetime, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app.auth_observability import describe
from crm_app.cara_api import CaraBearerAuthentication, CaraPrincipal, care_writes_enabled
from crm_app.cara_ownership import quarterly_owner
from crm_app.models import (
    CARE_TOUCH_KIND_CHOICES,
    CARE_TOUCH_OUTCOME_CHOICES,
    CARE_TOUCH_SOURCE_CHOICES,
    AuditLog,
    CareTouch,
    Company,
    Contact,
)
from crm_app.services.care_touches import touch_as_dict

RECORDED_BY = "cara"
DISABLED_DETAIL = "Cara care writes are disabled"
KEY_RE = re.compile(r"[A-Za-z0-9:._-]{8,200}\Z")
BATCH_RE = re.compile(r"[A-Za-z0-9:._-]{1,64}\Z")
FUTURE_TOLERANCE = timedelta(minutes=10)
SUMMARY_MAX = 500
CARE_SUMMARY_MAX = 2000

KINDS = frozenset(value for value, _ in CARE_TOUCH_KIND_CHOICES)
OUTCOMES = frozenset(value for value, _ in CARE_TOUCH_OUTCOME_CHOICES)
SOURCES = frozenset(value for value, _ in CARE_TOUCH_SOURCE_CHOICES)

TOUCH_KEYS = frozenset(
    {
        "idempotency_key",
        "company_id",
        "contact_id",
        "mailbox",
        "gmail_thread_id",
        "gmail_message_id",
        "occurred_at",
        "kind",
        "outcome",
        "summary",
        "source",
        "backfill_batch",
    }
)
SUMMARY_KEYS = frozenset({"care_summary", "expected_updated_at"})


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid request"
    default_code = "invalid"


class IsEnabledCaraCareWriter(BasePermission):
    """The Cara principal, with the write switch on, using the view's one method."""

    def has_permission(self, request, view):
        if not isinstance(request.user, CaraPrincipal):
            return False
        if request.method != view.write_method:
            return False
        if not care_writes_enabled():
            raise PermissionDenied(DISABLED_DETAIL)
        return True


class CaraWriteView(APIView):
    authentication_classes = (CaraBearerAuthentication,)
    permission_classes = (IsEnabledCaraCareWriter,)
    parser_classes = (JSONParser,)
    write_method = ""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def strict_body(self, request, allowed, required=()):
        if request.query_params:
            raise BadRequest("Query parameters are not allowed")
        body = request.data
        if not isinstance(body, dict):
            raise BadRequest("Body must be a JSON object")
        unknown = sorted(set(body) - allowed)
        if unknown:
            raise BadRequest("Unknown keys: " + ", ".join(unknown))
        missing = sorted(key for key in required if key not in body)
        if missing:
            raise BadRequest("Missing keys: " + ", ".join(missing))
        return body


# ------------------------------------------------------------------ validation


def _has_control(text, allow_newlines=False):
    for char in text:
        if allow_newlines and char in "\n\r":
            continue
        if unicodedata.category(char) in ("Cc", "Zl", "Zp"):
            return True
    return False


def _optional_str(body, key):
    value = body.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise BadRequest(f"{key} must be a string")
    return value


def _required_str(body, key):
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise BadRequest(f"{key} is required")
    return value


def _uuid(value, key):
    if not isinstance(value, str):
        raise BadRequest(f"{key} must be a UUID string")
    try:
        return UUID(value)
    except ValueError:
        raise BadRequest(f"{key} must be a UUID string") from None


def _aware_datetime(value, key):
    if not isinstance(value, str):
        raise BadRequest(f"{key} must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise BadRequest(f"{key} must be an ISO 8601 string") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BadRequest(f"{key} must include a timezone")
    return parsed


def _token_field(body, key, max_length):
    value = _optional_str(body, key)
    if len(value) > max_length:
        raise BadRequest(f"{key} is too long")
    if any(char.isspace() for char in value) or _has_control(value):
        raise BadRequest(f"{key} must not contain whitespace or control characters")
    return value


def _payload_sha256(body):
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validated_touch(body):
    """Return the CareTouch field values for a structurally valid body, or raise 400."""
    company_id = _uuid(body.get("company_id"), "company_id")
    company = Company.objects.filter(pk=company_id).only("pk").first()
    if company is None:
        raise BadRequest("company_id does not exist")

    contact_id = None
    if body.get("contact_id") is not None:
        contact_id = _uuid(body["contact_id"], "contact_id")
        if not Contact.objects.filter(pk=contact_id, company_id=company.pk).exists():
            raise BadRequest("contact_id does not belong to company_id")

    mailbox = _required_str(body, "mailbox")
    if len(mailbox) > 254 or mailbox != mailbox.strip():
        raise BadRequest("mailbox must be an email address")
    try:
        validate_email(mailbox)
    except DjangoValidationError:
        raise BadRequest("mailbox must be an email address") from None
    mailbox = mailbox.lower()

    occurred_at = _aware_datetime(body.get("occurred_at"), "occurred_at")
    if occurred_at > timezone.now() + FUTURE_TOLERANCE:
        raise BadRequest("occurred_at is too far in the future")

    kind = body.get("kind")
    if kind not in KINDS:
        raise BadRequest("kind must be one of: " + ", ".join(sorted(KINDS)))
    outcome = body.get("outcome", "none")
    if outcome is None:
        outcome = "none"
    if outcome not in OUTCOMES:
        raise BadRequest("outcome must be one of: " + ", ".join(sorted(OUTCOMES)))
    source = body.get("source")
    if source not in SOURCES:
        raise BadRequest("source must be one of: " + ", ".join(sorted(SOURCES)))

    summary = _optional_str(body, "summary")
    if len(summary) > SUMMARY_MAX:
        raise BadRequest(f"summary must be at most {SUMMARY_MAX} characters")
    if _has_control(summary):
        raise BadRequest("summary must be a single line without control characters")

    batch = _optional_str(body, "backfill_batch")
    if source == "gmail_backfill":
        if not BATCH_RE.fullmatch(batch):
            raise BadRequest("source gmail_backfill requires a valid backfill_batch")
    elif batch:
        raise BadRequest("backfill_batch is only allowed with source gmail_backfill")

    return {
        "company_id": company.pk,
        "contact_id": contact_id,
        "mailbox": mailbox,
        "gmail_thread_id": _token_field(body, "gmail_thread_id", 64),
        "gmail_message_id": _token_field(body, "gmail_message_id", 255),
        "occurred_at": occurred_at,
        "kind": kind,
        "outcome": outcome,
        "summary": summary,
        "source": source,
        "backfill_batch": batch,
    }


# ------------------------------------------------------------------ audit


def _client_ip(request):
    raw = str(request.META.get("REMOTE_ADDR", "") or "")
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def _audit(request, action, model_name, record_id, extra):
    AuditLog.objects.create(
        user=None,
        action=action,
        model_name=model_name,
        record_id=str(record_id),
        ip_address=_client_ip(request),
        user_agent=str(request.META.get("HTTP_USER_AGENT", "") or "")[:255],
        additional_data={**describe(request), **extra},
    )


# ------------------------------------------------------------------ touches


def _touch_response(touch, replayed, response_status):
    return Response(
        {
            **touch_as_dict(touch),
            "replayed": replayed,
            "contact_last_contacted_updated": touch.updated_last_contacted,
            "quarterly_owner": quarterly_owner(),
        },
        status=response_status,
    )


def _existing_outcome(key, digest, mailbox=None, message_id=""):
    """Replay/conflict response for an already stored key or Gmail message, or None."""
    existing = CareTouch.objects.filter(idempotency_key=key).first()
    if existing is not None:
        if existing.payload_sha256 == digest:
            return _touch_response(existing, True, status.HTTP_200_OK)
        return Response(
            {"detail": "idempotency_key reused with a different payload"},
            status=status.HTTP_409_CONFLICT,
        )
    if mailbox and message_id:
        other = (
            CareTouch.objects.filter(mailbox=mailbox, gmail_message_id=message_id)
            .only("pk")
            .first()
        )
        if other is not None:
            return Response(
                {
                    "detail": "gmail_message_id already recorded under another idempotency_key",
                    "existing_touch_id": str(other.pk),
                },
                status=status.HTTP_409_CONFLICT,
            )
    return None


class CaraTouchCreateView(CaraWriteView):
    http_method_names = ("post",)
    write_method = "POST"

    def post(self, request):
        body = self.strict_body(
            request,
            TOUCH_KEYS,
            required=("idempotency_key", "company_id", "mailbox", "occurred_at", "kind", "source"),
        )
        key = body.get("idempotency_key")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise BadRequest("idempotency_key must be 8-200 characters of [A-Za-z0-9:._-]")
        digest = _payload_sha256(body)

        replay = _existing_outcome(key, digest)
        if replay is not None:
            return replay

        values = _validated_touch(body)
        conflict = _existing_outcome(
            key, digest, values["mailbox"], values["gmail_message_id"]
        )
        if conflict is not None:
            return conflict

        touches_contact = (
            values["kind"] == "check_in"
            and values["source"] == "send"
            and values["contact_id"] is not None
        )
        try:
            with transaction.atomic():
                updated = False
                previous = None
                # A check-in inside the future tolerance never moves the contact past now;
                # the touch itself keeps the occurred_at it was sent with.
                contacted_at = min(values["occurred_at"], timezone.now())
                if touches_contact:
                    contact = (
                        Contact.objects.select_for_update()
                        .only("pk", "last_contacted")
                        .get(pk=values["contact_id"])
                    )
                    previous = contact.last_contacted
                    updated = previous is None or previous < contacted_at
                touch = CareTouch.objects.create(
                    **values,
                    idempotency_key=key,
                    recorded_by=RECORDED_BY,
                    payload_sha256=digest,
                    updated_last_contacted=updated,
                    previous_last_contacted=previous if updated else None,
                )
                if updated:
                    Contact.objects.filter(pk=values["contact_id"]).update(
                        last_contacted=contacted_at
                    )
                _audit(
                    request,
                    "CREATE",
                    "CareTouch",
                    touch.pk,
                    {
                        "source": touch.source,
                        "kind": touch.kind,
                        "backfill_batch": touch.backfill_batch,
                        "contact_last_contacted_updated": updated,
                    },
                )
        except IntegrityError:
            # A concurrent request stored the same key or Gmail message first.
            raced = _existing_outcome(
                key, digest, values["mailbox"], values["gmail_message_id"]
            )
            if raced is not None:
                return raced
            raise
        touch.refresh_from_db()
        return _touch_response(touch, False, status.HTTP_201_CREATED)


# ------------------------------------------------------------------ care summary


class CaraCareSummaryView(CaraWriteView):
    http_method_names = ("put",)
    write_method = "PUT"

    def put(self, request, company_id):
        body = self.strict_body(request, SUMMARY_KEYS, required=SUMMARY_KEYS)
        text = body["care_summary"]
        if not isinstance(text, str):
            raise BadRequest("care_summary must be a string")
        if len(text) > CARE_SUMMARY_MAX:
            raise BadRequest(f"care_summary must be at most {CARE_SUMMARY_MAX} characters")
        if _has_control(text, allow_newlines=True):
            raise BadRequest("care_summary must not contain control characters other than newlines")
        expected_raw = body["expected_updated_at"]
        expected = (
            None
            if expected_raw is None
            else _aware_datetime(expected_raw, "expected_updated_at")
        )

        with transaction.atomic():
            current = (
                Company.objects.select_for_update()
                .filter(pk=company_id)
                .values("care_summary", "care_summary_updated_at")
                .first()
            )
            if current is None:
                return Response(
                    {"detail": "Company not found"}, status=status.HTTP_404_NOT_FOUND
                )
            stored_at = current["care_summary_updated_at"]
            if expected != stored_at:
                return Response(
                    {
                        "detail": "care_summary changed since expected_updated_at",
                        "care_summary_updated_at": stored_at.isoformat()
                        if stored_at
                        else None,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            now = timezone.now()
            Company.objects.filter(pk=company_id).update(
                care_summary=text,
                care_summary_updated_at=now,
                care_summary_updated_by=RECORDED_BY,
            )
            _audit(
                request,
                "UPDATE",
                "Company",
                company_id,
                {
                    "field": "care_summary",
                    "length_before": len(current["care_summary"] or ""),
                    "length_after": len(text),
                },
            )
        saved = Company.objects.filter(pk=company_id).values(
            "care_summary", "care_summary_updated_at", "care_summary_updated_by"
        ).get()
        return Response(
            {
                "company_id": str(company_id),
                "care_summary": saved["care_summary"],
                "care_summary_updated_at": saved["care_summary_updated_at"].isoformat(),
                "care_summary_updated_by": saved["care_summary_updated_by"],
            }
        )
