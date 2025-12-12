"""
Unit tests for the Slide Assistant Service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pydantic import ValidationError

from src.services.slide_assistant.models import (
    ChatMessage,
    ChatResponse,
    ReferencedSlide,
    ChatRequest,
)
from src.services.slide_assistant.service import SlideAssistantService


class TestAgentFrameworkIntegration:
    """Tests for agent framework integration to prevent regressions."""
    
    def test_role_enum_has_required_attributes(self):
        """Verify the Role enum has the attributes we use."""
        from agent_framework import Role
        
        # These are the Role values we use in the service
        assert hasattr(Role, 'USER'), "Role.USER is required"
        assert hasattr(Role, 'ASSISTANT'), "Role.ASSISTANT is required"
        
        # Verify they are valid enum members
        assert Role.USER is not None
        assert Role.ASSISTANT is not None
    
    def test_chat_message_creation(self):
        """Test that ChatMessage can be created with Role enum."""
        from agent_framework import ChatMessage as AgentChatMessage, Role
        
        # Test USER role
        user_msg = AgentChatMessage(role=Role.USER, text="Hello")
        assert user_msg.role == Role.USER
        assert user_msg.text == "Hello"
        
        # Test ASSISTANT role
        assistant_msg = AgentChatMessage(role=Role.ASSISTANT, text="Hi there")
        assert assistant_msg.role == Role.ASSISTANT
        assert assistant_msg.text == "Hi there"
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_messages_uses_correct_roles(self, mock_get_settings):
        """Test that _build_messages uses correct Role enum values."""
        from agent_framework import Role
        
        settings = Mock()
        settings.has_azure_openai = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        history = [
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
        ]
        
        messages = service._build_messages(
            context="Test context",
            message="Current message",
            history=history,
        )
        
        # Verify message count: context + 3 history + current = 5
        assert len(messages) == 5
        
        # Verify roles are correctly mapped
        assert messages[0].role == Role.USER  # Context
        assert messages[1].role == Role.USER  # First user message
        assert messages[2].role == Role.ASSISTANT  # Assistant response
        assert messages[3].role == Role.USER  # Second user message  
        assert messages[4].role == Role.USER  # Current message
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_messages_with_empty_history(self, mock_get_settings):
        """Test message building with no history."""
        from agent_framework import Role
        
        settings = Mock()
        settings.has_azure_openai = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        messages = service._build_messages(
            context="Test context",
            message="Current message",
            history=[],
        )
        
        # Should have context + current message = 2
        assert len(messages) == 2
        assert messages[0].role == Role.USER
        assert messages[1].role == Role.USER
        assert "Test context" in messages[0].text
        assert messages[1].text == "Current message"
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_build_messages_limits_history(self, mock_get_settings):
        """Test that history is limited to last 6 messages."""
        settings = Mock()
        settings.has_azure_openai = True
        mock_get_settings.return_value = settings
        
        service = SlideAssistantService()
        
        # Create 10 history messages
        history = [
            ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
            for i in range(10)
        ]
        
        messages = service._build_messages(
            context="Test context",
            message="Current message",
            history=history,
        )
        
        # Should have context + last 6 history + current = 8
        assert len(messages) == 8


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
        settings.has_azure_openai = True
        settings.azure_openai_api_key = "test-key"
        settings.azure_openai_api_version = "2024-02-01"
        settings.azure_openai_endpoint = "https://test.openai.azure.com"
        settings.azure_openai_deployment = "gpt-4o"
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
                "score": 0.88,
                "thumbnail_url": "/thumbnails/BRK200_10.png",
            },
        ]
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_is_available_true(self, mock_get_settings, mock_settings):
        """Test service availability when OpenAI is configured."""
        mock_get_settings.return_value = mock_settings
        service = SlideAssistantService()
        assert service.is_available is True
    
    @patch("src.services.slide_assistant.service.get_settings")
    def test_is_available_false(self, mock_get_settings):
        """Test service unavailability when OpenAI is not configured."""
        settings = Mock()
        settings.has_azure_openai = False
        mock_get_settings.return_value = settings
        service = SlideAssistantService()
        assert service.is_available is False
    
    @pytest.mark.asyncio
    @patch("src.services.slide_assistant.service.get_settings")
    async def test_chat_unavailable_returns_error(self, mock_get_settings):
        """Test chat returns error when service unavailable."""
        settings = Mock()
        settings.has_azure_openai = False
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
    
    @pytest.fixture
    def mock_agent_response(self):
        """Create a mock agent framework response."""
        return ChatResponse(
            answer="I found some great slides about Azure Functions!",
            referenced_slides=[
                ReferencedSlide(
                    slide_id="BRK108_5",
                    session_code="BRK108",
                    slide_number=5,
                    title="Azure Functions Overview",
                    content="Content about serverless...",
                    event="Build",
                    relevance_reason="Covers Azure Functions in depth.",
                )
            ],
            follow_up_suggestions=["Want to see more about triggers?"],
        )
    
    @pytest.mark.asyncio
    @patch("src.services.slide_assistant.service.get_search_service")
    @patch("src.services.slide_assistant.service.get_settings")
    async def test_chat_success(
        self,
        mock_get_settings,
        mock_get_search_service,
        mock_agent_response,
    ):
        """Test successful chat with mocked dependencies."""
        from unittest.mock import AsyncMock
        
        # Setup settings
        settings = Mock()
        settings.has_azure_openai = True
        settings.azure_openai_api_key = "test-key"
        settings.azure_openai_api_version = "2024-02-01"
        settings.azure_openai_endpoint = "https://test.openai.azure.com"
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
        
        # Create service with mocked agent
        service = SlideAssistantService()
        
        # Mock the agent response
        mock_response = Mock()
        mock_response.value = mock_agent_response
        
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_response
        
        mock_client = Mock()
        mock_client.create_agent.return_value = mock_agent
        
        service._chat_client = mock_client
        service._assistant_agent = mock_agent
        
        # Execute
        response = await service.chat("Find slides about Azure Functions")
        
        # Verify
        assert "Azure Functions" in response.answer
        assert len(response.referenced_slides) == 1
        assert response.referenced_slides[0].slide_id == "BRK108_5"
        # Verify thumbnail was enriched
        assert response.referenced_slides[0].thumbnail_url == "/thumbnails/BRK108_5.png"
