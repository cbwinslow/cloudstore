"""
ShopGoodwill API endpoints.

This module provides RESTful API endpoints for interacting with ShopGoodwill.com,
allowing clients to search for items, get item details, and browse categories.
"""

import logging
from typing import List, Optional, Any, Dict
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, AnyHttpUrl

from cloudstore.core.config import settings
from crawlers.shopgoodwill.crawler import SyncShopGoodwillCrawler, ShopGoodwillError, ItemNotFoundError
from crawlers.shopgoodwill.constants import SortOptions, ConditionOptions

# Configure logger
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(
    prefix="/shopgoodwill",
    tags=["shopgoodwill"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)

# Pydantic models for request/response validation

class ItemImage(BaseModel):
    """Model for an item image URL."""
    url: AnyHttpUrl

class Bid(BaseModel):
    """Model for a bid on an item."""
    bidder: str
    amount: Decimal
    date: str

class ItemBase(BaseModel):
    """Base model for ShopGoodwill items."""
    item_id: str
    title: str
    current_price: Decimal
    url: AnyHttpUrl

class SearchResultItem(ItemBase):
    """Model for an item in search results."""
    shipping_cost: Optional[Decimal] = None
    seller: Optional[str] = None
    bids_count: Optional[int] = 0
    time_left: Optional[str] = None
    image_url: Optional[AnyHttpUrl] = None

    class Config:
        schema_extra = {
            "example": {
                "item_id": "123456",
                "title": "Vintage Camera",
                "current_price": 24.99,
                "shipping_cost": 8.99,
                "seller": "Seattle Goodwill",
                "bids_count": 5,
                "time_left": "1d 4h 30m",
                "image_url": "https://shopgoodwill.com/images/items/123456.jpg",
                "url": "https://shopgoodwill.com/item/123456"
            }
        }

class SearchResponse(BaseModel):
    """Model for search results response."""
    items: List[SearchResultItem]
    page: int
    total_pages: int
    total_items: int
    items_per_page: int
    query: Optional[str] = None

class ItemDetail(ItemBase):
    """Model for detailed item information."""
    condition: Optional[str] = None
    shipping_cost: Optional[Decimal] = None
    seller: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    bids: List[Dict[str, Any]] = Field(default_factory=list)
    end_date: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "item_id": "123456",
                "title": "Vintage Camera",
                "current_price": 24.99,
                "condition": "Good",
                "shipping_cost": 8.99,
                "seller": "Seattle Goodwill",
                "description": "Vintage camera in good working condition...",
                "images": [
                    "https://shopgoodwill.com/images/items/123456_1.jpg",
                    "https://shopgoodwill.com/images/items/123456_2.jpg"
                ],
                "bids": [
                    {"bidder": "user123", "amount": 24.99, "date": "2025-05-30 15:30:45"},
                    {"bidder": "user456", "amount": 22.50, "date": "2025-05-30 14:15:22"}
                ],
                "end_date": "2025-06-02 18:00:00",
                "url": "https://shopgoodwill.com/item/123456"
            }
        }

class Category(BaseModel):
    """Model for a ShopGoodwill category."""
    category_id: str
    name: str
    count: int
    url: AnyHttpUrl

    class Config:
        schema_extra = {
            "example": {
                "category_id": "18",
                "name": "Electronics",
                "count": 2345,
                "url": "https://shopgoodwill.com/categories?categoryId=18"
            }
        }

class ErrorResponse(BaseModel):
    """Model for API error responses."""
    error: str
    detail: Optional[str] = None

# Dependency for getting crawler instance
def get_crawler():
    """Dependency to get a configured ShopGoodwill crawler instance."""
    return SyncShopGoodwillCrawler(
        use_proxy=settings.SHOPGOODWILL_PROXY_ENABLED,
        rate_limit=settings.SHOPGOODWILL_RATE_LIMIT,
        burst_limit=settings.SHOPGOODWILL_RATE_LIMIT_BURST,
        retry_attempts=settings.SHOPGOODWILL_RETRY_ATTEMPTS,
        retry_backoff=settings.SHOPGOODWILL_RETRY_BACKOFF,
        timeout=settings.SHOPGOODWILL_REQUEST_TIMEOUT
    )

# API endpoints

@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for items on ShopGoodwill",
    description="Search for items on ShopGoodwill.com with various filters and pagination.",
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def search_items(
    query: Optional[str] = Query(None, description="Search query string"),
    category_id: Optional[str] = Query(None, description="Category ID to filter by"),
    sort_by: SortOptions = Query(SortOptions.ENDING_SOON, description="Sort order for results"),
    min_price: Optional[float] = Query(None, description="Minimum price filter", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price filter", ge=0),
    condition: Optional[ConditionOptions] = Query(None, description="Item condition filter"),
    page: int = Query(1, description="Page number", ge=1),
    items_per_page: int = Query(40, description="Items per page", ge=1, le=100),
    crawler: SyncShopGoodwillCrawler = Depends(get_crawler)
):
    """
    Search for items on ShopGoodwill.com.
    
    Parameters can be used to filter and sort the results.
    """
    try:
        # Validate min_price and max_price relationship if both are provided
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price"
            )
        
        results = crawler.search(
            query=query,
            category_id=category_id,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            page=page,
            items_per_page=items_per_page
        )
        
        return results
        
    except ShopGoodwillError as e:
        logger.error(f"Error searching ShopGoodwill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/item/{item_id}",
    response_model=ItemDetail,
    status_code=status.HTTP_200_OK,
    summary="Get item details",
    description="Get detailed information about a specific item on ShopGoodwill.com.",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Item not found"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_item_details(
    item_id: str = Path(..., description="Item ID to retrieve"),
    crawler: SyncShopGoodwillCrawler = Depends(get_crawler)
):
    """
    Get detailed information about a specific item on ShopGoodwill.com.
    """
    try:
        item = crawler.get_item(item_id)
        return item
        
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found"
        )
    except ShopGoodwillError as e:
        logger.error(f"Error getting item details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/categories",
    response_model=List[Category],
    status_code=status.HTTP_200_OK,
    summary="Get categories",
    description="Get a list of available categories on ShopGoodwill.com.",
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_categories(
    crawler: SyncShopGoodwillCrawler = Depends(get_crawler)
):
    """
    Get a list of available categories on ShopGoodwill.com.
    """
    try:
        categories = crawler.get_categories()
        return categories
        
    except ShopGoodwillError as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/search/multi-page",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search multiple pages",
    description="Search for items across multiple pages on ShopGoodwill.com.",
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def search_multiple_pages(
    query: Optional[str] = Query(None, description="Search query string"),
    category_id: Optional[str] = Query(None, description="Category ID to filter by"),
    sort_by: SortOptions = Query(SortOptions.ENDING_SOON, description="Sort order for results"),
    min_price: Optional[float] = Query(None, description="Minimum price filter", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price filter", ge=0),
    condition: Optional[ConditionOptions] = Query(None, description="Item condition filter"),
    max_pages: int = Query(3, description="Maximum number of pages to fetch", ge=1, le=10),
    items_per_page: int = Query(40, description="Items per page", ge=1, le=100),
    crawler: SyncShopGoodwillCrawler = Depends(get_crawler)
):
    """
    Search for items across multiple pages on ShopGoodwill.com.
    
    This endpoint allows fetching more results by automatically paginating through
    multiple pages and combining the results.
    """
    try:
        # Validate min_price and max_price relationship if both are provided
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price"
            )
        
        results = crawler.search_multiple_pages(
            query=query,
            category_id=category_id,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            max_pages=max_pages,
            items_per_page=items_per_page
        )
        
        return results
        
    except ShopGoodwillError as e:
        logger.error(f"Error searching multiple pages on ShopGoodwill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

