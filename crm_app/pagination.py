"""
Custom pagination classes for BMAsia CRM API
"""
from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    Pagination class that allows clients to request custom page sizes.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20, max: 1000)

    Example: /api/v1/zones/?page_size=100
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
