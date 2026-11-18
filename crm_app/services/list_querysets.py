"""Querysets for the list endpoints: the related data each list row needs, fetched once per page.

Without them the list serializers query the database again for every row (about 14
queries per company and 10 per contract). Each list action loads its rows through one
of these functions; the serializers and model properties read what they prepared:

- annotations named ``_list_*`` hold counts and sums worked out by the database, with
  the same filters and the same SQL aggregate the per-row code used, so the values,
  their types and their decimal places are what they were;
- ``to_attr`` prefetches named ``_prefetched_*`` hold the related rows a field needs,
  already filtered by the database where the per-row code filtered.

Where none of this has been loaded (detail pages, updates, other callers) the
serializers and properties keep querying exactly as before, so a record that was just
changed is never served from a stale prefetch.
"""
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Subquery, Sum
from django.db.models.functions import Coalesce


def count_of(model, fk, **filters):
    """Number of `model` rows pointing at the outer row through `fk`, 0 when there are none."""
    rows = (
        model.objects.filter(**{fk: OuterRef('pk')}, **filters)
        .order_by()
        .values(fk)
        .annotate(n=Count('pk'))
        .values('n')
    )
    return Coalesce(Subquery(rows, output_field=IntegerField()), 0)


def sum_of(model, fk, field, exclude=None, **filters):
    """SUM(field) over the `model` rows pointing at the outer row; NULL when there are none.

    The same aggregate the per-row `.aggregate(Sum(field))` ran, so the database returns
    the value in the same form (on SQLite a float-derived Decimal, on PostgreSQL numeric).
    """
    rows = model.objects.filter(**{fk: OuterRef('pk')}, **filters)
    if exclude:
        rows = rows.exclude(**exclude)
    rows = rows.order_by().values(fk).annotate(total=Sum(field)).values('total')
    return Subquery(rows)


def zone_links_prefetch(prefix=''):
    """Each zone's contract links with the few contract fields Zone.get_current_link() reads."""
    from crm_app.models import ContractZone

    links = ContractZone.objects.select_related('contract').only(
        'id', 'zone_id', 'contract_id', 'start_date', 'end_date', 'is_active',
        'contract__id', 'contract__contract_number', 'contract__status', 'contract__start_date',
    )
    return Prefetch(f'{prefix}zone_contracts', queryset=links, to_attr='_prefetched_zone_links')


def contract_list_queryset(queryset):
    """Contracts for /contracts/ (ContractSerializer). Keeps the view's select_related."""
    from crm_app.models import Contract, ContractDocument, ContractZone, Invoice

    invoices = Invoice.objects.select_related('company').prefetch_related('line_items')
    return (
        queryset
        .prefetch_related(None)
        .prefetch_related(
            'line_items',
            'service_locations',
            'service_items',
            Prefetch('contract_zones', queryset=ContractZone.objects.select_related('zone')),
            Prefetch('invoices', queryset=invoices),
            Prefetch('contract_documents',
                     queryset=ContractDocument.objects.select_related('uploaded_by')),
        )
        .annotate(
            _list_paid_invoices_count=count_of(Invoice, 'contract', status='Paid'),
            _list_outstanding_amount=sum_of(Invoice, 'contract', 'total_amount',
                                            exclude={'status': 'Paid'}),
            _list_active_zone_link_count=count_of(ContractZone, 'contract', is_active=True),
            _list_participation_agreements_count=count_of(Contract, 'master_contract'),
            _list_renewal_count=count_of(Contract, 'renewed_from'),
        )
    )


def company_list_queryset(queryset):
    """Companies for /companies/ (CompanySerializer)."""
    from crm_app.models import Contact, Contract, Opportunity, Zone

    zones = Zone.objects.select_related('device').prefetch_related(zone_links_prefetch())
    active_contracts = Contract.objects.filter(is_active=True).only(
        'id', 'company_id', 'contract_type', 'currency', 'value', 'start_date',
    )
    return (
        queryset
        .prefetch_related(None)
        .select_related('parent_company')
        .prefetch_related(
            'contacts',
            Prefetch('contacts', queryset=Contact.objects.filter(is_primary=True, is_active=True),
                     to_attr='_prefetched_primary_contacts'),
            Prefetch('zones', queryset=zones),
            Prefetch('contracts', queryset=active_contracts, to_attr='_prefetched_active_contracts'),
            'child_companies',
        )
        .annotate(
            _list_active_opportunities_count=count_of(Opportunity, 'company', is_active=True),
            _list_total_contract_value=sum_of(Contract, 'company', 'value', is_active=True),
        )
    )
