"""Slide-related Pydantic models."""
from typing import Optional

from pydantic import BaseModel, Field


class SlideInfo(BaseModel):
    """Complete slide information from the search index."""
    
    slide_id: str = Field(..., description="Unique slide identifier")
    session_code: str = Field(..., description="Session code")
    slide_number: int = Field(..., ge=1, description="Slide number")
    title: str = Field(..., description="Session/slide title")
    content: str = Field(default="", description="Slide text content")
    event: str = Field(default="", description="Event name (Build/Ignite)")
    session_url: str = Field(default="", description="Session URL")
    ppt_url: str = Field(default="", description="PowerPoint download URL")


class SlideSearchResult(BaseModel):
    """Search result for a slide with additional metadata."""
    
    slide_id: str = Field(..., description="Unique slide identifier")
    session_code: str = Field(..., description="Session code")
    title: str = Field(..., description="Session/slide title")
    slide_number: int = Field(..., ge=1, description="Slide number")
    content: str = Field(default="", description="Slide text content (truncated)")
    snippet: str = Field(default="", description="Search result snippet with highlights")
    event: str = Field(default="", description="Event name")
    session_url: str = Field(default="", description="Session URL")
    ppt_url: str = Field(default="", description="PowerPoint download URL")
    has_thumbnail: bool = Field(default=False, description="Whether thumbnail exists")
    has_pptx: bool = Field(default=False, description="Whether PPTX is available locally")
    score: float = Field(default=0.0, ge=0, description="Search relevance score")
    
    @property
    def thumbnail_filename(self) -> str:
        """Generate thumbnail filename."""
        return f"{self.session_code}_{self.slide_number}.png"
