"""
Pydantic models for Amazon data structures.

This module contains Pydantic models for various entities from Amazon,
including products, offers, variations, shipping information, seller details, reviews,
and browse nodes. It supports both Product Advertising API and web scraping data formats.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Set

from pydantic import BaseModel, Field, HttpUrl, validator, root_validator, conint, confloat

from .constants import Region, Language, Condition, PrimeEligible, SortBy


# Base models
class Amount(BaseModel):
    """Model for monetary amounts with currency."""
    value: Decimal = Field(..., description="The monetary value")
    currency: str = Field("USD", description="The currency code (e.g., USD)")
    formatted_price: Optional[str] = Field(None, description="Formatted price string")
    
    def __str__(self) -> str:
        """String representation of amount."""
        if self.formatted_price:
            return self.formatted_price
        return f"{self.value} {self.currency}"
    
    class Config:
        """Pydantic config for Amount model."""
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class Address(BaseModel):
    """Model for address information."""
    name: Optional[str] = Field(None, description="Name associated with the address")
    street1: Optional[str] = Field(None, description="Street address, line 1")
    street2: Optional[str] = Field(None, description="Street address, line 2")
    city: Optional[str] = Field(None, description="City name")
    state_or_province: Optional[str] = Field(None, description="State or province")
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="Country code (e.g., US)")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    phone: Optional[str] = Field(None, description="Phone number")
    
    class Config:
        """Pydantic config for Address model."""
        validate_assignment = True


class Image(BaseModel):
    """Model for product images."""
    url: HttpUrl = Field(..., description="Image URL")
    height: Optional[int] = Field(None, description="Image height in pixels")
    width: Optional[int] = Field(None, description="Image width in pixels")
    variant: Optional[str] = Field(None, description="Image variant (e.g., 'MAIN', 'PT01')")
    
    class Config:
        """Pydantic config for Image model."""
        validate_assignment = True


class ImageSet(BaseModel):
    """Model for a set of product images in different sizes."""
    small: Optional[Image] = Field(None, description="Small image")
    medium: Optional[Image] = Field(None, description="Medium image")
    large: Optional[Image] = Field(None, description="Large image")
    variant: Optional[str] = Field("MAIN", description="Image set variant")
    
    class Config:
        """Pydantic config for ImageSet model."""
        validate_assignment = True


class Dimension(BaseModel):
    """Model for product dimensions."""
    height: Optional[Decimal] = Field(None, description="Height")
    width: Optional[Decimal] = Field(None, description="Width")
    length: Optional[Decimal] = Field(None, description="Length")
    weight: Optional[Decimal] = Field(None, description="Weight")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    
    class Config:
        """Pydantic config for Dimension model."""
        validate_assignment = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# Feature models
class Feature(BaseModel):
    """Model for product features/bullet points."""
    text: str = Field(..., description="Feature text")
    
    class Config:
        """Pydantic config for Feature model."""
        validate_assignment = True


# Availability models
class AvailabilityStatus(str, Enum):
    """Availability status options."""
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    LIMITED_AVAILABILITY = "LIMITED_AVAILABILITY"
    PREORDER = "PREORDER"
    BACKORDER = "BACKORDER"
    UNKNOWN = "UNKNOWN"


class Availability(BaseModel):
    """Model for product availability."""
    status: AvailabilityStatus = Field(AvailabilityStatus.UNKNOWN, description="Availability status")
    message: Optional[str] = Field(None, description="Availability message")
    min_order_quantity: Optional[int] = Field(None, description="Minimum order quantity")
    max_order_quantity: Optional[int] = Field(None, description="Maximum order quantity")
    available_quantity: Optional[int] = Field(None, description="Available quantity")
    
    @validator('status', pre=True)
    def parse_status(cls, v):
        """Parse status from string."""
        if isinstance(v, str):
            v = v.upper().replace(" ", "_")
            if "IN_STOCK" in v:
                return AvailabilityStatus.IN_STOCK
            elif "OUT_OF_STOCK" in v:
                return AvailabilityStatus.OUT_OF_STOCK
            elif "LIMITED" in v:
                return AvailabilityStatus.LIMITED_AVAILABILITY
            elif "PREORDER" in v:
                return AvailabilityStatus.PREORDER
            elif "BACKORDER" in v:
                return AvailabilityStatus.BACKORDER
        
        try:
            return AvailabilityStatus(v)
        except (ValueError, TypeError):
            return AvailabilityStatus.UNKNOWN
    
    class Config:
        """Pydantic config for Availability model."""
        validate_assignment = True


# Seller models
class SellerInfo(BaseModel):
    """Model for seller information."""
    id: Optional[str] = Field(None, description="Seller ID")
    name: str = Field(..., description="Seller name")
    url: Optional[HttpUrl] = Field(None, description="Seller store URL")
    feedback_rating: Optional[float] = Field(None, description="Seller feedback rating")
    feedback_count: Optional[int] = Field(None, description="Number of feedback ratings")
    is_amazon: Optional[bool] = Field(None, description="Whether the seller is Amazon")
    ships_from: Optional[str] = Field(None, description="Ships from location")
    
    class Config:
        """Pydantic config for SellerInfo model."""
        validate_assignment = True


# Shipping models
class DeliveryInfo(BaseModel):
    """Model for delivery information."""
    is_prime: bool = Field(False, description="Whether the item is Prime eligible")
    is_free_shipping: bool = Field(False, description="Whether free shipping is available")
    is_amazon_global: Optional[bool] = Field(None, description="Whether Amazon Global shipping is available")
    shipping_charge: Optional[Amount] = Field(None, description="Shipping charge, if any")
    estimated_arrival: Optional[str] = Field(None, description="Estimated arrival timeframe")
    fastest_delivery_date: Optional[datetime] = Field(None, description="Fastest delivery date")
    
    class Config:
        """Pydantic config for DeliveryInfo model."""
        validate_assignment = True


# Price models
class Price(BaseModel):
    """Model for product price information."""
    amount: Amount = Field(..., description="Price amount")
    savings: Optional[Amount] = Field(None, description="Savings amount")
    original_price: Optional[Amount] = Field(None, description="Original price before discount")
    per_unit_price: Optional[Amount] = Field(None, description="Price per unit")
    discount_percentage: Optional[int] = Field(None, description="Discount percentage", ge=0, le=100)
    
    @root_validator
    def calculate_savings(cls, values):
        """Calculate savings and discount if not provided."""
        amount = values.get('amount')
        original = values.get('original_price')
        savings = values.get('savings')
        discount = values.get('discount_percentage')
        
        if original and amount:
            if original.value > amount.value:
                # Calculate savings
                if not savings:
                    savings_value = original.value - amount.value
                    values['savings'] = Amount(
                        value=savings_value,
                        currency=amount.currency
                    )
                
                # Calculate discount percentage
                if not discount:
                    if original.value > 0:
                        discount_pct = (1 - (amount.value / original.value)) * 100
                        values['discount_percentage'] = round(discount_pct)
        
        return values
    
    class Config:
        """Pydantic config for Price model."""
        validate_assignment = True


# Offer models
class OfferCondition(BaseModel):
    """Model for offer condition."""
    condition: Condition = Field(Condition.NEW, description="Item condition")
    condition_description: Optional[str] = Field(None, description="Condition description")
    
    class Config:
        """Pydantic config for OfferCondition model."""
        validate_assignment = True


class Offer(BaseModel):
    """Model for a product offer."""
    id: Optional[str] = Field(None, description="Offer ID")
    price: Price = Field(..., description="Offer price")
    condition: OfferCondition = Field(..., description="Offer condition")
    seller: SellerInfo = Field(..., description="Seller information")
    delivery: DeliveryInfo = Field(..., description="Delivery information")
    availability: Availability = Field(..., description="Availability information")
    is_buybox_winner: Optional[bool] = Field(None, description="Whether this is the buy box winner")
    program_eligibility: Optional[Dict[str, bool]] = Field(None, description="Program eligibility (Prime, etc.)")
    
    class Config:
        """Pydantic config for Offer model."""
        validate_assignment = True


class OfferSummary(BaseModel):
    """Model for offer summary."""
    lowest_price: Optional[Price] = Field(None, description="Lowest price offered")
    buybox_price: Optional[Price] = Field(None, description="Buy box price")
    total_offer_count: Optional[int] = Field(None, description="Total number of offers")
    new_offer_count: Optional[int] = Field(None, description="Number of new offers")
    used_offer_count: Optional[int] = Field(None, description="Number of used offers")
    refurbished_offer_count: Optional[int] = Field(None, description="Number of refurbished offers")
    collectible_offer_count: Optional[int] = Field(None, description="Number of collectible offers")
    
    class Config:
        """Pydantic config for OfferSummary model."""
        validate_assignment = True


# Variation models
class VariationDimension(BaseModel):
    """Model for variation dimension (e.g., Size, Color)."""
    name: str = Field(..., description="Dimension name")
    values: List[str] = Field(..., description="Possible values")
    
    class Config:
        """Pydantic config for VariationDimension model."""
        validate_assignment = True


class VariationAttribute(BaseModel):
    """Model for a single variation attribute."""
    name: str = Field(..., description="Attribute name")
    value: str = Field(..., description="Attribute value")
    
    class Config:
        """Pydantic config for VariationAttribute model."""
        validate_assignment = True


class Variation(BaseModel):
    """Model for a product variation."""
    asin: str = Field(..., description="ASIN of the variation")
    title: Optional[str] = Field(None, description="Variation title")
    url: Optional[HttpUrl] = Field(None, description="Variation URL")
    price: Optional[Price] = Field(None, description="Variation price")
    image: Optional[Image] = Field(None, description="Variation image")
    attributes: List[VariationAttribute] = Field(default_factory=list, description="Variation attributes")
    availability: Optional[Availability] = Field(None, description="Availability status")
    is_current: Optional[bool] = Field(None, description="Whether this is the currently selected variation")
    
    class Config:
        """Pydantic config for Variation model."""
        validate_assignment = True


# Review models
class ReviewRating(BaseModel):
    """Model for review rating statistics."""
    average: float = Field(..., description="Average rating", ge=0, le=5)
    count: int = Field(..., description="Total number of ratings")
    five_star_percentage: Optional[int] = Field(None, description="Percentage of 5-star ratings", ge=0, le=100)
    four_star_percentage: Optional[int] = Field(None, description="Percentage of 4-star ratings", ge=0, le=100)
    three_star_percentage: Optional[int] = Field(None, description="Percentage of 3-star ratings", ge=0, le=100)
    two_star_percentage: Optional[int] = Field(None, description="Percentage of 2-star ratings", ge=0, le=100)
    one_star_percentage: Optional[int] = Field(None, description="Percentage of 1-star ratings", ge=0, le=100)
    
    class Config:
        """Pydantic config for ReviewRating model."""
        validate_assignment = True


class Review(BaseModel):
    """Model for a product review."""
    id: Optional[str] = Field(None, description="Review ID")
    title: Optional[str] = Field(None, description="Review title")
    author: str = Field(..., description="Reviewer name")
    date: datetime = Field(..., description="Review date")
    verified_purchase: bool = Field(False, description="Whether this is a verified purchase")
    rating: float = Field(..., description="Rating (0-5)", ge=0, le=5)
    content: str = Field(..., description="Review content")
    images: List[HttpUrl] = Field(default_factory=list, description="Review images")
    helpful_votes: Optional[int] = Field(None, description="Number of helpful votes")
    
    class Config:
        """Pydantic config for Review model."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


# Browse Node (Category) models
class BrowseNode(BaseModel):
    """Model for a browse node (category)."""
    id: str = Field(..., description="Browse node ID")
    name: str = Field(..., description="Browse node name")
    children: List["BrowseNode"] = Field(default_factory=list, description="Child browse nodes")
    ancestors: List["BrowseNode"] = Field(default_factory=list, description="Ancestor browse nodes")
    context_free_name: Optional[str] = Field(None, description="Context-free name")
    display_name: Optional[str] = Field(None, description="Display name")
    is_root: Optional[bool] = Field(None, description="Whether this is a root browse node")
    path: Optional[List[str]] = Field(None, description="Path from root to this node")
    
    class Config:
        """Pydantic config for BrowseNode model."""
        validate_assignment = True


BrowseNode.update_forward_refs()


class WebsiteSalesRank(BaseModel):
    """Model for website sales rank."""
    category_id: Optional[str] = Field(None, description="Category ID")
    category_name: Optional[str] = Field(None, description="Category name")
    rank: int = Field(..., description="Sales rank")
    
    class Config:
        """Pydantic config for WebsiteSalesRank model."""
        validate_assignment = True


# Product models
class ExternalId(BaseModel):
    """Model for external IDs (ISBN, UPC, etc.)."""
    type: str = Field(..., description="ID type (e.g., ISBN, UPC, EAN)")
    value: str = Field(..., description="ID value")
    
    class Config:
        """Pydantic config for ExternalId model."""
        validate_assignment = True


class ContentInfo(BaseModel):
    """Model for content information."""
    publication_date: Optional[datetime] = Field(None, description="Publication date")
    edition: Optional[str] = Field(None, description="Edition")
    languages: Optional[List[str]] = Field(None, description="Languages")
    pages_count: Optional[int] = Field(None, description="Number of pages")
    
    class Config:
        """Pydantic config for ContentInfo model."""
        validate_assignment = True


class ManufactureInfo(BaseModel):
    """Model for manufacture information."""
    model: Optional[str] = Field(None, description="Model number")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    warranty: Optional[str] = Field(None, description="Warranty information")
    
    class Config:
        """Pydantic config for ManufactureInfo model."""
        validate_assignment = True


class ByLineInfo(BaseModel):
    """Model for by-line information (authors, brand, etc.)."""
    brand: Optional[str] = Field(None, description="Brand name")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    contributors: Optional[List[Dict[str, str]]] = Field(None, description="Contributors (authors, etc.)")
    
    class Config:
        """Pydantic config for ByLineInfo model."""
        validate_assignment = True


class BasicProduct(BaseModel):
    """Basic model for product data from search results."""
    asin: str = Field(..., description="Amazon Standard Identification Number")
    title: str = Field(..., description="Product title")
    url: HttpUrl = Field(..., description="Product URL")
    image: Optional[Image] = Field(None, description="Main product image")
    price: Optional[Price] = Field(None, description="Product price")
    rating: Optional[float] = Field(None, description="Product rating (0-5)", ge=0, le=5)
    ratings_total: Optional[int] = Field(None, description="Total number of ratings")
    is_prime: Optional[bool] = Field(None, description="Whether the product is Prime eligible")
    is_amazon_choice: Optional[bool] = Field(None, description="Whether the product is Amazon's Choice")
    is_best_seller: Optional[bool] = Field(None, description="Whether the product is a Best Seller")
    position: Optional[int] = Field(None, description="Position in search results")
    sponsored: Optional[bool] = Field(None, description="Whether the product is sponsored")
    
    class Config:
        """Pydantic config for BasicProduct model."""
        validate_assignment = True


class DetailedProduct(BaseModel):
    """Detailed model for product information."""
    asin: str = Field(..., description="Amazon Standard Identification Number")
    parent_asin: Optional[str] = Field(None, description="Parent ASIN for variations")
    title: str = Field(..., description="Product title")
    url: HttpUrl = Field(..., description="Product URL")
    images: List[ImageSet] = Field(default_factory=list, description="Product images")
    description: Optional[str] = Field(None, description="Product description")
    features: List[Feature] = Field(default_factory=list, description="Product features")
    price: Optional[Price] = Field(None, description="Product price")
    by_line_info: Optional[ByLineInfo] = Field(None, description="By-line information")
    dimensions: Optional[Dimension] = Field(None, description="Product dimensions")
    external_ids: List[ExternalId] = Field(default_factory=list, description="External IDs")
    manufacture_info: Optional[ManufactureInfo] = Field(None, description="Manufacture information")
    content_info: Optional[ContentInfo] = Field(None, description="Content information")
    variation_attributes: List[VariationDimension] = Field(default_factory=list, description="Variation attributes")
    variations: List[Variation] = Field(default_factory=list, description="Product variations")
    offers: List[Offer] = Field(default_factory=list, description="Available offers")
    offer_summary: Optional[OfferSummary] = Field(None, description="Summary of offers")
    browse_nodes: List[BrowseNode] = Field(default_factory=list, description="Browse nodes")
    website_sales_rank: List[WebsiteSalesRank] = Field(default_factory=list, description="Website sales ranks")
    rating: Optional[ReviewRating] = Field(None, description="Review rating statistics")
    reviews: List[Review] = Field(default_factory=list, description="Product reviews")
    availability: Optional[Availability] = Field(None, description="Availability status")
    category_id: Optional[str] = Field(None, description="Primary category ID")
    category_name: Optional[str] = Field(None, description="Primary category name")
    
    class Config:
        """Pydantic config for DetailedProduct model."""
        validate_assignment = True


# Search models
class SearchFilters(BaseModel):
    """Model for search filters."""
    min_price: Optional[Decimal] = Field(None, description="Minimum price")
    max_price: Optional[Decimal] = Field(None, description="Maximum price")
    condition: Optional[Condition] = Field(None, description="Product condition")
    prime: Optional[PrimeEligible] = Field(None, description="Prime eligibility")
    min_rating: Optional[float] = Field(None, description="Minimum rating", ge=0, le=5)
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
    current_page: int = Field(1, description="Current page number", ge=1)
    total_pages: Optional[int] = Field(None, description="Total number of pages")
    total_results: Optional[int] = Field(None, description="Total number of results")
    results_per_page: int = Field(..., description="Number of results per page", ge=1)
    next_page_url: Optional[HttpUrl] = Field(None, description="URL for next page")
    previous_page_url: Optional[HttpUrl] = Field(None, description="URL for previous page")
    
    class Config:
        """Pydantic config for SearchPagination model."""
        validate_assignment = True


class SearchResult(BaseModel):
    """Model for search results."""
    products: List[BasicProduct] = Field(default_factory=list, description="List of products")
    pagination: SearchPagination = Field(..., description="Pagination information")
    keywords: Optional[str] = Field(None, description="Search keywords")
    filters: Optional[SearchFilters] = Field(None, description="Applied filters")
    sort_by: Optional[SortBy] = Field(None, description="Sort order used")
    category_id: Optional[str] = Field(None, description="Category ID if searching in a category")
    category_name: Optional[str] = Field(None, description="Category name if searching in a category")
    region: Region = Field(Region.US, description="Amazon region")
    timestamp: datetime = Field(default_factory=datetime.now, description="Search timestamp")
    
    class Config:
        """Pydantic config for SearchResult model."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


# PA-API specific models
class PaApiResource(BaseModel):
    """Model for a PA-API resource."""
    name: str = Field(..., description="Resource name")
    value: Optional[Any] = Field(None, description="Resource value")
    
    class Config:
        """Pydantic config for PaApiResource model."""
        validate_assignment = True


class PaApiError(BaseModel):
    """Model for PA-API error."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    
    class Config:
        """Pydantic config for PaApiError model."""
        validate_assignment = True


class PaApiResponse(BaseModel):
    """Base model for PA-API responses."""
    request_id: Optional[str] = Field(None, description="Request ID")
    errors: List[PaApiError] = Field(default_factory=list, description="Errors, if any")
    
    class Config:
        """Pydantic config for PaApiResponse model."""
        validate_assignment = True


class SearchItemsResponse(PaApiResponse):
    """Model for SearchItems API response."""
    search_result: Optional[SearchResult] = Field(None, description="Search results")
    
    class Config:
        """Pydantic config for SearchItemsResponse model."""
        validate_assignment = True


class GetItemsResponse(PaApiResponse):
    """Model for GetItems API response."""
    items: List[DetailedProduct] = Field(default_factory=list, description="Items retrieved")
    
    class Config:
        """Pydantic config for GetItemsResponse model."""
        validate_assignment = True


class GetVariationsResponse(PaApiResponse):
    """Model for GetVariations API response."""
    variation_summary: Optional[Dict[str, Any]] = Field(None, description="Variation summary")
    items: List[Variation] = Field(default_factory=list, description="Variation items")
    
    class Config:
        """Pydantic config for GetVariationsResponse model."""
        validate_assignment = True


class GetBrowseNodesResponse(PaApiResponse):
    """Model for GetBrowseNodes API response."""
    browse_nodes: List[BrowseNode] = Field(default_factory=list, description="Browse nodes retrieved")
    
    class Config:
        """Pydantic config for GetBrowseNodesResponse model."""
        validate_assignment = True

