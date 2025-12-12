"""Slide API endpoints."""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from src.services import get_search_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["slides"])


@router.get("/slides/{session_code}/{slide_number}")
async def get_slide_info(
    session_code: str, 
    slide_number: int
) -> dict[str, Any]:
    """
    Get information about a specific slide from the index.
    
    Security: Only returns information from the indexed slides,
    not arbitrary file paths.
    """
    search_service = get_search_service()
    slide_info = search_service.get_slide_info(session_code, slide_number)
    
    if not slide_info:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    return slide_info.model_dump()
