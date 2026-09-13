"""Exact-record, bounded, read-only snapshot for the shadow comparison tool."""
import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from crm_app.models import Contact, Opportunity, Ticket, Zone
from crm_app.services.agent_shadow import FIELD_OWNERS


MODELS = {"contacts": Contact, "opportunities": Opportunity, "tickets": Ticket, "zones": Zone}


def project_snapshot(collection, record_id, requested_fields):
    """One SELECT; no save(), signal, model method or network operation."""
    if collection not in MODELS:
        raise ValueError("Collection is outside the shadow projection")
    record_id = str(UUID(str(record_id)))
    if not requested_fields or len(requested_fields) > 20:
        raise ValueError("Supply 1 to 20 exact fields")
    if len(set(requested_fields)) != len(requested_fields):
        raise ValueError("Duplicate field")
    if not set(requested_fields) <= set(FIELD_OWNERS[collection]):
        raise ValueError("Field is outside the shadow projection")
    row = MODELS[collection].objects.filter(pk=record_id).values(
        "updated_at", *requested_fields).first()
    if row is None:
        raise ValueError("Exact record not found; name matching is not permitted")
    updated_at = row.pop("updated_at")
    fields = {key: value.isoformat() if hasattr(value, "isoformat") else value
              for key, value in row.items()}
    return {"collection": collection, "id": record_id,
            "observed_at": timezone.now().isoformat(),
            "updated_at": updated_at.isoformat(), "fields": fields}


class Command(BaseCommand):
    help = "Read one exact CRM record for operator shadow comparison; never mutate it"
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--collection", choices=tuple(MODELS), required=True)
        parser.add_argument("--record-id", required=True)
        parser.add_argument("--fields", nargs="+", required=True)

    def handle(self, *args, **options):
        try:
            result = project_snapshot(options["collection"], options["record_id"], options["fields"])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
