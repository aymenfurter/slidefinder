"""Helper utilities for deck building."""
import logging
from typing import Optional
from agent_framework import ChatMessage, Role, TextContent, DataContent
from src.core import get_settings

logger = logging.getLogger(__name__)
DEFAULT_MAX_SLIDES, CONTENT_PREVIEW_LENGTH, CANDIDATE_CONTENT_LENGTH = 20, 150, 300

def load_slide_thumbnail(session_code: str, slide_number: int) -> Optional[bytes]:
    """Load a slide thumbnail image from disk."""
    path = get_settings().thumbnails_dir / f"{session_code}_{slide_number}.png"
    if path.exists():
        try:
            return path.read_bytes()
        except Exception as e:
            logger.warning(f"Failed to load thumbnail {path}: {e}")
    return None


def build_multimodal_message(text_prompt: str, slides: list[dict],
                             include_images: bool = True) -> ChatMessage:
    """Build a ChatMessage with text and optional slide thumbnails."""
    contents = [TextContent(text=text_prompt)]
    if include_images:
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            code, num = slide.get("session_code", ""), slide.get("slide_number", 0)
            if code and num and (img := load_slide_thumbnail(code, num)):
                contents.append(TextContent(text=f"\n[Image: {code} Slide {num}]"))
                contents.append(DataContent(data=img, media_type="image/png"))
    return ChatMessage(role=Role.USER, contents=contents)


def format_slides_summary(slides: list[dict], max_slides: int = DEFAULT_MAX_SLIDES) -> str:
    """Format slides as a text summary for the outline agent."""
    return "\n".join(
        f"- [{s.get('session_code', '')} #{s.get('slide_number', 0)}] "
        f"{s.get('title', '')}: {_get_slide_content(s)[:CONTENT_PREVIEW_LENGTH]}..."
        for s in slides[:max_slides]
    )

def _get_slide_content(slide: dict) -> str:
    """Extract content from slide, checking both field names."""
    return slide.get("content", slide.get("slide_text", ""))

def format_candidates(candidates: list[dict]) -> str:
    """Format candidate slides for the offer agent."""
    return "\n".join(line for i, s in enumerate(candidates, 1) for line in _format_single_candidate(i, s))

def _format_single_candidate(index: int, slide: dict) -> list[str]:
    """Format a single candidate slide entry."""
    code, num = slide.get("session_code", ""), slide.get("slide_number", 0)
    lines = [f"{index}. [{code} Slide {num}] {slide.get('title', '')}"]
    if session_title := slide.get("session_title", ""):
        lines.append(f"   Session: {session_title}")
    lines.extend([f"   Content: {_get_slide_content(slide)[:CANDIDATE_CONTENT_LENGTH]}...", ""])
    return lines


def compute_source_decks(deck: list[dict], all_slides: list[dict]) -> list[dict]:
    """Compute which source decks are used in the final deck."""
    session_map = {}
    for slide in deck:
        code = slide.get("session_code", "")
        if code not in session_map:
            session_map[code] = {"session_code": code, "title": "", "slides_used": [], "ppt_url": ""}
        session_map[code]["slides_used"].append(slide.get("slide_number", 0))
    for slide in all_slides:
        if (code := slide.get("session_code", "")) in session_map:
            entry = session_map[code]
            entry["title"] = entry["title"] or slide.get("session_title", code)
            entry["ppt_url"] = entry["ppt_url"] or slide.get("ppt_url", "")
    return list(session_map.values())
