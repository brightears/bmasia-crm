import json

import pytest
from mcp_server.query_tool import QueryTool

from crm_app.mcp import (
    ContractTemplateQuery,
    _COLLECTION_MAP,
    create_record,
    delete_record,
    update_record,
)
from crm_app.models import ContractTemplate


def test_contract_template_query_publishes_required_fields():
    assert ContractTemplateQuery.model is ContractTemplate
    assert {
        'id',
        'name',
        'template_type',
        'content',
        'pdf_format',
        'is_default',
        'is_active',
        'version',
        'created_at',
        'updated_at',
    } <= set(ContractTemplateQuery.fields)

    tool = QueryTool()
    tool.add_query_tool_model(ContractTemplateQuery)
    assert tool.query_tool_models['contracttemplate'] is ContractTemplateQuery


@pytest.mark.django_db
def test_contract_template_generic_create_and_update_preserve_exact_content():
    created = json.loads(
        create_record(
            'contracttemplate',
            json.dumps(
                {
                    'name': 'Hilton International — Stream-only',
                    'template_type': 'preamble',
                    'content': "Supplier's Business License: 34683002-000-05-26-3",
                    'pdf_format': 'standard',
                    'is_default': False,
                    'is_active': True,
                    'version': '1.0',
                }
            ),
        )
    )

    template = ContractTemplate.objects.get(id=created['id'])
    assert template.name == 'Hilton International — Stream-only'
    assert template.content == "Supplier's Business License: 34683002-000-05-26-3"
    assert template.pdf_format == 'standard'
    assert 'warning_ignored_keys' not in created

    updated = json.loads(
        update_record(
            'contracttemplate',
            str(template.id),
            json.dumps(
                {
                    'content': '{{hotel_legal_name}} (trading as {{hotel_trading_name}})',
                    'version': '1.1',
                }
            ),
        )
    )

    template.refresh_from_db()
    assert updated == {
        'updated': True,
        'id': str(template.id),
        'applied': {
            'content': '{{hotel_legal_name}} (trading as {{hotel_trading_name}})',
            'version': '1.1',
        },
    }
    assert template.content == '{{hotel_legal_name}} (trading as {{hotel_trading_name}})'
    assert template.version == '1.1'


@pytest.mark.django_db
def test_contract_template_generic_delete_is_blocked():
    template = ContractTemplate.objects.create(
        name='Protected template',
        template_type='preamble',
        content='Protected content',
        pdf_format='participation',
    )

    assert 'contracttemplate' in _COLLECTION_MAP
    assert 'Generic contract-template deletion is blocked' in delete_record(
        'contracttemplate',
        str(template.id),
    )
    assert ContractTemplate.objects.filter(id=template.id).exists()
