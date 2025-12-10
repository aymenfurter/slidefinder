"""Slide selection workflow using Microsoft Agent Framework."""

from agent_framework import ChatAgent, Workflow, WorkflowBuilder

from .executors import SearchExecutor, OfferExecutor, CritiqueExecutor, JudgeExecutor
from .state import SlideSelectionState

MAX_CRITIQUE_ATTEMPTS = 15
MAX_WORKFLOW_ITERATIONS = MAX_CRITIQUE_ATTEMPTS * 3


def build_slide_selection_workflow(
    offer_agent: ChatAgent,
    critique_agent: ChatAgent,
    judge_agent: ChatAgent,
) -> Workflow:
    """Build the slide selection workflow graph."""
    # Create executors
    search = SearchExecutor()
    offer = OfferExecutor(offer_agent)
    critique = CritiqueExecutor(critique_agent)
    judge = JudgeExecutor(judge_agent)
    
    # Build graph
    builder = WorkflowBuilder()
    
    builder.add_edge(search, offer, condition=lambda s: s.phase == "offer")
    builder.add_edge(offer, critique, condition=lambda s: s.phase == "critique")
    builder.add_edge(offer, judge, condition=lambda s: s.phase == "judge")
    builder.add_edge(offer, search, condition=lambda s: s.phase == "search")
    builder.add_edge(critique, search, condition=lambda s: s.phase == "search")
    builder.add_edge(critique, judge, condition=lambda s: s.phase == "judge")
    
    builder.set_start_executor(search)
    builder.set_max_iterations(MAX_WORKFLOW_ITERATIONS)
    
    return builder.build()


def create_slide_selection_workflow(
    offer_agent: ChatAgent,
    critique_agent: ChatAgent,
    judge_agent: ChatAgent,
) -> Workflow:
    """Create a slide selection workflow."""
    return build_slide_selection_workflow(offer_agent, critique_agent, judge_agent)
