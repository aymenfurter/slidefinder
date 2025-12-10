"""Slide selection workflow using Microsoft Agent Framework."""
from agent_framework import ChatAgent, Workflow, WorkflowBuilder
from .executors import SearchExecutor, OfferExecutor, CritiqueExecutor, JudgeExecutor
from .executors.constants import MAX_CRITIQUE_ATTEMPTS, WorkflowPhase
from .state import SlideSelectionState

MAX_WORKFLOW_ITERATIONS = MAX_CRITIQUE_ATTEMPTS * 3

def create_slide_selection_workflow(
    offer_agent: ChatAgent,
    critique_agent: ChatAgent,
    judge_agent: ChatAgent,
) -> Workflow:
    """Build and return the slide selection workflow graph."""
    search, offer = SearchExecutor(), OfferExecutor(offer_agent)
    critique, judge = CritiqueExecutor(critique_agent), JudgeExecutor(judge_agent)

    builder = WorkflowBuilder()
    builder.add_edge(search, offer, condition=lambda s: s.phase == WorkflowPhase.OFFER)
    builder.add_edge(offer, critique, condition=lambda s: s.phase == WorkflowPhase.CRITIQUE)
    builder.add_edge(offer, judge, condition=lambda s: s.phase == WorkflowPhase.JUDGE)
    builder.add_edge(offer, search, condition=lambda s: s.phase == WorkflowPhase.SEARCH)
    builder.add_edge(critique, search, condition=lambda s: s.phase == WorkflowPhase.SEARCH)
    builder.add_edge(critique, judge, condition=lambda s: s.phase == WorkflowPhase.JUDGE)
    builder.set_start_executor(search)
    builder.set_max_iterations(MAX_WORKFLOW_ITERATIONS)
    return builder.build()

build_slide_selection_workflow = create_slide_selection_workflow  # Alias
