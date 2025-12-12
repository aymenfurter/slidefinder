"""Pydantic models and schemas for type-safe data handling."""

from .slide import SlideInfo, SlideSearchResult
from .deck import DeckSession

__all__ = [
    # Slide models
    "SlideInfo",
    "SlideSearchResult",
    # Deck models
    "DeckSession",
]
