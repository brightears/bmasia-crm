"""
Custom pagination classes for BMAsia CRM API
"""
from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination


def _ends_on_unique_key(model, term):
    """True when an ordering term is the primary key or another unique, non-null column."""
    if not isinstance(term, str):
        return False
    name = term.lstrip('-+')
    if name == 'pk' or '__' in name:
        return name == 'pk'
    try:
        field = model._meta.get_field(name)
    except Exception:
        return False
    return getattr(field, 'primary_key', False) or (getattr(field, 'unique', False)
                                                     and not getattr(field, 'null', True))


def with_unique_tiebreak(queryset):
    """The same queryset, ordered so that no two rows tie: the primary key comes last.

    Rows that differ on the existing ordering keep their order; only rows that are equal on
    every ordering key are put in primary-key order, instead of an order the database is free
    to change between two page queries (which duplicated and dropped rows across pages).
    The default ordering (Meta.ordering) counts as the existing ordering.
    """
    if not isinstance(queryset, QuerySet) or queryset.query.is_sliced or queryset.query.combinator:
        return queryset
    query = queryset.query
    if query.order_by:
        ordering = list(query.order_by)
    elif query.default_ordering and queryset.model._meta.ordering:
        ordering = list(queryset.model._meta.ordering)
    else:
        ordering = []
    if '?' in ordering:
        return queryset  # random order was asked for
    if ordering and _ends_on_unique_key(queryset.model, ordering[-1]):
        return queryset
    if queryset._fields is not None and 'pk' not in queryset._fields and \
            queryset.model._meta.pk.name not in queryset._fields:
        return queryset  # a values() queryset without its key: leave it alone
    return queryset.order_by(*ordering, 'pk')


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    Pagination class that allows clients to request custom page sizes.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20, max: 1000)

    Example: /api/v1/zones/?page_size=100

    Every page is cut from an ordering that ends on the primary key (see
    with_unique_tiebreak), so walking the pages returns every row exactly once.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000

    def paginate_queryset(self, queryset, request, view=None):
        return super().paginate_queryset(with_unique_tiebreak(queryset), request, view)
