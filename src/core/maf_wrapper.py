"""
Microsoft Agent Framework (MAF) wrapper for Foundry Agents V2.

TEMPORARY WORKAROUND (December 2025):
At the time of writing, MAF only supports V1 Agents via AzureAIAgentClient.
V2 Agents (Foundry Agents with PromptAgentDefinition and Responses API) are
not yet supported by MAF's built-in clients.

This wrapper bridges that gap by providing a simple decorator that:
1. Wraps any async function in MAF's BaseAgent for telemetry
2. Creates OpenTelemetry spans automatically
3. Captures usage metrics

Once MAF adds native V2 support, this wrapper can be removed.

Usage:
    @with_maf_telemetry("MyAgent")
    async def my_agent_call(self, input_text: str) -> dict:
        # Your Foundry SDK code here
        return {"answer": "..."}
"""

import functools
import json
import logging
from typing import Any, Callable, TypeVar

from agent_framework import BaseAgent, AgentRunResponse, ChatMessage, Role, TextContent
from agent_framework.observability import use_agent_instrumentation

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Foundry Response Helpers
# =============================================================================

def extract_function_call(response, function_name: str, fallback: dict | None = None) -> dict:
    """
    Extract function call arguments from a Foundry Responses API response.
    
    This is a common pattern when using function calling with Foundry agents.
    The agent is configured to call a specific function, and this helper
    extracts the JSON arguments from that call.
    
    Args:
        response: The response from openai.responses.create()
        function_name: Name of the function to extract (e.g., "provide_chat_response")
        fallback: Default dict to return if function wasn't called
    
    Returns:
        Parsed JSON arguments from the function call, or fallback dict
    """
    for item in response.output:
        if item.type == "function_call" and item.name == function_name:
            return json.loads(item.arguments)
    
    if fallback is not None:
        return fallback
    
    # Default fallback with answer from output_text
    return {
        "answer": getattr(response, "output_text", None) or "I couldn't generate a response.",
    }


# =============================================================================
# SSE Streaming Helpers
# =============================================================================

def sse_event(event_type: str, data: dict | str | None = None) -> str:
    """Format a Server-Sent Event."""
    if data is None:
        payload = {"type": event_type}
    elif isinstance(data, str):
        payload = {"type": event_type, "message": data}
    else:
        payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


def sse_status(message: str) -> str:
    """Send a status update SSE."""
    return sse_event("status", message)


def sse_error(message: str) -> str:
    """Send an error SSE."""
    return sse_event("error", {"message": message})


def sse_done() -> str:
    """Send completion SSE."""
    return 'data: {"type": "done"}\n\n'


# =============================================================================
# MAF Telemetry Wrapper
# =============================================================================

@use_agent_instrumentation(capture_usage=True)
class _TelemetryAgent(BaseAgent):
    """Internal MAF agent that provides telemetry for a single call."""

    def __init__(self, name: str, description: str, result: dict) -> None:
        super().__init__(name=name, description=description)
        self._result = result

    async def run(self, messages=None, *, thread=None, **kwargs) -> AgentRunResponse:
        """Create response from pre-computed result (telemetry is recorded by decorator)."""
        return AgentRunResponse(messages=[
            ChatMessage(role=Role.ASSISTANT, contents=[
                TextContent(text=self._result.get("answer", ""))
            ])
        ])

    async def run_stream(self, messages=None, *, thread=None, **kwargs):
        result = await self.run(messages, thread=thread, **kwargs)
        for msg in result.messages:
            yield msg


def with_maf_telemetry(agent_name: str, description: str = "Foundry Agent V2"):
    """
    Decorator that adds MAF telemetry to any async function returning a dict.
    
    The decorated function should return a dict with at least an "answer" key.
    All MAF instrumentation (spans, metrics) is handled automatically.
    
    Example:
        @with_maf_telemetry("SlideAssistant")
        async def _invoke_agent(self, input_text: str) -> dict:
            response = self._openai.responses.create(...)
            return extract_function_call(response, "my_function")
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> dict:
            # 1. Call the actual Foundry function
            result = await fn(*args, **kwargs)
            
            # 2. Create a MAF agent to record telemetry
            agent = _TelemetryAgent(agent_name, description, result)
            await agent.run()
            
            return result
        return wrapper
    return decorator
