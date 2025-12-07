"""
Search service for slide content using Azure AI Search.

Security: All file paths are derived from the search index, not user input.
"""
import logging
import os
from pathlib import Path
from typing import Optional

import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from config import get_settings
from models.slide import SlideInfo, SlideSearchResult

logger = logging.getLogger(__name__)


class AzureSearchService:
    """
    Service for searching slide content using Azure AI Search.
    
    Thread-safe and suitable for use in async context.
    """
    
    def __init__(self):
        """
        Initialize the Azure search service.
        """
        self._settings = get_settings()
        self._available_pptx_cache: Optional[set[str]] = None
        self._client: Optional[SearchClient] = None
    
    @property
    def _search_client(self) -> SearchClient:
        """Get or create the Azure Search client."""
        if self._client is None:
            if not self._settings.has_azure_search:
                raise ValueError("Azure AI Search is not configured")
            
            self._client = SearchClient(
                endpoint=self._settings.azure_search_endpoint,
                index_name=self._settings.azure_search_index_name,
                credential=AzureKeyCredential(self._settings.azure_search_api_key)
            )
        return self._client
    
    @property
    def index_exists(self) -> bool:
        """Check if the search index is available."""
        return self._settings.has_azure_search
    
    def get_available_pptx_sessions(self) -> set[str]:
        """
        Get session codes that have local PPTX files.
        
        Cached for performance.
        """
        if self._available_pptx_cache is None:
            ppts_dir = self._settings.ppts_dir
            if ppts_dir.exists():
                self._available_pptx_cache = {p.stem for p in ppts_dir.glob("*.pptx")}
            else:
                self._available_pptx_cache = set()
        return self._available_pptx_cache
    
    def invalidate_pptx_cache(self) -> None:
        """Invalidate the PPTX sessions cache."""
        self._available_pptx_cache = None
    
    def search(
        self, 
        query: str, 
        limit: Optional[int] = None,
        include_pptx_status: bool = True
    ) -> tuple[list[SlideSearchResult], float]:
        """
        Search for slides matching the query using agentic retrieval.
        
        Uses Azure AI Search knowledge base API (2025-11-01-preview)
        for intelligent retrieval with reasoning and hybrid search.
        
        Args:
            query: Search query string (natural language question works best)
            limit: Maximum number of results (defaults to settings)
            include_pptx_status: Whether to check PPTX availability
            
        Returns:
            Tuple of (results list, search time in ms)
        """
        import time
        start_time = time.time()
        
        if not self.index_exists:
            return [], 0.0
        
        limit = limit or self._settings.search_results_limit
        
        available_pptx = self.get_available_pptx_sessions() if include_pptx_status else set()
        thumbnails_dir = self._settings.thumbnails_dir
        
        results = []
        logger.info(f"Agentic search for: {query}")
        
        # Use agentic retrieval via knowledge base
        endpoint = self._settings.azure_search_endpoint.rstrip('/')
        api_key = self._settings.azure_search_api_key
        knowledge_base_name = "slidefinder-kb"
        
        url = f"{endpoint}/knowledgebases('{knowledge_base_name}')/retrieve?api-version=2025-11-01-preview"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        
        # Agentic retrieval payload - query as natural language question
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": query
                        }
                    ]
                }
            ],
            "maxRuntimeInSeconds": 60,
            "maxOutputSize": 100000,
            "retrievalReasoningEffort": {
                "kind": "low"
            },
            "includeActivity": False,
            "outputMode": "extractiveData",
            "knowledgeSourceParams": [
                {
                    "knowledgeSourceName": "slidefinder-ks",
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                    "kind": "searchIndex"
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            
            if response.status_code in (200, 206):
                data = response.json()
                
                # Extract slides from references
                for ref in data.get("references", []):
                    if len(results) >= limit:
                        break
                        
                    source_data = ref.get("sourceData", {})
                    session_code = source_data.get("session_code", "")
                    slide_number = source_data.get("slide_number", 0)
                    content = source_data.get("content", "")
                    
                    # Check thumbnail existence
                    thumb_filename = f"{session_code}_{slide_number}.png"
                    thumb_path = thumbnails_dir / thumb_filename
                    
                    # Get reranker score
                    score = ref.get("rerankerScore", 1.0)
                    
                    results.append(SlideSearchResult(
                        slide_id=source_data.get("slide_id", ref.get("docKey", "")),
                        session_code=session_code,
                        title=source_data.get("title", ""),
                        slide_number=int(slide_number) if slide_number else 0,
                        content=content[:400] if include_pptx_status else content,
                        snippet=content[:200] + "..." if len(content) > 200 else content,
                        event=source_data.get("event", ""),
                        session_url=source_data.get("session_url", ""),
                        ppt_url=source_data.get("ppt_url", ""),
                        has_thumbnail=thumb_path.exists(),
                        has_pptx=session_code in available_pptx,
                        score=score,
                    ))
            else:
                logger.error(f"Agentic retrieval failed ({response.status_code}): {response.text[:200]}")
                search_time_ms = round((time.time() - start_time) * 1000, 2)
                return [], search_time_ms
                
        except Exception as e:
            logger.error(f"Agentic retrieval error: {e}")
            search_time_ms = round((time.time() - start_time) * 1000, 2)
            return [], search_time_ms
        
        search_time_ms = round((time.time() - start_time) * 1000, 2)
        return results, search_time_ms
    
    def get_slide_info(
        self, 
        session_code: str, 
        slide_number: int
    ) -> Optional[SlideInfo]:
        """
        Get information about a specific slide from the index.
        
        Args:
            session_code: Session code
            slide_number: Slide number
            
        Returns:
            SlideInfo if found, None otherwise
        """
        if not self.index_exists:
            return None
        
        # Sanitize input
        safe_session_code = "".join(c for c in session_code if c.isalnum() or c in "-_")
        slide_id = f"{safe_session_code}_{slide_number}"
        
        try:
            doc = self._search_client.get_document(key=slide_id)
            
            if doc:
                return SlideInfo(
                    slide_id=doc["slide_id"],
                    session_code=doc["session_code"],
                    slide_number=int(doc["slide_number"]),
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    event=doc.get("event", ""),
                    session_url=doc.get("session_url", ""),
                    ppt_url=doc.get("ppt_url", ""),
                )
        except Exception as e:
            logger.warning(f"Failed to get slide {slide_id}: {e}")
        
        return None
    
    def get_ppt_url_for_session(self, session_code: str) -> Optional[str]:
        """
        Get the PPTX download URL for a session.
        
        Args:
            session_code: Session code
            
        Returns:
            Download URL if available, None otherwise
        """
        if not self.index_exists:
            return None
        
        # Sanitize input
        safe_session_code = "".join(c for c in session_code if c.isalnum() or c in "-_")
        
        try:
            # Search for any slide in this session
            results = self._search_client.search(
                search_text="*",
                filter=f"session_code eq '{safe_session_code}'",
                top=1,
                select=["ppt_url"],
            )
            
            for hit in results:
                ppt_url = hit.get("ppt_url", "")
                if ppt_url:
                    return ppt_url
                    
        except Exception as e:
            logger.warning(f"Failed to get ppt_url for {session_code}: {e}")
        
        return None
    
    def get_session_slides(
        self,
        session_code: str,
        include_pptx_status: bool = True
    ) -> tuple[list[SlideSearchResult], Optional[dict]]:
        """
        Get all slides for a specific session code.
        
        Args:
            session_code: Session code (e.g., BRK108)
            include_pptx_status: Whether to check PPTX availability
            
        Returns:
            Tuple of (list of slides sorted by slide number, session info dict or None)
        """
        if not self.index_exists:
            return [], None
        
        # Sanitize input
        safe_session_code = "".join(c for c in session_code if c.isalnum() or c in "-_").upper()
        
        available_pptx = self.get_available_pptx_sessions() if include_pptx_status else set()
        thumbnails_dir = self._settings.thumbnails_dir
        
        results = []
        session_info = None
        
        try:
            # Search for all slides in this session
            search_results = self._search_client.search(
                search_text="*",
                filter=f"session_code eq '{safe_session_code}'",
                top=500,  # Max slides per session
                order_by=["slide_number asc"],
            )
            
            for hit in search_results:
                slide_number = hit["slide_number"]
                content = hit.get("content", "")
                
                # Check thumbnail existence
                thumb_filename = f"{safe_session_code}_{slide_number}.png"
                thumb_path = thumbnails_dir / thumb_filename
                
                # Capture session info from first hit
                if session_info is None:
                    session_info = {
                        "session_code": safe_session_code,
                        "title": hit.get("title", ""),
                        "event": hit.get("event", ""),
                        "session_url": hit.get("session_url", ""),
                        "ppt_url": hit.get("ppt_url", ""),
                        "has_pptx": safe_session_code in available_pptx,
                    }
                
                results.append(SlideSearchResult(
                    slide_id=hit["slide_id"],
                    session_code=safe_session_code,
                    title=hit.get("title", ""),
                    slide_number=int(slide_number),
                    content=content[:400] if include_pptx_status else content,
                    snippet=content[:200] + "..." if len(content) > 200 else content,
                    event=hit.get("event", ""),
                    session_url=hit.get("session_url", ""),
                    ppt_url=hit.get("ppt_url", ""),
                    has_thumbnail=thumb_path.exists(),
                    has_pptx=safe_session_code in available_pptx,
                    score=1.0,
                ))
                
        except Exception as e:
            logger.error(f"Failed to get session slides for {session_code}: {e}")
            return [], None
        
        # Sort by slide number (should already be sorted, but ensure)
        results.sort(key=lambda x: x.slide_number)
        
        return results, session_info


# Singleton instance
_azure_search_service: Optional[AzureSearchService] = None


def get_azure_search_service() -> AzureSearchService:
    """Get the singleton Azure search service instance."""
    global _azure_search_service
    if _azure_search_service is None:
        _azure_search_service = AzureSearchService()
    return _azure_search_service
