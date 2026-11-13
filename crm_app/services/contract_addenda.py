"""Contract addenda (CRM-007): validate, number, and apply one-page changes.

An addendum belongs to one numbered contract and carries a list of change
items. Nothing on the parent contract or company changes until the addendum is
marked Signed; that single write happens under row locks, keeps a before/after
snapshot, and rolls back whole if any part fails.

Change items (``changes`` is a list, at least one item):

- ``zone_add``: name, platform (soundtrack|beatbreeze|custom),
  custom_service_name (custom only), price (amount charged under this
  addendum), optional annual_price (shown as the yearly rate), optional
  start_date (defaults to the effective date). Adds a service-location row and
  raises the contract value by ``price``.
- ``zone_remove``: service_location_id of a row on the contract, credit (the
  amount the contract value drops by; "0" is valid). Not available when the
  contract is priced by line items.
- ``dates``: start_date and/or end_date of the contract.
- ``party``: legal_name and/or address {address_line1, address_line2, city,
  state, postal_code, country}. Applies to the company's legal name/address.
- ``clause``: action add|replace, clause_ref (required to replace), text.
- ``bank_details``: optional text. The issuer's bank details are copied in
  when the item is saved, so the printed numbers never come from a person.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

PARENT_STATUSES = ('Sent', 'Active', 'Renewed')
CHANGE_TYPES = ('zone_add', 'zone_remove', 'dates', 'party', 'clause', 'bank_details')
SINGLE_USE_TYPES = ('dates', 'party', 'bank_details')
PLATFORMS = ('soundtrack', 'beatbreeze', 'custom')
ADDRESS_FIELDS = ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
EDITABLE_FIELDS = (
    'effective_date', 'changes', 'customer_signatory_name', 'customer_signatory_title',
    'bmasia_signatory_name', 'bmasia_signatory_title', 'notes',
)
MAX_ITEMS = 30
MAX_TEXT = 5000
CENT = Decimal('0.01')


class AddendumError(ValueError):
    def __init__(self, message, *, code='invalid', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def payload(self):
        result = {'error': str(self), 'code': self.code}
        if self.details:
            result['details'] = self.details
        return result


def _money(value, label):
    if isinstance(value, bool) or value in (None, ''):
        raise AddendumError(f'{label} is required.')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AddendumError(f'{label} must be a number.')
    if not amount.is_finite() or amount < 0:
        raise AddendumError(f'{label} must be zero or more.')
    return amount.quantize(CENT)


def _date(value, label, *, required=False):
    if value in (None, ''):
        if required:
            raise AddendumError(f'{label} is required.')
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise AddendumError(f'{label} must be a date (YYYY-MM-DD).')


def _text(value, label, *, required=False, limit=MAX_TEXT):
    text = '' if value is None else str(value).strip()
    if required and not text:
        raise AddendumError(f'{label} is required.')
    if len(text) > limit:
        raise AddendumError(f'{label} is longer than {limit} characters.')
    return text


def _iso(value):
    return value.isoformat() if value else None


def parent_error(contract):
    """Why this contract cannot take an addendum, or None."""
    number = contract.contract_number or ''
    if not number or number.startswith(('DRAFT-', 'C-')):
        return 'The contract has no final HK-CT/TH-CT number yet. Change the Draft contract itself instead.'
    if contract.status not in PARENT_STATUSES:
        return f'Only Sent, Active or Renewed contracts take addenda (this one is {contract.status}).'
    return None


def contract_address(company):
    return {field: getattr(company, field, '') or '' for field in ADDRESS_FIELDS}


def _bank_snapshot(contract):
    from crm_app.commercial_pdf import entity_profile_for
    from crm_app.services.document_context import effective_billing_entity
    try:
        entity = entity_profile_for(effective_billing_entity(contract))
    except ValueError as exc:
        raise AddendumError(str(exc))
    return {
        'billing_entity': entity['billing_entity'],
        'beneficiary': entity['name'],
        'bank': entity['bank'],
        'swift': entity['swift'],
        'account': entity['account'],
    }


def _normalize_item(contract, raw, effective_date, uses_line_items):
    if not isinstance(raw, dict):
        raise AddendumError('Each change must be an object.')
    kind = raw.get('type')
    if kind not in CHANGE_TYPES:
        raise AddendumError(f"Unknown change type {kind!r}. Use one of: {', '.join(CHANGE_TYPES)}.")

    if kind == 'zone_add':
        platform = raw.get('platform') or 'soundtrack'
        if platform not in PLATFORMS:
            raise AddendumError(f"Zone platform must be one of: {', '.join(PLATFORMS)}.")
        annual = raw.get('annual_price')
        start = _date(raw.get('start_date'), 'Zone start date') or effective_date
        item = {
            'type': kind,
            'name': _text(raw.get('name'), 'Zone name', required=True, limit=200),
            'platform': platform,
            'custom_service_name': _text(raw.get('custom_service_name'), 'Custom service name', limit=200)
            if platform == 'custom' else '',
            'price': str(_money(raw.get('price'), 'Zone price')),
            'annual_price': None if annual in (None, '') else str(_money(annual, 'Annual price')),
            'start_date': start.isoformat(),
        }
        if platform == 'custom' and not item['custom_service_name']:
            raise AddendumError('A custom zone needs a custom service name.')
        return item

    if kind == 'zone_remove':
        if uses_line_items:
            raise AddendumError(
                'This contract is priced by line items, so a zone cannot be removed by addendum. '
                'Adjust the contract line items instead.', code='line_items')
        location_id = str(raw.get('service_location_id') or '')
        location = None
        if location_id:
            try:
                location = contract.service_locations.filter(id=location_id).first()
            except (ValidationError, ValueError):
                location = None
        if location is None:
            raise AddendumError('Zone to remove was not found on this contract.')
        return {
            'type': kind,
            'service_location_id': str(location.id),
            'name': location.location_name,
            'platform': location.platform,
            'credit': str(_money(raw.get('credit'), 'Credit for the removed zone')),
        }

    if kind == 'dates':
        start = _date(raw.get('start_date'), 'New start date')
        end = _date(raw.get('end_date'), 'New end date')
        if not start and not end:
            raise AddendumError('A date change needs a new start date, end date, or both.')
        new_start = start or contract.start_date
        new_end = end or contract.end_date
        if new_start and new_end and new_end <= new_start:
            raise AddendumError('The new end date must be after the start date.')
        return {
            'type': kind,
            'start_date': _iso(start),
            'end_date': _iso(end),
            'previous_start_date': _iso(contract.start_date),
            'previous_end_date': _iso(contract.end_date),
        }

    if kind == 'party':
        company = contract.company
        legal_name = _text(raw.get('legal_name'), 'New legal name', limit=255) or None
        address = raw.get('address')
        if address is not None:
            if not isinstance(address, dict):
                raise AddendumError('The new address must be an object of address fields.')
            unknown = sorted(set(address) - set(ADDRESS_FIELDS))
            if unknown:
                raise AddendumError(f"Unknown address fields: {', '.join(unknown)}.")
            limits = {'city': 100, 'state': 100, 'postal_code': 20, 'country': 100}
            address = {field: _text(address.get(field), field, limit=limits.get(field, 255))
                       for field in ADDRESS_FIELDS}
            if not any(address.values()):
                address = None
        if not legal_name and not address:
            raise AddendumError('A client details change needs a new legal name, address, or both.')
        return {
            'type': kind,
            'legal_name': legal_name,
            'address': address,
            'previous_legal_name': company.legal_entity_name or company.name,
            'previous_address': contract_address(company),
        }

    if kind == 'clause':
        action = raw.get('action') or 'add'
        if action not in ('add', 'replace'):
            raise AddendumError("Clause action must be 'add' or 'replace'.")
        clause_ref = _text(raw.get('clause_ref'), 'Clause reference', limit=200)
        if action == 'replace' and not clause_ref:
            raise AddendumError('Name the clause being replaced (for example "Clause 5 Payment").')
        return {
            'type': kind,
            'action': action,
            'clause_ref': clause_ref,
            'text': _text(raw.get('text'), 'Clause text', required=True),
        }

    return {'type': kind, 'text': _text(raw.get('text'), 'Bank details text'), **_bank_snapshot(contract)}


def normalize_changes(contract, changes, effective_date):
    """Return validated, display-ready change items or raise AddendumError."""
    if not isinstance(changes, list) or not changes:
        raise AddendumError('An addendum needs at least one change.')
    if len(changes) > MAX_ITEMS:
        raise AddendumError(f'An addendum holds at most {MAX_ITEMS} changes.')
    uses_line_items = contract.line_items.exists()
    items, errors = [], {}
    for index, raw in enumerate(changes):
        try:
            items.append(_normalize_item(contract, raw, effective_date, uses_line_items))
        except AddendumError as exc:
            errors[str(index)] = str(exc)
    if errors:
        raise AddendumError('Some changes are not valid.', details={'changes': errors})
    for kind in SINGLE_USE_TYPES:
        if sum(1 for item in items if item['type'] == kind) > 1:
            raise AddendumError(f'Put all {kind.replace("_", " ")} changes in one item.')
    removed = [item['service_location_id'] for item in items if item['type'] == 'zone_remove']
    if len(removed) != len(set(removed)):
        raise AddendumError('The same zone is removed twice.')
    return items


def value_delta(changes):
    total = Decimal('0')
    for item in changes or []:
        if item.get('type') == 'zone_add':
            total += Decimal(item['price'])
        elif item.get('type') == 'zone_remove':
            total -= Decimal(item['credit'])
    return total.quantize(CENT)


def has_value_change(changes):
    return any(item.get('type') in ('zone_add', 'zone_remove') for item in changes or [])


def _check_version(addendum, expected_version):
    if expected_version in (None, ''):
        return
    if str(expected_version) != addendum.updated_at.isoformat():
        raise AddendumError(
            'The addendum changed since it was read. Read it again and retry.', code='version_conflict',
            details={'current_version': addendum.updated_at.isoformat()})


def _audit(user, action, instance, changes=None, **extra):
    from crm_app.models import AuditLog
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    AuditLog.objects.create(
        user=user, action=action, model_name=instance.__class__.__name__, record_id=str(instance.pk),
        changes=changes, additional_data={'timestamp': timezone.now().isoformat(), **extra},
    )


def _field_values(fields):
    values = {}
    for key in EDITABLE_FIELDS:
        if key in fields and key != 'changes':
            values[key] = fields[key]
    for key in ('customer_signatory_name', 'customer_signatory_title',
                'bmasia_signatory_name', 'bmasia_signatory_title'):
        if key in values:
            values[key] = _text(values[key], key.replace('_', ' '), limit=255)
    if 'notes' in values:
        values['notes'] = _text(values['notes'], 'Notes', limit=20000)
    return values


def create_addendum(contract_id, fields, *, user=None):
    """Create a Draft addendum numbered <contract>-A<n>."""
    from crm_app.models import Contract, ContractAddendum
    unknown = sorted(set(fields) - set(EDITABLE_FIELDS))
    if unknown:
        raise AddendumError(f"Unknown fields: {', '.join(unknown)}.", details={'ignored_keys': unknown})
    with transaction.atomic():
        try:
            contract = Contract.objects.select_for_update().select_related('company').get(id=contract_id)
        except (Contract.DoesNotExist, ValidationError, ValueError, TypeError):
            raise AddendumError('Contract not found.', code='not_found')
        problem = parent_error(contract)
        if problem:
            raise AddendumError(problem, code='parent_not_eligible')
        effective = _date(fields.get('effective_date'), 'Effective date') or timezone.now().date()
        changes = normalize_changes(contract, fields.get('changes'), effective)
        last = contract.addenda.order_by('-sequence').values_list('sequence', flat=True).first() or 0
        sequence = last + 1
        values = _field_values(fields)
        values['effective_date'] = effective
        addendum = ContractAddendum.objects.create(
            contract=contract, sequence=sequence,
            addendum_number=f'{contract.contract_number}-A{sequence}',
            changes=changes, created_by=user if getattr(user, 'is_authenticated', False) else None,
            **values,
        )
        _audit(user, 'CREATE', addendum, contract=contract.contract_number)
    return addendum


def update_draft(addendum_id, fields, *, expected_version=None, user=None):
    unknown = sorted(set(fields) - set(EDITABLE_FIELDS))
    if unknown:
        raise AddendumError(f"Unknown fields: {', '.join(unknown)}.", details={'ignored_keys': unknown})
    with transaction.atomic():
        addendum = _locked(addendum_id)
        _check_version(addendum, expected_version)
        if addendum.status != 'Draft':
            raise AddendumError(f'Only a Draft addendum can be edited (this one is {addendum.status}).',
                                code='not_draft')
        contract = addendum.contract
        problem = parent_error(contract)
        if problem:
            raise AddendumError(problem, code='parent_not_eligible')
        before = {key: getattr(addendum, key) for key in EDITABLE_FIELDS}
        values = _field_values(fields)
        if 'effective_date' in fields:
            values['effective_date'] = _date(fields['effective_date'], 'Effective date', required=True)
        for key, value in values.items():
            setattr(addendum, key, value)
        if 'changes' in fields or 'effective_date' in fields:
            raw_changes = fields.get('changes', addendum.changes)
            addendum.changes = normalize_changes(contract, raw_changes, addendum.effective_date)
        addendum.save()
        changed = {key: {'old': str(before[key]), 'new': str(getattr(addendum, key))}
                   for key in EDITABLE_FIELDS if before[key] != getattr(addendum, key)}
        _audit(user, 'UPDATE', addendum, changed)
    return addendum


def _locked(addendum_id):
    from crm_app.models import ContractAddendum
    try:
        return ContractAddendum.objects.select_for_update().select_related(
            'contract', 'contract__company').get(id=addendum_id)
    except (ContractAddendum.DoesNotExist, ValidationError, ValueError, TypeError):
        raise AddendumError('Addendum not found.', code='not_found')


def mark_sent(addendum_id, *, sent_date=None, expected_version=None, user=None):
    with transaction.atomic():
        addendum = _locked(addendum_id)
        _check_version(addendum, expected_version)
        if addendum.status != 'Draft':
            raise AddendumError(f'Only a Draft addendum can be marked Sent (this one is {addendum.status}).',
                                code='bad_transition')
        problem = parent_error(addendum.contract)
        if problem:
            raise AddendumError(problem, code='parent_not_eligible')
        addendum.status = 'Sent'
        addendum.sent_date = _date(sent_date, 'Sent date') or timezone.now().date()
        addendum.save()
        _audit(user, 'UPDATE', addendum, {'status': {'old': 'Draft', 'new': 'Sent'}})
    return addendum


def cancel(addendum_id, *, expected_version=None, user=None):
    with transaction.atomic():
        addendum = _locked(addendum_id)
        _check_version(addendum, expected_version)
        if addendum.status not in ('Draft', 'Sent'):
            raise AddendumError(f'A {addendum.status} addendum cannot be cancelled.', code='bad_transition')
        old = addendum.status
        addendum.status = 'Cancelled'
        addendum.save()
        _audit(user, 'UPDATE', addendum, {'status': {'old': old, 'new': 'Cancelled'}})
    return addendum


def _contract_snapshot(contract):
    return {
        'value': str(contract.value),
        'tax_amount': str(contract.tax_amount),
        'total_value': str(contract.total_value),
        'start_date': _iso(contract.start_date),
        'end_date': _iso(contract.end_date),
        'service_locations': [
            {'id': str(row.id), 'name': row.location_name, 'platform': row.platform,
             'price': None if row.price is None else str(row.price)}
            for row in contract.service_locations.all()
        ],
    }


def _company_snapshot(company):
    return {'legal_entity_name': company.legal_entity_name, **contract_address(company)}


def mark_signed(addendum_id, *, signed_date=None, expected_version=None, user=None):
    """Mark Signed and apply the changes to the contract in one locked write."""
    from crm_app.models import Company, Contract, ContractLineItem, ContractServiceLocation
    from crm_app.services.contract_service_locations import (
        pricing_mismatch_message, service_location_pricing_mismatch,
    )
    with transaction.atomic():
        addendum = _locked(addendum_id)
        _check_version(addendum, expected_version)
        if addendum.status != 'Sent':
            raise AddendumError(f'Only a Sent addendum can be marked Signed (this one is {addendum.status}).',
                                code='bad_transition')
        contract = Contract.objects.select_for_update().get(id=addendum.contract_id)
        company = Company.objects.select_for_update().get(id=contract.company_id)
        problem = parent_error(contract)
        if problem:
            raise AddendumError(problem, code='parent_not_eligible')
        signed = _date(signed_date, 'Signed date') or timezone.now().date()
        uses_line_items = contract.line_items.exists()
        mismatch_before = service_location_pricing_mismatch(contract)
        before = {'contract': _contract_snapshot(contract), 'company': _company_snapshot(company)}
        contract_fields, company_fields = set(), set()
        created_rows, created_line_items, removed_rows = [], [], []

        for item in addendum.changes:
            kind = item['type']
            if kind == 'zone_add':
                price = Decimal(item['price'])
                last = contract.service_locations.order_by('-sort_order').values_list(
                    'sort_order', flat=True).first() or 0
                row = ContractServiceLocation.objects.create(
                    contract=contract, location_name=item['name'], platform=item['platform'],
                    custom_service_name=item.get('custom_service_name', ''), price=price,
                    sort_order=last + 1,
                )
                created_rows.append(str(row.id))
                if uses_line_items:
                    line = ContractLineItem.objects.create(
                        contract=contract,
                        product_service=item.get('custom_service_name') or row.get_platform_display(),
                        description=f"{item['name']} (addendum {addendum.addendum_number})",
                        quantity=1, unit_price=price, tax_rate=contract.tax_rate,
                    )
                    created_line_items.append(str(line.id))
                contract.value = (contract.value or Decimal('0')) + price
                contract_fields.add('value')
            elif kind == 'zone_remove':
                if uses_line_items:
                    raise AddendumError('This contract is now priced by line items; a zone cannot be '
                                        'removed by addendum.', code='line_items')
                row = contract.service_locations.filter(id=item['service_location_id']).first()
                if row is None:
                    raise AddendumError(f"Zone {item['name']} is no longer on the contract.",
                                        code='zone_missing')
                removed_rows.append(str(row.id))
                row.delete()
                contract.value = (contract.value or Decimal('0')) - Decimal(item['credit'])
                if contract.value < 0:
                    raise AddendumError('The credits would make the contract value negative.')
                contract_fields.add('value')
            elif kind == 'dates':
                if item.get('start_date'):
                    contract.start_date = date.fromisoformat(item['start_date'])
                    contract_fields.add('start_date')
                if item.get('end_date'):
                    contract.end_date = date.fromisoformat(item['end_date'])
                    contract_fields.add('end_date')
                if contract.start_date and contract.end_date and contract.end_date <= contract.start_date:
                    raise AddendumError('The new end date must be after the start date.')
            elif kind == 'party':
                if item.get('legal_name'):
                    company.legal_entity_name = item['legal_name']
                    company_fields.add('legal_entity_name')
                if item.get('address'):
                    for field in ADDRESS_FIELDS:
                        setattr(company, field, item['address'].get(field, ''))
                        company_fields.add(field)

        if 'value' in contract_fields:
            contract.tax_amount = (contract.value * (contract.tax_rate or Decimal('0')) / Decimal('100')).quantize(CENT)
            contract.total_value = contract.value + contract.tax_amount
            contract_fields.update({'tax_amount', 'total_value'})
            mismatch = service_location_pricing_mismatch(contract)
            if mismatch and not mismatch_before:
                raise AddendumError(
                    'Signing would leave the contract total out of line with its zones. '
                    + pricing_mismatch_message(mismatch), code='pricing_mismatch')
        if contract_fields or created_rows or removed_rows:
            contract.save(update_fields=sorted(contract_fields | {'updated_at'}))
        if company_fields:
            company.save(update_fields=sorted(company_fields | {'updated_at'}))

        after = {'contract': _contract_snapshot(contract), 'company': _company_snapshot(company)}
        addendum.status = 'Signed'
        addendum.signed_date = signed
        addendum.applied_at = timezone.now()
        addendum.applied_snapshot = {
            'before': before, 'after': after,
            'created_service_locations': created_rows,
            'created_line_items': created_line_items,
            'removed_service_locations': removed_rows,
        }
        addendum.save()
        _audit(user, 'UPDATE', addendum, {'status': {'old': 'Sent', 'new': 'Signed'}})
        if contract_fields or created_rows or removed_rows:
            _audit(user, 'UPDATE', contract, {'before': before['contract'], 'after': after['contract']},
                   addendum=addendum.addendum_number)
        if company_fields:
            _audit(user, 'UPDATE', company, {'before': before['company'], 'after': after['company']},
                   addendum=addendum.addendum_number)
    return addendum


def value_summary(addendum):
    """Contract value before and after this addendum, for the PDF and API."""
    if not has_value_change(addendum.changes):
        return None
    delta = value_delta(addendum.changes)
    snapshot = addendum.applied_snapshot or {}
    if snapshot.get('before'):
        before = Decimal(snapshot['before']['contract']['value'])
        after = Decimal(snapshot['after']['contract']['value'])
    else:
        before = Decimal(str(addendum.contract.value or 0)).quantize(CENT)
        after = before + delta
    return {'currency': addendum.contract.currency, 'before': before, 'change': delta, 'after': after}
