"""
eBay API endpoints.

This module provides RESTful API endpoints for interacting with eBay,
allowing clients to search for items, get item details, and browse categories.
"""

import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl, validator

from cloudstore.core.config import settings
from crawlers.ebay.api import (
    SyncEbayApiClient, EbayApiError, AuthenticationError, 
    RateLimitError, ItemNotFoundError, InvalidRequestError
)
from crawlers.ebay.constants import (
    SortOrder, ConditionId, ItemFilter, GlobalId,
    ERROR_MESSAGES
)
from crawlers.ebay.models import (
    Item, SearchResult, Category, CategoryHierarchy,
    Amount, Seller, ShippingInfo
)

# Configure logger
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(
    prefix="/ebay",
    tags=["ebay"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)

# Pydantic models for request/response validation

class ItemFilterRequest(BaseModel):
    """Model for item filter in search requests."""
    name: str = Field(..., description="Filter name")
    value: Any = Field(..., description="Filter value")
    paramName: Optional[str] = Field(None, description="Parameter name for parameterized filters")
    paramValue: Optional[str] = Field(None, description="Parameter value for parameterized filters")

    class Config:
        """Pydantic config for ItemFilterRequest model."""
        schema_extra = {
            "example": {
                "name": "MaxPrice",
                "value": "100.00",
                "paramName": "Currency",
                "paramValue": "USD"
            }
        }


class SearchRequest(BaseModel):
    """Model for search request parameters."""
    keywords: Optional[str] = Field(None, description="Search keywords")
    category_id: Optional[str] = Field(None, description="Category ID to search in")
    sort_order: Optional[SortOrder] = Field(SortOrder.BEST_MATCH, description="Sort order for results")
    item_filters: Optional[List[ItemFilterRequest]] = Field(None, description="Filters to apply")
    page: int = Field(1, description="Page number", ge=1)
    items_per_page: int = Field(50, description="Items per page", ge=1, le=100)
    global_id: Optional[GlobalId] = Field(GlobalId.EBAY_US, description="eBay global ID (marketplace)")
    
    @validator('keywords', 'category_id')
    def validate_search_criteria(cls, v, values):
        """Validate that either keywords or category_id is provided."""
        if not v and 'keywords' in values and not values['keywords'] and 'category_id' in values and not values['category_id']:
            raise ValueError("Either keywords or category_id must be provided")
        return v

    class Config:
        """Pydantic config for SearchRequest model."""
        validate_assignment = True
        schema_extra = {
            "example": {
                "keywords": "vintage camera",
                "category_id": "625",
                "sort_order": "BestMatch",
                "item_filters": [
                    {
                        "name": "MaxPrice",
                        "value": "100.00"
                    },
                    {
                        "name": "FreeShippingOnly",
                        "value": "true"
                    }
                ],
                "page": 1,
                "items_per_page": 50,
                "global_id": "EBAY-US"
            }
        }


class ErrorResponse(BaseModel):
    """Model for API error responses."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    error_code: Optional[str] = Field(None, description="Error code")

    class Config:
        """Pydantic config for ErrorResponse model."""
        schema_extra = {
            "example": {
                "error": "Item not found",
                "detail": "The requested item could not be found",
                "error_code": "35"
            }
        }


# Dependency for getting eBay client instance
def get_ebay_client():
    """Dependency to get a configured eBay API client instance."""
    client = SyncEbayApiClient(
        app_id=settings.EBAY_APP_ID,
        cert_id=settings.EBAY_CERT_ID,
        dev_id=settings.EBAY_DEV_ID,
        redirect_uri=settings.EBAY_REDIRECT_URI,
        client_id=settings.EBAY_CLIENT_ID,
        client_secret=settings.EBAY_CLIENT_SECRET,
        use_sandbox=settings.EBAY_USE_SANDBOX,
        global_id=GlobalId.EBAY_US,
        timeout=settings.EBAY_REQUEST_TIMEOUT,
        retry_attempts=settings.EBAY_RETRY_ATTEMPTS,
        retry_backoff=settings.EBAY_RETRY_BACKOFF
    )
    try:
        yield client
    finally:
        client.close()


# API endpoints

@router.get(
    "/search",
    response_model=SearchResult,
    status_code=status.HTTP_200_OK,
    summary="Search for items on eBay",
    description="Search for items on eBay with various filters and pagination.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid request parameters"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def search_items(
    keywords: Optional[str] = Query(None, description="Search query string"),
    category_id: Optional[str] = Query(None, description="Category ID to filter by"),
    sort_order: SortOrder = Query(SortOrder.BEST_MATCH, description="Sort order for results"),
    min_price: Optional[float] = Query(None, description="Minimum price filter", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price filter", ge=0),
    free_shipping_only: Optional[bool] = Query(None, description="Filter for items with free shipping"),
    condition_id: Optional[ConditionId] = Query(None, description="Item condition filter"),
    page: int = Query(1, description="Page number", ge=1),
    items_per_page: int = Query(50, description="Items per page", ge=1, le=100),
    ebay_client: SyncEbayApiClient = Depends(get_ebay_client)
):
    """
    Search for items on eBay.
    
    Parameters can be used to filter and sort the results.
    """
    try:
        # Validate search criteria
        if not keywords and not category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either keywords or category_id must be provided"
            )
        
        # Validate min_price and max_price relationship if both are provided
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price"
            )
        
        # Build item filters
        item_filters = []
        
        if min_price is not None:
            item_filters.append({
                "name": "MinPrice",
                "value": str(min_price),
                "paramName": "Currency",
                "paramValue": "USD"
            })
            
        if max_price is not None:
            item_filters.append({
                "name": "MaxPrice",
                "value": str(max_price),
                "paramName": "Currency",
                "paramValue": "USD"
            })
            
        if free_shipping_only:
            item_filters.append({
                "name": "FreeShippingOnly",
                "value": "true"
            })
            
        if condition_id:
            item_filters.append({
                "name": "Condition",
                "value": str(int(condition_id.value if isinstance(condition_id, ConditionId) else condition_id))
            })
        
        # Make the search request
        results = ebay_client.search_items(
            keywords=keywords,
            category_id=category_id,
            sort_order=sort_order,
            item_filters=item_filters,
            page=page,
            items_per_page=items_per_page
        )
        
        return results
        
    except InvalidRequestError as e:
        logger.error(f"Invalid eBay search request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RateLimitError as e:
        logger.error(f"eBay rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.error(f"eBay authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except EbayApiError as e:
        logger.error(f"eBay API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/item/{item_id}",
    response_model=Item,
    status_code=status.HTTP_200_OK,
    summary="Get item details",
    description="Get detailed information about a specific item on eBay.",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Item not found"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_item_details(
    item_id: str = Path(..., description="eBay item ID to retrieve"),
    include_description: bool = Query(True, description="Whether to include the item description"),
    ebay_client: SyncEbayApiClient = Depends(get_ebay_client)
):
    """
    Get detailed information about a specific item on eBay.
    """
    try:
        item = ebay_client.get_item(item_id, include_description)
        return item
        
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found"
        )
    except RateLimitError as e:
        logger.error(f"eBay rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.error(f"eBay authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except EbayApiError as e:
        logger.error(f"eBay API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/categories",
    response_model=CategoryHierarchy,
    status_code=status.HTTP_200_OK,
    summary="Get eBay categories",
    description="Get a list of available categories on eBay.",
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_categories(
    parent_id: Optional[str] = Query(None, description="Parent category ID to start from"),
    ebay_client: SyncEbayApiClient = Depends(get_ebay_client)
):
    """
    Get a list of available categories on eBay.
    
    Optionally filter by parent category ID.
    """
    try:
        categories = ebay_client.get_categories(parent_id)
        return categories
        
    except RateLimitError as e:
        logger.error(f"eBay rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.error(f"eBay authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except EbayApiError as e:
        logger.error(f"eBay API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/search/advanced",
    response_model=SearchResult,
    status_code=status.HTTP_200_OK,
    summary="Advanced search for items on eBay",
    description="Advanced search for items on eBay with complex filters and options.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid request parameters"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def advanced_search(
    request: SearchRequest,
    ebay_client: SyncEbayApiClient = Depends(get_ebay_client)
):
    """
    Advanced search for items on eBay.
    
    This endpoint allows for more complex search criteria using a request body.
    """
    try:
        # Validate search criteria
        if not request.keywords and not request.category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either keywords or category_id must be provided"
            )
        
        # Convert item filters to the format expected by the eBay API
        item_filters = []
        if request.item_filters:
            for filter_req in request.item_filters:
                filter_dict = {
                    "name": filter_req.name,
                    "value": filter_req.value
                }
                if filter_req.paramName and filter_req.paramValue:
                    filter_dict["paramName"] = filter_req.paramName
                    filter_dict["paramValue"] = filter_req.paramValue
                item_filters.append(filter_dict)
        
        # Make the search request
        results = ebay_client.search_items(
            keywords=request.keywords,
            category_id=request.category_id,
            sort_order=request.sort_order,
            item_filters=item_filters,
            page=request.page,
            items_per_page=request.items_per_page
        )
        
        return results
        
    except InvalidRequestError as e:
        logger.error(f"Invalid eBay search request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RateLimitError as e:
        logger.error(f"eBay rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.error(f"eBay authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except EbayApiError as e:
        logger.error(f"eBay API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

