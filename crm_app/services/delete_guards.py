"""Deletes that would erase customer history are refused, with the alternative named.

What a delete takes with it (on_delete=CASCADE):
- Company: contacts, contracts (and their zone links, service locations, line items,
  documents), quotes, invoices, opportunities, notes, tasks, zones, devices, tickets,
  tech details, email logs, campaigns, sequence enrolments, care touches.
- Contract: zone links, service locations, line items, documents, revenue events.
- Quote: line items, attachments, activity.
- Invoice: line items.
- Contact: campaign recipients, sequence and prospect enrolments.
"""


def _plural(count, word):
    return f'{count} {word}' + ('' if count == 1 else 's')


def company_delete_refusal(company):
    """None when the company may be deleted, otherwise the reply body for a 409."""
    counts = {
        'contracts': company.contracts.count(),
        'invoices': company.invoices.count(),
        'quotes': company.quotes.count(),
    }
    if not any(counts.values()):
        return None
    held = ', '.join(_plural(n, word[:-1]) for word, n in counts.items() if n)
    return {
        'error': (
            f'{company.name} has {held}, so it cannot be deleted: that would delete them too. '
            'Set the company inactive instead (is_active = false).'
        ),
        'code': 'company_has_records',
        **counts,
    }


# Agents (MCP delete_record): collections that may not be deleted, and what to do instead.
MCP_DELETE_ALTERNATIVES = {
    'company': (
        "update_record('company', id, {\"is_active\": false}) to deactivate it. Deleting a company "
        "also deletes its contacts, contracts, quotes, invoices, zones, notes and tasks."
    ),
    'contact': (
        "update_record('contact', id, {\"is_active\": false}) to deactivate the contact "
        "(and, if they asked not to be emailed, {\"unsubscribed\": true})."
    ),
    'contract': (
        "update_record('contract', id, {\"status\": \"Cancelled\"}) to cancel it; cancelling "
        "also releases its zones. A replaced term is linked with renewed_from instead."
    ),
    'quote': (
        "update_record('quote', id, {\"status\": \"Rejected\"}) for a declined quote, or "
        "{\"status\": \"Expired\"} for one that lapsed."
    ),
    'invoice': (
        "update_record('invoice', id, {\"status\": \"Cancelled\"}). Invoices are numbered in "
        "the accounting system, so a CRM invoice is cancelled, never removed."
    ),
}
