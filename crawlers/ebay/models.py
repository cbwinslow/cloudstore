"""
Pydantic models for eBay API responses.

This module contains Pydantic models representing various entities from eBay's APIs,
including items, search results, categories, and shipping information.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, HttpUrl, validator, constr, conint

from .constants import ConditionId, CONDITION_NAMES


# Base models
class Amount(BaseModel):
    """Model for monetary amounts with currency."""
    value: Decimal = Field(..., description="The monetary value")
    currency_id: str = Field(..., description="The currency code (e.g., USD)")

    class Config:
        """Pydantic config for Amount model."""
        json_encoders = {
            Decimal: lambda v: float(v)
        }

    def __str__(self) -> str:
        """String representation of amount."""
        return f"{self.value} {self.currency_id}"


class Address(BaseModel):
    """Model for address information."""
    name: Optional[str] = Field(None, description="Name associated with the address")
    street1: Optional[str] = Field(None, description="Street address, line 1")
    street2: Optional[str] = Field(None, description="Street address, line 2")
    city_name: Optional[str] = Field(None, description="City name")
    state_or_province: Optional[str] = Field(None, description="State or province")
    country: Optional[str] = Field(None, description="Country name")
    country_id: Optional[str] = Field(None, description="Country code (e.g., US)")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    phone: Optional[str] = Field(None, description="Phone number")
    address_id: Optional[str] = Field(None, description="eBay's internal address ID")

    class Config:
        """Pydantic config for Address model."""
        validate_assignment = True


class Seller(BaseModel):
    """Model for seller information."""
    user_id: str = Field(..., description="Seller's eBay user ID")
    feedback_score: Optional[int] = Field(None, description="Seller's feedback score")
    positive_feedback_percent: Optional[float] = Field(None, description="Percentage of positive feedback")
    feedback_rating_star: Optional[str] = Field(None, description="Feedback rating star")
    top_rated_seller: Optional[bool] = Field(None, description="Whether the seller is top-rated")
    store_name: Optional[str] = Field(None, description="Seller's store name, if any")
    store_url: Optional[HttpUrl] = Field(None, description="URL to the seller's eBay store")

    class Config:
        """Pydantic config for Seller model."""
        validate_assignment = True


class Category(BaseModel):
    """Model for a category."""
    category_id: str = Field(..., description="eBay category ID")
    category_name: str = Field(..., description="Category name")
    parent_category_id: Optional[str] = Field(None, description="Parent category ID")
    level: Optional[int] = Field(None, description="Category level in hierarchy")
    leaf_category: Optional[bool] = Field(None, description="Whether this is a leaf category")

    class Config:
        """Pydantic config for Category model."""
        validate_assignment = True


class ShippingOption(BaseModel):
    """Model for a shipping option."""
    shipping_service_code: str = Field(..., description="Shipping service code")
    shipping_service_name: str = Field(..., description="Shipping service name")
    shipping_cost: Amount = Field(..., description="Shipping cost")
    expedited_shipping: Optional[bool] = Field(None, description="Whether this is expedited shipping")
    shipping_time_min: Optional[int] = Field(None, description="Minimum shipping time in days")
    shipping_time_max: Optional[int] = Field(None, description="Maximum shipping time in days")
    free_shipping: Optional[bool] = Field(None, description="Whether shipping is free")
    ship_to_locations: Optional[List[str]] = Field(None, description="Locations that can be shipped to")

    class Config:
        """Pydantic config for ShippingOption model."""
        validate_assignment = True


class ShippingInfo(BaseModel):
    """Model for shipping information."""
    shipping_options: List[ShippingOption] = Field(default_factory=list, description="Available shipping options")
    handling_time: Optional[int] = Field(None, description="Handling time in days")
    shipping_type: Optional[str] = Field(None, description="Shipping type")
    ship_to_locations: Optional[List[str]] = Field(None, description="Locations that can be shipped to")
    global_shipping: Optional[bool] = Field(None, description="Whether global shipping is available")
    excluded_ship_to_locations: Optional[List[str]] = Field(None, description="Excluded shipping locations")

    class Config:
        """Pydantic config for ShippingInfo model."""
        validate_assignment = True


class ItemSpecific(BaseModel):
    """Model for item-specific details."""
    name: str = Field(..., description="Name of the specific")
    value: List[str] = Field(..., description="Values for the specific")

    class Config:
        """Pydantic config for ItemSpecific model."""
        validate_assignment = True


class ItemCondition(BaseModel):
    """Model for item condition information."""
    condition_id: int = Field(..., description="eBay condition ID")
    condition_name: str = Field(..., description="Condition name")
    
    @validator('condition_name', pre=True)
    def set_condition_name(cls, v, values):
        """Set condition name based on condition ID if not provided."""
        if not v and 'condition_id' in values:
            condition_id = values['condition_id']
            if condition_id in CONDITION_NAMES:
                return CONDITION_NAMES[condition_id]
        return v

    class Config:
        """Pydantic config for ItemCondition model."""
        validate_assignment = True


class ListingInfo(BaseModel):
    """Model for listing information."""
    best_offer_enabled: Optional[bool] = Field(None, description="Whether best offer is enabled")
    buy_it_now_available: Optional[bool] = Field(None, description="Whether Buy It Now is available")
    start_time: Optional[datetime] = Field(None, description="Listing start time")
    end_time: Optional[datetime] = Field(None, description="Listing end time")
    listing_type: Optional[str] = Field(None, description="Type of listing (e.g., FixedPrice, Auction)")
    gift: Optional[bool] = Field(None, description="Whether this item is eligible as a gift")
    lot_size: Optional[int] = Field(None, description="Number of items in the lot")
    watch_count: Optional[int] = Field(None, description="Number of watchers")
    hit_count: Optional[int] = Field(None, description="Number of page views")
    quantity: Optional[int] = Field(None, description="Available quantity")

    class Config:
        """Pydantic config for ListingInfo model."""
        validate_assignment = True


class ItemImage(BaseModel):
    """Model for an item image."""
    image_url: HttpUrl = Field(..., description="URL to the image")
    gallery_plus: Optional[bool] = Field(None, description="Whether this is a gallery plus image")
    gallery_type: Optional[str] = Field(None, description="Gallery type")
    is_primary: Optional[bool] = Field(None, description="Whether this is the primary image")
    max_height: Optional[int] = Field(None, description="Maximum height of the image")
    max_width: Optional[int] = Field(None, description="Maximum width of the image")

    class Config:
        """Pydantic config for ItemImage model."""
        validate_assignment = True


# Main models for API responses
class Item(BaseModel):
    """Model for an eBay item."""
    item_id: str = Field(..., description="eBay item ID")
    title: str = Field(..., description="Item title")
    subtitle: Optional[str] = Field(None, description="Item subtitle")
    primary_category: Optional[Category] = Field(None, description="Primary category")
    secondary_category: Optional[Category] = Field(None, description="Secondary category, if any")
    gallery_url: Optional[HttpUrl] = Field(None, description="URL to the gallery image")
    view_item_url: Optional[HttpUrl] = Field(None, description="URL to view the item")
    paypal_accepted: Optional[bool] = Field(None, description="Whether PayPal is accepted")
    auto_pay: Optional[bool] = Field(None, description="Whether auto-pay is enabled")
    location: Optional[str] = Field(None, description="Item location")
    country: Optional[str] = Field(None, description="Country code")
    shipping_info: Optional[ShippingInfo] = Field(None, description="Shipping information")
    seller: Optional[Seller] = Field(None, description="Seller information")
    bidding_info: Optional[Dict[str, Any]] = Field(None, description="Bidding information")
    listing_info: Optional[ListingInfo] = Field(None, description="Listing information")
    current_price: Optional[Amount] = Field(None, description="Current price")
    buy_it_now_price: Optional[Amount] = Field(None, description="Buy It Now price, if applicable")
    converted_current_price: Optional[Amount] = Field(None, description="Current price in preferred currency")
    item_specifics: Optional[List[ItemSpecific]] = Field(None, description="Item-specific details")
    description: Optional[str] = Field(None, description="Item description")
    condition: Optional[ItemCondition] = Field(None, description="Item condition")
    images: Optional[List[ItemImage]] = Field(None, description="Item images")
    quantity_available: Optional[int] = Field(None, description="Available quantity")
    quantity_sold: Optional[int] = Field(None, description="Quantity sold")
    top_rated_listing: Optional[bool] = Field(None, description="Whether this is a top-rated listing")

    class Config:
        """Pydantic config for Item model."""
        validate_assignment = True


class PaginationInfo(BaseModel):
    """Model for pagination information."""
    entry_per_page: int = Field(..., description="Number of entries per page")
    page_number: int = Field(..., description="Current page number")
    total_pages: int = Field(..., description="Total number of pages")
    total_entries: Optional[int] = Field(None, description="Total number of entries")

    class Config:
        """Pydantic config for PaginationInfo model."""
        validate_assignment = True


class SearchResult(BaseModel):
    """Model for search results."""
    items: List[Item] = Field(default_factory=list, description="Items found in the search")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    timestamp: datetime = Field(..., description="Timestamp of the search")
    search_terms: Optional[str] = Field(None, description="Search terms used")
    category_id: Optional[str] = Field(None, description="Category ID searched, if any")
    sort_order: Optional[str] = Field(None, description="Sort order used")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters applied to the search")
    total_items_count: Optional[int] = Field(None, description="Total count of items matching search")

    class Config:
        """Pydantic config for SearchResult model."""
        validate_assignment = True


class CategoryHierarchy(BaseModel):
    """Model for category hierarchy."""
    categories: List[Category] = Field(default_factory=list, description="List of categories")
    timestamp: datetime = Field(..., description="Timestamp of the retrieval")
    version: Optional[str] = Field(None, description="Version of the category hierarchy")
    update_time: Optional[datetime] = Field(None, description="Last update time of the hierarchy")
    category_count: Optional[int] = Field(None, description="Total number of categories")

    class Config:
        """Pydantic config for CategoryHierarchy model."""
        validate_assignment = True


class ApiResponse(BaseModel):
    """Base model for API responses."""
    ack: str = Field(..., description="Acknowledgement (Success, Failure, Warning, PartialFailure)")
    timestamp: datetime = Field(..., description="Timestamp of the response")
    version: Optional[str] = Field(None, description="API version")
    build: Optional[str] = Field(None, description="API build number")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Errors, if any")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for the request")

    class Config:
        """Pydantic config for ApiResponse model."""
        validate_assignment = True


class FindingApiResponse(ApiResponse):
    """Model for Finding API responses."""
    search_result: Optional[SearchResult] = Field(None, description="Search results")
    pagination_output: Optional[PaginationInfo] = Field(None, description="Pagination information")
    categories_version: Optional[str] = Field(None, description="Version of categories used")
    aspect_histogram_container: Optional[List[Dict[str, Any]]] = Field(None, description="Aspect histograms")

    class Config:
        """Pydantic config for FindingApiResponse model."""
        validate_assignment = True


class ShoppingApiResponse(ApiResponse):
    """Model for Shopping API responses."""
    item: Optional[Item] = Field(None, description="Item details")
    items: Optional[List[Item]] = Field(None, description="Multiple items, if applicable")
    category_array: Optional[List[Category]] = Field(None, description="Categories, if applicable")
    seller_info: Optional[Seller] = Field(None, description="Seller information, if applicable")
    ebay_time: Optional[datetime] = Field(None, description="eBay server time")

    class Config:
        """Pydantic config for ShoppingApiResponse model."""
        validate_assignment = True


# Authentication models
class OAuthToken(BaseModel):
    """Model for OAuth token."""
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(..., description="Token type (e.g., 'Bearer')")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token, if provided")
    scope: Optional[str] = Field(None, description="Scope of the token")
    expires_at: Optional[datetime] = Field(None, description="Timestamp when token expires")

    class Config:
        """Pydantic config for OAuthToken model."""
        validate_assignment = True

