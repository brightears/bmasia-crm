"""The Message-ID rule shared with the mail-capture app.

Each row is (input, canonical reference). The expected values were produced by the
mail-capture app's ``identity.canonical_source_ref`` (``parse.normalise_message_id``);
this app's ``canonical_message_id`` must give the same result for every row. When
the mail-capture app is installed, the second test compares the two directly.
"""
import importlib.util

import pytest

from agent_inbox.message_ids import canonical_message_id, gmail_ref_problem

SHARED_CASES = [
    ('<CAB123.456@mail.example.com>', 'CAB123.456@mail.example.com'),
    ('  <CAB123.456@mail.example.com>  ', 'CAB123.456@mail.example.com'),
    ('CAB123.456@Mail.Example.com', 'CAB123.456@Mail.Example.com'),
    ('<a@b> (comment)', 'a@b'),
    ('(comment) <a@b>', 'a@b'),
    ('<first@x.test> <second@x.test>', 'first@x.test'),
    ('<a b@x.test>', 'raw:ca5371a41aba171c9bf7a6b36ed04f9d3781ed77e961e2ddfc320d5fc33dcf51'),
    ('<>', 'raw:24295a9c545a402da4f2cc833dae7b4f3b80182f7f803516d580ca07c0642b64'),
    ('<<a@b>>', 'a@b'),
    ('a@', 'a@'),
    ('@b', '@b'),
    ('plain-token', 'plain-token'),
    ('18c2a4f0b1d2e3f4', '18c2a4f0b1d2e3f4'),
    ('<a@b\r\n >', 'raw:9319e1bb5b5b0438e602735fe89bd1bcef3bfae32bb4d804be9f43ab254be211'),
    ('folded\r\n <a@b>', 'a@b'),
    ('a@bé', 'a@bé'),
    ('<é@x.test>', 'é@x.test'),
    ('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@y', 'long:d305d0c5dd96c37b898f17184407f512ce6af143145dd6bee863c0ca841a6152'),
    ('<yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy@>', 'yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy@'),
    ('synthetic:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', ''),
    ('long:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'long:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
    ('raw:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc', 'raw:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'),
    ('a\x00@b', 'a@b'),
    ('\ud800@b', '�@b'),
    ('', ''),
    ('   ', ''),
    ('two words', 'raw:a03f1d611645eb53ad16c1af546ca0792dc884505bab57ede80f4dad6b911d3a'),
    ('<a@b>>', 'a@b'),
    ('<<a@b>', 'a@b'),
    ('tab\t<a@b>', 'a@b'),
]


@pytest.mark.parametrize('given, expected', SHARED_CASES)
def test_the_shared_table(given, expected):
    assert canonical_message_id(given) == expected


@pytest.mark.parametrize('given, expected', SHARED_CASES)
def test_the_rule_is_idempotent(given, expected):
    assert canonical_message_id(expected) == expected


@pytest.mark.skipif(importlib.util.find_spec('mail_capture') is None, reason='mail_capture is not installed')
@pytest.mark.parametrize('given, expected', SHARED_CASES)
def test_the_capture_app_agrees(given, expected):
    from mail_capture.identity import canonical_source_ref
    assert canonical_source_ref(given) == canonical_message_id(given) == expected


@pytest.mark.parametrize('ref, problem', [
    ('', 'is not a Message-ID'),
    ('18c2a4f0b1d2e3f4', 'Gmail API id'),
    ('CAB123@mail.example.com', None),
    ('raw:' + 'c' * 64, None),
])
def test_recording_refuses_empty_refs_and_gmail_api_ids(ref, problem):
    found = gmail_ref_problem(ref)
    assert (found is None) if problem is None else (problem in found)
