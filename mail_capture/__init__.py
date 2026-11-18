"""Capture of customer email from Google Workspace mailboxes into the CRM.

Switched off by default (settings.GOOGLE_CAPTURE_ENABLED). This package has no
Google client: the sync engine works against the ``GmailClient`` protocol in
``gmail_client.py``, for which only ``FakeGmailClient`` exists so far.

Importing this package opens no connection, starts no thread and registers no
signal handler that touches another app's models.
"""
