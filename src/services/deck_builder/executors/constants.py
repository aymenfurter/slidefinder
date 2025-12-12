"""Constants for the slide selection workflow executors."""
from enum import StrEnum


class WorkflowPhase(StrEnum):
    """Phases in the slide selection workflow."""
    SEARCH = "search"
    OFFER = "offer"
    CRITIQUE = "critique"
    JUDGE = "judge"
    DONE = "done"


MAX_CRITIQUE_ATTEMPTS = 15
MAX_SEARCH_RESULTS = 10
FALLBACK_SEARCH_LIMIT = 5
MAX_CANDIDATES_FOR_SELECTION = 5
CONTENT_PREVIEW_LENGTH = 300
PROMPT_CONTENT_LENGTH = 500
DEBUG_PREVIEW_COUNT = 6

def build_slide_key(session_code: str, slide_number: int, sep: str = "_") -> str:
    """Build a slide identifier with configurable separator (default: SESSION_NUMBER)."""
    return f"{session_code}{sep}{slide_number}"

def build_slide_display_key(session_code: str, slide_number: int) -> str:
    """Build a display slide identifier: SESSION#NUMBER."""
    return build_slide_key(session_code, slide_number, "#")
