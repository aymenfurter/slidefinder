"""Workflow state for slide selection."""

from typing import Optional, Callable, Any

from pydantic import BaseModel, Field, PrivateAttr

from .models import SlideOutlineItem, PresentationOutline
from .debug import DebugEventEmitter

EventCallback = Callable[[dict], Any]


class SlideSelectionState(BaseModel):
    """State that flows through all executors in the workflow graph."""
    model_config = {"arbitrary_types_allowed": True}
    
    # Input context
    outline_item: SlideOutlineItem
    full_outline: PresentationOutline
    all_slides: list[dict] = Field(default_factory=list)
    already_selected_keys: set[str] = Field(default_factory=set)
    
    # Search tracking
    current_search_query: str = ""
    current_candidates: list[dict] = Field(default_factory=list)
    previous_searches: list[str] = Field(default_factory=list)
    
    # Selection tracking
    current_attempt: int = 0
    current_selection: Optional[dict] = None
    conversation_history: list[dict] = Field(default_factory=list)
    
    # Output
    selected_slide: Optional[dict] = None
    phase: str = "search"
    
    # Event infrastructure
    event_callback: Optional[EventCallback] = Field(default=None, exclude=True)
    _debug: Optional[DebugEventEmitter] = PrivateAttr(default=None)
    events: list[dict] = Field(default_factory=list)
    
    def model_post_init(self, __context) -> None:
        self._debug = DebugEventEmitter(self.event_callback)

    @property
    def debug(self) -> DebugEventEmitter:
        return self._debug or DebugEventEmitter(self.event_callback)
    
    def emit_event(self, event: dict) -> None:
        self.events.append(event)
        if self.event_callback:
            self.event_callback(event)
    
    @property
    def position(self) -> int:
        """Convenience accessor for the current slide position."""
        return self.outline_item.position
