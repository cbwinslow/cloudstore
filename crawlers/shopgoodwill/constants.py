"""
Constants and configuration settings for the ShopGoodwill crawler.

This module contains base URLs, API endpoints, HTML selectors, and other
configuration constants needed for scraping ShopGoodwill.com.
"""

from enum import Enum
from typing import Dict, List

# Base URLs
BASE_URL = "https://shopgoodwill.com"
SEARCH_URL = f"{BASE_URL}/shop/home"
ITEM_URL = f"{BASE_URL}/item/"
CATEGORIES_URL = f"{BASE_URL}/categories"

# API endpoints (relative to API_V1_STR)
ENDPOINT_SEARCH = "/shopgoodwill/search"
ENDPOINT_ITEM = "/shopgoodwill/item/{item_id}"
ENDPOINT_CATEGORIES = "/shopgoodwill/categories"

# HTML Selectors
class Selectors:
    # Search page selectors
    SEARCH_RESULTS = ".mb-4.p-3.border.rounded"
    PRODUCT_TITLE = ".font-weight-bold.mb-2"
    PRODUCT_PRICE = ".d-flex.justify-content-between.align-items-center .h5"
    PRODUCT_CURRENT_BID = ".d-flex.justify-content-between.align-items-center .h5"
    PRODUCT_BIDS_COUNT = ".small.text-muted"
    PRODUCT_TIME_LEFT = ".small.text-muted:contains('Time Left')"
    PRODUCT_SHIPPING = ".small.text-muted:contains('Shipping')"
    PRODUCT_SELLER = ".small.text-muted:contains('Seller')"
    PRODUCT_IMAGE = ".card-img-top"
    PRODUCT_LINK = "a[href*='/item/']"
    
    # Item detail page selectors
    ITEM_TITLE = ".h4.mb-3"
    ITEM_CURRENT_PRICE = ".h3.font-weight-bold"
    ITEM_CONDITION = ".mb-2:contains('Condition')"
    ITEM_SHIPPING_COST = ".mb-2:contains('Shipping')"
    ITEM_SELLER = ".mb-2:contains('Seller')"
    ITEM_DESCRIPTION = "#item-description"
    ITEM_IMAGES = ".carousel-item img"
    ITEM_BIDS = "#bid-history-table tbody tr"
    ITEM_END_DATE = ".mb-2:contains('End Date')"
    
    # Category selectors
    CATEGORY_LIST = ".list-group-item"
    CATEGORY_NAME = ".font-weight-bold"
    CATEGORY_COUNT = ".badge"

# Rate limiting constants - these match values in .env
RATE_LIMIT = 20  # Requests per minute
RATE_LIMIT_BURST = 5  # Additional burst requests allowed
RETRY_ATTEMPTS = 3  # Number of retry attempts
RETRY_BACKOFF = 1.5  # Exponential backoff multiplier
REQUEST_TIMEOUT = 30  # Seconds

# Default headers to use in requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Sort options available in the ShopGoodwill interface
class SortOptions(str, Enum):
    ENDING_SOON = "endingSoon"
    NEWLY_LISTED = "newlyListed"
    MOST_BIDS = "mostBids"
    PRICE_LOWEST = "priceLowHigh"
    PRICE_HIGHEST = "priceHighLow"
    FEATURED = "featured"

# Condition options for filtering
class ConditionOptions(str, Enum):
    NEW = "New"
    LIKE_NEW = "Like New"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    FOR_PARTS = "For parts or not working"

# Error messages
ERROR_MESSAGES = {
    "CONNECTION_ERROR": "Failed to connect to ShopGoodwill.com",
    "TIMEOUT_ERROR": "Request timed out while connecting to ShopGoodwill.com",
    "PARSING_ERROR": "Failed to parse ShopGoodwill.com response",
    "RATE_LIMIT_ERROR": "Rate limit exceeded for ShopGoodwill.com",
    "ITEM_NOT_FOUND": "Item not found on ShopGoodwill.com",
    "INVALID_RESPONSE": "Received invalid response from ShopGoodwill.com",
}

# Item categories
# This will be populated dynamically but we can provide some common ones
COMMON_CATEGORIES = [
    "Electronics",
    "Collectibles",
    "Jewelry",
    "Art",
    "Books",
    "Clothing",
    "Furniture",
    "Home & Garden",
    "Music",
    "Sports",
    "Toys & Hobbies",
    "Video Games",
]

