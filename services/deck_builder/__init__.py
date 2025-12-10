"""Deck Builder Service Package."""

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
