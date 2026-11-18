"""The customer's legal name as printed on quotes and contracts.

A legal name of only spaces counts as missing, so the company name is used,
exactly as for an empty legal name. Every other input keeps its old output.
Synthetic fixtures only.
"""

from types import SimpleNamespace

import pytest

from crm_app.services.document_context import customer_legal_entity_name
from crm_app.tests.test_contract_pdf_v2 import (  # noqa: F401  (fixtures)
    _assert_a4,
    _text,
    client,
    contract,
    contract_v2_enabled,
    operator,
)


def _company(**values):
    defaults = dict(name="Example Hotel", legal_entity_name="Example Hotel Co., Ltd.", branch="")
    defaults.update(values)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize("values, expected", [
    # Unchanged outputs.
    ({}, "Example Hotel Co., Ltd."),
    ({"branch": "Branch 00001"}, "Example Hotel Co., Ltd. (Branch 00001)"),
    ({"branch": "  Branch 00001  "}, "Example Hotel Co., Ltd. (Branch 00001)"),
    ({"legal_entity_name": "Example Hotel Co., Ltd. (branch 00001)", "branch": "Branch 00001"},
     "Example Hotel Co., Ltd. (branch 00001)"),
    ({"legal_entity_name": "  Example Hotel Co., Ltd.  "}, "Example Hotel Co., Ltd."),
    ({"legal_entity_name": ""}, "Example Hotel"),
    ({"legal_entity_name": None, "branch": "Branch 00001"}, "Example Hotel (Branch 00001)"),
    ({"legal_entity_name": "", "name": "", "branch": ""}, ""),
    # A legal name of only spaces falls back to the company name.
    ({"legal_entity_name": "   "}, "Example Hotel"),
    ({"legal_entity_name": "   ", "branch": "Branch 00001"}, "Example Hotel (Branch 00001)"),
    ({"legal_entity_name": "\t \n", "name": "  Example Hotel  "}, "Example Hotel"),
])
def test_customer_legal_entity_name(values, expected):
    assert customer_legal_entity_name(_company(**values)) == expected


def test_customer_legal_entity_name_without_a_company():
    assert customer_legal_entity_name(None) == ""


@pytest.mark.django_db
def test_contract_card_uses_company_name_when_legal_name_is_only_spaces(contract, client):
    company = contract.company
    company.legal_entity_name = "   "
    company.branch = "Branch 00001"
    company.save(update_fields=["legal_entity_name", "branch"])

    response = client.get(f"/api/v1/contracts/{contract.pk}/pdf/")

    _assert_a4(response)
    text = _text(response.content)
    expected = f"{company.name} (Branch 00001)"
    assert expected in text
    # The branch is never printed on its own in place of the customer's name.
    assert text.count("(Branch 00001)") == text.count(expected)
