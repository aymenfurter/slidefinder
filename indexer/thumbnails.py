"""
Thumbnail generator - Generates slide thumbnails using Azure Container Apps.

This module handles:
- Azure infrastructure discovery
- Container image building and deployment
- Remote thumbnail generation at scale
"""

import asyncio
import base64
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import aiohttp

from .models import SessionInfo

logger = logging.getLogger(__name__)


class AzureDeployer:
    """Handles Azure Container Apps deployment for the thumbnail service."""
    
    def __init__(self):
        self.resource_group: Optional[str] = None
        self.acr_name: Optional[str] = None
        self.acr_login_server: Optional[str] = None
        self.aca_env_name: Optional[str] = None
        self.service_url: Optional[str] = None
    
    def _run_az(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run an Azure CLI command."""
        cmd = ["az"] + args
        logger.debug(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            logger.error(f"Azure CLI error: {result.stderr}")
            raise RuntimeError(f"Azure CLI failed: {result.stderr}")
        return result
    
    def discover_resources(self) -> bool:
        """Discover Azure resources from azd environment or CLI."""
        
        # Try azd first
        try:
            result = subprocess.run(
                ["azd", "env", "get-values"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                env = {}
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        k, v = line.split('=', 1)
                        env[k] = v.strip('"')
                
                self.acr_login_server = env.get('AZURE_CONTAINER_REGISTRY_ENDPOINT')
                self.aca_env_name = env.get('AZURE_CONTAINER_APP_ENVIRONMENT_NAME')
                
                if self.acr_login_server:
                    self.acr_name = self.acr_login_server.split('.')[0]
                    
                    # Get resource group from ACR
                    rg_result = self._run_az([
                        "acr", "show", "--name", self.acr_name,
                        "--query", "resourceGroup", "-o", "tsv"
                    ], check=False)
                    
                    if rg_result.returncode == 0:
                        self.resource_group = rg_result.stdout.strip()
                
                if all([self.resource_group, self.acr_login_server, self.aca_env_name]):
                    logger.info(f"Found Azure resources via azd:")
                    logger.info(f"  RG: {self.resource_group}")
                    logger.info(f"  ACR: {self.acr_login_server}")
                    logger.info(f"  ACA Env: {self.aca_env_name}")
                    return True
                    
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"azd discovery failed: {e}")
        
        # Fallback: search via Azure CLI
        logger.info("Searching for Azure resources via CLI...")
        
        try:
            # Find resource groups
            result = self._run_az([
                "group", "list",
                "--query", "[?contains(name, 'slidefinder') || contains(name, 'rg-')].name",
                "-o", "tsv"
            ], check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                for rg in result.stdout.strip().split('\n'):
                    rg = rg.strip()
                    if not rg:
                        continue
                    
                    # Check for ACR
                    acr_result = self._run_az([
                        "acr", "list", "--resource-group", rg,
                        "--query", "[0].loginServer", "-o", "tsv"
                    ], check=False)
                    
                    if acr_result.returncode == 0 and acr_result.stdout.strip():
                        self.resource_group = rg
                        self.acr_login_server = acr_result.stdout.strip()
                        self.acr_name = self.acr_login_server.split('.')[0]
                        
                        # Find ACA environment
                        env_result = self._run_az([
                            "containerapp", "env", "list", "--resource-group", rg,
                            "--query", "[0].name", "-o", "tsv"
                        ], check=False)
                        
                        if env_result.returncode == 0 and env_result.stdout.strip():
                            self.aca_env_name = env_result.stdout.strip()
                            break
            
            if all([self.resource_group, self.acr_login_server, self.aca_env_name]):
                logger.info(f"Found Azure resources via CLI:")
                logger.info(f"  RG: {self.resource_group}")
                logger.info(f"  ACR: {self.acr_login_server}")
                logger.info(f"  ACA Env: {self.aca_env_name}")
                return True
            
        except Exception as e:
            logger.error(f"Resource discovery failed: {e}")
        
        logger.warning("Could not find all required Azure resources")
        return False
    
    def build_and_push(self, service_dir: Path) -> str:
        """Build and push the thumbnail service image to ACR."""
        if not self.acr_login_server:
            raise RuntimeError("ACR not configured")
        
        image_tag = f"{self.acr_login_server}/thumbnail-service:latest"
        
        logger.info(f"Building image: {image_tag}")
        
        self._run_az([
            "acr", "build",
            "--registry", self.acr_name,
            "--image", "thumbnail-service:latest",
            "--file", str(service_dir / "Dockerfile"),
            str(service_dir)
        ])
        
        logger.info("Image pushed to ACR")
        return image_tag
    
    def deploy_service(self, replicas: int = 2) -> str:
        """Deploy the thumbnail service to Azure Container Apps."""
        if not all([self.resource_group, self.acr_login_server, self.aca_env_name]):
            raise RuntimeError("Azure resources not configured")
        
        service_name = "thumbnail-service"
        image = f"{self.acr_login_server}/thumbnail-service:latest"
        
        logger.info(f"Deploying {service_name} with {replicas} replicas...")
        
        # Check if app exists
        result = self._run_az([
            "containerapp", "show", "--name", service_name,
            "--resource-group", self.resource_group,
            "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"
        ], check=False)
        
        if result.returncode == 0 and result.stdout.strip():
            # Update existing app
            self._run_az([
                "containerapp", "update",
                "--name", service_name,
                "--resource-group", self.resource_group,
                "--image", image,
                "--min-replicas", str(replicas),
                "--max-replicas", str(replicas),
                "--cpu", "2.0", "--memory", "4Gi"
            ])
        else:
            # Create new app
            self._run_az([
                "containerapp", "create",
                "--name", service_name,
                "--resource-group", self.resource_group,
                "--environment", self.aca_env_name,
                "--image", image,
                "--target-port", "8080",
                "--ingress", "external",
                "--min-replicas", str(replicas),
                "--max-replicas", str(replicas),
                "--cpu", "2.0", "--memory", "4Gi"
            ])
        
        # Get URL
        result = self._run_az([
            "containerapp", "show", "--name", service_name,
            "--resource-group", self.resource_group,
            "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"
        ])
        
        fqdn = result.stdout.strip()
        self.service_url = f"https://{fqdn}"
        
        logger.info(f"Service URL: {self.service_url}")
        self._wait_for_health()
        
        return self.service_url
    
    def _wait_for_health(self, timeout: int = 120):
        """Wait for service to become healthy."""
        if not self.service_url:
            return
        
        import requests
        
        logger.info("Waiting for service health...")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                resp = requests.get(f"{self.service_url}/health", timeout=10)
                if resp.status_code == 200:
                    logger.info("Service is healthy")
                    return
            except Exception:
                pass
            time.sleep(5)
        
        logger.warning("Health check timed out")
    
    def cleanup(self):
        """Delete the thumbnail service."""
        if self.resource_group:
            self._run_az([
                "containerapp", "delete",
                "--name", "thumbnail-service",
                "--resource-group", self.resource_group,
                "--yes"
            ], check=False)


class ThumbnailGenerator:
    """Generates thumbnails at scale using a remote ACA service."""
    
    def __init__(self, service_url: str, output_dir: Path, max_parallel: int = 2):
        self.service_url = service_url
        self.output_dir = output_dir
        self.max_parallel = max_parallel
        self.generated = 0
        self.failed = 0
        self.skipped = 0
    
    async def generate_for_session(
        self,
        http_session: aiohttp.ClientSession,
        session: SessionInfo,
        semaphore: asyncio.Semaphore
    ) -> bool:
        """Generate thumbnails for a single session."""
        async with semaphore:
            # Check if thumbnails exist
            existing = list(self.output_dir.glob(f"{session.session_code}_*.png"))
            if existing:
                logger.debug(f"Skipping {session.session_code} - {len(existing)} exist")
                self.skipped += 1
                return True
            
            try:
                logger.info(f"Generating: {session.session_code}")
                
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
                        await asyncio.sleep(5)
                        return await self.generate_for_session(http_session, session, semaphore)
                    
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"Failed {session.session_code}: {resp.status} - {error[:200]}")
                        self.failed += 1
                        return False
                    
                    result = await resp.json()
                    
                    if not result.get('success'):
                        logger.error(f"Failed {session.session_code}: {result.get('error')}")
                        self.failed += 1
                        return False
                    
                    # Save thumbnails
                    for thumb in result.get('thumbnails', []):
                        slide_num = thumb['slide_number']
                        img_data = base64.b64decode(thumb['image_base64'])
                        output_path = self.output_dir / f"{session.session_code}_{slide_num}.png"
                        output_path.write_bytes(img_data)
                    
                    logger.info(f"✓ {session.session_code}: {len(result.get('thumbnails', []))} thumbnails")
                    self.generated += 1
                    return True
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout: {session.session_code}")
                self.failed += 1
                return False
            except Exception as e:
                logger.error(f"Error {session.session_code}: {e}")
                self.failed += 1
                return False
    
    async def generate_all(self, sessions: list[SessionInfo]) -> tuple[int, int, int]:
        """Generate thumbnails for all sessions."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Generating thumbnails for {len(sessions)} sessions")
        logger.info(f"Parallel requests: {self.max_parallel}")
        
        semaphore = asyncio.Semaphore(self.max_parallel)
        connector = aiohttp.TCPConnector(limit=self.max_parallel + 2)
        timeout = aiohttp.ClientTimeout(total=600)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as http_session:
            tasks = [
                self.generate_for_session(http_session, session, semaphore)
                for session in sessions
            ]
            
            # Process in batches
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
                
                total = self.generated + self.failed + self.skipped
                pct = (total / len(sessions) * 100) if sessions else 0
                logger.info(
                    f"Progress: {total}/{len(sessions)} ({pct:.1f}%) - "
                    f"Gen: {self.generated}, Failed: {self.failed}, Skip: {self.skipped}"
                )
        
        return self.generated, self.failed, self.skipped
