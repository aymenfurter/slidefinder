"""
OpenTelemetry Tracing Configuration for SlideFinder.

This module provides optional tracing support for:
- Microsoft Foundry Agent Service (azure-ai-projects SDK)

Tracing is disabled by default and can be enabled via environment variables.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_tracing_initialized = False


def setup_tracing() -> bool:
    """
    Set up OpenTelemetry tracing if enabled in configuration.
    
    This function should be called once at application startup.
    It configures tracing for Foundry SDK.
    
    Returns:
        bool: True if tracing was enabled and configured, False otherwise.
    """
    global _tracing_initialized
    
    if _tracing_initialized:
        logger.debug("Tracing already initialized, skipping")
        return True
    
    from src.core import get_settings
    settings = get_settings()
    
    if not settings.tracing_enabled:
        logger.info("🔇 Tracing is \033[91mdisabled\033[0m (set TRACING_ENABLED=true to enable)")
        return False
    
    try:
        _setup_foundry_tracing(settings)
        _tracing_initialized = True
        logger.info(f"OpenTelemetry tracing enabled for service: {settings.tracing_service_name}")
        return True
    except ImportError as e:
        logger.warning(f"Tracing dependencies not installed: {e}")
        logger.warning("Install with: pip install azure-monitor-opentelemetry azure-ai-projects")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return False


def _setup_foundry_tracing(settings) -> None:
    """
    Configure tracing for Microsoft Foundry Agent Service (azure-ai-projects SDK).
    
    Uses Azure Monitor OpenTelemetry for tracing to Application Insights.
    """
    # Enable Azure SDK tracing with OpenTelemetry
    from azure.core.settings import settings as azure_settings
    azure_settings.tracing_implementation = "opentelemetry"
    
    # Enable capturing binary data including images and files
    os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
    
    # Set service name for OpenTelemetry
    os.environ.setdefault("OTEL_SERVICE_NAME", settings.tracing_service_name)
    
    # Use Azure Monitor if Application Insights is configured
    if settings.applicationinsights_connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            from opentelemetry.sdk.resources import Resource
            
            resource = Resource.create({
                "service.name": settings.tracing_service_name
            })
            
            configure_azure_monitor(
                connection_string=settings.applicationinsights_connection_string,
                resource=resource,
                enable_live_metrics=True,
            )
            logger.info("📊 Using \033[96mAzure Application Insights\033[0m for tracing")
            
        except ImportError as e:
            logger.warning(f"azure-monitor-opentelemetry not installed: {e}")
            logger.warning("Install with: pip install azure-monitor-opentelemetry")
            logger.info("🔇 Tracing disabled - no valid exporter available")
            return
    else:
        logger.info("🔇 No Application Insights connection string configured, tracing disabled")
        return
    
    # Instrument azure-ai-projects SDK
    try:
        from azure.ai.projects.telemetry import AIProjectsInstrumentor
        AIProjectsInstrumentor().instrument(
            enable_content_recording=settings.tracing_enable_content_recording
        )
        logger.info("✅ Foundry SDK (azure-ai-projects) tracing instrumented")
    except ImportError:
        logger.debug("azure-ai-projects telemetry not available, skipping Foundry instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument Foundry SDK: {e}")


def is_tracing_enabled() -> bool:
    """Check if tracing is currently enabled."""
    return _tracing_initialized
