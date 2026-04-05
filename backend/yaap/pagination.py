from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """Default pagination — used for lists like search results, friends."""
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class MessageCursorPagination(CursorPagination):
    """
    Cursor-based pagination for chat messages.
    Cursor pagination is ideal for infinite scroll because it is stable
    even when new messages arrive (no page-drift).
    """
    page_size = 50
    ordering = "-created_at"
    cursor_query_param = "cursor"
