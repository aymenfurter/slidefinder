#!/usr/bin/env python3
"""
SlideFinder Indexer - Complete Indexing Pipeline

This script orchestrates the complete indexing process for Microsoft Build & Ignite slides:
1. Fetches session data from Microsoft APIs and creates slide_index.jsonl
2. Builds and deploys a thumbnail generation microservice to Azure Container Apps
3. Generates thumbnails at scale using parallel ACA instances
4. Saves all thumbnails locally

The thumbnails are generated remotely - no PPTX files need to be downloaded locally.

Usage:
    python indexer/run_indexer.py                     # Full pipeline
    python indexer/run_indexer.py --index-only        # Only create slide_index.jsonl
    python indexer/run_indexer.py --thumbs-only       # Only generate thumbnails (requires deployed service)
    python indexer/run_indexer.py --deploy-only       # Only deploy the ACA service
    python indexer/run_indexer.py --limit 10          # Limit sessions for testing
    python indexer/run_indexer.py --parallel 2        # Number of parallel requests (default: 2, max: 10)

Requirements:
    - Azure CLI installed and logged in
    - Docker installed (for building container)
    - Azure Container Registry and Container Apps Environment deployed
"""

import argparse
import asyncio
import base64
import gc
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import aiohttp

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings

# --- CONFIGURATION ---

settings = get_settings()

# Use indexer/data to avoid overwriting main data folder
INDEXER_DIR = Path(__file__).parent
DATA_DIR = INDEXER_DIR / "data"
THUMBS_DIR = DATA_DIR / "thumbnails"
SLIDE_INDEX_FILE = DATA_DIR / "slide_index.jsonl"

# API URLs for session data
BUILD_API = "https://eventtools.event.microsoft.com/build2025-prod/fallback/session-all-en-us.json"
IGNITE_API = "https://api-v2.ignite.microsoft.com/api/session/all/en-US"

# Partner Marketing Center API for partner presentations
PARTNER_API_BASE = "https://partner.microsoft.com/api/v2/assetlib2/finder/search2"
PARTNER_GALLERY_ID = "{A7EF63C1-15D2-4FE3-B9E5-971184DF1FFC}"
PARTNER_CONTEXT_ID = "c6e60a35-c418-4586-8cab-3b66b476f643"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SlideFinderBot/1.0)",
    "Accept": "application/json"
}

# Files to ignore (known to cause issues)
IGNORE_FILES = {
    "BRK224", "BRK301", "BRK344"
}

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- DATA MODELS ---

@dataclass
class SlideRecord:
    """Record for a single slide in the index."""
    slide_id: str
    session_code: str
    title: str
    slide_number: int
    content: str
    event: str
    session_url: str
    ppt_url: str


@dataclass
class SessionInfo:
    """Information about a session with slides."""
    session_code: str
    title: str
    event: str
    session_id: str
    session_url: str
    ppt_url: str


# --- AZURE INFRASTRUCTURE ---

class AzureDeployer:
    """Handles Azure Container Apps deployment for the thumbnail service."""
    
    def __init__(self):
        self.resource_group: Optional[str] = None
        self.acr_name: Optional[str] = None
        self.acr_login_server: Optional[str] = None
        self.aca_env_name: Optional[str] = None
        self.service_url: Optional[str] = None
        
    def _run_az_command(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run an Azure CLI command."""
        cmd = ["az"] + args
        logger.debug(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            logger.error(f"Azure CLI error: {result.stderr}")
            raise RuntimeError(f"Azure CLI command failed: {result.stderr}")
        return result
    
    def get_azure_resources(self) -> bool:
        """Discover existing Azure resources from azd environment or Azure CLI."""
        
        # First try azd environment
        try:
            result = subprocess.run(
                ["azd", "env", "get-values"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                # Parse environment values
                env_values = {}
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_values[key] = value.strip('"')
                
                self.acr_login_server = env_values.get('AZURE_CONTAINER_REGISTRY_ENDPOINT')
                self.aca_env_name = env_values.get('AZURE_CONTAINER_APP_ENVIRONMENT_NAME')
                
                if self.acr_login_server:
                    self.acr_name = self.acr_login_server.split('.')[0]
                    
                    # Get resource group from ACR
                    result = self._run_az_command([
                        "acr", "show",
                        "--name", self.acr_name,
                        "--query", "resourceGroup",
                        "-o", "tsv"
                    ], check=False)
                    
                    if result.returncode == 0:
                        self.resource_group = result.stdout.strip()
                
                if self.resource_group and self.acr_login_server and self.aca_env_name:
                    logger.info(f"Azure resources discovered from azd:")
                    logger.info(f"  Resource Group: {self.resource_group}")
                    logger.info(f"  ACR: {self.acr_login_server}")
                    logger.info(f"  ACA Environment: {self.aca_env_name}")
                    return True
        except FileNotFoundError:
            logger.debug("azd not found, trying Azure CLI directly")
        except Exception as e:
            logger.debug(f"azd discovery failed: {e}")
        
        # Fallback: Search for resources using Azure CLI directly
        logger.info("Searching for Azure resources via Azure CLI...")
        
        try:
            # Find slidefinder resource group
            result = self._run_az_command([
                "group", "list",
                "--query", "[?contains(name, 'slidefinder') || contains(name, 'rg-')].name",
                "-o", "tsv"
            ], check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                # Take the first matching resource group
                for rg in result.stdout.strip().split('\n'):
                    rg = rg.strip()
                    if not rg:
                        continue
                    
                    # Check if this RG has an ACR
                    acr_result = self._run_az_command([
                        "acr", "list",
                        "--resource-group", rg,
                        "--query", "[0].loginServer",
                        "-o", "tsv"
                    ], check=False)
                    
                    if acr_result.returncode == 0 and acr_result.stdout.strip():
                        self.resource_group = rg
                        self.acr_login_server = acr_result.stdout.strip()
                        self.acr_name = self.acr_login_server.split('.')[0]
                        
                        # Find Container Apps Environment
                        env_result = self._run_az_command([
                            "containerapp", "env", "list",
                            "--resource-group", rg,
                            "--query", "[0].name",
                            "-o", "tsv"
                        ], check=False)
                        
                        if env_result.returncode == 0 and env_result.stdout.strip():
                            self.aca_env_name = env_result.stdout.strip()
                            break
            
            if self.resource_group and self.acr_login_server and self.aca_env_name:
                logger.info(f"Azure resources discovered via CLI:")
                logger.info(f"  Resource Group: {self.resource_group}")
                logger.info(f"  ACR: {self.acr_login_server}")
                logger.info(f"  ACA Environment: {self.aca_env_name}")
                return True
            else:
                logger.warning("Could not find all required Azure resources")
                return False
                
        except Exception as e:
            logger.error(f"Failed to discover Azure resources: {e}")
            return False
    
    def build_and_push_image(self, service_dir: Path) -> str:
        """Build and push the thumbnail service Docker image to ACR."""
        
        if not self.acr_login_server:
            raise RuntimeError("ACR login server not configured")
        
        image_name = f"{self.acr_login_server}/thumbnail-service"
        image_tag = f"{image_name}:latest"
        
        logger.info(f"Building Docker image: {image_tag}")
        
        # Build image using ACR build (no local Docker required)
        self._run_az_command([
            "acr", "build",
            "--registry", self.acr_name,
            "--image", "thumbnail-service:latest",
            "--file", str(service_dir / "Dockerfile"),
            str(service_dir)
        ])
        
        logger.info(f"Image pushed to ACR: {image_tag}")
        return image_tag
    
    def deploy_thumbnail_service(self, min_replicas: int = 2, max_replicas: int = 10) -> str:
        """Deploy the thumbnail service to Azure Container Apps."""
        
        if not all([self.resource_group, self.acr_login_server, self.aca_env_name]):
            raise RuntimeError("Azure resources not fully configured")
        
        service_name = "thumbnail-service"
        image = f"{self.acr_login_server}/thumbnail-service:latest"
        
        logger.info(f"Deploying {service_name} to Azure Container Apps...")
        logger.info(f"  Min replicas: {min_replicas}, Max replicas: {max_replicas}")
        
        # Check if app exists
        result = self._run_az_command([
            "containerapp", "show",
            "--name", service_name,
            "--resource-group", self.resource_group,
            "--query", "properties.configuration.ingress.fqdn",
            "-o", "tsv"
        ], check=False)
        
        # First, try to create/find a user-assigned managed identity
        identity_name = "thumbnail-service-identity"
        identity_id = None
        
        # Check if identity exists or create it
        identity_result = self._run_az_command([
            "identity", "show",
            "--name", identity_name,
            "--resource-group", self.resource_group,
            "--query", "id",
            "-o", "tsv"
        ], check=False)
        
        if identity_result.returncode == 0 and identity_result.stdout.strip():
            identity_id = identity_result.stdout.strip()
            logger.info(f"Using existing managed identity: {identity_name}")
        else:
            # Create identity
            logger.info(f"Creating managed identity: {identity_name}")
            create_id_result = self._run_az_command([
                "identity", "create",
                "--name", identity_name,
                "--resource-group", self.resource_group,
                "-o", "json"
            ], check=False)
            
            if create_id_result.returncode == 0:
                import json as json_module
                try:
                    id_data = json_module.loads(create_id_result.stdout)
                    identity_id = id_data.get('id')
                    principal_id = id_data.get('principalId')
                    
                    # Grant ACR pull permission
                    logger.info("Granting ACR pull permission to identity...")
                    acr_id_result = self._run_az_command([
                        "acr", "show",
                        "--name", self.acr_name,
                        "--query", "id",
                        "-o", "tsv"
                    ], check=False)
                    
                    if acr_id_result.returncode == 0:
                        acr_id = acr_id_result.stdout.strip()
                        # Wait a moment for the identity to propagate
                        time.sleep(10)
                        self._run_az_command([
                            "role", "assignment", "create",
                            "--assignee", principal_id,
                            "--role", "AcrPull",
                            "--scope", acr_id
                        ], check=False)
                        # Wait for role assignment to propagate
                        time.sleep(15)
                except Exception as e:
                    logger.warning(f"Failed to set up managed identity: {e}")
        
        if result.returncode == 0 and result.stdout.strip():
            # App exists, update it
            logger.info("Updating existing Container App...")
            self._run_az_command([
                "containerapp", "update",
                "--name", service_name,
                "--resource-group", self.resource_group,
                "--image", image,
                "--min-replicas", str(min_replicas),
                "--max-replicas", str(max_replicas),
                "--cpu", "2.0",
                "--memory", "4Gi"
            ])
        else:
            # Create new app with managed identity
            logger.info("Creating new Container App with managed identity...")
            
            if identity_id:
                # Use managed identity for ACR access
                self._run_az_command([
                    "containerapp", "create",
                    "--name", service_name,
                    "--resource-group", self.resource_group,
                    "--environment", self.aca_env_name,
                    "--image", image,
                    "--target-port", "8080",
                    "--ingress", "external",
                    "--min-replicas", str(min_replicas),
                    "--max-replicas", str(max_replicas),
                    "--cpu", "2.0",
                    "--memory", "4Gi",
                    "--scale-rule-name", "http-rule",
                    "--scale-rule-type", "http",
                    "--scale-rule-http-concurrency", "1",
                    "--user-assigned", identity_id,
                    "--registry-server", self.acr_login_server,
                    "--registry-identity", identity_id
                ])
            else:
                # Fallback: enable admin and use password
                logger.info("Falling back to admin credentials...")
                self._run_az_command([
                    "acr", "update",
                    "--name", self.acr_name,
                    "--admin-enabled", "true"
                ], check=False)
                
                creds_result = self._run_az_command([
                    "acr", "credential", "show",
                    "--name", self.acr_name,
                    "-o", "json"
                ], check=False)
                
                acr_username = None
                acr_password = None
                if creds_result.returncode == 0:
                    import json as json_module
                    try:
                        creds = json_module.loads(creds_result.stdout)
                        acr_username = creds.get('username')
                        acr_password = creds.get('passwords', [{}])[0].get('value')
                    except Exception:
                        pass
                
                create_cmd = [
                    "containerapp", "create",
                    "--name", service_name,
                    "--resource-group", self.resource_group,
                    "--environment", self.aca_env_name,
                    "--image", image,
                    "--target-port", "8080",
                    "--ingress", "external",
                    "--min-replicas", str(min_replicas),
                    "--max-replicas", str(max_replicas),
                    "--cpu", "2.0",
                    "--memory", "4Gi",
                    "--scale-rule-name", "http-rule",
                    "--scale-rule-type", "http",
                    "--scale-rule-http-concurrency", "1",
                    "--registry-server", self.acr_login_server
                ]
                
                if acr_username and acr_password:
                    create_cmd.extend([
                        "--registry-username", acr_username,
                        "--registry-password", acr_password
                    ])
                
                self._run_az_command(create_cmd)
        
        # Get the service URL
        result = self._run_az_command([
            "containerapp", "show",
            "--name", service_name,
            "--resource-group", self.resource_group,
            "--query", "properties.configuration.ingress.fqdn",
            "-o", "tsv"
        ])
        
        fqdn = result.stdout.strip()
        self.service_url = f"https://{fqdn}"
        
        logger.info(f"Service deployed: {self.service_url}")
        
        # Wait for service to be ready
        self._wait_for_service_ready()
        
        return self.service_url
    
    def _wait_for_service_ready(self, timeout: int = 120):
        """Wait for the thumbnail service to become healthy."""
        
        if not self.service_url:
            return
        
        logger.info("Waiting for service to become healthy...")
        
        import requests
        
        start_time = time.time()
        health_url = f"{self.service_url}/health"
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    logger.info("Service is healthy!")
                    return
            except Exception:
                pass
            
            time.sleep(5)
        
        logger.warning("Service health check timed out, proceeding anyway...")
    
    def cleanup_service(self):
        """Delete the thumbnail service (optional cleanup after indexing)."""
        
        if not self.resource_group:
            return
        
        logger.info("Cleaning up thumbnail service...")
        
        self._run_az_command([
            "containerapp", "delete",
            "--name", "thumbnail-service",
            "--resource-group", self.resource_group,
            "--yes"
        ], check=False)


# --- SESSION FETCHING ---

async def fetch_partner_presentations(http_session: aiohttp.ClientSession, max_age_months: int = 12) -> list[SessionInfo]:
    """
    Fetch presentations from Microsoft Partner Marketing Center API.
    
    Only returns presentations released within the last max_age_months.
    """
    from datetime import datetime, timedelta
    
    sessions = []
    cutoff_date = datetime.now() - timedelta(days=max_age_months * 30)
    
    logger.info(f"Fetching Partner Marketing Center presentations (last {max_age_months} months)...")
    
    page = 0
    total_found = 0
    
    while True:
        try:
            url = (
                f"{PARTNER_API_BASE}?"
                f"galleryId={PARTNER_GALLERY_ID}&"
                f"locale=en-us&"
                f"page={page}&"
                f"contextItemId={PARTNER_CONTEXT_ID}&"
                f"isPreview=false&"
                f"search=.pptx&"
                f"sort=date&"
                f"facets=false"
            )
            
            async with http_session.get(url, headers=HEADERS) as resp:
                if resp.status != 200:
                    logger.warning(f"Partner API returned status {resp.status}")
                    break
                
                data = await resp.json()
                cards = data.get('AssetCards', [])
                
                if not cards:
                    break
                
                for card in cards:
                    # Only process Presentation type with .pptx files
                    if card.get('CardType') != 'Presentation':
                        continue
                    
                    ppt_url = card.get('ContentCardLink', '')
                    if not ppt_url or '.pptx' not in ppt_url.lower():
                        continue
                    
                    # Check date filter
                    priority_date_str = card.get('PriorityDate', '')
                    if priority_date_str:
                        try:
                            # Parse ISO date format: 2025-10-28T07:00:58Z
                            priority_date = datetime.fromisoformat(priority_date_str.replace('Z', '+00:00'))
                            if priority_date.replace(tzinfo=None) < cutoff_date:
                                continue
                        except ValueError:
                            pass  # Include if we can't parse the date
                    
                    # Generate a unique session code from the friendly name or source ID
                    source_id = card.get('SourceId', '')
                    friendly_name = card.get('FriendlyName', '') or card.get('DownloadName', '') or f"partner_{source_id}"
                    
                    # Create a short code from the friendly name
                    code = friendly_name.replace('-', '_').upper()[:30]
                    if not code:
                        code = f"PARTNER_{source_id}"
                    
                    title = card.get('Title', 'Unknown Partner Presentation')
                    
                    # Build asset URL for session link
                    asset_preview_url = card.get('AssetPreviewUrl', '') or \
                                       f"https://partner.microsoft.com/en-us/marketing-center/assets/detail/{friendly_name}"
                    
                    sessions.append(SessionInfo(
                        session_code=code,
                        title=title,
                        event='Partner',
                        session_id=source_id,
                        session_url=asset_preview_url,
                        ppt_url=ppt_url
                    ))
                    total_found += 1
                
                page += 1
                
                # Safety limit - max 20 pages (240 assets)
                if page >= 20:
                    break
                    
        except Exception as e:
            logger.error(f"Failed to fetch Partner page {page}: {e}")
            break
    
    logger.info(f"  Found {total_found} Partner presentations (< {max_age_months} months old)")
    return sessions


async def fetch_sessions(include_partner: bool = True, partner_max_age_months: int = 12) -> list[SessionInfo]:
    """Fetch all sessions with slide decks from Microsoft APIs."""
    
    sessions = []
    
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=10)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http_session:
        # Fetch Build sessions
        try:
            logger.info("Fetching Build sessions...")
            async with http_session.get(BUILD_API, headers=HEADERS) as resp:
                if resp.status == 200:
                    build_data = await resp.json()
                    for s in build_data:
                        if s.get('slideDeck'):
                            code = s.get('sessionCode', '')
                            if code and code not in IGNORE_FILES:
                                sessions.append(SessionInfo(
                                    session_code=code,
                                    title=s.get('title', 'Unknown'),
                                    event='Build',
                                    session_id=s.get('sessionId', ''),
                                    session_url=f"https://build.microsoft.com/en-US/sessions/{s.get('sessionId', '')}",
                                    ppt_url=s.get('slideDeck', '')
                                ))
                    logger.info(f"  Found {len([s for s in sessions if s.event == 'Build'])} Build sessions with slides")
        except Exception as e:
            logger.error(f"Failed to fetch Build sessions: {e}")
        
        # Fetch Ignite sessions
        try:
            logger.info("Fetching Ignite sessions...")
            async with http_session.get(IGNITE_API, headers=HEADERS) as resp:
                if resp.status == 200:
                    ignite_data = await resp.json()
                    for s in ignite_data:
                        if s.get('slideDeck'):
                            code = s.get('sessionCode', '')
                            if code and code not in IGNORE_FILES:
                                sessions.append(SessionInfo(
                                    session_code=code,
                                    title=s.get('title', 'Unknown'),
                                    event='Ignite',
                                    session_id=s.get('sessionId', ''),
                                    session_url=f"https://ignite.microsoft.com/en-US/sessions/{s.get('sessionId', '')}",
                                    ppt_url=s.get('slideDeck', '')
                                ))
                    logger.info(f"  Found {len([s for s in sessions if s.event == 'Ignite'])} Ignite sessions with slides")
        except Exception as e:
            logger.error(f"Failed to fetch Ignite sessions: {e}")
        
        # Fetch Partner Marketing Center presentations
        if include_partner:
            try:
                partner_sessions = await fetch_partner_presentations(http_session, partner_max_age_months)
                sessions.extend(partner_sessions)
            except Exception as e:
                logger.error(f"Failed to fetch Partner presentations: {e}")
    
    logger.info(f"Total sessions with slides: {len(sessions)}")
    return sessions


# --- SLIDE INDEX CREATION ---

def create_slide_index_jsonl(sessions: list[SessionInfo], output_file: Path) -> int:
    """
    Create slide_index.jsonl file for Azure AI Search ingestion.
    
    Note: This creates placeholder records. Content extraction would require
    downloading and parsing the PPTX files, which we skip for now since
    the focus is on thumbnail generation.
    """
    
    logger.info(f"Creating slide index at {output_file}...")
    
    records_written = 0
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for session in sessions:
            # Create a single record per session (as a placeholder)
            # In production, you'd parse the PPTX and create per-slide records
            record = SlideRecord(
                slide_id=f"{session.session_code}_1",
                session_code=session.session_code,
                title=session.title,
                slide_number=1,
                content=session.title,  # Placeholder
                event=session.event,
                session_url=session.session_url,
                ppt_url=session.ppt_url
            )
            
            f.write(json.dumps(asdict(record), ensure_ascii=False) + '\n')
            records_written += 1
    
    logger.info(f"Written {records_written} records to {output_file}")
    return records_written


# --- THUMBNAIL GENERATION ---

class ThumbnailGenerator:
    """Generates thumbnails at scale using the remote ACA service."""
    
    def __init__(self, service_url: str, max_parallel: int = 2):
        self.service_url = service_url
        self.max_parallel = max_parallel
        self.generated = 0
        self.failed = 0
        self.skipped = 0
    
    async def generate_thumbnails_for_session(
        self,
        http_session: aiohttp.ClientSession,
        session: SessionInfo,
        semaphore: asyncio.Semaphore
    ) -> bool:
        """Generate thumbnails for a single session."""
        
        async with semaphore:
            # Check if thumbnails already exist
            existing = list(THUMBS_DIR.glob(f"{session.session_code}_*.png"))
            if existing:
                logger.debug(f"Skipping {session.session_code} - {len(existing)} thumbnails exist")
                self.skipped += 1
                return True
            
            try:
                logger.info(f"Generating thumbnails for {session.session_code}...")
                
                # Call the thumbnail service
                payload = {
                    "url": session.ppt_url,
                    "session_code": session.session_code,
                    "format": "json"
                }
                
                async with http_session.post(
                    f"{self.service_url}/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    if resp.status == 503:
                        # Service busy, retry after delay
                        await asyncio.sleep(5)
                        return await self.generate_thumbnails_for_session(
                            http_session, session, semaphore
                        )
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Failed {session.session_code}: {resp.status} - {error_text[:200]}")
                        self.failed += 1
                        return False
                    
                    result = await resp.json()
                    
                    if not result.get('success'):
                        logger.error(f"Failed {session.session_code}: {result.get('error')}")
                        self.failed += 1
                        return False
                    
                    # Save thumbnails
                    thumbnails = result.get('thumbnails', [])
                    for thumb in thumbnails:
                        slide_num = thumb['slide_number']
                        img_data = base64.b64decode(thumb['image_base64'])
                        
                        output_path = THUMBS_DIR / f"{session.session_code}_{slide_num}.png"
                        output_path.write_bytes(img_data)
                    
                    logger.info(f"✓ {session.session_code}: {len(thumbnails)} thumbnails")
                    self.generated += 1
                    return True
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout generating thumbnails for {session.session_code}")
                self.failed += 1
                return False
            except Exception as e:
                logger.error(f"Error generating thumbnails for {session.session_code}: {e}")
                self.failed += 1
                return False
    
    async def generate_all(self, sessions: list[SessionInfo]) -> tuple[int, int, int]:
        """Generate thumbnails for all sessions."""
        
        THUMBS_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Generating thumbnails for {len(sessions)} sessions")
        logger.info(f"Using {self.max_parallel} parallel requests to match ACA instances")
        
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        connector = aiohttp.TCPConnector(limit=self.max_parallel + 2)
        timeout = aiohttp.ClientTimeout(total=600)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as http_session:
            tasks = [
                self.generate_thumbnails_for_session(http_session, session, semaphore)
                for session in sessions
            ]
            
            # Process in batches to show progress
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
                
                total = self.generated + self.failed + self.skipped
                pct = (total / len(sessions) * 100) if sessions else 0
                logger.info(f"Progress: {total}/{len(sessions)} ({pct:.1f}%) - "
                           f"Generated: {self.generated}, Failed: {self.failed}, Skipped: {self.skipped}")
        
        return self.generated, self.failed, self.skipped


# --- MAIN PIPELINE ---

async def run_full_pipeline(
    limit: Optional[int] = None,
    parallel: int = 2,
    index_only: bool = False,
    thumbs_only: bool = False,
    deploy_only: bool = False,
    service_url: Optional[str] = None,
    skip_cleanup: bool = True,
    include_partner: bool = True,
    partner_only: bool = False,
    partner_max_age_months: int = 12
):
    """Run the full indexing pipeline."""
    
    print("\n" + "=" * 70)
    print("SlideFinder Indexer - Full Pipeline")
    print("=" * 70)
    
    # Ensure indexer data directories exist (separate from main data folder)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize Azure deployer
    deployer = AzureDeployer()
    
    try:
        # Step 1: Fetch sessions
        if not thumbs_only:
            print("\n📡 Step 1: Fetching session data...")
            
            if partner_only:
                # Only fetch Partner presentations
                print("   (Partner presentations only)")
                timeout = aiohttp.ClientTimeout(total=60)
                connector = aiohttp.TCPConnector(limit=10)
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http_session:
                    sessions = await fetch_partner_presentations(http_session, partner_max_age_months)
            else:
                sessions = await fetch_sessions(
                    include_partner=include_partner,
                    partner_max_age_months=partner_max_age_months
                )
            
            if limit:
                sessions = sessions[:limit]
                print(f"   (Limited to {limit} sessions for testing)")
            
            if not sessions:
                print("⚠️  No sessions found. Exiting.")
                return
        else:
            # For thumbs-only, we need to read existing sessions from slide_index.jsonl
            print("\n📄 Reading existing slide index...")
            sessions = []
            if SLIDE_INDEX_FILE.exists():
                with open(SLIDE_INDEX_FILE, 'r', encoding='utf-8') as f:
                    seen_codes = set()
                    for line in f:
                        data = json.loads(line)
                        code = data.get('session_code')
                        if code and code not in seen_codes:
                            seen_codes.add(code)
                            sessions.append(SessionInfo(
                                session_code=code,
                                title=data.get('title', ''),
                                event=data.get('event', ''),
                                session_id='',
                                session_url=data.get('session_url', ''),
                                ppt_url=data.get('ppt_url', '')
                            ))
                
                if limit:
                    sessions = sessions[:limit]
            
            print(f"   Found {len(sessions)} sessions in index")
        
        # Step 2: Create slide index
        if not thumbs_only and not deploy_only:
            print("\n📝 Step 2: Creating slide_index.jsonl...")
            record_count = create_slide_index_jsonl(sessions, SLIDE_INDEX_FILE)
            print(f"   ✓ Written {record_count} records")
        
        if index_only:
            print("\n✅ Index creation complete!")
            return
        
        # Step 3: Deploy thumbnail service
        if not thumbs_only or not service_url:
            print("\n🚀 Step 3: Deploying thumbnail service to Azure Container Apps...")
            
            if not deployer.get_azure_resources():
                print("   ⚠️  Could not discover Azure resources.")
                print("   Run 'azd up' first to deploy the infrastructure.")
                return
            
            # Build and push the container image
            service_dir = Path(__file__).parent / "thumbnail_service"
            deployer.build_and_push_image(service_dir)
            
            # Deploy to ACA
            service_url = deployer.deploy_thumbnail_service(
                min_replicas=parallel,
                max_replicas=parallel  # Fixed replicas for predictable parallelism
            )
            
            print(f"   ✓ Service URL: {service_url}")
        
        if deploy_only:
            print("\n✅ Deployment complete!")
            print(f"   Service URL: {service_url}")
            return
        
        # Step 4: Generate thumbnails
        print(f"\n🖼️  Step 4: Generating thumbnails ({parallel} parallel)...")
        
        generator = ThumbnailGenerator(service_url, max_parallel=parallel)
        generated, failed, skipped = await generator.generate_all(sessions)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ Indexing Complete!")
        print("=" * 70)
        print(f"   Sessions processed: {len(sessions)}")
        print(f"   Thumbnails generated: {generated}")
        print(f"   Thumbnails skipped (existing): {skipped}")
        print(f"   Failed: {failed}")
        print(f"\n   Output files:")
        print(f"     - {SLIDE_INDEX_FILE}")
        print(f"     - {THUMBS_DIR}/ ({len(list(THUMBS_DIR.glob('*.png')))} PNG files)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.exception("Pipeline error")
        print(f"\n❌ Error: {e}")
    finally:
        # Optional cleanup
        if not skip_cleanup and deployer.service_url:
            print("\n🧹 Cleaning up...")
            deployer.cleanup_service()
        
        gc.collect()


def main():
    """CLI entry point."""
    
    parser = argparse.ArgumentParser(
        description="SlideFinder Indexer - Complete Indexing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python indexer/run_indexer.py                     # Full pipeline
  python indexer/run_indexer.py --limit 5           # Test with 5 sessions
  python indexer/run_indexer.py --parallel 10       # Use 10 ACA instances
  python indexer/run_indexer.py --index-only        # Only create slide_index.jsonl
  python indexer/run_indexer.py --deploy-only       # Only deploy ACA service
  python indexer/run_indexer.py --thumbs-only       # Only generate thumbnails
  python indexer/run_indexer.py --service-url URL   # Use existing service
  python indexer/run_indexer.py --no-partner        # Exclude Partner presentations
  python indexer/run_indexer.py --partner-only      # Only Partner presentations
        """
    )
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of sessions to process (for testing)"
    )
    parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=2,
        choices=range(1, 11),
        metavar="N",
        help="Number of parallel ACA instances (1-10, default: 2)"
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Only create slide_index.jsonl (no thumbnails)"
    )
    parser.add_argument(
        "--thumbs-only",
        action="store_true",
        help="Only generate thumbnails (use existing service)"
    )
    parser.add_argument(
        "--deploy-only",
        action="store_true",
        help="Only deploy the thumbnail service"
    )
    parser.add_argument(
        "--service-url",
        type=str,
        default=None,
        help="Use existing thumbnail service URL"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete thumbnail service after completion"
    )
    parser.add_argument(
        "--no-partner",
        action="store_true",
        help="Exclude Partner Marketing Center presentations"
    )
    parser.add_argument(
        "--partner-only",
        action="store_true",
        help="Only fetch Partner Marketing Center presentations (not Build/Ignite)"
    )
    parser.add_argument(
        "--partner-max-age",
        type=int,
        default=12,
        metavar="MONTHS",
        help="Max age in months for Partner presentations (default: 12)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    asyncio.run(run_full_pipeline(
        limit=args.limit,
        parallel=args.parallel,
        index_only=args.index_only,
        thumbs_only=args.thumbs_only,
        deploy_only=args.deploy_only,
        service_url=args.service_url,
        skip_cleanup=not args.cleanup,
        include_partner=not args.no_partner,
        partner_only=args.partner_only,
        partner_max_age_months=args.partner_max_age
    ))


if __name__ == "__main__":
    main()
