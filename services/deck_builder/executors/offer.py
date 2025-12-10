"""Offer executor for the slide selection workflow."""
import logging
from typing import Optional
from agent_framework import ChatAgent, Executor, WorkflowContext, handler
from ..helpers import build_multimodal_message, format_candidates
from ..models import SlideSelection
from ..state import SlideSelectionState
from .constants import MAX_CRITIQUE_ATTEMPTS, MAX_CANDIDATES_FOR_SELECTION, WorkflowPhase
from .base import build_selection_dict, has_exceeded_max_attempts, transition_to_phase, timed_operation, find_matching_slide

logger = logging.getLogger(__name__)


class OfferExecutor(Executor):
    """Selects the best slide from candidates using an LLM agent."""

    def __init__(self, offer_agent: ChatAgent, id: str = "offer"):
        super().__init__(id=id)
        self._offer_agent = offer_agent
    
    @handler
    async def handle(self, state: SlideSelectionState,
                     ctx: WorkflowContext[SlideSelectionState]) -> None:
        """Select a slide from candidates."""
        state.debug.offer_started(state.position, state.current_attempt + 1, len(state.current_candidates))
        
        if has_exceeded_max_attempts(state, MAX_CRITIQUE_ATTEMPTS):
            transition_to_phase(state, "offer", WorkflowPhase.JUDGE, f"max_attempts={MAX_CRITIQUE_ATTEMPTS}")
            await ctx.send_message(state)
            return
        if not state.current_candidates:
            transition_to_phase(state, "offer", WorkflowPhase.DONE, "no_candidates")
            await ctx.send_message(state)
            return
        
        await self._execute_selection(state)
        await self._handle_selection_result(state, ctx)

    async def _execute_selection(self, state: SlideSelectionState) -> None:
        """Execute the LLM-based slide selection."""
        candidates = state.current_candidates[:MAX_CANDIDATES_FOR_SELECTION]
        prompt = self._build_selection_prompt(state, candidates)
        message = build_multimodal_message(prompt, candidates, include_images=True)
        
        logger.info("OfferExecutor: %d candidates for position %d", len(candidates), state.position)
        state.debug.offer_llm_started(state.position, prompt)
        state.current_selection = None
        
        with timed_operation() as timing:
            try:
                response = await self._offer_agent.run([message], response_format=SlideSelection)
                self._handle_successful_response(state, response.value, timing["duration_ms"])
            except Exception as error:
                self._handle_failed_response(state, error, timing["duration_ms"])

    def _handle_successful_response(self, state: SlideSelectionState,
                                     selection: Optional[SlideSelection], duration_ms: int) -> None:
        if not selection:
            return
        logger.info("Offer agent selected: %s #%d", selection.session_code, selection.slide_number)
        state.debug.offer_llm_completed(state.position, selection.session_code,
                                        selection.slide_number, selection.reason, duration_ms)
        if validated := self._validate_selection(selection, state):
            state.current_selection = validated
            state.debug.slide_offered(state.position, selection.session_code,
                                       selection.slide_number, selection.reason)

    def _handle_failed_response(self, state: SlideSelectionState, error: Exception, duration_ms: int) -> None:
        logger.warning("Offer agent failed: %s", error)
        state.debug.llm_call_failed("OfferAgent", duration_ms, str(error), state.position)
    
    def _validate_selection(self, selection: SlideSelection,
                             state: SlideSelectionState) -> Optional[dict]:
        """Check that the selected slide exists in candidates."""
        slide_data = (find_matching_slide(selection.session_code, selection.slide_number, state.current_candidates)
                      or find_matching_slide(selection.session_code, selection.slide_number, state.all_slides))
        if not slide_data:
            return None
        return build_selection_dict(session_code=selection.session_code, slide_number=selection.slide_number,
                                     reason=selection.reason, slide_data=slide_data)

    async def _handle_selection_result(self, state: SlideSelectionState,
                                        ctx: WorkflowContext[SlideSelectionState]) -> None:
        if state.current_selection:
            sel = state.current_selection
            transition_to_phase(state, "offer", WorkflowPhase.CRITIQUE, f"selected {sel['session_code']}#{sel['slide_number']}")
        else:
            state.current_attempt += 1
            transition_to_phase(state, "offer", WorkflowPhase.SEARCH, "no_selection")
        await ctx.send_message(state)
    
    def _build_selection_prompt(self, state: SlideSelectionState, candidates: list[dict]) -> str:
        item, outline = state.outline_item, state.full_outline
        context = f"""PRESENTATION: {outline.title}
Narrative: {outline.narrative}

SLIDE REQUIREMENT:
Position: {item.position} of {len(outline.slides)}
Topic: {item.topic}
Purpose: {item.purpose}
Search Hints: {', '.join(item.search_hints)}"""
        prompt = f"{context}\n\nCANDIDATES:\n{format_candidates(candidates)}\n\nSlide images are attached below."
        if state.conversation_history:
            lines = ["\n\nPREVIOUS ATTEMPTS (avoid these issues):"]
            for a in state.conversation_history:
                lines.append(f"- {a['selected']['session_code']} #{a['selected']['slide_number']}: {a['critique']['feedback']}")
            prompt += "\n".join(lines)
        return prompt + "\n\nSelect the BEST matching slide."
