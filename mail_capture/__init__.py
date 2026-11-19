"""Capture of customer email from Google Workspace mailboxes into the CRM.

Switched off by default (settings.GOOGLE_CAPTURE_ENABLED). The sync engine
works against the ``GmailClient`` protocol in ``gmail_client.py``:
``FakeGmailClient`` for tests and the self-check, ``GoogleGmailClient``
(``google_client.py``) for real mailboxes, with credentials from
``credentials.py`` (mode ``off`` by default) and the ``gmail_sync`` command.

Importing this package opens no connection, starts no thread, imports no
Google library and registers no signal handler that touches another app's
models.
"""
