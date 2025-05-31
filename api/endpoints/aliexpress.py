"""
AliExpress API endpoints.

This module provides RESTful API endpoints for interacting with AliExpress,
allowing clients to search for products, get product details, and browse categories
with support for multiple languages, currencies, and regions.
"""

import logging
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query, Path, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl, validator, root_validator

from cloudstore.core.config import settings
from crawlers.aliexpress.crawler import (
    SyncAliExpressCrawler, AliExpressError, RateLimitError, 
    ItemNotFoundError, AntiScrapingError, RegionBlockedError, ParserError
)
from crawlers.aliexpress.constants import (
    SortOption, ShippingOption, Language, Currency, FilterOption,
    ERROR_MESSAGES, SUPPORTED_REGIONS
)
from crawlers.aliexpress.models import (
    BasicProduct, DetailedProduct, SearchResult, SearchFilters, 
    SearchPagination, Category, CategoryTree, Money, Price, SellerInfo
)

# Configure logger
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(
    prefix="/aliexpress",
    tags=["aliexpress"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        status.HTTP_403_FORBIDDEN: {"description": "Region blocked or anti-bot measures detected"},
    },
)

# Pydantic models for request/response validation

class SearchRequest(BaseModel):
    """Model for search request parameters."""
    query: Optional[str] = Field(None, description="Search query string")
    category_id: Optional[str] = Field(None, description="Category ID to search in")
    sort_by: SortOption = Field(SortOption.BEST_MATCH, description="Sort order for results")
    min_price: Optional[Decimal] = Field(None, description="Minimum price filter", ge=0)
    max_price: Optional[Decimal] = Field(None, description="Maximum price filter", ge=0)
    free_shipping: Optional[bool] = Field(None, description="Filter for free shipping")
    min_rating: Optional[float] = Field(None, description="Minimum rating (1-5)", ge=1, le=5)
    ship_from: Optional[str] = Field(None, description="Ship from country")
    ship_to: Optional[str] = Field(None, description="Ship to country")
    page: int = Field(1, description="Page number", ge=1)
    items_per_page: int = Field(60, description="Items per page", ge=1, le=100)
    language: Language = Field(Language.ENGLISH, description="Language for results")
    currency: Currency = Field(Currency.USD, description="Currency for prices")
    use_mobile: bool = Field(False, description="Whether to use mobile site")
    use_api: bool = Field(False, description="Whether to use API instead of HTML scraping")
    
    @validator('query', 'category_id')
    def validate_search_criteria(cls, v, values):
        """Validate that either query or category_id is provided."""
        if not v and 'query' in values and not values['query'] and 'category_id' in values and not values['category_id']:
            raise ValueError("Either query or category_id must be provided")
        return v
    
    @validator('min_price', 'max_price')
    def validate_price(cls, v):
        """Validate price is positive."""
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v
    
    @root_validator
    def validate_price_range(cls, values):
        """Validate min_price and max_price relationship."""
        min_price = values.get('min_price')
        max_price = values.get('max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price cannot be greater than max_price")
        return values

    class Config:
        """Pydantic config for SearchRequest model."""
        schema_extra = {
            "example": {
                "query": "smart watch",
                "category_id": "509",
                "sort_by": "orders",
                "min_price": 10.00,
                "max_price": 50.00,
                "free_shipping": True,
                "min_rating": 4.0,
                "ship_from": "CN",
                "ship_to": "US",
                "page": 1,
                "items_per_page": 60,
                "language": "en_US",
                "currency": "USD",
                "use_mobile": False,
                "use_api": False
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
                "error": "Product not found",
                "detail": "The requested product could not be found",
                "error_code": "ITEM_NOT_FOUND"
            }
        }


# Dependency for getting AliExpress crawler instance
def get_aliexpress_crawler(
    language: Language = Language.ENGLISH,
    currency: Currency = Currency.USD,
    country: str = "US",
    use_mobile: bool = False
):
    """
    Dependency to get a configured AliExpress crawler instance.
    
    Args:
        language: Language for results
        currency: Currency for prices
        country: Country code for shipping
        use_mobile: Whether to use mobile site
    
    Returns:
        Configured SyncAliExpressCrawler instance
    """
    crawler = SyncAliExpressCrawler(
        language=language,
        currency=currency,
        country=country,
        proxies=settings.ALIEXPRESS_PROXIES if settings.ALIEXPRESS_PROXY_ENABLED else None,
        use_mobile=use_mobile,
        rate_limit=settings.ALIEXPRESS_RATE_LIMIT,
        timeout=settings.ALIEXPRESS_REQUEST_TIMEOUT,
        retry_attempts=settings.ALIEXPRESS_RETRY_ATTEMPTS,
        retry_backoff=settings.ALIEXPRESS_RETRY_BACKOFF,
        random_delay=settings.ALIEXPRESS_RANDOM_DELAY,
    )
    
    try:
        yield crawler
    finally:
        crawler.close()


# API endpoints

@router.get(
    "/search",
    response_model=SearchResult,
    status_code=status.HTTP_200_OK,
    summary="Search for products on AliExpress",
    description="Search for products on AliExpress with various filters and pagination.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid request parameters"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Region blocked or anti-bot measures detected"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def search_products(
    query: Optional[str] = Query(None, description="Search query string"),
    category_id: Optional[str] = Query(None, description="Category ID to search in"),
    sort_by: SortOption = Query(SortOption.BEST_MATCH, description="Sort order for results"),
    min_price: Optional[float] = Query(None, description="Minimum price filter", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price filter", ge=0),
    free_shipping: Optional[bool] = Query(None, description="Filter for free shipping"),
    min_rating: Optional[float] = Query(None, description="Minimum rating (1-5)", ge=1, le=5),
    ship_from: Optional[str] = Query(None, description="Ship from country"),
    ship_to: Optional[str] = Query(None, description="Ship to country"),
    page: int = Query(1, description="Page number", ge=1),
    items_per_page: int = Query(60, description="Items per page", ge=1, le=100),
    language: Language = Query(Language.ENGLISH, description="Language for results"),
    currency: Currency = Query(Currency.USD, description="Currency for prices"),
    country: str = Query("US", description="Country code for shipping"),
    use_mobile: bool = Query(False, description="Whether to use mobile site"),
    use_api: bool = Query(False, description="Whether to use API instead of HTML scraping"),
    aliexpress_crawler: SyncAliExpressCrawler = Depends(get_aliexpress_crawler)
):
    """
    Search for products on AliExpress.
    
    Parameters can be used to filter and sort the results, and specify language,
    currency, and region preferences.
    """
    try:
        # Validate search criteria
        if not query and not category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either query or category_id must be provided"
            )
        
        # Validate min_price and max_price relationship if both are provided
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price"
            )
        
        # Create filters object
        filters = SearchFilters(
            min_price=Decimal(str(min_price)) if min_price is not None else None,
            max_price=Decimal(str(max_price)) if max_price is not None else None,
            free_shipping=free_shipping,
            min_rating=min_rating,
            ship_from=ship_from,
            ship_to=ship_to
        )
        
        # Make the search request
        results = aliexpress_crawler.search_products(
            query=query,
            category_id=category_id,
            filters=filters,
            sort=sort_by,
            page=page,
            items_per_page=items_per_page,
            use_api=use_api
        )
        
        return results
        
    except ValueError as e:
        logger.error(f"Invalid AliExpress search request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RateLimitError as e:
        logger.error(f"AliExpress rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except RegionBlockedError as e:
        logger.error(f"AliExpress region blocked: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AntiScrapingError as e:
        logger.error(f"AliExpress anti-bot measures detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AliExpressError as e:
        logger.error(f"AliExpress API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/search",
    response_model=SearchResult,
    status_code=status.HTTP_200_OK,
    summary="Advanced search for products",
    description="Advanced search for products on AliExpress with complex parameters.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid request parameters"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Region blocked or anti-bot measures detected"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def advanced_search(
    request: SearchRequest = Body(..., description="Search request parameters"),
    aliexpress_crawler: SyncAliExpressCrawler = Depends(
        lambda: next(get_aliexpress_crawler(
            language=request.language,
            currency=request.currency,
            country=request.ship_to or "US",
            use_mobile=request.use_mobile
        ))
    )
):
    """
    Advanced search for products on AliExpress.
    
    This endpoint allows for more complex search criteria using a request body.
    """
    try:
        # Create filters object
        filters = SearchFilters(
            min_price=request.min_price,
            max_price=request.max_price,
            free_shipping=request.free_shipping,
            min_rating=request.min_rating,
            ship_from=request.ship_from,
            ship_to=request.ship_to
        )
        
        # Make the search request
        results = aliexpress_crawler.search_products(
            query=request.query,
            category_id=request.category_id,
            filters=filters,
            sort=request.sort_by,
            page=request.page,
            items_per_page=request.items_per_page,
            use_api=request.use_api
        )
        
        return results
        
    except ValueError as e:
        logger.error(f"Invalid AliExpress search request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RateLimitError as e:
        logger.error(f"AliExpress rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except RegionBlockedError as e:
        logger.error(f"AliExpress region blocked: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AntiScrapingError as e:
        logger.error(f"AliExpress anti-bot measures detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AliExpressError as e:
        logger.error(f"AliExpress API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/product/{product_id}",
    response_model=DetailedProduct,
    status_code=status.HTTP_200_OK,
    summary="Get product details",
    description="Get detailed information about a specific product on AliExpress.",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Product not found"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Region blocked or anti-bot measures detected"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_product_details(
    product_id: str = Path(..., description="AliExpress product ID"),
    language: Language = Query(Language.ENGLISH, description="Language for results"),
    currency: Currency = Query(Currency.USD, description="Currency for prices"),
    country: str = Query("US", description="Country code for shipping"),
    use_mobile: bool = Query(False, description="Whether to use mobile site"),
    use_graphql: bool = Query(False, description="Whether to use GraphQL API"),
    aliexpress_crawler: SyncAliExpressCrawler = Depends(get_aliexpress_crawler)
):
    """
    Get detailed information about a specific product on AliExpress.
    
    Parameters allow specifying language, currency, and region preferences.
    """
    try:
        product = aliexpress_crawler.get_product_details(
            product_id=product_id,
            use_graphql=use_graphql
        )
        return product
        
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    except RateLimitError as e:
        logger.error(f"AliExpress rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except RegionBlockedError as e:
        logger.error(f"AliExpress region blocked: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AntiScrapingError as e:
        logger.error(f"AliExpress anti-bot measures detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AliExpressError as e:
        logger.error(f"AliExpress API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/categories",
    response_model=List[Category],
    status_code=status.HTTP_200_OK,
    summary="Get AliExpress categories",
    description="Get a list of available categories on AliExpress.",
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Region blocked or anti-bot measures detected"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_categories(
    parent_id: Optional[str] = Query(None, description="Parent category ID to get subcategories"),
    language: Language = Query(Language.ENGLISH, description="Language for results"),
    use_mobile: bool = Query(False, description="Whether to use mobile site"),
    aliexpress_crawler: SyncAliExpressCrawler = Depends(get_aliexpress_crawler)
):
    """
    Get a list of available categories on AliExpress.
    
    Optionally filter by parent category ID.
    """
    try:
        categories = aliexpress_crawler.get_categories(parent_id)
        return categories
        
    except RateLimitError as e:
        logger.error(f"AliExpress rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except RegionBlockedError as e:
        logger.error(f"AliExpress region blocked: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AntiScrapingError as e:
        logger.error(f"AliExpress anti-bot measures detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AliExpressError as e:
        logger.error(f"AliExpress API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/category-tree",
    response_model=CategoryTree,
    status_code=status.HTTP_200_OK,
    summary="Get category tree",
    description="Get the full category tree from AliExpress.",
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Region blocked or anti-bot measures detected"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
def get_category_tree(
    language: Language = Query(Language.ENGLISH, description="Language for results"),
    use_mobile: bool = Query(False, description="Whether to use mobile site"),
    aliexpress_crawler: SyncAliExpressCrawler = Depends(get_aliexpress_crawler)
):
    """
    Get the full category tree from AliExpress.
    """
    try:
        category_tree = aliexpress_crawler.get_category_tree()
        return category_tree
        
    except RateLimitError as e:
        logger.error(f"AliExpress rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except RegionBlockedError as e:
        logger.error(f"AliExpress region blocked: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AntiScrapingError as e:
        logger.error(f"AliExpress anti-bot measures detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AliExpressError as e:
        logger.error(f"AliExpress API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/languages",
    response_model=List[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Get supported languages",
    description="Get a list of languages supported by the AliExpress API."
)
def get_supported_languages():
    """
    Get a list of languages supported by the AliExpress API.
    """
    return [
        {"code": lang.value, "name": lang.name.replace("_", " ").title()}
        for lang in Language
    ]


@router.get(
    "/currencies",
    response_model=List[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Get supported currencies",
    description="Get a list of currencies supported by the AliExpress API."
)
def get_supported_currencies():
    """
    Get a list of currencies supported by the AliExpress API.
    """
    return [
        {"code": currency.value, "name": currency.name}
        for currency in Currency
    ]


@router.get(
    "/regions",
    response_model=List[str],
    status_code=status.HTTP_200_OK,
    summary="Get supported regions",
    description="Get a list of regions supported by the AliExpress API."
)
def get_supported_regions():
    """
    Get a list of regions supported by the AliExpress API.
    """
    return SUPPORTED_REGIONS
