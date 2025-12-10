"""Helper utilities for deck building."""

import logging
from typing import Optional

from agent_framework import ChatMessage, Role, TextContent, DataContent
from config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_MAX_SLIDES = 20
CONTENT_PREVIEW_LENGTH = 150
CANDIDATE_CONTENT_LENGTH = 300


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
    """Build a ChatMessage with text and optional slide thumbnails."""
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


def format_slides_summary(slides: list[dict], max_slides: int = DEFAULT_MAX_SLIDES) -> str:
    """Format slides as a text summary for the outline agent."""
    lines = []
    for slide in slides[:max_slides]:
        code = slide.get("session_code", "")
        num = slide.get("slide_number", 0)
        title = slide.get("title", "")
        content = _get_slide_content(slide)[:CONTENT_PREVIEW_LENGTH]
        lines.append(f"- [{code} #{num}] {title}: {content}...")
    return "\n".join(lines)


def _get_slide_content(slide: dict) -> str:
    """Extract content from slide, checking both field names."""
    return slide.get("content", slide.get("slide_text", ""))


def format_candidates(candidates: list[dict]) -> str:
    """Format candidate slides for the offer agent."""
    lines = []
    for i, slide in enumerate(candidates, 1):
        lines.extend(_format_single_candidate(i, slide))
    return "\n".join(lines)


def _format_single_candidate(index: int, slide: dict) -> list[str]:
    """Format a single candidate slide entry."""
    code = slide.get("session_code", "")
    num = slide.get("slide_number", 0)
    title = slide.get("title", "")
    content = _get_slide_content(slide)[:CANDIDATE_CONTENT_LENGTH]
    session_title = slide.get("session_title", "")
    
    lines = [f"{index}. [{code} Slide {num}] {title}"]
    if session_title:
        lines.append(f"   Session: {session_title}")
    lines.append(f"   Content: {content}...")
    lines.append("")
    return lines


def compute_source_decks(deck: list[dict], all_slides: list[dict]) -> list[dict]:
    """Compute which source decks are used in the final deck."""
    session_map = _build_session_map(deck)
    _enrich_session_metadata(session_map, all_slides)
    return list(session_map.values())


def _build_session_map(deck: list[dict]) -> dict[str, dict]:
    """Build a map of session codes to their slide usage."""
    session_map = {}
    for slide in deck:
        code = slide.get("session_code", "")
        if code not in session_map:
            session_map[code] = {
                "session_code": code,
                "title": "",
                "slides_used": [],
                "ppt_url": ""
            }
        session_map[code]["slides_used"].append(slide.get("slide_number", 0))
    return session_map


def _enrich_session_metadata(session_map: dict[str, dict], all_slides: list[dict]) -> None:
    """Add title and URL metadata from the full slide list."""
    for slide in all_slides:
        code = slide.get("session_code", "")
        if code in session_map:
            entry = session_map[code]
            if not entry["title"]:
                entry["title"] = slide.get("session_title", code)
            if not entry["ppt_url"]:
                entry["ppt_url"] = slide.get("ppt_url", "")
