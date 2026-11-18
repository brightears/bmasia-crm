"""Deletes that would erase customer history are refused, with an alternative that works.

The rules (REST single and bulk delete; the agents' delete_record refuses these five outright):
- Company: only when nothing at all points at it. Every relation is found from the model
  metadata (reverse foreign keys, one-to-ones and many-to-many memberships), so a table
  added later is counted without changing this file.
- Contract, quote, invoice: only while Draft, and only when nothing points at it except
  its own parts (line items; for a contract its zone links and service locations; for a
  quote its activity log and attachments).
- Contact: only when nothing points at it and it is not the company's primary contact.

A refusal names counts per kind of record and one alternative the caller can carry out
through the same interface (REST: a PATCH; MCP: an update_record call).
"""
import json

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response

from crm_app.models import Company, Contact, Contract, Invoice, Quote

# Rows that belong to the record and go with it when a Draft is deleted.
OWN_PARTS = {
    Contract: {'crm_app.ContractLineItem.contract', 'crm_app.ContractServiceLocation.contract',
               'crm_app.ContractZone.contract'},
    Quote: {'crm_app.QuoteLineItem.quote', 'crm_app.QuoteActivity.quote', 'crm_app.QuoteAttachment.quote'},
    Invoice: {'crm_app.InvoiceLineItem.invoice'},
    Company: set(),
    Contact: set(),
}

DRAFT_ONLY = (Contract, Quote, Invoice)

# The alternative, as the fields to change. REST callers PATCH them; agents use update_record.
ALTERNATIVE_FIELDS = {
    Company: {'is_active': False},
    Contact: {'is_active': False},
    Contract: {'status': 'Cancelled'},
    Quote: {'status': 'Rejected'},
    Invoice: {'status': 'Cancelled'},
}
_REST_PATHS = {Company: 'companies', Contact: 'contacts', Contract: 'contracts', Quote: 'quotes',
               Invoice: 'invoices'}
_ALTERNATIVE_WORDS = {
    Company: 'deactivate the company',
    Contact: 'deactivate the contact',
    Contract: 'cancel the contract',
    Quote: 'mark the quote Rejected (or Expired, if it lapsed)',
    Invoice: 'cancel the invoice (invoices are numbered in the accounting system)',
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


def reference_counts(instance):
    """{kind: count} of rows pointing at ``instance``, its own parts left out."""
    return {plural: n for plural, _singular, n in _reference_rows(instance)}


def _describe(rows):
    items = [f'{n} {singular if n == 1 else plural}' for plural, singular, n in rows]
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def rest_alternative(instance):
    model = type(instance)
    return {
        'method': 'PATCH',
        'path': f'/api/v1/{_REST_PATHS[model]}/{instance.pk}/',
        'data': ALTERNATIVE_FIELDS[model],
    }


def delete_refusal(instance):
    """None when the record may be deleted, otherwise the body of a 409 reply."""
    model = type(instance)
    if model not in OWN_PARTS:
        return None
    name = getattr(instance, 'name', None) or getattr(instance, 'contract_number', None) \
        or getattr(instance, 'quote_number', None) or getattr(instance, 'invoice_number', None) or str(instance.pk)
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
    if not reasons:
        return None
    alternative = rest_alternative(instance)
    return {
        'error': (f'{name} cannot be deleted: {"; ".join(reasons)}. Instead, '
                  f'{_ALTERNATIVE_WORDS[model]}: PATCH {alternative["path"]} '
                  f'{json.dumps(alternative["data"])}.'),
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


def destroy_one(viewset, instance):
    """Delete one record by the rules above. Returns (deleted, refusal_body)."""
    refusal = delete_refusal(instance)
    if refusal:
        return False, refusal
    try:
        with transaction.atomic():  # the audit row and the delete stand or fall together
            viewset.perform_destroy(instance)
    except ProtectedError as exc:
        kinds = sorted({str(o._meta.verbose_name_plural).lower() for o in exc.protected_objects})
        return False, {'error': f'This record cannot be deleted because other records depend on it '
                                f'({", ".join(kinds)}).', 'code': 'protected'}
    return True, None


def bulk_delete(viewset, queryset, ids):
    """bulk_operations action=delete: the single-delete rules, record by record."""
    found = {str(obj.pk): obj for obj in queryset}
    results = []
    for record_id in (str(i) for i in ids):
        obj = found.get(record_id)
        if obj is None:
            results.append({'id': record_id, 'deleted': False, 'error': 'Not found.'})
            continue
        deleted, refusal = destroy_one(viewset, obj)
        results.append({'id': record_id, 'deleted': True} if deleted
                       else {'id': record_id, 'deleted': False, **refusal})
    count = sum(1 for r in results if r['deleted'])
    return Response({'message': f'{count} records deleted', 'deleted': count, 'results': results},
                    status=status.HTTP_200_OK)
