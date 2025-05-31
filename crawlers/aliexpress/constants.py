"""
Constants and configuration settings for the AliExpress crawler.

This module contains base URLs, HTML selectors, API endpoints, rate limits,
and other configuration constants needed for scraping AliExpress.
"""

from enum import Enum
from typing import Dict, List, Set

# Base URLs - Different regions and domains
BASE_URL = "https://www.aliexpress.com"
GLOBAL_URL = "https://www.aliexpress.com"
US_URL = "https://www.aliexpress.us"
RU_URL = "https://aliexpress.ru"
ES_URL = "https://es.aliexpress.com"
FR_URL = "https://fr.aliexpress.com"
DE_URL = "https://de.aliexpress.com"
IT_URL = "https://it.aliexpress.com"
BR_URL = "https://pt.aliexpress.com"

# Search URLs
SEARCH_URL = f"{BASE_URL}/wholesale"
CATEGORY_URL = f"{BASE_URL}/category"

# Product URL pattern
PRODUCT_URL_PATTERN = f"{BASE_URL}/item/"

# Mobile URLs (sometimes easier to scrape)
MOBILE_BASE_URL = "https://m.aliexpress.com"
MOBILE_SEARCH_URL = f"{MOBILE_BASE_URL}/wholesale"

# API Endpoints (for AJAX calls)
API_SEARCH_URL = f"{BASE_URL}/glosearch/api/product"
API_PRODUCT_URL = f"{BASE_URL}/glosearch/api/item"
API_DESCRIPTION_URL = f"{BASE_URL}/getDescModuleAjax.htm"
API_FEEDBACK_URL = f"{BASE_URL}/feedback/service/evaluate.htm"
API_STORE_URL = f"{BASE_URL}/store/data/getSellerInfo.htm"

# GraphQL API (used for some data fetching)
GRAPHQL_URL = f"{BASE_URL}/aegraphql/ae_detail_service"

# Rate Limits
# AliExpress has aggressive anti-scraping, so we need to be conservative
RATE_LIMIT = 3  # Requests per minute (very conservative)
RATE_LIMIT_BURST = 2  # Additional burst requests allowed
RETRY_ATTEMPTS = 3  # Number of retry attempts
RETRY_BACKOFF = 2.0  # Exponential backoff multiplier
REQUEST_TIMEOUT = 30  # Seconds
DELAY_BETWEEN_REQUESTS = 5  # Seconds between requests
RANDOM_DELAY_RANGE = (3, 10)  # Random delay range in seconds

# Default request parameters
DEFAULT_ITEMS_PER_PAGE = 60  # Default items per page
MAX_PAGES = 100  # Maximum pages to fetch in pagination

# HTTP Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "TE": "Trailers",
    "Pragma": "no-cache",
}

# Mobile headers to mimic mobile device
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Cookies needed for certain regions or to bypass anti-scraping
DEFAULT_COOKIES = {
    "aep_usuc_f": "site=glo&c_tp=USD&region=US&b_locale=en_US",
    "intl_locale": "en_US",
    "xman_us_f": "x_l=0&x_locale=en_US",
}

# Supported languages
class Language(str, Enum):
    """Supported languages for AliExpress."""
    ENGLISH = "en_US"
    SPANISH = "es_ES"
    FRENCH = "fr_FR"
    GERMAN = "de_DE"
    ITALIAN = "it_IT"
    PORTUGUESE = "pt_BR"
    RUSSIAN = "ru_RU"
    DUTCH = "nl_NL"
    TURKISH = "tr_TR"
    POLISH = "pl_PL"
    KOREAN = "ko_KR"
    JAPANESE = "ja_JP"
    ARABIC = "ar_MA"

# Supported currencies
class Currency(str, Enum):
    """Supported currencies for AliExpress."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    RUB = "RUB"
    JPY = "JPY"
    KRW = "KRW"
    BRL = "BRL"
    MXN = "MXN"
    TRY = "TRY"
    INR = "INR"

# Sorting options
class SortOption(str, Enum):
    """Sort options for AliExpress search."""
    BEST_MATCH = "bestmatch"
    ORDERS = "orders"
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "feedback"

# Shipping options
class ShippingOption(str, Enum):
    """Shipping options for AliExpress search."""
    FREE_SHIPPING = "y"
    FOUR_DAY = "fs_0_fday"
    TEN_DAY = "fs_0_m10d"
    FIFTEEN_DAY = "fs_0_m15d"

# HTML Selectors - for web scraping
class Selectors:
    """HTML selectors for AliExpress pages."""
    
    # Search page selectors
    SEARCH_RESULTS_CONTAINER = ".JIIxO"
    PRODUCT_ITEM = ".Manhattan--container--1lP57Ag"
    PRODUCT_LINK = "a[href*='/item/']"
    PRODUCT_TITLE = ".Manhattan--titleText--WccSjUS"
    PRODUCT_PRICE = ".Manhattan--price--WTyAPsU"
    PRODUCT_ORIGINAL_PRICE = ".Manhattan--price-original--1kPJf6j"
    PRODUCT_SHIPPING = ".Manhattan--trade--2PeJIEB"
    PRODUCT_RATINGS = ".Manhattan--evaluation--3cSMUCf"
    PRODUCT_ORDERS = ".Manhattan--trade--2PeJIEB"
    PRODUCT_IMAGE = ".Manhattan--img--2a1yvje"
    
    # Pagination
    PAGINATION_CONTAINER = ".Pagination--pagination--2Xo5jv9"
    PAGINATION_NEXT = ".Pagination--next--2Yu8syA"
    PAGINATION_PREV = ".Pagination--prev--2O4HlCj"
    PAGINATION_CURRENT = ".Pagination--active--QH5zzGg"
    PAGINATION_TOTAL = ".Pagination--pageTotal--3JgG6k8"
    
    # Product detail page selectors
    PRODUCT_DETAIL_TITLE = ".product-title-text"
    PRODUCT_DETAIL_PRICE = ".uniform-banner-box-price"
    PRODUCT_DETAIL_ORIGINAL_PRICE = ".uniform-banner-box-discounts"
    PRODUCT_DETAIL_SHIPPING_INFO = ".product-shipping-info"
    PRODUCT_DETAIL_SELLER = ".shop-name"
    PRODUCT_DETAIL_RATING = ".overview-rating-average"
    PRODUCT_DETAIL_REVIEWS_COUNT = ".product-reviewer-reviews"
    PRODUCT_DETAIL_ORDERS_COUNT = ".product-reviewer-sold"
    
    # Product variants
    PRODUCT_VARIANTS_CONTAINER = ".sku-property-list"
    PRODUCT_VARIANT_ITEM = ".sku-property-item"
    PRODUCT_VARIANT_NAME = ".sku-property-name"
    PRODUCT_VARIANT_VALUE = ".sku-property-value"
    
    # Product description
    PRODUCT_DESCRIPTION = ".product-description"
    PRODUCT_SPECS = ".specification"
    
    # Seller information
    SELLER_INFO_CONTAINER = ".store-info"
    SELLER_NAME = ".shop-name"
    SELLER_POSITIVE_FEEDBACK = ".positive-feedback"
    SELLER_FOLLOWERS = ".follower-count"
    
    # Reviews
    REVIEWS_CONTAINER = ".feedback-list-wrap"
    REVIEW_ITEM = ".feedback-item"
    REVIEW_RATING = ".fb-star"
    REVIEW_CONTENT = ".fb-main"
    REVIEW_AUTHOR = ".user-name"
    REVIEW_DATE = ".feedback-time"
    
    # Mobile selectors (sometimes simpler)
    MOBILE_PRODUCT_ITEM = ".product-item"
    MOBILE_PRODUCT_LINK = ".product-link"
    MOBILE_PRODUCT_TITLE = ".product-title"
    MOBILE_PRODUCT_PRICE = ".product-price-value"

# Error messages
ERROR_MESSAGES = {
    "CONNECTION_ERROR": "Failed to connect to AliExpress",
    "TIMEOUT_ERROR": "Request timed out while connecting to AliExpress",
    "PARSING_ERROR": "Failed to parse AliExpress response",
    "RATE_LIMIT_ERROR": "Rate limit exceeded for AliExpress",
    "ITEM_NOT_FOUND": "Item not found on AliExpress",
    "INVALID_RESPONSE": "Received invalid response from AliExpress",
    "CAPTCHA_DETECTED": "Captcha detection triggered on AliExpress",
    "REGION_BLOCKED": "Access from your region may be restricted",
    "LOGIN_REQUIRED": "Login required to access this content",
}

# Anti-bot detection strings - used to check if we've been blocked
ANTI_BOT_MARKERS = [
    "captcha",
    "verify",
    "security check",
    "human verification",
    "robot",
    "suspicious activity",
    "unusual traffic",
    "blocked",
]

# Common categories on AliExpress
COMMON_CATEGORIES = {
    "consumer_electronics": "44",
    "phones": "509",
    "computer": "7",
    "home_appliances": "6",
    "home_garden": "15",
    "furniture": "1503",
    "toys_hobbies": "26",
    "sports": "18",
    "beauty_health": "66",
    "automobiles": "34",
    "tools": "13",
    "watches": "1511",
    "lights": "39",
    "jewelry": "1509",
    "shoes": "322",
    "men_clothing": "4",
    "women_clothing": "3",
}

# Common parameters for search requests
SEARCH_PARAMS = {
    "SortType": "default",
    "page": "1",
    "CatId": "0",
    "g": "y",  # Ships to parameter
    "needQuery": "n",
    "isrefine": "y",
}

# GraphQL queries (for product details and other data)
PRODUCT_DETAIL_QUERY = """
query DetailPageQuery($id: String!) {
  item(id: $id) {
    itemId
    title
    description
    price {
      amount
      currency
    }
    originalPrice {
      amount
      currency
    }
    discount
    shipping {
      method
      cost {
        amount
        currency
      }
      deliveryTime
    }
    seller {
      name
      storeId
      positiveRating
      followers
    }
    specs {
      name
      value
    }
    variants {
      name
      values {
        id
        name
        image
        price {
          amount
          currency
        }
        available
      }
    }
    reviews {
      total
      averageRating
      fiveStarCount
      fourStarCount
      threeStarCount
      twoStarCount
      oneStarCount
    }
  }
}
"""

# List of countries/regions supported by AliExpress
SUPPORTED_REGIONS = [
    "US", "UK", "CA", "AU", "RU", "ES", "FR", "DE", "IT", "BR",
    "NL", "TR", "PL", "IL", "SE", "CH", "AT", "BE", "DK", "NO",
    "FI", "GR", "PT", "IE", "NZ", "MX", "CL", "CO", "PE", "AR",
    "JP", "KR", "SG", "MY", "TH", "VN", "PH", "ID", "AE", "SA"
]

# Common filters used in searches
class FilterOption(str, Enum):
    """Filter options for AliExpress search."""
    FOUR_STAR_UP = "4*"
    FAST_SHIPPING = "Fast"
    FREE_RETURN = "return"
    CASH_ON_DELIVERY = "COD"
    READY_TO_SHIP = "RTS"
    DROPSHIPPING = "DS"
    OVERSEAS = "OS"

