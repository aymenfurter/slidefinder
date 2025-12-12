"""
Unit tests for configuration module.
"""
import os
from unittest.mock import patch

import pytest

from src.core import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = Settings()
        
        assert settings.app_name == "SlideFinder"
        assert settings.host == "0.0.0.0"
        assert settings.port == 7004
        assert settings.debug is False
    
    def test_port_validation(self):
        """Test that port validation works."""
        with pytest.raises(ValueError):
            Settings(port=0)  # Below minimum
        
        with pytest.raises(ValueError):
            Settings(port=70000)  # Above maximum
        
        settings = Settings(port=8080)
        assert settings.port == 8080
    
    def test_path_properties(self):
        """Test that path properties return correct values."""
        settings = Settings()
        
        assert settings.index_dir.name == "slide_index"
        assert settings.ppts_dir.name == "ppts"
        assert settings.thumbnails_dir.name == "thumbnails"
        assert settings.compiled_decks_dir.name == "compiled_decks"
    
    @patch.dict(os.environ, {
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4",
    })
    def test_has_azure_openai(self):
        """Test Azure OpenAI detection."""
        settings = Settings()
        
        assert settings.has_azure_openai is True
        assert settings.llm_provider == "azure"
    
    def test_no_provider(self):
        """Test when no LLM provider is configured."""
        settings = Settings(
            azure_openai_api_key=None,
            azure_openai_endpoint=None
        )
        
        assert settings.has_azure_openai is False
        assert settings.llm_provider == "none"
    
    def test_ensure_directories(self, tmp_path):
        """Test directory creation."""
        settings = Settings(data_dir=tmp_path / "data")
        settings.ensure_directories()
        
        assert settings.data_dir.exists()
        assert settings.index_dir.exists()
        assert settings.ppts_dir.exists()
        assert settings.thumbnails_dir.exists()


class TestGetSettings:
    """Tests for get_settings function."""
    
    def test_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)
    
    def test_cached_instance(self):
        """Test that get_settings returns the same cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
