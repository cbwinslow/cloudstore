"""
Configuration settings for the CloudStore application.

This module loads settings from environment variables and provides
configuration values for the application.
"""

import os
import secrets
from typing import List, Optional, Dict, Any, Union

from pydantic import (
    PostgresDsn, field_validator, computed_field,
    AnyHttpUrl, HttpUrl, ValidationInfo
)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Environment
    ENV: str = "development"
    DEBUG: bool = True
    
    # Database settings
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    SQL_ECHO: bool = False
    
    # Compute the database URLs
    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @computed_field
    @property
    def ASYNC_SQLALCHEMY_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    API_WORKERS: int = 4
    API_SECRET_KEY: str
    PROJECT_NAME: str = "CloudStore"
    API_V1_STR: str = "/api/v1"
    
    # Security Settings
    SECRET_KEY: str = os.getenv("API_SECRET_KEY", secrets.token_hex(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Custom validators
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Parse the CORS origins from string to list if needed."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Proxy Settings
    PROXY_PROVIDER: str
    PROXY_API_KEY: str
    
    # Scraping Settings
    SCRAPING_CONCURRENT_TASKS: int = 5
    SCRAPING_REQUEST_TIMEOUT: int = 30
    SCRAPING_MAX_RETRIES: int = 3
    SCRAPING_RETRY_DELAY: int = 5
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


# Create instance of settings to be imported by other modules
settings = Settings()

