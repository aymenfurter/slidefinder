"""Search API endpoints."""
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Query

from services.search_service import get_search_service

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
    
    Returns matching slides with thumbnails and source information.
    """
    search_service = get_search_service()
    results, search_time_ms = search_service.search(q)
    
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
    }
