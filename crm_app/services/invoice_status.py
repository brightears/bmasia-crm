"""The one rule for moving an invoice's status, used by every writer.

| From      | A plain update may set          | Sending the invoice              |
|-----------|---------------------------------|----------------------------------|
| Draft     | Sent, Overdue, Cancelled, Refunded | sets Sent                     |
| Sent      | Overdue, Cancelled, Refunded    | resend: status unchanged         |
| Overdue   | Sent, Cancelled, Refunded       | resend: status unchanged         |
| Paid      | Refunded                        | resend: status unchanged         |
| Cancelled | nothing                         | refused                          |
| Refunded  | nothing                         | refused                          |

- Paid is reached only through "Mark as paid" (crm_app/services/invoice_payments.py).
- Saving the current status is always allowed.
- Deliberate admin actions cover mistakes: "Mark selected invoices as unpaid" (Paid → Sent,
  keeps the receipt number) and "Reopen selected cancelled invoices" (Cancelled → Sent).

Writers: the invoice serializer (REST create/update, the agents' create_record/update_record,
bulk update_status), the send endpoint and EmailService.send_invoice_email, the payment
reminder sender (Sent → Overdue), and the Django admin change form.
"""

PLAIN_UPDATE_MOVES = {
    'Draft': frozenset({'Sent', 'Overdue', 'Cancelled', 'Refunded'}),
    'Sent': frozenset({'Overdue', 'Cancelled', 'Refunded'}),
    'Overdue': frozenset({'Sent', 'Cancelled', 'Refunded'}),
    'Paid': frozenset({'Refunded'}),
    'Cancelled': frozenset(),
    'Refunded': frozenset(),
}

SENDABLE = frozenset({'Draft', 'Sent', 'Overdue', 'Paid'})


def plain_update_refusal(current, target):
    """None when an edit may move the invoice from ``current`` to ``target``, else the reason."""
    if target is None or current is None or target == current:
        return None
    if target == 'Paid':
        return ('An invoice is marked paid only with "Mark as paid", which records the payment date and '
                'issues the receipt number. Payments are recorded by a person in the CRM (Invoices → '
                'Mark as paid; API: POST /api/v1/invoices/{id}/mark_paid/). An agent cannot set Paid: '
                'tell the person which invoice was paid and the payment date.')
    if target in PLAIN_UPDATE_MOVES.get(current, frozenset()):
        return None
    if current == 'Paid':
        return (f'A paid invoice cannot be set to {target} by an edit. Paid can change only to Refunded; '
                'to undo a payment recorded by mistake, use the admin action "Mark selected invoices as '
                'unpaid" (it keeps the receipt number).')
    if current == 'Cancelled':
        return ('A cancelled invoice stays cancelled. To reopen one cancelled by mistake, use the admin '
                'action "Reopen selected cancelled invoices".')
    if current == 'Refunded':
        return 'A refunded invoice stays refunded.'
    if target == 'Draft':
        return (f'An invoice that is {current} cannot go back to Draft. Use Cancelled for one that '
                'should not stand.')
    return f'An invoice cannot move from {current} to {target} by an edit.'


def send_refusal(current):
    """None when the invoice may be emailed to the customer, else the reason."""
    if current in SENDABLE:
        return None
    reason = f'A {current.lower()} invoice is not sent to the customer.'
    if current == 'Cancelled':
        reason += ' Reopen it first if it was cancelled by mistake (admin: "Reopen selected cancelled invoices").'
    return reason


def status_after_send(current):
    """The status once the invoice has been emailed: Draft becomes Sent; a resend changes nothing."""
    return 'Sent' if current == 'Draft' else current
