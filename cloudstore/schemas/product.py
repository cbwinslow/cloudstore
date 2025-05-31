"""
Schemas for Product model validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from cloudstore.schemas.base import BaseSchema, BaseResponseSchema
from cloudstore.database.models import SiteEnum, ConditionEnum


class ProductBase(BaseSchema):
    """
    Base schema for Product with common fields.
    
    Attributes:
        site_id: Original ID from the site
        site: Site enum (EBAY, AMAZON, etc.)
        title: Product title
        description: Product description
        category: Product category
        subcategory: Product subcategory
        condition: Product condition enum
        brand: Product brand
        model: Product model
        url: Product URL
        image_urls: List of image URLs
        product_metadata: Additional site-specific metadata
    """
    site_id: str = Field(..., description="Original ID from the e-commerce site")
    site: SiteEnum = Field(..., description="E-commerce site")
    title: str = Field(..., description="Product title", max_length=500)
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category", max_length=100)
    subcategory: Optional[str] = Field(None, description="Product subcategory", max_length=100)
    condition: Optional[ConditionEnum] = Field(None, description="Product condition")
    brand: Optional[str] = Field(None, description="Product brand", max_length=100)
    model: Optional[str] = Field(None, description="Product model", max_length=100)
    url: str = Field(..., description="Product URL", max_length=1000)
    image_urls: Optional[List[str]] = Field(None, description="List of image URLs")
    product_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional site-specific metadata")
    is_active: bool = Field(True, description="Whether the product is active")


class ProductCreate(ProductBase):
    """Schema for creating a new product."""
    
    @model_validator(mode='after')
    def validate_product(self) -> 'ProductCreate':
        """Validate product data."""
        # Add any cross-field validation here
        if self.condition is None:
            self.condition = ConditionEnum.UNKNOWN
        return self


class ProductUpdate(BaseSchema):
    """
    Schema for updating an existing product.
    All fields are optional.
    """
    site_id: Optional[str] = Field(None, description="Original ID from the e-commerce site")
    site: Optional[SiteEnum] = Field(None, description="E-commerce site")
    title: Optional[str] = Field(None, description="Product title", max_length=500)
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category", max_length=100)
    subcategory: Optional[str] = Field(None, description="Product subcategory", max_length=100)
    condition: Optional[ConditionEnum] = Field(None, description="Product condition")
    brand: Optional[str] = Field(None, description="Product brand", max_length=100)
    model: Optional[str] = Field(None, description="Product model", max_length=100)
    url: Optional[str] = Field(None, description="Product URL", max_length=1000)
    image_urls: Optional[List[str]] = Field(None, description="List of image URLs")
    product_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional site-specific metadata")
    is_active: Optional[bool] = Field(None, description="Whether the product is active")


class ProductResponse(ProductBase, BaseResponseSchema):
    """Schema for product response including ID and timestamps."""
    
    class Config:
        """Configuration for the ProductResponse schema."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "site_id": "B08F2VGGJM",
                "site": "AMAZON",
                "title": "Sony WH-1000XM4 Wireless Noise Cancelling Headphones",
                "description": "Industry-leading noise cancellation with Dual Noise Sensor Technology",
                "category": "Electronics",
                "subcategory": "Headphones",
                "condition": "NEW",
                "brand": "Sony",
                "model": "WH-1000XM4",
                "url": "https://www.amazon.com/Sony-WH-1000XM4-Canceling-Headphones-phone-call/dp/B08F2VGGJM",
                "image_urls": ["https://m.media-amazon.com/images/I/71o8Q5XJS5L._AC_SL1500_.jpg"],
                "product_metadata": {"features": ["Noise cancellation", "30-hour battery life"]},
                "is_active": True,
                "created_at": "2025-05-31T00:00:00Z",
                "updated_at": "2025-05-31T00:00:00Z"
            }
        }


class ProductSearchParams(BaseSchema):
    """
    Schema for product search parameters.
    
    Attributes:
        query: Search query string
        site: Filter by site
        category: Filter by category
        brand: Filter by brand
        condition: Filter by condition
        min_price: Filter by minimum price
        max_price: Filter by maximum price
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        page: Page number
        page_size: Number of items per page
    """
    query: Optional[str] = Field(None, description="Search query")
    site: Optional[SiteEnum] = Field(None, description="Filter by site")
    category: Optional[str] = Field(None, description="Filter by category")
    brand: Optional[str] = Field(None, description="Filter by brand")
    condition: Optional[ConditionEnum] = Field(None, description="Filter by condition")
    min_price: Optional[float] = Field(None, description="Filter by minimum price")
    max_price: Optional[float] = Field(None, description="Filter by maximum price")
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc or desc)")
    page: int = Field(1, description="Page number", ge=1)
    page_size: int = Field(10, description="Number of items per page", ge=1, le=100)

