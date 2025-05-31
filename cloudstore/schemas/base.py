"""
Base schemas for common fields and shared functionality.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List, Generic, TypeVar, Type

from pydantic import BaseModel, Field, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {}
        }
    )


class BaseResponseSchema(BaseSchema):
    """Base schema for all API responses with common metadata."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


# Generic type for ID
T = TypeVar('T')


class PaginatedResponse(BaseSchema, Generic[T]):
    """
    Generic schema for paginated responses.
    
    Attributes:
        items: List of items in the current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
        total_pages: Total number of pages
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseSchema):
    """
    Schema for API error responses.
    
    Attributes:
        detail: Error message
        code: Optional error code
    """
    detail: str
    code: Optional[str] = None

