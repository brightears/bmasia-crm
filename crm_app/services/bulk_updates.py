"""Bulk operations: enabled per record type, and the same rules as single edits.

A viewset offers only the operations it lists in ``bulk_allowed`` (none by default); any
other operation answers 405. At most ``MAX_BULK_IDS`` records per call. Each record goes
through the same path as a single edit or delete, in its own transaction, and the reply
lists the result per record:

- ``delete``: the single-delete rules (crm_app/services/delete_guards.py).
- ``update_status``: exactly one field, ``status``; the viewset's serializer validates it
  (so every transition rule applies, for example an invoice is never set Paid this way) and
  its ``perform_update`` saves it (model save, signals, one audit row).
- ``assign``: ``assigned_to`` must be an active user; saved through the serializer.
- ``activate`` / ``deactivate``: ``is_active`` through the serializer.
- ``export``: CSV of the selected records.
"""
from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response

MAX_BULK_IDS = 200


def run_bulk_operation(viewset, request):
    from crm_app.serializers import BulkOperationSerializer

    body = BulkOperationSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    action = body.validated_data['action']
    ids = list(dict.fromkeys(str(i) for i in body.validated_data['ids']))  # each record once, order kept
    data = body.validated_data.get('data') or {}

    if action not in getattr(viewset, 'bulk_allowed', frozenset()):
        return Response(
            {'error': f'Bulk {action} is not available for {viewset.basename} records; '
                      'change them one at a time.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
    if len(ids) > MAX_BULK_IDS:
        return Response({'error': f'At most {MAX_BULK_IDS} records per bulk operation.'},
                        status=status.HTTP_400_BAD_REQUEST)

    queryset = viewset.get_queryset().filter(pk__in=ids)
    if action == 'delete':
        from crm_app.services.delete_guards import bulk_delete
        return bulk_delete(viewset, queryset, ids)
    if action == 'update_status':
        return bulk_update_status(viewset, queryset, ids, data)
    if action == 'assign':
        return bulk_assign(viewset, queryset, ids, data)
    if action in ('activate', 'deactivate'):
        return _bulk_update_fields(viewset, queryset, ids, {'is_active': action == 'activate'}, verb=action + 'd')
    if action == 'export':
        return viewset.export_csv(queryset)
    return Response({'error': 'Unknown bulk operation.'}, status=status.HTTP_400_BAD_REQUEST)


def _bulk_update_fields(viewset, queryset, ids, fields, verb='updated'):
    """Save ``fields`` on each record through the viewset's serializer and perform_update."""
    lookup = viewset.lookup_url_kwarg or viewset.lookup_field
    found = {str(obj.pk): obj for obj in queryset}
    results = []
    for record_id in (str(i) for i in ids):
        obj = found.get(record_id)
        if obj is None or not type(obj)._base_manager.filter(pk=obj.pk).exists():
            results.append({'id': record_id, 'updated': False, 'error': 'Not found.'})
            continue
        # perform_update reads the record again through get_object(), as for PATCH /{id}/.
        viewset.kwargs = {**viewset.kwargs, lookup: record_id}
        serializer = viewset.get_serializer(obj, data=fields, partial=True)
        if not serializer.is_valid():
            results.append({'id': record_id, 'updated': False, 'errors': serializer.errors})
            continue
        try:
            with transaction.atomic():
                viewset.perform_update(serializer)
        except Http404:  # deleted by someone else while this call ran
            results.append({'id': record_id, 'updated': False, 'error': 'Not found.'})
            continue
        results.append({'id': record_id, 'updated': True})

    updated = sum(1 for r in results if r['updated'])
    noun = getattr(viewset, 'bulk_noun', 'record')
    return Response({'message': f'{updated} {noun}{"s" if updated != 1 else ""} {verb}',
                     'updated': updated, 'count': updated, 'results': results})


def bulk_update_status(viewset, queryset, ids, data):
    if set(data) != {'status'}:
        return Response(
            {'error': "update_status changes only the status: send data as {\"status\": \"<value>\"}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _bulk_update_fields(viewset, queryset, ids, {'status': data['status']})


def bulk_assign(viewset, queryset, ids, data):
    from crm_app.models import User

    if set(data) != {'assigned_to'}:
        return Response({'error': "assign changes only the assignee: send data as {\"assigned_to\": \"<user id>\"}."},
                        status=status.HTTP_400_BAD_REQUEST)
    from django.core.exceptions import ValidationError
    try:
        user = User.objects.filter(pk=data['assigned_to'], is_active=True).first() if data['assigned_to'] else None
    except (ValueError, ValidationError):
        user = None
    if user is None:
        return Response({'error': 'assigned_to must be an active user.'}, status=status.HTTP_400_BAD_REQUEST)
    return _bulk_update_fields(viewset, queryset, ids, {'assigned_to': str(user.pk)}, verb='assigned')
