"""Pydantic models for structured agent outputs."""

from typing import Optional
from pydantic import BaseModel, Field


class SlideOutlineItem(BaseModel):
    """A single item in the presentation outline."""
    position: int = Field(..., description="Position in the deck (1-based)")
    topic: str = Field(..., description="What this slide should cover")
    search_hints: list[str] = Field(default_factory=list, description="Keywords to search for")
    purpose: str = Field(..., description="Why this slide is needed in the flow")


class PresentationOutline(BaseModel):
    """Structured outline for a presentation."""
    title: str = Field(..., description="Overall presentation title")
    narrative: str = Field(..., description="Brief story arc description")
    slides: list[SlideOutlineItem] = Field(..., description="Ordered list of slides needed")


class SlideSelection(BaseModel):
    """A slide selected by the offer agent."""
    session_code: str
    slide_number: int
    reason: str = Field(..., description="Why this slide was selected")


class CritiqueResult(BaseModel):
    """Result from the critique agent evaluation."""
    approved: bool = Field(..., description="Whether the slide is approved")
    feedback: str = Field(..., description="Detailed feedback on the slide")
    issues: list[str] = Field(default_factory=list, description="Specific issues found")
    search_suggestion: Optional[str] = Field(None, description="Suggested search query if rejected")
