"""The sync engine against FakeGmailClient."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from crm_app.models import Contract, EmailLog, Invoice, Quote

from mail_capture import rules as capture_rules
from mail_capture import sync
from mail_capture.gmail_client import FakeGmailClient
from mail_capture.models import (
    CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog, MailboxCopy,
    MailConversation, MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from mail_capture.sync import sync_mailbox

from .builders import (
    OPS, SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed,
    recent,
)


pytestmark = pytest.mark.django_db


def run(mailbox, client, **kwargs):
    kwargs.setdefault('sleep', lambda s: None)
    return sync_mailbox(mailbox.pk, factory_for(client), **kwargs)


@pytest.fixture
def lagoon(capture_on):
    company = make_company('Lagoon Test Hotel')
    contact = make_contact(company, 'pat@lagoon.test', 'Pat Example')
    return company, contact


def inbound(gid, when=None, frm='Pat Example <pat@lagoon.test>', to=(SALES,), **kwargs):
    return gmail_message(gid, frm, to, date=when or recent(5), **kwargs)


class TestStorage:
    def test_one_message_in_two_mailboxes_is_one_message_two_copies(self, lagoon):
        a, b = make_mailbox(SALES), make_mailbox(OPS)
        ca, cb = primed(a), primed(b)
        shared = dict(message_id='<shared-1@mail.example.org>', to=(SALES, OPS))
        ca.add_message(inbound('ga1', **shared))
        cb.add_message(inbound('gb7', **shared))
        assert run(a, ca).counts['stored'] == 1
        result = run(b, cb)
        assert result.counts['stored'] == 0 and result.counts['copies_added'] == 1
        assert MailMessage.objects.count() == 1
        message = MailMessage.objects.get()
        assert sorted(message.copies.values_list('gmail_id', flat=True)) == ['ga1', 'gb7']
        assert MailConversation.objects.get().message_count == 1

    def test_rerun_is_a_no_op(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1'))
        client.add_message(inbound('g2', message_id='<g2@mail.example.org>'))
        run(mb, client)
        before = _table_counts()
        mb.refresh_from_db()
        cursor = mb.history_id
        # Re-read the same history from the old cursor: everything is known.
        CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='1000')
        second = run(mb, client)
        assert second.counts['stored'] == 0 and second.counts['already_known'] == 2
        after = _table_counts()
        after.pop('CaptureRun'); after.pop('MailboxAccessLog')
        before.pop('CaptureRun'); before.pop('MailboxAccessLog')
        assert after == before
        mb.refresh_from_db()
        assert mb.history_id == cursor

    def test_stores_participants_matches_and_conversation(self, lagoon):
        company, contact = lagoon
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', cc=('Someone New <new.person@lagoon.test>',)))
        run(mb, client)
        message = MailMessage.objects.get()
        assert message.direction == 'inbound' and message.body_text is None
        assert message.capture_state == 'headers'
        roles = {(p.role, p.address, p.is_internal, p.contact_id) for p in message.participants.all()}
        assert ('from', 'pat@lagoon.test', False, contact.pk) in roles
        assert ('to', SALES, True, None) in roles
        conv = message.conversation
        assert (conv.company_id, conv.link_state) == (company.pk, 'auto')
        assert set(MailMatch.objects.values_list('target_type', 'status')) == {
            ('company', 'auto'), ('contact', 'auto'),
        }
        # The unknown colleague at the matched company is queued as a contact suggestion.
        row = UnmatchedSender.objects.get(address='new.person@lagoon.test')
        assert row.reason == 'domain_match' and row.candidate_company_ids == [str(company.pk)]

    def test_first_incremental_without_cursor_only_sets_it(self, lagoon):
        mb = make_mailbox()
        client = FakeGmailClient(mb.email, messages=[inbound('old')])
        result = run(mb, client)
        mb.refresh_from_db()
        assert result.outcome == 'ok' and mb.history_id == client.history_id
        assert MailMessage.objects.count() == 0


class TestCursor:
    def test_crash_mid_batch_does_not_advance_cursor(self, lagoon, monkeypatch):
        mb = make_mailbox()
        client = primed(mb)
        start = mb.history_id
        for i in range(3):
            client.add_message(inbound(f'g{i}', message_id=f'<c{i}@mail.example.org>'))
        real_store = sync._Runner._store
        calls = {'n': 0}

        def flaky(self, plan, now):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('simulated crash')
            return real_store(self, plan, now)

        monkeypatch.setattr(sync._Runner, '_store', flaky)
        with pytest.raises(RuntimeError):
            run(mb, client)
        mb.refresh_from_db()
        assert mb.history_id == start
        assert MailMessage.objects.count() == 0       # the whole page rolled back
        assert mb.lease_token == ''                    # lease released
        assert CaptureRun.objects.get().outcome == 'error'

        monkeypatch.setattr(sync._Runner, '_store', real_store)
        assert run(mb, client).counts['stored'] == 3
        mb.refresh_from_db()
        assert mb.history_id == client.history_id

    def test_cursor_advances_page_by_page(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        for i in range(5):
            client.add_message(inbound(f'g{i}', message_id=f'<p{i}@mail.example.org>'))
        client.fail('get_message', 500, times=99, after=3)   # page 2 fails for good
        result = run(mb, client, page_size=2)
        assert result.outcome == 'error'
        mb.refresh_from_db()
        assert MailMessage.objects.count() == 2
        assert int(mb.history_id) == int(primed_start(client)) + 2

    def test_history_404_sets_resync_then_resync_runs(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', message_id='<r1@mail.example.org>'))
        client.add_message(inbound('g2', message_id='<r2@mail.example.org>'))
        client.expire_history()
        first = run(mb, client)
        mb.refresh_from_db()
        assert first.outcome == 'resync_needed' and mb.needs_resync
        assert MailMessage.objects.count() == 0

        second = run(mb, client)
        mb.refresh_from_db()
        assert second.kind == 'resync' and second.outcome == 'ok'
        assert not mb.needs_resync and mb.history_id == client.history_id
        assert MailMessage.objects.count() == 2
        assert CaptureRun.objects.filter(kind='resync').count() == 1

    def test_resync_is_bounded(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('old', when=recent(24 * 30), message_id='<old@mail.example.org>'))
        client.add_message(inbound('new', message_id='<new@mail.example.org>'))
        CaptureMailbox.objects.filter(pk=mb.pk).update(needs_resync=True)
        run(mb, client)
        assert list(MailMessage.objects.values_list('rfc_message_id', flat=True)) == ['new@mail.example.org']

    def test_rate_limit_is_retried_with_backoff(self, lagoon, no_sleep):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1'))
        client.fail('get_message', 429, times=2)
        result = run(mb, client, sleep=no_sleep)
        assert result.outcome == 'ok' and result.counts['stored'] == 1
        assert len(no_sleep.delays) == 2 and no_sleep.delays[1] > no_sleep.delays[0] / 2

    def test_persistent_rate_limit_stops_without_moving_cursor(self, lagoon, no_sleep):
        mb = make_mailbox()
        client = primed(mb)
        start = mb.history_id
        client.add_message(inbound('g1'))
        client.fail('list_history', 403, times=10, reason='userRateLimitExceeded')
        result = run(mb, client, sleep=no_sleep)
        mb.refresh_from_db()
        assert result.outcome == 'rate_limited' and mb.history_id == start
        assert mb.consecutive_errors == 1 and mb.last_error.startswith('rate limited')

    def test_backfill_since_date_and_max(self, lagoon):
        mb = make_mailbox()
        client = FakeGmailClient(mb.email, messages=[
            inbound('g-old', when=recent(24 * 40), message_id='<b0@mail.example.org>'),
            inbound('g-a', when=recent(24 * 3), message_id='<b1@mail.example.org>'),
            inbound('g-b', when=recent(24 * 2), message_id='<b2@mail.example.org>'),
        ])
        result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=10))
        mb.refresh_from_db()
        assert result.counts['stored'] == 2
        assert mb.history_id == client.history_id and mb.last_full_sync_at is not None
        capped = make_mailbox(OPS)
        client2 = FakeGmailClient(capped.email, messages=[
            inbound('h1', to=(OPS,), message_id='<b1@mail.example.org>'),
            inbound('h2', to=(OPS,), message_id='<b2@mail.example.org>'),
        ])
        assert run(capped, client2, kind='backfill', since=date(2000, 1, 1), max_messages=1).counts['fetched'] == 1


def primed_start(client):
    return int(client.history_id) - 5


class TestClassification:
    def test_internal_only_mail_is_skipped(self, capture_on):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(gmail_message('g1', SALES, [OPS], date=recent()))
        result = run(mb, client)
        assert result.counts['skipped_internal'] == 1
        assert MailMessage.objects.count() == 0 and UnmatchedSender.objects.count() == 0

    def test_bulk_and_spam_are_skipped(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', extra=[('List-Id', '<list.lagoon.test>')]))
        client.add_message(inbound('g2', message_id='<s2@mail.example.org>', labels=('SPAM',)))
        assert run(mb, client).counts['skipped_system'] == 2
        assert MailMessage.objects.count() == 0

    def test_freemail_goes_to_the_queue_headers_only(self, capture_on, monkeypatch):
        monkeypatch.setattr(capture_rules, 'FREEMAIL_DOMAINS',
                            capture_rules.FREEMAIL_DOMAINS | {'freemail.test'})
        company = make_company('Freemail Domain Company')
        CompanyDomain.objects.create(company=company, domain='freemail.test')
        mb = make_mailbox(body_mode='body')
        client = primed(mb)
        client.add_message(inbound('g1', frm='Some One <some.one@freemail.test>', subject='Hello'))
        result = run(mb, client)
        assert result.counts['unmatched'] == 1
        assert MailMessage.objects.count() == 0
        row = UnmatchedSender.objects.get()
        assert (row.address, row.reason, row.status) == ('some.one@freemail.test', 'freemail', 'open')
        assert row.sample_subjects == ['Hello'] and row.message_count == 1
        assert row.expires_at - row.last_seen == timedelta(days=30)
        assert not [c for c in client.calls if c[1].get('format') == 'full']   # no body read

    def test_unmatched_counts_are_idempotent(self, capture_on):
        a, b = make_mailbox(SALES), make_mailbox(OPS)
        ca, cb = primed(a), primed(b)
        for c in (ca, cb):
            c.add_message(inbound('gx', frm='x@unknown.test', to=(SALES, OPS),
                                  message_id='<u1@mail.example.org>'))
        run(a, ca)
        run(b, cb)
        CaptureMailbox.objects.filter(pk=a.pk).update(history_id='1000')
        run(a, ca)
        row = UnmatchedSender.objects.get()
        assert row.message_count == 1 and sorted(row.mailboxes) == [OPS, SALES]

    def test_shared_domain_never_auto_matches(self, capture_on):
        big, small = make_company('Harbour Group Hotel One'), make_company('Harbour Group Hotel Two')
        for c in (big, small):
            CompanyDomain.objects.create(company=c, domain='harbourgroup.test')
        make_contact(big, 'gm@harbourgroup.test')
        make_contact(big, 'fo@harbourgroup.test')
        make_contact(small, 'eng@harbourgroup.test')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', frm='new.person@harbourgroup.test'))
        run(mb, client)
        assert MailMessage.objects.count() == 0
        row = UnmatchedSender.objects.get()
        assert row.reason == 'shared_domain'
        assert row.candidate_company_ids == [str(big.pk), str(small.pk)]

    def test_unique_domain_matches(self, capture_on):
        company = make_company('Reef Test Resort')
        CompanyDomain.objects.create(company=company, domain='reefresort.test')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', frm='new@reefresort.test'))
        run(mb, client)
        conv = MailConversation.objects.get()
        assert conv.company == company
        assert MailMatch.objects.get(target_type='company').method == 'company_domain'

    def test_contact_on_two_companies_is_ambiguous(self, capture_on):
        one, two = make_company('Twin Record One'), make_company('Twin Record Two')
        make_contact(one, 'owner@twins.test')
        make_contact(two, 'owner@twins.test')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', frm='owner@twins.test'))
        run(mb, client)
        conv = MailConversation.objects.get()
        assert conv.link_state == 'ambiguous' and conv.company is None
        assert set(MailMatch.objects.values_list('target_id', 'status')) == {
            (str(one.pk), 'proposed'), (str(two.pk), 'proposed'),
        }

    def test_rejected_link_is_never_reproposed(self, lagoon):
        company, _ = lagoon
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', message_id='<root@mail.example.org>'))
        run(mb, client)
        conv = MailConversation.objects.get()
        # A person rejects the company link for this conversation.
        MailConversation.objects.filter(pk=conv.pk).update(company=None, link_state='none')
        MailMatch.objects.create(conversation=conv, target_type='company', target_id=str(company.pk),
                                 method='contact_email', confidence='high', status='rejected')
        client.add_message(inbound('g2', message_id='<reply@mail.example.org>',
                                   references='<root@mail.example.org>'))
        run(mb, client)
        reply = MailMessage.objects.filter(rfc_message_id='reply@mail.example.org').first()
        assert reply is None or not reply.matches.filter(target_id=str(company.pk)).exists()
        conv.refresh_from_db()
        assert conv.company is None


class TestDocumentNumbers:
    def test_each_number_type_links(self, capture_on):
        company = make_company('Document Test Company')
        contract = Contract.objects.create(
            company=company, contract_number='TH-CT99001', start_date=date(2099, 1, 1),
            value=Decimal('100.00'), status='Draft',
        )
        legacy = Contract.objects.create(
            company=company, contract_number='BMAT-99-C-0002', start_date=date(2099, 1, 1),
            value=Decimal('100.00'), status='Draft',
        )
        quote = Quote.objects.create(
            company=company, quote_number='HK-QT99003', valid_from=date(2099, 1, 1),
            valid_until=date(2099, 2, 1),
        )
        invoice = Invoice.objects.create(
            company=company, invoice_number='INV-TH-2099-0004', issue_date=date(2099, 1, 1),
            due_date=date(2099, 2, 1), amount=Decimal('1'), total_amount=Decimal('1'),
            receipt_number='REC-TH-2099-0005',
        )
        seq_invoice = Invoice.objects.create(
            company=company, invoice_number='TH-IV99006', issue_date=date(2099, 1, 1),
            due_date=date(2099, 2, 1), amount=Decimal('1'), total_amount=Decimal('1'),
        )
        cases = [
            ('TH-CT99001 signed', ('contract', contract.pk)),
            ('About BMAT-99-C-0002', ('contract', legacy.pk)),
            ('Quote HK-QT99003', ('quote', quote.pk)),
            ('Invoice INV-TH-2099-0004', ('invoice', invoice.pk)),
            ('Receipt REC-TH-2099-0005', ('invoice', invoice.pk)),
            ('Invoice TH-IV99006', ('invoice', seq_invoice.pk)),
        ]
        mb = make_mailbox()
        client = primed(mb)
        for i, (subject, _) in enumerate(cases):
            client.add_message(inbound(f'g{i}', frm=f'unknown{i}@docs.test', subject=subject,
                                       message_id=f'<doc{i}@mail.example.org>'))
        run(mb, client)
        for i, (_, (target_type, target_id)) in enumerate(cases):
            message = MailMessage.objects.get(rfc_message_id=f'doc{i}@mail.example.org')
            link = message.matches.get(target_type=target_type)
            assert (link.target_id, link.method, link.status) == (str(target_id), 'doc_number', 'auto')
            assert message.conversation.company == company


class TestCrmSentMail:
    def _log(self, company, contact, **kwargs):
        defaults = dict(
            company=company, contact=contact, email_type='manual', from_email=SALES,
            to_email='pat@lagoon.test', subject='Synthetic', body_html='', body_text='',
            status='sent',
        )
        defaults.update(kwargs)
        return EmailLog.objects.create(**defaults)

    def test_linked_by_message_id(self, lagoon):
        company, contact = lagoon
        log = self._log(company, contact, message_id='<crm-1@ourco.example>')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(gmail_message('g1', SALES, ['pat@lagoon.test'], date=recent(),
                                         message_id='<crm-1@ourco.example>'))
        run(mb, client)
        message = MailMessage.objects.get()
        assert message.email_log == log and message.direction == 'outbound'

    def test_linked_by_crm_header(self, lagoon):
        company, contact = lagoon
        log = self._log(company, contact)
        quote = Quote.objects.create(company=company, quote_number='TH-QT99010',
                                     valid_from=date(2099, 1, 1), valid_until=date(2099, 2, 1))
        when = recent()
        quote_log = self._log(company, contact, email_type='quote_send', quote=quote, sent_at=when)
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(gmail_message('g1', SALES, ['pat@lagoon.test'], date=when,
                                         extra=[('X-BMAsia-Email-ID', str(log.pk))]))
        client.add_message(gmail_message('g2', SALES, ['Pat@Lagoon.test'], date=when,
                                         message_id='<q@ourco.example>',
                                         extra=[('X-BMAsia-Email-ID', f'quote_{quote.pk}')]))
        run(mb, client)
        assert MailMessage.objects.get(rfc_message_id='g1@mail.example.org').email_log == log
        second = MailMessage.objects.get(rfc_message_id='q@ourco.example')
        assert second.email_log == quote_log
        assert second.matches.get(target_type='quote').status == 'auto'

    def test_header_on_inbound_mail_is_ignored(self, lagoon):
        company, contact = lagoon
        log = self._log(company, contact)
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', extra=[('X-BMAsia-Email-ID', str(log.pk))]))
        run(mb, client)
        assert MailMessage.objects.get().email_log is None


class TestConversationTimes:
    def test_last_inbound_and_outbound_across_mailboxes(self, lagoon):
        a, b = make_mailbox(SALES), make_mailbox(OPS)
        ca, cb = primed(a), primed(b)
        t1, t2, t3 = recent(30), recent(20), recent(10)
        ca.add_message(inbound('a1', when=t1, message_id='<t-root@mail.example.org>'))
        cb.add_message(gmail_message('b1', OPS, ['pat@lagoon.test'], date=t2,
                                     message_id='<t-reply@ourco.example>',
                                     in_reply_to='<t-root@mail.example.org>'))
        ca.add_message(inbound('a2', when=t3, message_id='<t-again@mail.example.org>',
                               in_reply_to='<t-reply@ourco.example>'))
        run(a, ca)
        run(b, cb)
        conv = MailConversation.objects.get()
        assert conv.message_count == 3
        assert (conv.last_inbound_at, conv.last_outbound_at) == (t3, t2)
        assert (conv.first_message_at, conv.last_message_at) == (t1, t3)

    def test_in_reply_to_chain_without_references_joins(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', when=recent(3), message_id='<j1@mail.example.org>'))
        client.add_message(gmail_message('g2', SALES, ['pat@lagoon.test'], date=recent(2),
                                         message_id='<j2@ourco.example>', in_reply_to='<j1@mail.example.org>'))
        client.add_message(inbound('g3', when=recent(1), message_id='<j3@mail.example.org>',
                                   in_reply_to='<j2@ourco.example>'))
        run(mb, client)
        assert MailConversation.objects.count() == 1

    def test_subject_fallback_for_reply_without_headers(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', when=recent(3), subject='Renewal 2099',
                                   message_id='<s1@mail.example.org>'))
        run(mb, client)
        client.add_message(inbound('g2', when=recent(2), subject='RE: Renewal 2099',
                                   message_id='<s2@mail.example.org>'))
        run(mb, client)
        assert MailConversation.objects.count() == 1


class TestBodies:
    def test_body_mode_stores_matched_body_only(self, lagoon):
        mb = make_mailbox(body_mode='body')
        client = primed(mb)
        client.add_message(inbound('g1', body='Please renew.\n\nOn Mon, x wrote:\n> old\n'))
        client.add_message(inbound('g2', frm='stranger@unknown.test', message_id='<u@mail.example.org>'))
        run(mb, client)
        message = MailMessage.objects.get()
        assert message.body_text == 'Please renew.' and message.capture_state == 'body'
        assert len(message.body_sha256) == 64
        full = [c for c in client.calls if c[0] == 'get_message' and c[1]['format'] == 'full']
        assert [c[1]['message_id'] for c in full] == ['g1']
        assert MailboxAccessLog.objects.filter(purpose='body', bodies_read=1).count() == 1

    def test_default_headers_only_reads_no_body(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1'))
        run(mb, client)
        assert MailMessage.objects.get().body_text is None
        assert not [c for c in client.calls if c[1].get('format') == 'full']

    def test_headers_only_rule_blocks_body(self, lagoon):
        CaptureRule.objects.create(kind='domain', value='lagoon.test', action='headers_only')
        mb = make_mailbox(body_mode='body')
        client = primed(mb)
        client.add_message(inbound('g1'))
        run(mb, client)
        message = MailMessage.objects.get()
        assert message.body_text is None and message.headers_only_rule


class TestAccessLogAndRuns:
    def test_every_read_is_logged(self, lagoon):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1'))
        result = run(mb, client, actor='job:test')
        entry = MailboxAccessLog.objects.get()
        assert (entry.purpose, entry.actor, entry.messages_read) == ('poll', 'job:test', 1)
        assert entry.api_calls == len(client.calls)
        run_row = CaptureRun.objects.get(pk=result.run_id)
        assert (run_row.outcome, run_row.fetched, run_row.stored, run_row.matched) == ('ok', 1, 1, 1)
        assert run_row.quota_units_est > 0

    def test_lease_held_by_another_runner_gives_busy(self, lagoon):
        from django.utils import timezone
        mb = make_mailbox()
        client = primed(mb)
        CaptureMailbox.objects.filter(pk=mb.pk).update(
            lease_token='other', lease_expires_at=timezone.now() + timedelta(minutes=5))
        result = run(mb, client)
        assert result.outcome == 'busy' and client.calls == []
        CaptureMailbox.objects.filter(pk=mb.pk).update(
            lease_expires_at=timezone.now() - timedelta(minutes=1))
        assert run(mb, client).outcome == 'ok'

    def test_no_subject_or_address_in_info_logs(self, lagoon, caplog):
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('g1', subject='Very private subject line'))
        client.add_message(inbound('g2', frm='stranger@unknown.test', message_id='<z@mail.example.org>'))
        with caplog.at_level('DEBUG', logger='mail_capture'):
            run(mb, client)
        text = caplog.text
        assert 'Very private' not in text and 'lagoon.test' not in text and 'unknown.test' not in text
        assert SALES not in text


def _table_counts():
    models = (CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog, MailboxCopy,
              MailConversation, MailMatch, MailMessage, MailParticipant, UnmatchedSender)
    return {m.__name__: m.objects.count() for m in models}
