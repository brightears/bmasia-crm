"""Delegated Google credentials for one capture mailbox.

``delegated_credentials(mailbox)`` is the only place a Google credential is
made. It refuses, before any Google library is touched:

* while capture is switched off (``conf.capture_state``);
* for a mailbox that is not enabled, or one on the hard deny-list
  ``GOOGLE_CAPTURE_NEVER_MAILBOXES`` (which overrides the table);
* for ``body_mode='body'`` while the scope is ``gmail.metadata`` (bodies need
  ``gmail.readonly``);
* in mode ``off`` (the default): ``CredentialsOff`` is raised.

Modes (``GOOGLE_CAPTURE_CREDENTIALS_MODE``):

* ``keyless``: workload identity federation. The process's own federated
  credential (``google.auth.default()``, which on Render reads the config
  Render writes when ``GCP_WORKLOAD_IDENTITY_PROVIDER`` is set) signs the
  delegation JWT through the IAM Credentials API (``google.auth.iam.Signer``,
  signBlob) as ``GOOGLE_CAPTURE_SERVICE_ACCOUNT``; the federated identity needs
  Service Account Token Creator on that service account. No key is stored.
* ``key_file``: a service-account JSON key at ``GOOGLE_CAPTURE_KEY_FILE`` (a
  Render secret file, never an environment variable or the repository).

Either way the result is a ``google.oauth2.service_account.Credentials`` with
``subject`` set to the mailbox (domain-wide delegation) and only the capture
scope. Nothing here logs a credential, a key path or a token; errors carry
class names only. Google libraries are imported inside the functions, so
importing this module costs nothing and opens nothing.
"""
from django.conf import settings

from . import conf


SCOPES = {
    'metadata': 'https://www.googleapis.com/auth/gmail.metadata',
    'readonly': 'https://www.googleapis.com/auth/gmail.readonly',
}
TOKEN_URI = 'https://oauth2.googleapis.com/token'
# Scope the federated (source) credential needs to call the IAM signBlob API.
IAM_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'
MODES = ('off', 'keyless', 'key_file')


class CredentialsRefused(Exception):
    """A credential must not be made for this mailbox (or at all, now)."""


class CredentialsOff(CredentialsRefused):
    """GOOGLE_CAPTURE_CREDENTIALS_MODE is off (the default)."""


class CredentialsMisconfigured(CredentialsRefused):
    """A setting the chosen mode needs is missing or invalid."""


def mode():
    value = str(getattr(settings, 'GOOGLE_CAPTURE_CREDENTIALS_MODE', 'off') or 'off').strip().lower()
    return value if value in MODES else 'invalid'


def scope_name():
    value = str(getattr(settings, 'GOOGLE_CAPTURE_SCOPE', 'metadata') or 'metadata').strip().lower()
    return value if value in SCOPES else 'invalid'


def never_mailboxes():
    return {str(v).strip().lower() for v in getattr(settings, 'GOOGLE_CAPTURE_NEVER_MAILBOXES', ()) or ()
            if str(v).strip()}


def check_mailbox(mailbox):
    """Raise ``CredentialsRefused`` unless a credential may be made for this
    mailbox now. Reads settings and the row only; touches no Google code."""
    state = conf.capture_state()
    if not state.enabled:
        raise CredentialsRefused(state.reason)
    current = mode()
    if current == 'off':
        raise CredentialsOff('GOOGLE_CAPTURE_CREDENTIALS_MODE is off')
    if current == 'invalid':
        raise CredentialsMisconfigured('GOOGLE_CAPTURE_CREDENTIALS_MODE must be off, keyless or key_file')
    if scope_name() == 'invalid':
        raise CredentialsMisconfigured('GOOGLE_CAPTURE_SCOPE must be metadata or readonly')
    from .models import CaptureMailbox
    fresh = CaptureMailbox.objects.filter(pk=mailbox.pk).values('enabled', 'body_mode', 'email').first()
    if fresh is None or not fresh['enabled']:
        raise CredentialsRefused('this mailbox is not enabled')
    if fresh['email'] in never_mailboxes():
        raise CredentialsRefused('this mailbox is on GOOGLE_CAPTURE_NEVER_MAILBOXES')
    if fresh['body_mode'] == 'body' and scope_name() == 'metadata':
        raise CredentialsRefused("body_mode 'body' needs GOOGLE_CAPTURE_SCOPE=readonly "
                                 '(gmail.metadata cannot read bodies)')
    return fresh


def delegated_credentials(mailbox):
    """A delegated credential for exactly this mailbox and the capture scope."""
    fresh = check_mailbox(mailbox)
    scopes = [SCOPES[scope_name()]]
    subject = fresh['email']
    if mode() == 'key_file':
        return _from_key_file(scopes, subject)
    return _keyless(scopes, subject)


def _from_key_file(scopes, subject):
    path = str(getattr(settings, 'GOOGLE_CAPTURE_KEY_FILE', '') or '').strip()
    if not path:
        raise CredentialsMisconfigured('GOOGLE_CAPTURE_KEY_FILE is not set')
    from google.oauth2 import service_account
    try:
        return service_account.Credentials.from_service_account_file(
            path, scopes=scopes, subject=subject)
    except (OSError, ValueError) as exc:
        # Never echo the path or the file's content.
        raise CredentialsMisconfigured(f'the key file could not be read ({type(exc).__name__})') from None


def _keyless(scopes, subject):
    account = str(getattr(settings, 'GOOGLE_CAPTURE_SERVICE_ACCOUNT', '') or '').strip()
    if not account or '@' not in account:
        raise CredentialsMisconfigured('GOOGLE_CAPTURE_SERVICE_ACCOUNT is not set')
    import google.auth
    from google.auth import iam
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    try:
        source, _ = google.auth.default(scopes=[IAM_SCOPE])
    except google.auth.exceptions.DefaultCredentialsError:
        raise CredentialsMisconfigured('no federated credential found (workload identity federation '
                                       'is not configured for this service)') from None
    signer = iam.Signer(Request(), source, account)
    return service_account.Credentials(signer, account, TOKEN_URI, scopes=scopes, subject=subject)
