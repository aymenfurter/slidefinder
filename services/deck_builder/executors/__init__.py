"""Executors for the slide selection workflow.

This package contains the individual executors that handle each phase
of the slide selection process:

- SearchExecutor: Finds candidate slides matching the outline topic
- OfferExecutor: Selects the best slide from candidates using an LLM
- CritiqueExecutor: Evaluates whether the selected slide is appropriate
- JudgeExecutor: Final arbiter when max attempts reached

Supporting Modules:
- constants: Shared configuration values
- base: Reusable utilities and patterns
"""

from .search import SearchExecutor
from .offer import OfferExecutor
from .critique import CritiqueExecutor
from .judge import JudgeExecutor

__all__ = [
    "SearchExecutor",
    "OfferExecutor",
    "CritiqueExecutor",
    "JudgeExecutor",
]
