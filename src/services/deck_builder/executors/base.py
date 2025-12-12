"""Base utilities for workflow executors."""
import time
from contextlib import contextmanager
from typing import Generator, Optional
from ..state import SlideSelectionState


def find_matching_slide(session_code: str, slide_number: int, slides: list[dict]) -> Optional[dict]:
    """Find a slide in a list by session code and slide number."""
    return next((s for s in slides if s["session_code"] == session_code and s["slide_number"] == slide_number), None)

@contextmanager
def timed_operation() -> Generator[dict, None, None]:
    """Context manager for timing operations."""
    timing = {"start": time.time(), "duration_ms": 0}
    try:
        yield timing
    finally:
        timing["duration_ms"] = int((time.time() - timing["start"]) * 1000)

def build_selection_dict(session_code: str, slide_number: int, reason: str,
                         slide_data: Optional[dict] = None, title: Optional[str] = None) -> dict:
    """Build a slide selection dictionary."""
    selection = {"session_code": session_code, "slide_number": slide_number, "reason": reason}
    if slide_data is not None:
        selection["slide_data"] = slide_data
    selection["title"] = title if title else (slide_data.get("title", "") if slide_data else None)
    return {k: v for k, v in selection.items() if v is not None}

def has_exceeded_max_attempts(state: SlideSelectionState, max_attempts: int) -> bool:
    """Check if the workflow has exceeded maximum attempts."""
    return state.current_attempt >= max_attempts

def transition_to_phase(state: SlideSelectionState, from_node: str, to_node: str, condition: str) -> None:
    """Transition the workflow to a new phase."""
    state.debug.edge_transition(from_node=from_node, to_node=to_node,
                                condition=condition, position=state.outline_item.position)
    state.phase = to_node

def mark_slide_as_tried(state: SlideSelectionState, slide: dict) -> None:
    """Mark a slide as already tried."""
    state.already_selected_keys.add(f"{slide['session_code']}_{slide['slide_number']}")
