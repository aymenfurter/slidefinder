"""
Data models for the Slide Assistant service.
Uses Pydantic for structured outputs from the LLM.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReferencedSlide(BaseModel):
    """A slide referenced in the assistant's response."""
    
    slide_id: str = Field(description="Unique identifier for the slide")
    session_code: str = Field(description="Session code (e.g., BRK108)")
    slide_number: int = Field(description="Slide number within the session")
    title: str = Field(description="Session title")
    content: str = Field(description="Slide content snippet")
    event: str = Field(description="Event name (Build/Ignite)")
    session_url: str = Field(default="", description="URL to the session")
    ppt_url: str = Field(default="", description="URL to the PowerPoint file")
    relevance_reason: str = Field(description="Why this slide is relevant to the query")
    thumbnail_url: Optional[str] = Field(default=None, description="URL to slide thumbnail")


class ChatResponse(BaseModel):
    """Structured response from the slide assistant."""
    
    answer: str = Field(
        description="Helpful, conversational answer to the user's question about finding slides. "
        "Should be friendly and guide users to relevant slides."
    )
    referenced_slides: list[ReferencedSlide] = Field(
        default_factory=list,
        description="List of relevant slides that match the user's query. "
        "Include slides that are specifically relevant to what the user is looking for."
    )
    follow_up_suggestions: list[str] = Field(
        default_factory=list,
        description="2-3 natural follow-up questions the USER would want to ask next to explore the topic further. "
        "Phrase these as direct search queries like 'Show me slides about X' or 'What sessions cover Y?' "
        "Do NOT phrase as questions directed at the user like 'Would you like...?' or 'Are you interested in...?'"
    )


class ChatMessage(BaseModel):
    """A message in the chat history."""
    
    role: str = Field(description="Either 'user' or 'assistant'")
    content: str = Field(description="The message content")


class ChatRequest(BaseModel):
    """Request model for the slide assistant chat."""
    
    message: str = Field(description="The user's message")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in the conversation"
    )
