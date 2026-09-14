from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
import json

from crm_app.management.commands.agent_crm_shadow_snapshot import project_snapshot
from crm_app.models import Company, Contact
from crm_app.management.commands.agent_crm_shadow_snapshot import MODELS
from crm_app.services.agent_shadow import FIELD_OWNERS, _field_value_valid


@pytest.mark.django_db
def test_exact_snapshot_is_one_read_and_does_not_mutate(django_assert_num_queries):
    company = Company.objects.create(name="Synthetic shadow account")
    contact = Contact.objects.create(company=company, name="Synthetic contact",
                                     email="shadow@example.invalid", title="Manager")
    before = dict(Contact.objects.filter(pk=contact.pk).values().get())
    with patch.object(Contact, "save", side_effect=AssertionError("write forbidden")):
        with django_assert_num_queries(1):
            result = project_snapshot("contacts", str(contact.pk), ["title", "last_contacted"])
    assert result["id"] == str(contact.pk)
    assert result["fields"] == {"title": "Manager", "last_contacted": None}
    assert dict(Contact.objects.filter(pk=contact.pk).values().get()) == before


@pytest.mark.parametrize("collection,record_id,fields", [
    ("contracts", "00000000-0000-0000-0000-000000000001", ["status"]),
    ("contacts", "not-a-uuid", ["title"]),
    ("contacts", "00000000-0000-0000-0000-000000000001", ["unsubscribe_token"]),
    ("contacts", "00000000-0000-0000-0000-000000000001", ["email"]),
    ("contacts", "00000000-0000-0000-0000-000000000001", ["title", "title"]),
    ("contacts", "00000000-0000-0000-0000-000000000001", []),
])
def test_rejected_projection_does_not_query(collection, record_id, fields, django_assert_num_queries):
    with django_assert_num_queries(0), pytest.raises(ValueError):
        project_snapshot(collection, record_id, fields)


def test_missing_record_is_not_name_matched():
    with pytest.raises(ValueError, match="Exact record not found"):
        project_snapshot("contacts", "00000000-0000-0000-0000-000000000099", ["title"])


def test_management_command_outputs_exact_projection():
    company = Company.objects.create(name="Synthetic command account")
    contact = Contact.objects.create(company=company, name="Synthetic command contact",
                                     email="command@example.invalid", title="Operations")
    output = StringIO()
    call_command("agent_crm_shadow_snapshot", collection="contacts", record_id=str(contact.pk),
                 fields=["title"], stdout=output)
    assert json.loads(output.getvalue())["fields"] == {"title": "Operations"}
    with pytest.raises(CommandError):
        call_command("agent_crm_shadow_snapshot", collection="contacts", record_id="wrong", fields=["title"])


def test_shadow_projection_policy_matches_current_models():
    for collection, fields in FIELD_OWNERS.items():
        for name in fields:
            field = MODELS[collection]._meta.get_field(name)
            for value, _label in field.choices or []:
                assert _field_value_valid(collection, name, value), (collection, name, value)
    for collection, name in (("opportunities", "stage"), ("tickets", "status"), ("tickets", "priority")):
        assert not _field_value_valid(collection, name, "not-a-real-choice")


def test_readonly_mcp_exposes_versioned_shadow_projection_fields():
    from crm_app.mcp import ContactQuery, OpportunityQuery, TicketQuery, ZoneQuery
    queries = {'contacts': ContactQuery, 'opportunities': OpportunityQuery,
               'tickets': TicketQuery, 'zones': ZoneQuery}
    for collection, fields in FIELD_OWNERS.items():
        assert set(fields).issubset(set(queries[collection].fields))
        assert {'id', 'company', 'updated_at'}.issubset(set(queries[collection].fields))
