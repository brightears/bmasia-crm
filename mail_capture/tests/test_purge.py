"""Never-log rules, private labels, Gmail deletions and expiry applied to
mail already stored; the confirmation step; nothing left behind."""
import json
from datetime import timedelta

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from mail_capture import purge
from mail_capture.models import (
    CapturePurge, CaptureRule, CaptureRun, MailboxAccessLog, MailboxCopy, MailConversation,
    MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from mail_capture.signals import mail_purged
from mail_capture.sync import sync_mailbox

from .builders import (
    OPS, SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent,
)


pytestmark = pytest.mark.django_db

PRIVATE = {'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}
PERSONAL = {'id': 'Label_5', 'name': 'Personal', 'type': 'user'}


def run(mailbox, client, **kwargs):
    return sync_mailbox(mailbox.pk, factory_for(client), sleep=lambda s: None, **kwargs)


def confirmed_rule(**kwargs):
    rule = CaptureRule.objects.create(**kwargs)
    purge.confirm_rule(rule)
    rule.refresh_from_db()
    return rule


@pytest.fixture
def stored(capture_on):
    """One matched message from a contact, stored from the sales mailbox."""
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox()
    client = primed(mb, labels=[PRIVATE, PERSONAL])
    client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent()))
    run(mb, client)
    assert MailMessage.objects.count() == 1
    return mb, client


def _nothing_left():
    return (MailMessage.objects.count(), MailboxCopy.objects.count(), MailParticipant.objects.count(),
            MailMatch.objects.count(), MailConversation.objects.count()) == (0, 0, 0, 0, 0)


def _all_text():
    """Every value in every mail_capture table, as text (the rules table
    excepted: it is the never-log list and must hold the address)."""
    out = []
    for model in apps.get_app_config('mail_capture').get_models():
        if model is CaptureRule:
            continue
        for row in model.objects.all().values():
            out.append(json.dumps(row, default=str))
    return '\n'.join(out)


class TestConfirmation:
    def test_unconfirmed_rule_blocks_capture_but_purges_nothing(self, stored):
        mb, client = stored
        CaptureRule.objects.create(kind='domain', value='lagoon.test', action='skip')
        run(mb, client)
        assert MailMessage.objects.count() == 1
        client.add_message(gmail_message('g2', 'pat@lagoon.test', [SALES], date=recent(),
                                         message_id='<g2@mail.example.org>'))
        assert run(mb, client).counts['skipped_by_rule'] == 1

    def test_confirmed_rule_purges_at_next_run_and_is_done(self, stored):
        mb, client = stored
        rule = confirmed_rule(kind='domain', value='lagoon.test', action='skip')
        result = run(mb, client)
        assert result.counts['purged'] == 1 and _nothing_left()
        rule.refresh_from_db()
        assert rule.purge_state == 'done' and rule.purge_done_at is not None
        summary = CapturePurge.objects.get()
        assert (summary.reason, summary.rule_id, summary.messages, summary.remaining) == ('rule', rule.pk, 1, False)

    def test_editing_a_rule_needs_a_new_confirmation(self, stored):
        rule = confirmed_rule(kind='domain', value='lagoon.test', action='skip')
        rule.value = 'other.test'
        rule.save()
        rule.refresh_from_db()
        assert rule.purge_state == 'awaiting_confirmation' and rule.confirmed_at is None

    def test_preview_counts_and_reads_only(self, stored):
        UnmatchedSender.objects.create(
            address='other@lagoon.test', domain='lagoon.test', first_seen=timezone.now(),
            last_seen=timezone.now(), expires_at=timezone.now() + timedelta(days=30),
            message_keys=[['k1', SALES]])
        rule = CaptureRule.objects.create(kind='domain', value='lagoon.test', action='skip')
        assert purge.preview_rule(rule) == {'messages': 1, 'copies': 1, 'conversations': 1, 'queue_rows': 1}
        assert MailMessage.objects.count() == 1 and UnmatchedSender.objects.count() == 1

    def test_purge_is_capped_and_continues(self, stored):
        mb, client = stored
        for i in range(4):
            client.add_message(gmail_message(f'c{i}', 'pat@lagoon.test', [SALES], date=recent(),
                                             message_id=f'<cap{i}@mail.example.org>'))
        run(mb, client)
        rule = confirmed_rule(kind='address', value='pat@lagoon.test', action='skip')
        purge.enforce_rules(cap=2)
        rule.refresh_from_db()
        assert MailMessage.objects.count() == 3 and rule.purge_state == 'confirmed'
        assert CapturePurge.objects.get().remaining
        purge.enforce_rules(cap=2)
        purge.enforce_rules(cap=2)
        rule.refresh_from_db()
        assert MailMessage.objects.count() == 0 and rule.purge_state == 'done'

    def test_steady_state_runs_scan_nothing_for_rules(self, stored, django_assert_max_num_queries):
        confirmed_rule(kind='domain', value='lagoon.test', action='skip')
        purge.enforce_rules()                         # done now
        CaptureRule.objects.create(kind='domain', value='other.test', action='skip')   # unconfirmed
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            purge.enforce_rules()
        assert not [q for q in ctx.captured_queries if 'mailparticipant' in q['sql'].lower()]


class TestRefusedValues:
    @pytest.mark.parametrize('kind, value', [
        ('domain', 'test'), ('domain', 'co.th'), ('domain', 'com'), ('domain', 'ourco.example'),
        ('domain', 'mail.ourco.example'), ('domain', 'gmail.com'), ('domain', 'lagoon*.test'),
        ('domain', ''), ('address', 'nobody'), ('address', '@lagoon.test'), ('label', 'INBOX'),
        ('label', 'sent'), ('label', 'CATEGORY_UPDATES'),
    ])
    def test_refused(self, capture_on, kind, value):
        rule = CaptureRule(kind=kind, value=value, action='skip')
        with pytest.raises(ValidationError):
            rule.full_clean()

    def test_a_refused_rule_in_the_table_is_never_applied(self, stored):
        mb, client = stored
        CaptureRule.objects.create(kind='domain', value='test', action='skip', purge_state='confirmed')
        CaptureRule.objects.create(kind='domain', value='ourco.example', action='skip',
                                   purge_state='confirmed')
        purge.enforce_rules()
        client.add_message(gmail_message('g2', 'pat@lagoon.test', [SALES], date=recent(),
                                         message_id='<g2@mail.example.org>'))
        run(mb, client)
        assert MailMessage.objects.count() == 2

    @pytest.mark.parametrize('domain', ['gmail.com', 'foxmail.com', 'co.th', 'test', 'ourco.example'])
    def test_company_domain_refused(self, capture_on, domain):
        from mail_capture.models import CompanyDomain
        with pytest.raises(ValidationError):
            CompanyDomain.objects.create(company=make_company(f'Co {domain}'), domain=domain)


class TestCompleteness:
    def test_purge_leaves_no_trace_in_any_table(self, capture_on, django_capture_on_commit_callbacks):
        """Subject, sender and the outbound subject leave every table, other
        senders' queue rows included; counts-only rows stay."""
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(gmail_message('g1', 'Pat Secretname <pat+news@lagoon.test>', [SALES],
                                         cc=['friend@another-co.test'], subject='Zebra medical results',
                                         date=recent(3), message_id='<m-one@mail.example.org>'))
        client.add_message(gmail_message('g2', SALES, ['pat@lagoon.test', 'other@another-co.test'],
                                         labels=('SENT',), subject='Zebra outbound subject',
                                         date=recent(2), message_id='<m-two@ourco.example>',
                                         in_reply_to='<m-one@mail.example.org>'))
        client.add_message(gmail_message('g3', SALES, ['pat@unknown-co.test', 'other@another-co.test'],
                                         labels=('SENT',), subject='Zebra queue subject',
                                         date=recent(1), message_id='<m-three@ourco.example>'))
        client.add_message(gmail_message('g4', 'Keep Me <keep@lagoon2.test>', [SALES],
                                         subject='Unrelated', date=recent(1), message_id='<m-four@x.test>'))
        run(mb, client)
        assert 'Zebra' in _all_text()
        refs = []
        mail_purged.connect(lambda sender, source_refs, **kw: refs.extend(source_refs), weak=False,
                            dispatch_uid='test-purge-refs')
        try:
            with django_capture_on_commit_callbacks(execute=True):
                CaptureRule.objects.create(kind='address', value='pat@unknown-co.test', action='skip')
                rule = confirmed_rule(kind='address', value='pat@lagoon.test', action='skip')
                purge.enforce_rules()
                # Not confirmed yet: passing it explicitly still does nothing.
                purge.enforce_rules(rules=[CaptureRule.objects.get(value='pat@unknown-co.test')])
                purge.confirm_rule(CaptureRule.objects.get(value='pat@unknown-co.test'))
                purge.enforce_rules()
        finally:
            mail_purged.disconnect(dispatch_uid='test-purge-refs')
        text = _all_text()
        for secret in ('Zebra', 'Secretname', 'pat@lagoon.test', 'pat+news', 'pat@unknown-co.test',
                       'm-one@mail.example.org'):
            assert secret not in text, secret
        assert MailMessage.objects.count() == 0
        assert UnmatchedSender.objects.filter(address='keep@lagoon2.test').count() == 1   # unrelated
        rule.refresh_from_db()
        assert rule.purge_state == 'done'
        assert sorted(refs) == ['m-one@mail.example.org', 'm-two@ourco.example']
        assert CaptureRun.objects.exists() and MailboxAccessLog.objects.exists()

    def test_subdomains_are_purged(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@mail.lagoon.test')
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(gmail_message('g1', 'pat@mail.lagoon.test', [SALES], date=recent()))
        run(mb, client)
        confirmed_rule(kind='domain', value='lagoon.test', action='skip')
        purge.enforce_rules()
        assert _nothing_left()

    def test_mailbox_scoped_rule_drops_only_that_copy_and_its_queue_samples(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        a, b = make_mailbox(SALES), make_mailbox(OPS)
        ca, cb = primed(a), primed(b)
        for c, gid in ((ca, 'a1'), (cb, 'b1')):
            c.add_message(gmail_message(gid, 'pat@lagoon.test', [SALES, OPS], date=recent(),
                                        message_id='<both@mail.example.org>'))
            c.add_message(gmail_message(gid + 'q', 'x@unknown.test', [SALES, OPS], date=recent(),
                                        subject='Queued', message_id='<q@mail.example.org>'))
        run(a, ca)
        run(b, cb)
        assert sorted(UnmatchedSender.objects.get().mailboxes) == [OPS, SALES]
        confirmed_rule(kind='address', value='pat@lagoon.test', action='skip', scope='mailbox', mailbox=b)
        confirmed_rule(kind='address', value='x@unknown.test', action='skip', scope='mailbox', mailbox=b)
        purge.enforce_rules()
        message = MailMessage.objects.get()
        assert list(message.copies.values_list('mailbox_id', flat=True)) == [a.pk]
        row = UnmatchedSender.objects.get()
        assert row.mailboxes == [SALES] and all(s['m'] == SALES for s in row.samples)

    def test_headers_only_rule_clears_stored_bodies(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        mb = make_mailbox(body_mode='body')
        client = primed(mb)
        client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent(), body='Text.\n'))
        run(mb, client)
        assert MailMessage.objects.get().body_text == 'Text.'
        confirmed_rule(kind='domain', value='lagoon.test', action='headers_only')
        assert purge.enforce_rules()['bodies_cleared'] == 1
        message = MailMessage.objects.get()
        assert (message.body_text, message.body_sha256, message.capture_state) == (None, '', 'headers')

    def test_purge_recomputes_the_conversation_and_its_subject(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        make_contact(company, 'sam@other-domain.test')
        mb = make_mailbox()
        client = primed(mb)
        first, second = recent(3), recent(1)
        client.add_message(gmail_message('g1', 'sam@other-domain.test', [SALES], date=first,
                                         subject='Private first subject', message_id='<p1@mail.example.org>'))
        client.add_message(gmail_message('g2', 'pat@lagoon.test', [SALES], date=second,
                                         subject='Re: kept', message_id='<p2@mail.example.org>',
                                         in_reply_to='<p1@mail.example.org>',
                                         references='<p1@mail.example.org>'))
        run(mb, client)
        conv = MailConversation.objects.get()
        assert conv.message_count == 2 and conv.subject_normalised == 'private first subject'
        confirmed_rule(kind='domain', value='other-domain.test', action='skip')
        purge.enforce_rules()
        conv.refresh_from_db()
        assert conv.message_count == 1 and conv.last_inbound_at == second
        assert conv.subject_normalised == 'kept'
        assert conv.conversation_key.startswith('purged:')
        kept = MailMessage.objects.get()
        assert kept.in_reply_to.startswith('purged:') and kept.references[0].startswith('purged:')
        # A later reply naming the purged root still finds the conversation.
        client.add_message(gmail_message('g3', 'pat@lagoon.test', [SALES], date=recent(0),
                                         subject='Re: kept', message_id='<p3@mail.example.org>',
                                         references='<p1@mail.example.org>'))
        run(mb, client)
        assert MailConversation.objects.count() == 1


class TestLabelsAndDeletion:
    def test_private_label_on_new_mail_skips_it(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        mb = make_mailbox()
        client = primed(mb, labels=[PRIVATE])
        client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent(),
                                         labels=('INBOX', 'Label_9')))
        assert run(mb, client).counts['skipped_by_rule'] == 1
        assert MailMessage.objects.count() == 0

    def test_private_label_added_later_purges_the_only_copy(self, stored):
        mb, client = stored
        client.add_labels('g1', ['Label_9'])
        result = run(mb, client)
        assert result.counts['purged'] == 1 and _nothing_left()
        assert CapturePurge.objects.get().reason == 'label'

    def test_private_label_on_unmatched_mail_removes_its_queue_subject(self, capture_on):
        mb = make_mailbox()
        client = primed(mb, labels=[PRIVATE])
        client.add_message(gmail_message('q1', 'Stranger <who@unknown-co.test>', [SALES],
                                         subject='Medical results', date=recent(2)))
        run(mb, client)
        assert UnmatchedSender.objects.count() == 1
        client.add_labels('q1', ['Label_9'])
        run(mb, client)
        assert 'Medical results' not in _all_text()

    def test_private_label_on_one_copy_keeps_the_other(self, capture_on):
        company = make_company('Lagoon Test Hotel')
        make_contact(company, 'pat@lagoon.test')
        a, b = make_mailbox(SALES), make_mailbox(OPS)
        ca, cb = primed(a, labels=[PRIVATE]), primed(b, labels=[PRIVATE])
        for c, gid in ((ca, 'a1'), (cb, 'b1')):
            c.add_message(gmail_message(gid, 'pat@lagoon.test', [SALES, OPS], date=recent(),
                                        message_id='<both@mail.example.org>'))
        run(a, ca)
        run(b, cb)
        cb.add_labels('b1', ['Label_9'])
        run(b, cb)
        message = MailMessage.objects.get()
        assert list(message.copies.values_list('mailbox_id', flat=True)) == [a.pk]

    def test_label_rule_added_later_applies_to_stored_copies(self, stored):
        mb, client = stored
        client.add_labels('g1', ['Label_5'])
        run(mb, client)                       # 'Personal' is not a rule yet: kept
        assert MailMessage.objects.count() == 1
        rule = CaptureRule.objects.create(kind='label', value='Personal', action='private')
        run(mb, client)                       # saved, not confirmed: stored mail stays
        assert MailMessage.objects.count() == 1
        preview = purge.preview_rule(rule)
        assert (preview['messages'], preview['copies']) == (1, 1)
        client.add_message(gmail_message('g2', 'pat@lagoon.test', [SALES], date=recent(),
                                         labels=('INBOX', 'Label_5'), message_id='<new@mail.example.org>'))
        assert run(mb, client).counts['skipped_by_rule'] == 1   # but new capture is blocked at once
        purge.confirm_rule(rule)
        run(mb, client)
        assert _nothing_left()

    def test_a_label_added_later_under_an_unconfirmed_rule_purges_nothing(self, stored):
        mb, client = stored
        CaptureRule.objects.create(kind='label', value='Personal', action='private')
        run(mb, client)
        client.add_labels('g1', ['Label_5'])
        run(mb, client)
        assert MailMessage.objects.count() == 1
        assert MailboxCopy.objects.get().label_ids == ['INBOX', 'Label_5']

    @pytest.mark.parametrize('kind, value', [('domain', 'lagoon.test'), ('address', 'pat@lagoon.test'),
                                             ('label', 'Personal')])
    def test_a_rule_changed_after_confirmation_counts_as_unconfirmed(self, stored, kind, value):
        """QuerySet.update() skips save(): the fingerprint still catches it."""
        mb, client = stored
        client.add_labels('g1', ['Label_5'])
        run(mb, client)
        rule = CaptureRule.objects.create(kind=kind, value='nothing-here.test' if kind == 'domain' else
                                          ('nobody@nothing-here.test' if kind == 'address' else 'Other'),
                                          action='skip')
        purge.confirm_rule(rule)
        run(mb, client)
        CaptureRule.objects.filter(pk=rule.pk).update(value=value)
        run(mb, client)
        assert MailMessage.objects.count() == 1
        rule.refresh_from_db()
        assert not rule.is_confirmed
        if kind != 'label':
            assert rule.purge_state == 'awaiting_confirmation'

    def test_gmail_deletion_of_the_last_copy_removes_the_message(self, stored):
        mb, client = stored
        client.delete_message('g1')
        run(mb, client)
        assert _nothing_left()
        assert CapturePurge.objects.get().reason == 'gmail_deleted'

    def test_trash_label_drops_the_copy(self, stored):
        mb, client = stored
        client.add_labels('g1', ['TRASH'])
        run(mb, client)
        assert _nothing_left()

    def test_private_label_during_a_history_gap_is_enforced_by_the_resync(self, stored):
        mb, client = stored
        client.add_labels('g1', ['Label_9'])
        client.expire_history()
        assert run(mb, client).outcome == 'resync_needed'
        second = run(mb, client)
        assert second.kind == 'resync' and second.outcome == 'ok'
        assert _nothing_left()

    def test_deletion_during_a_history_gap_is_found_by_the_resync(self, stored):
        mb, client = stored
        client.delete_message('g1')
        client.expire_history()
        run(mb, client)
        run(mb, client)
        assert _nothing_left()


class TestExpiryAndRetention:
    def test_expired_unmatched_rows_are_removed(self, capture_on):
        now = timezone.now()
        for address, expires, status in (('old@x.test', now - timedelta(days=1), 'open'),
                                          ('fresh@x.test', now + timedelta(days=1), 'open'),
                                          ('kept@x.test', now - timedelta(days=1), 'ignored')):
            UnmatchedSender.objects.create(address=address, first_seen=now, last_seen=now,
                                           expires_at=expires, status=status)
        assert purge.purge_expired_unmatched(now) == 1
        assert sorted(UnmatchedSender.objects.values_list('address', flat=True)) == ['fresh@x.test', 'kept@x.test']

    def test_old_runs_and_access_log_rows_go(self, stored, settings):
        settings.CAPTURE_RUN_RETENTION_DAYS = 10
        settings.CAPTURE_ACCESS_LOG_RETENTION_DAYS = 20
        old = timezone.now() - timedelta(days=15)
        older = timezone.now() - timedelta(days=25)
        CaptureRun.objects.update(started_at=old)
        MailboxAccessLog.objects.update(at=older)
        counts = purge.purge_old_records()
        assert counts['runs'] == 1 and counts['access_log'] == 1
        assert not CaptureRun.objects.exists() and not MailboxAccessLog.objects.exists()


class TestAdmin:
    def test_saving_a_rule_shows_a_preview_and_needs_confirmation(self, stored, admin_client):
        UnmatchedSender.objects.create(
            address='other@lagoon.test', domain='lagoon.test', first_seen=timezone.now(),
            last_seen=timezone.now(), expires_at=timezone.now() + timedelta(days=30),
            message_keys=[['k1', SALES]], samples=[{'k': 'k1', 'm': SALES, 's': 'Queued subject'}])
        response = admin_client.post('/admin/mail_capture/capturerule/add/', {
            'kind': 'domain', 'value': 'lagoon.test', 'scope': 'org', 'action': 'skip', 'note': '',
        })
        assert response.status_code == 302 and 'confirm-purge' in response['Location']
        assert MailMessage.objects.count() == 1          # nothing purged on save
        page = admin_client.get(response['Location']).content.decode()
        assert 'Messages purged: <strong>1</strong>' in page
        assert 'Unmatched-sender rows removed: <strong>1</strong>' in page
        response = admin_client.post(response['Location'], {'confirm': 'yes'})
        assert response.status_code == 302
        assert _nothing_left() and UnmatchedSender.objects.count() == 0
        assert CaptureRule.objects.get().purge_state == 'done'

    def test_admin_refuses_a_broad_rule(self, stored, admin_client):
        response = admin_client.post('/admin/mail_capture/capturerule/add/', {
            'kind': 'domain', 'value': 'test', 'scope': 'org', 'action': 'skip', 'note': '',
        })
        assert response.status_code == 200 and CaptureRule.objects.count() == 0
        assert MailMessage.objects.count() == 1
