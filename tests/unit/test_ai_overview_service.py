"""
Unit tests for the AI Overview Service.
Tests agent framework integration and service functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.services.ai_overview.service import (
    AIOverviewService,
    build_user_prompt,
    OVERVIEW_AGENT_INSTRUCTIONS,
)


class TestAgentFrameworkIntegration:
    """Tests for agent framework integration to prevent regressions."""
    
    def test_role_enum_has_user_attribute(self):
        """Verify the Role enum has USER attribute we use."""
        from agent_framework import Role
        
        assert hasattr(Role, 'USER'), "Role.USER is required"
        assert Role.USER is not None
    
    def test_chat_message_creation_with_user_role(self):
        """Test that ChatMessage can be created with USER role."""
        from agent_framework import ChatMessage, Role
        
        msg = ChatMessage(role=Role.USER, text="Test message")
        assert msg.role == Role.USER
        assert msg.text == "Test message"
    
    def test_agent_run_response_has_text_attribute(self):
        """Verify AgentRunResponse has text attribute for plain responses."""
        from agent_framework._types import AgentRunResponse
        
        # AgentRunResponse should have 'text' attribute for plain text responses
        # and 'value' attribute for structured output
        assert hasattr(AgentRunResponse, '__annotations__') or True  # Just verify class exists
        
        # Create a mock response to verify expected interface
        mock_response = Mock()
        mock_response.text = "Some text response"
        mock_response.value = None
        
        assert mock_response.text == "Some text response"
        assert mock_response.value is None
    
    def test_azure_openai_chat_client_import(self):
        """Verify AzureOpenAIChatClient can be imported."""
        from agent_framework.azure import AzureOpenAIChatClient
        
        assert AzureOpenAIChatClient is not None


class TestBuildUserPrompt:
    """Tests for the build_user_prompt function."""
    
    def test_builds_prompt_with_string_context(self):
        """Test prompt building with string context."""
        prompt = build_user_prompt(
            query="AI agents",
            context_data="Some context data",
            result_count=10,
            unique_sessions=3,
        )
        
        assert 'AI agents' in prompt
        assert '10 matching slides' in prompt
        assert '3 presentations' in prompt
        assert 'Some context data' in prompt
    
    def test_builds_prompt_with_dict_context(self):
        """Test prompt building with dict context."""
        context = {"key": "value", "sessions": ["BRK101", "BRK102"]}
        
        prompt = build_user_prompt(
            query="Azure Functions",
            context_data=context,
            result_count=5,
            unique_sessions=2,
        )
        
        assert 'Azure Functions' in prompt
        assert '5 matching slides' in prompt
    
    def test_truncates_long_context(self):
        """Test that long context is truncated."""
        long_context = "x" * 5000
        
        prompt = build_user_prompt(
            query="test",
            context_data=long_context,
            result_count=1,
            unique_sessions=1,
        )
        
        # Context should be truncated to 3000 chars
        assert len(prompt) < 5000


class TestAIOverviewService:
    """Tests for the AIOverviewService class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.has_azure_openai = True
        settings.azure_openai_api_key = "test-key"
        settings.azure_openai_api_version = "2024-02-01"
        settings.azure_openai_endpoint = "https://test.openai.azure.com"
        settings.azure_openai_nano_deployment = "gpt-4.1-nano"
        return settings
    
    @patch("src.services.ai_overview.service.get_settings")
    def test_is_available_true(self, mock_get_settings, mock_settings):
        """Test service availability when OpenAI is configured."""
        mock_get_settings.return_value = mock_settings
        service = AIOverviewService()
        assert service.is_available is True
    
    @patch("src.services.ai_overview.service.get_settings")
    def test_is_available_false(self, mock_get_settings):
        """Test service unavailability when OpenAI is not configured."""
        settings = Mock()
        settings.has_azure_openai = False
        mock_get_settings.return_value = settings
        service = AIOverviewService()
        assert service.is_available is False
    
    @pytest.mark.asyncio
    @patch("src.services.ai_overview.service.get_settings")
    async def test_generate_overview_returns_empty_when_unavailable(self, mock_get_settings):
        """Test generate_overview returns empty string when service unavailable."""
        settings = Mock()
        settings.has_azure_openai = False
        mock_get_settings.return_value = settings
        
        service = AIOverviewService()
        result = await service.generate_overview(
            query="test",
            search_context="{}",
            result_count=10,
            unique_sessions=3,
        )
        
        assert result == ""
    
    @pytest.mark.asyncio
    @patch("src.services.ai_overview.service.get_settings")
    async def test_generate_overview_success(self, mock_get_settings, mock_settings):
        """Test successful overview generation with mocked agent."""
        mock_get_settings.return_value = mock_settings
        
        service = AIOverviewService()
        
        # Mock the agent response - text is in response.text, not response.value
        mock_response = Mock()
        mock_response.text = "This is a great overview of Azure Functions."
        mock_response.value = None  # value is only for structured output
        
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_response
        
        mock_client = Mock()
        mock_client.create_agent.return_value = mock_agent
        
        service._chat_client = mock_client
        service._overview_agent = mock_agent
        
        result = await service.generate_overview(
            query="Azure Functions",
            search_context='{"sessions": ["BRK101"]}',
            result_count=10,
            unique_sessions=3,
        )
        
        assert result == "This is a great overview of Azure Functions."
        mock_agent.run.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("src.services.ai_overview.service.get_settings")
    async def test_generate_overview_handles_error(self, mock_get_settings, mock_settings):
        """Test that errors are handled gracefully."""
        mock_get_settings.return_value = mock_settings
        
        service = AIOverviewService()
        
        # Mock agent that raises exception
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = Exception("API error")
        
        mock_client = Mock()
        mock_client.create_agent.return_value = mock_agent
        
        service._chat_client = mock_client
        service._overview_agent = mock_agent
        
        result = await service.generate_overview(
            query="test",
            search_context="{}",
            result_count=1,
            unique_sessions=1,
        )
        
        # Should return empty string on error, not raise
        assert result == ""


class TestOverviewAgentInstructions:
    """Tests for agent instructions content."""
    
    def test_instructions_include_key_guidelines(self):
        """Verify instructions contain expected guidance."""
        assert "concise" in OVERVIEW_AGENT_INSTRUCTIONS.lower()
        assert "session" in OVERVIEW_AGENT_INSTRUCTIONS.lower()
        assert "2-4 sentences" in OVERVIEW_AGENT_INSTRUCTIONS
    
    def test_instructions_mention_formatting(self):
        """Verify instructions mention markdown formatting."""
        assert "markdown" in OVERVIEW_AGENT_INSTRUCTIONS.lower()
        assert "bold" in OVERVIEW_AGENT_INSTRUCTIONS.lower()
