import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory
BASE_DIR = Path(__file__).parent

class Settings(BaseSettings):
    """Centralized configuration for the application using Pydantic Settings."""
    
    # Application configuration
    APP_PORT: int = 1231
    LOG_LEVEL: str = "INFO"
    
    # Optional path to cloudflared binary
    CLOUDFLARED_PATH: Optional[str] = None

    # Database configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///./tunnels.db"
    
    # API Token Security
    API_TOKEN: str = "your-default-secret-token"

    # Load from .env file in the project root
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars
    )

# Instantiate the global settings object
settings = Settings()

