"""Judge executor for the slide selection workflow."""

import logging
from typing import Optional

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message
from ..models import SlideSelection
from ..state import SlideSelectionState
from .constants import build_slide_display_key
from .base import build_selection_dict, timed_operation, transition_to_phase

logger = logging.getLogger(__name__)


class JudgeExecutor(Executor):
    """Final arbiter that picks the best slide from all attempted candidates."""
    
    def __init__(self, judge_agent: ChatAgent, id: str = "judge"):
        super().__init__(id=id)
        self._judge_agent = judge_agent
    
    # =========================================================================
    # Main Handler
    # =========================================================================
    
    @handler
    async def handle(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]
    ) -> None:
        """Pick the best slide from all previous attempts."""
        self._emit_started_event(state)
        self._emit_judge_start_ui_event(state)
        
        tried_slides = self._collect_tried_slides(state)
        
        if tried_slides:
            await self._execute_judgment(state, tried_slides)
        
        await self._complete_workflow(state, ctx)
    
    # =========================================================================
    # Slide Collection
    # =========================================================================
    
    def _collect_tried_slides(self, state: SlideSelectionState) -> list[dict]:
        """Collect all slides that were tried during the workflow."""
        tried_slides = []
        
        for history_entry in state.conversation_history:
            slide_info = history_entry["selected"]
            matching_slide = self._find_matching_slide(
                slide_info["session_code"],
                slide_info["slide_number"],
                state.all_slides
            )
            
            if matching_slide:
                enriched_slide = {
                    **matching_slide,
                    "attempt_reason": slide_info["reason"],
                    "critique_feedback": history_entry["critique"]["feedback"]
                }
                tried_slides.append(enriched_slide)
        
        return tried_slides
    
    def _find_matching_slide(
        self,
        session_code: str,
        slide_number: int,
        slides: list[dict]
    ) -> Optional[dict]:
        """Find a slide in the list by session code and number."""
        for slide in slides:
            if (slide["session_code"] == session_code and
                slide["slide_number"] == slide_number):
                return slide
        return None
    
    # =========================================================================
    # Judge Execution
    # =========================================================================
    
    async def _execute_judgment(
        self,
        state: SlideSelectionState,
        tried_slides: list[dict]
    ) -> None:
        """Execute the LLM-based final judgment."""
        prompt = self._build_judgment_prompt(state, tried_slides)
        message = build_multimodal_message(prompt, tried_slides, include_images=True)
        
        self._emit_llm_start_event(state, prompt, len(tried_slides))
        
        with timed_operation() as timing:
            try:
                response = await self._judge_agent.run(
                    [message],
                    response_format=SlideSelection
                )
                
                if response.value:
                    self._handle_successful_response(
                        state, tried_slides, response.value, timing["duration_ms"]
                    )
                    
            except Exception as error:
                logger.warning("Judge failed: %s", error)
                state.debug.llm_call_failed(
                    "JudgeAgent",
                    timing["duration_ms"],
                    str(error),
                    state.outline_item.position
                )
    
    def _handle_successful_response(
        self,
        state: SlideSelectionState,
        tried_slides: list[dict],
        selection: SlideSelection,
        duration_ms: int
    ) -> None:
        """Process a successful judge response."""
        self._emit_llm_complete_event(state, selection, duration_ms)
        self._emit_judge_result_event(state, tried_slides, selection)
        self._apply_selection(state, tried_slides, selection)
    
    # =========================================================================
    # Prompt Building
    # =========================================================================
    
    def _build_judgment_prompt(
        self,
        state: SlideSelectionState,
        tried_slides: list[dict]
    ) -> str:
        """Build the judge's selection prompt."""
        candidates_text = self._format_candidates_for_judgment(tried_slides)
        
        return f"""Pick the BEST slide for:
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

{candidates_text}

Pick ONE slide (the least problematic option)."""
    
    def _format_candidates_for_judgment(self, tried_slides: list[dict]) -> str:
        """Format all candidates with their feedback for the judge."""
        lines = []
        for index, slide in enumerate(tried_slides, start=1):
            slide_key = build_slide_display_key(
                slide["session_code"],
                slide["slide_number"]
            )
            title = slide.get("title", "")
            feedback = slide.get("critique_feedback", "")
            lines.append(f"CANDIDATE {index}: {slide_key} - {title}")
            lines.append(f"  Feedback: {feedback}")
        return "\n".join(lines)
    
    # =========================================================================
    # Selection Application
    # =========================================================================
    
    def _apply_selection(
        self,
        state: SlideSelectionState,
        tried_slides: list[dict],
        selection: SlideSelection
    ) -> None:
        """Apply the judge's selection to state."""
        matching_slide = self._find_matching_slide(
            selection.session_code,
            selection.slide_number,
            tried_slides
        )
        
        if matching_slide:
            state.selected_slide = build_selection_dict(
                session_code=matching_slide["session_code"],
                slide_number=matching_slide["slide_number"],
                reason=f"Judge selected: {selection.reason or ''}",
                title=matching_slide.get("title", "")
            )
    
    # =========================================================================
    # Workflow Completion
    # =========================================================================
    
    async def _complete_workflow(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext
    ) -> None:
        """Complete the workflow with final transition."""
        selected_key = self._get_selected_slide_key(state)
        transition_to_phase(state, "judge", "done", f"selected={selected_key}")
        await ctx.yield_output(state)
    
    def _get_selected_slide_key(self, state: SlideSelectionState) -> str:
        """Get the key for the selected slide, or 'none' if no selection."""
        if state.selected_slide:
            return build_slide_display_key(
                state.selected_slide["session_code"],
                state.selected_slide["slide_number"]
            )
        return "none"
    
    # =========================================================================
    # Logging and Events
    # =========================================================================
    
    def _emit_started_event(self, state: SlideSelectionState) -> None:
        """Emit debug event for executor start."""
        state.debug.executor_started(
            executor="judge",
            position=state.outline_item.position,
            candidate_count=len(state.conversation_history)
        )
    
    def _emit_judge_start_ui_event(self, state: SlideSelectionState) -> None:
        """Emit UI event for judge start."""
        state.emit_event({
            "type": "llm_judge_start",
            "position": state.outline_item.position,
            "candidate_count": len(state.conversation_history),
            "message": (
                f"Max attempts reached. Judge selecting best from "
                f"{len(state.conversation_history)} candidates..."
            )
        })
    
    def _emit_llm_start_event(
        self,
        state: SlideSelectionState,
        prompt: str,
        candidate_count: int
    ) -> None:
        """Emit debug event for LLM call start."""
        state.debug.llm_call_started(
            agent="JudgeAgent",
            task=f"Final selection from {candidate_count} candidates",
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
            agent="JudgeAgent",
            duration_ms=duration_ms,
            response_preview=f"Selected: {selection.session_code} #{selection.slide_number}",
            position=state.outline_item.position
        )
    
    def _emit_judge_result_event(
        self,
        state: SlideSelectionState,
        tried_slides: list[dict],
        selection: SlideSelection
    ) -> None:
        """Emit debug event for judge decision."""
        state.debug.judge_invoked(
            position=state.outline_item.position,
            candidates_count=len(tried_slides),
            selected_code=selection.session_code,
            selected_number=selection.slide_number,
            reason=selection.reason or ""
        )
