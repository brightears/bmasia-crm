"""bulk_operations action=update_status: the same rules as a single update, record by record.

The old branch ran ``queryset.update(**data)``: any fields, no validation, no audit row.
Now only ``status`` may be changed. Each record goes through the viewset's own serializer
(so a value a single update would refuse is refused here too, for example an invoice set
to Paid, which only "Mark as paid" may do) and its own ``perform_update`` (one audit row
per record), each in its own transaction. The reply lists the result per record.
"""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response


def bulk_update_status(viewset, queryset, ids, data):
    if set(data) != {'status'}:
        return Response(
            {'error': "update_status changes only the status: send data as {\"status\": \"<value>\"}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lookup = viewset.lookup_url_kwarg or viewset.lookup_field
    found = {str(obj.pk): obj for obj in queryset}
    results = []
    for record_id in (str(i) for i in ids):
        obj = found.get(record_id)
        if obj is None:
            results.append({'id': record_id, 'updated': False, 'error': 'Not found.'})
            continue
        # perform_update reads the record again through get_object(), as for PATCH /{id}/.
        viewset.kwargs = {**viewset.kwargs, lookup: record_id}
        serializer = viewset.get_serializer(obj, data={'status': data['status']}, partial=True)
        if not serializer.is_valid():
            results.append({'id': record_id, 'updated': False, 'errors': serializer.errors})
            continue
        with transaction.atomic():
            viewset.perform_update(serializer)
        results.append({'id': record_id, 'updated': True})

    updated = sum(1 for r in results if r['updated'])
    return Response({'message': f'{updated} records updated', 'updated': updated, 'results': results})
