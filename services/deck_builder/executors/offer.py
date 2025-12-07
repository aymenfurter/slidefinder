"""Offer executor for the slide selection workflow."""

import logging

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message, format_candidates
from ..models import SlideOutlineItem, PresentationOutline, SlideSelection
from ..state import SlideSelectionState

logger = logging.getLogger(__name__)

MAX_CRITIQUE_ATTEMPTS = 15


class OfferExecutor(Executor):
    """Agent selects the best slide from candidates."""
    
    def __init__(self, offer_agent: ChatAgent, id: str = "offer"):
        super().__init__(id=id)
        self._offer_agent = offer_agent
    
    @handler
    async def handle(self, state: SlideSelectionState, ctx: WorkflowContext[SlideSelectionState]) -> None:
        """Select a slide from candidates."""
        # Check max attempts
        if state.current_attempt >= MAX_CRITIQUE_ATTEMPTS:
            state.phase = "judge"
            await ctx.send_message(state)
            return
        
        if not state.current_candidates:
            state.phase = "done"
            await ctx.send_message(state)
            return
        
        # Build prompt - limit candidates for agent to avoid overwhelming it
        candidates_for_agent = state.current_candidates[:5]  # Top 5 candidates
        context = self._build_context(state.outline_item, state.full_outline)
        prompt = self._build_prompt(context, candidates_for_agent, state.conversation_history)
        message = build_multimodal_message(prompt, candidates_for_agent, include_images=True)
        
        logger.info(f"OfferExecutor: {len(candidates_for_agent)} candidates for position {state.outline_item.position}")
        
        state.current_selection = None
        
        try:
            response = await self._offer_agent.run([message], response_format=SlideSelection)
            
            if response.value:
                selection = response.value
                logger.info(f"Offer agent selected: {selection.session_code} #{selection.slide_number}")
                
                # Validate selection exists in candidates
                for s in state.current_candidates:
                    if s['session_code'] == selection.session_code and s['slide_number'] == selection.slide_number:
                        state.current_selection = {
                            "session_code": selection.session_code,
                            "slide_number": selection.slide_number,
                            "reason": selection.reason,
                            "slide_data": s
                        }
                        logger.info(f"Selection validated against candidates")
                        break
                
                # If not found in candidates, try to find in all_slides as fallback
                if not state.current_selection:
                    logger.warning(f"Selection not in candidates, checking all_slides")
                    for s in state.all_slides:
                        if s['session_code'] == selection.session_code and s['slide_number'] == selection.slide_number:
                            state.current_selection = {
                                "session_code": selection.session_code,
                                "slide_number": selection.slide_number,
                                "reason": selection.reason,
                                "slide_data": s
                            }
                            logger.info(f"Selection found in all_slides")
                            break
        except Exception as e:
            logger.warning(f"Offer agent failed: {e}")
            import traceback
            traceback.print_exc()
        
        if state.current_selection:
            state.phase = "critique"
        else:
            # Failed to select - if we have candidates, just pick the first one
            if state.current_candidates:
                first = state.current_candidates[0]
                state.current_selection = {
                    "session_code": first['session_code'],
                    "slide_number": first['slide_number'],
                    "reason": "Auto-selected top search result",
                    "slide_data": first
                }
                logger.info(f"Fallback: auto-selected first candidate")
                state.phase = "critique"
            else:
                # No candidates at all
                state.current_attempt += 1
                state.phase = "search"
        
        await ctx.send_message(state)
    
    def _build_context(self, item: SlideOutlineItem, outline: PresentationOutline) -> str:
        return f"""PRESENTATION: {outline.title}
Narrative: {outline.narrative}

SLIDE REQUIREMENT:
Position: {item.position} of {len(outline.slides)}
Topic: {item.topic}
Purpose: {item.purpose}
Search Hints: {', '.join(item.search_hints)}"""

    def _build_prompt(self, context: str, candidates: list[dict], history: list[dict]) -> str:
        candidates_text = format_candidates(candidates)
        prompt = f"""{context}

CANDIDATES:
{candidates_text}

Slide images are attached below."""

        if history:
            prompt += "\n\nPREVIOUS ATTEMPTS (avoid these issues):\n"
            for h in history:
                prompt += f"- {h['selected']['session_code']} #{h['selected']['slide_number']}: {h['critique']['feedback']}\n"
        
        prompt += "\n\nSelect the BEST matching slide."
        return prompt
