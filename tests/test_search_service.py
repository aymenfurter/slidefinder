"""
Unit tests for search service.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.search.azure import AzureSearchService
from src.services.search import get_search_service
from src.models.slide import SlideSearchResult, SlideInfo


class TestAzureSearchService:
    """Tests for AzureSearchService class."""
    
    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = Mock()
        settings.ppts_dir = tmp_path / "ppts"
        settings.thumbnails_dir = tmp_path / "thumbnails"
        settings.search_results_limit = 100
        settings.has_azure_search = True
        settings.azure_search_endpoint = "https://test.search.windows.net"
        settings.azure_search_api_key = "test-key"
        settings.azure_search_index_name = "test-index"
        return settings
    
    def test_get_available_pptx_sessions_empty(self, mock_settings, tmp_path):
        """Test getting available sessions when directory is empty."""
        mock_settings.ppts_dir = tmp_path / "empty_ppts"
        mock_settings.ppts_dir.mkdir(parents=True)
        
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = AzureSearchService()
            sessions = service.get_available_pptx_sessions()
            
            assert sessions == set()
    
    def test_get_available_pptx_sessions_with_files(self, mock_settings, tmp_path):
        """Test getting available sessions with PPTX files."""
        ppts_dir = tmp_path / "ppts"
        ppts_dir.mkdir()
        (ppts_dir / "BRK211.pptx").touch()
        (ppts_dir / "BRK212.pptx").touch()
        mock_settings.ppts_dir = ppts_dir
        
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = AzureSearchService()
            sessions = service.get_available_pptx_sessions()
            
            assert "BRK211" in sessions
            assert "BRK212" in sessions
    
    def test_invalidate_pptx_cache(self, mock_settings, tmp_path):
        """Test cache invalidation."""
        ppts_dir = tmp_path / "ppts"
        ppts_dir.mkdir()
        mock_settings.ppts_dir = ppts_dir
        
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = AzureSearchService()
            
            # First call caches result
            sessions1 = service.get_available_pptx_sessions()
            
            # Add a new file
            (ppts_dir / "BRK213.pptx").touch()
            
            # Still cached
            sessions2 = service.get_available_pptx_sessions()
            assert sessions1 == sessions2
            
            # Invalidate and check again
            service.invalidate_pptx_cache()
            sessions3 = service.get_available_pptx_sessions()
            assert "BRK213" in sessions3
    
    def test_index_exists_when_configured(self, mock_settings, tmp_path):
        """Test that index_exists returns True when Azure Search is configured."""
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = AzureSearchService()
            assert service.index_exists is True
    
    def test_index_exists_when_not_configured(self, mock_settings, tmp_path):
        """Test that index_exists returns False when Azure Search is not configured."""
        mock_settings.has_azure_search = False
        
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = AzureSearchService()
            assert service.index_exists is False


class TestSearchServiceFactory:
    """Tests for get_search_service factory function."""
    
    def test_returns_azure_search_service(self, tmp_path):
        """Test that factory returns AzureSearchService when configured."""
        mock_settings = Mock()
        mock_settings.has_azure_search = True
        mock_settings.azure_search_endpoint = "https://test.search.windows.net"
        mock_settings.azure_search_api_key = "test-key"
        mock_settings.azure_search_index_name = "test-index"
        mock_settings.ppts_dir = tmp_path / "ppts"
        mock_settings.thumbnails_dir = tmp_path / "thumbnails"
        mock_settings.search_results_limit = 100
        
        # Reset singleton
        import src.services.search as search_module
        import src.services.search.azure as azure_module
        search_module._search_service = None
        azure_module._azure_search_service = None
        
        with patch("src.services.search.azure.get_settings", return_value=mock_settings):
            service = get_search_service()
            assert isinstance(service, AzureSearchService)
