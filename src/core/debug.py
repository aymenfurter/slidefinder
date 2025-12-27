"""Debug mode configuration."""

import os
import logging

logger = logging.getLogger(__name__)
_trace_count = 0
_debug_mode_enabled = False


def init_debug_mode() -> bool:
    global _debug_mode_enabled
    _debug_mode_enabled = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes", "on")
    
    if _debug_mode_enabled:
        os.environ["TRACING_ENABLED"] = "true"
        os.environ["ENABLE_SENSITIVE_DATA"] = "true"
        os.environ["ENABLE_INSTRUMENTATION"] = "true"
        logger.info("🐛 Debug mode \033[92mENABLED\033[0m")
    else:
        os.environ.setdefault("TRACING_ENABLED", "false")
        os.environ.setdefault("ENABLE_SENSITIVE_DATA", "false")
        os.environ.setdefault("ENABLE_INSTRUMENTATION", "false")
    
    return _debug_mode_enabled


def is_debug_mode() -> bool:
    return _debug_mode_enabled


def increment_trace_count(count: int = 1) -> int:
    global _trace_count
    _trace_count += count
    return _trace_count


def get_trace_count() -> int:
    return _trace_count


def reset_trace_count() -> None:
    global _trace_count
    _trace_count = 0


def get_debug_status() -> dict:
    return {
        "debug_mode": _debug_mode_enabled,
        "trace_count": _trace_count,
        "tracing_enabled": os.environ.get("TRACING_ENABLED", "false").lower() == "true",
        "sensitive_data_enabled": os.environ.get("ENABLE_SENSITIVE_DATA", "false").lower() == "true",
        "instrumentation_enabled": os.environ.get("ENABLE_INSTRUMENTATION", "false").lower() == "true",
    }
