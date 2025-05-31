"""
eBay API client implementation.

This module provides a client for interacting with eBay's APIs, including
authentication, rate limiting, retry logic, and methods for common operations.
"""

import asyncio
import base64
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from urllib.parse import urlencode

import aiohttp
import backoff
import requests
from requests.auth import HTTPBasicAuth
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, RetryError
)

from .constants import (
    PRODUCTION_BASE_URL, SANDBOX_BASE_URL,
    OAUTH_PROD_TOKEN_URL, OAUTH_SANDBOX_TOKEN_URL,
    FINDING_API_URL, SHOPPING_API_URL, BROWSE_API_URL, TAXONOMY_API_URL,
    FINDING_API_RATE_LIMIT, SHOPPING_API_RATE_LIMIT,
    RETRY_ATTEMPTS, RETRY_BACKOFF, REQUEST_TIMEOUT,
    DEFAULT_ITEMS_PER_PAGE, MAX_PAGES, MAX_ENTRIES_PER_PAGE,
    DEFAULT_HEADERS, COMPATIBILITY_LEVEL,
    FindingApiOperation, ShoppingApiOperation, GlobalId, SortOrder, ItemFilter,
    ERROR_MESSAGES, ERROR_CODES
)
from .models import (
    OAuthToken, Item, SearchResult, PaginationInfo, CategoryHierarchy,
    ApiResponse, FindingApiResponse, ShoppingApiResponse
)

# Configure logger
logger = logging.getLogger(__name__)


# Custom exceptions
class EbayApiError(Exception):
    """Base exception for eBay API errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        """
        Initialize eBay API error.
        
        Args:
            message: Error message
            error_code: eBay error code, if available
            details: Additional error details
        """
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(EbayApiError):
    """Exception for authentication failures."""
    pass


class RateLimitError(EbayApiError):
    """Exception for rate limit exceeded errors."""
    pass


class ConnectionError(EbayApiError):
    """Exception for connection errors."""
    pass


class TimeoutError(EbayApiError):
    """Exception for timeout errors."""
    pass


class ItemNotFoundError(EbayApiError):
    """Exception for item not found errors."""
    pass


class InvalidRequestError(EbayApiError):
    """Exception for invalid request errors."""
    pass


class ParsingError(EbayApiError):
    """Exception for response parsing errors."""
    pass


class RateLimiter:
    """Rate limiter implementation using token bucket algorithm."""
    
    def __init__(self, rate_limit: int, burst_limit: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            rate_limit: Number of requests allowed per second
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
        new_tokens = elapsed * self.rate_limit
        
        if new_tokens > 0:
            self.tokens = min(self.tokens + new_tokens, self.burst_limit)
            self.last_refill = now
    
    async def acquire(self):
        """
        Acquire a token for making a request.
        
        Raises:
            RateLimitError: If no tokens are available
        """
        async with self.lock:
            self._refill_tokens()
            
            if self.tokens < 1:
                # Calculate how long to wait until a token becomes available
                wait_time = (1 - self.tokens) / self.rate_limit
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
                raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_EXCEEDED"])
            
            self.tokens -= 1
            return True


class EbayApiClient:
    """Client for eBay APIs with authentication, rate limiting, and retry logic."""
    
    def __init__(
        self,
        app_id: str,
        cert_id: str,
        dev_id: str,
        redirect_uri: str,
        client_id: str = None,
        client_secret: str = None,
        use_sandbox: bool = False,
        global_id: GlobalId = GlobalId.EBAY_US,
        timeout: int = REQUEST_TIMEOUT,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff: float = RETRY_BACKOFF,
    ):
        """
        Initialize eBay API client.
        
        Args:
            app_id: eBay application ID
            cert_id: eBay certification ID
            dev_id: eBay developer ID
            redirect_uri: OAuth redirect URI
            client_id: OAuth client ID (if different from app_id)
            client_secret: OAuth client secret (if different from cert_id)
            use_sandbox: Whether to use eBay sandbox environment
            global_id: Global ID for the eBay marketplace
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_backoff: Exponential backoff multiplier
        """
        self.app_id = app_id
        self.cert_id = cert_id
        self.dev_id = dev_id
        self.redirect_uri = redirect_uri
        self.client_id = client_id or app_id
        self.client_secret = client_secret or cert_id
        self.use_sandbox = use_sandbox
        self.global_id = global_id
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        
        # Set base URLs based on environment
        self.base_url = SANDBOX_BASE_URL if use_sandbox else PRODUCTION_BASE_URL
        self.token_url = OAUTH_SANDBOX_TOKEN_URL if use_sandbox else OAUTH_PROD_TOKEN_URL
        
        # Setup rate limiters for different APIs
        self.finding_rate_limiter = RateLimiter(FINDING_API_RATE_LIMIT)
        self.shopping_rate_limiter = RateLimiter(SHOPPING_API_RATE_LIMIT)
        
        # OAuth token storage
        self.oauth_token: Optional[OAuthToken] = None
        
        # Session for API requests
        self.session = None
        
        # Headers for requests
        self.headers = DEFAULT_HEADERS.copy()
        self.headers["X-EBAY-API-APP-NAME"] = self.app_id
        
        logger.info(f"Initialized eBay API client (sandbox={use_sandbox}, global_id={global_id.value})")
    
    async def _init_session(self):
        """Initialize aiohttp session if not already created."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)
    
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
    
    async def authenticate(self, refresh: bool = False) -> OAuthToken:
        """
        Authenticate with eBay API using client credentials.
        
        Args:
            refresh: Force token refresh even if current token is valid
            
        Returns:
            OAuth token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Check if we already have a valid token
        if not refresh and self.oauth_token and self.is_token_valid():
            logger.debug("Using existing OAuth token")
            return self.oauth_token
        
        logger.info("Authenticating with eBay API")
        
        # Prepare auth headers
        auth_string = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        # Prepare request data
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }
        
        try:
            # Initialize session if needed
            await self._init_session()
            
            async with self.session.post(
                self.token_url,
                headers=headers,
                data=urlencode(data),
                timeout=self.timeout
            ) as response:
                response.raise_for_status()
                token_data = await response.json()
                
                # Add expiration time
                token_data["expires_at"] = datetime.now() + timedelta(seconds=token_data["expires_in"])
                
                self.oauth_token = OAuthToken(**token_data)
                logger.info("Successfully obtained OAuth token")
                
                return self.oauth_token
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(ERROR_MESSAGES["AUTH_ERROR"], str(e.status), {"response": str(e)})
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Connection error during authentication: {e}")
            raise ConnectionError(ERROR_MESSAGES["CONNECTION_ERROR"], None, {"error": str(e)})
    
    def is_token_valid(self) -> bool:
        """
        Check if the current OAuth token is valid.
        
        Returns:
            True if token is valid, False otherwise
        """
        if not self.oauth_token or not self.oauth_token.expires_at:
            return False
        
        # Add buffer time to ensure token doesn't expire during request
        buffer_time = timedelta(minutes=5)
        return datetime.now() < self.oauth_token.expires_at - buffer_time
    
    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_BACKOFF, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, RateLimitError)),
        reraise=True
    )
    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_required: bool = True,
        rate_limiter: Optional[RateLimiter] = None,
        use_xml: bool = False,
    ) -> Union[Dict[str, Any], str]:
        """
        Make HTTP request to eBay API with rate limiting and retries.
        
        Args:
            url: URL to request
            method: HTTP method (GET, POST)
            params: URL parameters
            data: Request data
            headers: Request headers
            auth_required: Whether authentication is required
            rate_limiter: Rate limiter to use
            use_xml: Whether to use XML for request/response
            
        Returns:
            Response data as dictionary or string (if use_xml=True)
            
        Raises:
            ConnectionError: If connection to eBay fails
            TimeoutError: If request times out
            RateLimitError: If rate limit is exceeded
            AuthenticationError: If authentication fails
            InvalidRequestError: If request is invalid
            EbayApiError: For other eBay API errors
        """
        # Apply rate limiting if provided
        if rate_limiter:
            try:
                await rate_limiter.acquire()
            except RateLimitError as e:
                # Wait a bit before retrying
                await asyncio.sleep(1)
                try:
                    await rate_limiter.acquire()
                except RateLimitError:
                    # If still rate limited, raise the exception
                    logger.warning("Rate limit exceeded after waiting")
                    raise
        
        # Authenticate if required
        if auth_required:
            await self.authenticate()
            
        # Initialize session if needed
        await self._init_session()
        
        # Prepare headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
            
        # Add authentication header if required
        if auth_required and self.oauth_token:
            request_headers["Authorization"] = f"{self.oauth_token.token_type} {self.oauth_token.access_token}"
            
        # Set content type based on use_xml
        if use_xml:
            request_headers["Content-Type"] = "application/xml"
            request_headers["Accept"] = "application/xml"
        else:
            request_headers["Content-Type"] = "application/json"
            request_headers["Accept"] = "application/json"
        
        # Prepare URL
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}{url}"
        
        try:
            start_time = time.time()
            
            logger.debug(f"Making {method} request to {url}")
            
            if method.upper() == "GET":
                async with self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout
                ) as response:
                    await self._handle_response_status(response)
                    if use_xml:
                        return await response.text()
                    return await response.json()
                    
            elif method.upper() == "POST":
                # Convert data to appropriate format
                post_data = data
                if data and not use_xml and not isinstance(data, str):
                    post_data = json.dumps(data)
                
                async with self.session.post(
                    url,
                    params=params,
                    data=post_data,
                    headers=request_headers,
                    timeout=self.timeout
                ) as response:
                    await self._handle_response_status(response)
                    if use_xml:
                        return await response.text()
                    return await response.json()
                    
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
        except aiohttp.ClientResponseError as e:
            # Handle response errors
            if e.status == 401:
                logger.error(f"Authentication error: {e}")
                raise AuthenticationError(ERROR_MESSAGES["AUTH_ERROR"], str(e.status))
            elif e.status == 429:
                logger.error(f"Rate limit exceeded: {e}")
                raise RateLimitError(ERROR_MESSAGES["RATE_LIMIT_EXCEEDED"], str(e.status))
            elif e.status == 400:
                logger.error(f"Invalid request: {e}")
                raise InvalidRequestError(ERROR_MESSAGES["INVALID_REQUEST"], str(e.status))
            elif e.status == 404:
                logger.error(f"Resource not found: {e}")
                raise ItemNotFoundError(ERROR_MESSAGES["ITEM_NOT_FOUND"], str(e.status))
            else:
                logger.error(f"HTTP error {e.status}: {e}")
                raise EbayApiError(f"HTTP error {e.status}", str(e.status))
                
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(ERROR_MESSAGES["CONNECTION_ERROR"], None, {"error": str(e)})
            
        except asyncio.TimeoutError as e:
            logger.error(f"Request timed out: {e}")
            raise TimeoutError(ERROR_MESSAGES["TIMEOUT_ERROR"], None, {"error": str(e)})
    
    async def _handle_response_status(self, response: aiohttp.ClientResponse):
        """
        Handle response status codes and raise appropriate exceptions.
        
        Args:
            response: aiohttp response object
            
        Raises:
            AuthenticationError: If authentication failed
            RateLimitError: If rate limit is exceeded
            ItemNotFoundError: If item is not found
            InvalidRequestError: If request is invalid
            EbayApiError: For other eBay API errors
        """
        # Raise for HTTP status errors
        response.raise_for_status()
        
        # Additional error handling for eBay-specific errors
        content_type = response.headers.get("Content-Type", "")
        
        # For JSON responses, check for errors in the response
        if "application/json" in content_type:
            try:
                peek_data = await response.json()
                if "errors" in peek_data and peek_data["errors"]:
                    error = peek_data["errors"][0]
                    error_code = error.get("errorId") or error.get("code")
                    error_message = error.get("message") or error.get("longMessage") or "Unknown eBay error"
                    
                    # Map error code to exception
                    if error_code == "931" or error_code == "17470" or error_code == "21916884":
                        raise AuthenticationError(error_message, error_code, error)
                    elif error_code == "218050" or error_code == "218053":
                        raise RateLimitError(error_message, error_code, error)
                    elif error_code == "35":
                        raise ItemNotFoundError(error_message, error_code, error)
                    elif error_code == "10007":
                        raise InvalidRequestError(error_message, error_code, error)
                    else:
                        raise EbayApiError(error_message, error_code, error)
            except (json.JSONDecodeError, KeyError):
                # If we can't parse the response as JSON or find errors, continue
                pass
    
    async def search_items(
        self,
        keywords: Optional[str] = None,
        category_id: Optional[str] = None,
        sort_order: SortOrder = SortOrder.BEST_MATCH,
        item_filters: Optional[List[Dict[str, Any]]] = None,
        page: int = 1,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        include_selector: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        Search for items on eBay using the Finding API.
        
        Args:
            keywords: Search keywords
            category_id: Category ID to search in
            sort_order: Sort order for results
            item_filters: List of filters to apply
            page: Page number
            items_per_page: Number of items per page
            include_selector: Additional data to include
            
        Returns:
            SearchResult object with the search results
            
        Raises:
            InvalidRequestError: If the request is invalid
            EbayApiError: For other eBay API errors
        """
        logger.info(f"Searching eBay for items: keywords='{keywords}', category={category_id}")
        
        # Determine which operation to use
        operation = None
        if keywords and category_id:
            operation = FindingApiOperation.FIND_ITEMS_ADVANCED
        elif keywords:
            operation = FindingApiOperation.FIND_ITEMS_BY_KEYWORDS
        elif category_id:
            operation = FindingApiOperation.FIND_ITEMS_BY_CATEGORY
        else:
            raise InvalidRequestError("Either keywords or category_id must be provided")
        
        # Build request data
        request_data = {
            "findItemsAdvancedRequest" if operation == FindingApiOperation.FIND_ITEMS_ADVANCED else
            "findItemsByKeywordsRequest" if operation == FindingApiOperation.FIND_ITEMS_BY_KEYWORDS else
            "findItemsByCategoryRequest": {
                "keywords": keywords if keywords else None,
                "categoryId": category_id if category_id else None,
                "paginationInput": {
                    "entriesPerPage": min(items_per_page, MAX_ENTRIES_PER_PAGE),
                    "pageNumber": page
                },
                "sortOrder": sort_order.value if isinstance(sort_order, SortOrder) else sort_order,
                "itemFilter": item_filters if item_filters else [],
                "outputSelector": include_selector if include_selector else []
            }
        }
        
        # Prepare headers
        headers = {
            "X-EBAY-SOA-OPERATION-NAME": operation.value,
            "X-EBAY-SOA-SECURITY-APPNAME": self.app_id,
            "X-EBAY-SOA-GLOBAL-ID": self.global_id.value if isinstance(self.global_id, GlobalId) else self.global_id,
        }
        
        try:
            # Make the request
            response = await self._make_request(
                FINDING_API_URL,
                method="POST",
                data=request_data,
                headers=headers,
                rate_limiter=self.finding_rate_limiter,
                auth_required=False  # Finding API uses app ID in header, not OAuth
            )
            
            # Parse the response
            operation_response = operation.value + "Response"
            if operation_response not in response:
                raise ParsingError(f"Unexpected response format: {operation_response} not found")
            
            response_data = response[operation_response]
            
            # Process search result
            search_result_data = response_data.get("searchResult", {})
            items_data = search_result_data.get("item", [])
            
            # Create pagination info
            pagination_data = response_data.get("paginationOutput", {})
            pagination = PaginationInfo(
                entry_per_page=int(pagination_data.get("entriesPerPage", items_per_page)),
                page_number=int(pagination_data.get("pageNumber", page)),
                total_pages=int(pagination_data.get("totalPages", 1)),
                total_entries=int(pagination_data.get("totalEntries", len(items_data)))
            )
            
            # Process items
            items = []
            for item_data in items_data:
                try:
                    item = await self._parse_finding_item(item_data)
                    items.append(item)
                except Exception as e:
                    logger.warning(f"Error parsing item: {e}")
                    continue
            
            # Create search result
            search_result = SearchResult(
                items=items,
                pagination=pagination,
                timestamp=datetime.now(),
                search_terms=keywords,
                category_id=category_id,
                sort_order=sort_order.value if isinstance(sort_order, SortOrder) else sort_order,
                filters_applied={} if not item_filters else {"filters": item_filters},
                total_items_count=int(pagination_data.get("totalEntries", len(items)))
            )
            
            logger.info(f"Found {len(items)} items (page {pagination.page_number}/{pagination.total_pages})")
            return search_result
            
        except EbayApiError as e:
            logger.error(f"Error searching items: {e}")
            raise
    
    async def get_item(self, item_id: str, include_description: bool = True) -> Item:
        """
        Get detailed information about a specific item using the Shopping API.
        
        Args:
            item_id: eBay item ID
            include_description: Whether to include the item description
            
        Returns:
            Item object with item details
            
        Raises:
            ItemNotFoundError: If the item is not found
            EbayApiError: For other eBay API errors
        """
        logger.info(f"Getting item details for ID: {item_id}")
        
        # Prepare parameters
        params = {
            "callname": ShoppingApiOperation.GET_SINGLE_ITEM.value,
            "responseencoding": "JSON",
            "siteid": "0",  # US site
            "version": "1155",
            "ItemID": item_id,
            "IncludeSelector": "Details,ShippingCosts,ItemSpecifics,Variations" + 
                               (",Description" if include_description else "")
        }
        
        try:
            # Make the request
            response = await self._make_request(
                f"{SHOPPING_API_URL}?appid={self.app_id}",
                params=params,
                rate_limiter=self.shopping_rate_limiter,
                auth_required=False  # Shopping API uses app ID in params, not OAuth
            )
            
            # Check for errors
            if "Errors" in response and response["Errors"]:
                error = response["Errors"][0]
                error_code = error.get("ErrorCode")
                error_message = error.get("LongMessage") or error.get("ShortMessage") or "Unknown eBay error"
                
                if error_code == "35":
                    raise ItemNotFoundError(f"Item {item_id} not found: {error_message}", error_code)
                else:
                    raise EbayApiError(error_message, error_code, error)
            
            # Check for item
            if "Item" not in response:
                raise ParsingError("Item not found in response")
            
            # Parse the item
            item_data = response["Item"]
            item = await self._parse_shopping_item(item_data)
            
            logger.info(f"Successfully retrieved item: {item.title}")
            return item
            
        except EbayApiError as e:
            logger.error(f"Error getting item details: {e}")
            raise
    
    async def get_categories(self, parent_id: Optional[str] = None) -> CategoryHierarchy:
        """
        Get category hierarchy using the Taxonomy API.
        
        Args:
            parent_id: Parent category ID to start from
            
        Returns:
            CategoryHierarchy object with categories
            
        Raises:
            EbayApiError: For eBay API errors
        """
        logger.info(f"Getting category hierarchy" + (f" for parent {parent_id}" if parent_id else ""))
        
        # Use the Taxonomy API
        url = f"{TAXONOMY_API_URL}/get_category_tree"
        params = {
            "category_tree_id": "0"  # US site
        }
        
        if parent_id:
            url = f"{TAXONOMY_API_URL}/get_category_subtree"
            params["category_id"] = parent_id
        
        try:
            # Make the request with OAuth
            await self.authenticate()
            response = await self._make_request(
                url,
                params=params,
                auth_required=True
            )
            
            # Parse the response
            if "categoryTreeId" not in response:
                raise ParsingError("Unexpected response format from Taxonomy API")
            
            categories = []
            root_node = response.get("rootCategoryNode", {})
            
            # Process the category tree recursively
            await self._process_category_tree(root_node, categories)
            
            # Create category hierarchy
            hierarchy = CategoryHierarchy(
                categories=categories,
                timestamp=datetime.now(),
                version=response.get("categoryTreeVersion"),
                category_count=len(categories)
            )
            
            logger.info(f"Retrieved {len(categories)} categories")
            return hierarchy
            
        except EbayApiError as e:
            logger.error(f"Error getting categories: {e}")
            raise
    
    async def _process_category_tree(self, node: Dict[str, Any], categories: List, parent_id: Optional[str] = None, level: int = 0):
        """
        Process category tree recursively.
        
        Args:
            node: Category node
            categories: List to append categories to
            parent_id: Parent category ID
            level: Category level in hierarchy
        """
        if not node:
            return
        
        # Extract category data
        category_data = node.get("category", {})
        category_id = category_data.get("categoryId")
        
        if category_id:
            # Create category
            from .models import Category
            category = Category(
                category_id=category_id,
                category_name=category_data.get("categoryName", ""),
                parent_category_id=parent_id,
                level=level,
                leaf_category=not bool(node.get("childCategoryTreeNodes"))
            )
            
            # Add to list
            categories.append(category)
            
            # Process child categories
            child_nodes = node.get("childCategoryTreeNodes", [])
            for child_node in child_nodes:
                await self._process_category_tree(child_node, categories, category_id, level + 1)
    
    async def _parse_finding_item(self, item_data: Dict[str, Any]) -> Item:
        """
        Parse item data from Finding API response.
        
        Args:
            item_data: Item data from response
            
        Returns:
            Item object
        """
        from .models import Amount, Category, Seller, ShippingInfo, ListingInfo, ItemCondition
        
        # Basic item info
        item_id = item_data.get("itemId")
        title = item_data.get("title", "")
        
        # Parse primary category
        primary_category = None
        if "primaryCategory" in item_data:
            category_data = item_data["primaryCategory"]
            primary_category = Category(
                category_id=category_data.get("categoryId", ""),
                category_name=category_data.get("categoryName", "")
            )
        
        # Parse seller
        seller = None
        if "sellerInfo" in item_data:
            seller_data = item_data["sellerInfo"]
            seller = Seller(
                user_id=seller_data.get("sellerUserName", ""),
                feedback_score=seller_data.get("feedbackScore"),
                positive_feedback_percent=seller_data.get("positiveFeedbackPercent"),
                top_rated_seller=seller_data.get("topRatedSeller") == "true"
            )
        
        # Parse shipping info
        shipping_info = None
        if "shippingInfo" in item_data:
            shipping_data = item_data["shippingInfo"]
            shipping_cost = None
            
            if "shippingServiceCost" in shipping_data:
                cost_data = shipping_data["shippingServiceCost"]
                if isinstance(cost_data, dict):
                    shipping_cost = Amount(
                        value=Decimal(cost_data.get("__value__", "0")),
                        currency_id=cost_data.get("@currencyId", "USD")
                    )
            
            shipping_info = ShippingInfo(
                shipping_type=shipping_data.get("shippingType", ""),
                shipping_cost=shipping_cost
            )
        
        # Parse listing info
        listing_info = None
        if "listingInfo" in item_data:
            listing_data = item_data["listingInfo"]
            start_time = None
            end_time = None
            
            if "startTime" in listing_data:
                try:
                    start_time = datetime.fromisoformat(listing_data["startTime"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
                
            if "endTime" in listing_data:
                try:
                    end_time = datetime.fromisoformat(listing_data["endTime"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            listing_info = ListingInfo(
                listing_type=listing_data.get("listingType", ""),
                buy_it_now_available=listing_data.get("buyItNowAvailable") == "true",
                start_time=start_time,
                end_time=end_time,
                watch_count=int(listing_data.get("watchCount", 0)) if "watchCount" in listing_data else None
            )
        
        # Parse condition
        condition = None
        if "condition" in item_data:
            condition_data = item_data["condition"]
            condition_id = int(condition_data.get("conditionId", 0)) if "conditionId" in condition_data else None
            condition_name = condition_data.get("conditionDisplayName", "")
            
            if condition_id is not None:
                condition = ItemCondition(
                    condition_id=condition_id,
                    condition_name=condition_name
                )
        
        # Parse current price
        current_price = None
        if "sellingStatus" in item_data and "currentPrice" in item_data["sellingStatus"]:
            price_data = item_data["sellingStatus"]["currentPrice"]
            if isinstance(price_data, dict):
                current_price = Amount(
                    value=Decimal(price_data.get("__value__", "0")),
                    currency_id=price_data.get("@currencyId", "USD")
                )
        
        # Create item
        item = Item(
            item_id=item_id,
            title=title,
            primary_category=primary_category,
            seller=seller,
            shipping_info=shipping_info,
            listing_info=listing_info,
            condition=condition,
            current_price=current_price,
            gallery_url=item_data.get("galleryURL"),
            view_item_url=item_data.get("viewItemURL"),
            location=item_data.get("location"),
            country=item_data.get("country")
        )
        
        return item
    
    async def _parse_shopping_item(self, item_data: Dict[str, Any]) -> Item:
        """
        Parse item data from Shopping API response.
        
        Args:
            item_data: Item data from response
            
        Returns:
            Item object
        """
        from .models import Amount, Category, Seller, ShippingInfo, ListingInfo, ItemCondition, ItemSpecific
        
        # Basic item info
        item_id = item_data.get("ItemID")
        title = item_data.get("Title", "")
        subtitle = item_data.get("Subtitle")
        
        # Parse primary category
        primary_category = None
        if "PrimaryCategory" in item_data:
            category_data = item_data["PrimaryCategory"]
            primary_category = Category(
                category_id=category_data.get("CategoryID", ""),
                category_name=category_data.get("CategoryName", "")
            )
        
        # Parse seller
        seller = None
        if "Seller" in item_data:
            seller_data = item_data["Seller"]
            seller = Seller(
                user_id=seller_data.get("UserID", ""),
                feedback_score=seller_data.get("FeedbackScore"),
                positive_feedback_percent=seller_data.get("PositiveFeedbackPercent"),
                top_rated_seller=seller_data.get("TopRatedSeller") == "true"
            )
        
        # Parse shipping info
        shipping_info = None
        if "ShippingCostSummary" in item_data:
            shipping_data = item_data["ShippingCostSummary"]
            shipping_cost = None
            
            if "ShippingServiceCost" in shipping_data:
                cost_data = shipping_data["ShippingServiceCost"]
                if isinstance(cost_data, dict):
                    shipping_cost = Amount(
                        value=Decimal(str(cost_data.get("Value", "0"))),
                        currency_id=cost_data.get("CurrencyID", "USD")
                    )
            
            shipping_info = ShippingInfo(
                shipping_type=item_data.get("ShippingType", ""),
                shipping_cost=shipping_cost
            )
        
        # Parse condition
        condition = None
        if "ConditionID" in item_data:
            condition_id = int(item_data["ConditionID"])
            condition_name = item_data.get("ConditionDisplayName", "")
            
            condition = ItemCondition(
                condition_id=condition_id,
                condition_name=condition_name
            )
        
        # Parse current price
        current_price = None
        if "CurrentPrice" in item_data:
            price_data = item_data["CurrentPrice"]
            if isinstance(price_data, dict):
                current_price = Amount(
                    value=Decimal(str(price_data.get("Value", "0"))),
                    currency_id=price_data.get("CurrencyID", "USD")
                )
        
        # Parse item specifics
        item_specifics = []
        if "ItemSpecifics" in item_data and "NameValueList" in item_data["ItemSpecifics"]:
            for specific in item_data["ItemSpecifics"]["NameValueList"]:
                name = specific.get("Name", "")
                values = specific.get("Value", [])
                if not isinstance(values, list):
                    values = [values]
                
                item_specifics.append(ItemSpecific(
                    name=name,
                    value=values
                ))
        
        # Create item
        item = Item(
            item_id=item_id,
            title=title,
            subtitle=subtitle,
            primary_category=primary_category,
            seller=seller,
            shipping_info=shipping_info,
            condition=condition,
            current_price=current_price,
            gallery_url=item_data.get("GalleryURL"),
            view_item_url=item_data.get("ViewItemURLForNaturalSearch"),
            location=item_data.get("Location"),
            country=item_data.get("Country"),
            description=item_data.get("Description"),
            item_specifics=item_specifics
        )
        
        return item


# Synchronous wrapper
class SyncEbayApiClient:
    """Synchronous wrapper for EbayApiClient."""
    
    def __init__(self, **kwargs):
        """Initialize with same parameters as async version."""
        self.client_params = kwargs
        self._async_client = None
    
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
        return loop.run_until_complete(self._run_with_client(coro))
    
    async def _run_with_client(self, coro):
        """Run coroutine with client context manager."""
        if self._async_client is None:
            self._async_client = EbayApiClient(**self.client_params)
            
        return await coro(self._async_client)
    
    def authenticate(self, refresh: bool = False):
        """Synchronous version of authenticate."""
        return self._run_async(lambda client: client.authenticate(refresh))
    
    def search_items(self, **kwargs):
        """Synchronous version of search_items."""
        return self._run_async(lambda client: client.search_items(**kwargs))
    
    def get_item(self, item_id: str, include_description: bool = True):
        """Synchronous version of get_item."""
        return self._run_async(lambda client: client.get_item(item_id, include_description))
    
    def get_categories(self, parent_id: Optional[str] = None):
        """Synchronous version of get_categories."""
        return self._run_async(lambda client: client.get_categories(parent_id))
    
    def close(self):
        """Close the async client."""
        if self._async_client is not None:
            self._run_async(lambda client: client._close_session())
            self._async_client = None

