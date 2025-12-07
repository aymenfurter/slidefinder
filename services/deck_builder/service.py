"""Main Deck Builder Service."""

import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from dotenv import load_dotenv

from config import get_settings
from models.deck import DeckSession
from services.search_service import get_search_service

from .agents import WorkflowOrchestrator
from .helpers import compute_source_decks
from .models import SlideOutlineItem, PresentationOutline

load_dotenv()

logger = logging.getLogger(__name__)


class DeckBuilderService:
    """
    AI-powered deck builder with Outline → Critique/Offer workflow.
    
    Workflow:
    1. Initial Search: Find relevant slides based on user query
    2. Outline Agent: Creates a structured outline using query + available slides
    3. For each slide in outline, run Critique & Offer loop to select best match
    """
    
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
            yield {"type": "thinking", "message": "Starting deck build..."}
            
            yield {"type": "agent_start", "agent": "Researcher", "task": "Searching for relevant slides"}
            all_slides = await self._initial_search(message)
            yield {"type": "agent_complete", "agent": "Researcher", "summary": f"Found {len(all_slides)} candidate slides"}
            yield {"type": "search_complete", "results": all_slides[:8]}
            
            if not all_slides:
                yield {"type": "message", "content": "I couldn't find any relevant slides for your request. Please try a different topic."}
                yield {"type": "complete"}
                return
            
            yield {"type": "agent_start", "agent": "Architect", "task": "Creating presentation outline"}
            outline = await self._orchestrator.generate_outline(message, all_slides)
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
        """Continue deck building after user confirms/edits the outline."""
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
            
            yield {"type": "outline_confirmed", "title": outline.title, "slide_count": len(outline.slides)}
            
            final_deck = []
            already_selected_keys = set()
            
            for outline_item in outline.slides:
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
                    
                    yield {
                        "type": "slide_selected",
                        "position": outline_item.position,
                        "slide": selected_slide,
                        "topic": outline_item.topic
                    }
                else:
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
        """Perform initial search to find candidate slides."""
        results, _ = self._search_service.search(query, limit=30, include_pptx_status=True)
        all_slides = [r.model_dump() for r in results]
        
        words = query.split()
        if len(words) > 2:
            sub_query = " ".join(words[:len(words)//2])
            sub_results, _ = self._search_service.search(sub_query, limit=10, include_pptx_status=True)
            existing_keys = {f"{s['session_code']}_{s['slide_number']}" for s in all_slides}
            
            for r in sub_results:
                slide_dict = r.model_dump()
                key = f"{slide_dict['session_code']}_{slide_dict['slide_number']}"
                if key not in existing_keys:
                    all_slides.append(slide_dict)
        
        return all_slides

    async def generate_deck_pptx(self, session: DeckSession) -> Path:
        """Generate a PPTX file from the compiled deck."""
        from services.pptx_merger import merge_slides_to_deck
        
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
