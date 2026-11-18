"""The business day: BMAsia runs on Bangkok time.

A date the CRM stamps on a record (sent, accepted, ended, paid, issued) and every
"is this today / overdue / expired" check uses the calendar day in ``TIME_ZONE``
(Asia/Bangkok), not the UTC date. Between 00:00 and 07:00 in Bangkok the UTC date
is still the previous day, so ``timezone.now().date()`` stamps yesterday.

Instants (``*_at`` timestamps, expiry of tokens, "24 hours ago") stay
``timezone.now()``; only calendar days go through here.
"""
from django.utils import timezone


def business_today():
    """Today's date in Bangkok (the project's ``TIME_ZONE``)."""
    return timezone.localdate()
