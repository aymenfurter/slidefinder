"""Search API endpoints."""
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.services import get_search_service, get_ai_overview_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

# Pattern to detect session IDs (e.g., BRK108, KEY001, THR502)
SESSION_ID_PATTERN = re.compile(r'^([A-Za-z]{2,4}\d{2,4})$')


@router.get("/session/{session_code}")
async def get_session_slides(
    session_code: str
) -> dict[str, Any]:
    """
    Get all slides for a specific session.
    
    Returns all slides from the session sorted by slide number.
    """
    search_service = get_search_service()
    results, session_info = search_service.get_session_slides(session_code)
    
    if not results:
        return {
            "session": None,
            "slides": [],
            "total": 0,
        }
    
    # Convert to response format
    slides_data = []
    for result in results:
        slides_data.append({
            "slide_id": result.slide_id,
            "session_code": result.session_code,
            "title": result.title,
            "slide_number": result.slide_number,
            "content": result.content,
            "snippet": result.snippet,
            "event": result.event,
            "session_url": result.session_url,
            "ppt_url": result.ppt_url,
            "has_thumbnail": result.has_thumbnail,
        })
    
    return {
        "session": session_info,
        "slides": slides_data,
        "total": len(slides_data),
    }


@router.get("/search")
async def search_slides(
    q: str = Query(..., min_length=2, max_length=500, description="Search query - natural language questions work best")
) -> dict[str, Any]:
    """
    Search for slides using agentic retrieval.
    
    Uses Azure AI Search knowledge base with intelligent reasoning
    to find the most relevant slides. Natural language questions
    produce the best results.
    
    Returns matching slides with thumbnails, source information,
    and a search_context string that can be used with /api/ai-overview.
    """
    search_service = get_search_service()
    results, search_time_ms, search_context = search_service.search(q)
    
    # Convert to response format
    results_data = []
    for result in results:
        results_data.append({
            "slide_id": result.slide_id,
            "session_code": result.session_code,
            "title": result.title,
            "slide_number": result.slide_number,
            "content": result.content,
            "snippet": result.snippet,
            "event": result.event,
            "session_url": result.session_url,
            "ppt_url": result.ppt_url,
            "has_thumbnail": result.has_thumbnail,
            "score": result.score,
        })
    
    # Sort by score (highest first)
    results_data.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "results": results_data,
        "search_time_ms": search_time_ms,
        "search_context": search_context,
        "query": q,
    }


class AIOverviewRequest(BaseModel):
    """Request model for AI overview generation."""
    query: str
    search_context: str
    result_count: int
    unique_sessions: int


@router.post("/ai-overview")
async def generate_ai_overview(request: AIOverviewRequest) -> dict[str, Any]:
    """
    Generate an AI overview of search results.
    
    Uses Microsoft Agent Framework with gpt-4.1-nano to generate a concise 
    summary of available slide content for the given topic based on the 
    search context.
    
    Args:
        query: The original search query
        search_context: The finishContext JSON from search results
        result_count: Number of matching slides
        unique_sessions: Number of unique presentation sessions
        
    Returns:
        Generated overview text
    """
    ai_overview_service = get_ai_overview_service()
    
    if not ai_overview_service.is_available:
        return {
            "overview": "",
            "available": False,
        }
    
    overview = await ai_overview_service.generate_overview(
        query=request.query,
        search_context=request.search_context,
        result_count=request.result_count,
        unique_sessions=request.unique_sessions,
    )
    
    return {
        "overview": overview,
        "available": True,
    }


@router.post("/ai-overview/stream")
async def generate_ai_overview_stream(request: AIOverviewRequest):
    """
    Generate an AI overview with streaming response.
    
    Uses gpt-4.1-nano to generate a concise summary of available
    slide content, streamed for responsive UI updates.
    
    Returns:
        Server-sent events stream with overview chunks
    """
    ai_overview_service = get_ai_overview_service()
    
    if not ai_overview_service.is_available:
        async def empty_stream():
            yield "data: {\"done\": true, \"available\": false}\n\n"
        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
        )
    
    async def stream_overview():
        try:
            async for chunk in ai_overview_service.generate_overview_stream(
                query=request.query,
                search_context=request.search_context,
                result_count=request.result_count,
                unique_sessions=request.unique_sessions,
            ):
                yield f"data: {{\"chunk\": \"{chunk.replace(chr(34), chr(92) + chr(34)).replace(chr(10), chr(92) + 'n')}\"}}\n\n"
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            logger.error(f"AI overview stream error: {e}")
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(
        stream_overview(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
