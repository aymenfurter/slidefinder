"""
SlideFinder - Main Application Entry Point

A search engine for Microsoft Build & Ignite conference slides with 
AI-powered deck building capabilities.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.core import get_settings
from src.api.routes import search, slides, deck_builder, slide_assistant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    settings = get_settings()
    
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    settings.ensure_directories()
    
    # Log configuration
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Index directory: {settings.index_dir}")
    
    # Initialize search service on startup to validate index
    from src.services.search import get_search_service
    search_service = get_search_service()
    if search_service.index_exists:
        logger.info("Search index loaded successfully")
    else:
        logger.warning("Search index not found - search will return empty results")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")


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
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        from src.services.search import get_search_service
        search_service = get_search_service()
        
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "llm_provider": settings.llm_provider,
            "index_available": search_service.index_exists,
        }
    
    @app.get("/api/config")
    async def get_public_config():
        """Get public configuration."""
        return {
            "app_name": settings.app_name,
            "llm_enabled": settings.llm_provider != "none",
            "search_limit": settings.search_results_limit,
        }
    
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
