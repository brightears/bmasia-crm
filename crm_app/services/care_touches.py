"""Client-care touch helpers: JSON shapes, recent-touch reads and backfill revert.

Touches are written only through the Cara bearer endpoint
(``crm_app/cara_care_writes.py``). This module never sends email and never
changes contacts.
"""
from __future__ import annotations

from django.db import transaction

from crm_app.models import AuditLog, CareTouch


def _iso(value):
    return value.isoformat() if value is not None else None


def touch_as_dict(touch: CareTouch) -> dict:
    """The full JSON shape of one touch (ISO datetimes, string UUIDs)."""
    return {
        'id': str(touch.pk),
        'company_id': str(touch.company_id),
        'contact_id': str(touch.contact_id) if touch.contact_id else None,
        'mailbox': touch.mailbox,
        'gmail_thread_id': touch.gmail_thread_id,
        'gmail_message_id': touch.gmail_message_id,
        'occurred_at': _iso(touch.occurred_at),
        'kind': touch.kind,
        'outcome': touch.outcome,
        'summary': touch.summary,
        'source': touch.source,
        'backfill_batch': touch.backfill_batch,
        'idempotency_key': touch.idempotency_key,
        'recorded_by': touch.recorded_by,
        'updated_last_contacted': touch.updated_last_contacted,
        'previous_last_contacted': _iso(touch.previous_last_contacted),
        'created_at': _iso(touch.created_at),
    }


# Fields the website's CompanyCareCard shows. Mailbox, Gmail ids and the
# idempotency key stay out of the website response.
WEBSITE_TOUCH_FIELDS = ('id', 'occurred_at', 'kind', 'outcome', 'summary')


def recent_touches(company_id, limit: int = 20) -> list[dict]:
    """Most recent touches for one company, newest first, in the website's slim shape."""
    rows = (
        CareTouch.objects.filter(company_id=company_id)
        .order_by('-occurred_at', '-created_at')
        .values(*WEBSITE_TOUCH_FIELDS)[:limit]
    )
    return [
        {
            'id': str(row['id']),
            'occurred_at': _iso(row['occurred_at']),
            'kind': row['kind'],
            'outcome': row['outcome'],
            'summary': row['summary'],
        }
        for row in rows
    ]


def revert_backfill_batch(batch: str, execute: bool = False) -> dict:
    """Count (dry run) or delete (execute) the Gmail-backfill touches of one batch.

    Only rows with ``source='gmail_backfill'`` and exactly this
    ``backfill_batch`` are touched. Backfill rows never change contacts, so
    deleting them is a complete revert. On execute, one AuditLog DELETE row is
    written with the count (no summary text, no mailbox).

    One-off invocation (dry run first, then execute)::

        python manage.py shell -c "from crm_app.services.care_touches import revert_backfill_batch as r; print(r('<batch>'))"
        python manage.py shell -c "from crm_app.services.care_touches import revert_backfill_batch as r; print(r('<batch>', execute=True))"
    """
    if not isinstance(batch, str) or not batch.strip():
        raise ValueError('batch is required')
    rows = CareTouch.objects.filter(source='gmail_backfill', backfill_batch=batch)
    if not execute:
        return {'batch': batch, 'execute': False, 'matched': rows.count(), 'deleted': 0}
    with transaction.atomic():
        ids = list(rows.select_for_update().values_list('pk', flat=True))
        deleted, _ = CareTouch.objects.filter(pk__in=ids).delete()
        AuditLog.objects.create(
            user=None,
            action='DELETE',
            model_name='CareTouch',
            record_id=f'batch:{batch}'[:100],
            additional_data={
                'operation': 'revert_backfill_batch',
                'source': 'gmail_backfill',
                'backfill_batch': batch,
                'count': deleted,
            },
        )
    return {'batch': batch, 'execute': True, 'matched': len(ids), 'deleted': deleted}
