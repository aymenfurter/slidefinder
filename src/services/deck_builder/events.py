"""SSE event factories for the deck builder workflow."""

from typing import Optional

REPO_BASE = "https://github.com/aymenfurter/slidefinder/blob/main"
MESSAGE_PREVIEW_LENGTH = 100
MAX_SEARCH_RESULTS = 8
MAX_SLIDES_PREVIEW = 5

CODE_LINKS = {
    "service": f"{REPO_BASE}/src/services/deck_builder/service.py",
    "workflow": f"{REPO_BASE}/src/services/deck_builder/workflow.py",
    "agents": f"{REPO_BASE}/src/services/deck_builder/agents.py",
    "state": f"{REPO_BASE}/src/services/deck_builder/state.py",
    "prompts": f"{REPO_BASE}/src/services/deck_builder/prompts.py",
    "models": f"{REPO_BASE}/src/services/deck_builder/models.py",
    "debug": f"{REPO_BASE}/src/services/deck_builder/debug.py",
    "search_executor": f"{REPO_BASE}/src/services/deck_builder/executors/search.py",
    "offer_executor": f"{REPO_BASE}/src/services/deck_builder/executors/offer.py",
    "critique_executor": f"{REPO_BASE}/src/services/deck_builder/executors/critique.py",
    "judge_executor": f"{REPO_BASE}/src/services/deck_builder/executors/judge.py",
    "search_service": f"{REPO_BASE}/src/services/search/__init__.py",
    "azure_search": f"{REPO_BASE}/src/services/search/azure.py",
    "pptx_merger": f"{REPO_BASE}/src/services/pptx/merger.py",
}


def get_code_links() -> dict:
    """Get all code links for the nerd info panel."""
    return CODE_LINKS.copy()


def phase_init(message: str) -> dict:
    return {
        "type": "debug_phase",
        "phase": "init",
        "description": f"Starting deck build workflow for: {message[:MESSAGE_PREVIEW_LENGTH]}...",
        "code_link": CODE_LINKS["service"],
    }


def phase_search() -> dict:
    return {
        "type": "debug_phase",
        "phase": "search",
        "description": "Initial search to find candidate slides",
        "code_link": CODE_LINKS["search_service"],
    }


def phase_outline() -> dict:
    return {
        "type": "debug_phase",
        "phase": "outline",
        "description": "Generating presentation outline using AI",
        "code_link": CODE_LINKS["agents"],
    }


def phase_slide_selection(count: int) -> dict:
    return {
        "type": "debug_phase",
        "phase": "slide_selection",
        "description": f"Starting slide selection workflow for {count} slides",
        "code_link": CODE_LINKS["workflow"],
    }


def phase_complete(slide_count: int) -> dict:
    return {
        "type": "debug_phase",
        "phase": "complete",
        "description": f"Workflow complete! Built deck with {slide_count} slides",
        "code_link": CODE_LINKS["service"],
    }


def search_complete(
    query: str,
    result_count: int,
    duration_ms: int,
    results: Optional[list] = None
) -> dict:
    return {
        "type": "debug_search",
        "query": query,
        "result_count": result_count,
        "duration_ms": duration_ms,
        "results": results[:MAX_SEARCH_RESULTS] if results else [],
        "code_link": CODE_LINKS["search_service"],
    }


def outline_llm_start(
    query: str,
    slides_sample: list,
    total_slides: int
) -> dict:
    slides_preview = "\n".join([
        f"- {s.get('session_code', '?')} #{s.get('slide_number', '?')}: {s.get('title', 'Untitled')[:60]}"
        for s in slides_sample[:MAX_SLIDES_PREVIEW]
    ])
    
    prompt_preview = f"""Create a presentation outline for: {query}

AVAILABLE SLIDES (sample of {total_slides} total):
{slides_preview}
{"..." if total_slides > MAX_SLIDES_PREVIEW else ""}

Create a structured outline with 5-9 slides."""
    
    return {
        "type": "debug_llm_start",
        "agent": "OutlineAgent",
        "task": "Generate structured presentation outline",
        "response_format": "PresentationOutline",
        "prompt_preview": prompt_preview,
        "code_link": CODE_LINKS["agents"],
    }


def outline_llm_complete(outline, duration_ms: int) -> dict:
    outline_response = f"""Title: {outline.title}
Narrative: {outline.narrative}

Slides:
""" + "\n".join([
        f"{s.position}. {s.topic} (hints: {', '.join(s.search_hints[:2])})"
        for s in outline.slides
    ])
    
    return {
        "type": "debug_llm_complete",
        "agent": "OutlineAgent",
        "status": "success",
        "duration_ms": duration_ms,
        "response_preview": outline_response,
        "code_link": CODE_LINKS["agents"],
    }


def slide_workflow_start(position: int, topic: str, total: int) -> dict:
    return {
        "type": "debug_slide_workflow_start",
        "position": position,
        "topic": topic,
        "total": total,
        "workflow_graph": "search → offer → critique → [done | loop | judge]",
        "code_links": {
            "workflow": CODE_LINKS["workflow"],
            "search": CODE_LINKS["search_executor"],
            "offer": CODE_LINKS["offer_executor"],
            "critique": CODE_LINKS["critique_executor"],
            "judge": CODE_LINKS["judge_executor"],
        },
    }


def slide_workflow_complete(
    position: int,
    success: bool,
    slide: Optional[dict] = None
) -> dict:
    return {
        "type": "debug_slide_workflow_complete",
        "position": position,
        "success": success,
        "slide": {
            "session_code": slide["session_code"],
            "slide_number": slide["slide_number"]
        } if slide else None,
    }


def code_documentation() -> dict:
    return {
        "type": "debug_code_links",
        "links": {
            "Deck Builder Service": {
                "url": CODE_LINKS["service"],
                "description": "Main orchestration: process_message_stream() and continue_with_outline_stream()"
            },
            "Workflow Graph": {
                "url": CODE_LINKS["workflow"],
                "description": "LangGraph-style workflow: create_slide_selection_workflow()"
            },
            "Agent Orchestrator": {
                "url": CODE_LINKS["agents"],
                "description": "WorkflowOrchestrator: generate_outline(), select_slide_with_critique()"
            },
            "Workflow State": {
                "url": CODE_LINKS["state"],
                "description": "SlideSelectionState: tracks current phase, candidates, history"
            },
            "Agent Prompts": {
                "url": CODE_LINKS["prompts"],
                "description": "System instructions for OutlineAgent, OfferAgent, CritiqueAgent, JudgeAgent"
            },
            "Search Executor": {
                "url": CODE_LINKS["search_executor"],
                "description": "SearchExecutor: searches for candidate slides"
            },
            "Offer Executor": {
                "url": CODE_LINKS["offer_executor"],
                "description": "OfferExecutor: AI selects best slide from candidates"
            },
            "Critique Executor": {
                "url": CODE_LINKS["critique_executor"],
                "description": "CritiqueExecutor: AI evaluates if slide matches requirements"
            },
            "Judge Executor": {
                "url": CODE_LINKS["judge_executor"],
                "description": "JudgeExecutor: final selection after max attempts"
            },
            "Search Service": {
                "url": CODE_LINKS["search_service"],
                "description": "Whoosh/Azure search abstraction"
            },
            "PPTX Merger": {
                "url": CODE_LINKS["pptx_merger"],
                "description": "merge_slides_to_deck(): assembles final PowerPoint"
            },
        }
    }
