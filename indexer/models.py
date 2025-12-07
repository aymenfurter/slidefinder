"""
Data models for the SlideFinder indexer.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class SessionInfo:
    """Information about a session with slides."""
    session_code: str
    title: str
    event: str  # 'Build', 'Ignite', or 'Partner'
    session_id: str
    session_url: str
    ppt_url: str
    description: str = ""  # Used for Partner content (can't download PPTX without auth)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass  
class SlideRecord:
    """Record for a single slide in the index."""
    slide_id: str           # Format: {session_code}_{slide_number}
    session_code: str
    title: str
    slide_number: int
    content: str
    event: str
    session_url: str
    ppt_url: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class IndexingStats:
    """Statistics for an indexing run."""
    sessions_processed: int = 0
    slides_indexed: int = 0
    thumbnails_generated: int = 0
    thumbnails_skipped: int = 0
    errors: int = 0
    
    def __str__(self) -> str:
        return (
            f"Sessions: {self.sessions_processed}, "
            f"Slides: {self.slides_indexed}, "
            f"Thumbnails: {self.thumbnails_generated} (skipped: {self.thumbnails_skipped}), "
            f"Errors: {self.errors}"
        )


# Known problematic files to skip
IGNORE_SESSION_CODES = frozenset({
    "BRK224", "BRK301", "BRK344"
})


# API endpoints for Build and Ignite
API_URLS = {
    "build": "https://eventtools.event.microsoft.com/build2025-prod/fallback/session-all-en-us.json",
    "ignite": "https://api-v2.ignite.microsoft.com/api/session/all/en-US",
}

# HTTP headers for API requests
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (SlideFinderBot/1.0)",
    "Accept": "application/json"
}
