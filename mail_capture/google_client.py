"""``GoogleGmailClient``: the real Gmail API behind the ``GmailClient`` protocol.

Built on the official client library (``googleapiclient.discovery.build``
with the discovery document bundled in the package, so building the client
makes no network call). One client per mailbox, authorised with the delegated
credential from ``credentials.delegated_credentials``; ``userId='me'`` is then
that mailbox.

* Errors from Google become ``GmailError`` subclasses: 404/410 gone, 429 or
  a 403 rate-limit reason (with Retry-After when sent), 5xx. Authentication
  and permission failures become ``GmailAuthError`` and are never retried: a
  refused token (``RefreshError``: ``unauthorized_client``, ``invalid_grant``,
  ...), an unreachable token endpoint or a refused signBlob
  (``google.auth`` ``TransportError``), Gmail's 401, and a 403 that is not a
  rate limit. Only the OAuth error code is kept, never the library's message
  (it can quote the response). Other transport failures become a retryable
  503. The library's own retries are off: the sync engine retries with backoff.
* ``get_messages`` fetches up to ``BATCH_SIZE`` messages in one HTTP batch
  request (Gmail allows 100 per batch and recommends no more than 50; each
  call in a batch still costs its own quota units). A failed item comes back
  as that item's error; only a failure of the whole request is raised.
* ``pace`` keeps calls under the per-mailbox and per-project quota per
  minute (``gmail_client.QuotaPacer``); the engine calls it before each call.
* Nothing is fetched at import; Google libraries are imported when a client
  is built.
"""
import json

from .gmail_client import (
    GmailAuthError, GmailNotFound, GmailServerError, error_for_status, pacers_for,
)
from .parse import METADATA_HEADERS


BATCH_SIZE = 50
HISTORY_TYPES = ['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved']


def _reason(exc):
    try:
        payload = json.loads(exc.content.decode('utf-8', 'replace'))
        errors = payload.get('error', {}).get('errors') or []
        if errors:
            return str(errors[0].get('reason') or '')[:80]
        return str(payload.get('error', {}).get('status') or '')[:80]
    except Exception:
        return ''


_OAUTH_CODES = ('unauthorized_client', 'invalid_grant', 'access_denied', 'invalid_scope', 'invalid_client')


def _oauth_code(exc):
    """The OAuth error code of a ``RefreshError``, from the decoded response
    when the library kept it, else from the start of its message."""
    for arg in getattr(exc, 'args', ())[1:]:
        if isinstance(arg, dict) and str(arg.get('error', '')) in _OAUTH_CODES:
            return str(arg['error'])
    first = str(exc.args[0]) if getattr(exc, 'args', None) else ''
    for code in _OAUTH_CODES:
        if first.startswith(code) or f"'{code}'" in first[:200] or f'"{code}"' in first[:200]:
            return code
    return 'token_refused'


def _retry_after(exc):
    try:
        value = exc.resp.get('retry-after')
        return min(300.0, max(0.0, float(value))) if value not in (None, '') else None
    except (AttributeError, TypeError, ValueError):
        return None


def _translate(exc):
    """A Gmail error for an exception from the library or the transport.
    Never carries the exception's message: only a status, a reason code or an
    OAuth error code."""
    from google.auth import exceptions as auth_exceptions
    from googleapiclient.errors import HttpError
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, 'status', 500)
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = 500
        return error_for_status(status, _reason(exc), _retry_after(exc))
    if isinstance(exc, auth_exceptions.RefreshError):
        return GmailAuthError(_oauth_code(exc))
    if isinstance(exc, auth_exceptions.TransportError):
        # Raised while making the credential's token: the signBlob call
        # (keyless mode) or the token endpoint itself.
        text = str(exc.args[0]) if exc.args else ''
        return GmailAuthError('signblob_refused' if 'signblob' in text[:80].lower() else
                              'token_endpoint_unreachable')
    if isinstance(exc, auth_exceptions.GoogleAuthError):
        return GmailAuthError('credentials')
    return GmailServerError(503, f'transport {type(exc).__name__}')


def _token_error(exc):
    """An error while making the access token (before any Gmail call)."""
    error = _translate(exc)
    if isinstance(error, GmailAuthError):
        return error
    # A socket or httplib2 error on the token request: the endpoint (or the
    # IAM signBlob endpoint) could not be reached.
    return GmailAuthError('token_endpoint_unreachable')


class GoogleGmailClient:
    """One mailbox through the Gmail API. In production pass ``credentials``
    only. ``http`` is for tests: a fake transport, used as is, or (with
    ``credentials``) under the credential like the real one."""

    supports_batch = True

    def __init__(self, mailbox_email, credentials=None, http=None, pacers=None):
        from googleapiclient.discovery import build
        self.mailbox_email = mailbox_email.lower()
        self._pacers = tuple(pacers) if pacers is not None else pacers_for(self.mailbox_email)
        self._credentials = credentials
        self._token_http = None
        kwargs = {'cache_discovery': False, 'static_discovery': True, 'num_retries': 0}
        if credentials is not None:
            # What build(credentials=...) does, kept in hand so the token can be
            # made on its own first (its errors are then auth errors, not 503s).
            import google_auth_httplib2
            from googleapiclient.http import build_http
            self._token_http = http if http is not None else build_http()
            kwargs['http'] = google_auth_httplib2.AuthorizedHttp(credentials, http=self._token_http)
        elif http is not None:
            kwargs['http'] = http
        self._service = build('gmail', 'v1', **kwargs)
        self._users = self._service.users()

    def _ensure_token(self):
        """Make the access token before the first call (and after expiry), so a
        refused or unreachable token request ends the run as an auth error."""
        if self._credentials is None or self._credentials.valid:
            return
        import google_auth_httplib2
        try:
            self._credentials.refresh(google_auth_httplib2.Request(self._token_http))
        except Exception as exc:
            raise _token_error(exc) from None

    def _run(self, request):
        self._ensure_token()
        try:
            return request.execute(num_retries=0)
        except Exception as exc:
            raise _translate(exc) from None

    # -- pacing ----------------------------------------------------------------
    def pace(self, units, sleep):
        """Wait until ``units`` may be spent under every bucket."""
        for pacer in self._pacers:
            pacer.acquire(units, sleep)

    def drain_pace(self):
        for pacer in self._pacers[:1]:   # Gmail said 429 for this mailbox
            pacer.drain()

    # -- the protocol ----------------------------------------------------------
    def get_profile(self):
        return self._run(self._users.getProfile(userId='me'))

    def list_labels(self):
        return self._run(self._users.labels().list(userId='me')).get('labels', [])

    def list_messages(self, page_token=None, q=None, max_results=100):
        kwargs = {'userId': 'me', 'maxResults': max_results}
        if page_token:
            kwargs['pageToken'] = page_token
        if q:
            kwargs['q'] = q   # not allowed under gmail.metadata; the engine never sends one
        return self._run(self._users.messages().list(**kwargs))

    def list_history(self, start_history_id, page_token=None, max_results=100):
        kwargs = {'userId': 'me', 'startHistoryId': str(start_history_id), 'maxResults': max_results,
                  'historyTypes': HISTORY_TYPES}
        if page_token:
            kwargs['pageToken'] = page_token
        return self._run(self._users.history().list(**kwargs))

    def get_message(self, message_id, format='metadata', metadata_headers=None):
        return self._run(self._message_request(message_id, format, metadata_headers))

    def get_attachment(self, message_id, attachment_id):
        return self._run(self._users.messages().attachments().get(
            userId='me', messageId=message_id, id=attachment_id))

    def get_messages(self, message_ids, format='metadata', metadata_headers=None):
        """Many ``messages.get`` in HTTP batches of ``BATCH_SIZE``. Returns
        ``{id: message}``; a message gone since it was listed (404/410) maps
        to None, and an item Gmail refused maps to its ``GmailError`` (the
        engine decides: retry, fail that message, or stop the run). Only a
        failure of a whole batch request is raised."""
        out = {}
        ids = list(message_ids)
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start:start + BATCH_SIZE]

            def collect(request_id, response, exception, out=out):
                if exception is None:
                    out[request_id] = response
                    return
                error = _translate(exception)
                out[request_id] = None if isinstance(error, GmailNotFound) else error

            self._ensure_token()
            batch = self._service.new_batch_http_request(callback=collect)
            for message_id in chunk:
                batch.add(self._message_request(message_id, format, metadata_headers), request_id=message_id)
            try:
                batch.execute()
            except Exception as exc:
                raise _translate(exc) from None
        return out

    def _message_request(self, message_id, format, metadata_headers):
        kwargs = {'userId': 'me', 'id': message_id, 'format': format}
        if format == 'metadata':
            kwargs['metadataHeaders'] = list(metadata_headers or METADATA_HEADERS)
        return self._users.messages().get(**kwargs)


def client_for(mailbox):
    """Client factory for the sync engine: a delegated credential (which
    refuses disabled mailboxes and switched-off capture) and a client."""
    from .credentials import delegated_credentials
    return GoogleGmailClient(mailbox.email, credentials=delegated_credentials(mailbox))
