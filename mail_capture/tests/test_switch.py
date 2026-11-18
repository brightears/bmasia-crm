"""The master switch, the per-mailbox switch, dry-run and the self-check."""
import importlib
import socket
import threading
from io import StringIO

import pytest
from django.core.management import call_command

from crm_app.models import Company, Contact

from mail_capture.gmail_client import FakeGmailClient
from mail_capture.models import (
    CaptureMailbox, CaptureRun, MailboxAccessLog, MailMessage, UnmatchedSender,
)
from mail_capture.sync import CaptureRefused, sync_all_enabled, sync_mailbox

from .builders import SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, no_client, primed, recent
from .test_sync import _table_counts


pytestmark = pytest.mark.django_db


class TestDisabled:
    def test_flag_off_makes_no_client_and_writes_nothing(self, settings):
        settings.GOOGLE_CAPTURE_ENABLED = False
        settings.CAPTURE_INTERNAL_DOMAINS = ['ourco.example']
        mb = make_mailbox()
        before = _table_counts()
        result = sync_mailbox(mb.pk, no_client)
        assert result.outcome == 'disabled' and 'GOOGLE_CAPTURE_ENABLED' in result.reason
        assert sync_all_enabled(no_client)[0].outcome == 'disabled'
        assert _table_counts() == before

    def test_flag_off_refuses_a_real_client_even_for_the_selfcheck_path(self, settings):
        settings.GOOGLE_CAPTURE_ENABLED = False
        settings.CAPTURE_INTERNAL_DOMAINS = ['ourco.example']
        mb = make_mailbox()

        class NotFake:
            mailbox_email = SALES
            calls = []

            def __getattr__(self, name):
                raise AssertionError(f'{name} called')

        with pytest.raises(CaptureRefused):
            sync_mailbox(mb.pk, lambda m: NotFake(), fake_only=True)

    def test_internal_domains_missing_is_disabled(self, settings):
        settings.GOOGLE_CAPTURE_ENABLED = True
        settings.CAPTURE_INTERNAL_DOMAINS = []
        mb = make_mailbox()
        result = sync_mailbox(mb.pk, no_client)
        assert result.outcome == 'disabled' and 'CAPTURE_INTERNAL_DOMAINS' in result.reason

    def test_mailbox_not_enabled(self, capture_on):
        mb = make_mailbox(enabled=False)
        assert sync_mailbox(mb.pk, no_client).outcome == 'disabled'
        assert sync_all_enabled(no_client)[0].reason == 'no mailbox is enabled'
        assert CaptureRun.objects.count() == 0

    def test_all_enabled_skips_disabled_mailboxes(self, capture_on):
        on = make_mailbox(SALES)
        make_mailbox('off@ourco.example', enabled=False)
        client = primed(on)
        factory = factory_for(client)
        results = sync_all_enabled(factory, sleep=lambda s: None)
        assert [r.outcome for r in results] == ['ok'] and factory.calls == [SALES]

    def test_selfcheck_command_flag_off_leaves_nothing(self, settings):
        settings.GOOGLE_CAPTURE_ENABLED = False
        settings.CAPTURE_INTERNAL_DOMAINS = []
        before = _table_counts()
        companies, contacts = Company.objects.count(), Contact.objects.count()
        out = StringIO()
        call_command('mail_capture_selfcheck', stdout=out, stderr=StringIO())
        text = out.getvalue()
        assert 'GOOGLE_CAPTURE_ENABLED: off' in text
        assert 'pipeline: OK' in text
        assert 'pipeline messages stored: 5' in text
        assert _table_counts() == before
        assert (Company.objects.count(), Contact.objects.count()) == (companies, contacts)
        # counts only: no fixture subject or address in the output
        assert 'casey' not in text and 'renewal question' not in text

    def test_selfcheck_no_pipeline(self, settings):
        settings.GOOGLE_CAPTURE_ENABLED = False
        out = StringIO()
        call_command('mail_capture_selfcheck', '--no-pipeline', stdout=out)
        assert 'pipeline' not in out.getvalue()


class TestDryRun:
    def test_dry_run_writes_only_its_run_and_access_log(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        mb = make_mailbox(body_mode='body')
        client = primed(mb)
        client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent()))
        client.add_message(gmail_message('g2', 'x@unknown.test', [SALES], date=recent(),
                                         message_id='<u@mail.example.org>'))
        mb.refresh_from_db()
        snapshot_fields = (mb.history_id, mb.last_poll_at, mb.lease_token, mb.updated_at)
        before = _table_counts()
        result = sync_mailbox(mb.pk, factory_for(client), dry_run=True, sleep=lambda s: None)
        after = _table_counts()
        assert result.outcome == 'ok' and result.counts['matched'] == 1 and result.counts['unmatched'] == 1
        assert after.pop('CaptureRun') == before.pop('CaptureRun') + 1
        assert after.pop('MailboxAccessLog') == before.pop('MailboxAccessLog') + 1
        assert after == before
        mb.refresh_from_db()
        assert (mb.history_id, mb.last_poll_at, mb.lease_token, mb.updated_at) == snapshot_fields
        assert CaptureRun.objects.get().dry_run and MailboxAccessLog.objects.get().dry_run
        assert not [c for c in client.calls if c[1].get('format') == 'full']
        assert MailMessage.objects.count() == 0 and UnmatchedSender.objects.count() == 0


class TestNoSideEffectsOnImport:
    def test_import_opens_no_socket_and_starts_no_thread(self, monkeypatch):
        def refuse(*args, **kwargs):
            raise AssertionError('network access during import')

        monkeypatch.setattr(socket.socket, 'connect', refuse)
        monkeypatch.setattr(socket, 'create_connection', refuse)
        threads = threading.active_count()
        import mail_capture
        for name in ('conf', 'parse', 'rules', 'match', 'gmail_client', 'snapshot', 'purge',
                     'sync', 'admin', 'models'):
            importlib.import_module(f'mail_capture.{name}')
        importlib.reload(importlib.import_module('mail_capture.parse'))
        assert threading.active_count() == threads
        assert mail_capture.__doc__

    def test_fake_client_records_calls(self):
        client = FakeGmailClient(SALES)
        client.get_profile()
        assert client.calls == [('get_profile', {})]
        assert CaptureMailbox.objects.count() == 0
