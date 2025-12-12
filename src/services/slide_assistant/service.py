"""
Slide Assistant Service
Provides AI-powered conversational search for finding slides.

Uses Microsoft Agent Framework for consistent orchestration across all AI services.
Structured output API provides type-safe LLM responses.
"""

import json
import logging
from typing import Optional, AsyncGenerator

from agent_framework import ChatMessage, Role
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential
from pydantic import ValidationError

from src.core import get_settings
from src.services.search import get_search_service
from .models import ChatMessage as ChatHistoryMessage, ChatResponse, ReferencedSlide

logger = logging.getLogger(__name__)


SLIDE_ASSISTANT_INSTRUCTIONS = """You are a helpful slide assistant for SlideFinder, a tool that helps users find slides from Microsoft Build and Ignite conferences.

Your role is to help users find the most relevant slides for their needs. You have access to search results from a large collection of presentation slides.

Guidelines:
- Be conversational and helpful
- When users ask about a topic, suggest specific slides that match their needs
- Explain WHY each slide is relevant to their query
- If you don't find good matches, suggest alternative search terms
- Keep your answers concise but informative
- Always reference specific slides when discussing content

For follow_up_suggestions: Generate 2-3 natural follow-up questions that the USER would logically want to ask next to explore the topic further. These should be phrased as direct questions the user might type, like "Show me slides about Azure security" or "What sessions cover Kubernetes deployment?" - NOT questions directed at the user like "Would you like...?" or "Are you interested in...?"

The search results below contain slides that might be relevant to the user's query. Analyze them and provide helpful recommendations.

Only include slides that are actually relevant to the user's question. Provide a clear relevance_reason for each slide."""


class SlideAssistantService:
    """
    Service for AI-powered slide search assistance.
    
    Uses Microsoft Agent Framework with Azure OpenAI for consistent
    orchestration across all AI services. Structured output provides
    type-safe responses.
    """
    
    def __init__(self):
        """Initialize the slide assistant service."""
        self._settings = get_settings()
        self._chat_client: Optional[AzureOpenAIChatClient] = None
        self._assistant_agent = None
    
    @property
    def is_available(self) -> bool:
        """Check if the service is available."""
        return self._settings.has_azure_openai
    
    def _ensure_client(self) -> None:
        """Ensure the chat client and agent are initialized."""
        if self._chat_client is None:
            credential = DefaultAzureCredential()
            self._chat_client = AzureOpenAIChatClient(
                credential=credential,
                endpoint=self._settings.azure_openai_endpoint or "",
                deployment_name=self._settings.azure_openai_nano_deployment,
                api_version=self._settings.azure_openai_api_version,
            )
            
            # Create the slide assistant agent
            self._assistant_agent = self._chat_client.create_agent(
                name="SlideAssistantAgent",
                instructions=SLIDE_ASSISTANT_INSTRUCTIONS,
            )
    
    def _search_slides(self, query: str) -> list[dict]:
        """Search for relevant slides."""
        search_service = get_search_service()
        results, _, _ = search_service.search(query, limit=15)
        
        slides = []
        for result in results:
            thumbnail_url = None
            if result.has_thumbnail:
                thumbnail_url = f"/thumbnails/{result.session_code}_{result.slide_number}.png"
            
            slides.append({
                "slide_id": result.slide_id,
                "session_code": result.session_code,
                "slide_number": result.slide_number,
                "title": result.title,
                "content": result.content,
                "event": result.event,
                "session_url": result.session_url,
                "ppt_url": result.ppt_url,
                "score": result.score,
                "thumbnail_url": thumbnail_url,
            })
        
        return slides
    
    def _build_context(self, search_results: list[dict]) -> str:
        """Build context string with search results."""
        context = "## Available Slides from Search:\n\n"
        for i, slide in enumerate(search_results[:10], 1):
            context += f"### Slide {i}\n"
            context += f"- **Slide ID**: {slide['slide_id']}\n"
            context += f"- **Session**: {slide['session_code']} (Slide #{slide['slide_number']})\n"
            context += f"- **Title**: {slide['title']}\n"
            context += f"- **Event**: {slide['event']}\n"
            context += f"- **Session URL**: {slide['session_url']}\n"
            context += f"- **PPT URL**: {slide['ppt_url']}\n"
            context += f"- **Content**: {slide['content'][:500]}...\n\n"
        return context
    
    def _build_messages(
        self,
        context: str,
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> list[ChatMessage]:
        """Build message list for the agent."""
        messages = []
        
        # Add context as first user message
        messages.append(ChatMessage(
            role=Role.USER,
            text=f"Here are the search results for context:\n\n{context}"
        ))
        
        # Add history (map assistant to ASSISTANT role)
        history = history or []
        for msg in history[-6:]:  # Keep last 6 messages
            if msg.role == "user":
                messages.append(ChatMessage(role=Role.USER, text=msg.content))
            else:
                messages.append(ChatMessage(role=Role.ASSISTANT, text=msg.content))
        
        # Add current message
        messages.append(ChatMessage(role=Role.USER, text=message))
        
        return messages
    
    async def chat(
        self,
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> ChatResponse:
        """
        Process a chat message and return a structured response.
        
        Args:
            message: The user's message
            history: Previous messages in the conversation
            
        Returns:
            ChatResponse with answer and referenced slides
        """
        if not self.is_available:
            return ChatResponse(
                answer="I'm sorry, the AI service is not available at the moment.",
                referenced_slides=[],
                follow_up_suggestions=[],
            )
        
        try:
            self._ensure_client()
            history = history or []
            
            # Search for relevant slides
            search_results = self._search_slides(message)
            
            # Build context and messages
            context = self._build_context(search_results)
            messages = self._build_messages(context, message, history)
            
            # Use agent with structured output
            response = await self._assistant_agent.run(
                messages,
                response_format=ChatResponse
            )
            
            if response.value and isinstance(response.value, ChatResponse):
                parsed = response.value
            elif response.value:
                # Try to parse if it's a dict or similar
                parsed = ChatResponse.model_validate(response.value)
            else:
                raise ValueError("Failed to parse response")
            
            # Enrich referenced slides with thumbnail URLs from search results
            enriched_slides = self._enrich_slides_with_thumbnails(
                parsed.referenced_slides, search_results
            )
            
            return ChatResponse(
                answer=parsed.answer,
                referenced_slides=enriched_slides,
                follow_up_suggestions=parsed.follow_up_suggestions,
            )
            
        except (ValidationError, ValueError) as e:
            logger.error(f"Slide assistant parsing error: {e}")
            return self._error_response("I couldn't process the response properly.")
        except Exception as e:
            logger.error(f"Slide assistant error: {e}")
            return self._error_response("I encountered an error. Please try again.")
    
    def _enrich_slides_with_thumbnails(
        self,
        slides: list[ReferencedSlide],
        search_results: list[dict],
    ) -> list[ReferencedSlide]:
        """Add thumbnail URLs and ppt URLs to referenced slides from search results."""
        search_lookup = {
            sr["slide_id"]: {
                "thumbnail_url": sr.get("thumbnail_url"),
                "ppt_url": sr.get("ppt_url", ""),
                "session_url": sr.get("session_url", ""),
            }
            for sr in search_results
        }
        
        return [
            ReferencedSlide(
                slide_id=slide.slide_id,
                session_code=slide.session_code,
                slide_number=slide.slide_number,
                title=slide.title,
                content=slide.content[:300],
                event=slide.event,
                session_url=slide.session_url or search_lookup.get(slide.slide_id, {}).get("session_url", ""),
                ppt_url=search_lookup.get(slide.slide_id, {}).get("ppt_url", ""),
                relevance_reason=slide.relevance_reason,
                thumbnail_url=search_lookup.get(slide.slide_id, {}).get("thumbnail_url"),
            )
            for slide in slides
        ]
    
    def _error_response(self, message: str) -> ChatResponse:
        """Create a standard error response."""
        return ChatResponse(
            answer=message,
            referenced_slides=[],
            follow_up_suggestions=["Try rephrasing your question", "Search for a specific topic"],
        )
    
    async def chat_stream(
        self,
        message: str,
        history: list[ChatHistoryMessage] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat message with streaming response.
        
        Uses Microsoft Agent Framework for consistent orchestration.
        Yields SSE-formatted events for real-time UI updates.
        
        Args:
            message: The user's message
            history: Previous messages in the conversation
            
        Yields:
            SSE-formatted event strings
        """
        if not self.is_available:
            yield 'data: {"type": "error", "message": "AI service not available"}\n\n'
            return
        
        try:
            self._ensure_client()
            history = history or []
            
            # First, search for relevant slides
            yield 'data: {"type": "status", "message": "Searching for relevant slides..."}\n\n'
            search_results = self._search_slides(message)
            
            # Send search results for immediate display
            slides_for_frontend = []
            for slide in search_results[:8]:
                slides_for_frontend.append({
                    "slide_id": slide["slide_id"],
                    "session_code": slide["session_code"],
                    "slide_number": slide["slide_number"],
                    "title": slide["title"],
                    "content": slide["content"][:200],
                    "event": slide["event"],
                    "session_url": slide["session_url"],
                    "ppt_url": slide.get("ppt_url", ""),
                    "thumbnail_url": slide.get("thumbnail_url"),
                })
            
            # Build context and messages
            context = self._build_context(search_results)
            messages = self._build_messages(context, message, history)
            
            yield 'data: {"type": "status", "message": "Analyzing slides..."}\n\n'
            
            # Use agent with structured output
            response = await self._assistant_agent.run(
                messages,
                response_format=ChatResponse
            )
            
            if response.value and isinstance(response.value, ChatResponse):
                parsed = response.value
            elif response.value:
                parsed = ChatResponse.model_validate(response.value)
            else:
                raise ValueError("Failed to parse response")
            
            # Enrich referenced slides with thumbnail URLs
            enriched_slides = self._enrich_slides_with_thumbnails(
                parsed.referenced_slides, search_results
            )
            
            # Send the complete response
            final_response = {
                "type": "response",
                "answer": parsed.answer,
                "referenced_slides": [slide.model_dump() for slide in enriched_slides],
                "follow_up_suggestions": parsed.follow_up_suggestions,
            }
            
            yield f'data: {json.dumps(final_response)}\n\n'
            yield 'data: {"type": "done"}\n\n'
            
        except (ValidationError, ValueError) as e:
            logger.error(f"Slide assistant stream parsing error: {e}")
            yield f'data: {json.dumps({"type": "error", "message": "Failed to process response"})}\n\n'
        except Exception as e:
            logger.error(f"Slide assistant stream error: {e}")
            yield f'data: {json.dumps({"type": "error", "message": "An error occurred"})}\n\n'


# Singleton instance
_slide_assistant_service: Optional[SlideAssistantService] = None


def get_slide_assistant_service() -> SlideAssistantService:
    """Get the singleton slide assistant service instance."""
    global _slide_assistant_service
    if _slide_assistant_service is None:
        _slide_assistant_service = SlideAssistantService()
    return _slide_assistant_service
