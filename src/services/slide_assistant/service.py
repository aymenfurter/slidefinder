"""
Slide Assistant Service - AI-powered conversational search.

This service demonstrates how to use Azure AI Foundry SDK to build
an AI agent with function calling for structured outputs.

Architecture:
- Uses AIProjectClient from azure-ai-projects SDK
- Creates versioned agents with PromptAgentDefinition
- Invokes via Responses API with agent_reference
- Function calling enforces structured JSON output
"""

import json
import logging
from typing import Optional, AsyncGenerator

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from azure.identity import DefaultAzureCredential
from pydantic import ValidationError

from src.core import get_settings
from src.core.maf_wrapper import (
    with_maf_telemetry,
    extract_function_call,
    sse_status,
    sse_event,
    sse_error,
    sse_done,
)
from src.services.search import get_search_service
from .models import ChatMessage as ChatHistoryMessage, ChatResponse, ReferencedSlide

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Configuration
# =============================================================================

AGENT_INSTRUCTIONS = """You are a helpful slide assistant for SlideFinder, a tool that helps users find slides from Microsoft Build and Ignite conferences.

Your role is to help users find the most relevant slides for their needs. You have access to search results from a large collection of presentation slides.

Guidelines:
- Be conversational and helpful
- When users ask about a topic, suggest specific slides that match their needs
- Explain WHY each slide is relevant to their query
- If you don't find good matches, suggest alternative search terms
- Keep your answers concise but informative
- Always reference specific slides when discussing content

For follow_up_suggestions: Generate 2-3 natural follow-up questions that the USER would logically want to ask next. These should be phrased as direct questions like "Show me slides about Azure security" - NOT questions directed at the user like "Would you like...?"

IMPORTANT: You MUST call the 'provide_chat_response' function to return your response.
Only include slides that are actually relevant to the user's question."""

RESPONSE_FUNCTION = FunctionTool(
    name="provide_chat_response",
    description="Provide a structured response to the user's slide search query.",
    parameters={
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "Helpful answer to the user's question about finding slides.",
            },
            "referenced_slides": {
                "type": "array",
                "description": "List of relevant slides that match the user's query.",
                "items": {
                    "type": "object",
                    "properties": {
                        "slide_id": {"type": "string"},
                        "session_code": {"type": "string"},
                        "slide_number": {"type": "integer"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "event": {"type": "string"},
                        "session_url": {"type": "string"},
                        "ppt_url": {"type": "string"},
                        "relevance_reason": {"type": "string"},
                    },
                    "required": ["slide_id", "session_code", "slide_number", "title", "content", "event", "session_url", "ppt_url", "relevance_reason"],
                    "additionalProperties": False,
                },
            },
            "follow_up_suggestions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["answer", "referenced_slides", "follow_up_suggestions"],
        "additionalProperties": False,
    },
    strict=True,
)


# =============================================================================
# Service Implementation
# =============================================================================

class SlideAssistantService:
    """AI-powered slide search using Azure AI Foundry."""
    
    def __init__(self):
        self._settings = get_settings()
        self._project: AIProjectClient | None = None
        self._openai = None
        self._agent = None
    
    @property
    def is_available(self) -> bool:
        return self._settings.has_foundry_agent
    
    def _ensure_client(self) -> None:
        """Initialize Foundry client and agent on first use."""
        if self._project is not None:
            return
        
        self._project = AIProjectClient(
            endpoint=self._settings.azure_ai_project_endpoint or "",
            credential=DefaultAzureCredential(),
        )
        self._openai = self._project.get_openai_client()
        
        self._agent = self._project.agents.create_version(
            agent_name=self._settings.azure_ai_foundry_agent_name,
            definition=PromptAgentDefinition(
                model=self._settings.azure_openai_nano_deployment,
                instructions=AGENT_INSTRUCTIONS,
                tools=[RESPONSE_FUNCTION],
            ),
        )
        logger.info(f"Foundry agent ready: {self._agent.name} v{self._agent.version}")
    
    async def chat(
        self,
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> ChatResponse:
        """Process a chat message and return structured response."""
        if not self.is_available:
            return self._error_response("AI service is not available.")
        
        try:
            # 1. Search for relevant slides
            search_results = self._search_slides(message)
            
            # 2. Build prompt with context
            input_text = self._build_prompt(search_results, message, history)
            
            # 3. Call agent
            response_data = await self._invoke_agent(input_text)
            
            # 4. Build response with enriched slides
            slides = [ReferencedSlide(**s) for s in response_data.get("referenced_slides", [])]
            enriched = self._enrich_slides(slides, search_results)
            
            return ChatResponse(
                answer=response_data.get("answer", ""),
                referenced_slides=enriched,
                follow_up_suggestions=response_data.get("follow_up_suggestions", []),
            )
            
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Response error: {e}")
            return self._error_response("I couldn't process the response properly.")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return self._error_response("I encountered an error. Please try again.")
    
    async def chat_stream(
        self,
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> AsyncGenerator[str, None]:
        """Process chat with Server-Sent Events for progress updates."""
        if not self.is_available:
            yield sse_error("AI service not available")
            return
        
        try:
            yield sse_status("Searching for relevant slides...")
            search_results = self._search_slides(message)
            
            yield sse_status("Analyzing slides...")
            input_text = self._build_prompt(search_results, message, history)
            response_data = await self._invoke_agent(input_text)
            
            slides = [ReferencedSlide(**s) for s in response_data.get("referenced_slides", [])]
            enriched = self._enrich_slides(slides, search_results)
            
            yield sse_event("response", {
                "answer": response_data.get("answer", ""),
                "referenced_slides": [s.model_dump() for s in enriched],
                "follow_up_suggestions": response_data.get("follow_up_suggestions", []),
            })
            yield sse_done()
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield sse_error("An error occurred")
    
    # -------------------------------------------------------------------------
    # Agent Invocation
    # -------------------------------------------------------------------------
    
    @with_maf_telemetry("SlideAssistant", "AI-powered slide search assistant")
    async def _invoke_agent(self, input_text: str, **kwargs) -> dict:
        """Call Foundry agent - wrapped with MAF for telemetry."""
        self._ensure_client()
        
        response = self._openai.responses.create(
            input=input_text,
            extra_body={"agent": {"name": self._settings.azure_ai_foundry_agent_name, "type": "agent_reference"}},
        )
        
        return extract_function_call(
            response,
            "provide_chat_response",
            fallback={
                "answer": "I couldn't generate a response.",
                "referenced_slides": [],
                "follow_up_suggestions": ["Try searching for a specific topic"],
            },
        )
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _search_slides(self, query: str) -> list[dict]:
        """Search for relevant slides."""
        search_service = get_search_service()
        results, _, _ = search_service.search(query, limit=15)
        
        return [{
            "slide_id": r.slide_id,
            "session_code": r.session_code,
            "slide_number": r.slide_number,
            "title": r.title,
            "content": r.content,
            "event": r.event,
            "session_url": r.session_url,
            "ppt_url": r.ppt_url,
            "score": r.score,
            "thumbnail_url": f"/thumbnails/{r.session_code}_{r.slide_number}.png" if r.has_thumbnail else None,
        } for r in results]
    
    def _build_prompt(
        self,
        search_results: list[dict],
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> str:
        """Build prompt with search context and conversation history."""
        context = "## Available Slides:\n\n"
        for i, slide in enumerate(search_results[:10], 1):
            context += f"### Slide {i}\n"
            context += f"- **ID**: {slide['slide_id']}\n"
            context += f"- **Session**: {slide['session_code']} (#{slide['slide_number']})\n"
            context += f"- **Title**: {slide['title']}\n"
            context += f"- **Event**: {slide['event']}\n"
            context += f"- **URLs**: {slide['session_url']} | {slide['ppt_url']}\n"
            context += f"- **Content**: {slide['content'][:500]}...\n\n"
        
        parts = [f"Search results:\n\n{context}"]
        for msg in (history or [])[-6:]:
            parts.append(f"[{msg.role.upper()}]: {msg.content}")
        parts.append(f"[USER]: {message}")
        
        return "\n\n".join(parts)
    
    def _enrich_slides(
        self,
        slides: list[ReferencedSlide],
        search_results: list[dict],
    ) -> list[ReferencedSlide]:
        """Add thumbnail URLs to slides from search results."""
        lookup = {s["slide_id"]: s for s in search_results}
        
        return [
            ReferencedSlide(
                slide_id=s.slide_id,
                session_code=s.session_code,
                slide_number=s.slide_number,
                title=s.title,
                content=s.content[:300],
                event=s.event,
                session_url=s.session_url or lookup.get(s.slide_id, {}).get("session_url", ""),
                ppt_url=lookup.get(s.slide_id, {}).get("ppt_url", ""),
                relevance_reason=s.relevance_reason,
                thumbnail_url=lookup.get(s.slide_id, {}).get("thumbnail_url"),
            )
            for s in slides
        ]
    
    def _error_response(self, message: str) -> ChatResponse:
        return ChatResponse(
            answer=message,
            referenced_slides=[],
            follow_up_suggestions=["Try rephrasing your question", "Search for a specific topic"],
        )


# =============================================================================
# Singleton Access
# =============================================================================

_service: Optional[SlideAssistantService] = None


def get_slide_assistant_service() -> SlideAssistantService:
    """Get singleton service instance."""
    global _service
    if _service is None:
        _service = SlideAssistantService()
    return _service
