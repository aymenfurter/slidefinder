"""Search executor for the slide selection workflow."""

import logging

from agent_framework import Executor, WorkflowContext, handler

from services.search_service import get_search_service

from ..state import SlideSelectionState

logger = logging.getLogger(__name__)


class SearchExecutor(Executor):
    """Searches for candidate slides based on the current query."""
    
    def __init__(self, id: str = "search"):
        super().__init__(id=id)
        self._search_service = get_search_service()
    
    @handler
    async def handle(self, state: SlideSelectionState, ctx: WorkflowContext[SlideSelectionState]) -> None:
        """Search for candidate slides."""
        # Determine search query
        if state.current_attempt == 0:
            # First attempt: use search hints from outline
            state.current_search_query = (
                state.outline_item.search_hints[0] 
                if state.outline_item.search_hints 
                else state.outline_item.topic
            )
        elif state.conversation_history:
            # Use critique's suggested query if available
            last_critique = state.conversation_history[-1].get("critique", {})
            suggested = last_critique.get("search_suggestion", "")
            
            # Avoid repeating searches - if suggested was already tried, use topic with variation
            if suggested and suggested.lower() not in [s.lower() for s in state.previous_searches]:
                state.current_search_query = suggested
            else:
                # Try a different search hint if available
                hint_idx = state.current_attempt % len(state.outline_item.search_hints) if state.outline_item.search_hints else 0
                if state.outline_item.search_hints and hint_idx < len(state.outline_item.search_hints):
                    state.current_search_query = state.outline_item.search_hints[hint_idx]
                else:
                    # Fallback to topic
                    state.current_search_query = state.outline_item.topic
        
        # Track this search
        if state.current_search_query not in state.previous_searches:
            state.previous_searches.append(state.current_search_query)
        
        # Search
        candidates, _ = self._search_service.search(
            state.current_search_query, limit=10, include_pptx_status=True
        )
        
        # Filter out already-used slides
        state.current_candidates = [
            c.model_dump() for c in candidates
            if f"{c.session_code}_{c.slide_number}" not in state.already_selected_keys
        ]
        
        logger.info(
            f"Search '{state.current_search_query}' returned "
            f"{len(state.current_candidates)} candidates for position {state.outline_item.position}"
        )
        
        # If no candidates, try topic as fallback
        if not state.current_candidates and state.current_search_query != state.outline_item.topic:
            fallback_results, _ = self._search_service.search(
                state.outline_item.topic, limit=5, include_pptx_status=True
            )
            state.current_candidates = [
                c.model_dump() for c in fallback_results
                if f"{c.session_code}_{c.slide_number}" not in state.already_selected_keys
            ]
        
        if state.current_candidates:
            state.phase = "offer"
        else:
            # No candidates at all - we're done (no slide found)
            state.phase = "done"
        
        await ctx.send_message(state)
