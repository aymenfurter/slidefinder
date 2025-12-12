"""Slide Assistant API endpoints."""
import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.services import get_slide_assistant_service
from src.services.slide_assistant.models import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slide-assistant", tags=["slide-assistant"])


@router.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    """
    Send a message to the slide assistant.
    
    Uses Microsoft Agent Framework for consistent AI orchestration.
    Returns a structured response with:
    - answer: The assistant's conversational response
    - referenced_slides: Relevant slides with thumbnails and reasons
    - follow_up_suggestions: Optional follow-up questions
    """
    service = get_slide_assistant_service()
    
    if not service.is_available:
        return {
            "available": False,
            "answer": "The AI service is not configured.",
            "referenced_slides": [],
            "follow_up_suggestions": [],
        }
    
    response = await service.chat(
        message=request.message,
        history=request.history,
    )
    
    return {
        "available": True,
        "answer": response.answer,
        "referenced_slides": [slide.model_dump() for slide in response.referenced_slides],
        "follow_up_suggestions": response.follow_up_suggestions,
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Send a message to the slide assistant with streaming response.
    
    Returns SSE events:
    - {"type": "status", "message": "..."} - Status updates
    - {"type": "response", "answer": "...", "referenced_slides": [...]} - Final response
    - {"type": "done"} - Stream complete
    - {"type": "error", "message": "..."} - Error occurred
    """
    service = get_slide_assistant_service()
    
    if not service.is_available:
        async def unavailable_stream():
            yield 'data: {"type": "error", "message": "AI service not available"}\n\n'
        return StreamingResponse(
            unavailable_stream(),
            media_type="text/event-stream",
        )
    
    async def event_stream():
        async for event in service.chat_stream(
            message=request.message,
            history=request.history,
        ):
            yield event
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Check if the slide assistant service is available."""
    service = get_slide_assistant_service()
    return {
        "available": service.is_available,
    }
