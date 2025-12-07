"""
Session fetcher - Fetches session data from Microsoft APIs.

Supports:
- Microsoft Build sessions
- Microsoft Ignite sessions  
- Partner Marketing Center presentations (campaigns -> collections -> presentations)

Partner Marketing Center structure:
  Campaigns page: https://partner.microsoft.com/en-GB/asset/collection/solution-area-partner-marketing-campaigns-content#/
  
  Flow:
    1. Fetch all campaigns from the campaigns API
    2. For each campaign, fetch its collections
    3. For each collection, fetch presentations (PPTX files)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from .models import (
    SessionInfo, 
    API_URLS, 
    HTTP_HEADERS,
    IGNORE_SESSION_CODES,
)

logger = logging.getLogger(__name__)

# Partner Marketing Center API configuration
# Main campaigns page: https://partner.microsoft.com/en-GB/asset/collection/solution-area-partner-marketing-campaigns-content#/
PARTNER_CAMPAIGNS_URL = (
    "https://partner.microsoft.com/api/v2/assetlib2/finder/pagedSearch?"
    "galleryId=%7B2771030A-13D2-4787-88A6-3653082B54CD%7D&"
    "locale=en-GB&"
    "page={page}&"
    "contextItemId=d1d04f40-2050-479c-9099-93d9df81d268&"
    "parentAsset=10747962&"
    "isPreview=false&"
    "search=&"
    "sort=null"
)

# URL template for fetching items under a parent (campaign or collection)
PARTNER_ITEMS_URL = (
    "https://partner.microsoft.com/api/v2/assetlib2/finder/pagedSearch?"
    "galleryId=%7B0A18AEC4-34C0-4E70-B832-4BCC6CD065E8%7D&"
    "locale=en-gb&"
    "page={page}&"
    "contextItemId=bdf76123-d9cd-4b02-bdd5-45d420cec4a8&"
    "parentAsset={parent_id}&"
    "isPreview=false&"
    "search=&"
    "sort=null"
)


async def fetch_build_sessions(http_session: aiohttp.ClientSession) -> list[SessionInfo]:
    """Fetch sessions from Microsoft Build API."""
    sessions = []
    
    try:
        logger.info("Fetching Build sessions...")
        async with http_session.get(API_URLS["build"], headers=HTTP_HEADERS) as resp:
            if resp.status != 200:
                logger.warning(f"Build API returned status {resp.status}")
                return sessions
            
            data = await resp.json()
            
            for s in data:
                if not s.get('slideDeck'):
                    continue
                    
                code = s.get('sessionCode', '')
                if not code or code in IGNORE_SESSION_CODES:
                    continue
                
                sessions.append(SessionInfo(
                    session_code=code,
                    title=s.get('title', 'Unknown'),
                    event='Build',
                    session_id=s.get('sessionId', ''),
                    session_url=f"https://build.microsoft.com/en-US/sessions/{s.get('sessionId', '')}",
                    ppt_url=s.get('slideDeck', '')
                ))
            
            logger.info(f"  Found {len(sessions)} Build sessions with slides")
            
    except Exception as e:
        logger.error(f"Failed to fetch Build sessions: {e}")
    
    return sessions


async def fetch_ignite_sessions(http_session: aiohttp.ClientSession) -> list[SessionInfo]:
    """Fetch sessions from Microsoft Ignite API."""
    sessions = []
    
    try:
        logger.info("Fetching Ignite sessions...")
        async with http_session.get(API_URLS["ignite"], headers=HTTP_HEADERS) as resp:
            if resp.status != 200:
                logger.warning(f"Ignite API returned status {resp.status}")
                return sessions
            
            data = await resp.json()
            
            for s in data:
                if not s.get('slideDeck'):
                    continue
                    
                code = s.get('sessionCode', '')
                if not code or code in IGNORE_SESSION_CODES:
                    continue
                
                sessions.append(SessionInfo(
                    session_code=code,
                    title=s.get('title', 'Unknown'),
                    event='Ignite',
                    session_id=s.get('sessionId', ''),
                    session_url=f"https://ignite.microsoft.com/en-US/sessions/{s.get('sessionId', '')}",
                    ppt_url=s.get('slideDeck', '')
                ))
            
            logger.info(f"  Found {len(sessions)} Ignite sessions with slides")
            
    except Exception as e:
        logger.error(f"Failed to fetch Ignite sessions: {e}")
    
    return sessions


async def _fetch_paged_items(
    http_session: aiohttp.ClientSession,
    parent_id: str,
    max_pages: int = 50
) -> list[dict]:
    """Fetch all items under a parent asset (paginated)."""
    all_items = []
    
    for page in range(max_pages):
        url = PARTNER_ITEMS_URL.format(page=page, parent_id=parent_id)
        
        try:
            async with http_session.get(url, headers=HTTP_HEADERS) as resp:
                if resp.status != 200:
                    break
                
                data = await resp.json()
                cards = data.get('AssetCards', [])
                
                if not cards:
                    break
                
                all_items.extend(cards)
                
        except Exception as e:
            logger.warning(f"Error fetching page {page} for parent {parent_id}: {e}")
            break
    
    return all_items


async def fetch_partner_sessions(http_session: aiohttp.ClientSession) -> list[SessionInfo]:
    """
    Fetch ALL presentations from Microsoft Partner Marketing Center.
    
    Traverses: Campaigns -> Collections -> Presentations (PPTX files)
    
    Source: https://partner.microsoft.com/en-GB/asset/collection/solution-area-partner-marketing-campaigns-content#/
    """
    sessions = []
    seen_urls = set()  # Deduplicate by URL
    
    logger.info("Fetching Partner Marketing Center presentations...")
    logger.info("  Source: https://partner.microsoft.com/en-GB/asset/collection/solution-area-partner-marketing-campaigns-content#/")
    
    # Step 1: Fetch all campaigns
    campaigns = []
    for page in range(10):
        url = PARTNER_CAMPAIGNS_URL.format(page=page)
        try:
            async with http_session.get(url, headers=HTTP_HEADERS) as resp:
                if resp.status != 200:
                    break
                data = await resp.json()
                cards = data.get('AssetCards', [])
                if not cards:
                    break
                campaigns.extend(cards)
        except Exception as e:
            logger.error(f"Failed to fetch campaigns page {page}: {e}")
            break
    
    logger.info(f"  Found {len(campaigns)} campaigns")
    
    # Step 2: For each campaign, fetch collections
    for campaign in campaigns:
        campaign_id = campaign.get('SourceId')
        campaign_title = campaign.get('Title', 'Unknown')
        
        logger.debug(f"  Processing campaign: {campaign_title}")
        
        collections = await _fetch_paged_items(http_session, campaign_id)
        
        # Step 3: For each collection, fetch presentations
        for collection in collections:
            coll_id = collection.get('SourceId')
            coll_title = collection.get('Title', '')
            coll_type = collection.get('CardType', '')
            
            # If it's a direct PPTX link, add it
            content_link = collection.get('ContentCardLink', '')
            if '.pptx' in content_link.lower():
                if content_link not in seen_urls:
                    seen_urls.add(content_link)
                    sessions.append(_create_partner_session(collection, campaign_title))
                continue
            
            # If it's a collection, fetch its contents
            if 'Collection' in coll_type or coll_type == 'Campaign & Product Guide':
                items = await _fetch_paged_items(http_session, coll_id)
                
                for item in items:
                    item_link = item.get('ContentCardLink', '')
                    if '.pptx' in item_link.lower():
                        if item_link not in seen_urls:
                            seen_urls.add(item_link)
                            sessions.append(_create_partner_session(item, f"{campaign_title} > {coll_title}"))
    
    logger.info(f"  Found {len(sessions)} Partner presentations (PPTX files)")
    return sessions


def _create_partner_session(card: dict, context: str = "") -> SessionInfo:
    """Create a SessionInfo from a Partner Marketing Center card."""
    source_id = card.get('SourceId', '')
    friendly_name = (
        card.get('FriendlyName', '') or 
        card.get('DownloadName', '') or 
        f"partner_{source_id}"
    )
    
    # Generate unique code
    code = friendly_name.replace('-', '_').upper()[:30]
    if not code:
        code = f"PARTNER_{source_id}"
    
    title = card.get('Title', 'Unknown Partner Presentation')
    
    # Note: ContentCardLink requires Partner authentication, so PPTX download won't work
    # We store it for reference but actual downloads need auth
    ppt_url = card.get('ContentCardLink', '')
    
    # Build preview URL
    asset_url = (
        card.get('AssetPreviewUrl', '') or
        f"https://partner.microsoft.com/en-gb/marketing-center/assets/detail/{friendly_name}"
    )
    
    # Extract description for search indexing (since we can't download PPTX)
    description = card.get('ShortDescription', '') or card.get('LongDescription', '') or ''
    
    return SessionInfo(
        session_code=code,
        title=f"{title}" + (f" [{context}]" if context else ""),
        event='Partner',
        session_id=source_id,
        session_url=asset_url,
        ppt_url=ppt_url,
        description=description  # Add description for metadata-only indexing
    )


async def fetch_all_sessions(
    include_build: bool = True,
    include_ignite: bool = True,
    include_partner: bool = True,
    partner_max_age_months: int = 0,  # Not used for Partner anymore
) -> list[SessionInfo]:
    """
    Fetch all sessions from enabled sources.
    
    Args:
        include_build: Include Microsoft Build sessions
        include_ignite: Include Microsoft Ignite sessions
        include_partner: Include Partner Marketing Center presentations
        partner_max_age_months: (deprecated) Not used
    
    Returns:
        Combined list of SessionInfo objects
    """
    sessions = []
    
    timeout = aiohttp.ClientTimeout(total=120)  # Longer timeout for Partner
    connector = aiohttp.TCPConnector(limit=10)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http_session:
        if include_build:
            build_sessions = await fetch_build_sessions(http_session)
            sessions.extend(build_sessions)
        
        if include_ignite:
            ignite_sessions = await fetch_ignite_sessions(http_session)
            sessions.extend(ignite_sessions)
        
        if include_partner:
            partner_sessions = await fetch_partner_sessions(http_session)
            sessions.extend(partner_sessions)
    
    logger.info(f"Total sessions fetched: {len(sessions)}")
    return sessions
