"""Workflow state for slide selection.

This module defines the state that flows through all executors in the workflow graph.
"""

from typing import Optional, Callable, Any

from pydantic import BaseModel, Field

from .models import SlideOutlineItem, PresentationOutline


class SlideSelectionState(BaseModel):
    """State for the slide selection workflow.
    
    This flows through all executors in the workflow graph.
    """
    model_config = {"arbitrary_types_allowed": True}
    
    # Input: What slide we're looking for
    outline_item: SlideOutlineItem
    full_outline: PresentationOutline
    all_slides: list[dict] = Field(default_factory=list)
    already_selected_keys: set[str] = Field(default_factory=set)
    
    # Search state
    current_search_query: str = ""
    current_candidates: list[dict] = Field(default_factory=list)
    previous_searches: list[str] = Field(default_factory=list)  # Track all searches tried
    
    # Selection state
    current_attempt: int = 0
    current_selection: Optional[dict] = None  # {session_code, slide_number, reason, slide_data}
    conversation_history: list[dict] = Field(default_factory=list)
    
    # Result
    selected_slide: Optional[dict] = None  # Final selected slide
    
    # Control flow
    phase: str = "search"  # search, offer, critique, judge, done
    
    # Event streaming - callback to emit events in real-time
    event_callback: Optional[Callable[[dict], Any]] = Field(default=None, exclude=True)
    
    # Events for streaming to UI (also kept for backward compatibility)
    events: list[dict] = Field(default_factory=list)
    
    def emit_event(self, event: dict) -> None:
        """Emit an event immediately if callback is set, also append to events list."""
        self.events.append(event)
        if self.event_callback:
            # Put event in queue for async consumption
            self.event_callback(event)
