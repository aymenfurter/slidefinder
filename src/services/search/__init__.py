"""Search service package."""

from .azure import AzureSearchService, get_azure_search_service

# Re-export as the main search service
SearchService = AzureSearchService
get_search_service = get_azure_search_service

__all__ = [
    "SearchService",
    "get_search_service",
    "AzureSearchService",
    "get_azure_search_service",
]
