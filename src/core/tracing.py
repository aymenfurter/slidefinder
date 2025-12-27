"""OpenTelemetry tracing for SlideFinder."""

import logging
import os

logger = logging.getLogger(__name__)
_tracing_initialized = False


def setup_tracing() -> bool:
    global _tracing_initialized
    if _tracing_initialized:
        return True
    
    from src.core import get_settings
    settings = get_settings()
    
    if not settings.tracing_enabled:
        logger.info("🔇 Tracing is \033[91mdisabled\033[0m (set TRACING_ENABLED=true to enable)")
        return False
    
    if not settings.applicationinsights_connection_string:
        logger.info("🔇 No Application Insights connection string configured")
        return False
    
    from azure.core.settings import settings as azure_settings
    azure_settings.tracing_implementation = "opentelemetry"
    os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
    os.environ.setdefault("OTEL_SERVICE_NAME", settings.tracing_service_name)
    
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry import trace as otel_trace
    
    configure_azure_monitor(
        connection_string=settings.applicationinsights_connection_string,
        resource=Resource.create({"service.name": settings.tracing_service_name}),
        enable_live_metrics=True,
    )
    
    tracer_provider = otel_trace.get_tracer_provider()
    if hasattr(tracer_provider, 'add_span_processor'):
        from opentelemetry.sdk.trace import SpanProcessor
        from src.core.debug import increment_trace_count
        
        class CountingProcessor(SpanProcessor):
            def on_start(self, span, parent_context=None): pass
            def on_end(self, span): increment_trace_count()
            def shutdown(self): pass
            def force_flush(self, timeout_millis=30000): return True
        
        tracer_provider.add_span_processor(CountingProcessor())
    
    logger.info("📊 Using \033[96mAzure Application Insights\033[0m for tracing")
    
    try:
        from azure.ai.projects.telemetry import AIProjectsInstrumentor
        AIProjectsInstrumentor().instrument(enable_content_recording=settings.tracing_enable_content_recording)
        logger.info("✅ Foundry SDK tracing instrumented")
    except ImportError:
        pass
    
    _tracing_initialized = True
    logger.info(f"OpenTelemetry tracing enabled for service: {settings.tracing_service_name}")
    return True


def is_tracing_enabled() -> bool:
    return _tracing_initialized
