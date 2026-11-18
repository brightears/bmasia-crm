"""API error replies that never carry internal exception text.

- ``api_exception_handler`` is the DRF ``EXCEPTION_HANDLER``. Everything DRF already
  handles (validation, authentication, permission, not found, throttling, bad
  request bodies) keeps its usual reply. A delete blocked by a protecting foreign
  key gets 409 with the kinds of records in the way. Any other exception is logged
  with its traceback and a request id, and the caller gets a generic message with
  that id.
- ``internal_error_text`` does the same for views that catch an exception
  themselves and put a message in their own reply.

The request id is the ``X-Request-ID`` header when the caller sent a sensible one,
otherwise a new random id; it is kept on the request so every log line for the
request shares it.
"""
import logging
import re
import uuid

from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback

logger = logging.getLogger('crm_app.api_errors')

GENERIC_ERROR = 'Something went wrong on the server'
_INCOMING_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')


def request_id_for(request):
    """The id for this request, made once and reused."""
    raw = getattr(request, '_request', request)  # DRF Request wraps Django's HttpRequest
    if raw is None:
        return uuid.uuid4().hex[:16]
    existing = getattr(raw, 'crm_request_id', None)
    if existing:
        return existing
    incoming = (getattr(raw, 'META', {}) or {}).get('HTTP_X_REQUEST_ID', '')
    request_id = incoming if _INCOMING_ID.match(incoming or '') else uuid.uuid4().hex[:16]
    try:
        raw.crm_request_id = request_id
    except AttributeError:
        pass
    return request_id


def _log(request, exc, summary):
    raw = getattr(request, '_request', request)
    logger.error(
        '%s [request_id=%s] %s %s', summary, request_id_for(request),
        getattr(raw, 'method', '-'), getattr(raw, 'path', '-'),
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def internal_error_text(request, exc, summary=GENERIC_ERROR):
    """Log ``exc`` and return text safe to show: the summary plus the request id."""
    _log(request, exc, summary)
    return f'{summary}. Reference: {request_id_for(request)}'


def smtp_error_text(request, exc):
    """A mail-settings check failed: say which step, not the mail server's raw reply."""
    import smtplib

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        summary = 'The mail server did not accept this email address and app password'
    elif isinstance(exc, smtplib.SMTPException):
        summary = 'The mail server refused the request'
    elif isinstance(exc, OSError):
        summary = 'Could not connect to the mail server'
    else:
        summary = GENERIC_ERROR
    return internal_error_text(request, exc, summary)


def _blocking_kinds(exc):
    objects = getattr(exc, 'protected_objects', None) or getattr(exc, 'restricted_objects', None) or []
    return sorted({str(obj._meta.verbose_name_plural).lower() for obj in objects})


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get('request')
    if isinstance(exc, (ProtectedError, RestrictedError)):
        set_rollback()
        kinds = _blocking_kinds(exc)
        detail = f" ({', '.join(kinds)})" if kinds else ''
        return Response(
            {'error': f'This record cannot be deleted because other records depend on it{detail}.',
             'code': 'protected'},
            status=status.HTTP_409_CONFLICT,
        )

    set_rollback()
    request_id = request_id_for(request)
    _log(request, exc, 'Unhandled API error')
    return Response(
        {'error': f'{GENERIC_ERROR}. Reference: {request_id}', 'request_id': request_id},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={'X-Request-ID': request_id},
    )
