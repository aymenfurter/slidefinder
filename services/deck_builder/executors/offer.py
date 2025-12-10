"""Offer executor for the slide selection workflow."""

import logging
from typing import Optional

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message, format_candidates
from ..models import SlideOutlineItem, PresentationOutline, SlideSelection
from ..state import SlideSelectionState
from .constants import MAX_CRITIQUE_ATTEMPTS, MAX_CANDIDATES_FOR_SELECTION
from .base import (
    build_selection_dict,
    has_exceeded_max_attempts,
    transition_to_phase,
    timed_operation,
)

logger = logging.getLogger(__name__)


class OfferExecutor(Executor):
    """Selects the best slide from candidates using an LLM agent."""
    
    def __init__(self, offer_agent: ChatAgent, id: str = "offer"):
        super().__init__(id=id)
        self._offer_agent = offer_agent
    
    # =========================================================================
    # Main Handler
    # =========================================================================
    
    @handler
    async def handle(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState]
    ) -> None:
        """Select a slide from candidates."""
        self._emit_started_event(state)
        
        if has_exceeded_max_attempts(state, MAX_CRITIQUE_ATTEMPTS):
            transition_to_phase(state, "offer", "judge", f"max_attempts={MAX_CRITIQUE_ATTEMPTS}")
            await ctx.send_message(state)
            return
        
        if not state.current_candidates:
            transition_to_phase(state, "offer", "done", "no_candidates")
            await ctx.send_message(state)
            return
        
        await self._execute_selection(state)
        await self._handle_selection_result(state, ctx)
    
    # =========================================================================
    # Selection Logic
    # =========================================================================
    
    async def _execute_selection(self, state: SlideSelectionState) -> None:
        """Execute the LLM-based slide selection."""
        candidates = state.current_candidates[:MAX_CANDIDATES_FOR_SELECTION]
        prompt = self._build_selection_prompt(state, candidates)
        message = build_multimodal_message(prompt, candidates, include_images=True)
        
        self._log_selection_start(state, candidates)
        self._emit_llm_start_event(state, prompt)
        
        state.current_selection = None
        
        with timed_operation() as timing:
            try:
                selection = await self._call_agent(message)
                self._handle_successful_response(state, selection, timing["duration_ms"])
            except Exception as error:
                self._handle_failed_response(state, error, timing["duration_ms"])
    
    async def _call_agent(self, message) -> Optional[SlideSelection]:
        """Call the offer agent and extract the response."""
        response = await self._offer_agent.run([message], response_format=SlideSelection)
        return response.value if response.value else None
    
    def _handle_successful_response(
        self,
        state: SlideSelectionState,
        selection: Optional[SlideSelection],
        duration_ms: int
    ) -> None:
        """Process a successful LLM response."""
        if not selection:
            return
        
        logger.info(
            "Offer agent selected: %s #%d",
            selection.session_code,
            selection.slide_number
        )
        
        self._emit_llm_complete_event(state, selection, duration_ms)
        
        validated_selection = self._validate_selection(selection, state)
        if validated_selection:
            state.current_selection = validated_selection
            self._emit_slide_offered_event(state, selection)
    
    def _handle_failed_response(
        self,
        state: SlideSelectionState,
        error: Exception,
        duration_ms: int
    ) -> None:
        """Handle LLM call failure."""
        logger.warning("Offer agent failed: %s", error)
        state.debug.llm_call_failed(
            "OfferAgent",
            duration_ms,
            str(error),
            state.outline_item.position
        )
    
    # =========================================================================
    # Selection Validation
    # =========================================================================
    
    def _validate_selection(
        self,
        selection: SlideSelection,
        state: SlideSelectionState
    ) -> Optional[dict]:
        """Check that the selected slide exists in candidates."""
        slide_data = self._find_slide_in_list(
            selection.session_code,
            selection.slide_number,
            state.current_candidates
        ) or self._find_slide_in_list(
            selection.session_code,
            selection.slide_number,
            state.all_slides
        )
        
        if not slide_data:
            return None
        
        return build_selection_dict(
            session_code=selection.session_code,
            slide_number=selection.slide_number,
            reason=selection.reason,
            slide_data=slide_data
        )
    
    def _find_slide_in_list(
        self,
        session_code: str,
        slide_number: int,
        slides: list[dict]
    ) -> Optional[dict]:
        """Find a slide by session code and number in a list."""
        for slide in slides:
            if (slide["session_code"] == session_code and 
                slide["slide_number"] == slide_number):
                return slide
        return None
    
    # =========================================================================
    # Result Handling
    # =========================================================================
    
    async def _handle_selection_result(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState]
    ) -> None:
        """Transition based on selection result."""
        if state.current_selection:
            self._transition_to_critique(state)
        else:
            state.current_attempt += 1
            transition_to_phase(state, "offer", "search", "no_selection")
        
        await ctx.send_message(state)
    
    def _transition_to_critique(self, state: SlideSelectionState) -> None:
        """Transition to critique phase."""
        selection = state.current_selection
        slide_key = f"{selection['session_code']}#{selection['slide_number']}"
        transition_to_phase(state, "offer", "critique", f"selected {slide_key}")
    
    # =========================================================================
    # Prompt Building
    # =========================================================================
    
    def _build_selection_prompt(
        self,
        state: SlideSelectionState,
        candidates: list[dict]
    ) -> str:
        """Build the complete prompt for slide selection."""
        context = self._format_presentation_context(
            state.outline_item,
            state.full_outline
        )
        candidates_text = format_candidates(candidates)
        
        prompt = f"""{context}

CANDIDATES:
{candidates_text}

Slide images are attached below."""
        
        if state.conversation_history:
            prompt += self._format_previous_attempts(state.conversation_history)
        
        prompt += "\n\nSelect the BEST matching slide."
        return prompt
    
    def _format_presentation_context(
        self,
        item: SlideOutlineItem,
        outline: PresentationOutline
    ) -> str:
        """Format the presentation context for the prompt."""
        return f"""PRESENTATION: {outline.title}
Narrative: {outline.narrative}

SLIDE REQUIREMENT:
Position: {item.position} of {len(outline.slides)}
Topic: {item.topic}
Purpose: {item.purpose}
Search Hints: {', '.join(item.search_hints)}"""
    
    def _format_previous_attempts(self, history: list[dict]) -> str:
        """Format previous attempts as a warning section."""
        lines = ["\n\nPREVIOUS ATTEMPTS (avoid these issues):"]
        for attempt in history:
            selected = attempt["selected"]
            feedback = attempt["critique"]["feedback"]
            lines.append(
                f"- {selected['session_code']} #{selected['slide_number']}: {feedback}"
            )
        return "\n".join(lines)
    
    # =========================================================================
    # Logging and Events
    # =========================================================================
    
    def _emit_started_event(self, state: SlideSelectionState) -> None:
        """Emit debug event for executor start."""
        state.debug.executor_started(
            executor="offer",
            position=state.outline_item.position,
            attempt=state.current_attempt + 1,
            details={"candidate_count": len(state.current_candidates)}
        )
    
    def _emit_llm_start_event(self, state: SlideSelectionState, prompt: str) -> None:
        """Emit debug event for LLM call start."""
        state.debug.llm_call_started(
            agent="OfferAgent",
            task="Select best matching slide",
            prompt_preview=prompt,
            response_format="SlideSelection",
            position=state.outline_item.position
        )
    
    def _emit_llm_complete_event(
        self,
        state: SlideSelectionState,
        selection: SlideSelection,
        duration_ms: int
    ) -> None:
        """Emit debug event for successful LLM response."""
        state.debug.llm_call_completed(
            agent="OfferAgent",
            duration_ms=duration_ms,
            response_preview=f"Selected: {selection.session_code} #{selection.slide_number} - {selection.reason}",
            position=state.outline_item.position
        )
    
    def _emit_slide_offered_event(
        self,
        state: SlideSelectionState,
        selection: SlideSelection
    ) -> None:
        """Emit debug event for slide selection."""
        state.debug.slide_offered(
            position=state.outline_item.position,
            session_code=selection.session_code,
            slide_number=selection.slide_number,
            reason=selection.reason
        )
    
    def _log_selection_start(
        self,
        state: SlideSelectionState,
        candidates: list[dict]
    ) -> None:
        """Log the start of selection process."""
        logger.info(
            "OfferExecutor: %d candidates for position %d",
            len(candidates),
            state.outline_item.position
        )
