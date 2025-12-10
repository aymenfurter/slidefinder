"""Search executor for the slide selection workflow."""
import logging
from typing import Any
from agent_framework import Executor, WorkflowContext, handler
from services.search_service import get_search_service
from ..state import SlideSelectionState
from .constants import MAX_SEARCH_RESULTS, DEBUG_PREVIEW_COUNT, build_slide_key, WorkflowPhase
from .base import transition_to_phase

logger = logging.getLogger(__name__)


class SearchExecutor(Executor):
    """Searches for candidate slides based on the current query."""

    def __init__(self, id: str = "search"):
        super().__init__(id=id)
        self._search_service = get_search_service()
    
    @handler
    async def handle(self, state: SlideSelectionState,
                     ctx: WorkflowContext[SlideSelectionState]) -> None:
        """Execute the search phase."""
        state.debug.search_started(state.position, state.current_attempt + 1, state.outline_item.topic)
        
        query = self._determine_search_query(state)
        self._track_query(state, query)
        state.current_candidates = self._search_and_filter(state, query)
        
        logger.info("Search '%s' returned %d candidates for position %d",
                    query, len(state.current_candidates), state.position)
        state.debug.search_results(state.position, query, state.current_candidates,
                                   state.previous_searches, DEBUG_PREVIEW_COUNT)
        
        await self._transition_to_next_phase(state, ctx)

    def _determine_search_query(self, state: SlideSelectionState) -> str:
        """Determine the search query based on current state."""
        if state.current_attempt == 0:
            hints = state.outline_item.search_hints
            return hints[0] if hints else state.outline_item.topic
        if crit := self._get_unused_critique_suggestion(state):
            return crit
        return self._get_next_hint(state) or state.outline_item.topic
    
    def _get_unused_critique_suggestion(self, state: SlideSelectionState) -> str | None:
        """Get search suggestion from last critique if not already tried."""
        if not state.conversation_history:
            return None
        suggestion = state.conversation_history[-1].get("critique", {}).get("search_suggestion", "")
        if not suggestion:
            return None
        return None if suggestion.lower() in {q.lower() for q in state.previous_searches} else suggestion

    def _get_next_hint(self, state: SlideSelectionState) -> str | None:
        """Get the next search hint by cycling through available hints."""
        hints = state.outline_item.search_hints
        return hints[state.current_attempt % len(hints)] if hints else None

    def _track_query(self, state: SlideSelectionState, query: str) -> None:
        """Record the query in state to prevent duplicates."""
        state.current_search_query = query
        if query not in state.previous_searches:
            state.previous_searches.append(query)

    def _search_and_filter(self, state: SlideSelectionState, query: str) -> list[dict[str, Any]]:
        """Execute search and filter out already-selected slides."""
        raw_results, _ = self._search_service.search(query, limit=MAX_SEARCH_RESULTS, include_pptx_status=True)
        return [r.model_dump() for r in raw_results
                if build_slide_key(r.session_code, r.slide_number) not in state.already_selected_keys]

    async def _transition_to_next_phase(self, state: SlideSelectionState,
                                         ctx: WorkflowContext[SlideSelectionState]) -> None:
        """Transition to 'offer' if candidates found, 'done' otherwise."""
        next_phase = WorkflowPhase.OFFER if state.current_candidates else WorkflowPhase.DONE
        transition_to_phase(state, "search", next_phase, f"found {len(state.current_candidates)} candidates")
        await ctx.send_message(state)
