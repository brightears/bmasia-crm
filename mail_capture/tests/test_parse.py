"""Header parsing edge cases. Pure: no database."""
import base64
from datetime import datetime, timezone as dt_timezone

import pytest

from mail_capture import parse
from mail_capture.gmail_client import eml_to_gmail

from .builders import build_eml, gmail_message


def _parsed(headers, body='Synthetic body.\n', **kwargs):
    raw = build_eml(headers, body, **kwargs)
    return parse.parse_gmail_message(eml_to_gmail(raw, 'g1', internal_date_ms='4070908800000'))


def _b64(text, charset='utf-8'):
    return base64.b64encode(text.encode(charset)).decode('ascii')


class TestAddresses:
    def test_case_and_plus_addressing(self):
        [a] = parse.parse_address_list('Pat Example <Pat.Example+Renewals@Lagoon.TEST>')
        assert a.address == 'pat.example+renewals@lagoon.test'
        assert a.domain == 'lagoon.test'
        assert a.match_key == 'pat.example@lagoon.test'
        assert a.display_name == 'Pat Example'
        assert a.valid

    def test_duplicates_are_kept_once(self):
        found = parse.parse_address_list('a@x.test, A@X.test, "Again" <a@x.test>, b@x.test')
        assert [a.address for a in found] == ['a@x.test', 'b@x.test']

    def test_group_syntax_returns_members(self):
        found = parse.parse_address_list('Project Team: one@x.test, two@y.test;, three@z.test')
        assert [a.address for a in found] == ['one@x.test', 'two@y.test', 'three@z.test']

    def test_empty_group_gives_nothing(self):
        assert parse.parse_address_list('undisclosed-recipients:;') == []

    def test_encoded_word_display_name_thai(self):
        name = 'สมชาย ทดสอบ'
        value = f'=?UTF-8?B?{_b64(name)}?= <somchai@lagoon.test>'
        [a] = parse.parse_address_list(value)
        assert a.display_name == name
        assert a.address == 'somchai@lagoon.test'

    def test_tis620_encoded_name(self):
        name = 'ทดสอบ'
        value = f'=?TIS-620?B?{_b64(name, "tis-620")}?= <x@lagoon.test>'
        [a] = parse.parse_address_list(value)
        assert a.display_name == name

    @pytest.mark.parametrize('value', [
        'not an address', 'Broken <no-at-sign>', '<@>', '"unterminated <a@x.test', 'a@', '@x.test',
        '\x00\x01', 'a@@x.test', 'x' * 2000 + '@x.test',
    ])
    def test_malformed_never_raises(self, value):
        found = parse.parse_address_list(value)
        for item in found:
            assert len(item.address) <= parse.MAX_ADDRESS

    def test_malformed_is_flagged_not_dropped(self):
        found = parse.parse_address_list('Broken <no-at-sign>')
        assert found and not found[0].valid


class TestMessageIds:
    def test_brackets_and_whitespace_removed_case_kept(self):
        assert parse.normalise_message_id('  <AbC.123@Mail.Example.org>  ') == 'AbC.123@Mail.Example.org'

    def test_folded_message_id(self):
        assert parse.normalise_message_id('\r\n <x1@mail.example.org>') == 'x1@mail.example.org'

    def test_overlong_id_is_hashed(self):
        value = parse.normalise_message_id('<' + 'a' * 600 + '@x.test>')
        assert value.startswith('long:') and len(value) < 100

    def test_reference_list(self):
        refs = parse.parse_id_list('<r1@x.test>\r\n <r2@x.test> <r1@x.test>')
        assert refs == ['r1@x.test', 'r2@x.test']

    def test_conversation_key_order(self):
        assert parse.conversation_key('m', 'p', ['root', 'p']) == 'root'
        assert parse.conversation_key('m', 'p', []) == 'p'
        assert parse.conversation_key('m', '', []) == 'm'


class TestSubjects:
    def test_prefixes_removed(self):
        assert parse.normalise_subject('RE: Fwd: AW: [EXT] Renewal  2099') == 'renewal 2099'

    def test_thai_reply_prefix(self):
        assert parse.normalise_subject('ตอบกลับ: ใบเสนอราคา') == 'ใบเสนอราคา'

    def test_encoded_thai_subject(self):
        subject = 'ใบเสนอราคา TH-QT99001'
        p = _parsed([
            ('From', 'a@lagoon.test'), ('To', 'sales@ourco.example'),
            ('Subject', f'=?UTF-8?B?{_b64(subject)}?='), ('Message-ID', '<t1@x.test>'),
            ('Date', 'Mon, 05 Jan 2099 09:00:00 +0700'),
        ])
        assert p.subject == subject

    def test_folded_encoded_subject_in_two_words(self):
        first, second = 'ใบเสนอ', 'ราคา'
        p = _parsed([
            ('From', 'a@lagoon.test'), ('To', 'sales@ourco.example'),
            ('Subject', f'=?UTF-8?B?{_b64(first)}?=\r\n =?UTF-8?B?{_b64(second)}?='),
            ('Message-ID', '<t2@x.test>'), ('Date', 'Mon, 05 Jan 2099 09:00:00 +0000'),
        ])
        assert p.subject == first + second

    def test_unknown_charset_degrades(self):
        assert parse.decode_words('=?x-unknown?B?SGVsbG8=?=') == 'Hello'


class TestParsedMessage:
    def test_folded_headers(self):
        p = _parsed([
            ('From', 'Pat\r\n Example <pat@lagoon.test>'),
            ('To', 'sales@ourco.example,\r\n\tops@ourco.example'),
            ('Subject', 'A long\r\n subject'), ('Message-ID', '<f1@x.test>'),
            ('Date', 'Mon, 05 Jan 2099\r\n 09:00:00 +0000'),
        ])
        assert p.from_address.display_name == 'Pat Example'
        assert [a.address for a in p.to] == ['sales@ourco.example', 'ops@ourco.example']
        assert p.subject == 'A long subject'
        assert p.claimed_date == datetime(2099, 1, 5, 9, 0, tzinfo=dt_timezone.utc)

    def test_missing_message_id_gets_stable_synthetic_key(self):
        headers = [
            ('From', 'pat@lagoon.test'), ('To', 'sales@ourco.example'),
            ('Subject', 'No id'), ('Date', 'Mon, 05 Jan 2099 09:00:00 +0000'),
        ]
        one, two = _parsed(headers), _parsed(headers)
        assert one.message_id_synthetic and one.message_id.startswith('synthetic:')
        assert one.message_id == two.message_id
        assert 'no Message-ID' in one.defects

    def test_duplicate_recipients_across_headers(self):
        p = _parsed([
            ('From', 'pat@lagoon.test'), ('To', 'sales@ourco.example, sales@ourco.example'),
            ('Cc', 'SALES@ourco.example'), ('Subject', 's'), ('Message-ID', '<d1@x.test>'),
            ('Date', 'Mon, 05 Jan 2099 09:00:00 +0000'),
        ])
        assert [a.address for a in p.to] == ['sales@ourco.example']
        assert len(p.addresses()) == 2

    def test_bad_date_falls_back_to_internal_date(self):
        p = _parsed([
            ('From', 'pat@lagoon.test'), ('To', 'sales@ourco.example'), ('Subject', 's'),
            ('Message-ID', '<bd@x.test>'), ('Date', 'not a date at all'),
        ])
        assert p.sent_at == datetime(2099, 1, 1, tzinfo=dt_timezone.utc)
        assert 'unparseable Date' in p.defects

    def test_no_from_is_kept_with_a_defect(self):
        p = _parsed([('To', 'sales@ourco.example'), ('Subject', 's'), ('Message-ID', '<nf@x.test>')])
        assert p.from_address is None and 'no From address' in p.defects
        assert [a.address for a in p.to] == ['sales@ourco.example']

    def test_empty_message_never_raises(self):
        p = parse.parse_gmail_message({})
        assert p.message_id.startswith('synthetic:')
        assert p.addresses() == []

    def test_garbage_shapes_never_raise(self):
        for message in ({'payload': {'headers': [{'name': 'From'}]}},
                        {'payload': {'headers': [{'name': None, 'value': None}]}},
                        {'internalDate': 'x', 'payload': None}):
            parse.parse_gmail_message(message)

    def test_bulk_markers(self):
        base = [('From', 'news@lagoon.test'), ('To', 'sales@ourco.example'),
                ('Subject', 's'), ('Message-ID', '<b1@x.test>')]
        assert _parsed(base + [('List-Id', '<news.lagoon.test>')]).is_bulk
        assert _parsed(base + [('Precedence', 'bulk')]).is_bulk
        assert _parsed(base + [('Auto-Submitted', 'auto-replied')]).is_bulk
        assert not _parsed(base + [('Auto-Submitted', 'no')]).is_bulk

    def test_crm_header(self):
        p = _parsed([('From', 'sales@ourco.example'), ('To', 'pat@lagoon.test'),
                     ('Subject', 's'), ('Message-ID', '<c1@x.test>'),
                     ('X-BMAsia-Email-ID', 'quote_00000000-0000-0000-0000-000000000001')])
        assert p.crm_email_id == 'quote_00000000-0000-0000-0000-000000000001'

    def test_own_id_not_in_references(self):
        p = _parsed([('From', 'a@lagoon.test'), ('To', 'sales@ourco.example'), ('Subject', 's'),
                     ('Message-ID', '<self@x.test>'), ('References', '<self@x.test>')])
        assert p.references == [] and p.conversation_key == 'self@x.test'


class TestBodies:
    def test_plain_text_preferred_and_quote_stripped(self):
        raw = (
            'From: pat@lagoon.test\r\nTo: sales@ourco.example\r\nSubject: s\r\n'
            'Message-ID: <body1@x.test>\r\nMIME-Version: 1.0\r\n'
            'Content-Type: multipart/alternative; boundary="b"\r\n\r\n'
            '--b\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n'
            'Please renew TH-CT99001.\r\n\r\nOn Mon, someone wrote:\r\n> old text\r\n'
            '--b\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>HTML</p>\r\n--b--\r\n'
        ).encode()
        message = eml_to_gmail(raw, 'g-body')
        assert parse.extract_body_text(message['payload']) == 'Please renew TH-CT99001.'

    def test_html_only(self):
        raw = build_eml(
            [('From', 'pat@lagoon.test'), ('Subject', 's')],
            body='<html><style>x{}</style><p>Hello&nbsp;there</p><br>Line two</html>',
            content_type='text/html; charset=utf-8',
        )
        message = eml_to_gmail(raw, 'g-html')
        assert parse.extract_body_text(message['payload']) == 'Hello there\nLine two'

    def test_cap(self):
        message = gmail_message('g-long', 'pat@lagoon.test', ['sales@ourco.example'], body='x' * 70000)
        assert len(parse.extract_body_text(message['payload'])) == parse.MAX_BODY_CHARS

    def test_attachments_metadata_skips_inline_images(self):
        raw = (
            'From: pat@lagoon.test\r\nSubject: s\r\nMIME-Version: 1.0\r\n'
            'Content-Type: multipart/mixed; boundary="b"\r\n\r\n'
            '--b\r\nContent-Type: text/plain\r\n\r\nSee attached.\r\n'
            '--b\r\nContent-Type: application/pdf\r\n'
            'Content-Disposition: attachment; filename="signed.pdf"\r\n'
            'Content-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n'
            '--b\r\nContent-Type: image/png\r\nContent-Disposition: inline; filename="logo.png"\r\n'
            'Content-Transfer-Encoding: base64\r\n\r\niVBORw==\r\n--b--\r\n'
        ).encode()
        message = eml_to_gmail(raw, 'g-att')
        meta = parse.attachment_metadata(message['payload'], 'g-att')
        assert [m['filename'] for m in meta] == ['signed.pdf']
        assert meta[0]['mime_type'] == 'application/pdf' and meta[0]['attachment_id']
