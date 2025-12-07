"""Unit tests for deck builder service."""

import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestDeckBuilderWorkflow:
    """Tests for DeckBuilderService workflow."""
    
    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = Mock()
        settings.azure_openai_endpoint = "https://test.openai.azure.com"
        settings.azure_openai_deployment = "gpt-4"
        settings.azure_openai_api_key = "test-key"
        settings.azure_openai_api_version = "2024-10-21"
        settings.data_dir = tmp_path / "data"
        settings.ppts_dir = tmp_path / "ppts"
        settings.thumbnails_dir = tmp_path / "thumbnails"
        settings.compiled_decks_dir = tmp_path / "compiled_decks"
        return settings
    
    @pytest.fixture
    def mock_search_service(self):
        """Create mock search service."""
        mock = Mock()
        mock.search.return_value = ([], 0.0)
        mock.get_available_pptx_sessions.return_value = set()
        return mock
    
    def test_service_initialization(self, mock_settings, mock_search_service):
        """Test that the service initializes correctly."""
        with patch("services.deck_builder.service.get_settings", return_value=mock_settings), \
             patch("services.deck_builder.service.get_search_service", return_value=mock_search_service), \
             patch("services.deck_builder.agents.get_search_service", return_value=mock_search_service), \
             patch("services.deck_builder.agents.DefaultAzureCredential"), \
             patch("services.deck_builder.agents.AzureOpenAIChatClient"):
            
            from services.deck_builder import DeckBuilderService
            
            service = DeckBuilderService()
            assert service is not None


class TestPydanticModels:
    """Tests for Pydantic models."""
    
    def test_slide_outline_item(self):
        """Test SlideOutlineItem model."""
        from services.deck_builder.models import SlideOutlineItem
        
        item = SlideOutlineItem(
            position=1,
            topic="Introduction",
            search_hints=["intro", "overview"],
            purpose="Set the stage"
        )
        
        assert item.position == 1
        assert item.topic == "Introduction"
        assert len(item.search_hints) == 2
        assert item.purpose == "Set the stage"
    
    def test_presentation_outline(self):
        """Test PresentationOutline model."""
        from services.deck_builder.models import PresentationOutline, SlideOutlineItem
        
        outline = PresentationOutline(
            title="Test Presentation",
            narrative="A test narrative",
            slides=[
                SlideOutlineItem(position=1, topic="Intro", search_hints=[], purpose="Start")
            ]
        )
        
        assert outline.title == "Test Presentation"
        assert len(outline.slides) == 1
    
    def test_critique_result(self):
        """Test CritiqueResult model."""
        from services.deck_builder.models import CritiqueResult
        
        result = CritiqueResult(
            approved=True,
            feedback="Looks good",
            issues=[],
            search_suggestion=None
        )
        
        assert result.approved is True
        assert result.feedback == "Looks good"


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_format_slides_summary(self):
        """Test format_slides_summary function."""
        from services.deck_builder.helpers import format_slides_summary
        
        slides = [
            {"session_code": "TEST1", "slide_number": 1, "title": "Test", "content": "Content"}
        ]
        
        result = format_slides_summary(slides)
        assert "TEST1" in result
        assert "#1" in result
    
    def test_format_slides_summary_with_limit(self):
        """Test format_slides_summary respects max_slides limit."""
        from services.deck_builder.helpers import format_slides_summary
        
        slides = [
            {"session_code": f"TEST{i}", "slide_number": i, "title": f"Test {i}", "content": "Content"}
            for i in range(30)
        ]
        
        result = format_slides_summary(slides, max_slides=5)
        assert "TEST0" in result
        assert "TEST4" in result
        assert "TEST5" not in result
    
    def test_format_candidates(self):
        """Test format_candidates function."""
        from services.deck_builder.helpers import format_candidates
        
        candidates = [
            {"session_code": "TEST1", "slide_number": 1, "title": "Test", "content": "Content"}
        ]
        
        result = format_candidates(candidates)
        assert "TEST1" in result
        assert "Slide 1" in result
    
    def test_format_candidates_with_session_title(self):
        """Test format_candidates includes session title when present."""
        from services.deck_builder.helpers import format_candidates
        
        candidates = [
            {
                "session_code": "TEST1", 
                "slide_number": 1, 
                "title": "Slide Title", 
                "content": "Content",
                "session_title": "Session: Introduction to Testing"
            }
        ]
        
        result = format_candidates(candidates)
        assert "Session: Introduction to Testing" in result
    
    def test_compute_source_decks(self):
        """Test compute_source_decks function."""
        from services.deck_builder.helpers import compute_source_decks
        
        deck = [
            {"session_code": "TEST1", "slide_number": 1},
            {"session_code": "TEST1", "slide_number": 2},
            {"session_code": "TEST2", "slide_number": 5}
        ]
        
        all_slides = [
            {"session_code": "TEST1", "session_title": "Test Session 1", "ppt_url": "url1"},
            {"session_code": "TEST2", "session_title": "Test Session 2", "ppt_url": "url2"}
        ]
        
        result = compute_source_decks(deck, all_slides)
        
        assert len(result) == 2
        session_codes = {r["session_code"] for r in result}
        assert "TEST1" in session_codes
        assert "TEST2" in session_codes
    
    def test_compute_source_decks_tracks_slides_used(self):
        """Test compute_source_decks tracks which slides are used."""
        from services.deck_builder.helpers import compute_source_decks
        
        deck = [
            {"session_code": "TEST1", "slide_number": 1},
            {"session_code": "TEST1", "slide_number": 3},
        ]
        
        all_slides = [
            {"session_code": "TEST1", "session_title": "Test", "ppt_url": "url1"},
        ]
        
        result = compute_source_decks(deck, all_slides)
        
        assert len(result) == 1
        assert 1 in result[0]["slides_used"]
        assert 3 in result[0]["slides_used"]
    
    def test_load_slide_thumbnail_not_exists(self, tmp_path):
        """Test load_slide_thumbnail returns None when file doesn't exist."""
        from services.deck_builder.helpers import load_slide_thumbnail
        from unittest.mock import patch, Mock
        
        mock_settings = Mock()
        mock_settings.thumbnails_dir = tmp_path / "thumbnails"
        mock_settings.thumbnails_dir.mkdir()
        
        with patch("services.deck_builder.helpers.get_settings", return_value=mock_settings):
            result = load_slide_thumbnail("NONEXISTENT", 1)
        
        assert result is None
    
    def test_load_slide_thumbnail_exists(self, tmp_path):
        """Test load_slide_thumbnail returns bytes when file exists."""
        from services.deck_builder.helpers import load_slide_thumbnail
        from unittest.mock import patch, Mock
        
        mock_settings = Mock()
        mock_settings.thumbnails_dir = tmp_path / "thumbnails"
        mock_settings.thumbnails_dir.mkdir()
        
        # Create a test thumbnail
        thumb_path = mock_settings.thumbnails_dir / "TEST1_1.png"
        thumb_path.write_bytes(b"fake png data")
        
        with patch("services.deck_builder.helpers.get_settings", return_value=mock_settings):
            result = load_slide_thumbnail("TEST1", 1)
        
        assert result == b"fake png data"


class TestAgentFrameworkIntegration:
    """Tests for agent framework message format."""
    
    def test_chat_message_has_contents_attribute(self):
        """Test that ChatMessage objects have contents attribute."""
        from agent_framework import ChatMessage
        
        msg = ChatMessage(role='user', text='Hello world')
        
        assert hasattr(msg, 'contents')
        assert msg.contents is not None
        assert len(msg.contents) > 0
    
    def test_chat_message_has_text_property(self):
        """Test that ChatMessage has text property."""
        from agent_framework import ChatMessage
        
        msg = ChatMessage(role='user', text='Hello world')
        
        assert hasattr(msg, 'text')
        assert msg.text == 'Hello world'


class TestSlideSelectionModel:
    """Tests for SlideSelection Pydantic model."""
    
    def test_slide_selection(self):
        """Test SlideSelection model creation."""
        from services.deck_builder.models import SlideSelection
        
        selection = SlideSelection(
            session_code="BRK211",
            slide_number=5,
            reason="Best match for introduction topic"
        )
        
        assert selection.session_code == "BRK211"
        assert selection.slide_number == 5
        assert selection.reason == "Best match for introduction topic"
    
    def test_slide_selection_minimal(self):
        """Test SlideSelection with minimal data."""
        from services.deck_builder.models import SlideSelection
        
        selection = SlideSelection(
            session_code="TEST",
            slide_number=1,
            reason=""
        )
        
        assert selection.session_code == "TEST"


class TestBuildMultimodalMessage:
    """Tests for build_multimodal_message helper."""
    
    def test_build_multimodal_message_text_only(self):
        """Test building a message with text only."""
        from services.deck_builder.helpers import build_multimodal_message
        
        msg = build_multimodal_message("Hello world", [], include_images=False)
        
        assert msg is not None
        assert len(msg.contents) == 1
    
    def test_build_multimodal_message_with_slides_no_images(self):
        """Test building a message with slides but no image loading."""
        from services.deck_builder.helpers import build_multimodal_message
        
        slides = [
            {"session_code": "TEST1", "slide_number": 1}
        ]
        
        msg = build_multimodal_message("Test prompt", slides, include_images=False)
        
        assert msg is not None
        # Should only have text content when include_images is False
        assert len(msg.contents) == 1
