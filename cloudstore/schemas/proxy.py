"""
Schemas for ProxyConfig model validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator, model_validator

from cloudstore.schemas.base import BaseSchema, BaseResponseSchema


class ProxyConfigBase(BaseSchema):
    """
    Base schema for ProxyConfig with common fields.
    
    Attributes:
        ip_address: IP address of the proxy
        port: Port number
        protocol: Protocol (http, https, socks5)
        username: Username for authentication
        password: Password for authentication
        country: ISO country code
        provider: Proxy provider
        is_active: Whether the proxy is active
        banned_sites: List of sites where this proxy is banned
        expires_at: Expiration time
    """
    ip_address: str = Field(..., description="IP address of the proxy")
    port: int = Field(..., description="Port number", ge=1, le=65535)
    protocol: str = Field("http", description="Protocol (http, https, socks5)")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    country: Optional[str] = Field(None, description="ISO country code", min_length=2, max_length=2)
    provider: Optional[str] = Field("ipburger", description="Proxy provider")
    is_active: bool = Field(True, description="Whether the proxy is active")
    banned_sites: Optional[List[str]] = Field(None, description="List of sites where this proxy is banned")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    
    @field_validator('protocol')
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        """Validate proxy protocol."""
        allowed_protocols = ["http", "https", "socks5"]
        if v.lower() not in allowed_protocols:
            raise ValueError(f"Protocol must be one of {allowed_protocols}")
        return v.lower()


class ProxyConfigCreate(ProxyConfigBase):
    """Schema for creating a new proxy configuration."""
    
    @model_validator(mode='after')
    def validate_proxy_config(self) -> 'ProxyConfigCreate':
        """Validate proxy configuration."""
        # Validate that username and password are either both present or both absent
        if (self.username is None) != (self.password is None):
            raise ValueError("Username and password must be either both provided or both omitted")
            
        return self


class ProxyConfigUpdate(BaseSchema):
    """
    Schema for updating an existing proxy configuration.
    All fields are optional.
    """
    ip_address: Optional[str] = Field(None, description="IP address of the proxy")
    port: Optional[int] = Field(None, description="Port number", ge=1, le=65535)
    protocol: Optional[str] = Field(None, description="Protocol (http, https, socks5)")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    country: Optional[str] = Field(None, description="ISO country code", min_length=2, max_length=2)
    provider: Optional[str] = Field(None, description="Proxy provider")
    is_active: Optional[bool] = Field(None, description="Whether the proxy is active")
    banned_sites: Optional[List[str]] = Field(None, description="List of sites where this proxy is banned")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    
    @field_validator('protocol')
    @classmethod
    def validate_protocol(cls, v: Optional[str]) -> Optional[str]:
        """Validate proxy protocol."""
        if v is None:
            return v
            
        allowed_protocols = ["http", "https", "socks5"]
        if v.lower() not in allowed_protocols:
            raise ValueError(f"Protocol must be one of {allowed_protocols}")
        return v.lower()


class ProxyConfigResponse(ProxyConfigBase, BaseResponseSchema):
    """
    Schema for proxy configuration response including ID and timestamps.
    
    Additional attributes:
        last_used: Last time the proxy was used
        success_count: Number of successful uses
        failure_count: Number of failed uses
        last_failure: Last time the proxy failed
        failure_reason: Reason for the last failure
    """
    last_used: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    failure_reason: Optional[str] = None
    
    # Mask sensitive information in response
    @model_validator(mode='after')
    def mask_sensitive_data(self) -> 'ProxyConfigResponse':
        """Mask sensitive data in response."""
        if self.password:
            self.password = '********'
        return self
    
    class Config:
        """Configuration for the ProxyConfigResponse schema."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "ip_address": "192.168.1.1",
                "port": 8080,
                "protocol": "http",
                "username": "proxyuser",
                "password": "********",
                "country": "US",
                "provider": "ipburger",
                "is_active": True,
                "banned_sites": ["ebay"],
                "expires_at": "2025-06-30T00:00:00Z",
                "last_used": "2025-05-31T00:00:00Z",
                "success_count": 10,
                "failure_count": 2,
                "last_failure": "2025-05-30T00:00:00Z",
                "failure_reason": "Connection timeout",
                "created_at": "2025-05-31T00:00:00Z",
                "updated_at": None
            }
        }


class ProxyStatusResponse(BaseSchema):
    """
    Schema for proxy status response.
    
    Attributes:
        total: Total number of proxies
        active: Number of active proxies
        inactive: Number of inactive proxies
        success_rate: Overall success rate
        banned_count: Number of banned proxies
        expiring_soon: Number of proxies expiring soon
    """
    total: int
    active: int
    inactive: int
    success_rate: float
    banned_count: int
    expiring_soon: int

