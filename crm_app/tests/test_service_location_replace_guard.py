"""Service-location rows are deleted only when the request names them.

Regression for the contract form: opening a contract whose rows are not backed by music line items
and saving it sent `replace_service_locations: true` with a list rebuilt from nothing, and the API
deleted every saved row. A replacement may now drop a row only when its id is listed in
`remove_service_location_ids`; anything else is refused and nothing is written. All data synthetic.
"""
import json
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.mcp import update_record
from crm_app.models import ContractServiceLocation, User
from crm_app.serializers import ContractSerializer
from crm_app.tests.factories import ContractFactory
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db
_n = iter(range(1, 10_000))


def _contract(names=('Lobby', 'Pool', 'Spa'), status='Active'):
    contract = ContractFactory(value=Decimal('900.00'), currency='USD', price_per_zone=Decimal('300.00'),
                               show_zone_pricing_detail=True, discount_percentage=Decimal('0.00'),
                               status=status, company__soundtrack_account_id='')
    rows = [ContractServiceLocation.objects.create(contract=contract, location_name=name, platform='soundtrack',
                                                   sort_order=i) for i, name in enumerate(names)]
    return contract, rows


def _state(contract):
    contract.refresh_from_db()
    return (str(contract.value), sorted((str(r.id), r.location_name, r.platform)
                                        for r in contract.service_locations.all()))


def _patch(contract, data):
    user = User.objects.create_user(username=f'sl-guard-{next(_n)}', role='Sales')
    request = APIRequestFactory().patch(f'/api/v1/contracts/{contract.pk}/', data, format='json')
    force_authenticate(request, user=user)
    return ContractViewSet.as_view({'patch': 'partial_update'})(request, pk=str(contract.pk))


def _row(r, **over):
    return {'id': str(r.id), 'location_name': r.location_name, 'platform': r.platform,
            'sort_order': r.sort_order, **over}


# --- the reported loss ----------------------------------------------------------------

def test_empty_replacement_from_the_form_is_refused_and_keeps_rows():
    contract, _ = _contract()
    before = _state(contract)
    response = _patch(contract, {'notes': 'edited', 'service_locations': [], 'replace_service_locations': True})
    assert response.status_code == 400
    assert 'would delete 3 existing service location' in str(response.data['service_locations'])
    assert _state(contract) == before
    contract.refresh_from_db()
    assert contract.notes != 'edited'  # the whole update rolled back


def test_partial_replacement_that_omits_rows_is_refused():
    contract, rows = _contract()
    before = _state(contract)
    response = _patch(contract, {'value': '600.00', 'replace_service_locations': True,
                                 'service_locations': [_row(rows[0]), _row(rows[1])]})
    assert response.status_code == 400
    assert _state(contract) == before


def test_replacement_rebuilt_without_ids_is_refused():
    # Same names, no ids: would delete the saved rows and create look-alikes with new ids.
    contract, rows = _contract()
    before = _state(contract)
    response = _patch(contract, {'replace_service_locations': True, 'service_locations': [
        {'location_name': r.location_name, 'platform': r.platform, 'sort_order': r.sort_order} for r in rows]})
    assert response.status_code == 400
    assert _state(contract) == before


# --- deliberate edits keep working --------------------------------------------------------

def test_full_list_with_ids_saves_and_keeps_ids():
    contract, rows = _contract()
    response = _patch(contract, {'replace_service_locations': True, 'service_locations': [
        _row(rows[0], location_name='Lobby renamed'), _row(rows[1]), _row(rows[2])]})
    assert response.status_code == 200, response.data
    _, after = _state(contract)
    assert [r[0] for r in after] == sorted(str(r.id) for r in rows)
    assert 'Lobby renamed' in [r[1] for r in after]


def test_named_removal_in_replace_mode_deletes_only_those_rows():
    contract, rows = _contract()
    response = _patch(contract, {'value': '600.00', 'replace_service_locations': True,
                                 'remove_service_location_ids': [str(rows[2].id)],
                                 'service_locations': [_row(rows[0]), _row(rows[1])]})
    assert response.status_code == 200, response.data
    _, after = _state(contract)
    assert [r[0] for r in after] == sorted([str(rows[0].id), str(rows[1].id)])


def test_named_removal_with_additions_in_one_save():
    contract, rows = _contract()
    response = _patch(contract, {'replace_service_locations': True,
                                 'remove_service_location_ids': [str(rows[2].id)],
                                 'service_locations': [_row(rows[0]), _row(rows[1]),
                                                       {'location_name': 'Gym', 'platform': 'soundtrack',
                                                        'sort_order': 3}]})
    assert response.status_code == 200, response.data
    names = sorted(r.location_name for r in contract.service_locations.all())
    assert names == ['Gym', 'Lobby', 'Pool']


def test_removal_only_update_without_replace():
    contract, rows = _contract()
    response = _patch(contract, {'value': '600.00', 'remove_service_location_ids': [str(rows[0].id)]})
    assert response.status_code == 200, response.data
    assert not ContractServiceLocation.objects.filter(id=rows[0].id).exists()
    assert contract.service_locations.count() == 2


def test_partial_upsert_still_never_deletes():
    contract, rows = _contract()
    response = _patch(contract, {'service_locations': [_row(rows[0], location_name='Front desk')]})
    assert response.status_code == 200, response.data
    assert contract.service_locations.count() == 3


def test_update_without_service_location_keys_leaves_rows_alone():
    contract, _ = _contract()
    before = _state(contract)
    assert _patch(contract, {'notes': 'only a note'}).status_code == 200
    assert _state(contract) == before


# --- malformed removal requests ------------------------------------------------------------

def test_foreign_removal_id_is_refused():
    contract, _ = _contract()
    _, other_rows = _contract(('Elsewhere',))
    before = _state(contract)
    response = _patch(contract, {'remove_service_location_ids': [str(other_rows[0].id)]})
    assert response.status_code == 400
    assert _state(contract) == before
    assert ContractServiceLocation.objects.filter(id=other_rows[0].id).exists()


def test_row_both_kept_and_removed_is_refused():
    contract, rows = _contract()
    before = _state(contract)
    response = _patch(contract, {'remove_service_location_ids': [str(rows[0].id)],
                                 'service_locations': [_row(rows[0])]})
    assert response.status_code == 400
    assert _state(contract) == before


def test_replace_without_a_list_is_refused():
    contract, _ = _contract()
    response = _patch(contract, {'replace_service_locations': True})
    assert response.status_code == 400


def test_create_with_removal_ids_is_refused():
    contract, rows = _contract()
    serializer = ContractSerializer(data={
        'company': str(contract.company_id), 'start_date': '2026-01-01', 'end_date': '2026-12-31',
        'value': '100.00', 'remove_service_location_ids': [str(rows[0].id)]})
    assert not serializer.is_valid()
    assert 'no service locations to remove' in str(serializer.errors['remove_service_location_ids'])
    assert ContractServiceLocation.objects.filter(id=rows[0].id).exists()


# --- agent (MCP) paths ----------------------------------------------------------------------

def test_mcp_replacement_without_named_removals_is_refused():
    contract, rows = _contract()
    before = _state(contract)
    result = update_record('contract', str(contract.pk), json.dumps({
        'replace_service_locations': True, 'service_locations': [_row(rows[0])], 'value': '300.00'}))
    assert result.startswith('Validation errors:')  # the tool's normal refusal reply
    assert 'remove_service_location_ids' in result and 'No rows were changed' in result
    assert _state(contract) == before


def test_mcp_guarded_replacement_with_named_removals():
    contract, rows = _contract(status='Draft')
    observed = ContractSerializer(contract).data
    patch = {'value': '600.00', 'replace_service_locations': True,
             'remove_service_location_ids': [str(rows[2].id)],
             'service_locations': [_row(rows[0]), _row(rows[1])]}
    expected = {'value': observed['value'], 'replace_service_locations': None,
                'remove_service_location_ids': None,
                'service_locations': json.loads(json.dumps(observed['service_locations'], default=str))}
    result = json.loads(update_record('contract', str(contract.pk), json.dumps(patch),
                                      expected_version=observed['updated_at'],
                                      expected_values=json.dumps(expected)))
    assert result['updated'] is True, result
    assert result['applied']['remove_service_location_ids'] == [str(rows[2].id)]
    assert sorted(str(r.id) for r in contract.service_locations.all()) == sorted([str(rows[0].id), str(rows[1].id)])
