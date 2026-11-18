"""Which unlinked contracts could be a term's next term.

Shared by the Needs fixing check (``data_quality.EndingWithoutSuccessor``) and the
Renewals page (``renewals_page_service``), so both leave out the same contracts:
one-time services, consulting and maintenance, One-time contracts or billing,
add-ons and churn records, and contracts that end on or before the term's end.
"""

ONE_OFF_SERVICE_TYPES = ('one_time_setup', 'consulting', 'maintenance')
ONE_OFF_LIFECYCLE_TYPES = ('addon', 'churn')
ONE_OFF_CONTRACT_TYPE = 'One-time'
ONE_OFF_BILLING = ('one-time', 'one time', 'onetime', 'once')


def exclude_one_offs(queryset):
    """The queryset without one-off and add-on contracts (service type, lifecycle type, contract type)."""
    return (queryset
            .exclude(service_type__in=ONE_OFF_SERVICE_TYPES)
            .exclude(lifecycle_type__in=ONE_OFF_LIFECYCLE_TYPES)
            .exclude(contract_type=ONE_OFF_CONTRACT_TYPE))


def is_one_off_billing(billing_frequency):
    return (billing_frequency or '').strip().lower() in ONE_OFF_BILLING


def is_one_off(service_type, lifecycle_type, contract_type, billing_frequency):
    """exclude_one_offs() and is_one_off_billing() for a contract already read."""
    return ((service_type or '') in ONE_OFF_SERVICE_TYPES
            or (lifecycle_type or '') in ONE_OFF_LIFECYCLE_TYPES
            or contract_type == ONE_OFF_CONTRACT_TYPE
            or is_one_off_billing(billing_frequency))


def ends_after_term(term_end, start, end):
    """A next term ends after the term it follows and after its own start (no end date passes)."""
    return end is None or (end > term_end and end > start)
