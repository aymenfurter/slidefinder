"""Judge executor for the slide selection workflow."""
import logging
from agent_framework import ChatAgent, Executor, WorkflowContext, handler
from ..helpers import build_multimodal_message
from ..models import SlideSelection
from ..state import SlideSelectionState
from .constants import build_slide_display_key, WorkflowPhase
from .base import build_selection_dict, timed_operation, transition_to_phase, find_matching_slide

logger = logging.getLogger(__name__)


class JudgeExecutor(Executor):
    """Final arbiter that picks the best slide from all attempted candidates."""

    def __init__(self, judge_agent: ChatAgent, id: str = "judge"):
        super().__init__(id=id)
        self._judge_agent = judge_agent
    
    @handler
    async def handle(self, state: SlideSelectionState,
                     ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]) -> None:
        """Pick the best slide from all previous attempts."""
        candidate_count = len(state.conversation_history)
        state.debug.judge_started(state.position, candidate_count)
        state.debug.judge_ui_started(state.position, candidate_count)
        
        tried_slides = self._collect_tried_slides(state)
        if tried_slides:
            await self._execute_judgment(state, tried_slides)
        await self._complete_workflow(state, ctx)

    def _collect_tried_slides(self, state: SlideSelectionState) -> list[dict]:
        """Collect all slides that were tried during the workflow."""
        tried_slides = []
        for entry in state.conversation_history:
            info = entry["selected"]
            if slide := find_matching_slide(info["session_code"], info["slide_number"], state.all_slides):
                tried_slides.append({**slide, "attempt_reason": info["reason"],
                                     "critique_feedback": entry["critique"]["feedback"]})
        return tried_slides
    
    async def _execute_judgment(self, state: SlideSelectionState, tried_slides: list[dict]) -> None:
        """Execute the LLM-based final judgment."""
        prompt = self._build_judgment_prompt(state, tried_slides)
        message = build_multimodal_message(prompt, tried_slides, include_images=True)
        state.debug.judge_llm_started(state.position, len(tried_slides), prompt)
        
        with timed_operation() as timing:
            try:
                response = await self._judge_agent.run([message], response_format=SlideSelection)
                if response.value:
                    state.debug.judge_llm_completed(state.position, response.value.session_code,
                                                    response.value.slide_number, timing["duration_ms"])
                    state.debug.judge_invoked(state.position, len(tried_slides),
                                              response.value.session_code, response.value.slide_number,
                                              response.value.reason or "")
                    self._apply_selection(state, tried_slides, response.value)
            except Exception as error:
                logger.warning("Judge failed: %s", error)
                state.debug.llm_call_failed("JudgeAgent", timing["duration_ms"], str(error), state.position)

    def _build_judgment_prompt(self, state: SlideSelectionState, tried_slides: list[dict]) -> str:
        lines = []
        for i, slide in enumerate(tried_slides, 1):
            key = build_slide_display_key(slide["session_code"], slide["slide_number"])
            lines.append(f"CANDIDATE {i}: {key} - {slide.get('title', '')}")
            lines.append(f"  Feedback: {slide.get('critique_feedback', '')}")
        return f"""Pick the BEST slide for:
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

{chr(10).join(lines)}

Pick ONE slide (the least problematic option)."""

    def _apply_selection(self, state: SlideSelectionState, tried_slides: list[dict], selection: SlideSelection) -> None:
        if slide := find_matching_slide(selection.session_code, selection.slide_number, tried_slides):
            state.selected_slide = build_selection_dict(session_code=slide["session_code"],
                                                         slide_number=slide["slide_number"],
                                                         reason=f"Judge selected: {selection.reason or ''}",
                                                         title=slide.get("title", ""))
    
    async def _complete_workflow(self, state: SlideSelectionState, ctx: WorkflowContext) -> None:
        selected_key = (build_slide_display_key(state.selected_slide["session_code"], state.selected_slide["slide_number"])
                        if state.selected_slide else "none")
        transition_to_phase(state, "judge", WorkflowPhase.DONE, f"selected={selected_key}")
        await ctx.yield_output(state)
