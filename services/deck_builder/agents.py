"""Agent orchestration for deck building."""

import asyncio
import logging
from typing import AsyncIterator

from agent_framework import ChatMessage, Role
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from config import get_settings
from services.search_service import get_search_service

from .helpers import format_slides_summary
from .models import SlideOutlineItem, PresentationOutline
from .prompts import (
    OUTLINE_AGENT_INSTRUCTIONS,
    OFFER_AGENT_INSTRUCTIONS,
    CRITIQUE_AGENT_INSTRUCTIONS,
    JUDGE_AGENT_INSTRUCTIONS,
)
from .workflow import create_slide_selection_workflow, SlideSelectionState

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Orchestrates outline generation and slide selection workflows."""
    
    def __init__(self):
        settings = get_settings()
        credential = DefaultAzureCredential()
        self._chat_client = AzureOpenAIChatClient(
            credential=credential,
            endpoint=settings.azure_openai_endpoint or "",
            deployment_name=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )
        self._search_service = get_search_service()
        
        # Create agents
        self._outline_agent = self._chat_client.create_agent(
            name="OutlineAgent",
            instructions=OUTLINE_AGENT_INSTRUCTIONS,
        )
        self._offer_agent = self._chat_client.create_agent(
            name="OfferAgent",
            instructions=OFFER_AGENT_INSTRUCTIONS,
        )
        self._critique_agent = self._chat_client.create_agent(
            name="CritiqueAgent",
            instructions=CRITIQUE_AGENT_INSTRUCTIONS,
        )
        self._judge_agent = self._chat_client.create_agent(
            name="JudgeAgent",
            instructions=JUDGE_AGENT_INSTRUCTIONS,
        )
        
        # Create the slide selection workflow
        self._slide_workflow = create_slide_selection_workflow(
            offer_agent=self._offer_agent,
            critique_agent=self._critique_agent,
            judge_agent=self._judge_agent,
        )

    async def generate_outline(
        self,
        query: str,
        available_slides: list[dict]
    ) -> PresentationOutline:
        """Generate a structured presentation outline using the outline agent."""
        slides_summary = format_slides_summary(available_slides)
        
        prompt = f"""Create a presentation outline for: {query}

AVAILABLE SLIDES (from search):
{slides_summary}

Create a structured outline with 5-9 slides."""

        response = await self._outline_agent.run(
            [ChatMessage(role=Role.USER, text=prompt)],
            response_format=PresentationOutline
        )
        if response.value:
            return response.value
        
        raise ValueError("Failed to generate presentation outline")

    async def select_slide_with_critique(
        self,
        outline_item: SlideOutlineItem,
        full_outline: PresentationOutline,
        all_slides: list[dict],
        already_selected_keys: set[str]
    ) -> AsyncIterator[dict]:
        """Run the slide selection workflow for a single slide position."""
        # Create an event queue for real-time streaming
        event_queue: asyncio.Queue[dict] = asyncio.Queue()
        
        def event_callback(event: dict) -> None:
            event_queue.put_nowait(event)
        
        # Create initial state for the workflow with event callback
        initial_state = SlideSelectionState(
            outline_item=outline_item,
            full_outline=full_outline,
            all_slides=all_slides,
            already_selected_keys=already_selected_keys.copy(),
            phase="search",
            event_callback=event_callback
        )
        
        logger.info(f"Starting slide selection workflow for position {outline_item.position}")
        
        # Run the workflow in the background while yielding events
        workflow_task = asyncio.create_task(self._slide_workflow.run(initial_state))
        
        # Poll for events while workflow is running
        while not workflow_task.done():
            try:
                # Check for events with a short timeout
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                # No event available, continue waiting
                continue
        
        # Drain any remaining events in the queue
        while not event_queue.empty():
            event = event_queue.get_nowait()
            yield event
        
        # Get the result
        result = await workflow_task
        
        # Get the final state from workflow outputs
        outputs = result.get_outputs()
        final_state = None
        final_slide = None
        
        if outputs:
            for output in outputs:
                if isinstance(output, SlideSelectionState):
                    final_state = output
                    break
        
        if final_state:
            final_slide = final_state.selected_slide
            logger.info(f"Workflow complete for position {outline_item.position}: {final_slide}")
        else:
            logger.warning(f"No final state from workflow for position {outline_item.position}")
        
        # Yield the final result
        yield {
            "type": "slide_result",
            "slide": final_slide
        }

