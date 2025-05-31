"""
AliExpress Crawler for fetching product listings, details, and categories.

This module provides functionality for crawling AliExpress website, handling
rate limiting, retries, proxies, and anti-bot detection.
"""

import asyncio
import json
import logging
import random
import re
import time
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urlencode, quote_plus, urlparse, parse_qs

import aiohttp
import backoff
from fake_useragent import UserAgent
from tenacity import (
    retry, stop_after_attempt, wait_exponential, 
    retry_if_exception_type, RetryError
)

from .parser import (
    ProductListingParser, ItemDetailParser, CategoryParser, 
    AntiBot, ParsingError
)
from .constants import (
    BASE_URL, MOBILE_BASE_URL, SEARCH_URL, CATEGORY_URL, PRODUCT_URL_PATTERN,
    API_SEARCH_URL, API_PRODUCT_URL, GRAPHQL_URL,
    DEFAULT_HEADERS, MOBILE_HEADERS, DEFAULT_COOKIES,
    RATE_LIMIT, RETRY_ATTEMPTS, RETRY_BACKOFF, REQUEST_TIMEOUT, DELAY_BETWEEN_REQUESTS,
    RANDOM_DELAY_RANGE, DEFAULT_ITEMS_PER_PAGE, MAX_PAGES,
    SortOption, ShippingOption, Language, Currency, COMMON_CATEGORIES,
    ERROR_MESSAGES, PRODUCT_DETAIL_QUERY
)
from .models import (
    BasicProduct, DetailedProduct, SearchResult, SearchFilters, 
    SearchPagination, Category, CategoryTree
)

# Configure logger
logger = logging.getLogger(__name__)


class AliExpressError(Exception):
    """Base exception for AliExpress crawler errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        """Initialize with error message, code, and details."""
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ConnectionError(AliExpressError):
    """Exception for connection errors."""
    pass


class TimeoutError(AliExpressError):
    """Exception for timeout errors."""
    pass


class RateLimitError(AliExpressError):
    """Exception for rate limit exceeded errors."""
    pass


class ItemNotFoundError(AliExpressError):
    """Exception for item not found errors."""
    pass


class AntiScrapingError(AliExpressError):
    """Exception for anti-scraping detection."""
    pass


class RegionBlockedError(AliExpressError):
    """Exception for region blocking."""
    pass


class ParserError(AliExpressError):
    """Exception for parsing errors."""
    pass


class AliExpressRateLimiter:
    """Rate limiter implementation for AliExpress API."""
    
    def __init__(self, rate_limit: int = RATE_LIMIT, burst_limit: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            rate_limit: Number of requests allowed per minute
            burst_limit: Number of additional burst requests allowed
        """
        self.rate_limit = rate_limit
        self.burst_limit = burst_limit or rate_limit * 2
        self.tokens = self.burst_limit  # Start with full burst capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    def _refill_tokens(self):
        """Refill tokens based on time elapsed since last refill."""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.rate_limit / 60)  # Convert to tokens per second
        
        if new_tokens > 0:
            self.tokens = min(self.tokens + new_tokens, self.burst_limit)
            self.last_refill = now
    
    async def acquire(self, cost: int = 1):
        """
        Acquire a token for making a request.
        
        Args:
            cost: Cost of the request in tokens
            
        Raises:
            RateLimitError: If no tokens are available
        """
        async with self.lock:
            self._refill_tokens()
            
            if self.tokens < cost:
                # Calculate how long to wait until a token becomes available
                wait_time = (cost - self.tokens) / (self.rate_limit / 60)
                logger.warning(f"Rate limit reached. Would need to wait {wait_time:.2f} seconds")
                raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_ERROR"])
            
            self.tokens -= cost
            return True


class ProxyManager:
    """Manager for handling proxy rotation."""
    
    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize proxy manager.
        
        Args:
            proxies: List of proxy URLs (e.g., "http://user:pass@host:port")
        """
        self.proxies = proxies or []
        self.current_index = 0
        self.failed_proxies = set()
        self.lock = asyncio.Lock()
    
    async def get_proxy(self) -> Optional[str]:
        """
        Get next available proxy.
        
        Returns:
            Proxy URL or None if no proxies available
        """
        if not self.proxies:
            return None
        
        async with self.lock:
            # Skip failed proxies
            attempts = 0
            while attempts < len(self.proxies):
                proxy = self.proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.proxies)
                
                if proxy not in self.failed_proxies:
                    return proxy
                
                attempts += 1
            
            # If all proxies have failed, reset and try again
            if self.failed_proxies and attempts >= len(self.proxies):
                logger.warning("All proxies have failed, resetting failed list")
                self.failed_proxies.clear()
                return self.proxies[self.current_index]
            
            return None
    
    async def mark_proxy_failed(self, proxy: str):
        """
        Mark a proxy as failed.
        
        Args:
            proxy: Proxy URL that failed
        """
        if not proxy:
            return
        
        async with self.lock:
            self.failed_proxies.add(proxy)
            logger.warning(f"Marked proxy as failed: {proxy}")


class AliExpressCrawler:
    """Crawler for AliExpress website."""
    
    def __init__(
        self,
        language: Language = Language.ENGLISH,
        currency: Currency = Currency.USD,
        country: str = "US",
        proxies: Optional[List[str]] = None,
        use_mobile: bool = False,
        rate_limit: int = RATE_LIMIT,
        timeout: int = REQUEST_TIMEOUT,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff: float = RETRY_BACKOFF,
        random_delay: bool = True,
        cookies: Optional[Dict[str, str]] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize AliExpress crawler.
        
        Args:
            language: Language for results
            currency: Currency for prices
            country: Country code for shipping
            proxies: List of proxy URLs
            use_mobile: Whether to use mobile site
            rate_limit: Number of requests allowed per minute
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_backoff: Exponential backoff multiplier
            random_delay: Whether to add random delays between requests
            cookies: Custom cookies to use
            user_agent: Custom user agent string
        """
        self.language = language
        self.currency = currency
        self.country = country
        self.use_mobile = use_mobile
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.random_delay = random_delay
        
        # Set up rate limiter
        self.rate_limiter = AliExpressRateLimiter(rate_limit)
        
        # Set up proxy manager
        self.proxy_manager = ProxyManager(proxies)
        
        # Set up base URLs
        self.base_url = MOBILE_BASE_URL if use_mobile else BASE_URL
        
        # Set up headers
        self.headers = MOBILE_HEADERS.copy() if use_mobile else DEFAULT_HEADERS.copy()
        
        # Use custom or random user agent
        if user_agent:
            self.headers["User-Agent"] = user_agent
        else:
            try:
                ua = UserAgent()
                agent = ua.random if not use_mobile else ua.random_mobile
                self.headers["User-Agent"] = agent
            except:
                # If fake_useragent fails, keep the default
                pass
        
        # Set up cookies
        self.cookies = DEFAULT_COOKIES.copy()
        if cookies:
            self.cookies.update(cookies)
        
        # Add language, currency, and country cookies
        self.cookies.update({
            "aep_usuc_f": f"site=glo&c_tp={self.currency.value}&region={self.country}&b_locale={self.language.value}",
            "intl_locale": self.language.value,
            "xman_us_f": f"x_l=0&x_locale={self.language.value}",
        })
        
        # Session for API requests
        self.session = None
        
        logger.info(f"Initialized AliExpress crawler (mobile={use_mobile}, language={language.value}, currency={currency.value})")
    
    async def _init_session(self):
        """Initialize aiohttp session if not already created."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers, cookies=self.cookies)
    
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
    
    async def _add_delay(self):
        """Add delay between requests if random_delay is enabled."""
        if self.random_delay:
            delay = random.uniform(RANDOM_DELAY_RANGE[0], RANDOM_DELAY_RANGE[1])
            logger.debug(f"Adding random delay of {delay:.2f} seconds")
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
    
    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_BACKOFF, min=1, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        use_json: bool = False,
    ) -> Union[str, Dict[str, Any]]:
        """
        Make HTTP request to AliExpress with rate limiting and retries.
        
        Args:
            url: URL to request
            method: HTTP method (GET, POST)
            params: URL parameters
            data: Request data
            headers: Additional request headers
            proxy: Proxy URL to use
            use_json: Whether to parse response as JSON
            
        Returns:
            Response text or JSON
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If request times out
            RateLimitError: If rate limit is exceeded
            AntiScrapingError: If anti-scraping measures detected
            RegionBlockedError: If region is blocked
            AliExpressError: For other errors
        """
        # Apply rate limiting
        try:
            await self.rate_limiter.acquire()
        except RateLimitError as e:
            # Try to wait a bit and retry once
            logger.warning("Rate limit exceeded, waiting before retry")
            await asyncio.sleep(random.uniform(5, 10))
            try:
                await self.rate_limiter.acquire()
            except RateLimitError:
                # If still rate limited, raise the exception
                raise
        
        # Add delay between requests to be polite
        await self._add_delay()
        
        # Initialize session if needed
        await self._init_session()
        
        # Get proxy if not provided
        if not proxy and self.proxy_manager.proxies:
            proxy = await self.proxy_manager.get_proxy()
        
        # Prepare headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Prepare URL
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}{url}"
        
        logger.debug(f"Making {method} request to {url}")
        
        try:
            if method.upper() == "GET":
                async with self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    proxy=proxy,
                    timeout=self.timeout
                ) as response:
                    await self._handle_response_status(response)
                    if use_json:
                        return await response.json()
                    return await response.text()
                    
            elif method.upper() == "POST":
                # Convert data to JSON if needed
                if data and use_json and not isinstance(data, str):
                    request_data = json.dumps(data)
                    request_headers["Content-Type"] = "application/json"
                else:
                    request_data = data
                
                async with self.session.post(
                    url,
                    params=params,
                    data=request_data,
                    headers=request_headers,
                    proxy=proxy,
                    timeout=self.timeout
                ) as response:
                    await self._handle_response_status(response)
                    if use_json:
                        return await response.json()
                    return await response.text()
            
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientResponseError as e:
            # Mark proxy as failed if used
            if proxy:
                await self.proxy_manager.mark_proxy_failed(proxy)
            
            # Handle response errors
            if e.status == 403:
                logger.error(f"Access forbidden (403): {e}")
                raise RegionBlockedError(ERROR_MESSAGES["REGION_BLOCKED"], str(e.status), {"url": url})
            elif e.status == 429:
                logger.error(f"Rate limit exceeded (429): {e}")
                raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_ERROR"], str(e.status), {"url": url})
            elif e.status == 404:
                logger.error(f"Resource not found (404): {e}")
                raise ItemNotFoundError(ERROR_MESSAGES["ITEM_NOT_FOUND"], str(e.status), {"url": url})
            else:
                logger.error(f"HTTP error {e.status}: {e}")
                raise AliExpressError(f"HTTP error {e.status}", str(e.status), {"url": url})
                
        except aiohttp.ClientConnectionError as e:
            # Mark proxy as failed if used
            if proxy:
                await self.proxy_manager.mark_proxy_failed(proxy)
                
            logger.error(f"Connection error: {e}")
            raise ConnectionError(ERROR_MESSAGES["CONNECTION_ERROR"], None, {"url": url, "error": str(e)})
            
        except asyncio.TimeoutError as e:
            # Mark proxy as failed if used
            if proxy:
                await self.proxy_manager.mark_proxy_failed(proxy)
                
            logger.error(f"Request timed out: {e}")
            raise TimeoutError(ERROR_MESSAGES["TIMEOUT_ERROR"], None, {"url": url, "error": str(e)})
    
    async def _handle_response_status(self, response: aiohttp.ClientResponse):
        """
        Handle response status codes and raise appropriate exceptions.
        
        Args:
            response: aiohttp response object
            
        Raises:
            RegionBlockedError: If region is blocked
            RateLimitError: If rate limit is exceeded
            ItemNotFoundError: If item is not found
            AliExpressError: For other AliExpress errors
        """
        # Raise for HTTP status errors
        response.raise_for_status()
    
    async def search_products(
        self,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
        filters: Optional[SearchFilters] = None,
        sort: SortOption = SortOption.BEST_MATCH,
        page: int = 1,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        use_api: bool = False,
    ) -> SearchResult:
        """
        Search for products on AliExpress.
        
        Args:
            query: Search query
            category_id: Category ID to search in
            filters: Search filters
            sort: Sort order
            page: Page number
            items_per_page: Items per page
            use_api: Whether to use API instead of HTML scraping
            
        Returns:
            SearchResult object with search results
            
        Raises:
            AliExpressError: If search fails
        """
        if not query and not category_id:
            raise ValueError("Either query or category_id must be provided")
        
        logger.info(f"Searching AliExpress for: query='{query}', category={category_id}, page={page}")
        
        try:
            if use_api:
                return await self._search_api(query, category_id, filters, sort, page, items_per_page)
            else:
                return await self._search_html(query, category_id, filters, sort, page, items_per_page)
        except (AntiBot, AntiScrapingError) as e:
            logger.warning(f"Anti-bot measures detected, switching to mobile site: {e}")
            # Try mobile site if anti-bot measures detected
            original_mobile = self.use_mobile
            try:
                self.use_mobile = True
                result = await self._search_html(query, category_id, filters, sort, page, items_per_page)
                return result
            finally:
                self.use_mobile = original_mobile
    
    async def _search_html(
        self,
        query: Optional[str],
        category_id: Optional[str],
        filters: Optional[SearchFilters],
        sort: SortOption,
        page: int,
        items_per_page: int,
    ) -> SearchResult:
        """
        Search for products using HTML scraping.
        
        Args:
            query: Search query
            category_id: Category ID to search in
            filters: Search filters
            sort: Sort order
            page: Page number
            items_per_page: Items per page
            
        Returns:
            SearchResult object with search results
            
        Raises:
            AliExpressError: If search fails
        """
        # Build search URL
        params = {
            "SearchText": query if query else "",
            "page": page,
            "SortType": sort.value if isinstance(sort, SortOption) else sort,
            "g": "y",  # Ship to flag
            "CatId": category_id if category_id else "0",
            "initiative_id": "SB_20220713063900",
            "dida": "y",
        }
        
        # Add filters if provided
        if filters:
            if filters.min_price is not None:
                params["minPrice"] = str(filters.min_price)
            if filters.max_price is not None:
                params["maxPrice"] = str(filters.max_price)
            if filters.free_shipping:
                params["isFreeShip"] = "y"
            if filters.ship_from:
                params["shipFromCountry"] = filters.ship_from
            if filters.min_rating:
                params["feedback"] = f"{int(filters.min_rating)}f"
        
        # Choose base URL based on whether searching by query or category
        base_search_url = CATEGORY_URL if category_id and not query else SEARCH_URL
        
        # Construct search URL
        if self.use_mobile:
            url = f"{MOBILE_BASE_URL}/wholesale"
        else:
            url = base_search_url
        
        try:
            # Make the request
            html = await self._make_request(url, params=params)
            
            # Parse the results
            parser = ProductListingParser(html, is_mobile=self.use_mobile)
            search_result = parser.parse_listings()
            
            # Add query and filters to result
            search_result.query = query
            search_result.filters = filters
            search_result.category_id = category_id
            search_result.sort_by = sort.value if isinstance(sort, SortOption) else sort
            
            logger.info(f"Found {len(search_result.products)} products (page {search_result.pagination.page}/{search_result.pagination.total_pages})")
            return search_result
            
        except AntiBot as e:
            logger.error(f"Anti-bot measures detected: {e}")
            raise AntiScrapingError(ERROR_MESSAGES["CAPTCHA_DETECTED"], None, {"query": query, "category_id": category_id})
            
        except ParsingError as e:
            logger.error(f"Failed to parse search results: {e}")
            raise ParserError(ERROR_MESSAGES["PARSING_ERROR"], None, {"query": query, "category_id": category_id})
    
    async def _search_api(
        self,
        query: Optional[str],
        category_id: Optional[str],
        filters: Optional[SearchFilters],
        sort: SortOption,
        page: int,
        items_per_page: int,
    ) -> SearchResult:
        """
        Search for products using AliExpress API.
        
        Args:
            query: Search query
            category_id: Category ID to search in
            filters: Search filters
            sort: Sort order
            page: Page number
            items_per_page: Items per page
            
        Returns:
            SearchResult object with search results
            
        Raises:
            AliExpressError: If search fails
        """
        # Build API URL
        params = {
            "keyword": query if query else "",
            "pageNo": page,
            "pageSize": items_per_page,
            "sortType": sort.value if isinstance(sort, SortOption) else sort,
            "categoryId": category_id if category_id else "",
            "locale": self.language.value,
            "currency": self.currency.value,
            "country": self.country,
        }
        
        # Add filters if provided
        if filters:
            if filters.min_price is not None:
                params["minPrice"] = str(filters.min_price)
            if filters.max_price is not None:
                params["maxPrice"] = str(filters.max_price)
            if filters.free_shipping:
                params["isFreeShip"] = "y"
            if filters.ship_from:
                params["shipFromCountry"] = filters.ship_from
            if filters.min_rating:
                params["starRating"] = str(int(filters.min_rating))
        
        # Add API key
        params["_cb"] = str(int(time.time() * 1000))
        
        try:
            # Make the request
            data = await self._make_request(API_SEARCH_URL, params=params, use_json=True)
            
            # Parse the results directly from JSON
            products = []
            for item_data in data.get("items", []):
                try:
                    # Extract into BasicProduct model
                    from .parser import _parse_product_from_json
                    product = _parse_product_from_json(item_data)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error parsing product from API response: {e}")
                    continue
            
            # Create pagination info
            page_info = data.get("pageInfo", {})
            pagination = SearchPagination(
                page=page_info.get("page", page),
                total_pages=page_info.get("totalPage", 1),
                items_per_page=items_per_page,
                total_items=page_info.get("totalResults", len(products))
            )
            
            # Create search result
            search_result = SearchResult(
                products=products,
                pagination=pagination,
                query=query,
                category_id=category_id,
                filters=filters,
                sort_by=sort.value if isinstance(sort, SortOption) else sort,
            )
            
            logger.info(f"Found {len(products)} products via API (page {pagination.page}/{pagination.total_pages})")
            return search_result
            
        except Exception as e:
            logger.error(f"API search failed: {e}")
            # Fall back to HTML search
            logger.info("Falling back to HTML search")
            return await self._search_html(query, category_id, filters, sort, page, items_per_page)
    
    async def get_product_details(
        self,
        product_id: str,
        use_graphql: bool = False,
    ) -> DetailedProduct:
        """
        Get detailed information about a product.
        
        Args:
            product_id: Product ID
            use_graphql: Whether to use GraphQL API
            
        Returns:
            DetailedProduct object with product details
            
        Raises:
            ItemNotFoundError: If product not found
            AliExpressError: If request fails
        """
        logger.info(f"Getting product details for ID: {product_id}")
        
        try:
            if use_graphql:
                return await self._get_product_details_graphql(product_id)
            else:
                return await self._get_product_details_html(product_id)
        except (AntiBot, AntiScrapingError) as e:
            logger.warning(f"Anti-bot measures detected, switching to mobile site: {e}")
            # Try mobile site if anti-bot measures detected
            original_mobile = self.use_mobile
            try:
                self.use_mobile = True
                result = await self._get_product_details_html(product_id)
                return result
            finally:
                self.use_mobile = original_mobile
    
    async def _get_product_details_html(self, product_id: str) -> DetailedProduct:
        """
        Get product details using HTML scraping.
        
        Args:
            product_id: Product ID
            
        Returns:
            DetailedProduct object with product details
            
        Raises:
            ItemNotFoundError: If product not found
            AliExpressError: If request fails
        """
        # Build product URL
        url = f"{PRODUCT_URL_PATTERN}{product_id}.html"
        
        try:
            # Make the request
            html = await self._make_request(url)
            
            # Parse the results
            parser = ItemDetailParser(html, is_mobile=self.use_mobile)
            product = parser.parse_item()
            
            logger.info(f"Successfully retrieved product details: {product.title}")
            return product
            
        except AntiBot as e:
            logger.error(f"Anti-bot measures detected: {e}")
            raise AntiScrapingError(ERROR_MESSAGES["CAPTCHA_DETECTED"], None, {"product_id": product_id})
            
        except ParsingError as e:
            logger.error(f"Failed to parse product details: {e}")
            raise ParserError(ERROR_MESSAGES["PARSING_ERROR"], None, {"product_id": product_id})
    
    async def _get_product_details_graphql(self, product_id: str) -> DetailedProduct:
        """
        Get product details using GraphQL API.
        
        Args:
            product_id: Product ID
            
        Returns:
            DetailedProduct object with product details
            
        Raises:
            ItemNotFoundError: If product not found
            AliExpressError: If request fails
        """
        # Prepare GraphQL query
        query_data = {
            "query": PRODUCT_DETAIL_QUERY,
            "variables": {
                "id": product_id
            }
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-App": "pc",
            "X-Client-Side": "web",
        }
        
        try:
            # Make the request
            data = await self._make_request(
                GRAPHQL_URL,
                method="POST",
                data=query_data,
                headers=headers,
                use_json=True
            )
            
            # Check for errors
            if "errors" in data and data["errors"]:
                error = data["errors"][0]
                error_message = error.get("message", "Unknown error")
                
                if "not found" in error_message.lower():
                    raise ItemNotFoundError(f"Product {product_id} not found: {error_message}")
                else:
                    raise AliExpressError(error_message, None, {"graphql_error": error})
            
            # Check for data
            if "data" not in data or "item" not in data["data"] or not data["data"]["item"]:
                raise ItemNotFoundError(f"Product {product_id} not found")
            
            # Extract product data
            product_data = data["data"]["item"]
            
            # Convert to DetailedProduct
            # This would require a dedicated parser for GraphQL data
            # For now, fall back to HTML parsing
            logger.info("GraphQL response needs custom parsing, falling back to HTML")
            return await self._get_product_details_html(product_id)
            
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            logger.error(f"GraphQL request failed: {e}")
            # Fall back to HTML
            logger.info("Falling back to HTML product details")
            return await self._get_product_details_html(product_id)
    
    async def get_categories(self, parent_id: Optional[str] = None) -> List[Category]:
        """
        Get categories or subcategories.
        
        Args:
            parent_id: Parent category ID for subcategories
            
        Returns:
            List of Category objects
            
        Raises:
            AliExpressError: If request fails
        """
        logger.info(f"Getting categories" + (f" for parent {parent_id}" if parent_id else ""))
        
        # Build URL
        if parent_id:
            url = f"{CATEGORY_URL}/{parent_id}.html"
        else:
            url = f"{BASE_URL}/all-wholesale-products.html"
        
        try:
            # Make the request
            html = await self._make_request(url)
            
            # Parse the results
            parser = CategoryParser(html, is_mobile=self.use_mobile)
            categories = parser.parse_categories()
            
            logger.info(f"Successfully retrieved {len(categories)} categories")
            return categories
            
        except AntiBot as e:
            logger.error(f"Anti-bot measures detected: {e}")
            raise AntiScrapingError(ERROR_MESSAGES["CAPTCHA_DETECTED"], None, {"parent_id": parent_id})
            
        except ParsingError as e:
            logger.error(f"Failed to parse categories: {e}")
            raise ParserError(ERROR_MESSAGES["PARSING_ERROR"], None, {"parent_id": parent_id})
    
    async def get_category_tree(self) -> CategoryTree:
        """
        Get the full category tree.
        
        Returns:
            CategoryTree object with all categories
            
        Raises:
            AliExpressError: If request fails
        """
        logger.info("Getting category tree")
        
        # First get top-level categories
        top_categories = await self.get_categories()
        
        # Initialize tree
        tree = CategoryTree(
            categories=top_categories,
            total_count=len(top_categories),
        )
        
        # Optionally fetch children for each top category
        # This is resource-intensive and may trigger anti-bot
        # Consider implementing this as a separate method if needed
        
        return tree
    
    async def close(self):
        """Close the session."""
        await self._close_session()


# Synchronous wrapper
class SyncAliExpressCrawler:
    """Synchronous wrapper for AliExpressCrawler."""
    
    def __init__(self, **kwargs):
        """Initialize with same parameters as async version."""
        self.crawler_params = kwargs
        self._async_crawler = None
    
    def _get_event_loop(self):
        """Get event loop or create one if needed."""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def _run_async(self, coro):
        """Run coroutine in event loop."""
        loop = self._get_event_loop()
        return loop.run_until_complete(self._run_with_crawler(coro))
    
    async def _run_with_crawler(self, coro):
        """Run coroutine with crawler context manager."""
        if self._async_crawler is None:
            self._async_crawler = AliExpressCrawler(**self.crawler_params)
            
        return await coro(self._async_crawler)
    
    def search_products(self, **kwargs):
        """Synchronous version of search_products."""
        return self._run_async(lambda crawler: crawler.search_products(**kwargs))
    
    def get_product_details(self, product_id: str, use_graphql: bool = False):
        """Synchronous version of get_product_details."""
        return self._run_async(lambda crawler: crawler.get_product_details(product_id, use_graphql))
    
    def get_categories(self, parent_id: Optional[str] = None):
        """Synchronous version of get_categories."""
        return self._run_async(lambda crawler: crawler.get_categories(parent_id))
    
    def get_category_tree(self):
        """Synchronous version of get_category_tree."""
        return self._run_async(lambda crawler: crawler.get_category_tree())
    
    def close(self):
        """Close the async crawler."""
        if self._async_crawler is not None:
            self._run_async(lambda crawler: crawler.close())
            self._async_crawler = None
