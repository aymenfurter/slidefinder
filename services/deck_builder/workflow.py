"""Slide Selection Workflow using Microsoft Agent Framework.

This module defines a workflow graph for selecting a single slide
through an iterative critique/offer loop. The workflow is run once
per slide position in the presentation.

The orchestrator runs this workflow for each slide position.
"""

from agent_framework import ChatAgent, Workflow, WorkflowBuilder

from .executors import SearchExecutor, OfferExecutor, CritiqueExecutor, JudgeExecutor
from .state import SlideSelectionState

MAX_CRITIQUE_ATTEMPTS = 15


# ============================================================================
# Workflow Builder
# ============================================================================

def build_slide_selection_workflow(
    offer_agent: ChatAgent,
    critique_agent: ChatAgent,
    judge_agent: ChatAgent,
) -> Workflow:
    """Build the slide selection workflow graph.
    
    Graph:
        search → offer → critique → done (if approved)
                   ↑         ↓
                   └─────────┘ (if rejected, loop back)
                             ↓
                          judge → done (if max attempts)
    """
    # Create executors
    search = SearchExecutor()
    offer = OfferExecutor(offer_agent)
    critique = CritiqueExecutor(critique_agent)
    judge = JudgeExecutor(judge_agent)
    
    # Build graph
    builder = WorkflowBuilder()
    
    # search → offer (when candidates found)
    builder.add_edge(search, offer, condition=lambda s: s.phase == "offer")
    
    # search → done (when no candidates)
    # Note: We handle this by checking phase in offer executor
    
    # offer → critique
    builder.add_edge(offer, critique, condition=lambda s: s.phase == "critique")
    
    # offer → judge (max attempts)
    builder.add_edge(offer, judge, condition=lambda s: s.phase == "judge")
    
    # offer → search (retry)
    builder.add_edge(offer, search, condition=lambda s: s.phase == "search")
    
    # critique → search (rejected, try again)
    builder.add_edge(critique, search, condition=lambda s: s.phase == "search")
    
    # critique → judge (max attempts after rejection)
    builder.add_edge(critique, judge, condition=lambda s: s.phase == "judge")
    
    # judge has no outgoing edges - workflow ends when phase="done"
    
    # Start at search
    builder.set_start_executor(search)
    
    # Prevent infinite loops
    builder.set_max_iterations(MAX_CRITIQUE_ATTEMPTS * 3)
    
    return builder.build()


def create_slide_selection_workflow(
    offer_agent: ChatAgent,
    critique_agent: ChatAgent,
    judge_agent: ChatAgent,
) -> Workflow:
    """Factory function to create a slide selection workflow."""
    return build_slide_selection_workflow(offer_agent, critique_agent, judge_agent)
