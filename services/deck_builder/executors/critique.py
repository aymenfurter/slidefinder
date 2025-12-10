"""Critique executor for the slide selection workflow."""

import logging

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message
from ..models import CritiqueResult
from ..state import SlideSelectionState
from .constants import MAX_CRITIQUE_ATTEMPTS, PROMPT_CONTENT_LENGTH
from .base import (
    build_selection_dict,
    has_exceeded_max_attempts,
    transition_to_phase,
    mark_slide_as_tried,
    timed_operation,
)

logger = logging.getLogger(__name__)


class CritiqueExecutor(Executor):
    """Evaluates whether the selected slide matches requirements."""
    
    def __init__(self, critique_agent: ChatAgent, id: str = "critique"):
        super().__init__(id=id)
        self._critique_agent = critique_agent
    
    # =========================================================================
    # Main Handler
    # =========================================================================
    
    @handler
    async def handle(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]
    ) -> None:
        """Critique the selected slide."""
        self._emit_started_event(state)
        
        slide = state.current_selection["slide_data"]
        
        # Execute critique
        critique = await self._execute_critique(state, slide)
        
        # Record attempt
        self._record_attempt(state, slide, critique)
        self._emit_critique_events(state, slide, critique)
        
        # Handle result
        if critique.approved:
            await self._handle_approval(state, slide, ctx)
        else:
            await self._handle_rejection(state, slide, critique, ctx)
    
    # =========================================================================
    # Critique Execution
    # =========================================================================
    
    async def _execute_critique(
        self,
        state: SlideSelectionState,
        slide: dict
    ) -> CritiqueResult:
        """Execute the LLM-based slide critique."""
        prompt = self._build_critique_prompt(state, slide)
        message = build_multimodal_message(prompt, [slide], include_images=True)
        
        self._emit_llm_start_event(state, slide, prompt)
        
        with timed_operation() as timing:
            response = await self._critique_agent.run(
                [message],
                response_format=CritiqueResult
            )
            self._emit_llm_complete_event(state, response.value, timing["duration_ms"])
            return response.value
    
    # =========================================================================
    # Prompt Building
    # =========================================================================
    
    def _build_critique_prompt(
        self,
        state: SlideSelectionState,
        slide: dict
    ) -> str:
        """Build the critique evaluation prompt."""
        previous_searches_section = self._format_previous_searches(state)
        slide_content = self._truncate_content(slide)
        
        return f"""PRESENTATION: {state.full_outline.title}

SLIDE REQUIREMENT:
Position: {state.outline_item.position}
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

SELECTED SLIDE:
Session: {slide.get('session_code')} Slide #{slide.get('slide_number')}
Title: {slide.get('title', '')}
Content: {slide_content}

Selection Reason: {state.current_selection.get('reason', '')}
{previous_searches_section}

Does this slide match the topic? If rejecting, suggest a DIFFERENT 2-4 word search using specific service names (e.g., AKS, Container Apps, Functions, App Service, Cosmos DB)."""
    
    def _format_previous_searches(self, state: SlideSelectionState) -> str:
        """Format previous searches as a warning section."""
        if not state.previous_searches:
            return ""
        
        searches = "\n- ".join(state.previous_searches)
        return f"\n\nPREVIOUS SEARCHES TRIED (do NOT suggest these again):\n- {searches}"
    
    def _truncate_content(self, slide: dict) -> str:
        """Get slide content, truncated to reasonable length."""
        content = slide.get("content", slide.get("slide_text", ""))
        return content[:PROMPT_CONTENT_LENGTH]
    
    # =========================================================================
    # History Recording
    # =========================================================================
    
    def _record_attempt(
        self,
        state: SlideSelectionState,
        slide: dict,
        critique: CritiqueResult
    ) -> None:
        """Record the critique attempt in conversation history."""
        attempt_record = {
            "attempt": state.current_attempt + 1,
            "search_query": state.current_search_query,
            "selected": {
                "session_code": slide["session_code"],
                "slide_number": slide["slide_number"],
                "title": slide.get("title", ""),
                "reason": state.current_selection.get("reason", "")
            },
            "critique": {
                "approved": critique.approved,
                "feedback": critique.feedback,
                "issues": critique.issues,
                "search_suggestion": critique.search_suggestion
            }
        }
        state.conversation_history.append(attempt_record)
    
    # =========================================================================
    # Result Handling
    # =========================================================================
    
    async def _handle_approval(
        self,
        state: SlideSelectionState,
        slide: dict,
        ctx: WorkflowContext
    ) -> None:
        """Handle an approved slide - complete the workflow."""
        state.selected_slide = build_selection_dict(
            session_code=slide["session_code"],
            slide_number=slide["slide_number"],
            reason=state.current_selection.get("reason", ""),
            title=slide.get("title", "")
        )
        
        transition_to_phase(state, "critique", "done", "approved")
        
        logger.info(
            "Slide approved for position %d on attempt %d",
            state.outline_item.position,
            state.current_attempt + 1
        )
        
        await ctx.yield_output(state)
    
    async def _handle_rejection(
        self,
        state: SlideSelectionState,
        slide: dict,
        critique: CritiqueResult,
        ctx: WorkflowContext
    ) -> None:
        """Handle a rejected slide."""
        mark_slide_as_tried(state, slide)
        state.current_selection = None
        state.current_attempt += 1
        
        if has_exceeded_max_attempts(state, MAX_CRITIQUE_ATTEMPTS):
            transition_to_phase(state, "critique", "judge", f"max_attempts={MAX_CRITIQUE_ATTEMPTS}")
        else:
            suggestion = critique.search_suggestion or "none"
            transition_to_phase(state, "critique", "search", f"rejected, suggestion={suggestion}")
        
        logger.info(
            "Slide rejected for position %d: %s",
            state.outline_item.position,
            critique.feedback[:100]
        )
        
        await ctx.send_message(state)
    
    # =========================================================================
    # Logging and Events
    # =========================================================================
    
    def _emit_started_event(self, state: SlideSelectionState) -> None:
        """Emit debug event for executor start."""
        state.debug.executor_started(
            executor="critique",
            position=state.outline_item.position,
            attempt=state.current_attempt + 1
        )
    
    def _emit_llm_start_event(
        self,
        state: SlideSelectionState,
        slide: dict,
        prompt: str
    ) -> None:
        """Emit debug event for LLM call start."""
        state.debug.llm_call_started(
            agent="CritiqueAgent",
            task=f"Evaluate slide {slide.get('session_code')} #{slide.get('slide_number')}",
            prompt_preview=prompt,
            response_format="CritiqueResult",
            position=state.outline_item.position
        )
    
    def _emit_llm_complete_event(
        self,
        state: SlideSelectionState,
        critique: CritiqueResult,
        duration_ms: int
    ) -> None:
        """Emit debug event for successful LLM response."""
        status = "✅ Approved" if critique.approved else "❌ Rejected"
        state.debug.llm_call_completed(
            agent="CritiqueAgent",
            duration_ms=duration_ms,
            response_preview=f"{status}: {critique.feedback}",
            position=state.outline_item.position
        )
    
    def _emit_critique_events(
        self,
        state: SlideSelectionState,
        slide: dict,
        critique: CritiqueResult
    ) -> None:
        """Emit debug and UI events for the critique result."""
        # Debug event
        state.debug.slide_critiqued(
            position=state.outline_item.position,
            session_code=slide["session_code"],
            slide_number=slide["slide_number"],
            approved=critique.approved,
            feedback=critique.feedback,
            suggestion=critique.search_suggestion
        )
        
        # UI event for real-time feedback
        state.emit_event({
            "type": "critique_attempt",
            "position": state.outline_item.position,
            "attempt": state.current_attempt + 1,
            "search_query": state.current_search_query,
            "result_count": len(state.current_candidates),
            "slide_code": slide["session_code"],
            "slide_number": slide["slide_number"],
            "slide_title": slide.get("title", ""),
            "thumbnail_url": f"/thumbnails/{slide['session_code']}_{slide['slide_number']}.png",
            "selection_reason": state.current_selection.get("reason", ""),
            "approved": critique.approved,
            "feedback": critique.feedback,
            "issues": critique.issues
        })
