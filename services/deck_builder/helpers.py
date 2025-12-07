"""Helper utilities for deck building."""

import logging
from typing import Optional

from agent_framework import ChatMessage, Role, TextContent, DataContent
from config import get_settings

logger = logging.getLogger(__name__)


def load_slide_thumbnail(session_code: str, slide_number: int) -> Optional[bytes]:
    """Load a slide thumbnail image from disk."""
    settings = get_settings()
    thumbnail_path = settings.thumbnails_dir / f"{session_code}_{slide_number}.png"
    
    if thumbnail_path.exists():
        try:
            return thumbnail_path.read_bytes()
        except Exception as e:
            logger.warning(f"Failed to load thumbnail {thumbnail_path}: {e}")
    return None


def build_multimodal_message(
    text_prompt: str,
    slides: list[dict],
    include_images: bool = True
) -> ChatMessage:
    """Build a ChatMessage with text and optional slide thumbnail images."""
    contents = [TextContent(text=text_prompt)]
    
    if include_images:
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            session_code = slide.get("session_code", "")
            slide_number = slide.get("slide_number", 0)
            
            if not session_code or not slide_number:
                continue
                
            image_bytes = load_slide_thumbnail(session_code, slide_number)
            if image_bytes:
                contents.append(TextContent(
                    text=f"\n[Image: {session_code} Slide {slide_number}]"
                ))
                contents.append(DataContent(data=image_bytes, media_type="image/png"))
    
    return ChatMessage(role=Role.USER, contents=contents)


def format_slides_summary(slides: list[dict], max_slides: int = 20) -> str:
    """Format slides for the outline agent."""
    lines = []
    for s in slides[:max_slides]:
        code = s.get("session_code", "")
        num = s.get("slide_number", 0)
        title = s.get("title", "")
        content = s.get("content", s.get("slide_text", ""))[:150]
        lines.append(f"- [{code} #{num}] {title}: {content}...")
    return "\n".join(lines)


def format_candidates(candidates: list[dict]) -> str:
    """Format candidates for the offer agent."""
    lines = []
    for i, s in enumerate(candidates, 1):
        code = s.get("session_code", "")
        num = s.get("slide_number", 0)
        title = s.get("title", "")
        content = s.get("content", s.get("slide_text", ""))[:300]
        session_title = s.get("session_title", "")
        
        lines.append(f"{i}. [{code} Slide {num}] {title}")
        if session_title:
            lines.append(f"   Session: {session_title}")
        lines.append(f"   Content: {content}...")
        lines.append("")
    return "\n".join(lines)


def compute_source_decks(deck: list[dict], all_slides: list[dict]) -> list[dict]:
    """Compute which source decks are used in the final deck."""
    session_slides = {}
    
    for slide in deck:
        code = slide.get("session_code", "")
        if code not in session_slides:
            session_slides[code] = {
                "session_code": code,
                "title": "",
                "slides_used": [],
                "ppt_url": ""
            }
        session_slides[code]["slides_used"].append(slide.get("slide_number", 0))
    
    for s in all_slides:
        code = s.get("session_code", "")
        if code in session_slides:
            if not session_slides[code]["title"]:
                session_slides[code]["title"] = s.get("session_title", code)
            if not session_slides[code]["ppt_url"]:
                session_slides[code]["ppt_url"] = s.get("ppt_url", "")
    
    return list(session_slides.values())
