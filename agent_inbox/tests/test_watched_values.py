"""A suggestion counts as "changed since it was made" only when a value it shows changed.

Edits to other fields of the record (or to the record's other suggestions being
accepted) leave the reviewer's view valid; a watched field, a deleted or
inactive record, or a new duplicate contact does not.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal, watched_fields
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client, seen_of
from crm_app.models import Company, Contact

FIVE_FIELDS = {
    'phone': '+66 2 111 2222', 'email': 'desk@riverside.example.com', 'website': 'https://riverside.example.org',
    'city': 'Chiang Mai', 'address_line1': '2 Example Road',
}


def _field(company, field, value, quote='as written in the message'):
    return {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {field: value}, 'evidence_quote': quote}


def _five(agent, company):
    return [create_proposal(agent, _field(company, field, value), via='rest')[0]
            for field, value in FIVE_FIELDS.items()]


def _flagged(proposals):
    """Read the list as the reviewer does, then count the proposals marked changed."""
    ids = [p.pk for p in proposals]
    return ChangeProposal.objects.filter(pk__in=ids, target_changed_at__isnull=False).count()


def _read_all(client):
    response = client.get(PROPOSALS, {'page_size': 200})
    assert response.status_code == 200, response.content
    return response


def _bump(record, **fields):
    for name, value in fields.items():
        setattr(record, name, value)
    record.save()


# ------------------------------------------------------------------ the measured scenarios


def test_accepting_one_of_five_from_the_same_message_flags_none_of_the_others(agent, person, company):
    proposals = _five(agent, company)
    client = jwt_client(person)
    _read_all(client)
    seen_before = {p.pk: seen_of(p.pk) for p in proposals[1:]}
    assert decide(client, proposals[0].pk, 'accept').status_code == 200
    _read_all(client)
    assert _flagged(proposals[1:]) == 0
    assert {p.pk: seen_of(p.pk) for p in proposals[1:]} == seen_before
    # Each of the others can still be accepted with the view loaded before.
    for proposal in proposals[1:]:
        response = decide(client, proposal.pk, 'accept', seen_version=seen_before[proposal.pk])
        assert response.status_code == 200, response.content


def test_an_unrelated_notes_edit_on_twenty_companies_flags_none_of_their_hundred(agent, person):
    companies = [Company.objects.create(name=f'Example Seeded Hotel {n:02d}', billing_entity='BMAsia Limited',
                                        phone='+66 2 000 0000', email='front@seeded.example.com',
                                        website='https://seeded.example.com', city='Bangkok',
                                        address_line1='1 Example Road', notes='Old note')
                 for n in range(20)]
    proposals = [p for company in companies for p in _five(agent, company)]
    assert len(proposals) == 100
    client = jwt_client(person)
    _read_all(client)
    for company in companies:
        _bump(company, notes='Someone added a line about parking')
    _read_all(client)
    assert _flagged(proposals) == 0


def test_a_watched_field_edit_flags_exactly_the_proposals_watching_it(agent, person, company, other_company):
    mine = _five(agent, company)
    other = create_proposal(agent, _field(other_company, 'phone', '+66 2 333 3333'), via='rest')[0]
    client = jwt_client(person)
    _read_all(client)
    _bump(company, phone='+66 2 999 9999', notes='and an unrelated edit')
    _read_all(client)
    flagged = set(ChangeProposal.objects.filter(target_changed_at__isnull=False).values_list('pk', flat=True))
    assert flagged == {mine[0].pk}
    row = ChangeProposal.objects.get(pk=mine[0].pk)
    assert row.current_values == {'phone': '+66 2 999 9999'}
    assert other.pk not in flagged


# ------------------------------------------------------------------ comparison


@pytest.mark.parametrize('stored, now, changed', [
    ('front@riverside.example.com', '  Front@Riverside.EXAMPLE.com ', False),   # case and spacing in an email
    ('front@riverside.example.com', 'frontdesk@riverside.example.com', True),
])
def test_email_is_compared_without_case_or_spacing(agent, person, company, stored, now, changed):
    proposal = create_proposal(agent, _field(company, 'email', 'desk@riverside.example.com'), via='rest')[0]
    assert proposal.current_values == {'email': stored}
    Company.objects.filter(pk=company.pk).update(email=now, updated_at=timezone.now() + timedelta(seconds=1))
    _read_all(jwt_client(person))
    assert _flagged([proposal]) == int(changed)


def test_spacing_and_empty_versus_missing_are_not_changes(agent, person, company, contact):
    name = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                   'target_id': str(contact.pk), 'patch': {'name': 'Pat Q. Example'},
                                   'evidence_quote': 'Pat Q. Example'}, via='rest')[0]
    state = create_proposal(agent, _field(company, 'state', 'Bangkok'), via='rest')[0]
    later = timezone.now() + timedelta(seconds=1)
    Contact.objects.filter(pk=contact.pk).update(name='  Pat   Example ', updated_at=later)
    # The record shows an empty state; a snapshot holding null for it is the same value.
    assert Company.objects.get(pk=company.pk).state == ''
    ChangeProposal.objects.filter(pk=state.pk).update(current_values={'state': None})
    Company.objects.filter(pk=company.pk).update(updated_at=later)
    _read_all(jwt_client(person))
    assert _flagged([name, state]) == 0
    Contact.objects.filter(pk=contact.pk).update(name='Pat Other', updated_at=later + timedelta(seconds=1))
    _read_all(jwt_client(person))
    assert _flagged([name, state]) == 1


def test_watched_fields_are_the_patch_and_snapshot_fields(agent, company):
    proposal = create_proposal(agent, _field(company, 'city', 'Chiang Mai'), via='rest')[0]
    assert watched_fields(proposal) == ['city']
    note = create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                                   'patch': {'notes': 'Likes jazz'}, 'evidence_quote': 'likes jazz'}, via='rest')[0]
    assert watched_fields(note) == []  # a note only appends: it watches the record's state, not its notes


def test_a_notes_edit_does_not_flag_a_note_suggestion(agent, person, company):
    """A note is appended to the notes as they are when it is accepted, so an edit to them is no change."""
    note = create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                                   'patch': {'notes': 'Likes jazz'}, 'evidence_quote': 'likes jazz'}, via='rest')[0]
    phone = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    _bump(company, notes='Rewritten by a person')
    _read_all(jwt_client(person))
    assert ChangeProposal.objects.get(pk=note.pk).target_changed_at is None
    assert ChangeProposal.objects.get(pk=phone.pk).target_changed_at is None


# ------------------------------------------------------------------ the version the reviewer binds to


def test_seen_version_is_stable_across_unrelated_edits_and_moves_on_watched_ones(agent, person, company):
    proposal = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    client = jwt_client(person)
    first = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    _bump(company, city='Hua Hin')
    assert client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version'] == first
    _bump(company, phone='+66 2 999 9999')
    moved = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert moved['seen_version'] != first and moved['target_changed_at']
    # Reading again after the change does not move it again.
    assert client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version'] == moved['seen_version']


def test_reject_then_reopen_still_gets_a_fresh_version(agent, person, other_person, company):
    proposal = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    loaded = seen_of(proposal.pk)
    assert decide(jwt_client(person), proposal.pk, 'reject', reason='no').status_code == 200
    assert decide(jwt_client(other_person), proposal.pk, 'reopen', note='again').status_code == 200
    assert seen_of(proposal.pk) != loaded


def _proposal_writes(queries):
    return [q['sql'] for q in queries.captured_queries
            if q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE'))
            and 'agent_inbox_changeproposal' in q['sql']]


def test_an_unrelated_edit_changes_nothing_a_reviewer_sees(agent, person, company):
    """The first read after an unrelated edit advances the stored version, once, with one small UPDATE.

    That UPDATE sets expected_version only: no seen_version, target_changed_at,
    updated_at or snapshot moves. Every later read writes nothing.
    """
    proposals = _five(agent, company)
    client = jwt_client(person)
    _read_all(client)
    _bump(company, notes='Unrelated')
    stamps = dict(ChangeProposal.objects.values_list('pk', 'updated_at'))
    seen = {p.pk: seen_of(p.pk) for p in proposals}
    with CaptureQueriesContext(connection) as first:
        _read_all(client)
    writes = _proposal_writes(first)
    assert len(writes) == 1 and '"expected_version"' in writes[0]
    assert 'target_changed_at' not in writes[0] and '"updated_at"' not in writes[0]
    with CaptureQueriesContext(connection) as later:
        _read_all(client)
        client.get(f'{PROPOSALS}{proposals[2].pk}/')
    assert _proposal_writes(later) == []
    assert dict(ChangeProposal.objects.values_list('pk', 'updated_at')) == stamps
    assert {p.pk: seen_of(p.pk) for p in proposals} == seen
    assert _flagged(proposals) == 0


def test_a_read_issues_no_extra_query_when_nothing_moved(agent, person, company, other_company):
    client = jwt_client(person)
    create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')
    _read_all(client)
    with CaptureQueriesContext(connection) as few:
        _read_all(client)
    for field, value in list(FIVE_FIELDS.items())[1:]:
        create_proposal(agent, _field(company, field, value), via='rest')
    create_proposal(agent, _field(other_company, 'phone', '+66 2 333 3333'), via='rest')
    with CaptureQueriesContext(connection) as many:
        _read_all(client)
    assert len(many.captured_queries) == len(few.captured_queries)


# ------------------------------------------------------------------ accept races


def test_an_unrelated_edit_after_the_read_does_not_block_the_accept(agent, person, company):
    proposal = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    seen = seen_of(proposal.pk)
    _bump(company, city='Hua Hin', notes='Edited while the reviewer was reading')
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert response.status_code == 200, response.content
    company.refresh_from_db()
    assert (company.phone, company.city, company.notes) == ('+66 2 111 2222', 'Hua Hin',
                                                            'Edited while the reviewer was reading')


def test_a_watched_edit_after_the_read_blocks_the_accept(agent, person, company):
    proposal = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    seen = seen_of(proposal.pk)
    _bump(company, phone='+66 2 999 9999')
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'record_changed')
    company.refresh_from_db()
    assert company.phone == '+66 2 999 9999'
    row = ChangeProposal.objects.get(pk=proposal.pk)
    assert row.current_values == {'phone': '+66 2 999 9999'} and row.target_changed_at is not None


def test_a_note_accept_appends_to_the_notes_as_they_are_now(agent, person, company):
    """A spacing-only edit to the notes is not a change; the note is appended to the stored text."""
    note = create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                                   'patch': {'notes': 'Likes jazz'}, 'evidence_quote': 'likes jazz'}, via='rest')[0]
    seen = seen_of(note.pk)
    Company.objects.filter(pk=company.pk).update(notes='Existing  company note ',
                                                 updated_at=timezone.now() + timedelta(seconds=1))
    response = decide(jwt_client(person), note.pk, 'accept', seen_version=seen)
    assert response.status_code == 200, response.content
    company.refresh_from_db()
    assert company.notes.startswith('Existing  company note') and company.notes.endswith('Likes jazz')


# ------------------------------------------------------------------ deleted, inactive, duplicate


def test_a_deleted_or_inactive_record_counts_as_changed(agent, person, company, contact):
    client = jwt_client(person)
    on_contact = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                         'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                         'evidence_quote': 'Director'}, via='rest')[0]
    on_company = create_proposal(agent, _field(company, 'phone', '+66 2 111 2222'), via='rest')[0]
    _read_all(client)
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    _read_all(client)
    row = ChangeProposal.objects.get(pk=on_contact.pk)
    assert (row.target_state, row.target_changed_at is not None) == ('inactive', True)
    assert ChangeProposal.objects.get(pk=on_company.pk).target_changed_at is None
    seen = seen_of(on_contact.pk)
    _read_all(client)
    assert seen_of(on_contact.pk) == seen  # stable while it stays inactive
    Contact.objects.filter(pk=contact.pk).update(is_active=True)
    _read_all(client)
    assert ChangeProposal.objects.get(pk=on_contact.pk).target_state == 'present'
    assert seen_of(on_contact.pk) != seen  # coming back is a change too
    ChangeProposal.objects.filter(pk=on_contact.pk).update(status='rejected')  # not in the way of the delete
    contact_pk = contact.pk
    other = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                    'target_id': str(contact_pk), 'patch': {'department': 'Front office'},
                                    'evidence_quote': 'Front office'}, via='rest')[0]
    Contact.objects.filter(pk=contact_pk).delete()
    _read_all(client)
    row = ChangeProposal.objects.get(pk=other.pk)
    assert (row.target_state, row.target_changed_at is not None) == ('missing', True)
    seen = seen_of(other.pk)
    _read_all(client)
    assert seen_of(other.pk) == seen


def test_an_accept_on_a_record_made_inactive_after_the_read_is_refused(agent, person, contact):
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                       'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                       'evidence_quote': 'Director'}, via='rest')[0]
    seen = seen_of(proposal.pk)
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'record_changed')
    assert ChangeProposal.objects.get(pk=proposal.pk).target_state == 'inactive'


def _new_contact(agent, company, email='new.person@riverside.example.com', name='New Person'):
    return create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                   'patch': {'name': name, 'email': email},
                                   'evidence_quote': f'please add {email}'}, via='rest')[0]


def test_a_new_contact_suggestion_changes_only_when_its_duplicate_check_does(agent, person, company):
    proposal = _new_contact(agent, company)
    assert proposal.target_state == 'no_duplicate'
    client = jwt_client(person)
    _read_all(client)
    seen = seen_of(proposal.pk)
    _bump(company, notes='Touched', phone='+66 2 777 7777')
    _read_all(client)
    assert seen_of(proposal.pk) == seen and _flagged([proposal]) == 0
    Contact.objects.create(company=company, name='Someone', email='NEW.Person@riverside.example.com ')
    _read_all(client)
    row = ChangeProposal.objects.get(pk=proposal.pk)
    assert (row.target_state, row.target_changed_at is not None) == ('duplicate', True)
    assert seen_of(proposal.pk) != seen


def test_a_new_contact_with_the_same_name_counts_as_a_duplicate(agent, person, company):
    proposal = _new_contact(agent, company, email='np@riverside.example.com', name='New Person')
    Contact.objects.create(company=company, name='new  person', email='other@riverside.example.com')
    _read_all(jwt_client(person))
    assert ChangeProposal.objects.get(pk=proposal.pk).target_state == 'duplicate'


def test_an_accept_after_a_duplicate_appeared_is_refused(agent, person, company):
    proposal = _new_contact(agent, company)
    seen = seen_of(proposal.pk)
    Contact.objects.create(company=company, name='Someone', email='new.person@riverside.example.com')
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'record_changed')
    assert Contact.objects.filter(company=company, email__iexact='new.person@riverside.example.com').count() == 1
    fresh = response.json()['proposal']
    assert fresh['target_state'] == 'duplicate'
    # Bound to the new view it is still refused: a duplicate contact is never created.
    again = decide(jwt_client(person), proposal.pk, 'accept', seen_version=fresh['seen_version'])
    assert (again.status_code, again.json()['code']) == (409, 'not_acceptable')
    assert Contact.objects.filter(company=company, email__iexact='new.person@riverside.example.com').count() == 1


def test_a_same_name_duplicate_is_never_added_but_an_edit_can_make_it_new(agent, person, company):
    proposal = _new_contact(agent, company, email='second.pat@riverside.example.com', name='Pat Example')
    seen = seen_of(proposal.pk)
    Contact.objects.create(company=company, name='Pat Example', email='pat@riverside.example.com')
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'record_changed')
    fresh = response.json()['proposal']['seen_version']
    again = decide(jwt_client(person), proposal.pk, 'accept', seen_version=fresh)
    assert (again.status_code, again.json()['code']) == (409, 'not_acceptable')
    assert again.json()['target_state_reason'] == 'A contact with this email or name already exists at the company.'
    edited = decide(jwt_client(person), proposal.pk, 'accept-with-edits', seen_version=seen_of(proposal.pk),
                    edits={'name': 'Pat Example Junior'})
    assert edited.status_code == 200, edited.content
    assert Contact.objects.filter(company=company, name='Pat Example Junior').count() == 1
