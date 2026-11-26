"""Reserve a Draft contract's final number for review without recording delivery.

Renewals have used this since September. New contracts use it too (Norbert,
2026-09-30), so the PDF a customer receives already carries its permanent
HK-CT/TH-CT number and the contract can later be recorded as Sent unchanged.
"""

import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from crm_app.models import Contract, RenePreparedContract
from crm_app.services import mcp_audit
from crm_app.services.rene_phase2 import (
    RenePhase2Error,
    _reserve_final_contract_number,
)
from crm_app.services.rene_phase2_common import rfc3339


FINAL_CONTRACT_NUMBER = re.compile(r'(?:HK|TH)-CT\d{5,}')


class ContractReviewError(ValueError):
    """The requested review cannot be prepared without changing its scope."""


def _render_numbered_sent_contract(contract, render_pdf):
    """Render a Sent contract that already carries its final number.

    The caller holds the row lock and has checked expected_version. Nothing is
    reserved and nothing is written: a revised Sent contract only needs its
    current PDF, under the number the customer already has.
    """
    if FINAL_CONTRACT_NUMBER.fullmatch(contract.contract_number or '') is None:
        raise ContractReviewError(
            'A Sent contract without a final HK-CT/TH-CT number needs reconciliation; '
            'no number is reserved for a Sent contract.'
        )
    if contract.renewed_from_id and contract.renewed_from.company_id != contract.company_id:
        raise ContractReviewError('Renewal and predecessor must belong to the same company.')
    response = render_pdf(contract)
    if response.status_code != 200 or not response.content.startswith(b'%PDF-'):
        raise ContractReviewError('Contract PDF generation failed; nothing was changed.')
    return response, {
        'contract_id': str(contract.id),
        'contract_number': contract.contract_number,
        'status': contract.status,
        'sent_date': contract.sent_date.isoformat() if contract.sent_date else None,
        'updated_at': rfc3339(contract.updated_at),
        'customer_delivery_performed': False,
    }


def generate_numbered_renewal_review(contract_id, expected_version, render_pdf):
    """Render one current renewal Draft with its permanent Cira-owned number."""
    return generate_numbered_contract_review(
        contract_id, expected_version, render_pdf, require_renewal=True,
    )


@transaction.atomic
def generate_numbered_contract_review(contract_id, expected_version, render_pdf, *, require_renewal=False):
    """Render one current Draft contract with its permanent Cira-owned number.

    The caller supplies the last observed updated_at, never a document number.
    The contract row remains locked through rendering. A failed PDF rolls back
    the reservation; successful retries reuse the already reserved number.
    No save signals, lifecycle transitions, or customer delivery are invoked.

    A Sent contract that already carries its final number is rendered under the
    same lock and version check without reserving or writing anything (not for
    renewal-only calls, which stay Draft-only). Other statuses are refused.
    """
    try:
        expected = parse_datetime(expected_version) if isinstance(expected_version, str) else None
    except ValueError:
        expected = None
    if expected is None or timezone.is_naive(expected):
        raise ContractReviewError('A timezone-aware expected_version from the current contract read is required.')

    # renewed_from is nullable in the model: restrict PostgreSQL's row lock to
    # the contract itself instead of locking the nullable side of the join.
    contract = Contract.objects.select_for_update(of=('self',)).select_related(
        'company', 'renewed_from'
    ).get(pk=contract_id)
    if contract.updated_at != expected:
        raise ContractReviewError('stale_read: contract changed; read it again before preparing the review PDF.')
    if require_renewal and (contract.status != 'Draft' or not contract.renewed_from_id):
        raise ContractReviewError('Numbered renewal review requires an existing linked renewal in Draft status.')
    if contract.status == 'Sent':
        return _render_numbered_sent_contract(contract, render_pdf)
    if contract.status != 'Draft':
        raise ContractReviewError(
            f'A final number can be reserved only for a Draft contract; this contract is '
            f'{contract.status}. Only a Sent contract that already carries its final number can be '
            f're-rendered here, because a fresh PDF of a {contract.status} contract can differ from '
            f'the signed copy.'
        )
    if contract.renewed_from_id and contract.renewed_from.company_id != contract.company_id:
        raise ContractReviewError('Renewal and predecessor must belong to the same company.')
    if contract.sent_date is not None:
        raise ContractReviewError('A Draft with a sent date needs reconciliation before review preparation.')
    if RenePreparedContract.objects.filter(contract_id=contract.id).exists():
        raise ContractReviewError('This renewal belongs to an existing dedicated preparation receipt; use that receipt.')

    number = contract.contract_number or ''
    if not number or number.startswith(('DRAFT-', 'C-')):
        try:
            number = _reserve_final_contract_number(contract)
        except RenePhase2Error as exc:
            raise ContractReviewError('No safe final contract number could be reserved.') from exc
        # Updating exactly these fields avoids lifecycle/revenue side effects
        # from Contract.save() and its signals. Status and delivery evidence
        # remain unchanged, including historical Draft is_active values.
        previous_number = contract.contract_number
        Contract.objects.filter(pk=contract.pk).update(
            contract_number=number, updated_at=timezone.now()
        )
        contract.refresh_from_db()
        # Same transaction: a failed render rolls back the number and its row.
        mcp_audit.record(
            'UPDATE', 'Contract', contract.pk, tool='generate_contract_pdf',
            changes={'contract_number': {'old': previous_number, 'new': contract.contract_number}},
            extra={
                'kind': 'renewal_number_reservation' if require_renewal else 'final_number_reservation',
                'expected_version': expected_version,
                'post_version': rfc3339(contract.updated_at),
            },
        )
    elif FINAL_CONTRACT_NUMBER.fullmatch(number) is None:
        raise ContractReviewError('The existing contract number needs reconciliation before review preparation.')

    response = render_pdf(contract)
    if response.status_code != 200 or not response.content.startswith(b'%PDF-'):
        raise ContractReviewError('Review PDF generation failed; no number reservation was committed.')
    return response, {
        'contract_id': str(contract.id),
        'contract_number': contract.contract_number,
        'status': contract.status,
        'sent_date': None,
        'updated_at': rfc3339(contract.updated_at),
        'customer_delivery_performed': False,
    }
