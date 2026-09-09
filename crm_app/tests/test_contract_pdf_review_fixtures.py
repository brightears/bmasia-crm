"""Opt-in fictional PDFs for raster QA, generated only in pytest's test DB."""
import os
from pathlib import Path

import pytest

from crm_app.tests.test_contract_pdf_v2 import contract, client, operator, contract_v2_enabled


@pytest.mark.django_db
@pytest.mark.skipif(not os.environ.get('CONTRACT_PDF_REVIEW_DIR'), reason='Opt-in visual QA fixture export')
@pytest.mark.parametrize('category', ['standard', 'corporate_master', 'participation'])
def test_export_contract_review_pdf(contract, client, category):
    contract.contract_category = category
    contract.payment_custom = 'Payment is due in USD within 45 days of the invoice date.'
    contract.payment_schedule = 'Billed annually for the service period shown above.'
    contract.activation_custom = 'Activation follows written approval of the agreed schedule.'
    contract.custom_terms = '\n\n'.join(
        f'{index}. The Parties agree that the service schedule for the designated venue will be reviewed in writing, with existing obligations continuing until a mutually approved replacement takes effect.'
        for index in range(1, 13 if category == 'standard' else 3)
    )
    contract.save()
    response = client.get(f'/api/v1/contracts/{contract.pk}/preview-pdf/')
    assert response.status_code == 200, getattr(response, 'data', None)
    output = Path(os.environ['CONTRACT_PDF_REVIEW_DIR'])
    output.mkdir(parents=True, exist_ok=True)
    (output / f'bmasia-contract-{category}-v2.pdf').write_bytes(response.content)
