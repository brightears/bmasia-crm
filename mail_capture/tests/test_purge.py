"""Never-log rules, private labels and expiry applied to mail already stored."""
from datetime import timedelta

import pytest
from django.utils import timezone

from mail_capture import purge
from mail_capture.models import (
    CaptureRule, MailboxCopy, MailConversation, MailMatch, MailMessage, MailParticipant,
    UnmatchedSender,
)
from mail_capture.sync import sync_mailbox

from .builders import OPS, SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent


pytestmark = pytest.mark.django_db

PRIVATE = {'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}
PERSONAL = {'id': 'Label_5', 'name': 'Personal', 'type': 'user'}


def run(mailbox, client, **kwargs):
    return sync_mailbox(mailbox.pk, factory_for(client), sleep=lambda s: None, **kwargs)


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


def test_new_never_log_domain_purges_stored_mail_at_next_run(stored):
    mb, client = stored
    CaptureRule.objects.create(kind='domain', value='lagoon.test', action='skip')
    result = run(mb, client)
    assert result.counts['purged'] == 1
    assert _nothing_left()


def test_enforce_rules_directly_and_queue_rows_go_too(stored):
    UnmatchedSender.objects.create(
        address='other@lagoon.test', domain='lagoon.test', first_seen=timezone.now(),
        last_seen=timezone.now(), expires_at=timezone.now() + timedelta(days=30),
    )
    rule = CaptureRule.objects.create(kind='address', value='PAT@lagoon.test', action='skip')
    assert rule.value == 'pat@lagoon.test'
    counts = purge.enforce_rules()
    assert counts['purged'] == 1 and _nothing_left()
    CaptureRule.objects.create(kind='domain', value='lagoon.test', action='skip')
    assert purge.enforce_rules()['queue_removed'] == 1


def test_never_log_rule_stops_capture(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    CaptureRule.objects.create(kind='domain', value='lagoon.test', action='skip')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(gmail_message('g1', 'pat@mail.lagoon.test', [SALES], date=recent()))
    assert run(mb, client).counts['skipped_by_rule'] == 1
    assert MailMessage.objects.count() == 0 and UnmatchedSender.objects.count() == 0


def test_mailbox_scoped_rule_drops_only_that_copy(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    a, b = make_mailbox(SALES), make_mailbox(OPS)
    ca, cb = primed(a), primed(b)
    for c, gid in ((ca, 'a1'), (cb, 'b1')):
        c.add_message(gmail_message(gid, 'pat@lagoon.test', [SALES, OPS], date=recent(),
                                    message_id='<both@mail.example.org>'))
    run(a, ca)
    run(b, cb)
    CaptureRule.objects.create(kind='address', value='pat@lagoon.test', action='skip',
                               scope='mailbox', mailbox=b)
    purge.enforce_rules()
    message = MailMessage.objects.get()
    assert list(message.copies.values_list('mailbox_id', flat=True)) == [a.pk]


def test_private_label_on_new_mail_skips_it(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox()
    client = primed(mb, labels=[PRIVATE])
    client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent(),
                                     labels=('INBOX', 'Label_9')))
    assert run(mb, client).counts['skipped_by_rule'] == 1
    assert MailMessage.objects.count() == 0


def test_private_label_added_later_purges_the_only_copy(stored):
    mb, client = stored
    client.add_labels('g1', ['Label_9'])
    result = run(mb, client)
    assert result.counts['purged'] == 1 and _nothing_left()


def test_private_label_on_one_copy_keeps_the_other(capture_on):
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


def test_label_rule_added_later_applies_to_stored_copies(stored):
    mb, client = stored
    client.add_labels('g1', ['Label_5'])
    run(mb, client)                       # 'Personal' is not a rule yet: kept
    assert MailMessage.objects.count() == 1
    CaptureRule.objects.create(kind='label', value='Personal', action='private')
    run(mb, client)
    assert _nothing_left()


def test_headers_only_rule_clears_stored_bodies(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox(body_mode='body')
    client = primed(mb)
    client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent(), body='Text.\n'))
    run(mb, client)
    assert MailMessage.objects.get().body_text == 'Text.'
    CaptureRule.objects.create(kind='domain', value='lagoon.test', action='headers_only')
    assert purge.enforce_rules()['bodies_cleared'] == 1
    message = MailMessage.objects.get()
    assert (message.body_text, message.body_sha256, message.capture_state) == (None, '', 'headers')


def test_purge_recomputes_the_conversation(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    make_contact(company, 'sam@other-domain.test')
    mb = make_mailbox()
    client = primed(mb)
    first = recent(3)
    client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=first,
                                     message_id='<p1@mail.example.org>'))
    client.add_message(gmail_message('g2', 'sam@other-domain.test', [SALES], date=recent(1),
                                     message_id='<p2@mail.example.org>', in_reply_to='<p1@mail.example.org>'))
    run(mb, client)
    conv = MailConversation.objects.get()
    assert conv.message_count == 2
    CaptureRule.objects.create(kind='domain', value='other-domain.test', action='skip')
    purge.enforce_rules()
    conv.refresh_from_db()
    assert conv.message_count == 1 and conv.last_inbound_at == first


def test_expired_unmatched_rows_are_removed(capture_on):
    now = timezone.now()
    for address, expires, status in (('old@x.test', now - timedelta(days=1), 'open'),
                                      ('fresh@x.test', now + timedelta(days=1), 'open'),
                                      ('kept@x.test', now - timedelta(days=1), 'ignored')):
        UnmatchedSender.objects.create(address=address, first_seen=now, last_seen=now,
                                       expires_at=expires, status=status)
    assert purge.purge_expired_unmatched(now) == 1
    assert sorted(UnmatchedSender.objects.values_list('address', flat=True)) == ['fresh@x.test', 'kept@x.test']


def test_admin_save_applies_rules(stored, admin_client):
    response = admin_client.post('/admin/mail_capture/capturerule/add/', {
        'kind': 'domain', 'value': 'lagoon.test', 'scope': 'org', 'action': 'skip', 'note': '',
    })
    assert response.status_code == 302
    assert _nothing_left()
