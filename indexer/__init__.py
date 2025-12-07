"""
SlideFinder Indexer Module

A modular indexing pipeline for Microsoft Build & Ignite slides.

Modules:
    models          - Data models (SessionInfo, SlideRecord, etc.)
    fetcher         - Fetch sessions from Microsoft APIs
    slide_indexer   - Create JSONL index with slide content
    thumbnails      - Generate thumbnails via Azure Container Apps
    ai_search       - Azure AI Search index management
    cli             - Command-line interface for the full pipeline

Usage:
    python indexer/cli.py                  # Run full pipeline
    python indexer/cli.py --step 1         # Step 1: Create JSONL
    python indexer/cli.py --step 2         # Step 2: Generate thumbnails
    python indexer/cli.py --step 3         # Step 3: Populate AI Search
    python indexer/cli.py --step 4         # Step 4: Verify search

The pipeline flow:
    1. Fetch sessions → slide_index.jsonl (with slide content)
    2. Generate thumbnails → data/thumbnails/*.png
    3. Upload to Azure AI Search
    4. Verify search functionality
"""

from .models import SessionInfo, SlideRecord, IndexingStats, IGNORE_SESSION_CODES
from .fetcher import fetch_all_sessions
from .slide_indexer import create_slide_index, load_sessions_from_jsonl
from .thumbnails import AzureDeployer, ThumbnailGenerator
from .ai_search import (
    create_index,
    delete_index,
    upload_documents,
    verify_index,
    get_index_stats,
    setup_knowledge_source,
    setup_knowledge_base,
)

__all__ = [
    # Models
    "SessionInfo",
    "SlideRecord", 
    "IndexingStats",
    "IGNORE_SESSION_CODES",
    # Fetcher
    "fetch_all_sessions",
    # Slide indexer
    "create_slide_index",
    "load_sessions_from_jsonl",
    # Thumbnails
    "AzureDeployer",
    "ThumbnailGenerator",
    # AI Search
    "create_index",
    "delete_index",
    "upload_documents",
    "verify_index",
    "get_index_stats",
    "setup_knowledge_source",
    "setup_knowledge_base",
]
