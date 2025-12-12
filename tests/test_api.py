"""
Unit tests for API endpoints.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routes.search import router as search_router
from src.api.routes.deck_builder import router as deck_builder_router
from src.api.routes.slides import router as slides_router


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(search_router)
    app.include_router(deck_builder_router)
    app.include_router(slides_router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestSearchAPI:
    """Tests for search API endpoints."""
    
    def test_search_success(self, client):
        """Test successful search."""
        mock_result = Mock()
        mock_result.slide_id = "BRK211_1"
        mock_result.session_code = "BRK211"
        mock_result.title = "Test Title"
        mock_result.slide_number = 1
        mock_result.content = "Test content"
        mock_result.snippet = "Test <b>content</b>"
        mock_result.event = "Build"
        mock_result.session_url = "https://example.com"
        mock_result.ppt_url = "https://example.com/ppt.pptx"
        mock_result.has_thumbnail = True
        mock_result.score = 1.5
        
        mock_service = Mock()
        mock_service.search.return_value = ([mock_result], 15.5, None)
        
        with patch("src.api.routes.search.get_search_service", return_value=mock_service):
            response = client.get("/api/search?q=test")
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "search_time_ms" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["slide_id"] == "BRK211_1"
    
    def test_search_query_too_short(self, client):
        """Test search with query too short."""
        response = client.get("/api/search?q=a")
        
        assert response.status_code == 422  # Validation error
    
    def test_search_no_results(self, client):
        """Test search with no results."""
        mock_service = Mock()
        mock_service.search.return_value = ([], 5.0, None)
        
        with patch("src.api.routes.search.get_search_service", return_value=mock_service):
            response = client.get("/api/search?q=xyznonexistent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []


class TestSlidesAPI:
    """Tests for slides API endpoints."""
    
    def test_get_slide_info_found(self, client):
        """Test getting slide info when found."""
        mock_info = Mock()
        mock_info.model_dump.return_value = {
            "slide_id": "BRK211_1",
            "session_code": "BRK211",
            "slide_number": 1,
            "title": "Test",
            "content": "Content",
            "event": "Build",
            "session_url": "https://example.com",
            "ppt_url": "https://example.com/ppt.pptx",
        }
        
        mock_service = Mock()
        mock_service.get_slide_info.return_value = mock_info
        
        with patch("src.api.routes.slides.get_search_service", return_value=mock_service):
            response = client.get("/api/slides/BRK211/1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["slide_id"] == "BRK211_1"
    
    def test_get_slide_info_not_found(self, client):
        """Test getting slide info when not found."""
        mock_service = Mock()
        mock_service.get_slide_info.return_value = None
        
        with patch("src.api.routes.slides.get_search_service", return_value=mock_service):
            response = client.get("/api/slides/INVALID/999")
        
        assert response.status_code == 404


class TestDeckBuilderAPI:
    """Tests for deck builder API endpoints."""
    
    def test_get_session_not_found(self, client):
        """Test getting non-existent session."""
        response = client.get("/api/deck-builder/session/nonexistent")
        
        assert response.status_code == 404
    
    def test_chat_creates_session(self, client):
        """Test that chat creates a new session."""
        mock_deck_builder = Mock()
        
        async def mock_stream(*args, **kwargs):
            yield {"type": "complete", "status": "done"}
        
        mock_deck_builder.process_message_stream = mock_stream
        
        with patch("src.api.routes.deck_builder.get_deck_builder_service", return_value=mock_deck_builder):
            response = client.post("/api/deck-builder/chat", json={
                "message": "Build a deck about AI"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data


class TestDeckBuilderChatEndpoint:
    """Tests for chat endpoint specifically."""
    
    def test_chat_non_streaming(self, client):
        """Test non-streaming chat endpoint."""
        mock_deck_builder = Mock()
        
        async def mock_stream(*args, **kwargs):
            yield {"type": "thinking", "message": "Processing..."}
            yield {"type": "tool_call", "tool": "search_slides", "args": {"query": "AI"}}
            yield {"type": "deck_compiled", "slides": [], "flow_explanation": ""}
            yield {"type": "message", "content": "Done!"}
            yield {"type": "complete", "status": "done"}
        
        mock_deck_builder.process_message_stream = mock_stream
        
        with patch("src.api.routes.deck_builder.get_deck_builder_service", return_value=mock_deck_builder):
            response = client.post("/api/deck-builder/chat", json={
                "message": "Build a deck about AI"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["final_response"] == "Done!"
    
    def test_chat_with_session_id(self, client):
        """Test chat with existing session ID."""
        from src.api.routes.deck_builder import deck_sessions
        from src.models.deck import DeckSession
        
        # Create a session
        session = DeckSession(session_id="test-session-123")
        deck_sessions["test-session-123"] = session
        
        mock_deck_builder = Mock()
        
        async def mock_stream(*args, **kwargs):
            yield {"type": "complete", "status": "done"}
        
        mock_deck_builder.process_message_stream = mock_stream
        
        with patch("src.api.routes.deck_builder.get_deck_builder_service", return_value=mock_deck_builder):
            response = client.post("/api/deck-builder/chat", json={
                "message": "Add more slides",
                "session_id": "test-session-123"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        
        # Cleanup
        del deck_sessions["test-session-123"]


class TestSessionAPI:
    """Tests for session API endpoints."""
    
    def test_get_session_slides_found(self, client):
        """Test getting slides for a session."""
        mock_result = Mock()
        mock_result.slide_id = "BRK211_1"
        mock_result.session_code = "BRK211"
        mock_result.title = "Test Title"
        mock_result.slide_number = 1
        mock_result.content = "Test content"
        mock_result.snippet = "Test <b>content</b>"
        mock_result.event = "Build"
        mock_result.session_url = "https://example.com"
        mock_result.ppt_url = "https://example.com/ppt.pptx"
        mock_result.has_thumbnail = True
        
        mock_session_info = {
            "session_code": "BRK211",
            "title": "Test Title",
            "event": "Build",
            "session_url": "https://example.com",
            "ppt_url": "https://example.com/ppt.pptx",
            "has_pptx": True
        }
        
        mock_service = Mock()
        mock_service.get_session_slides.return_value = ([mock_result], mock_session_info)
        
        with patch("src.api.routes.search.get_search_service", return_value=mock_service):
            response = client.get("/api/session/BRK211")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["session"]["session_code"] == "BRK211"
        assert len(data["slides"]) == 1
    
    def test_get_session_slides_not_found(self, client):
        """Test getting slides for a non-existent session."""
        mock_service = Mock()
        mock_service.get_session_slides.return_value = ([], None)
        
        with patch("src.api.routes.search.get_search_service", return_value=mock_service):
            response = client.get("/api/session/NONEXISTENT")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["session"] is None


class TestDeckBuilderDownload:
    """Tests for deck download endpoint."""
    
    def test_download_deck_no_session(self, client):
        """Test downloading deck when session doesn't exist."""
        response = client.get("/api/deck-builder/download/nonexistent")
        
        assert response.status_code == 404
    
    def test_download_deck_no_compiled_deck(self, client):
        """Test downloading deck when no deck has been compiled."""
        from src.api.routes.deck_builder import deck_sessions
        from src.models.deck import DeckSession
        
        session = DeckSession(session_id="test-download-123")
        deck_sessions["test-download-123"] = session
        
        try:
            response = client.get("/api/deck-builder/download/test-download-123")
            assert response.status_code == 400
            assert "No deck compiled" in response.json()["detail"]
        finally:
            del deck_sessions["test-download-123"]
