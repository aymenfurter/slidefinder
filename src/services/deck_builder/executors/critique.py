"""Critique executor for the slide selection workflow."""
import logging
from agent_framework import ChatAgent, Executor, WorkflowContext, handler
from ..helpers import build_multimodal_message
from ..models import CritiqueResult
from ..state import SlideSelectionState
from .constants import MAX_CRITIQUE_ATTEMPTS, PROMPT_CONTENT_LENGTH, WorkflowPhase
from .base import build_selection_dict, has_exceeded_max_attempts, transition_to_phase, mark_slide_as_tried, timed_operation

logger = logging.getLogger(__name__)


class CritiqueExecutor(Executor):
    """Evaluates whether the selected slide matches requirements."""

    def __init__(self, critique_agent: ChatAgent, id: str = "critique"):
        super().__init__(id=id)
        self._critique_agent = critique_agent
    
    @handler
    async def handle(self, state: SlideSelectionState,
                     ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]) -> None:
        """Critique the selected slide."""
        state.debug.critique_started(state.position, state.current_attempt + 1)
        
        slide = state.current_selection["slide_data"]
        critique = await self._execute_critique(state, slide)
        self._record_attempt(state, slide, critique)
        self._emit_critique_events(state, slide, critique)
        
        if critique.approved:
            await self._handle_approval(state, slide, ctx)
        else:
            await self._handle_rejection(state, slide, critique, ctx)

    async def _execute_critique(self, state: SlideSelectionState, slide: dict) -> CritiqueResult:
        """Execute the LLM-based slide critique."""
        prompt = self._build_critique_prompt(state, slide)
        message = build_multimodal_message(prompt, [slide], include_images=True)
        state.debug.critique_llm_started(state.position, slide.get("session_code"),
                                         slide.get("slide_number"), prompt)
        with timed_operation() as timing:
            response = await self._critique_agent.run([message], response_format=CritiqueResult)
            state.debug.critique_llm_completed(state.position, response.value.approved,
                                               response.value.feedback, timing["duration_ms"])
            return response.value
    
    def _build_critique_prompt(self, state: SlideSelectionState, slide: dict) -> str:
        """Build the critique evaluation prompt."""
        prev_searches = ""
        if state.previous_searches:
            prev_searches = f"\n\nPREVIOUS SEARCHES TRIED (do NOT suggest these again):\n- " + "\n- ".join(state.previous_searches)
        content = slide.get("content", slide.get("slide_text", ""))[:PROMPT_CONTENT_LENGTH]
        return f"""PRESENTATION: {state.full_outline.title}

SLIDE REQUIREMENT:
Position: {state.outline_item.position}
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

SELECTED SLIDE:
Session: {slide.get('session_code')} Slide #{slide.get('slide_number')}
Title: {slide.get('title', '')}
Content: {content}

Selection Reason: {state.current_selection.get('reason', '')}{prev_searches}

Does this slide match the topic? If rejecting, suggest a DIFFERENT 2-4 word search using specific service names (e.g., AKS, Container Apps, Functions, App Service, Cosmos DB)."""
    
    def _record_attempt(self, state: SlideSelectionState, slide: dict, critique: CritiqueResult) -> None:
        """Record the critique attempt in conversation history."""
        state.conversation_history.append({
            "attempt": state.current_attempt + 1,
            "search_query": state.current_search_query,
            "selected": {"session_code": slide["session_code"], "slide_number": slide["slide_number"],
                         "title": slide.get("title", ""), "reason": state.current_selection.get("reason", "")},
            "critique": {"approved": critique.approved, "feedback": critique.feedback,
                         "issues": critique.issues, "search_suggestion": critique.search_suggestion}
        })

    async def _handle_approval(self, state: SlideSelectionState, slide: dict, ctx: WorkflowContext) -> None:
        """Handle an approved slide - complete the workflow."""
        state.selected_slide = build_selection_dict(session_code=slide["session_code"],
                                                     slide_number=slide["slide_number"],
                                                     reason=state.current_selection.get("reason", ""),
                                                     title=slide.get("title", ""))
        transition_to_phase(state, "critique", WorkflowPhase.DONE, "approved")
        logger.info("Slide approved for position %d on attempt %d", state.position, state.current_attempt + 1)
        await ctx.yield_output(state)

    async def _handle_rejection(self, state: SlideSelectionState, slide: dict,
                                 critique: CritiqueResult, ctx: WorkflowContext) -> None:
        """Handle a rejected slide."""
        mark_slide_as_tried(state, slide)
        state.current_selection = None
        state.current_attempt += 1
        if has_exceeded_max_attempts(state, MAX_CRITIQUE_ATTEMPTS):
            transition_to_phase(state, "critique", WorkflowPhase.JUDGE, f"max_attempts={MAX_CRITIQUE_ATTEMPTS}")
        else:
            transition_to_phase(state, "critique", WorkflowPhase.SEARCH, f"rejected, suggestion={critique.search_suggestion or 'none'}")
        logger.info("Slide rejected for position %d: %s", state.position, critique.feedback[:100])
        await ctx.send_message(state)

    def _emit_critique_events(self, state: SlideSelectionState, slide: dict, critique: CritiqueResult) -> None:
        """Emit debug and UI events for the critique result."""
        state.debug.slide_critiqued(position=state.position, session_code=slide["session_code"],
                                     slide_number=slide["slide_number"], approved=critique.approved,
                                     feedback=critique.feedback, suggestion=critique.search_suggestion)
        state.debug.critique_attempt_ui(
            position=state.position, attempt=state.current_attempt + 1,
            query=state.current_search_query, candidate_count=len(state.current_candidates),
            slide=slide, selection_reason=state.current_selection.get("reason", ""),
            approved=critique.approved, feedback=critique.feedback, issues=critique.issues
        )
