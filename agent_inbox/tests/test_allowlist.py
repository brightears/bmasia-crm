"""The proposal allowlist: every field outside it is refused, on every collection."""
import pytest

from agent_inbox import policy
from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.validation import ServiceError
from crm_app.mcp import _COLLECTION_MAP, _get_serializer_class

ALLOWED_COLLECTIONS = ('company', 'contact', 'task')


def writable_fields(collection):
    _, path = _COLLECTION_MAP[collection]
    return sorted(name for name, field in _get_serializer_class(path)().fields.items() if not field.read_only)


def refusal(user, body):
    with pytest.raises(ServiceError) as caught:
        create_proposal(user, body, via='rest')
    return caught.value


def test_allowlist_only_names_writable_fields_of_guarded_collections():
    for kind, targets in policy.PROPOSAL_ALLOWLIST.items():
        assert kind in policy.APPLICABLE_KINDS
        for collection, fields in targets.items():
            assert collection in _COLLECTION_MAP
            assert collection in ALLOWED_COLLECTIONS
            assert set(fields) <= set(writable_fields(collection)), (kind, collection)


@pytest.mark.parametrize('name', [
    'status', 'value', 'total_value', 'tax_rate', 'tax_amount', 'discount_percentage', 'price_per_zone',
    'currency', 'billing_entity', 'start_date', 'end_date', 'sent_date', 'signed_date', 'contract_number',
    'invoice_number', 'quote_number', 'amount', 'paid_date', 'company', 'is_primary', 'unsubscribed',
    'receives_invoice_emails', 'assigned_to', 'legal_entity_name', 'tax_id', 'care_summary',
    'soundtrack_account_id', 'parent_company', 'is_active',
])
def test_sensitive_names_appear_in_no_allowlist(name):
    for targets in policy.PROPOSAL_ALLOWLIST.values():
        for fields in targets.values():
            assert name not in fields


def _body_for(kind, collection, field, company, contact, task):
    target = {'company': company, 'contact': contact, 'task': task}[collection]
    body = {'kind': kind, 'target_collection': collection, 'patch': {field: 'x'}, 'evidence_quote': 'x'}
    if kind in policy.CREATE_KINDS:
        body['company_id'] = str(company.pk)
        body['patch'].update({'name': 'A', 'email': 'a@example.test', 'title': 'T'})
        body['patch'][field] = 'x'
    else:
        body['target_id'] = str(target.pk)
    return body


def _cases():
    cases = []
    for collection in ALLOWED_COLLECTIONS:
        for kind in sorted(policy.APPLICABLE_KINDS):
            if collection not in policy.collections_for(kind):
                continue
            allowed = policy.allowed_fields(kind, collection)
            for field in writable_fields(collection):
                if field not in allowed:
                    cases.append((kind, collection, field))
    return cases


FORBIDDEN_CASES = _cases()


def test_there_are_many_forbidden_cases():
    assert len(FORBIDDEN_CASES) >= 100


@pytest.fixture
def task(company, person):
    from crm_app.models import Task
    return Task.objects.create(company=company, title='Existing task', created_by=person)


@pytest.mark.parametrize('kind, collection, field', FORBIDDEN_CASES)
def test_every_field_outside_the_allowlist_is_refused(agent, company, contact, task, kind, collection, field):
    error = refusal(agent, _body_for(kind, collection, field, company, contact, task))
    assert (error.status, error.code) == (422, 'field_not_allowed')
    assert field in error.extra['blocked_fields']
    assert ChangeProposal.objects.count() == 0


FORBIDDEN_COLLECTIONS = sorted(set(_COLLECTION_MAP) - set(ALLOWED_COLLECTIONS))


@pytest.mark.parametrize('collection', FORBIDDEN_COLLECTIONS)
@pytest.mark.parametrize('kind', sorted(policy.APPLICABLE_KINDS))
def test_every_other_collection_is_refused_with_every_field(agent, company, collection, kind):
    for field in writable_fields(collection):
        body = {'kind': kind, 'target_collection': collection, 'target_id': str(company.pk),
                'company_id': str(company.pk), 'patch': {field: 'x'}, 'evidence_quote': 'x'}
        error = refusal(agent, body)
        assert (error.status, error.code) == (422, 'collection_not_allowed'), (collection, field)
    assert ChangeProposal.objects.count() == 0


def test_contract_fields_cannot_reach_a_contract_through_a_company_target(agent, person, company, contract):
    """Naming a company target never lets a contract field through."""
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'status': 'Cancelled', 'value': '1'}, 'evidence_quote': 'x'}
    error = refusal(agent, body)
    assert error.code == 'field_not_allowed'
    assert sorted(error.extra['blocked_fields']) == ['status', 'value']
    contract.refresh_from_db()
    assert contract.status == 'Active'
