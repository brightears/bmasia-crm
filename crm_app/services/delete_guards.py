"""Deletes that would erase customer history are refused, with an alternative that works.

The rules (REST single and bulk delete; the agents' delete_record refuses these five outright):
- Company: only when nothing at all points at it. Every relation is found from the model
  metadata (reverse foreign keys, one-to-ones and many-to-many memberships), so a table
  added later is counted without changing this file.
- Contract, quote, invoice: only while Draft, and only when nothing points at it except
  its own parts (line items; for a contract its zone links and service locations; for a
  quote its activity log and attachments).
- Contact: only when nothing points at it and it is not the company's primary contact.

- Configuration and history records (templates, sequences, enrolments, segments, knowledge
  base categories, tags and articles, tickets, zones): only when nothing points at them
  except their own parts. Configuration records are deleted by a person signed in to the
  CRM, never by an agent account.

A refusal names counts per kind of record and, where there is one, an alternative the caller
can carry out through the same interface (REST: a PATCH; MCP: an update_record call).
"""
import json

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response

from crm_app.models import (
    Company, Contact, Contract, ContractTemplate, CorporatePdfTemplate, CustomerSegment, EmailSequence,
    EmailTemplate, Invoice, KBArticle, KBCategory, KBTag, ProspectEnrollment, ProspectSequence, Quote,
    SeasonalTriggerDate, SequenceEnrollment, SequenceStep, StaticDocument, Ticket, Zone,
)

# Rows that belong to the record and go with it when a Draft is deleted.
OWN_PARTS = {
    Contract: {'crm_app.ContractLineItem.contract', 'crm_app.ContractServiceLocation.contract',
               'crm_app.ContractZone.contract'},
    Quote: {'crm_app.QuoteLineItem.quote', 'crm_app.QuoteActivity.quote', 'crm_app.QuoteAttachment.quote'},
    # Revenue-recognition schedules are written for the invoice when it is saved with service
    # dates (InvoiceViewSet._generate_revenue_recognition); they go with a deleted Draft.
    Invoice: {'crm_app.InvoiceLineItem.invoice', 'crm_app.RevenueRecognitionSchedule.invoice'},
    Company: set(),
    Contact: set(),
    # Configuration and history records: deletable only while nothing else refers to them.
    EmailTemplate: set(),
    EmailSequence: {'crm_app.SequenceStep.sequence'},
    SequenceStep: set(),
    SequenceEnrollment: set(),
    ProspectSequence: {'crm_app.ProspectSequenceStep.sequence'},
    ProspectEnrollment: set(),
    ContractTemplate: set(),
    CorporatePdfTemplate: set(),
    StaticDocument: set(),
    SeasonalTriggerDate: set(),
    CustomerSegment: set(),
    KBCategory: set(),
    KBTag: set(),
    KBArticle: {'crm_app.KBArticleView.article', 'crm_app.KBArticleRating.article',
                'crm_app.KBArticleAttachment.article', 'crm_app.KBArticleRelation.from_article',
                'crm_app.KBArticleRelation.to_article'},
    Ticket: set(),
    Zone: set(),
}

# Deleted only by a person signed in to the CRM, never by an agent account.
CONFIGURATION_MODELS = (
    EmailTemplate, EmailSequence, SequenceStep, ProspectSequence, ContractTemplate, CorporatePdfTemplate,
    StaticDocument, SeasonalTriggerDate, CustomerSegment, KBCategory, KBTag,
)

DRAFT_ONLY = (Contract, Quote, Invoice)

# The alternative, as the fields to change. REST callers PATCH them; agents use update_record.
ALTERNATIVE_FIELDS = {
    Company: {'is_active': False},
    Contact: {'is_active': False},
    Contract: {'status': 'Cancelled'},
    Quote: {'status': 'Rejected'},
    Invoice: {'status': 'Cancelled'},
    EmailTemplate: {'is_active': False},
    EmailSequence: {'status': 'archived'},
    SequenceStep: {'is_active': False},
    SequenceEnrollment: {'status': 'paused'},
    ProspectSequence: {'is_active': False},
    ProspectEnrollment: {'status': 'cancelled'},
    ContractTemplate: {'is_active': False},
    CustomerSegment: {'status': 'archived'},
    KBCategory: {'is_active': False},
    KBArticle: {'status': 'archived'},
    Ticket: {'status': 'closed'},
    Zone: {'status': 'cancelled'},
}
_REST_PATHS = {
    Company: 'companies', Contact: 'contacts', Contract: 'contracts', Quote: 'quotes', Invoice: 'invoices',
    EmailTemplate: 'email-templates', EmailSequence: 'email-sequences', SequenceStep: 'sequence-steps',
    SequenceEnrollment: 'sequence-enrollments', ProspectSequence: 'prospect-sequences',
    ProspectEnrollment: 'prospect-enrollments', ContractTemplate: 'contract-templates',
    CustomerSegment: 'segments', KBCategory: 'kb/categories', KBArticle: 'kb/articles', Ticket: 'tickets',
    Zone: 'zones',
}
_ALTERNATIVE_WORDS = {
    Company: 'deactivate the company',
    Contact: 'deactivate the contact',
    Contract: 'cancel the contract',
    Quote: 'mark the quote Rejected (or Expired, if it lapsed)',
    Invoice: 'cancel the invoice (invoices are numbered in the accounting system)',
    EmailTemplate: 'deactivate the template',
    EmailSequence: 'archive the sequence',
    SequenceStep: 'deactivate the step',
    SequenceEnrollment: 'pause the enrolment',
    ProspectSequence: 'deactivate the sequence',
    ProspectEnrollment: 'cancel the enrolment',
    ContractTemplate: 'deactivate the template',
    CustomerSegment: 'archive the segment',
    KBCategory: 'deactivate the category',
    KBArticle: 'archive the article',
    Ticket: 'close the ticket',
    Zone: 'mark the zone cancelled',
}

MCP_COLLECTIONS = {'company': Company, 'contact': Contact, 'contract': Contract, 'quote': Quote,
                   'invoice': Invoice}


def relation_key(rel):
    return f'{rel.related_model._meta.label}.{rel.field.name}'


def referencing_relations(model):
    """Every relation pointing at ``model``, read from the model metadata."""
    return list(model._meta.related_objects)


def cascading_relation_keys(model):
    """The relations whose rows a delete of ``model`` would delete with it."""
    from django.db.models import CASCADE
    return sorted(relation_key(rel) for rel in referencing_relations(model)
                  if rel.many_to_many or getattr(rel, 'on_delete', None) is CASCADE)


def _reference_rows(instance):
    """[(plural kind, singular kind, count)] of rows pointing at ``instance``, its own parts left out."""
    parts = OWN_PARTS.get(type(instance), set())
    rows = {}
    for rel in referencing_relations(type(instance)):
        if relation_key(rel) in parts:
            continue
        n = rel.related_model._base_manager.filter(**{rel.field.name: instance}).count()
        if not n:
            continue
        meta = rel.related_model._meta
        plural, singular = str(meta.verbose_name_plural).lower(), str(meta.verbose_name).lower()
        if plural == singular + 's':  # Django's default plural: "opportunitys", "care touchs"
            if singular.endswith('y'):
                plural = singular[:-1] + 'ies'
            elif singular.endswith(('ch', 'sh', 's', 'x', 'z')):
                plural = singular + 'es'
        if rel.related_model is type(instance):
            suffix = f' linked by {rel.field.verbose_name}'
            plural, singular = plural + suffix, singular + suffix
        previous = rows.get(plural, (singular, 0))
        rows[plural] = (singular, previous[1] + n)
    return [(plural, singular, n) for plural, (singular, n) in sorted(rows.items())]


def protecting_relation_keys(model):
    """The relations that block a delete of ``model`` at the database (PROTECT, RESTRICT)."""
    from django.db.models import PROTECT, RESTRICT
    return sorted(relation_key(rel) for rel in referencing_relations(model)
                  if getattr(rel, 'on_delete', None) in (PROTECT, RESTRICT))


def reference_counts(instance):
    """{kind: count} of rows pointing at ``instance``, its own parts left out."""
    return {plural: n for plural, _singular, n in _reference_rows(instance)}


def _describe(rows):
    items = [f'{n} {singular if n == 1 else plural}' for plural, singular, n in rows]
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def rest_alternative(instance):
    model = type(instance)
    if model not in ALTERNATIVE_FIELDS:
        return None
    return {
        'method': 'PATCH',
        'path': f'/api/v1/{_REST_PATHS[model]}/{instance.pk}/',
        'data': ALTERNATIVE_FIELDS[model],
    }


def _refusal_reasons(instance):
    """(name, reasons, counts) for a record covered by these rules; reasons is empty when it may go."""
    model = type(instance)
    name = next((str(getattr(instance, attr)) for attr in (
        'name', 'contract_number', 'quote_number', 'invoice_number', 'title', 'subject', 'ticket_number')
        if getattr(instance, attr, None)), str(instance.pk))
    reasons = []
    if model in DRAFT_ONLY and instance.status != 'Draft':
        reasons.append(f'it is {instance.status}; only a Draft can be deleted')
    if model is Contact and instance.is_primary:
        reasons.append("it is the company's primary contact")
    rows = _reference_rows(instance)
    counts = {plural: n for plural, _singular, n in rows}
    if rows:
        verb = 'refers' if len(rows) == 1 and rows[0][2] == 1 else 'refer'
        reasons.append(f'{_describe(rows)} {verb} to it, and deleting it would delete or orphan them')
    return name, reasons, counts


def delete_refusal(instance):
    """None when the record may be deleted, otherwise the body of a 409 reply."""
    model = type(instance)
    if model not in OWN_PARTS:
        return None
    name, reasons, counts = _refusal_reasons(instance)
    if not reasons:
        return None
    alternative = rest_alternative(instance)
    instead = (f'{_ALTERNATIVE_WORDS[model]}: PATCH {alternative["path"]} {json.dumps(alternative["data"])}'
               if alternative else 'remove or move what refers to it first')
    return {
        'error': f'{name} cannot be deleted: {"; ".join(reasons)}. Instead, {instead}.',
        'code': 'delete_refused',
        'references': counts,
        'alternative': alternative,
    }


def mcp_delete_refusal(collection):
    """The agents' delete_record message for a collection it refuses, or None."""
    model = MCP_COLLECTIONS.get(collection)
    if model is None:
        return None
    data = json.dumps(ALTERNATIVE_FIELDS[model])
    return (f"Error: Deleting a {collection} is blocked because it would erase customer history. "
            f"Instead, {_ALTERNATIVE_WORDS[model]}: update_record('{collection}', id, '{data}').")


def mcp_record_refusal(instance, collection):
    """The agents' delete_record message for a record these rules keep, or None."""
    if type(instance) not in OWN_PARTS:
        return None
    name, reasons, _counts = _refusal_reasons(instance)
    if not reasons:
        return None
    fields = ALTERNATIVE_FIELDS.get(type(instance))
    instead = (f"{_ALTERNATIVE_WORDS[type(instance)]}: update_record('{collection}', id, '{json.dumps(fields)}')"
               if fields else 'remove or move what refers to it first')
    return f'Error: {name} cannot be deleted: {"; ".join(reasons)}. Instead, {instead}.'


def _delete_parts_that_would_be_orphaned(instance):
    """Own parts whose link is SET_NULL would be left behind without their record: delete them too."""
    from django.db.models import CASCADE
    parts = OWN_PARTS.get(type(instance), set())
    for rel in referencing_relations(type(instance)):
        if relation_key(rel) in parts and not rel.many_to_many and rel.on_delete is not CASCADE:
            rel.related_model._base_manager.filter(**{rel.field.name: instance}).delete()


def is_agent_user(user):
    """An agent account (agent_inbox's rule where that app is installed, else the agent names)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    from django.apps import apps
    if apps.is_installed('agent_inbox'):
        from agent_inbox.policy import is_agent_account
        return is_agent_account(user)
    from crm_app import agent_policy
    return agent_policy.principal_for_username(getattr(user, 'username', '')) is not None


def agent_refusal(viewset, instance):
    """Configuration records are not deleted by agent accounts: the body of a 403, or None."""
    if not isinstance(instance, CONFIGURATION_MODELS):
        return None
    if not is_agent_user(getattr(getattr(viewset, 'request', None), 'user', None)):
        return None
    kind = str(instance._meta.verbose_name).lower()
    return {'error': f'A {kind} is configuration: it is deleted by a person signed in to the CRM, '
                     'not by an agent account.', 'code': 'not_for_agents'}


def destroy_one(viewset, instance):
    """Delete one record by the rules above. Returns (deleted, refusal_body, http_status)."""
    refusal = agent_refusal(viewset, instance)
    if refusal:
        return False, refusal, status.HTTP_403_FORBIDDEN
    refusal = delete_refusal(instance)
    if refusal:
        return False, refusal, status.HTTP_409_CONFLICT
    try:
        with transaction.atomic():  # the audit row, the parts and the delete stand or fall together
            _delete_parts_that_would_be_orphaned(instance)
            viewset.perform_destroy(instance)
    except ProtectedError as exc:
        kinds = sorted({str(o._meta.verbose_name_plural).lower() for o in exc.protected_objects})
        return False, {'error': f'This record cannot be deleted because other records depend on it '
                                f'({", ".join(kinds)}).', 'code': 'protected'}, status.HTTP_409_CONFLICT
    return True, None, status.HTTP_204_NO_CONTENT


class GuardedDestroyMixin:
    """DELETE /{id}/ under the rules above, for viewsets not built on BaseModelViewSet."""

    def destroy(self, request, *args, **kwargs):
        deleted, refusal, http_status = destroy_one(self, self.get_object())
        if not deleted:
            return Response(refusal, status=http_status)
        return Response(status=status.HTTP_204_NO_CONTENT)


def bulk_delete(viewset, queryset, ids):
    """bulk_operations action=delete: the single-delete rules, record by record."""
    found = {str(obj.pk): obj for obj in queryset}
    results = []
    for record_id in (str(i) for i in ids):
        obj = found.get(record_id)
        if obj is None:
            results.append({'id': record_id, 'deleted': False, 'error': 'Not found.'})
            continue
        deleted, refusal, _status = destroy_one(viewset, obj)
        results.append({'id': record_id, 'deleted': True} if deleted
                       else {'id': record_id, 'deleted': False, **refusal})
    count = sum(1 for r in results if r['deleted'])
    return Response({'message': f'{count} records deleted', 'deleted': count, 'results': results},
                    status=status.HTTP_200_OK)
