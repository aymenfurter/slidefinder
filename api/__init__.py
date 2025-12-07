"""API routes for SlideFinder."""

from .search import router as search_router
from .deck_builder import router as deck_builder_router
from .slides import router as slides_router

__all__ = [
    "search_router",
    "deck_builder_router",
    "slides_router",
]
