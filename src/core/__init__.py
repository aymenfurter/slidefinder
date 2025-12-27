"""Core configuration module for SlideFinder."""

from .debug import init_debug_mode, is_debug_mode, get_debug_status, increment_trace_count, get_trace_count
from .config import Settings, get_settings
from .tracing import setup_tracing, is_tracing_enabled
from .maf_wrapper import with_maf_telemetry

__all__ = [
    "Settings", 
    "get_settings", 
    "setup_tracing", 
    "is_tracing_enabled",
    "init_debug_mode",
    "is_debug_mode",
    "get_debug_status",
    "increment_trace_count",
    "get_trace_count",
    "with_maf_telemetry",
]
