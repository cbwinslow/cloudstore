"""
Pydantic models for AliExpress data structures.

This module contains Pydantic models for various entities from AliExpress,
including products, variations, shipping information, seller details, and reviews.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Set

from pydantic import BaseModel, Field, HttpUrl, validator, root_validator, conint, confloat

from .constants import Currency, Language


# Base models
class Money(BaseModel):
    """Model for monetary values with currency."""
    value: Decimal = Field(..., description="The monetary value")
    currency: Currency = Field(Currency.USD, description="The currency code (e.g., USD)")
    
    def __str__(self) -> str:
        """String representation of money value."""
        return f"{self.value} {self.currency}"
    
    class Config:
        """Pydantic config for Money model."""
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class Price(BaseModel):
    """Model for product price information."""
    current: Money = Field(..., description="Current price")
    original: Optional[Money] = Field(None, description="Original price before discount")
    discount_percentage: Optional[int] = Field(None, description="Discount percentage", ge=0, le=100)
    
    @root_validator
    def calculate_discount(cls, values):
        """Calculate discount percentage if not provided."""
        current = values.get('current')
        original = values.get('original')
        discount = values.get('discount_percentage')
        
        if original and current and discount is None:
            if original.value > 0 and original.value > current.value:
                discount_pct = (1 - (current.value / original.value)) * 100
                values['discount_percentage'] = round(discount_pct)
        
        return values
    
    class Config:
        """Pydantic config for Price model."""
        validate_assignment = True


class Image(BaseModel):
    """Model for product images."""
    url: HttpUrl = Field(..., description="Image URL")
    thumbnail_url: Optional[HttpUrl] = Field(None, description="Thumbnail URL")
    position: Optional[int] = Field(None, description="Image position/order")
    
    class Config:
        """Pydantic config for Image model."""
        validate_assignment = True


class Address(BaseModel):
    """Model for address information."""
    country: Optional[str] = Field(None, description="Country")
    state: Optional[str] = Field(None, description="State or province")
    city: Optional[str] = Field(None, description="City")
    zip_code: Optional[str] = Field(None, description="Postal/ZIP code")
    
    class Config:
        """Pydantic config for Address model."""
        validate_assignment = True


class Specification(BaseModel):
    """Model for product specifications."""
    name: str = Field(..., description="Specification name")
    value: str = Field(..., description="Specification value")
    
    class Config:
        """Pydantic config for Specification model."""
        validate_assignment = True


# Shipping models
class ShippingMethod(BaseModel):
    """Model for shipping method information."""
    name: str = Field(..., description="Shipping method name")
    company: Optional[str] = Field(None, description="Shipping company")
    cost: Money = Field(..., description="Shipping cost")
    delivery_time: Optional[str] = Field(None, description="Estimated delivery time")
    tracking_available: Optional[bool] = Field(None, description="Whether tracking is available")
    
    class Config:
        """Pydantic config for ShippingMethod model."""
        validate_assignment = True


class ShippingInfo(BaseModel):
    """Model for shipping information."""
    methods: List[ShippingMethod] = Field(default_factory=list, description="Available shipping methods")
    free_shipping: bool = Field(False, description="Whether free shipping is available")
    ships_from: Optional[str] = Field(None, description="Country/region item ships from")
    ships_to: List[str] = Field(default_factory=list, description="Countries/regions item ships to")
    
    @validator('free_shipping', pre=True)
    def check_free_shipping(cls, v, values):
        """Check if any shipping method is free."""
        if v is True:
            return True
        
        methods = values.get('methods', [])
        for method in methods:
            if hasattr(method, 'cost') and method.cost.value == 0:
                return True
        
        return False
    
    class Config:
        """Pydantic config for ShippingInfo model."""
        validate_assignment = True


# Seller models
class SellerInfo(BaseModel):
    """Model for seller information."""
    id: str = Field(..., description="Seller ID")
    name: str = Field(..., description="Seller name/store name")
    url: Optional[HttpUrl] = Field(None, description="Seller store URL")
    positive_feedback_percentage: Optional[float] = Field(None, description="Positive feedback percentage", ge=0, le=100)
    feedback_score: Optional[int] = Field(None, description="Feedback score")
    top_rated: Optional[bool] = Field(None, description="Whether seller is top-rated")
    years_active: Optional[int] = Field(None, description="Years active on platform")
    followers_count: Optional[int] = Field(None, description="Number of followers")
    
    class Config:
        """Pydantic config for SellerInfo model."""
        validate_assignment = True


# Review models
class ReviewRating(BaseModel):
    """Model for review rating statistics."""
    average: float = Field(..., description="Average rating", ge=0, le=5)
    count: int = Field(..., description="Total number of ratings")
    five_star: Optional[int] = Field(None, description="Number of 5-star ratings")
    four_star: Optional[int] = Field(None, description="Number of 4-star ratings")
    three_star: Optional[int] = Field(None, description="Number of 3-star ratings")
    two_star: Optional[int] = Field(None, description="Number of 2-star ratings")
    one_star: Optional[int] = Field(None, description="Number of 1-star ratings")
    
    @validator('average')
    def validate_average(cls, v):
        """Validate average rating."""
        return round(v * 2) / 2  # Round to nearest 0.5
    
    class Config:
        """Pydantic config for ReviewRating model."""
        validate_assignment = True


class Review(BaseModel):
    """Model for a product review."""
    id: Optional[str] = Field(None, description="Review ID")
    author: str = Field(..., description="Reviewer name/username")
    date: datetime = Field(..., description="Review date")
    rating: float = Field(..., description="Rating (0-5)", ge=0, le=5)
    content: str = Field(..., description="Review content")
    images: List[HttpUrl] = Field(default_factory=list, description="Review images")
    country: Optional[str] = Field(None, description="Reviewer country")
    helpful_votes: Optional[int] = Field(None, description="Number of helpful votes")
    
    class Config:
        """Pydantic config for Review model."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


# Variation models
class VariationOption(BaseModel):
    """Model for a single variation option."""
    id: str = Field(..., description="Option ID")
    name: str = Field(..., description="Option name")
    image: Optional[HttpUrl] = Field(None, description="Option image")
    price_adjustment: Optional[Money] = Field(None, description="Price adjustment")
    available: bool = Field(True, description="Whether the option is available")
    
    class Config:
        """Pydantic config for VariationOption model."""
        validate_assignment = True


class Variation(BaseModel):
    """Model for product variation."""
    name: str = Field(..., description="Variation name (e.g., 'Color', 'Size')")
    options: List[VariationOption] = Field(..., description="Available options")
    
    class Config:
        """Pydantic config for Variation model."""
        validate_assignment = True


# Product models
class BasicProduct(BaseModel):
    """Basic model for product data from search results."""
    product_id: str = Field(..., description="Product ID")
    title: str = Field(..., description="Product title")
    url: HttpUrl = Field(..., description="Product URL")
    price: Price = Field(..., description="Product price information")
    image_url: Optional[HttpUrl] = Field(None, description="Main product image URL")
    shipping_price: Optional[Money] = Field(None, description="Shipping price")
    free_shipping: bool = Field(False, description="Whether free shipping is available")
    rating: Optional[float] = Field(None, description="Product rating (0-5)", ge=0, le=5)
    reviews_count: Optional[int] = Field(None, description="Number of reviews")
    orders_count: Optional[int] = Field(None, description="Number of orders")
    seller_name: Optional[str] = Field(None, description="Seller name")
    
    class Config:
        """Pydantic config for BasicProduct model."""
        validate_assignment = True


class DetailedProduct(BaseModel):
    """Detailed model for product information."""
    product_id: str = Field(..., description="Product ID")
    title: str = Field(..., description="Product title")
    url: HttpUrl = Field(..., description="Product URL")
    price: Price = Field(..., description="Product price information")
    images: List[Image] = Field(default_factory=list, description="Product images")
    description: Optional[str] = Field(None, description="Product description")
    specifications: List[Specification] = Field(default_factory=list, description="Product specifications")
    variations: List[Variation] = Field(default_factory=list, description="Product variations")
    shipping: ShippingInfo = Field(..., description="Shipping information")
    seller: SellerInfo = Field(..., description="Seller information")
    rating: Optional[ReviewRating] = Field(None, description="Review rating statistics")
    reviews: List[Review] = Field(default_factory=list, description="Product reviews")
    orders_count: Optional[int] = Field(None, description="Number of orders")
    available_quantity: Optional[int] = Field(None, description="Available quantity")
    min_order_quantity: Optional[int] = Field(1, description="Minimum order quantity")
    max_order_quantity: Optional[int] = Field(None, description="Maximum order quantity")
    sku: Optional[str] = Field(None, description="Product SKU")
    category_id: Optional[str] = Field(None, description="Category ID")
    category_name: Optional[str] = Field(None, description="Category name")
    
    class Config:
        """Pydantic config for DetailedProduct model."""
        validate_assignment = True


# Search models
class SearchFilters(BaseModel):
    """Model for search filters."""
    min_price: Optional[Decimal] = Field(None, description="Minimum price")
    max_price: Optional[Decimal] = Field(None, description="Maximum price")
    free_shipping: Optional[bool] = Field(None, description="Free shipping filter")
    min_rating: Optional[float] = Field(None, description="Minimum rating", ge=0, le=5)
    ship_from: Optional[str] = Field(None, description="Ship from country")
    ship_to: Optional[str] = Field(None, description="Ship to country")
    category_id: Optional[str] = Field(None, description="Category ID")
    
    @validator('min_price', 'max_price')
    def validate_price(cls, v):
        """Validate price is positive."""
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v
    
    class Config:
        """Pydantic config for SearchFilters model."""
        validate_assignment = True


class SearchPagination(BaseModel):
    """Model for search pagination information."""
    page: int = Field(1, description="Current page number", ge=1)
    total_pages: int = Field(1, description="Total number of pages", ge=1)
    items_per_page: int = Field(..., description="Number of items per page", ge=1)
    total_items: Optional[int] = Field(None, description="Total number of items")
    
    @validator('page')
    def validate_page(cls, v, values):
        """Validate page number."""
        total_pages = values.get('total_pages', 1)
        if v > total_pages:
            return total_pages
        return v
    
    class Config:
        """Pydantic config for SearchPagination model."""
        validate_assignment = True


class SearchResult(BaseModel):
    """Model for search results."""
    products: List[BasicProduct] = Field(default_factory=list, description="List of products")
    pagination: SearchPagination = Field(..., description="Pagination information")
    query: Optional[str] = Field(None, description="Search query")
    filters: Optional[SearchFilters] = Field(None, description="Applied filters")
    sort_by: Optional[str] = Field(None, description="Sort order used")
    category_id: Optional[str] = Field(None, description="Category ID if searching in a category")
    category_name: Optional[str] = Field(None, description="Category name if searching in a category")
    timestamp: datetime = Field(default_factory=datetime.now, description="Search timestamp")
    
    class Config:
        """Pydantic config for SearchResult model."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class Category(BaseModel):
    """Model for product category."""
    id: str = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    url: Optional[HttpUrl] = Field(None, description="Category URL")
    parent_id: Optional[str] = Field(None, description="Parent category ID")
    level: Optional[int] = Field(None, description="Category level in hierarchy")
    children: List["Category"] = Field(default_factory=list, description="Child categories")
    product_count: Optional[int] = Field(None, description="Number of products in category")
    
    class Config:
        """Pydantic config for Category model."""
        validate_assignment = True


Category.update_forward_refs()


class CategoryTree(BaseModel):
    """Model for category tree."""
    categories: List[Category] = Field(default_factory=list, description="List of top-level categories")
    total_count: Optional[int] = Field(None, description="Total number of categories")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")
    
    class Config:
        """Pydantic config for CategoryTree model."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

