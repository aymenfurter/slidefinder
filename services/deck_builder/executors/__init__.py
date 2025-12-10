"""Executors for the slide selection workflow.

- SearchExecutor: Finds candidate slides matching the outline topic
- OfferExecutor: Selects the best slide from candidates using an LLM
- CritiqueExecutor: Evaluates whether the selected slide is appropriate
- JudgeExecutor: Final arbiter when max attempts reached
"""
from .search import SearchExecutor
from .offer import OfferExecutor
from .critique import CritiqueExecutor
from .judge import JudgeExecutor
from .constants import WorkflowPhase

__all__ = ["SearchExecutor", "OfferExecutor", "CritiqueExecutor", "JudgeExecutor", "WorkflowPhase"]
