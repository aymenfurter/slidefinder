"""Search executor for the slide selection workflow."""

import logging
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from models.slide import SlideSearchResult
from services.search_service import get_search_service

from ..state import SlideSelectionState
from .constants import (
    MAX_SEARCH_RESULTS,
    DEBUG_PREVIEW_COUNT,
    build_slide_key,
)
from .base import transition_to_phase

logger = logging.getLogger(__name__)


class SearchExecutor(Executor):
    """Searches for candidate slides based on the current query."""
    
    def __init__(self, id: str = "search"):
        super().__init__(id=id)
        self._search_service = get_search_service()
    
    # =========================================================================
    # Main Handler
    # =========================================================================
    
    @handler
    async def handle(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState]
    ) -> None:
        """Execute the search phase."""
        self._emit_started_event(state)
        
        query = self._determine_search_query(state)
        self._track_query(state, query)
        
        candidates = self._search_and_filter(state, query)
        state.current_candidates = candidates
        
        self._log_results(state, query, candidates)
        self._emit_completed_event(state, query)
        
        await self._transition_to_next_phase(state, ctx)
    
    # =========================================================================
    # Query Determination Strategy
    # =========================================================================
    
    def _determine_search_query(self, state: SlideSelectionState) -> str:
        """Determine the search query based on current state."""
        if self._is_first_attempt(state):
            return self._get_initial_query(state)
        
        critique_query = self._get_unused_critique_suggestion(state)
        if critique_query:
            return critique_query
        
        return self._get_next_hint(state) or state.outline_item.topic
    
    def _is_first_attempt(self, state: SlideSelectionState) -> bool:
        """Check if this is the first search attempt."""
        return state.current_attempt == 0
    
    def _get_initial_query(self, state: SlideSelectionState) -> str:
        """Get the query for the first search attempt."""
        hints = state.outline_item.search_hints
        return hints[0] if hints else state.outline_item.topic
    
    def _get_unused_critique_suggestion(self, state: SlideSelectionState) -> str | None:
        """Get search suggestion from last critique if not already tried."""
        if not state.conversation_history:
            return None
        
        last_critique = state.conversation_history[-1].get("critique", {})
        suggestion = last_critique.get("search_suggestion", "")
        
        if not suggestion:
            return None
        
        tried_queries = {query.lower() for query in state.previous_searches}
        return None if suggestion.lower() in tried_queries else suggestion
    
    def _get_next_hint(self, state: SlideSelectionState) -> str | None:
        """Get the next search hint by cycling through available hints."""
        hints = state.outline_item.search_hints
        if not hints:
            return None
        
        hint_index = state.current_attempt % len(hints)
        return hints[hint_index]
    
    # =========================================================================
    # Search Execution
    # =========================================================================
    
    def _track_query(self, state: SlideSelectionState, query: str) -> None:
        """Record the query in state to prevent duplicates."""
        state.current_search_query = query
        if query not in state.previous_searches:
            state.previous_searches.append(query)
    
    def _search_and_filter(
        self,
        state: SlideSelectionState,
        query: str
    ) -> list[dict[str, Any]]:
        """Execute search and filter out already-selected slides."""
        raw_results, _ = self._search_service.search(
            query,
            limit=MAX_SEARCH_RESULTS,
            include_pptx_status=True
        )
        return self._exclude_selected_slides(raw_results, state.already_selected_keys)
    
    def _exclude_selected_slides(
        self,
        results: list[SlideSearchResult],
        exclusion_keys: set[str]
    ) -> list[dict[str, Any]]:
        """Filter out slides already in the deck."""
        return [
            result.model_dump()
            for result in results
            if build_slide_key(result.session_code, result.slide_number) not in exclusion_keys
        ]
    
    # =========================================================================
    # State Transitions
    # =========================================================================
    
    async def _transition_to_next_phase(
        self,
        state: SlideSelectionState,
        ctx: WorkflowContext[SlideSelectionState]
    ) -> None:
        """Transition to 'offer' if candidates found, 'done' otherwise."""
        next_phase = "offer" if state.current_candidates else "done"
        condition = f"found {len(state.current_candidates)} candidates"
        
        transition_to_phase(state, "search", next_phase, condition)
        await ctx.send_message(state)
    
    # =========================================================================
    # Logging and Events
    # =========================================================================
    
    def _emit_started_event(self, state: SlideSelectionState) -> None:
        """Emit debug event for search start."""
        state.debug.executor_started(
            executor="search",
            position=state.outline_item.position,
            attempt=state.current_attempt + 1,
            details={"topic": state.outline_item.topic}
        )
    
    def _emit_completed_event(self, state: SlideSelectionState, query: str) -> None:
        """Emit debug event with search results."""
        state.debug.workflow_search(
            position=state.outline_item.position,
            query=query,
            result_count=len(state.current_candidates),
            previous_searches=state.previous_searches.copy(),
            results=state.current_candidates[:DEBUG_PREVIEW_COUNT]
        )
    
    def _log_results(
        self,
        state: SlideSelectionState,
        query: str,
        candidates: list[dict[str, Any]]
    ) -> None:
        """Log search results for monitoring."""
        logger.info(
            "Search '%s' returned %d candidates for position %d",
            query,
            len(candidates),
            state.outline_item.position
        )
