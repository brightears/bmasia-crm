"""``GoogleGmailClient``: the real Gmail API behind the ``GmailClient`` protocol.

Built on the official client library (``googleapiclient.discovery.build``
with the discovery document bundled in the package, so building the client
makes no network call). One client per mailbox, authorised with the delegated
credential from ``credentials.delegated_credentials``; ``userId='me'`` is then
that mailbox.

* Errors from Google become ``GmailError`` subclasses (404, 429 or a 403
  rate-limit reason, 5xx); transport failures become a retryable 503. The
  library's own retries are off: the sync engine retries with backoff.
* ``get_messages`` fetches up to ``BATCH_SIZE`` messages in one HTTP batch
  request (Gmail allows 100 per batch and recommends no more than 50; each
  call in a batch still costs its own quota units).
* Nothing is fetched at import; Google libraries are imported when a client
  is built.
"""
import json

from .gmail_client import GmailNotFound, GmailServerError, error_for_status
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


def _translate(exc):
    """A Gmail error for an exception from the library or the transport."""
    from googleapiclient.errors import HttpError
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, 'status', 500)
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = 500
        return error_for_status(status, _reason(exc))
    return GmailServerError(503, f'transport {type(exc).__name__}')


class GoogleGmailClient:
    """One mailbox through the Gmail API. ``http`` is for tests (a fake
    transport); in production pass ``credentials`` only."""

    supports_batch = True

    def __init__(self, mailbox_email, credentials=None, http=None):
        from googleapiclient.discovery import build
        self.mailbox_email = mailbox_email.lower()
        kwargs = {'cache_discovery': False, 'static_discovery': True, 'num_retries': 0}
        if http is not None:
            kwargs['http'] = http
        else:
            kwargs['credentials'] = credentials
        self._service = build('gmail', 'v1', **kwargs)
        self._users = self._service.users()

    def _run(self, request):
        try:
            return request.execute(num_retries=0)
        except Exception as exc:
            raise _translate(exc) from None

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
        ``{id: message}``; a message gone since it was listed (404) maps to
        None. Any other error fails the whole call with a ``GmailError``."""
        out = {}
        ids = list(message_ids)
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start:start + BATCH_SIZE]
            failures = {}

            def collect(request_id, response, exception, out=out, failures=failures):
                if exception is None:
                    out[request_id] = response
                    return
                error = _translate(exception)
                if isinstance(error, GmailNotFound):
                    out[request_id] = None
                else:
                    failures[request_id] = error

            batch = self._service.new_batch_http_request(callback=collect)
            for message_id in chunk:
                batch.add(self._message_request(message_id, format, metadata_headers), request_id=message_id)
            try:
                batch.execute()
            except Exception as exc:
                raise _translate(exc) from None
            if failures:
                raise next(iter(failures.values()))
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
