"""
Unit tests for the Slide Assistant Service.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pydantic import ValidationError

from src.services.slide_assistant.models import (
    ChatMessage,
    ChatResponse,
    ReferencedSlide,
    ChatRequest,
)
from src.services.slide_assistant.service import SlideAssistantService, ChatResponseOutput, SlideReference


class TestAgentFrameworkIntegration:
    """Tests for Agent Framework Service integration to prevent regressions."""
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_user_message_returns_string(self, mock_get_settings):
        """Test that _build_user_message returns a properly formatted string."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        history = [
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
        ]
        
        result = service._build_user_message(
            context="Test context",
            message="Current message",
            history=history,
        )
        
        # Verify result is a string
        assert isinstance(result, str)
        
        # Verify context is included
        assert "Test context" in result
        
        # Verify current message is included
        assert "Current message" in result
        
        # Verify history is included
        assert "First question" in result
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_user_message_with_empty_history(self, mock_get_settings):
        """Test message building with no history."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        result = service._build_user_message(
            context="Test context",
            message="Current message",
            history=[],
        )
        
        assert isinstance(result, str)
        assert "Test context" in result
        assert "Current message" in result
        # Should not have "Previous conversation" section
        assert "Previous conversation" not in result
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_user_message_limits_history(self, mock_get_settings):
        """Test that history is limited to last 6 messages."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create 10 history messages
        history = [
            ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
            for i in range(10)
        ]
        
        result = service._build_user_message(
            context="Test context",
            message="Current message",
            history=history,
        )
        
        # First 4 messages should NOT be included (only last 6)
        assert "Message 0" not in result
        assert "Message 1" not in result
        assert "Message 2" not in result
        assert "Message 3" not in result
        
        # Last 6 messages SHOULD be included
        assert "Message 4" in result
        assert "Message 9" in result
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_parse_structured_response_with_value(self, mock_get_settings):
        """Test processing a valid structured output response."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create mock response with structured output value
        mock_output = ChatResponseOutput(
            answer="Here are some slides about Azure",
            referenced_slides=[
                SlideReference(
                    slide_id="BRK108_5",
                    session_code="BRK108",
                    slide_number=5,
                    title="Azure Functions",
                    content="Content about Azure Functions",
                    event="Build",
                    session_url="https://example.com",
                    ppt_url="https://example.com/ppt",
                    relevance_reason="Covers Azure Functions in depth"
                )
            ],
            follow_up_suggestions=["Show me more about triggers"]
        )
        
        mock_response = Mock()
        mock_response.value = mock_output
        mock_response.text = None
        
        result = service._parse_structured_response(mock_response)
        
        assert result.answer == "Here are some slides about Azure"
        assert len(result.referenced_slides) == 1
        assert result.referenced_slides[0].slide_id == "BRK108_5"
        assert result.follow_up_suggestions == ["Show me more about triggers"]
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_parse_structured_response_fallback_to_json(self, mock_get_settings):
        """Test fallback to JSON parsing when no value is present."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create mock response with JSON text
        mock_response = Mock()
        mock_response.value = None
        mock_response.text = json.dumps({
            "answer": "Fallback JSON response",
            "referenced_slides": [],
            "follow_up_suggestions": ["Try another search"]
        })
        
        result = service._parse_structured_response(mock_response)
        
        assert result.answer == "Fallback JSON response"
        assert result.referenced_slides == []
        assert result.follow_up_suggestions == ["Try another search"]
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_parse_structured_response_fallback_to_text(self, mock_get_settings):
        """Test fallback when response is plain text."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create mock response with plain text
        mock_response = Mock()
        mock_response.value = None
        mock_response.text = "Plain text fallback response"
        
        result = service._parse_structured_response(mock_response)
        
        assert result.answer == "Plain text fallback response"
        assert result.referenced_slides == []
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_parse_structured_response_no_output_raises(self, mock_get_settings):
        """Test that missing output raises ValueError."""
        settings = Mock()
        settings.has_foundry_agent = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create mock response with no value and no text
        mock_response = Mock()
        mock_response.value = None
        mock_response.text = None
        
        with pytest.raises(ValueError):
            service._parse_structured_response(mock_response)


class TestChatResponseModel:
    """Tests for the ChatResponse Pydantic model."""
    
    def test_minimal_response(self):
        """Test ChatResponse with only required fields."""
        response = ChatResponse(answer="Hello, I found some slides.")
        assert response.answer == "Hello, I found some slides."
        assert response.referenced_slides == []
        assert response.follow_up_suggestions == []
    
    def test_full_response(self):
        """Test ChatResponse with all fields populated."""
        slide = ReferencedSlide(
            slide_id="BRK108_5",
            session_code="BRK108",
            slide_number=5,
            title="Azure Functions Overview",
            content="Content about Azure Functions...",
            event="Build",
            relevance_reason="Directly covers Azure Functions.",
        )
        response = ChatResponse(
            answer="Here's what I found.",
            referenced_slides=[slide],
            follow_up_suggestions=["Want to know more about triggers?"],
        )
        assert len(response.referenced_slides) == 1
        assert response.referenced_slides[0].session_code == "BRK108"


class TestReferencedSlideModel:
    """Tests for the ReferencedSlide Pydantic model."""
    
    def test_slide_with_thumbnail(self):
        """Test slide with thumbnail URL."""
        slide = ReferencedSlide(
            slide_id="BRK108_5",
            session_code="BRK108",
            slide_number=5,
            title="Test Slide",
            content="Test content",
            event="Build",
            relevance_reason="Relevant because...",
            thumbnail_url="/thumbnails/BRK108_5.png",
        )
        assert slide.thumbnail_url == "/thumbnails/BRK108_5.png"
    
    def test_slide_without_thumbnail(self):
        """Test slide without thumbnail URL defaults to None."""
        slide = ReferencedSlide(
            slide_id="BRK108_5",
            session_code="BRK108",
            slide_number=5,
            title="Test Slide",
            content="Test content",
            event="Build",
            relevance_reason="Relevant because...",
        )
        assert slide.thumbnail_url is None


class TestChatMessageModel:
    """Tests for the ChatMessage model."""
    
    def test_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage(role="user", content="Find slides about AI")
        assert msg.role == "user"
        assert msg.content == "Find slides about AI"
    
    def test_assistant_message(self):
        """Test creating an assistant message."""
        msg = ChatMessage(role="assistant", content="Here are some slides...")
        assert msg.role == "assistant"


class TestChatRequestModel:
    """Tests for the ChatRequest model."""
    
    def test_simple_request(self):
        """Test request with just a message."""
        request = ChatRequest(message="Find AI slides")
        assert request.message == "Find AI slides"
        assert request.history == []
    
    def test_request_with_history(self):
        """Test request with conversation history."""
        history = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help?"),
        ]
        request = ChatRequest(message="Find AI slides", history=history)
        assert len(request.history) == 2


class TestSlideAssistantService:
    """Tests for the SlideAssistantService class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.has_foundry_agent = True
        settings.azure_ai_project_endpoint = "https://test.ai.azure.com/api/projects/test"
        settings.azure_ai_foundry_agent_name = "SlideAssistantAgent"
        settings.azure_openai_nano_deployment = "gpt-4.1-nano"
        return settings
    
    @pytest.fixture
    def mock_search_results(self):
        """Create mock search results."""
        return [
            {
                "slide_id": "BRK108_5",
                "session_code": "BRK108",
                "slide_number": 5,
                "title": "Azure Functions Overview",
                "content": "This slide covers Azure Functions...",
                "event": "Build",
                "session_url": "https://example.com/session",
                "ppt_url": "https://example.com/ppt",
                "score": 0.95,
                "thumbnail_url": "/thumbnails/BRK108_5.png",
            },
            {
                "slide_id": "BRK200_10",
                "session_code": "BRK200",
                "slide_number": 10,
                "title": "Serverless Patterns",
                "content": "Serverless architecture patterns...",
                "event": "Ignite",
                "session_url": "https://example.com/session2",
                "ppt_url": "https://example.com/ppt2",
                "score": 0.88,
                "thumbnail_url": "/thumbnails/BRK200_10.png",
            },
        ]
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_is_available_true(self, mock_get_settings, mock_settings):
        """Test service availability when Foundry is configured."""
        mock_get_settings.return_value = mock_settings
        service = SlideAssistantService()
        assert service.is_available is True
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_is_available_false(self, mock_get_settings):
        """Test service unavailability when Foundry is not configured."""
        settings = Mock()
        settings.has_foundry_agent = False
        mock_get_settings.return_value = settings
        service = SlideAssistantService()
        assert service.is_available is False
    
    @pytest.mark.asyncio
    @patch("src.services.slide_assistant.service.get_settings")
    async def test_chat_unavailable_returns_error(self, mock_get_settings):
        """Test chat returns error when service unavailable."""
        settings = Mock()
        settings.has_foundry_agent = False
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        response = await service.chat("Find slides about AI")
        
        assert "not available" in response.answer.lower()
        assert response.referenced_slides == []
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_enrich_slides_with_thumbnails(self, mock_get_settings, mock_settings, mock_search_results):
        """Test thumbnail enrichment for referenced slides."""
        mock_get_settings.return_value = mock_settings
        service = SlideAssistantService()
        
        slides = [
            ReferencedSlide(
                slide_id="BRK108_5",
                session_code="BRK108",
                slide_number=5,
                title="Test",
                content="Content",
                event="Build",
                relevance_reason="Relevant",
            ),
        ]
        
        enriched = service._enrich_slides_with_thumbnails(slides, mock_search_results)
        
        assert len(enriched) == 1
        assert enriched[0].thumbnail_url == "/thumbnails/BRK108_5.png"
        assert enriched[0].ppt_url == "https://example.com/ppt"
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_error_response_format(self, mock_get_settings, mock_settings):
        """Test error response has correct structure."""
        mock_get_settings.return_value = mock_settings
        service = SlideAssistantService()
        
        response = service._error_response("Test error message")
        
        assert response.answer == "Test error message"
        assert response.referenced_slides == []
        assert len(response.follow_up_suggestions) == 2


class TestSlideAssistantServiceIntegration:
    """Integration-style tests with mocked external dependencies."""
    
    @pytest.mark.asyncio
    @patch("src.services.slide_assistant.service.get_search_service")
    @patch("src.services.slide_assistant.service.get_settings")
    async def test_chat_success(
        self,
        mock_get_settings,
        mock_get_search_service,
    ):
        """Test successful chat with mocked dependencies."""
        # Setup settings
        settings = Mock()
        settings.has_foundry_agent = True
        settings.azure_ai_project_endpoint = "https://test.ai.azure.com/api/projects/test"
        settings.azure_ai_foundry_agent_name = "SlideAssistantAgent"
        settings.azure_openai_nano_deployment = "gpt-4.1-nano"
        mock_get_settings.return_value = settings
        
        # Setup search service
        mock_result = Mock()
        mock_result.slide_id = "BRK108_5"
        mock_result.session_code = "BRK108"
        mock_result.slide_number = 5
        mock_result.title = "Azure Functions"
        mock_result.content = "Content..."
        mock_result.event = "Build"
        mock_result.session_url = "https://example.com"
        mock_result.ppt_url = "https://example.com/ppt"
        mock_result.score = 0.95
        mock_result.has_thumbnail = True
        
        search_service = Mock()
        search_service.search.return_value = ([mock_result], 1, None)
        mock_get_search_service.return_value = search_service
        
        # Create service
        service = SlideAssistantService()
        
        # Mock the Agent Framework response with structured output
        mock_structured_output = ChatResponseOutput(
            answer="I found some great slides about Azure Functions!",
            referenced_slides=[
                SlideReference(
                    slide_id="BRK108_5",
                    session_code="BRK108",
                    slide_number=5,
                    title="Azure Functions Overview",
                    content="Content about serverless...",
                    event="Build",
                    session_url="https://example.com",
                    ppt_url="https://example.com/ppt",
                    relevance_reason="Covers Azure Functions in depth."
                )
            ],
            follow_up_suggestions=["Want to see more about triggers?"]
        )
        
        mock_agent_response = Mock()
        mock_agent_response.value = mock_structured_output
        mock_agent_response.text = None
        
        # Create mock agent
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_response)
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(return_value=None)
        
        # Inject mocked agent
        service._agent = mock_agent
        
        # Execute
        response = await service.chat("Find slides about Azure Functions")
        
        # Verify
        assert "Azure Functions" in response.answer
        assert len(response.referenced_slides) == 1
        assert response.referenced_slides[0].slide_id == "BRK108_5"
        # Verify thumbnail was enriched
        assert response.referenced_slides[0].thumbnail_url == "/thumbnails/BRK108_5.png"
