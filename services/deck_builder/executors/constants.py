"""Constants for the slide selection workflow executors."""

MAX_CRITIQUE_ATTEMPTS = 15
MAX_SEARCH_RESULTS = 10
FALLBACK_SEARCH_LIMIT = 5
MAX_CANDIDATES_FOR_SELECTION = 5
CONTENT_PREVIEW_LENGTH = 300
PROMPT_CONTENT_LENGTH = 500
DEBUG_PREVIEW_COUNT = 6


def build_slide_key(session_code: str, slide_number: int) -> str:
    """Build a unique slide identifier: SESSION_NUMBER."""
    return f"{session_code}_{slide_number}"


def build_slide_display_key(session_code: str, slide_number: int) -> str:
    """Build a display slide identifier: SESSION#NUMBER."""
    return f"{session_code}#{slide_number}"
