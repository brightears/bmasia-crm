"""What a list read costs once records were edited, note suggestions, moved and unacceptable targets."""
import threading

import pytest
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client, make_user, seen_of
from agent_inbox.validation import url_warnings
from crm_app.models import Company, Contact

FOUR = (('phone', '+66 2 111 2222'), ('city', 'Chiang Mai'), ('state', 'Phuket'), ('postal_code', '50000'))


def _read(client):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(PROPOSALS, {'page_size': 200})
    assert response.status_code == 200
    sql = [q['sql'].lstrip().upper() for q in queries.captured_queries]
    return len(sql), sum(1 for q in sql if q.startswith('UPDATE')), len(response.json()['results'])


def _page(agent, rows, prefix='Example Count Hotel'):
    companies = []
    made = 0
    while made < rows:
        company = Company.objects.create(name=f'{prefix} {len(companies):03d}',
                                         billing_entity='BMAsia Limited', phone='+66 2 000 0000')
        companies.append(company)
        for field, value in FOUR[:min(4, rows - made)]:
            create_proposal(agent, {'kind': 'field_update', 'target_collection': 'company',
                                    'target_id': str(company.pk), 'patch': {field: value},
                                    'evidence_quote': 'as written'}, via='rest')
            made += 1
    return companies


def _edit_all(companies, **fields):
    for company in companies:
        company.refresh_from_db()
        for name, value in fields.items():
            setattr(company, name, value)
        company.save()


@pytest.mark.parametrize('rows', [5, 50, 200])
def test_list_read_cost_after_unrelated_and_watched_edits(agent, person, rows):
    client = jwt_client(person)
    companies = _page(agent, rows)
    _read(client)
    idle, idle_updates, shown = _read(client)
    assert (idle_updates, shown) == (0, rows)

    # An unrelated edit on every company: one small version UPDATE per company on the
    # first read (and one query more to read the watched values), then back to idle.
    _edit_all(companies, notes='An unrelated line')
    first, updates, _ = _read(client)
    assert updates == len(companies)
    assert first - updates <= idle + 1
    assert _read(client) == (idle, 0, rows)
    assert ChangeProposal.objects.filter(target_changed_at__isnull=False).count() == 0

    # A watched edit (phone): the phone suggestions are flagged, the others' versions advanced.
    _edit_all(companies, phone='+66 2 444 4444')
    watching = ChangeProposal.objects.filter(patch__has_key='phone').count() if connection.vendor == 'postgresql' \
        else sum(1 for p in ChangeProposal.objects.all() if 'phone' in p.patch)
    others = sum(1 for c in companies if ChangeProposal.objects.filter(target_id=str(c.pk)).count() > 1)
    first, updates, _ = _read(client)
    assert updates == watching + others
    assert first - updates <= idle + 1
    assert _read(client) == (idle, 0, rows)
    assert ChangeProposal.objects.filter(target_changed_at__isnull=False).count() == watching


def test_only_compared_suggestions_have_their_version_advanced(agent, person, company):
    """Reading one suggestion never advances another's version unseen, so a later read still flags it."""
    client = jwt_client(person)
    phone = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'company',
                                    'target_id': str(company.pk), 'patch': {'phone': '+66 2 111 2222'},
                                    'evidence_quote': 'as written'}, via='rest')[0]
    city = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'company',
                                   'target_id': str(company.pk), 'patch': {'city': 'Chiang Mai'},
                                   'evidence_quote': 'as written'}, via='rest')[0]
    company.refresh_from_db()
    company.city = 'Phuket'
    company.save()
    assert client.get(f'{PROPOSALS}{phone.pk}/').json()['target_changed_at'] is None
    shown = client.get(f'{PROPOSALS}{city.pk}/').json()
    assert shown['target_changed_at'] and shown['current_values'] == {'city': 'Phuket'}


def test_the_idle_read_does_not_grow_with_rows(agent, person):
    client = jwt_client(person)
    _page(agent, 5)
    _read(client)
    small = _read(client)[0]
    _page(agent, 45, prefix='Example More Hotel')
    _read(client)
    assert _read(client)[0] == small


# ------------------------------------------------------------------ notes only append


def test_five_notes_accepted_one_by_one_flag_nothing(agent, person, company):
    client = jwt_client(person)
    notes = [create_proposal(agent, {'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
                                     'patch': {'notes': f'Note number {n}'}, 'evidence_quote': 'as written'},
                             via='rest')[0] for n in range(5)]
    flagged = []
    for index, note in enumerate(notes):
        client.get(PROPOSALS)
        response = decide(client, note.pk, 'accept')
        assert response.status_code == 200, response.content
        client.get(PROPOSALS)
        rest = [n.pk for n in notes[index + 1:]]
        flagged.append(ChangeProposal.objects.filter(pk__in=rest, target_changed_at__isnull=False).count())
    assert flagged == [0, 0, 0, 0, 0]
    company.refresh_from_db()
    assert all(f'Note number {n}' in company.notes for n in range(5))
    assert company.notes.startswith('Existing company note')


def test_a_note_still_follows_its_records_state(agent, person, contact):
    note = create_proposal(agent, {'kind': 'note', 'target_collection': 'contact', 'target_id': str(contact.pk),
                                   'patch': {'notes': 'Prefers calls'}, 'evidence_quote': 'as written'}, via='rest')[0]
    assert jwt_client(person).get(f'{PROPOSALS}{note.pk}/').json()['watched_fields'] == []
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    shown = jwt_client(person).get(f'{PROPOSALS}{note.pk}/').json()
    assert shown['target_state'] == 'inactive' and shown['target_changed_at']


# ------------------------------------------------------------------ a moved contact


def test_a_contact_moved_to_another_company_is_flagged_and_never_accepted(agent, person, company, other_company,
                                                                         contact):
    client = jwt_client(person)
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                       'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                       'evidence_quote': 'Director'}, via='rest')[0]
    seen = seen_of(proposal.pk)
    Contact.objects.filter(pk=contact.pk).update(company=other_company)
    response = decide(client, proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'record_changed')
    assert response.json()['target_state'] == 'moved'
    assert 'now belongs to another company' in response.json()['detail']
    shown = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert (shown['target_state'], shown['target_state_reason']) == (
        'moved', 'This contact now belongs to another company.')
    again = decide(client, proposal.pk, 'accept', seen_version=shown['seen_version'])
    assert (again.status_code, again.json()['code']) == (409, 'not_acceptable')
    contact.refresh_from_db()
    assert contact.title == 'Manager' and contact.company_id == other_company.pk
    # Moved back, it is present again (a change too) and can be accepted.
    Contact.objects.filter(pk=contact.pk).update(company=company)
    back = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert back['target_state'] == 'present' and back['target_state_reason'] == ''
    assert decide(client, proposal.pk, 'accept', seen_version=back['seen_version']).status_code == 200


def test_a_read_flags_a_moved_contact(agent, person, other_company, contact):
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                       'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                       'evidence_quote': 'Director'}, via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(company=other_company)
    jwt_client(person).get(PROPOSALS)
    row = ChangeProposal.objects.get(pk=proposal.pk)
    assert row.target_state == 'moved' and row.target_changed_at is not None


# ------------------------------------------------------------------ states the server never accepts


@pytest.mark.parametrize('collection', ['company', 'contact'])
def test_an_inactive_record_is_never_accepted_even_with_a_fresh_view(agent, person, company, contact, collection):
    target = company if collection == 'company' else contact
    field, value = ('city', 'Chiang Mai') if collection == 'company' else ('title', 'Director')
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': collection,
                                       'target_id': str(target.pk), 'patch': {field: value},
                                       'evidence_quote': 'as written'}, via='rest')[0]
    type(target).objects.filter(pk=target.pk).update(is_active=False)
    shown = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert shown['target_state'] == 'inactive'
    assert shown['target_state_reason'] == f'This {collection} is inactive. Activate it first to accept this suggestion.'
    for route, extra in (('accept', {}), ('accept-with-edits', {'edits': {field: value + ' (edited)'}})):
        response = decide(jwt_client(person), proposal.pk, route, seen_version=shown['seen_version'], **extra)
        assert (response.status_code, response.json()['code']) == (409, 'not_acceptable')
    target.refresh_from_db()
    assert getattr(target, field) != value


def test_a_deleted_record_reads_with_its_reason_and_fails_on_accept(agent, person, contact):
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                       'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                       'evidence_quote': 'Director'}, via='rest')[0]
    Contact.objects.filter(pk=contact.pk).delete()
    shown = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert (shown['target_state'], shown['target_state_reason']) == ('missing', 'This record no longer exists.')
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=shown['seen_version'])
    assert (response.status_code, response.json()['code']) == (409, 'target_missing')


def test_the_serializer_shows_the_state_for_a_present_record(agent, person, company):
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'company',
                                       'target_id': str(company.pk), 'patch': {'city': 'Chiang Mai'},
                                       'evidence_quote': 'as written'}, via='rest')[0]
    shown = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert (shown['target_state'], shown['target_state_reason'], shown['watched_fields']) == ('present', '', ['city'])
    new = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                  'patch': {'name': 'Brand New', 'email': 'brand.new@riverside.example.com'},
                                  'evidence_quote': 'please add brand.new@riverside.example.com'}, via='rest')[0]
    shown = jwt_client(person).get(f'{PROPOSALS}{new.pk}/').json()
    assert (shown['target_state'], shown['target_state_reason']) == ('no_duplicate', '')


# ------------------------------------------------------------------ new-contact accepts one at a time


@pytest.mark.skipif(connection.vendor != 'postgresql', reason='row locks need PostgreSQL')
@pytest.mark.django_db(transaction=True)
def test_two_same_name_new_contacts_accepted_at_once_create_one(agent, other_agent, company):
    first = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                    'patch': {'name': 'Twin Name', 'email': 'twin.a@riverside.example.com'},
                                    'evidence_quote': 'please add twin.a@riverside.example.com'}, via='rest')[0]
    second = create_proposal(other_agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                           'patch': {'name': 'Twin Name', 'email': 'twin.b@riverside.example.com'},
                                           'evidence_quote': 'please add twin.b@riverside.example.com'},
                             via='rest')[0]
    seen = {first.pk: seen_of(first.pk), second.pk: seen_of(second.pk)}
    barrier = threading.Barrier(2)
    codes = []

    def accept(proposal_id, username):
        try:
            client = jwt_client(make_user(username, role='Admin'))
            barrier.wait()
            response = client.post(f'{PROPOSALS}{proposal_id}/accept/', {'seen_version': seen[proposal_id]},
                                   format='json')
            codes.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=accept, args=(first.pk, 'reviewer-person')),
               threading.Thread(target=accept, args=(second.pk, 'second-person'))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(codes) == [200, 409]
    assert Contact.objects.filter(company=company, name='Twin Name').count() == 1


# ------------------------------------------------------------------ the providers' own domains


@pytest.mark.parametrize('url', [
    'https://outlook.office365.com/mail/', 'https://outlook.live.com/mail/', 'https://login.microsoftonline.com/x',
    'https://outlook.office.com/x', 'https://docs.google.co.th/x', 'https://www.google.de/x',
    'https://mail.google.com.vn/x', 'https://accounts.google.co.uk/x', 'https://www.hotmail.com/x',
    'https://www.google.co.kr/x',
])
def test_the_providers_own_country_and_service_domains_carry_no_warning(url):
    assert url_warnings('source_url', url, 'other') == []


@pytest.mark.parametrize('url', [
    'https://google.evil.co.th/x', 'https://outlook.example.co.uk/x', 'https://office365-login.example/x',
    'https://mail.google.com.other.example/x',
])
def test_a_provider_name_under_an_unrelated_domain_still_warns(url):
    assert [w['code'] for w in url_warnings('source_url', url, 'other')] == ['url_lookalike_host']
