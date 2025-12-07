"""Critique executor for the slide selection workflow."""

import logging

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from ..helpers import build_multimodal_message
from ..models import CritiqueResult
from ..state import SlideSelectionState

logger = logging.getLogger(__name__)

MAX_CRITIQUE_ATTEMPTS = 15


class CritiqueExecutor(Executor):
    """Agent evaluates whether the selected slide is appropriate."""
    
    def __init__(self, critique_agent: ChatAgent, id: str = "critique"):
        super().__init__(id=id)
        self._critique_agent = critique_agent
    
    @handler
    async def handle(self, state: SlideSelectionState, ctx: WorkflowContext[SlideSelectionState, SlideSelectionState]) -> None:
        """Critique the selected slide."""
        if not state.current_selection:
            state.phase = "search"
            state.current_attempt += 1
            await ctx.send_message(state)
            return
        
        slide = state.current_selection["slide_data"]
        
        previous_searches_text = ""
        if state.previous_searches:
            previous_searches_text = f"\n\nPREVIOUS SEARCHES TRIED (do NOT suggest these again):\n- " + "\n- ".join(state.previous_searches)
        
        prompt = f"""PRESENTATION: {state.full_outline.title}

SLIDE REQUIREMENT:
Position: {state.outline_item.position}
Topic: {state.outline_item.topic}
Purpose: {state.outline_item.purpose}

SELECTED SLIDE:
Session: {slide.get('session_code')} Slide #{slide.get('slide_number')}
Title: {slide.get('title', '')}
Content: {slide.get('content', slide.get('slide_text', ''))[:500]}

Selection Reason: {state.current_selection.get('reason', '')}
{previous_searches_text}

Does this slide match the topic? If rejecting, suggest a DIFFERENT 2-4 word search using specific service names (e.g., AKS, Container Apps, Functions, App Service, Cosmos DB)."""

        message = build_multimodal_message(prompt, [slide], include_images=True)
        
        critique = CritiqueResult(approved=True, feedback="Unable to critique", issues=[])
        
        try:
            response = await self._critique_agent.run([message], response_format=CritiqueResult)
            if response.value:
                critique = response.value
        except Exception as e:
            logger.warning(f"Critique failed: {e}")
        
        # Record attempt
        state.conversation_history.append({
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
        })
        
        # Emit event immediately for real-time streaming
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
        
        if critique.approved:
            # Success!
            state.selected_slide = {
                "session_code": slide["session_code"],
                "slide_number": slide["slide_number"],
                "reason": state.current_selection.get("reason", ""),
                "title": slide.get("title", "")
            }
            state.phase = "done"
            
            logger.info(
                f"Slide approved for position {state.outline_item.position} "
                f"on attempt {state.current_attempt + 1}"
            )
            # Yield the final state as workflow output
            await ctx.yield_output(state)
            return
        else:
            # Rejected - mark as used and try again
            state.already_selected_keys.add(f"{slide['session_code']}_{slide['slide_number']}")
            state.current_selection = None
            state.current_attempt += 1
            
            if state.current_attempt >= MAX_CRITIQUE_ATTEMPTS:
                state.phase = "judge"
            else:
                state.phase = "search"
            
            logger.info(
                f"Slide rejected for position {state.outline_item.position}: "
                f"{critique.feedback[:100]}"
            )
        
        await ctx.send_message(state)
