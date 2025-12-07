#!/usr/bin/env python3
"""
SlideFinder Indexer CLI - Complete Indexing Pipeline

This orchestrates the full indexing workflow:
  Step 1: Fetch sessions and create slide_index.jsonl
  Step 2: Generate thumbnails (using Azure Container Apps)
  Step 3: Delete and repopulate Azure AI Search
  Step 4: Setup knowledge source/base for agentic retrieval
  Step 5: Verify search functionality

Usage:
    python indexer/cli.py                      # Run full pipeline
    python indexer/cli.py --step 1             # Only Step 1: Create JSONL index
    python indexer/cli.py --step 2             # Only Step 2: Generate thumbnails
    python indexer/cli.py --step 3             # Only Step 3: Populate AI Search
    python indexer/cli.py --step 4             # Only Step 4: Setup knowledge source/base
    python indexer/cli.py --step 5             # Only Step 5: Verify search
    python indexer/cli.py --limit 10           # Limit sessions for testing
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings

from indexer.models import IndexingStats
from indexer.fetcher import fetch_all_sessions
from indexer.slide_indexer import create_slide_index, load_sessions_from_jsonl
from indexer.thumbnails import AzureDeployer, ThumbnailGenerator
from indexer.ai_search import (
    create_index,
    delete_index,
    upload_documents,
    verify_index,
    get_index_stats,
    setup_knowledge_source,
    setup_knowledge_base,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
INDEXER_DIR = Path(__file__).parent
DATA_DIR = INDEXER_DIR / "data"
SLIDE_INDEX_FILE = DATA_DIR / "slide_index.jsonl"
THUMBS_DIR = DATA_DIR / "thumbnails"
PPTS_DIR = DATA_DIR / "ppts"


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


async def step1_create_index(
    limit: int = None,
    include_build: bool = True,
    include_ignite: bool = True,
    include_partner: bool = True,
    partner_max_age: int = 0,
    download_ppts: bool = True,
) -> int:
    """
    Step 1: Fetch sessions and create slide_index.jsonl
    
    Returns:
        Number of slides indexed
    """
    print_header("Step 1: Create Slide Index (JSONL)")
    
    # Ensure directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Fetch sessions
    print("\n📡 Fetching sessions from Microsoft APIs...")
    sessions = await fetch_all_sessions(
        include_build=include_build,
        include_ignite=include_ignite,
        include_partner=include_partner,
        partner_max_age_months=partner_max_age,
    )
    
    if limit:
        sessions = sessions[:limit]
        print(f"   (Limited to {limit} sessions for testing)")
    
    if not sessions:
        print("⚠️  No sessions found!")
        return 0
    
    print(f"   Found {len(sessions)} sessions with slides")
    
    # Create JSONL index
    print(f"\n📝 Creating slide index...")
    count = await create_slide_index(
        sessions=sessions,
        output_file=SLIDE_INDEX_FILE,
        ppts_dir=PPTS_DIR,
        download_ppts=download_ppts,
    )
    
    print(f"\n✅ Step 1 Complete!")
    print(f"   Output: {SLIDE_INDEX_FILE}")
    print(f"   Records: {count:,}")
    
    return count


async def step2_generate_thumbnails(
    limit: int = None,
    parallel: int = 2,
    service_url: str = None,
    skip_deploy: bool = False,
) -> tuple[int, int, int]:
    """
    Step 2: Generate thumbnails using Azure Container Apps
    
    Returns:
        Tuple of (generated, failed, skipped) counts
    """
    print_header("Step 2: Generate Thumbnails")
    
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load sessions from existing index
    if not SLIDE_INDEX_FILE.exists():
        print(f"❌ Slide index not found: {SLIDE_INDEX_FILE}")
        print("   Run Step 1 first to create the index.")
        return 0, 0, 0
    
    sessions = load_sessions_from_jsonl(SLIDE_INDEX_FILE)
    
    if limit:
        sessions = sessions[:limit]
        print(f"   (Limited to {limit} sessions)")
    
    print(f"   Found {len(sessions)} sessions in index")
    
    # Get or deploy thumbnail service
    if service_url:
        print(f"\n🔗 Using provided service: {service_url}")
    elif skip_deploy:
        print("❌ No service URL provided and --skip-deploy specified")
        return 0, 0, 0
    else:
        print("\n🚀 Deploying thumbnail service to Azure Container Apps...")
        
        deployer = AzureDeployer()
        if not deployer.discover_resources():
            print("❌ Could not find Azure resources.")
            print("   Run 'azd up' first to deploy infrastructure.")
            return 0, 0, 0
        
        # Build and deploy
        service_dir = INDEXER_DIR / "thumbnail_service"
        deployer.build_and_push(service_dir)
        service_url = deployer.deploy_service(replicas=parallel)
    
    # Generate thumbnails
    print(f"\n🖼️  Generating thumbnails ({parallel} parallel)...")
    
    generator = ThumbnailGenerator(
        service_url=service_url,
        output_dir=THUMBS_DIR,
        max_parallel=parallel,
    )
    
    generated, failed, skipped = await generator.generate_all(sessions)
    
    print(f"\n✅ Step 2 Complete!")
    print(f"   Generated: {generated:,}")
    print(f"   Skipped:   {skipped:,}")
    print(f"   Failed:    {failed:,}")
    print(f"   Output:    {THUMBS_DIR}")
    
    return generated, failed, skipped


def step3_populate_search(delete_first: bool = True) -> tuple[int, int]:
    """
    Step 3: Delete and repopulate Azure AI Search
    
    Returns:
        Tuple of (successful, failed) counts
    """
    print_header("Step 3: Populate Azure AI Search")
    
    settings = get_settings()
    
    if not settings.has_azure_search:
        print("❌ Azure AI Search is not configured.")
        print("   Set AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, and AZURE_SEARCH_INDEX_NAME in .env")
        return 0, 0
    
    print(f"   Endpoint: {settings.azure_search_endpoint}")
    print(f"   Index:    {settings.azure_search_index_name}")
    
    # Check for JSONL file
    if not SLIDE_INDEX_FILE.exists():
        print(f"\n❌ Slide index not found: {SLIDE_INDEX_FILE}")
        print("   Run Step 1 first to create the index.")
        return 0, 0
    
    # Delete and recreate index
    if delete_first:
        print(f"\n🗑️  Deleting existing index...")
        delete_index(
            endpoint=settings.azure_search_endpoint,
            api_key=settings.azure_search_api_key,
            index_name=settings.azure_search_index_name,
        )
    
    print(f"\n📝 Creating index schema...")
    create_index(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
        delete_first=False,
    )
    
    # Upload documents
    print(f"\n📤 Uploading documents...")
    successful, failed = upload_documents(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
        jsonl_path=SLIDE_INDEX_FILE,
    )
    
    print(f"\n✅ Step 3 Complete!")
    print(f"   Uploaded: {successful:,}")
    print(f"   Failed:   {failed:,}")
    
    return successful, failed


def step4_setup_knowledge_source() -> bool:
    """
    Step 4: Setup knowledge source and knowledge base for agentic retrieval.
    
    This configures which fields are returned when using the knowledge base API.
    
    Returns:
        True if successful
    """
    print_header("Step 4: Setup Knowledge Source/Base")
    
    settings = get_settings()
    
    if not settings.has_azure_search:
        print("❌ Azure AI Search is not configured.")
        return False
    
    print(f"   Endpoint: {settings.azure_search_endpoint}")
    print(f"   Index:    {settings.azure_search_index_name}")
    
    # Setup knowledge source
    print(f"\n📚 Configuring knowledge source...")
    ks_success = setup_knowledge_source(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
        knowledge_source_name="slidefinder-ks",
    )
    
    if not ks_success:
        print("   ❌ Failed to configure knowledge source")
        return False
    
    print("   ✅ Knowledge source configured")
    
    # Setup knowledge base
    print(f"\n📖 Configuring knowledge base...")
    kb_success = setup_knowledge_base(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        knowledge_base_name="slidefinder-kb",
        knowledge_source_name="slidefinder-ks",
    )
    
    if not kb_success:
        print("   ❌ Failed to configure knowledge base")
        return False
    
    print("   ✅ Knowledge base configured")
    
    print(f"\n✅ Step 4 Complete!")
    print("   Knowledge source and base ready for agentic retrieval")
    
    return True


def step5_verify_search(queries: list[str] = None) -> bool:
    """
    Step 5: Verify search functionality
    
    Returns:
        True if verification passes
    """
    print_header("Step 5: Verify Search")
    
    settings = get_settings()
    
    if not settings.has_azure_search:
        print("❌ Azure AI Search is not configured.")
        return False
    
    print(f"   Endpoint: {settings.azure_search_endpoint}")
    print(f"   Index:    {settings.azure_search_index_name}")
    
    # Get stats
    print(f"\n📊 Index Statistics:")
    stats = get_index_stats(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
    )
    
    if not stats["exists"]:
        print("   ❌ Index does not exist!")
        return False
    
    print(f"   Documents: {stats['document_count']:,}")
    print(f"   Fields:    {len(stats['fields'])}")
    
    # Run verification queries
    queries = queries or ["AI", "Azure", "machine learning", "cloud", "security"]
    
    print(f"\n🔍 Running test queries...")
    success = verify_index(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
        test_queries=queries,
    )
    
    if success:
        print(f"\n✅ Step 5 Complete! Search is working correctly.")
    else:
        print(f"\n❌ Step 5 Failed! Some queries did not work.")
    
    return success


async def run_full_pipeline(
    limit: int = None,
    parallel: int = 2,
    service_url: str = None,
    skip_thumbnails: bool = False,
    download_ppts: bool = True,
):
    """Run the complete indexing pipeline."""
    print_header("SlideFinder Indexer - Full Pipeline")
    
    stats = IndexingStats()
    
    # Step 1: Create JSONL index
    slides = await step1_create_index(
        limit=limit,
        download_ppts=download_ppts,
    )
    stats.slides_indexed = slides
    
    if slides == 0:
        print("\n❌ No slides indexed. Stopping pipeline.")
        return stats
    
    # Step 2: Generate thumbnails (optional)
    if not skip_thumbnails:
        gen, failed, skipped = await step2_generate_thumbnails(
            limit=limit,
            parallel=parallel,
            service_url=service_url,
        )
        stats.thumbnails_generated = gen
        stats.thumbnails_skipped = skipped
        stats.errors = failed
    else:
        print("\n⏭️  Skipping thumbnail generation (--skip-thumbnails)")
    
    # Step 3: Populate Azure AI Search
    successful, failed = step3_populate_search(delete_first=True)
    stats.errors += failed
    
    # Step 4: Setup knowledge source/base
    step4_setup_knowledge_source()
    
    # Step 5: Verify
    step5_verify_search()
    
    # Summary
    print_header("Pipeline Complete!")
    print(f"   {stats}")
    
    return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SlideFinder Indexer - Complete Indexing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  1. Create slide_index.jsonl from Microsoft APIs
  2. Generate thumbnails (using Azure Container Apps)
  3. Delete and repopulate Azure AI Search
  4. Setup knowledge source/base for agentic retrieval
  5. Verify search functionality

Examples:
  python indexer/cli.py                      # Full pipeline
  python indexer/cli.py --step 1             # Only create JSONL index
  python indexer/cli.py --step 2             # Only generate thumbnails
  python indexer/cli.py --step 3             # Only populate AI Search
  python indexer/cli.py --step 4             # Only setup knowledge source/base
  python indexer/cli.py --step 5             # Only verify search
  python indexer/cli.py --limit 10           # Test with 10 sessions
  python indexer/cli.py --skip-thumbnails    # Skip Step 2
        """
    )
    
    parser.add_argument(
        "--step", "-s",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run only a specific step (1-5)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of sessions (for testing)"
    )
    parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=2,
        help="Parallel thumbnail requests (default: 2)"
    )
    parser.add_argument(
        "--service-url",
        type=str,
        help="Use existing thumbnail service URL"
    )
    parser.add_argument(
        "--skip-thumbnails",
        action="store_true",
        help="Skip thumbnail generation (Step 2)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip PPTX download (create placeholder index)"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Exclude Microsoft Build sessions"
    )
    parser.add_argument(
        "--no-ignite",
        action="store_true",
        help="Exclude Microsoft Ignite sessions"
    )
    parser.add_argument(
        "--no-partner",
        action="store_true",
        help="Exclude Partner presentations"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run specific step or full pipeline
    if args.step == 1:
        asyncio.run(step1_create_index(
            limit=args.limit,
            include_build=not args.no_build,
            include_ignite=not args.no_ignite,
            include_partner=not args.no_partner,
            download_ppts=not args.skip_download,
        ))
    elif args.step == 2:
        asyncio.run(step2_generate_thumbnails(
            limit=args.limit,
            parallel=args.parallel,
            service_url=args.service_url,
        ))
    elif args.step == 3:
        step3_populate_search()
    elif args.step == 4:
        step4_setup_knowledge_source()
    elif args.step == 5:
        step5_verify_search()
    else:
        # Full pipeline
        asyncio.run(run_full_pipeline(
            limit=args.limit,
            parallel=args.parallel,
            service_url=args.service_url,
            skip_thumbnails=args.skip_thumbnails,
            download_ppts=not args.skip_download,
        ))


if __name__ == "__main__":
    main()
