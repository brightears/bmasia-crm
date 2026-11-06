"""Contract addenda (CRM-007): numbering, validation, apply-on-sign, PDF, API."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from crm_app.models import (
    AuditLog, Company, Contract, ContractAddendum, ContractLineItem, ContractServiceLocation, User,
)
from crm_app.services import contract_addenda as addenda
from crm_app.services.contract_addenda import AddendumError


def _company(**extra):
    values = dict(
        name='Melia Vinpearl Hai Phong Rivera', legal_entity_name='Vinpearl Hai Phong JSC',
        country='Vietnam', city='Hai Phong', address_line1='1 Le Thanh Tong',
        billing_entity='BMAsia Limited',
    )
    values.update(extra)
    return Company.objects.create(**values)


def _contract(company=None, **extra):
    values = dict(
        company=company or _company(), contract_number='HK-CT261021', status='Active',
        start_date=date(2026, 7, 22), end_date=date(2027, 7, 21), value=Decimal('520.00'),
        tax_rate=Decimal('0'), tax_amount=Decimal('0'), total_value=Decimal('520.00'),
        currency='USD', price_per_zone=Decimal('260.00'), show_zone_pricing_detail=True,
        customer_signatory_name='Nguyen Van A', customer_signatory_title='General Manager',
    )
    values.update(extra)
    contract = Contract.objects.create(**values)
    if 'contract_number' in extra or values['contract_number'] != contract.contract_number:
        Contract.objects.filter(id=contract.id).update(contract_number=values['contract_number'])
        contract.refresh_from_db()
    return contract


def _with_zones(contract, names=('Lobby', 'Pool Bar')):
    return [ContractServiceLocation.objects.create(
        contract=contract, location_name=name, platform='soundtrack', sort_order=index)
        for index, name in enumerate(names)]


@pytest.fixture
def admin():
    return User.objects.create_user(username='norbert', password='x', role='Admin')


def test_numbers_follow_the_parent_and_skip_the_document_sequence():
    contract = _contract()
    first = addenda.create_addendum(contract.id, {'changes': [{'type': 'bank_details'}]})
    second = addenda.create_addendum(contract.id, {'changes': [{'type': 'clause', 'text': 'X'}]})
    assert (first.addendum_number, second.addendum_number) == ('HK-CT261021-A1', 'HK-CT261021-A2')
    assert first.status == 'Draft'
    assert Contract.objects.count() == 1


@pytest.mark.parametrize('status_name, number', [('Draft', 'DRAFT-0001'), ('Expired', 'HK-CT261021'),
                                                 ('Cancelled', 'HK-CT261021')])
def test_only_numbered_live_contracts_take_addenda(status_name, number):
    contract = _contract(status=status_name)
    Contract.objects.filter(id=contract.id).update(contract_number=number)
    with pytest.raises(AddendumError) as exc:
        addenda.create_addendum(contract.id, {'changes': [{'type': 'bank_details'}]})
    assert exc.value.code == 'parent_not_eligible'


def test_bank_details_are_copied_from_the_issuer_not_typed():
    contract = _contract()
    addendum = addenda.create_addendum(contract.id, {'changes': [
        {'type': 'bank_details', 'text': 'Payments go to:', 'account': '000-FAKE'}]})
    item = addendum.changes[0]
    assert item['account'] == '808-021570-838'
    assert item['swift'] == 'HSBCHKHHHKH'
    assert item['beneficiary'] == 'BMAsia Limited'


@pytest.mark.parametrize('changes, message', [
    ([], 'at least one change'),
    ([{'type': 'rename'}], 'not valid'),
    ([{'type': 'zone_add', 'name': 'Spa'}], 'not valid'),
    ([{'type': 'zone_add', 'name': 'Spa', 'price': '-1'}], 'not valid'),
    ([{'type': 'dates', 'end_date': '2026-01-01'}], 'not valid'),
    ([{'type': 'clause', 'action': 'replace', 'text': 'New wording'}], 'not valid'),
    ([{'type': 'party'}], 'not valid'),
    ([{'type': 'bank_details'}, {'type': 'bank_details'}], 'in one item'),
])
def test_invalid_changes_are_refused(changes, message):
    contract = _contract()
    with pytest.raises(AddendumError) as exc:
        addenda.create_addendum(contract.id, {'changes': changes})
    assert message in str(exc.value)
    assert not ContractAddendum.objects.exists()


def test_zone_remove_must_name_a_row_on_this_contract():
    contract = _contract()
    other = _contract(company=_company(name='Other hotel'), contract_number='HK-CT261022')
    foreign = _with_zones(other, ['Elsewhere'])[0]
    with pytest.raises(AddendumError) as exc:
        addenda.create_addendum(contract.id, {'changes': [
            {'type': 'zone_remove', 'service_location_id': str(foreign.id), 'credit': '0'}]})
    assert 'not found on this contract' in exc.value.details['changes']['0']


def test_only_drafts_can_be_edited_and_versions_are_checked():
    contract = _contract()
    addendum = addenda.create_addendum(contract.id, {'changes': [{'type': 'bank_details'}]})
    with pytest.raises(AddendumError) as exc:
        addenda.update_draft(addendum.id, {'notes': 'x'}, expected_version='2000-01-01T00:00:00+00:00')
    assert exc.value.code == 'version_conflict'
    addendum = addenda.update_draft(addendum.id, {'notes': 'checked'}, expected_version=addendum.updated_at.isoformat())
    assert addendum.notes == 'checked'
    addenda.mark_sent(addendum.id)
    with pytest.raises(AddendumError) as exc:
        addenda.update_draft(addendum.id, {'notes': 'late'})
    assert exc.value.code == 'not_draft'


def test_signing_requires_sent_and_is_final():
    contract = _contract()
    addendum = addenda.create_addendum(contract.id, {'changes': [{'type': 'bank_details'}]})
    with pytest.raises(AddendumError):
        addenda.mark_signed(addendum.id)
    addenda.mark_sent(addendum.id, sent_date='2026-10-30')
    addendum = addenda.mark_signed(addendum.id, signed_date='2026-10-31')
    assert (addendum.status, addendum.sent_date, addendum.signed_date) == ('Signed', date(2026, 10, 30), date(2026, 10, 31))
    with pytest.raises(AddendumError):
        addenda.cancel(addendum.id)


def test_nothing_changes_on_the_contract_until_signed(admin):
    contract = _contract()
    lobby, pool = _with_zones(contract)
    addendum = addenda.create_addendum(contract.id, {'effective_date': '2026-11-01', 'changes': [
        {'type': 'zone_add', 'name': 'Tenggara', 'platform': 'beatbreeze', 'price': '195', 'annual_price': '260'},
        {'type': 'zone_remove', 'service_location_id': str(pool.id), 'credit': '260'},
        {'type': 'dates', 'end_date': '2027-10-31'},
        {'type': 'party', 'legal_name': 'Vinpearl Hai Phong JSC (renamed)',
         'address': {'address_line1': '2 New Street', 'city': 'Hai Phong', 'country': 'Vietnam'}},
    ]}, user=admin)
    addenda.mark_sent(addendum.id, user=admin)
    contract.refresh_from_db()
    assert contract.value == Decimal('520.00')
    assert contract.service_locations.count() == 2

    addenda.mark_signed(addendum.id, user=admin)
    contract.refresh_from_db()
    company = contract.company
    company.refresh_from_db()
    assert contract.value == Decimal('455.00')
    assert contract.total_value == Decimal('455.00')
    assert contract.end_date == date(2027, 10, 31)
    assert sorted(contract.service_locations.values_list('location_name', flat=True)) == ['Lobby', 'Tenggara']
    new_row = contract.service_locations.get(location_name='Tenggara')
    assert (new_row.platform, new_row.price) == ('beatbreeze', Decimal('195.00'))
    assert company.legal_entity_name == 'Vinpearl Hai Phong JSC (renamed)'
    assert (company.address_line1, company.address_line2) == ('2 New Street', '')
    assert company.name == 'Melia Vinpearl Hai Phong Rivera'

    addendum.refresh_from_db()
    snapshot = addendum.applied_snapshot
    assert snapshot['before']['contract']['value'] == '520.00'
    assert snapshot['after']['contract']['value'] == '455.00'
    assert snapshot['removed_service_locations'] == [str(pool.id)]
    assert addenda.value_summary(addendum)['after'] == Decimal('455.00')
    assert AuditLog.objects.filter(model_name='Contract', record_id=str(contract.id),
                                   additional_data__addendum='HK-CT261021-A1').exists()
    assert AuditLog.objects.filter(model_name='Company', record_id=str(company.id)).exists()


def test_signing_recomputes_tax():
    contract = _contract(currency='THB', tax_rate=Decimal('7'), tax_amount=Decimal('36.40'),
                         total_value=Decimal('556.40'), show_zone_pricing_detail=False)
    addendum = addenda.create_addendum(contract.id, {'changes': [
        {'type': 'zone_add', 'name': 'Spa', 'price': '1000'}]})
    addenda.mark_sent(addendum.id)
    addenda.mark_signed(addendum.id)
    contract.refresh_from_db()
    assert (contract.value, contract.tax_amount, contract.total_value) == (
        Decimal('1520.00'), Decimal('106.40'), Decimal('1626.40'))


def test_signing_rolls_back_when_zone_pricing_would_stop_reconciling():
    contract = _contract()
    _, pool = _with_zones(contract)
    addendum = addenda.create_addendum(contract.id, {'changes': [
        {'type': 'zone_add', 'name': 'Spa', 'price': '195'},
        {'type': 'zone_remove', 'service_location_id': str(pool.id), 'credit': '0'},
        {'type': 'dates', 'end_date': '2027-12-31'}]})
    addenda.mark_sent(addendum.id)
    with pytest.raises(AddendumError) as exc:
        addenda.mark_signed(addendum.id)
    assert exc.value.code == 'pricing_mismatch'
    contract.refresh_from_db()
    addendum.refresh_from_db()
    assert addendum.status == 'Sent'
    assert contract.end_date == date(2027, 7, 21)
    assert not contract.service_locations.filter(location_name='Spa').exists()
    assert contract.service_locations.filter(id=pool.id).exists()


def test_line_item_contracts_get_a_line_item_and_cannot_remove_zones():
    contract = _contract(show_zone_pricing_detail=False)
    ContractLineItem.objects.create(contract=contract, product_service='Soundtrack Your Brand',
                                    quantity=2, unit_price=Decimal('260'))
    row = _with_zones(contract, ['Lobby'])[0]
    with pytest.raises(AddendumError):
        addenda.create_addendum(contract.id, {'changes': [
            {'type': 'zone_remove', 'service_location_id': str(row.id), 'credit': '0'}]})
    addendum = addenda.create_addendum(contract.id, {'changes': [
        {'type': 'zone_add', 'name': 'Spa', 'price': '260'}]})
    addenda.mark_sent(addendum.id)
    addenda.mark_signed(addendum.id)
    assert contract.line_items.filter(description='Spa (addendum HK-CT261021-A1)', unit_price=Decimal('260')).exists()


@pytest.mark.parametrize('changes', [
    [{'type': 'bank_details', 'text': 'All payments under the Agreement are made by bank transfer to:'}],
    [{'type': 'zone_add', 'name': 'Tenggara', 'platform': 'beatbreeze', 'price': '195', 'annual_price': '260'}],
    [{'type': 'party', 'legal_name': 'New Owner Co., Ltd.', 'address': {'address_line1': '9 Road', 'city': 'Hanoi'}},
     {'type': 'dates', 'end_date': '2027-12-31'}],
])
def test_typical_addenda_fit_on_one_page(changes):
    from crm_app.addendum_pdf import build_addendum_pdf
    contract = _contract(show_zone_pricing_detail=False)
    addendum = addenda.create_addendum(contract.id, {'changes': changes})
    assert len(PdfReader(BytesIO(build_addendum_pdf(addendum))).pages) == 1


def test_pdf_carries_every_change_and_both_signers():
    from crm_app.addendum_pdf import build_addendum_pdf
    contract = _contract()
    _, pool = _with_zones(contract)
    addendum = addenda.create_addendum(contract.id, {'effective_date': '2026-11-01', 'changes': [
        {'type': 'bank_details', 'text': 'All payments under the Agreement are made to:'},
        {'type': 'zone_add', 'name': 'Tenggara', 'platform': 'beatbreeze', 'price': '195', 'annual_price': '260'},
        {'type': 'zone_remove', 'service_location_id': str(pool.id), 'credit': '0'},
        {'type': 'clause', 'action': 'replace', 'clause_ref': 'Clause 5 Payment',
         'text': 'Payment is due within 30 days of invoice.'},
    ]})
    data = build_addendum_pdf(addendum)
    reader = PdfReader(BytesIO(data))
    text = ' '.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) <= 2
    for expected in ('Addendum No. 1', 'HK-CT261021-A1', '808-021570-838', 'Tenggara',
                     'Replacement of Clause 5 Payment', 'remain unchanged', 'Nguyen Van A',
                     'Vinpearl Hai Phong JSC', 'USD 715.00'):
        assert expected in text, expected


def test_api_flow_and_no_delete(admin):
    contract = _contract()
    client = APIClient()
    client.force_authenticate(admin)
    created = client.post('/api/v1/contract-addenda/', {
        'contract': str(contract.id), 'changes': [{'type': 'bank_details'}]}, format='json')
    assert created.status_code == 201, created.content
    body = created.json()
    assert body['addendum_number'] == 'HK-CT261021-A1'
    assert body['created_by'] == str(admin.id)
    addendum_id = body['id']

    stale = client.patch(f'/api/v1/contract-addenda/{addendum_id}/', {
        'notes': 'x', 'expected_version': '2000-01-01T00:00:00+00:00'}, format='json')
    assert stale.status_code == 409
    bad = client.post('/api/v1/contract-addenda/', {'contract': str(contract.id), 'changes': [],
                                                    'status': 'Signed'}, format='json')
    assert bad.status_code == 400

    listed = client.get(f'/api/v1/contract-addenda/?contract__company={contract.company_id}')
    assert [row['id'] for row in listed.json()['results']] == [addendum_id]
    assert client.post(f'/api/v1/contract-addenda/{addendum_id}/mark-sent/', {}, format='json').status_code == 200
    signed = client.post(f'/api/v1/contract-addenda/{addendum_id}/mark-signed/', {}, format='json')
    assert signed.json()['status'] == 'Signed'
    pdf = client.get(f'/api/v1/contract-addenda/{addendum_id}/pdf/')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert client.delete(f'/api/v1/contract-addenda/{addendum_id}/').status_code == 405


def test_mcp_tools_cover_the_whole_lifecycle():
    import base64
    import json
    from crm_app.mcp import (
        create_contract_addendum, generate_addendum_pdf, set_contract_addendum_status,
        update_contract_addendum,
    )
    contract = _contract(show_zone_pricing_detail=False)
    created = json.loads(create_contract_addendum(str(contract.id), json.dumps({
        'effective_date': '2026-11-01',
        'changes': [{'type': 'zone_add', 'name': 'Tenggara', 'platform': 'beatbreeze', 'price': '195'}]})))
    assert created['ok'] and created['addendum_number'] == 'HK-CT261021-A1'
    assert created['value_summary'] == {'currency': 'USD', 'before': '520.00', 'change': '195.00', 'after': '715.00'}

    refused = json.loads(create_contract_addendum(str(contract.id), json.dumps({'changes': [], 'status': 'Signed'})))
    assert refused == {'ok': False, 'error': 'Unknown fields: status.', 'code': 'invalid',
                       'details': {'ignored_keys': ['status']}}
    assert json.loads(update_contract_addendum(created['id'], '{"notes": "x"}', ''))['ok'] is False

    edited = json.loads(update_contract_addendum(created['id'], '{"notes": "per HK-QT26172"}',
                                                 created['expected_version']))
    assert edited['ok']
    early = json.loads(set_contract_addendum_status(created['id'], 'Signed', edited['expected_version']))
    assert early['code'] == 'bad_transition'
    sent = json.loads(set_contract_addendum_status(created['id'], 'Sent', edited['expected_version'], '2026-10-30'))
    signed = json.loads(set_contract_addendum_status(created['id'], 'Signed', sent['expected_version']))
    assert signed['status'] == 'Signed'
    contract.refresh_from_db()
    assert contract.value == Decimal('715.00')

    pdf = json.loads(generate_addendum_pdf(created['id']))
    assert base64.b64decode(pdf['content_b64']).startswith(b'%PDF')
    assert pdf['filename'] == 'Addendum_HK-CT261021-A1.pdf'
    assert 'error' in json.loads(generate_addendum_pdf('not-a-uuid'))
