"""The matcher as a pure function over a snapshot. No database."""
import pytest

from mail_capture import match, rules
from mail_capture.match import ContactRef, CrmSentRef, DocRef, DomainRef, Snapshot, match_message
from mail_capture.parse import parse_gmail_message

from .builders import OPS, OUR_DOMAIN, SALES, gmail_message


def snap(**kwargs):
    kwargs.setdefault('internal_domains', (OUR_DOMAIN,))
    return Snapshot(**kwargs)


def msg(from_, to=(SALES,), cc=(), subject='Synthetic subject', **kwargs):
    return parse_gmail_message(gmail_message('m1', from_, to, cc, subject, **kwargs))


class TestDocumentNumbers:
    @pytest.mark.parametrize('text, expected', [
        ('Contract TH-CT99001 attached', [('contract', 'TH-CT99001')]),
        ('re hk-ct 99002', [('contract', 'HK-CT99002')]),
        ('Quote HK-QT99003 and TH QT99004', [('quote', 'HK-QT99003'), ('quote', 'TH-QT99004')]),
        ('Invoice TH-IV99005', [('invoice', 'TH-IV99005')]),
        ('Invoice INV-TH-2099-0006 due', [('invoice', 'INV-TH-2099-0006')]),
        ('Receipt REC-HK-2099-0007', [('receipt', 'REC-HK-2099-0007')]),
        ('Old form BMAT-99-C-0008', [('contract', 'BMAT-99-C-0008')]),
        ('Proforma PF-HK-CT99009', [('contract', 'HK-CT99009')]),
        ('Draft DRAFT-0010 only', []),
        ('XTH-CT99011 and TH-CT990', []),
        ('', []),
    ])
    def test_patterns(self, text, expected):
        assert match.find_document_numbers(text) == expected

    def test_no_repeats_in_order(self):
        assert match.find_document_numbers('TH-QT99002 then TH-CT99001 then TH-QT99002') == [
            ('quote', 'TH-QT99002'), ('contract', 'TH-CT99001'),
        ]


class TestOrder:
    def test_all_internal_is_skipped(self):
        result = match_message(msg(SALES, (OPS,)), snap())
        assert result.decision == match.SKIP_INTERNAL

    def test_internal_subdomain_and_extra_address(self):
        m = msg(f'a@mail.{OUR_DOMAIN}', ('agent@helper.example.com',))
        assert match_message(m, snap(internal_addresses=('agent@helper.example.com',))).decision == match.SKIP_INTERNAL

    def test_no_participants_is_malformed(self):
        m = msg('', (), omit=('From',))
        assert match_message(m, snap()).decision == match.MALFORMED

    def test_never_log_domain_beats_contact(self):
        s = snap(
            contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)},
            rules=(rules.Rule('domain', 'lagoon.test', 'skip'),),
        )
        result = match_message(msg('pat@lagoon.test'), s)
        assert result.decision == match.SKIP_RULE

    def test_mailbox_scoped_rule_only_in_its_mailbox(self):
        s = snap(rules=(rules.Rule('address', 'pat@lagoon.test', 'skip', mailbox_id='mb1'),))
        assert match_message(msg('pat@lagoon.test'), s, mailbox_id='mb1').decision == match.SKIP_RULE
        assert match_message(msg('pat@lagoon.test'), s, mailbox_id='mb2').decision == match.UNMATCHED

    def test_headers_only_rule_is_remembered(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)},
                 rules=(rules.Rule('address', 'pat@lagoon.test', 'headers_only'),))
        result = match_message(msg('pat@lagoon.test'), s)
        assert result.decision == match.MATCHED and result.rule_action == 'headers_only'

    def test_contact_email_case_and_plus(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)})
        result = match_message(msg('Pat <PAT+x@Lagoon.test>'), s)
        assert result.decision == match.MATCHED
        assert (result.company_id, result.method, result.confidence) == ('A', 'contact_email', 'high')
        assert {(l.target_type, l.target_id, l.status) for l in result.links} == {
            ('contact', 'c1', 'auto'), ('company', 'A', 'auto'),
        }

    def test_contact_on_two_companies_is_ambiguous(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'), ContactRef('c2', 'B'))})
        result = match_message(msg('pat@lagoon.test'), s)
        assert result.decision == match.AMBIGUOUS
        assert result.company_id is None
        assert set(result.candidates) == {'A', 'B'}
        assert all(l.status == 'proposed' for l in result.links)

    def test_outbound_primary_company_is_the_recipient(self):
        s = snap(contacts={
            'one@lagoon.test': (ContactRef('c1', 'A'),),
            'two@harbour.test': (ContactRef('c2', 'B'),),
        })
        result = match_message(msg(SALES, ('two@harbour.test',), ('one@lagoon.test',)), s)
        assert result.direction == 'outbound' and result.company_id == 'B'
        assert {l.target_id for l in result.links if l.target_type == 'company'} == {'A', 'B'}

    def test_document_number_decides_when_no_contact(self):
        s = snap(documents={'TH-CT99001': (DocRef('contract', 'k1', 'A', 'TH-CT99001'),)})
        result = match_message(msg('new.person@lagoon.test', subject='Signed TH-CT99001'), s)
        assert result.decision == match.MATCHED and result.method == 'doc_number'
        assert ('contract', 'k1', 'auto') in {(l.target_type, l.target_id, l.status) for l in result.links}

    def test_document_of_another_company_is_only_proposed(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)},
                 documents={'HK-QT99002': (DocRef('quote', 'q1', 'B', 'HK-QT99002'),)})
        result = match_message(msg('pat@lagoon.test', subject='About HK-QT99002'), s)
        assert result.company_id == 'A'
        [link] = [l for l in result.links if l.target_type == 'quote']
        assert link.status == 'proposed'

    def test_documents_of_two_companies_are_ambiguous(self):
        s = snap(documents={
            'TH-CT99001': (DocRef('contract', 'k1', 'A', 'TH-CT99001'),),
            'TH-CT99002': (DocRef('contract', 'k2', 'B', 'TH-CT99002'),),
        })
        result = match_message(msg('x@lagoon.test', subject='TH-CT99001 / TH-CT99002'), s)
        assert result.decision == match.AMBIGUOUS and set(result.candidates) == {'A', 'B'}

    def test_thread_inheritance(self):
        s = snap(confirmed_conversations={'root@x.test': 'A'})
        result = match_message(msg('new@elsewhere.test', references='<root@x.test>'), s)
        assert (result.decision, result.method, result.company_id) == (match.MATCHED, 'thread', 'A')

    def test_unique_domain_matches_medium_and_suggests_contact(self):
        s = snap(domains={'lagoon.test': (DomainRef('A'),)})
        result = match_message(msg('new@lagoon.test'), s)
        assert (result.decision, result.method, result.confidence) == (match.MATCHED, 'company_domain', 'medium')
        assert [(a.address, c) for a, c in result.new_contact_candidates] == [('new@lagoon.test', 'A')]

    def test_shared_domain_never_auto_matches(self):
        s = snap(domains={'harbour.test': (DomainRef('A'), DomainRef('B'))},
                 shared_domain_ranking={'harbour.test': ('B', 'A')})
        result = match_message(msg('new@harbour.test'), s)
        assert result.decision == match.UNMATCHED and result.unmatched_reason == 'shared_domain'
        assert result.candidates == ('B', 'A')
        assert not result.links

    def test_flagged_group_domain_on_one_company_never_auto_matches(self):
        s = snap(domains={'harbour.test': (DomainRef('A', shared_group_domain=True),)})
        assert match_message(msg('new@harbour.test'), s).decision == match.UNMATCHED

    def test_freemail_never_matches_by_domain(self):
        s = snap(domains={'freemail.test': (DomainRef('A'),)}, extra_freemail=frozenset({'freemail.test'}))
        result = match_message(msg('someone@freemail.test'), s)
        assert result.decision == match.UNMATCHED and result.unmatched_reason == 'freemail'
        assert [a.address for a in result.queue_addresses] == ['someone@freemail.test']

    def test_freemail_contact_still_matches_exactly(self):
        s = snap(contacts={'someone@freemail.test': (ContactRef('c1', 'A'),)},
                 extra_freemail=frozenset({'freemail.test'}))
        assert match_message(msg('someone@freemail.test'), s).decision == match.MATCHED

    def test_unknown_outbound_queues_every_recipient(self):
        result = match_message(msg(SALES, ('a@one.test', 'b@two.test')), snap())
        assert [a.address for a in result.queue_addresses] == ['a@one.test', 'b@two.test']

    def test_rejected_link_is_not_proposed_again(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)},
                 rejected={'m1@mail.example.org': frozenset({('company', 'A')})})
        result = match_message(msg('pat@lagoon.test'), s)
        assert result.decision == match.UNMATCHED
        assert not [l for l in result.links if l.target_id == 'A']

    def test_crm_sent_links_outbound_only(self):
        s = snap(crm_sent={'m1@mail.example.org': CrmSentRef('log1', 'A', (('quote', 'q1'),))})
        out = match_message(msg(SALES, ('unknown@lagoon.test',)), s)
        assert (out.decision, out.method, out.email_log_id) == (match.MATCHED, 'crm_sent', 'log1')
        assert ('quote', 'q1', 'auto') in {(l.target_type, l.target_id, l.status) for l in out.links}
        inbound = match_message(msg('unknown@lagoon.test'), s)
        assert inbound.email_log_id is None and inbound.decision == match.UNMATCHED

    def test_pure_and_repeatable(self):
        s = snap(contacts={'pat@lagoon.test': (ContactRef('c1', 'A'),)})
        m = msg('pat@lagoon.test')
        assert match_message(m, s) == match_message(m, s)


class TestCopyRules:
    def test_private_label_and_system_labels(self):
        ids = rules.private_label_ids({'Label_1': 'CRM Private', 'Label_2': 'Work'}, (), None)
        assert ids == {'Label_1'}
        assert rules.copy_decision(['INBOX', 'Label_1'], ids) == rules.COPY_PRIVATE
        assert rules.copy_decision(['SPAM'], ids) == rules.COPY_SKIP_SYSTEM
        assert rules.copy_decision(['CATEGORY_PROMOTIONS'], ids) == rules.COPY_SKIP_SYSTEM
        assert rules.copy_decision(['INBOX'], ids) == rules.COPY_KEEP

    def test_label_rule(self):
        rule = rules.Rule('label', 'Personal', 'private')
        ids = rules.private_label_ids({'Label_5': 'personal'}, (rule,), None)
        assert ids == {'Label_5'}

    def test_domain_rule_covers_subdomains(self):
        [addr] = msg('x@mail.lagoon.test').addresses()[:1]
        assert rules.message_rule_action([addr], (rules.Rule('domain', 'lagoon.test', 'skip'),), None) == 'skip'
