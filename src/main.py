"""
SlideFinder - Main Application Entry Point

A search engine for Microsoft Build & Ignite conference slides with 
AI-powered deck building capabilities.
"""
import os
import sys
from pathlib import Path as PathlibPath

def _init_debug_mode():
    """Initialize debug mode before any other modules are loaded."""
    env_file = PathlibPath(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value
    
    debug_env = os.environ.get("DEBUG", "").lower()
    if debug_env in ("true", "1", "yes", "on"):
        os.environ["TRACING_ENABLED"] = "true"
        os.environ["ENABLE_SENSITIVE_DATA"] = "true"
        os.environ["ENABLE_INSTRUMENTATION"] = "true"

_init_debug_mode()

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.core import get_settings, setup_tracing, is_tracing_enabled, init_debug_mode, is_debug_mode, get_debug_status
from src.api.routes import search, slides, deck_builder, slide_assistant

# Initialize the debug mode state (after early env var setup)
init_debug_mode()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Reduce noise from Azure SDK, OpenTelemetry, and agent framework
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.WARNING)
logging.getLogger("opentelemetry.exporter").setLevel(logging.WARNING)
logging.getLogger("opentelemetry.sdk").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("agent_framework").setLevel(logging.WARNING)
logging.getLogger("src.services.deck_builder").setLevel(logging.WARNING)
logging.getLogger("src.services.search").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    settings = get_settings()
    
    # Startup
    logger.info(f"🚀 Starting {settings.app_name}...")
    settings.ensure_directories()
    
    # Log debug mode status
    if is_debug_mode():
        logger.info("🐛 Debug mode is \033[92mACTIVE\033[0m")
    
    # Initialize tracing (if enabled)
    tracing_status = setup_tracing()
    if tracing_status:
        logger.info("📡 OpenTelemetry tracing is active")
    
    # Log configuration
    logger.info(f"🤖 LLM Provider: \033[96m{settings.llm_provider}\033[0m")
    logger.info(f"📁 Data directory: \033[93m{settings.data_dir}\033[0m")
    logger.info(f"📂 Index directory: \033[93m{settings.index_dir}\033[0m")
    tracing_color = "\033[92m" if is_tracing_enabled() else "\033[91m"
    logger.info(f"🔍 Tracing enabled: {tracing_color}{is_tracing_enabled()}\033[0m")
    
    # Initialize search service on startup to validate index
    from src.services.search import get_search_service
    search_service = get_search_service()
    if search_service.index_exists:
        logger.info("✅ Search index loaded successfully")
    else:
        logger.warning("⚠️  Search index not found - search will return empty results")
    
    yield
    
    # Shutdown
    logger.info(f"👋 Shutting down {settings.app_name}...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="Search engine for Microsoft Build & Ignite slides with AI deck builder",
        version="2.0.0",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(search.router, tags=["search"])
    app.include_router(slides.router, tags=["slides"])
    app.include_router(deck_builder.router, tags=["deck-builder"])
    app.include_router(slide_assistant.router, tags=["slide-assistant"])
    
    # Static files - serve from src/web/static
    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Serve thumbnails
    thumbnails_dir = settings.thumbnails_dir
    if thumbnails_dir.exists():
        app.mount("/thumbnails", StaticFiles(directory=thumbnails_dir), name="thumbnails")
    
    # Serve compiled decks
    compiled_dir = settings.data_dir / "compiled_decks"
    if compiled_dir.exists():
        app.mount("/compiled", StaticFiles(directory=compiled_dir), name="compiled")
    
    # Templates
    templates_dir = Path(__file__).parent / "web" / "templates"
    templates = Jinja2Templates(directory=templates_dir)
    
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Serve the main page."""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": settings.app_name,
            }
        )
    
    @app.get("/about", response_class=HTMLResponse)
    async def about(request: Request):
        """Serve the about page for users who want to learn more before agreeing."""
        return templates.TemplateResponse(
            "about.html",
            {
                "request": request,
                "app_name": settings.app_name,
            }
        )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        from src.services.search import get_search_service
        search_service = get_search_service()
        debug_status = get_debug_status()
        
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "llm_provider": settings.llm_provider,
            "index_available": search_service.index_exists,
            "tracing_enabled": is_tracing_enabled(),
            "debug_mode": debug_status["debug_mode"],
            "trace_count": debug_status["trace_count"],
        }
    
    @app.get("/api/config")
    async def get_public_config():
        """Get public configuration."""
        debug_status = get_debug_status()
        return {
            "app_name": settings.app_name,
            "llm_enabled": settings.llm_provider != "none",
            "search_limit": settings.search_results_limit,
            "debug_mode": debug_status["debug_mode"],
            "trace_count": debug_status["trace_count"],
        }
    
    # Only register debug endpoint if debug mode is enabled
    if is_debug_mode():
        @app.get("/api/debug")
        async def get_debug_info():
            """Get debug mode status and trace count."""
            return get_debug_status()
    
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
