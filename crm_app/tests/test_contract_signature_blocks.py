from types import SimpleNamespace

from crm_app.views import ContractViewSet


def _plain_text(value):
    if hasattr(value, 'getPlainText'):
        return value.getPlainText()
    return value


def _table_text(table):
    text = []
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, '_cellvalues'):
                text.extend(_table_text(cell))
            elif isinstance(cell, list):
                for item in cell:
                    text.append(_plain_text(item))
            else:
                text.append(_plain_text(cell))
    return [item for item in text if item]


def _contract(additional_signatories):
    company = SimpleNamespace(name='Default Hotel Co.', legal_entity_name='Default Hotel Legal Ltd.')
    return SimpleNamespace(
        company=company,
        bmasia_signatory_name='Chris Andrews',
        bmasia_signatory_title='Director',
        customer_signatory_name='Primary Client',
        customer_signatory_title='General Manager',
        additional_customer_signatories=additional_signatories,
    )


def test_signature_blocks_use_per_signatory_entity_and_poa():
    table = ContractViewSet()._build_signature_blocks_table(
        _contract([
            {
                'name': 'Jane Delegate',
                'title': 'Director',
                'legal_entity_name': 'Owner Entity Pte. Ltd.',
                'poa': 'Power of Attorney dated 01 January 2026',
            }
        ]),
        'BMAsia Limited',
        'BMAsia Limited',
    )

    text = _table_text(table)

    assert 'Primary Client' in text
    assert 'Default Hotel Legal Ltd.' in text
    assert 'Jane Delegate' in text
    assert 'Owner Entity Pte. Ltd.' in text
    assert 'POA: Power of Attorney dated 01 January 2026' in text


def test_signature_blocks_keep_existing_additional_signatory_shape():
    table = ContractViewSet()._build_signature_blocks_table(
        _contract([{'name': 'Legacy Signer', 'title': 'Owner'}]),
        'BMAsia Limited',
        'BMAsia Limited',
    )

    text = _table_text(table)

    assert 'Legacy Signer' in text
    assert 'Owner' in text
    assert text.count('Default Hotel Legal Ltd.') == 2
