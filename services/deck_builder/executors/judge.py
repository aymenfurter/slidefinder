"""Judge executor for the slide selection workflow."""

import logging

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message
from ..models import SlideSelection
from ..state import SlideSelectionState

logger = logging.getLogger(__name__)


class JudgeExecutor(Executor):
    """Final arbiter when max attempts reached - picks best from all tried."""
    
    def __init__(self, judge_agent: ChatAgent, id: str = "judge"):
        super().__init__(id=id)
        self._judge_agent = judge_agent
    
    @handler
    async def handle(self, state: SlideSelectionState, ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]) -> None:
        """Pick the best slide from all attempts."""
        state.emit_event({
            "type": "llm_judge_start",
            "position": state.outline_item.position,
            "candidate_count": len(state.conversation_history),
            "message": f"Max attempts reached. Judge selecting best from {len(state.conversation_history)} candidates..."
        })
        
        if not state.conversation_history:
            state.phase = "done"
            await ctx.yield_output(state)
            return
        
        # Collect all tried slides
        tried_slides = []
        for h in state.conversation_history:
            info = h["selected"]
            for s in state.all_slides:
                if s["session_code"] == info["session_code"] and s["slide_number"] == info["slide_number"]:
                    tried_slides.append({
                        **s,
                        "attempt_reason": info["reason"],
                        "critique_feedback": h["critique"]["feedback"]
                    })
                    break
        
        if not tried_slides:
            state.phase = "done"
            await ctx.yield_output(state)
            return
        
        # Build judge prompt
        candidates_text = "\n".join([
            f"CANDIDATE {i}: {s['session_code']} #{s['slide_number']} - {s.get('title', '')}\n  Feedback: {s.get('critique_feedback', '')}"
            for i, s in enumerate(tried_slides, 1)
        ])
        
        prompt = f"""Pick the BEST slide for:
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

{candidates_text}

Pick ONE slide (the least problematic option)."""

        message = build_multimodal_message(prompt, tried_slides, include_images=True)
        
        try:
            response = await self._judge_agent.run([message], response_format=SlideSelection)
            if response.value:
                selection = response.value
                for s in tried_slides:
                    if s["session_code"] == selection.session_code and s["slide_number"] == selection.slide_number:
                        state.selected_slide = {
                            "session_code": s["session_code"],
                            "slide_number": s["slide_number"],
                            "reason": f"Judge selected: {selection.reason or ''}",
                            "title": s.get("title", "")
                        }
                        break
        except Exception as e:
            logger.warning(f"Judge failed: {e}")
        
        # Fallback to last attempted
        if not state.selected_slide and state.conversation_history:
            last = state.conversation_history[-1]["selected"]
            state.selected_slide = {
                "session_code": last["session_code"],
                "slide_number": last["slide_number"],
                "reason": f"Fallback: {last['reason']}",
                "title": last.get("title", "")
            }
        
        state.phase = "done"
        # Yield the final state as workflow output
        await ctx.yield_output(state)
