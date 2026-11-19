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

from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback

from crm_app.request_ids import request_id_for  # noqa: F401 (re-exported)
from crm_app.services.exception_safety import (  # noqa: F401 (describe_mail_exception re-exported)
    describe_exception, describe_mail_exception, log_exception,
)

logger = logging.getLogger('crm_app.api_errors')

GENERIC_ERROR = 'Something went wrong on the server'


def _log(request, exc, summary):
    """Log an unexpected error with a reference; never a mail server's reply (exception_safety rule)."""
    raw = getattr(request, '_request', request)
    message = '%s [request_id=%s] %s %s' % (
        summary, request_id_for(request), getattr(raw, 'method', '-'), getattr(raw, 'path', '-'))
    log_exception(logger, message, exc)


def internal_error_text(request, exc, summary=GENERIC_ERROR):
    """Log ``exc`` and return text safe to show: the summary plus the request id."""
    _log(request, exc, summary)
    return f'{summary}. Reference: {request_id_for(request)}'


def client_error_text(exc):
    """The message of an exception that means the request itself was wrong, else None.

    Django validation errors (a malformed id, a bad value), ValueError raised on input,
    FieldError (an unknown field in filter criteria) and a missing related record are
    the caller's to fix, and their message says what to fix.
    """
    from django.core.exceptions import FieldError, ObjectDoesNotExist, ValidationError

    if isinstance(exc, ValidationError):
        return ' '.join(exc.messages)
    if isinstance(exc, (ValueError, FieldError)):
        return str(exc)
    if isinstance(exc, ObjectDoesNotExist):
        return 'A record named in the request does not exist.'
    return None


def error_response(request, exc, summary=GENERIC_ERROR):
    """400 with the reason for a caller's mistake; otherwise a logged 500 with a reference."""
    reason = client_error_text(exc)
    if reason:
        return Response({'error': reason}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'error': internal_error_text(request, exc, summary)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def mail_failure_text(request, summary, detail):
    """The mail layer failed: log what happened (never a mail server's raw reply); give a reference."""
    reference = request_id_for(request)  # a fresh id when there is no request (crons)
    if isinstance(detail, BaseException):
        detail = describe_exception(detail)
    logger.error('%s [request_id=%s]: %s', summary, reference, detail)
    return f'{summary}. Reference: {reference}'


# Mail-layer messages written by the code itself, safe to pass on.
_OWN_MAIL_MESSAGES = re.compile(
    r'^(No recipients found for this \w+'
    r'|No receipt number generated for this invoice'
    r'|\w+ with ID [\w-]+ not found'
    r'|Contract PDF generation was blocked \(HTTP \d{3}\)'
    r'|.+\. Reference: [A-Za-z0-9._-]{8,64})$'
)


def safe_mail_message(request, message):
    """Pass on the mail layer's own wording; replace anything else (a mail server's reply)."""
    if isinstance(message, str) and _OWN_MAIL_MESSAGES.match(message):
        return message
    return mail_failure_text(request, 'Failed to send the email', message)


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
        return internal_error_text(request, exc, GENERIC_ERROR)
    raw = getattr(request, '_request', request)
    logger.error(
        '%s [request_id=%s] %s %s: %s', summary, request_id_for(request),
        getattr(raw, 'method', '-'), getattr(raw, 'path', '-'), describe_mail_exception(exc),
    )
    return f'{summary}. Reference: {request_id_for(request)}'


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
