"""
Search service for slide content using Azure AI Search.

Security: All file paths are derived from the search index, not user input.
"""
import logging
from typing import Optional

from config import get_settings
from services.azure_search_service import AzureSearchService, get_azure_search_service

logger = logging.getLogger(__name__)


# Re-export for backwards compatibility
SearchService = AzureSearchService


def get_search_service() -> AzureSearchService:
    """
    Get the singleton search service instance.
    
    Returns the Azure AI Search service.
    """
    return get_azure_search_service()

