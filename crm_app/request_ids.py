"""One id per API request, so a reply's "Reference" can be found in the server log.

The id is the caller's ``X-Request-ID`` header when it is a sensible one, otherwise a new
random id. It is kept on the request, so every log line for the request shares it.
"""
import re
import uuid

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
