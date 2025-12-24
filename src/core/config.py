"""
Application settings using Pydantic for validation and type safety.
Security: All sensitive values loaded from environment variables.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration with validation and security best practices."""
    
    # Application
    app_name: str = Field(default="SlideFinder", description="Application name")
    debug: bool = Field(default=False, description="Debug mode flag")
    
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=7004, ge=1, le=65535, description="Server port")
    
    # Paths (relative to workspace root)
    data_dir: Path = Field(default=Path("data"), description="Data directory")
    
    @property
    def index_dir(self) -> Path:
        """Get slide index directory path."""
        return self.data_dir / "slide_index"
    
    @property
    def ppts_dir(self) -> Path:
        """Get PowerPoint files directory path."""
        return self.data_dir / "ppts"
    
    @property
    def thumbnails_dir(self) -> Path:
        """Get thumbnails directory path."""
        return self.data_dir / "thumbnails"
    
    @property
    def compiled_decks_dir(self) -> Path:
        """Get compiled decks directory path."""
        return self.data_dir / "compiled_decks"
    
    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(
        default=None, 
        description="Azure OpenAI API key (sensitive)"
    )
    azure_openai_endpoint: Optional[str] = Field(
        default=None, 
        description="Azure OpenAI endpoint URL"
    )
    azure_openai_deployment: str = Field(
        default="gpt-4o", 
        description="Azure OpenAI deployment name for deck builder agent"
    )
    azure_openai_api_version: str = Field(
        default="2024-10-21", 
        description="Azure OpenAI API version"
    )
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-ada-002",
        description="Azure OpenAI embedding deployment name for vector search"
    )
    azure_openai_nano_deployment: str = Field(
        default="gpt-4.1-nano",
        description="Azure OpenAI nano deployment name for lightweight AI overview generation"
    )
    
    # Azure AI Foundry Configuration
    azure_ai_project_endpoint: Optional[str] = Field(
        default=None,
        description="Azure AI Foundry project endpoint URL"
    )
    azure_ai_foundry_agent_name: str = Field(
        default="SlideAssistantAgent",
        description="Agent name for Slide Assistant in Foundry"
    )
    
    # Azure AI Search Configuration
    azure_search_endpoint: Optional[str] = Field(
        default=None,
        description="Azure AI Search endpoint URL"
    )
    azure_search_api_key: Optional[str] = Field(
        default=None,
        description="Azure AI Search API key (sensitive)"
    )
    azure_search_index_name: str = Field(
        default="slidefinder",
        description="Azure AI Search index name"
    )
    
    # Search Configuration
    search_results_limit: int = Field(
        default=250, 
        ge=1, 
        le=1000, 
        description="Maximum number of slides returned by search API"
    )
    
    # Download Configuration
    pptx_download_timeout: int = Field(
        default=120, 
        ge=10, 
        le=600, 
        description="PPTX download timeout in seconds"
    )
    
    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    
    # Tracing Configuration (Optional - disabled by default)
    tracing_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing for AI services"
    )
    tracing_otlp_endpoint: str = Field(
        default="http://localhost:4318/v1/traces",
        description="OTLP HTTP endpoint for trace export (Foundry SDK)"
    )
    tracing_otlp_grpc_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint for trace export (Agent Framework)"
    )
    tracing_service_name: str = Field(
        default="slidefinder",
        description="Service name for tracing"
    )
    tracing_enable_content_recording: bool = Field(
        default=True,
        description="Enable recording of prompts and completions in traces"
    )
    applicationinsights_connection_string: Optional[str] = Field(
        default=None,
        description="Azure Application Insights connection string for cloud tracing"
    )
    
    @property
    def has_azure_openai(self) -> bool:
        """Check if Azure OpenAI is fully configured."""
        return bool(
            self.azure_openai_api_key 
            and self.azure_openai_endpoint 
            and self.azure_openai_deployment
        )
    
    @property
    def has_foundry_agent(self) -> bool:
        """Check if Azure AI Foundry Agent Service is configured."""
        return bool(self.azure_ai_project_endpoint)
    
    @property
    def llm_provider(self) -> str:
        """Get the active LLM provider name."""
        if self.has_azure_openai:
            return "azure"
        return "none"
    
    @property
    def has_azure_search(self) -> bool:
        """Check if Azure AI Search is fully configured."""
        return bool(
            self.azure_search_endpoint 
            and self.azure_search_api_key 
            and self.azure_search_index_name
        )
    
    @property
    def search_provider(self) -> str:
        """Get the active search provider name."""
        if self.has_azure_search:
            return "azure"
        return "none"
    
    @field_validator("data_dir")
    @classmethod
    def validate_data_dir(cls, v: Path) -> Path:
        """Ensure data directory path is valid."""
        return Path(v)
    
    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for dir_path in [
            self.data_dir,
            self.index_dir,
            self.ppts_dir,
            self.thumbnails_dir,
            self.compiled_decks_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Map environment variable names to field names
        env_prefix = ""
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Using lru_cache ensures settings are loaded once and reused.
    """
    return Settings()
