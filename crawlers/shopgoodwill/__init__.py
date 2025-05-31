"""
ShopGoodwill Crawler Package

This package provides functionality for crawling and scraping ShopGoodwill.com,
including search capabilities, item detail extraction, and category browsing.

Main components:
- SyncShopGoodwillCrawler: Synchronous crawler for ShopGoodwill
- ShopGoodwillCrawler: Asynchronous crawler for ShopGoodwill
- ProductListingParser: Parser for product listings
- ItemDetailParser: Parser for item details
- CategoryParser: Parser for categories
- Constants and configuration values (e.g., rate limits, URLs)

Usage:
    from crawlers.shopgoodwill import SyncShopGoodwillCrawler
    
    crawler = SyncShopGoodwillCrawler()
    results = crawler.search(query="vintage camera")
    
    # Or using the async version with an async context manager
    async with ShopGoodwillCrawler() as crawler:
        results = await crawler.search(query="vintage camera")
"""

__version__ = "0.1.0"
__author__ = "CloudStore Team"
__email__ = "info@cloudstore.com"
__license__ = "Proprietary"

# Import main components for easier access
from .crawler import (
    ShopGoodwillCrawler,
    SyncShopGoodwillCrawler,
    ShopGoodwillError,
    ConnectionError,
    TimeoutError,
    RateLimitError,
    ItemNotFoundError,
)

from .parser import (
    ProductListingParser,
    ItemDetailParser,
    CategoryParser,
    ParsingError,
    clean_text,
    extract_price,
    extract_item_id,
)

from .constants import (
    BASE_URL,
    SEARCH_URL,
    ITEM_URL,
    CATEGORIES_URL,
    RATE_LIMIT,
    RATE_LIMIT_BURST,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF,
    REQUEST_TIMEOUT,
    Selectors,
    SortOptions,
    ConditionOptions,
)

# Define public API
__all__ = [
    "ShopGoodwillCrawler",
    "SyncShopGoodwillCrawler",
    "ProductListingParser",
    "ItemDetailParser",
    "CategoryParser",
    "ShopGoodwillError",
    "ConnectionError",
    "TimeoutError",
    "RateLimitError",
    "ItemNotFoundError",
    "ParsingError",
    "SortOptions",
    "ConditionOptions",
    "Selectors",
    "BASE_URL",
    "SEARCH_URL",
    "ITEM_URL",
    "CATEGORIES_URL",
]

