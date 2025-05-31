"""
Schemas for SiteMetadata model validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from cloudstore.schemas.base import BaseSchema, BaseResponseSchema
from cloudstore.database.models import SiteEnum


class SiteMetadataBase(BaseSchema):
    """
    Base schema for SiteMetadata with common fields.
    
    Attributes:
        site: Site enum (EBAY, AMAZON, etc.)
        base_url: Base URL of the site
        search_url_template: URL template for search queries
        last_crawl_time: Time of the last crawl
        crawl_frequency_minutes: Frequency of crawls in minutes
        rate_limit_requests: Number of requests allowed in the rate limit period
        rate_limit_period_seconds: Rate limit period in seconds
        requires_proxy: Whether the site requires a proxy
        requires_login: Whether the site requires login
        login_details: Login credentials and details
        crawl_settings: Additional crawl settings
    """
    site: SiteEnum = Field(..., description="E-commerce site")
    base_url: str = Field(..., description="Base URL of the site")
    search_url_template: Optional[str] = Field(None, description="URL template for search queries")
    last_crawl_time: Optional[datetime] = Field(None, description="Time of the last crawl")
    crawl_frequency_minutes: int = Field(1440, description="Frequency of crawls in minutes", ge=1)
    rate_limit_requests: int = Field(10, description="Number of requests allowed in the rate limit period", ge=1)
    rate_limit_period_seconds: int = Field(60, description="Rate limit period in seconds", ge=1)
    requires_proxy: bool = Field(True, description="Whether the site requires a proxy")
    requires_login: bool = Field(False, description="Whether the site requires login")
    login_details: Optional[Dict[str, Any]] = Field(None, description="Login credentials and details")
    crawl_settings: Optional[Dict[str, Any]] = Field(None, description="Additional crawl settings")


class SiteMetadataCreate(SiteMetadataBase):
    """Schema for creating new site metadata."""
    
    @model_validator(mode='after')
    def validate_site_metadata(self) -> 'SiteMetadataCreate':
        """Validate site metadata."""
        # Add security check for login details
        if self.requires_login and self.login_details is None:
            raise ValueError("Login details must be provided if login is required")
            
        # Sanitize login details to ensure they're properly structured
        if self.login_details:
            required_keys = ["username", "password"]
            for key in required_keys:
                if key not in self.login_details:
                    raise ValueError(f"Login details must contain '{key}'")
                    
        return self


class SiteMetadataUpdate(BaseSchema):
    """
    Schema for updating existing site metadata.
    All fields are optional.
    """
    base_url: Optional[str] = Field(None, description="Base URL of the site")
    search_url_template: Optional[str] = Field(None, description="URL template for search queries")
    last_crawl_time: Optional[datetime] = Field(None, description="Time of the last crawl")
    crawl_frequency_minutes: Optional[int] = Field(None, description="Frequency of crawls in minutes", ge=1)
    rate_limit_requests: Optional[int] = Field(None, description="Number of requests allowed in the rate limit period", ge=1)
    rate_limit_period_seconds: Optional[int] = Field(None, description="Rate limit period in seconds", ge=1)
    requires_proxy: Optional[bool] = Field(None, description="Whether the site requires a proxy")
    requires_login: Optional[bool] = Field(None, description="Whether the site requires login")
    login_details: Optional[Dict[str, Any]] = Field(None, description="Login credentials and details")
    crawl_settings: Optional[Dict[str, Any]] = Field(None, description="Additional crawl settings")


class SiteMetadataResponse(SiteMetadataBase, BaseResponseSchema):
    """Schema for site metadata response including ID and timestamps."""
    
    # Mask sensitive login details in response
    @model_validator(mode='after')
    def mask_sensitive_data(self) -> 'SiteMetadataResponse':
        """Mask sensitive data in response."""
        if self.login_details and 'password' in self.login_details:
            self.login_details['password'] = '********'
        return self
    
    class Config:
        """Configuration for the SiteMetadataResponse schema."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "site": "AMAZON",
                "base_url": "https://www.amazon.com",
                "search_url_template": "https://www.amazon.com/s?k={query}",
                "last_crawl_time": "2025-05-31T00:00:00Z",
                "crawl_frequency_minutes": 1440,
                "rate_limit_requests": 10,
                "rate_limit_period_seconds": 60,
                "requires_proxy": True,
                "requires_login": False,
                "login_details": None,
                "crawl_settings": {
                    "max_pages": 10,
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                "created_at": "2025-05-31T00:00:00Z",
                "updated_at": None
            }
        }

