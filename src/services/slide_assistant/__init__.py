"""
Slide Assistant Service
Provides AI-powered chat assistance for finding slides.
"""

from .service import SlideAssistantService, get_slide_assistant_service
from .models import ChatMessage, ChatResponse, ReferencedSlide

__all__ = [
    "SlideAssistantService",
    "get_slide_assistant_service",
    "ChatMessage",
    "ChatResponse",
    "ReferencedSlide",
]
