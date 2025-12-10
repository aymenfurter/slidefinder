"""Deck Builder API endpoints."""
import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from models.deck import DeckSession
from services.deck_builder import get_deck_builder_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deck-builder", tags=["deck-builder"])

# Session storage (in production, use Redis or database)
deck_sessions: dict[str, DeckSession] = {}


class ChatRequest(BaseModel):
    """Request payload for chat endpoints."""
    
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="User message"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Session ID for continuing a conversation"
    )


class OutlineSlideItem(BaseModel):
    """A single slide in the outline."""
    position: int
    topic: str
    search_hints: list[str] = Field(default_factory=list)
    purpose: str


class ConfirmOutlineRequest(BaseModel):
    """Request payload for confirming/editing an outline."""
    session_id: str = Field(..., description="Session ID")
    title: str = Field(..., description="Presentation title")
    narrative: str = Field(..., description="Presentation narrative")
    slides: list[OutlineSlideItem] = Field(..., description="Outline slides")
    all_slides: list[dict] = Field(..., description="Available slides from search")


@router.post("/chat/stream")
async def deck_builder_chat_stream(request: ChatRequest) -> EventSourceResponse:
    """
    SSE endpoint for streaming chat responses with real-time tool updates.
    
    Streams events as:
    - session: Session ID
    - thinking: Processing indicator
    - tool_call: Tool being called
    - search_complete: Search results
    - deck_compiled: Deck compilation result
    - message: Final AI message
    - download_info: Source deck information
    - complete: Processing complete
    - error: Error occurred
    - debug_*: Debug events (always sent, frontend decides visibility)
    """
    session_id = request.session_id
    
    if not session_id or session_id not in deck_sessions:
        session_id = str(uuid.uuid4())
        deck_sessions[session_id] = DeckSession(session_id=session_id)
    
    session = deck_sessions[session_id]
    deck_builder = get_deck_builder_service()
    
    async def event_generator():
        # Send session ID first
        yield {
            "event": "session",
            "data": json.dumps({"type": "session", "session_id": session_id}),
        }
        
        try:
            async for event in deck_builder.process_message_stream(
                session, 
                request.message
            ):
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                }
        except Exception as e:
            logger.exception(f"Deck builder stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
    
    return EventSourceResponse(event_generator())


@router.post("/confirm-outline/stream")
async def confirm_outline_stream(request: ConfirmOutlineRequest) -> EventSourceResponse:
    """
    SSE endpoint for continuing deck build after user confirms/edits the outline.
    """
    session_id = request.session_id
    
    if session_id not in deck_sessions:
        deck_sessions[session_id] = DeckSession(session_id=session_id)
    
    session = deck_sessions[session_id]
    deck_builder = get_deck_builder_service()
    
    # Convert to dict format
    outline_data = {
        "title": request.title,
        "narrative": request.narrative,
        "slides": [s.model_dump() for s in request.slides]
    }
    
    async def event_generator():
        try:
            async for event in deck_builder.continue_with_outline_stream(
                session,
                outline_data,
                request.all_slides
            ):
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                }
        except Exception as e:
            logger.exception(f"Confirm outline stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
    
    return EventSourceResponse(event_generator())


@router.post("/chat")
async def deck_builder_chat(request: ChatRequest) -> dict[str, Any]:
    """
    Non-streaming fallback endpoint for chat.
    
    Returns all events collected from the stream.
    """
    try:
        session_id = request.session_id
        
        if not session_id or session_id not in deck_sessions:
            session_id = str(uuid.uuid4())
            deck_sessions[session_id] = DeckSession(session_id=session_id)
        
        session = deck_sessions[session_id]
        deck_builder = get_deck_builder_service()
        
        events = []
        final_message = ""
        
        async for event in deck_builder.process_message_stream(
            session, 
            request.message
        ):
            events.append(event)
            if event.get("type") == "message":
                final_message = event.get("content", "")
        
        return {
            "session_id": session_id,
            "events": events,
            "final_response": final_message,
            "compiled_deck": session.compiled_deck if session.status == "complete" else None,
            "flow_explanation": session.flow_explanation if session.status == "complete" else None,
            "status": session.status,
        }
        
    except Exception as e:
        logger.exception(f"Deck builder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_deck_session(session_id: str) -> dict[str, Any]:
    """Get the current state of a deck builder session."""
    if session_id not in deck_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = deck_sessions[session_id]
    return session.to_dict()


@router.get("/download/{session_id}")
async def download_deck(session_id: str):
    """Download the compiled deck as a PPTX file."""
    if session_id not in deck_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = deck_sessions[session_id]
    if not session.compiled_deck:
        raise HTTPException(status_code=400, detail="No deck compiled yet")
        
    deck_builder = get_deck_builder_service()
    try:
        file_path = await deck_builder.generate_deck_pptx(session)
        return FileResponse(
            path=file_path,
            filename=f"SlideFinder_Deck_{session_id[:8]}.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    except Exception as e:
        logger.exception(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
