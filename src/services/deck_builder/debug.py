"""Debug event emission for deck builder workflow."""
from typing import Callable, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SlideSelection, CritiqueResult

QUERY_PREVIEW_LENGTH, PROMPT_PREVIEW_LENGTH = 100, 500
RESPONSE_PREVIEW_LENGTH, MAX_SEARCH_RESULTS_PREVIEW = 300, 6


class DebugEventEmitter:
    """Emits debug events for workflow visualization.
    
    This class centralizes all event emission logic for debugging and UI updates.
    Executors call these methods to emit events without cluttering their business logic.
    """

    def __init__(self, callback: Optional[Callable[[dict], Any]] = None):
        self._callback = callback

    def _emit(self, event_type: str, **data) -> None:
        if self._callback:
            self._callback({"type": event_type, **data})

    def _emit_ui_event(self, event: dict) -> None:
        """Emit a UI event (separate from debug events)."""
        if self._callback:
            self._callback(event)

    def process_started(self, query: str) -> None:
        self._emit("debug_process_start", phase="init",
                   description=f"Starting deck build for: {_truncate(query, QUERY_PREVIEW_LENGTH)}")

    def search_phase_started(self) -> None:
        self._emit("debug_phase", phase="initial_search",
                   description="Searching for candidate slides across the index")

    def search_completed(self, query: str, result_count: int, duration_ms: int) -> None:
        self._emit("debug_search", query=query, result_count=result_count, duration_ms=duration_ms)

    def outline_phase_started(self) -> None:
        self._emit("debug_phase", phase="outline_generation",
                   description="Generating presentation outline using AI")

    def slide_selection_phase_started(self, total_slides: int) -> None:
        self._emit("debug_phase", phase="slide_selection",
                   description=f"Starting slide selection workflow for {total_slides} slides")

    def process_completed(self, slides_found: int, total_slides: int) -> None:
        self._emit("debug_process_complete", phase="complete",
                   description=f"Workflow complete - selected {slides_found}/{total_slides} slides")
    
    def llm_call_started(self, agent: str, task: str, prompt_preview: str,
                          response_format: str, position: Optional[int] = None) -> None:
        self._emit("debug_llm_start", agent=agent, task=task,
                   prompt_preview=_truncate(prompt_preview, PROMPT_PREVIEW_LENGTH),
                   full_prompt=prompt_preview, response_format=response_format, position=position)

    def llm_call_completed(self, agent: str, duration_ms: int,
                           response_preview: str, position: Optional[int] = None) -> None:
        self._emit("debug_llm_complete", agent=agent, status="success", duration_ms=duration_ms,
                   response_preview=_truncate(response_preview, RESPONSE_PREVIEW_LENGTH), position=position)

    def llm_call_failed(self, agent: str, duration_ms: int,
                        error: str, position: Optional[int] = None) -> None:
        self._emit("debug_llm_complete", agent=agent, status="error",
                   duration_ms=duration_ms, error=error, position=position)
    
    def slide_workflow_started(self, position: int, topic: str, total: int) -> None:
        self._emit("debug_slide_workflow_start", position=position, topic=topic, total=total,
                   workflow_graph="search → offer → critique → [done | loop | judge]")

    def slide_workflow_completed(self, position: int, success: bool,
                                  slide: Optional[dict] = None, attempts: int = 0) -> None:
        self._emit("debug_slide_workflow_complete", position=position,
                   success=success, slide=slide, attempts=attempts)

    def executor_started(self, executor: str, position: int, attempt: Optional[int] = None,
                         candidate_count: Optional[int] = None, details: Optional[dict] = None) -> None:
        data = {"executor": executor, "position": position, "details": details or {}}
        if attempt is not None:
            data["attempt"] = attempt
        if candidate_count is not None:
            data["candidate_count"] = candidate_count
        self._emit("debug_executor_start", **data)

    def executor_completed(self, executor: str, position: int, result_summary: str) -> None:
        self._emit("debug_executor_complete", executor=executor,
                   position=position, result_summary=result_summary)

    def edge_transition(self, from_node: str, to_node: str,
                        condition: str, position: Optional[int] = None) -> None:
        self._emit("debug_edge", from_node=from_node, to_node=to_node,
                   condition=condition, position=position)
    
    def workflow_search(self, position: int, query: str, result_count: int,
                         previous_searches: list[str], results: list[dict] = None) -> None:
        self._emit("debug_workflow_search", position=position, query=query,
                   result_count=result_count, previous_searches=previous_searches,
                   is_retry=len(previous_searches) > 1,
                   results=results[:MAX_SEARCH_RESULTS_PREVIEW] if results else [])

    def slide_offered(self, position: int, session_code: str,
                      slide_number: int, reason: str) -> None:
        self._emit("debug_slide_offered", position=position, session_code=session_code,
                   slide_number=slide_number, reason=reason)

    def slide_critiqued(self, position: int, session_code: str, slide_number: int,
                        approved: bool, feedback: str, suggestion: Optional[str] = None) -> None:
        self._emit("debug_slide_critiqued", position=position, session_code=session_code,
                   slide_number=slide_number, approved=approved, feedback=feedback,
                   search_suggestion=suggestion)

    def judge_invoked(self, position: int, candidates_count: int,
                      selected_code: str, selected_number: int, reason: str) -> None:
        self._emit("debug_judge_invoked", position=position, candidates_count=candidates_count,
                   selected_code=selected_code, selected_number=selected_number, reason=reason)

    def judge_selected(self, position: int, session_code: str,
                       slide_number: int, reason: str) -> None:
        self._emit("debug_judge_selected", position=position, session_code=session_code,
                   slide_number=slide_number, reason=reason)

    def fallback_used(self, executor: str, position: int, fallback_slide: str) -> None:
        self._emit("debug_fallback", executor=executor, position=position,
                   fallback_slide=fallback_slide,
                   description="LLM failed; using last attempted slide as fallback")

    # =========================================================================
    # Executor-Specific Convenience Methods
    # =========================================================================
    # These methods encapsulate common emit patterns used by each executor,
    # keeping the executor code focused on business logic.

    def search_started(self, position: int, attempt: int, topic: str) -> None:
        """Emit search executor started event."""
        self.executor_started(executor="search", position=position,
                              attempt=attempt, details={"topic": topic})

    def search_results(self, position: int, query: str, candidates: list[dict],
                       previous_searches: list[str], preview_count: int = 6) -> None:
        """Emit search results event with candidate preview."""
        self.workflow_search(position=position, query=query,
                             result_count=len(candidates),
                             previous_searches=previous_searches.copy(),
                             results=candidates[:preview_count])

    def offer_started(self, position: int, attempt: int, candidate_count: int) -> None:
        """Emit offer executor started event."""
        self.executor_started(executor="offer", position=position,
                              attempt=attempt, details={"candidate_count": candidate_count})

    def offer_llm_started(self, position: int, prompt: str) -> None:
        """Emit LLM call started for offer agent."""
        self.llm_call_started(agent="OfferAgent", task="Select best matching slide",
                              prompt_preview=prompt, response_format="SlideSelection",
                              position=position)

    def offer_llm_completed(self, position: int, session_code: str,
                            slide_number: int, reason: str, duration_ms: int) -> None:
        """Emit LLM call completed for offer agent."""
        self.llm_call_completed(agent="OfferAgent", duration_ms=duration_ms,
                                response_preview=f"Selected: {session_code} #{slide_number} - {reason}",
                                position=position)

    def critique_started(self, position: int, attempt: int) -> None:
        """Emit critique executor started event."""
        self.executor_started(executor="critique", position=position, attempt=attempt)

    def critique_llm_started(self, position: int, session_code: str,
                             slide_number: int, prompt: str) -> None:
        """Emit LLM call started for critique agent."""
        self.llm_call_started(agent="CritiqueAgent",
                              task=f"Evaluate slide {session_code} #{slide_number}",
                              prompt_preview=prompt, response_format="CritiqueResult",
                              position=position)

    def critique_llm_completed(self, position: int, approved: bool,
                               feedback: str, duration_ms: int) -> None:
        """Emit LLM call completed for critique agent."""
        status = "✅ Approved" if approved else "❌ Rejected"
        self.llm_call_completed(agent="CritiqueAgent", duration_ms=duration_ms,
                                response_preview=f"{status}: {feedback}",
                                position=position)

    def critique_attempt_ui(self, position: int, attempt: int, query: str,
                            candidate_count: int, slide: dict, selection_reason: str,
                            approved: bool, feedback: str, issues: list[str]) -> None:
        """Emit UI event for a critique attempt."""
        self._emit_ui_event({
            "type": "critique_attempt", "position": position,
            "attempt": attempt, "search_query": query,
            "result_count": candidate_count,
            "slide_code": slide["session_code"],
            "slide_number": slide["slide_number"],
            "slide_title": slide.get("title", ""),
            "thumbnail_url": f"/thumbnails/{slide['session_code']}_{slide['slide_number']}.png",
            "selection_reason": selection_reason,
            "approved": approved, "feedback": feedback, "issues": issues
        })

    def judge_started(self, position: int, candidate_count: int) -> None:
        """Emit judge executor started event."""
        self.executor_started(executor="judge", position=position,
                              candidate_count=candidate_count)

    def judge_ui_started(self, position: int, candidate_count: int) -> None:
        """Emit UI event for judge starting."""
        self._emit_ui_event({
            "type": "llm_judge_start", "position": position,
            "candidate_count": candidate_count,
            "message": f"Max attempts reached. Judge selecting best from {candidate_count} candidates..."
        })

    def judge_llm_started(self, position: int, candidate_count: int, prompt: str) -> None:
        """Emit LLM call started for judge agent."""
        self.llm_call_started(agent="JudgeAgent",
                              task=f"Final selection from {candidate_count} candidates",
                              prompt_preview=prompt, response_format="SlideSelection",
                              position=position)

    def judge_llm_completed(self, position: int, session_code: str,
                            slide_number: int, duration_ms: int) -> None:
        """Emit LLM call completed for judge agent."""
        self.llm_call_completed(agent="JudgeAgent", duration_ms=duration_ms,
                                response_preview=f"Selected: {session_code} #{slide_number}",
                                position=position)

def _truncate(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if too long."""
    return text if len(text) <= max_length else text[:max_length] + "..."
