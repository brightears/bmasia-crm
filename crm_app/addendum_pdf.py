"""One-page contract addendum PDF (CRM-007).

Same letterhead, party cards and signing area as the agreement it amends. The
body states only the changes, then that every other term stays in force.
"""
from datetime import date
from decimal import Decimal
from html import escape

from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from crm_app.commercial_pdf import (
    CONTENT_WIDTH, LINE, SURFACE, build_document_pdf, clean_text, document_intro,
    document_styles, entity_profile_for, html_text, item_table, metadata_table,
    money, section_heading,
)
from crm_app.contract_pdf_v2 import _signature_table, contract_party_cards
from crm_app.services.contract_addenda import ADDRESS_FIELDS, value_summary
from crm_app.services.document_context import effective_billing_entity

PLATFORM_LABELS = {'soundtrack': 'Soundtrack Your Brand', 'beatbreeze': 'Beat Breeze'}


def _day(value):
    if not value:
        return 'Not specified'
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime('%d %b %Y')


def _product(item):
    return item.get('custom_service_name') or PLATFORM_LABELS.get(item.get('platform'), 'Custom')


def _address(values):
    return ', '.join(values.get(field, '') for field in ADDRESS_FIELDS if values.get(field)) or 'Not specified'


def _flow(value):
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _paragraph(text, styles, style='body'):
    return Paragraph(html_text(text), styles[style])


def _key_values(rows, styles):
    data = [[Paragraph(escape(clean_text(label)), styles['label']), _paragraph(value, styles)]
            for label, value in rows]
    table = Table(data, colWidths=[118, CONTENT_WIDTH - 118], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SURFACE),
        ('BOX', (0, 0), (-1, -1), 0.65, LINE),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


class _AddendumSigners:
    """The parent contract as the signature builder sees it, with this
    addendum's signatory overrides. No full template applies to an addendum."""

    preamble_template = None

    def __init__(self, contract, addendum):
        self._contract = contract
        self._overrides = {
            key: getattr(addendum, key) for key in (
                'customer_signatory_name', 'customer_signatory_title',
                'bmasia_signatory_name', 'bmasia_signatory_title',
            ) if getattr(addendum, key)
        }
        if self._overrides.get('customer_signatory_name'):
            self.additional_customer_signatories = []

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._contract, name)


def _signature_blocks(contract, addendum, entity, styles):
    from crm_app.views import ContractViewSet
    source = ContractViewSet()._build_signature_blocks_table(
        _AddendumSigners(contract, addendum), entity['billing_entity'], entity['name'])
    return _signature_table(source, CONTENT_WIDTH, styles) or source


def _change_sections(addendum, styles):
    contract = addendum.contract
    currency = contract.currency
    sections = []
    added = [item for item in addendum.changes if item['type'] == 'zone_add']
    removed = [item for item in addendum.changes if item['type'] == 'zone_remove']
    end = _day(next((item.get('end_date') for item in addendum.changes
                     if item['type'] == 'dates' and item.get('end_date')), contract.end_date))

    widths = [CONTENT_WIDTH * 0.27, CONTENT_WIDTH * 0.33, CONTENT_WIDTH * 0.23, CONTENT_WIDTH * 0.17]
    if added:
        rows = []
        for item in added:
            service = _product(item)
            if item.get('annual_price'):
                service += f"\n{money(currency, Decimal(item['annual_price']))} per zone per year"
            rows.append([item['name'], service, f"{_day(item['start_date'])} - {end}",
                         money(currency, Decimal(item['price']))])
        sections.append(('Zones added', _flow(item_table(
            ['Zone', 'Service', 'Period', 'Amount'], rows, widths, {3}, styles, amount_columns={3}))))
    if removed:
        rows = [[item['name'], _product(item), _day(addendum.effective_date), money(currency, Decimal(item['credit']))]
                for item in removed]
        sections.append(('Zones removed', _flow(item_table(
            ['Zone', 'Service', 'Ends on', 'Credit'], rows, widths, {3}, styles, amount_columns={3}))))

    summary = value_summary(addendum)
    if summary:
        change = summary['change']
        sign = '+' if change >= 0 else '-'
        sections.append(('Contract value', [_key_values([(
            'New contract value',
            f"{money(currency, summary['after'])}  (was {money(currency, summary['before'])}, "
            f"{sign}{money(currency, abs(change))})",
        )], styles)]))

    for item in addendum.changes:
        kind = item['type']
        if kind == 'dates':
            rows = []
            if item.get('start_date'):
                rows.append(('Start date', f"{_day(item['previous_start_date'])}  to  {_day(item['start_date'])}"))
            if item.get('end_date'):
                rows.append(('End date', f"{_day(item['previous_end_date'])}  to  {_day(item['end_date'])}"))
            sections.append(('Term of the Agreement', [_key_values(rows, styles)]))
        elif kind == 'party':
            rows = []
            if item.get('legal_name'):
                rows.append(('Legal name', f"{item['previous_legal_name']}  to  {item['legal_name']}"))
            if item.get('address'):
                rows.append(('Previous address', _address(item['previous_address'])))
                rows.append(('New address', _address(item['address'])))
            sections.append(('Client details', [_key_values(rows, styles)]))
        elif kind == 'clause':
            if item['action'] == 'replace':
                title = f"Replacement of {item['clause_ref']}"
                lead = f"{item['clause_ref']} of the Agreement is deleted and replaced with the following:"
            else:
                title = f"Additional clause{': ' + item['clause_ref'] if item['clause_ref'] else ''}"
                lead = 'The following clause is added to the Agreement:'
            sections.append((title, [_paragraph(lead, styles), Spacer(1, 4), _paragraph(item['text'], styles)]))
        elif kind == 'bank_details':
            body = []
            if item.get('text'):
                body.extend([_paragraph(item['text'], styles), Spacer(1, 5)])
            body.append(_key_values([
                ('Beneficiary', item['beneficiary']),
                ('Bank', item['bank']),
                ('SWIFT code', item['swift']),
                ('Account number', item['account']),
            ], styles))
            sections.append(('Bank details for payments', body))
    return sections


def build_addendum_pdf(addendum, *, logo_path=None):
    contract = addendum.contract
    styles = document_styles()
    entity = entity_profile_for(effective_billing_entity(contract))
    company = contract.company
    customer = company.legal_entity_name or company.name
    title = f'Addendum No. {addendum.sequence}'
    story = document_intro(title, f'to Agreement {contract.contract_number}', styles)
    story.append(metadata_table([
        ('Addendum number', addendum.addendum_number),
        ('Effective date', _day(addendum.effective_date)),
        ('Original agreement', f'{contract.contract_number}, dated {_day(contract.start_date)}'),
    ], styles))
    story.append(contract_party_cards(contract, entity, styles))
    story.append(Spacer(1, 6))
    story.append(_paragraph(
        f'This addendum amends the agreement {contract.contract_number} dated {_day(contract.start_date)} '
        f'between {entity["name"]} and {customer} (the "Agreement"). From the effective date above, '
        'the Agreement is changed as follows.', styles))
    story.append(Spacer(1, 8))

    for number, (heading, body) in enumerate(_change_sections(addendum, styles), start=1):
        story.append(KeepTogether([section_heading(f'{number:02d}', heading, styles), Spacer(1, 4), *body]))
        story.append(Spacer(1, 8))

    story.append(_paragraph(
        'All other terms and conditions of the Agreement remain unchanged and in full force and effect. '
        'This addendum forms part of the Agreement. If this addendum and the Agreement conflict, '
        'this addendum prevails.', styles))
    story.append(Spacer(1, 16))
    story.append(KeepTogether([_signature_blocks(contract, addendum, entity, styles)]))
    return build_document_pdf(story, document_title=title, document_id=addendum.addendum_number,
                              entity=entity, logo_path=logo_path)
