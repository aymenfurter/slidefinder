"""
AI Overview Service

Generates concise AI-powered overviews of search results using gpt-4.1-nano
for lightweight, fast summarization of available slide content.

Uses Microsoft Agent Framework for consistent orchestration across all AI services.
"""
import json
import logging
from typing import Optional, AsyncIterator

from agent_framework import ChatMessage, Role
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.core import get_settings

logger = logging.getLogger(__name__)

# Agent instructions for AI overview generation
OVERVIEW_AGENT_INSTRUCTIONS = """You are an expert at summarizing Microsoft Build and Ignite presentation content.
Generate a brief, helpful overview (2-4 sentences) of what presentation slides are available for the user's query.

Guidelines:
- Be concise and informative
- Highlight the TOP 1-2 session decks that have the best slides for this topic (mention session codes like BRK121, KEY001)
- Explain what makes those decks particularly relevant (e.g., "BRK121 covers AKS Automatic from basics to deployment")
- Mention other notable themes or sessions if relevant
- Use markdown formatting: **bold** for session codes and key terms
- Do NOT use headers or bullet points
- Keep it to 2-4 sentences maximum"""


def build_user_prompt(query: str, context_data, result_count: int, unique_sessions: int) -> str:
    """Build the user prompt for AI overview generation."""
    context_str = context_data[:3000] if isinstance(context_data, str) else json.dumps(context_data, indent=2)[:3000]
    return f"""Search query: "{query}"

Found {result_count} matching slides across {unique_sessions} presentations.

Search results summary (includes session codes, titles, and content snippets):
{context_str}

Generate a brief overview highlighting which session decks have the best slides for this topic."""


class AIOverviewService:
    """
    Service for generating AI overviews of search results.
    
    Uses Microsoft Agent Framework with Azure OpenAI gpt-4.1-nano deployment 
    for fast, lightweight summarization of available slide content.
    """
    
    def __init__(self):
        """Initialize the AI Overview service."""
        self._settings = get_settings()
        self._chat_client: Optional[AzureOpenAIChatClient] = None
        self._overview_agent = None
    
    def _ensure_client(self) -> None:
        """Ensure the chat client and agent are initialized."""
        if self._chat_client is None:
            if not self._settings.has_azure_openai:
                raise ValueError("Azure OpenAI is not configured")
            
            credential = DefaultAzureCredential()
            self._chat_client = AzureOpenAIChatClient(
                credential=credential,
                endpoint=self._settings.azure_openai_endpoint or "",
                deployment_name=self._settings.azure_openai_nano_deployment,
                api_version=self._settings.azure_openai_api_version,
            )
            
            # Create the overview agent
            self._overview_agent = self._chat_client.create_agent(
                name="OverviewAgent",
                instructions=OVERVIEW_AGENT_INSTRUCTIONS,
            )
    
    @property
    def is_available(self) -> bool:
        """Check if the AI Overview service is available."""
        return self._settings.has_azure_openai
    
    async def generate_overview(
        self,
        query: str,
        search_context: str,
        result_count: int,
        unique_sessions: int,
    ) -> str:
        """
        Generate an AI overview of search results.
        
        Args:
            query: The original search query
            search_context: The finishContext JSON from agentic retrieval
            result_count: Number of matching slides found
            unique_sessions: Number of unique presentation sessions
            
        Returns:
            Generated overview text (markdown formatted)
        """
        if not self.is_available:
            return ""
        
        try:
            self._ensure_client()
            
            user_prompt = build_user_prompt(query, search_context, result_count, unique_sessions)

            response = await self._overview_agent.run(
                [ChatMessage(role=Role.USER, text=user_prompt)]
            )
            
            # For plain text responses, use response.text (not response.value)
            # response.value is only populated when using structured output
            if response.text:
                return response.text.strip()
            
            return ""
            
        except Exception as e:
            logger.error(f"Failed to generate AI overview: {e}")
            return ""
    
    async def generate_overview_stream(
        self,
        query: str,
        search_context: str,
        result_count: int,
        unique_sessions: int,
    ) -> AsyncIterator[str]:
        """
        Generate an AI overview with streaming response.
        
        Args:
            query: The original search query
            search_context: The finishContext JSON from agentic retrieval
            result_count: Number of matching slides found
            unique_sessions: Number of unique presentation sessions
            
        Yields:
            Chunks of the generated overview text
        """
        if not self.is_available:
            return
        
        try:
            self._ensure_client()
            
            user_prompt = build_user_prompt(query, search_context, result_count, unique_sessions)

            async for chunk in self._overview_agent.run_stream(
                [ChatMessage(role=Role.USER, text=user_prompt)]
            ):
                # Stream chunks have text attribute
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
                elif hasattr(chunk, 'delta') and chunk.delta:
                    yield chunk.delta
                    
        except Exception as e:
            logger.error(f"Failed to generate AI overview stream: {e}")


# Singleton instance
_ai_overview_service: Optional[AIOverviewService] = None


def get_ai_overview_service() -> AIOverviewService:
    """Get the singleton AI Overview service instance."""
    global _ai_overview_service
    if _ai_overview_service is None:
        _ai_overview_service = AIOverviewService()
    return _ai_overview_service
