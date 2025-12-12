"""Deck-related Pydantic models."""
from dataclasses import dataclass, field


@dataclass
class DeckSession:
    """
    Maintains state for a deck building conversation.
    
    Uses dataclass for mutable state management during agent execution.
    """
    session_id: str
    messages: list = field(default_factory=list)
    all_searched_slides: list = field(default_factory=list)
    compiled_deck: list = field(default_factory=list)
    flow_explanation: str = ""
    search_count: int = 0
    has_compiled: bool = False
    status: str = "pending"
    
    def to_dict(self) -> dict:
        """Convert session to dictionary for API responses."""
        return {
            "session_id": self.session_id,
            "compiled_deck": self.compiled_deck,
            "flow_explanation": self.flow_explanation,
            "message_count": len(self.messages),
            "slide_count": len(self.compiled_deck),
            "status": self.status,
        }
    
    def reset_turn_state(self) -> None:
        """Reset per-turn state before processing a new message."""
        self.search_count = 0
        self.has_compiled = False
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
    
    def add_search_results(self, results: list) -> None:
        """Add search results to the accumulated slides."""
        self.all_searched_slides.extend(results)
        self.search_count += 1
    
    def compile(self, slides: list, flow_explanation: str) -> None:
        """Set the compiled deck."""
        self.compiled_deck = slides
        self.flow_explanation = flow_explanation
        self.has_compiled = True
        self.status = "complete"
