"""Main Deck Builder Service."""

import logging
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from dotenv import load_dotenv

INITIAL_SEARCH_LIMIT = 30
SUB_SEARCH_LIMIT = 10
SEARCH_PREVIEW_COUNT = 8

from src.core import get_settings
from src.models.deck import DeckSession
from src.services.search import get_search_service

from .agents import WorkflowOrchestrator
from .helpers import compute_source_decks
from .models import SlideOutlineItem, PresentationOutline
from . import events  # Debug event factories

load_dotenv()

logger = logging.getLogger(__name__)


class DeckBuilderService:
    """AI-powered deck builder with outline generation and slide selection workflow."""
    
    def __init__(self):
        self._settings = get_settings()
        self._search_service = get_search_service()
        self._orchestrator = WorkflowOrchestrator()

    async def process_message_stream(
        self,
        session: DeckSession,
        message: str
    ) -> AsyncIterator[dict]:
        """Process a user message and stream events."""
        try:
            # Emit code documentation links for nerd mode
            yield events.code_documentation()
            
            yield events.phase_init(message)
            yield {"type": "thinking", "message": "Starting deck build..."}
            
            # --- Initial Search Phase ---
            yield events.phase_search()
            yield {"type": "agent_start", "agent": "Researcher", "task": "Searching for relevant slides"}
            
            start_time = time.time()
            all_slides = await self._initial_search(message)
            search_duration = int((time.time() - start_time) * 1000)
            
            yield {"type": "agent_complete", "agent": "Researcher", "summary": f"Found {len(all_slides)} candidate slides"}
            yield {"type": "search_complete", "results": all_slides[:SEARCH_PREVIEW_COUNT]}
            yield events.search_complete(message, len(all_slides), search_duration, all_slides)
            
            if not all_slides:
                yield {"type": "message", "content": "I couldn't find any relevant slides for your request. Please try a different topic."}
                yield {"type": "complete"}
                return
            
            # --- Outline Generation Phase ---
            yield events.phase_outline()
            yield {"type": "agent_start", "agent": "Architect", "task": "Creating presentation outline"}
            yield events.outline_llm_start(message, all_slides, len(all_slides))
            
            start_time = time.time()
            outline = await self._orchestrator.generate_outline(message, all_slides)
            outline_duration = int((time.time() - start_time) * 1000)
            
            yield events.outline_llm_complete(outline, outline_duration)
            yield {"type": "agent_complete", "agent": "Architect", "summary": f"Created outline with {len(outline.slides)} slides"}
            
            yield {
                "type": "outline_pending",
                "title": outline.title,
                "narrative": outline.narrative,
                "slides": [
                    {
                        "position": s.position,
                        "topic": s.topic,
                        "search_hints": s.search_hints,
                        "purpose": s.purpose
                    }
                    for s in outline.slides
                ],
                "all_slides": all_slides
            }
            
            yield {"type": "awaiting_confirmation"}
            
        except Exception as e:
            logger.exception(f"Error in deck builder: {e}")
            yield {"type": "error", "message": str(e)}

    async def continue_with_outline_stream(
        self,
        session: DeckSession,
        outline_data: dict,
        all_slides: list[dict]
    ) -> AsyncIterator[dict]:
        """Continue deck building after user confirms the outline."""
        try:
            outline = PresentationOutline(
                title=outline_data.get("title", "Presentation"),
                narrative=outline_data.get("narrative", ""),
                slides=[
                    SlideOutlineItem(
                        position=s.get("position", i + 1),
                        topic=s.get("topic", ""),
                        search_hints=s.get("search_hints", []),
                        purpose=s.get("purpose", "")
                    )
                    for i, s in enumerate(outline_data.get("slides", []))
                ]
            )
            
            yield events.phase_slide_selection(len(outline.slides))
            yield {"type": "outline_confirmed", "title": outline.title, "slide_count": len(outline.slides)}
            
            final_deck = []
            already_selected_keys = set()
            
            for outline_item in outline.slides:
                yield events.slide_workflow_start(outline_item.position, outline_item.topic, len(outline.slides))
                yield {
                    "type": "slide_selection_start",
                    "position": outline_item.position,
                    "topic": outline_item.topic,
                    "total": len(outline.slides)
                }
                
                selected_slide = None
                async for event in self._orchestrator.select_slide_with_critique(
                    outline_item=outline_item,
                    full_outline=outline,
                    all_slides=all_slides,
                    already_selected_keys=already_selected_keys
                ):
                    if event.get("type") == "slide_result":
                        selected_slide = event.get("slide")
                    else:
                        yield event
                
                if selected_slide:
                    selected_slide["reason"] = f"{outline_item.purpose} - {selected_slide.get('reason', '')}"
                    final_deck.append(selected_slide)
                    already_selected_keys.add(f"{selected_slide['session_code']}_{selected_slide['slide_number']}")
                    
                    yield events.slide_workflow_complete(outline_item.position, True, selected_slide)
                    yield {
                        "type": "slide_selected",
                        "position": outline_item.position,
                        "slide": selected_slide,
                        "topic": outline_item.topic
                    }
                else:
                    yield events.slide_workflow_complete(outline_item.position, False)
                    yield {
                        "type": "slide_not_found",
                        "position": outline_item.position,
                        "topic": outline_item.topic
                    }
                
                yield {
                    "type": "intermediate_deck",
                    "deck": final_deck,
                    "narrative": outline.narrative,
                    "revision_round": 0,
                    "is_final": False
                }
            
            yield events.phase_complete(len(final_deck))
            
            if final_deck:
                session.compiled_deck = final_deck
                session.deck_narrative = outline.narrative
                session.flow_explanation = f"Presentation: {outline.title}"
                session.status = "complete"
                
                source_decks = compute_source_decks(final_deck, all_slides)
                
                yield {"type": "deck_compiled", "slides": final_deck, "narrative": outline.narrative}
                yield {"type": "download_info", "decks": source_decks}
                yield {
                    "type": "message",
                    "content": f"I've created a {len(final_deck)}-slide presentation: **{outline.title}**\n\n{outline.narrative}"
                }
            else:
                yield {"type": "message", "content": "I wasn't able to find suitable slides for your presentation."}
            
            yield {"type": "complete"}
            
        except Exception as e:
            logger.exception(f"Error continuing with outline: {e}")
            yield {"type": "error", "message": str(e)}

    async def _initial_search(self, query: str) -> list[dict]:
        """Search for candidate slides matching the query."""
        results, _, _ = self._search_service.search(query, limit=INITIAL_SEARCH_LIMIT, include_pptx_status=True)
        all_slides = [r.model_dump() for r in results]
        
        self._add_partial_query_results(query, all_slides)
        return all_slides
    
    def _add_partial_query_results(self, query: str, slides: list[dict]) -> None:
        """Add results from a partial query to diversify candidates."""
        words = query.split()
        if len(words) <= 2:
            return
        
        sub_query = " ".join(words[:len(words)//2])
        sub_results, _, _ = self._search_service.search(sub_query, limit=SUB_SEARCH_LIMIT, include_pptx_status=True)
        existing_keys = {_slide_key(s) for s in slides}
        
        for result in sub_results:
            slide_dict = result.model_dump()
            if _slide_key(slide_dict) not in existing_keys:
                slides.append(slide_dict)

    async def generate_deck_pptx(self, session: DeckSession) -> Path:
        """Generate a PPTX file from the compiled deck."""
        from src.services.pptx import merge_slides_to_deck
        
        if not session.compiled_deck:
            raise ValueError("No compiled deck to generate")
        
        output_dir = self._settings.compiled_decks_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / f"deck_{session.session_id}.pptx"
        
        slide_specs = [
            (slide["session_code"], slide["slide_number"])
            for slide in session.compiled_deck
        ]
        
        merge_slides_to_deck(
            slide_specs=slide_specs,
            output_path=output_path,
            ppts_dir=self._settings.ppts_dir
        )
        
        return output_path


_deck_builder_service: Optional[DeckBuilderService] = None


def get_deck_builder_service() -> DeckBuilderService:
    """Get the singleton deck builder service instance."""
    global _deck_builder_service
    if _deck_builder_service is None:
        _deck_builder_service = DeckBuilderService()
    return _deck_builder_service


def _slide_key(slide: dict) -> str:
    """Generate a unique key for a slide."""
    return f"{slide['session_code']}_{slide['slide_number']}"
