"""
Unit tests for Pydantic models.
"""
import pytest

from src.models.slide import SlideInfo, SlideSearchResult
from src.models.deck import DeckSession


class TestSlideInfo:
    """Tests for SlideInfo model."""
    
    def test_complete_info(self):
        """Test creating complete slide info."""
        info = SlideInfo(
            slide_id="BRK211_5",
            session_code="BRK211",
            slide_number=5,
            title="Introduction to Azure",
            content="Azure overview content",
            event="Build",
            session_url="https://example.com/session",
            ppt_url="https://example.com/ppt.pptx"
        )
        
        assert info.slide_id == "BRK211_5"
        assert info.title == "Introduction to Azure"
        assert info.event == "Build"


class TestSlideSearchResult:
    """Tests for SlideSearchResult model."""
    
    def test_thumbnail_filename(self):
        """Test thumbnail filename generation."""
        result = SlideSearchResult(
            slide_id="BRK211_5",
            session_code="BRK211",
            title="Test",
            slide_number=5,
        )
        
        assert result.thumbnail_filename == "BRK211_5.png"
    
    def test_default_values(self):
        """Test default values are set correctly."""
        result = SlideSearchResult(
            slide_id="BRK211_5",
            session_code="BRK211",
            title="Test",
            slide_number=5,
        )
        
        assert result.content == ""
        assert result.snippet == ""
        assert result.has_thumbnail is False
        assert result.has_pptx is False
        assert result.score == 0.0
    
    def test_full_search_result(self):
        """Test creating a complete search result."""
        result = SlideSearchResult(
            slide_id="BRK211_5",
            session_code="BRK211",
            title="Azure AI Introduction",
            slide_number=5,
            content="Full content of the slide",
            snippet="<b>Azure</b> AI Introduction",
            event="Build",
            session_url="https://example.com/session",
            ppt_url="https://example.com/ppt.pptx",
            has_thumbnail=True,
            has_pptx=True,
            score=0.95
        )
        
        assert result.has_thumbnail is True
        assert result.has_pptx is True
        assert result.score == 0.95


class TestDeckSession:
    """Tests for DeckSession dataclass."""
    
    def test_initialization(self):
        """Test session initialization."""
        session = DeckSession(session_id="test-123")
        
        assert session.session_id == "test-123"
        assert session.messages == []
        assert session.compiled_deck == []
        assert session.status == "pending"
    
    def test_add_message(self):
        """Test adding messages."""
        session = DeckSession(session_id="test")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["content"] == "Hi there!"
    
    def test_add_search_results(self):
        """Test adding search results."""
        session = DeckSession(session_id="test")
        results = [{"slide_id": "BRK211_1"}, {"slide_id": "BRK211_2"}]
        
        session.add_search_results(results)
        
        assert len(session.all_searched_slides) == 2
        assert session.search_count == 1
    
    def test_compile(self):
        """Test compiling a deck."""
        session = DeckSession(session_id="test")
        slides = [{"session_code": "BRK211", "slide_number": 1}]
        
        session.compile(slides, "Introduction flow")
        
        assert session.compiled_deck == slides
        assert session.flow_explanation == "Introduction flow"
        assert session.has_compiled is True
        assert session.status == "complete"
    
    def test_reset_turn_state(self):
        """Test resetting turn state."""
        session = DeckSession(session_id="test")
        session.search_count = 5
        session.has_compiled = True
        
        session.reset_turn_state()
        
        assert session.search_count == 0
        assert session.has_compiled is False
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        session = DeckSession(session_id="test-123")
        session.add_message("user", "Hello")
        session.compile([{"session_code": "BRK211", "slide_number": 1}], "Test")
        
        result = session.to_dict()
        
        assert result["session_id"] == "test-123"
        assert result["message_count"] == 1
        assert result["slide_count"] == 1
        assert result["status"] == "complete"


class TestAPIRequestModels:
    """Tests for API request models (defined in api modules)."""
    
    def test_chat_request_valid(self):
        """Test valid chat request."""
        from src.api.routes.deck_builder import ChatRequest
        
        request = ChatRequest(message="Build a deck about AI")
        
        assert request.message == "Build a deck about AI"
        assert request.session_id is None
    
    def test_chat_request_with_session(self):
        """Test chat request with session ID."""
        from src.api.routes.deck_builder import ChatRequest
        
        request = ChatRequest(
            message="Add more slides",
            session_id="abc-123"
        )
        
        assert request.session_id == "abc-123"
    
    def test_chat_request_validation(self):
        """Test chat request validation."""
        from src.api.routes.deck_builder import ChatRequest
        
        with pytest.raises(ValueError):
            ChatRequest(message="")  # Too short
    
    def test_outline_slide_item(self):
        """Test OutlineSlideItem model."""
        from src.api.routes.deck_builder import OutlineSlideItem
        
        item = OutlineSlideItem(
            position=1,
            topic="Introduction",
            search_hints=["intro", "overview"],
            purpose="Set the stage"
        )
        
        assert item.position == 1
        assert item.topic == "Introduction"
        assert len(item.search_hints) == 2
    
    def test_confirm_outline_request(self):
        """Test ConfirmOutlineRequest model."""
        from src.api.routes.deck_builder import ConfirmOutlineRequest, OutlineSlideItem
        
        request = ConfirmOutlineRequest(
            session_id="test-123",
            title="Azure Overview",
            narrative="An introduction to Azure",
            slides=[
                OutlineSlideItem(position=1, topic="Intro", search_hints=[], purpose="Start")
            ],
            all_slides=[{"session_code": "BRK211", "slide_number": 1}]
        )
        
        assert request.session_id == "test-123"
        assert request.title == "Azure Overview"
        assert len(request.slides) == 1
