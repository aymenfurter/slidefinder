"""
Deck Builder Service Package.

Provides AI-powered deck building with outline generation and slide selection.
"""

from .service import DeckBuilderService, get_deck_builder_service
from .models import (
    SlideOutlineItem,
    PresentationOutline,
    SlideSelection,
    CritiqueResult,
)
from .state import SlideSelectionState
from .workflow import build_slide_selection_workflow, create_slide_selection_workflow

__all__ = [
    "DeckBuilderService",
    "get_deck_builder_service",
    "SlideOutlineItem",
    "PresentationOutline",
    "SlideSelection",
    "CritiqueResult",
    "SlideSelectionState",
    "build_slide_selection_workflow",
    "create_slide_selection_workflow",
]
