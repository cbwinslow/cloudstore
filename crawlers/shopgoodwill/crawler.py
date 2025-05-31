"""
ShopGoodwill crawler implementation.

This module provides the crawler functionality for fetching data from ShopGoodwill.com,
implementing rate limiting, retry logic, and proxy support.
"""

import logging
import time
import asyncio
import random
from typing import Dict, List, Optional, Any, Union, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
import functools

import aiohttp
import backoff
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .parser import ProductListingParser, ItemDetailParser, CategoryParser, ParsingError
from .constants import (
    BASE_URL, SEARCH_URL, ITEM_URL, CATEGORIES_URL,
    RATE_LIMIT, RATE_LIMIT_BURST, RETRY_ATTEMPTS, RETRY_BACKOFF, REQUEST_TIMEOUT,
    DEFAULT_HEADERS, ERROR_MESSAGES, SortOptions, ConditionOptions
)

# Configure logger
logger = logging.getLogger(__name__)

# Custom exceptions
class ShopGoodwillError(Exception):
    """Base exception for ShopGoodwill crawler errors."""
    pass

class ConnectionError(ShopGoodwillError):
    """Exception raised when connection to ShopGoodwill fails."""
    pass

class TimeoutError(ShopGoodwillError):
    """Exception raised when request to ShopGoodwill times out."""
    pass

class RateLimitError(ShopGoodwillError):
    """Exception raised when rate limit is exceeded."""
    pass

class ItemNotFoundError(ShopGoodwillError):
    """Exception raised when an item is not found."""
    pass


class RateLimiter:
    """Rate limiter implementation using token bucket algorithm."""
    
    def __init__(self, rate_limit: int = RATE_LIMIT, burst_limit: int = RATE_LIMIT_BURST):
        """
        Initialize rate limiter.
        
        Args:
            rate_limit: Number of requests allowed per minute
            burst_limit: Number of additional burst requests allowed
        """
        self.rate_limit = rate_limit
        self.burst_limit = burst_limit
        self.tokens = burst_limit  # Start with full burst capacity
        self.last_refill = time.time()
    
    def _refill_tokens(self):
        """Refill tokens based on time elapsed since last refill."""
        now = time.time()
        elapsed = now - self.last_refill
        # Convert rate_limit from per minute to per second
        rate_per_second = self.rate_limit / 60
        # Calculate how many new tokens to add
        new_tokens = elapsed * rate_per_second
        
        if new_tokens > 0:
            self.tokens = min(self.tokens + new_tokens, self.burst_limit)
            self.last_refill = now
    
    async def acquire(self):
        """
        Acquire a token for making a request.
        
        Raises:
            RateLimitError: If no tokens are available
        """
        self._refill_tokens()
        
        if self.tokens < 1:
            # Calculate how long to wait until a token becomes available
            wait_time = (1 - self.tokens) / (self.rate_limit / 60)
            logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
            raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_ERROR"])
        
        self.tokens -= 1
        return True


class ShopGoodwillCrawler:
    """Crawler for ShopGoodwill.com."""
    
    def __init__(
        self,
        use_proxy: bool = False,
        proxy_provider: Optional[str] = None,
        rate_limit: int = RATE_LIMIT,
        burst_limit: int = RATE_LIMIT_BURST,
        timeout: int = REQUEST_TIMEOUT,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff: float = RETRY_BACKOFF
    ):
        """
        Initialize ShopGoodwill crawler.
        
        Args:
            use_proxy: Whether to use proxies
            proxy_provider: Name of proxy provider to use
            rate_limit: Number of requests allowed per minute
            burst_limit: Number of additional burst requests allowed
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_backoff: Exponential backoff multiplier
        """
        self.use_proxy = use_proxy
        self.proxy_provider = proxy_provider
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.rate_limiter = RateLimiter(rate_limit, burst_limit)
        self.session = None
        
        logger.info(f"Initialized ShopGoodwill crawler (use_proxy={use_proxy}, rate_limit={rate_limit}/min)")
    
    async def _init_session(self):
        """Initialize aiohttp session if not already created."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
    
    async def _close_session(self):
        """Close aiohttp session if open."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
    
    def _get_proxy(self) -> Optional[str]:
        """
        Get a proxy URL to use for requests.
        
        Returns:
            Proxy URL or None if proxies are disabled
        """
        if not self.use_proxy:
            return None
            
        # In a real implementation, this would get a proxy from a pool
        # For now, we'll just return None (no proxy)
        logger.debug("Proxy support not fully implemented yet")
        return None
    
    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_BACKOFF, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def _make_request(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> str:
        """
        Make HTTP request to ShopGoodwill.com with rate limiting and retries.
        
        Args:
            url: URL to request
            method: HTTP method (GET, POST)
            params: URL parameters
            
        Returns:
            Response text
            
        Raises:
            ConnectionError: If connection to ShopGoodwill fails
            TimeoutError: If request times out
            RateLimitError: If rate limit is exceeded
        """
        # Apply rate limiting
        try:
            await self.rate_limiter.acquire()
        except RateLimitError as e:
            # Wait a bit before retrying
            await asyncio.sleep(random.uniform(1, 3))
            await self.rate_limiter.acquire()  # Try again
        
        # Initialize session if needed
        await self._init_session()
        
        # Get proxy if enabled
        proxy = self._get_proxy()
        
        # Build URL with params if provided
        if params:
            # Parse the URL
            parsed_url = urlparse(url)
            # Parse existing query parameters
            query_dict = parse_qs(parsed_url.query)
            # Add new parameters
            query_dict.update({k: [v] if not isinstance(v, list) else v for k, v in params.items()})
            # Build new query string
            query_string = urlencode(query_dict, doseq=True)
            # Rebuild URL
            url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                query_string,
                parsed_url.fragment
            ))
        
        try:
            start_time = time.time()
            
            logger.debug(f"Making {method} request to {url}")
            
            if method.upper() == "GET":
                async with self.session.get(url, proxy=proxy, timeout=self.timeout) as response:
                    response.raise_for_status()
                    html = await response.text()
            elif method.upper() == "POST":
                async with self.session.post(url, proxy=proxy, timeout=self.timeout) as response:
                    response.raise_for_status()
                    html = await response.text()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            elapsed = time.time() - start_time
            logger.debug(f"Request completed in {elapsed:.2f}s")
            
            return html
            
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(ERROR_MESSAGES["CONNECTION_ERROR"]) from e
        except asyncio.TimeoutError as e:
            logger.error(f"Request timed out: {e}")
            raise TimeoutError(ERROR_MESSAGES["TIMEOUT_ERROR"]) from e
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                logger.error(f"Rate limit exceeded: {e}")
                raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_ERROR"]) from e
            elif e.status == 404:
                logger.error(f"Item not found: {e}")
                raise ItemNotFoundError(ERROR_MESSAGES["ITEM_NOT_FOUND"]) from e
            else:
                logger.error(f"HTTP error {e.status}: {e}")
                raise ConnectionError(f"HTTP error {e.status}") from e
    
    async def search(
        self,
        query: str = "",
        category_id: Optional[str] = None,
        sort_by: SortOptions = SortOptions.ENDING_SOON,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: Optional[ConditionOptions] = None,
        page: int = 1,
        items_per_page: int = 40
    ) -> Dict[str, Any]:
        """
        Search for items on ShopGoodwill.com.
        
        Args:
            query: Search query
            category_id: Category ID to filter by
            sort_by: Sort order
            min_price: Minimum price filter
            max_price: Maximum price filter
            condition: Item condition filter
            page: Page number
            items_per_page: Number of items per page
            
        Returns:
            Dictionary with search results
        """
        # Build search parameters
        params = {
            "searchQuery": query if query else "",
            "page": page,
            "itemsPerPage": items_per_page,
            "sortBy": sort_by.value if isinstance(sort_by, SortOptions) else sort_by
        }
        
        # Add optional filters
        if category_id:
            params["categoryId"] = category_id
        if min_price is not None:
            params["minPrice"] = min_price
        if max_price is not None:
            params["maxPrice"] = max_price
        if condition:
            params["condition"] = condition.value if isinstance(condition, ConditionOptions) else condition
        
        logger.info(f"Searching ShopGoodwill with params: {params}")
        
        try:
            html = await self._make_request(SEARCH_URL, params=params)
            parser = ProductListingParser(html)
            products = parser.parse_listings()
            total_pages = parser.get_total_pages()
            
            return {
                "items": products,
                "page": page,
                "total_pages": total_pages,
                "items_per_page": items_per_page,
                "total_items": len(products) if page == total_pages else total_pages * items_per_page,
                "query": query
            }
            
        except ParsingError as e:
            logger.error(f"Failed to parse search results: {e}")
            raise
        except (ConnectionError, TimeoutError, RateLimitError) as e:
            logger.error(f"Search request failed: {e}")
            raise
    
    async def get_item(self, item_id: str) -> Dict[str, Any]:
        """
        Get details of a specific item.
        
        Args:
            item_id: ID of the item
            
        Returns:
            Dictionary with item details
        """
        url = f"{ITEM_URL}{item_id}"
        logger.info(f"Getting item details for ID: {item_id}")
        
        try:
            html = await self._make_request(url)
            parser = ItemDetailParser(html)
            item = parser.parse_item()
            
            return item
            
        except ParsingError as e:
            logger.error(f"Failed to parse item details: {e}")
            raise
        except ItemNotFoundError:
            logger.error(f"Item not found: {item_id}")
            raise
        except (ConnectionError, TimeoutError, RateLimitError) as e:
            logger.error(f"Item request failed: {e}")
            raise
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get list of categories from ShopGoodwill.com.
        
        Returns:
            List of category dictionaries
        """
        logger.info("Getting categories from ShopGoodwill")
        
        try:
            html = await self._make_request(CATEGORIES_URL)
            parser = CategoryParser(html)
            categories = parser.parse_categories()
            
            return categories
            
        except ParsingError as e:
            logger.error(f"Failed to parse categories: {e}")
            raise
        except (ConnectionError, TimeoutError, RateLimitError) as e:
            logger.error(f"Categories request failed: {e}")
            raise
    
    async def search_by_category(
        self,
        category_id: str,
        sort_by: SortOptions = SortOptions.ENDING_SOON,
        page: int = 1,
        items_per_page: int = 40
    ) -> Dict[str, Any]:
        """
        Search for items in a specific category.
        
        Args:
            category_id: Category ID
            sort_by: Sort order
            page: Page number
            items_per_page: Number of items per page
            
        Returns:
            Dictionary with search results
        """
        return await self.search(
            category_id=category_id,
            sort_by=sort_by,
            page=page,
            items_per_page=items_per_page
        )
    
    async def search_multiple_pages(
        self,
        query: str = "",
        category_id: Optional[str] = None,
        sort_by: SortOptions = SortOptions.ENDING_SOON,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: Optional[ConditionOptions] = None,
        max_pages: int = 3,
        items_per_page: int = 40
    ) -> Dict[str, Any]:
        """
        Search for items across multiple pages.
        
        Args:
            query: Search query
            category_id: Category ID to filter by
            sort_by: Sort order
            min_price: Minimum price filter
            max_price: Maximum price filter
            condition: Item condition filter
            max_pages: Maximum number of pages to fetch
            items_per_page: Number of items per page
            
        Returns:
            Dictionary with combined search results
        """
        logger.info(f"Searching multiple pages (max={max_pages}) with query: {query}")
        
        all_items = []
        total_pages = 1
        
        # Get first page to determine total pages
        first_page = await self.search(
            query=query,
            category_id=category_id,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            page=1,
            items_per_page=items_per_page
        )
        
        all_items.extend(first_page["items"])
        total_pages = min(first_page["total_pages"], max_pages)
        
        # Get remaining pages
        for page in range(2, total_pages + 1):
            try:
                page_results = await self.search(
                    query=query,
                    category_id=category_id,
                    sort_by=sort_by,
                    min_price=min_price,
                    max_price=max_price,
                    condition=condition,
                    page=page,
                    items_per_page=items_per_page
                )
                all_items.extend(page_results["items"])
                
                # Small delay between pages to be nice to the server
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        return {
            "items": all_items,
            "total_pages": total_pages,
            "items_per_page": items_per_page,
            "total_items": len(all_items),
            "query": query
        }


# Synchronous wrapper for convenience
class SyncShopGoodwillCrawler:
    """Synchronous wrapper for ShopGoodwillCrawler."""
    
    def __init__(
        self,
        use_proxy: bool = False,
        proxy_provider: Optional[str] = None,
        rate_limit: int = RATE_LIMIT,
        burst_limit: int = RATE_LIMIT_BURST,
        timeout: int = REQUEST_TIMEOUT,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff: float = RETRY_BACKOFF
    ):
        """Initialize with same parameters as async version."""
        self.crawler_params = {
            "use_proxy": use_proxy,
            "proxy_provider": proxy_provider,
            "rate_limit": rate_limit,
            "burst_limit": burst_limit,
            "timeout": timeout,
            "retry_attempts": retry_attempts,
            "retry_backoff": retry_backoff
        }
    
    def _run_async(self, coro):
        """Run coroutine in event loop."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._run_with_crawler(coro))
    
    async def _run_with_crawler(self, coro):
        """Run coroutine with crawler context manager."""
        async with ShopGoodwillCrawler(**self.crawler_params) as crawler:
            return await coro(crawler)
    
    def search(self, **kwargs):
        """Synchronous version of search."""
        return self._run_async(lambda crawler: crawler.search(**kwargs))
    
    def get_item(self, item_id: str):
        """Synchronous version of get_item."""
        return self._run_async(lambda crawler: crawler.get_item(item_id))
    
    def get_categories(self):
        """Synchronous version of get_categories."""
        return self._run_async(lambda crawler: crawler.get_categories())
    
    def search_by_category(self, **kwargs):
        """Synchronous version of search_by_category."""
        return self._run_async(lambda crawler: crawler.search_by_category(**kwargs))
    
    def search_multiple_pages(self, **kwargs):
        """Synchronous version of search_multiple_pages."""
        return self._run_async(lambda crawler: crawler.search_multiple_pages(**kwargs))

