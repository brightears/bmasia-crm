"""Two runners at once. Needs real row locks, so Postgres only."""
import threading

import pytest
from django.db import connection, connections, transaction

from mail_capture.gmail_client import FakeGmailClient
from mail_capture.models import CaptureMailbox, MailboxCopy, MailMessage
from mail_capture.sync import sync_mailbox

from .builders import OPS, SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='row locks need Postgres'),
]

WAIT = 20


class BlockingClient(FakeGmailClient):
    """Pauses inside the first call of ``method`` until released."""

    def __init__(self, *args, method='list_history', **kwargs):
        super().__init__(*args, **kwargs)
        self.block_method = method
        self.entered = threading.Event()
        self.release = threading.Event()

    def _enter(self, method, **kwargs):
        if method == self.block_method and not self.entered.is_set():
            self.entered.set()
            assert self.release.wait(WAIT), 'never released'
        return super()._enter(method, **kwargs)


def _in_thread(fn, results, key):
    def target():
        try:
            results[key] = fn()
        except BaseException as exc:  # surfaced by the test
            results[key] = exc
        finally:
            connections.close_all()
    thread = threading.Thread(target=target)
    thread.start()
    return thread


@pytest.fixture
def contact(capture_on):
    company = make_company('Lagoon Test Hotel')
    return make_contact(company, 'pat@lagoon.test')


def test_second_runner_on_the_same_mailbox_is_busy(contact):
    mb = make_mailbox()
    blocking = BlockingClient(mb.email)
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=blocking.history_id)
    blocking.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent()))
    results = {}
    first = _in_thread(lambda: sync_mailbox(mb.pk, factory_for(blocking), sleep=lambda s: None), results, 'a')
    assert blocking.entered.wait(WAIT)

    other = FakeGmailClient(mb.email)
    second = _in_thread(lambda: sync_mailbox(mb.pk, factory_for(other), sleep=lambda s: None), results, 'b')
    second.join(WAIT)
    assert not second.is_alive()
    assert results['b'].outcome == 'busy' and other.calls == []

    blocking.release.set()
    first.join(WAIT)
    assert results['a'].outcome == 'ok' and results['a'].counts['stored'] == 1
    assert MailMessage.objects.count() == 1
    assert CaptureMailbox.objects.get(pk=mb.pk).lease_token == ''


def test_acquire_skips_a_locked_row_instead_of_waiting(contact):
    mb = make_mailbox()
    client = primed(mb)
    locked, release = threading.Event(), threading.Event()

    def hold_lock():
        with transaction.atomic():
            list(CaptureMailbox.objects.select_for_update(no_key=True).filter(pk=mb.pk))
            locked.set()
            release.wait(WAIT)

    results = {}
    holder = _in_thread(hold_lock, results, 'holder')
    assert locked.wait(WAIT)
    runner = _in_thread(lambda: sync_mailbox(mb.pk, factory_for(client), sleep=lambda s: None),
                        results, 'runner')
    runner.join(WAIT)
    alive = runner.is_alive()
    release.set()
    holder.join(WAIT)
    runner.join(WAIT)
    assert not alive, 'the runner waited for the lock instead of skipping it'
    assert results['runner'].outcome == 'busy'


def test_same_message_from_two_mailboxes_at_once_is_stored_once(contact):
    a, b = make_mailbox(SALES), make_mailbox(OPS)
    barrier = threading.Barrier(2, timeout=WAIT)

    class Racing(FakeGmailClient):
        def get_message(self, *args, **kwargs):
            barrier.wait()
            return super().get_message(*args, **kwargs)

    clients = {}
    for mb, gid in ((a, 'a1'), (b, 'b1')):
        client = Racing(mb.email)
        CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=client.history_id)
        client.add_message(gmail_message(gid, 'pat@lagoon.test', [SALES, OPS], date=recent(),
                                         message_id='<race@mail.example.org>'))
        clients[mb.pk] = client
    results = {}
    threads = [
        _in_thread(lambda pk=pk: sync_mailbox(pk, factory_for(clients[pk]), sleep=lambda s: None),
                   results, str(pk))
        for pk in clients
    ]
    for thread in threads:
        thread.join(WAIT)
    outcomes = [results[str(pk)] for pk in clients]
    assert all(getattr(r, 'outcome', r) == 'ok' for r in outcomes), outcomes
    assert MailMessage.objects.count() == 1
    assert MailboxCopy.objects.count() == 2
