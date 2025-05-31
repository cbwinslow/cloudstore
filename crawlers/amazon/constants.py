"""
Constants and configuration settings for the Amazon crawler.

This module contains API endpoints, rate limits, regions, HTML selectors,
and other configuration constants needed for interacting with Amazon.
Supports both Product Advertising API and web scraping approaches.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Set

# Region configurations (country-specific)
class Region(str, Enum):
    """Amazon marketplace regions."""
    US = "US"
    CA = "CA"
    UK = "UK"
    DE = "DE"
    FR = "FR"
    ES = "ES"
    IT = "IT"
    JP = "JP"
    AU = "AU"
    IN = "IN"
    MX = "MX"
    BR = "BR"
    AE = "AE"
    SG = "SG"

# Map of region codes to base domains
REGION_DOMAINS = {
    Region.US: "amazon.com",
    Region.CA: "amazon.ca",
    Region.UK: "amazon.co.uk",
    Region.DE: "amazon.de",
    Region.FR: "amazon.fr",
    Region.ES: "amazon.es",
    Region.IT: "amazon.it",
    Region.JP: "amazon.co.jp",
    Region.AU: "amazon.com.au",
    Region.IN: "amazon.in",
    Region.MX: "amazon.com.mx",
    Region.BR: "amazon.com.br",
    Region.AE: "amazon.ae",
    Region.SG: "amazon.sg",
}

# Base URLs - Different regions and domains
def get_base_url(region: Region = Region.US) -> str:
    """Get base URL for a specific region."""
    domain = REGION_DOMAINS.get(region, REGION_DOMAINS[Region.US])
    return f"https://www.{domain}"

def get_mobile_url(region: Region = Region.US) -> str:
    """Get mobile base URL for a specific region."""
    domain = REGION_DOMAINS.get(region, REGION_DOMAINS[Region.US])
    return f"https://m.{domain}"

# Default region
DEFAULT_REGION = Region.US

# Product Advertising API endpoints by region
PA_API_HOSTS = {
    Region.US: "webservices.amazon.com",
    Region.CA: "webservices.amazon.ca",
    Region.UK: "webservices.amazon.co.uk",
    Region.DE: "webservices.amazon.de",
    Region.FR: "webservices.amazon.fr",
    Region.ES: "webservices.amazon.es",
    Region.IT: "webservices.amazon.it",
    Region.JP: "webservices.amazon.co.jp",
    Region.AU: "webservices.amazon.com.au",
    Region.IN: "webservices.amazon.in",
    Region.MX: "webservices.amazon.com.mx",
    Region.BR: "webservices.amazon.com.br",
    Region.AE: "webservices.amazon.ae",
    Region.SG: "webservices.amazon.sg",
}

# PA-API version
PAAPI_VERSION = "5.0"

# PA-API operations
PAAPI_SEARCH_ITEMS = "SearchItems"
PAAPI_GET_ITEMS = "GetItems"
PAAPI_GET_VARIATIONS = "GetVariations"
PAAPI_GET_BROWSE_NODES = "GetBrowseNodes"

# PA-API resource paths
def get_paapi_endpoint(region: Region = Region.US, operation: str = PAAPI_SEARCH_ITEMS) -> str:
    """Get Product Advertising API endpoint for a specific region and operation."""
    host = PA_API_HOSTS.get(region, PA_API_HOSTS[Region.US])
    return f"https://{host}/paapi5/{operation.lower()}"

# API default resources to request
DEFAULT_RESOURCES = [
    "Images.Primary.Medium",
    "Images.Primary.Large",
    "Images.Variants.Medium",
    "ItemInfo.Title",
    "ItemInfo.Features",
    "ItemInfo.ProductInfo",
    "ItemInfo.ByLineInfo",
    "ItemInfo.ContentInfo",
    "ItemInfo.ExternalIds",
    "ItemInfo.ManufactureInfo",
    "ItemInfo.TechnicalInfo",
    "ItemInfo.ContentRating",
    "ItemInfo.TradeInInfo",
    "Offers.Listings.Price",
    "Offers.Listings.Availability",
    "Offers.Listings.Condition",
    "Offers.Listings.DeliveryInfo.IsPrimeEligible",
    "Offers.Listings.PromotionIds",
    "Offers.Summaries.LowestPrice",
    "OfferCount",
    "ParentASIN",
    "RentalOffers.Listings.Price",
    "BrowseNodeInfo.BrowseNodes",
    "BrowseNodeInfo.WebsiteSalesRank",
    "CustomerReviews.Count",
    "CustomerReviews.StarRating",
]

# Web scraping URLs and patterns
SEARCH_PATH = "/s"
PRODUCT_PATH = "/dp/"
REVIEWS_PATH = "/product-reviews/"
BROWSE_NODES_PATH = "/gp/browse/"

# URL patterns for extraction
ASIN_PATTERN = r"/dp/([A-Z0-9]{10})(?:/|\?|$)"
ASIN_REGEX = re.compile(ASIN_PATTERN)

# Rate limiting configurations
# PA-API has a default of 1 request per second
PA_API_RATE_LIMIT = 1  # Requests per second
PA_API_BURST_LIMIT = 2  # Allow small burst

# Web scraping rate limits should be very conservative
WEB_RATE_LIMIT = 1/5  # One request per 5 seconds
WEB_BURST_LIMIT = 2

# Retry settings
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2.0
REQUEST_TIMEOUT = 30  # Seconds

# Delay settings
DELAY_BETWEEN_REQUESTS = 5  # Seconds
RANDOM_DELAY_RANGE = (3, 10)  # Random delay range in seconds

# Amazon search parameters
class SortBy(str, Enum):
    """Sort options for Amazon search."""
    FEATURED = "featured-rank"
    PRICE_LOW_HIGH = "price-asc-rank"
    PRICE_HIGH_LOW = "price-desc-rank"
    CUSTOMER_REVIEW = "review-rank"
    NEWEST_ARRIVALS = "date-desc-rank"
    BEST_SELLER = "bestseller-rank"

# Condition filter options
class Condition(str, Enum):
    """Product condition options."""
    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"
    COLLECTIBLE = "collectible"

# Prime filter
class PrimeEligible(str, Enum):
    """Prime eligibility options."""
    YES = "yes"
    NO = "no"

# Category/Department mapping - common top-level departments
DEPARTMENTS = {
    "All": "all",
    "Arts & Crafts": "arts-crafts",
    "Automotive": "automotive",
    "Baby": "baby-products",
    "Beauty & Personal Care": "beauty",
    "Books": "stripbooks",
    "Computers": "computers",
    "Digital Music": "digital-music",
    "Electronics": "electronics",
    "Fashion": "fashion",
    "Garden & Outdoor": "lawngarden",
    "Grocery & Gourmet Food": "grocery",
    "Handmade": "handmade",
    "Health & Household": "hpc",
    "Home & Kitchen": "garden",
    "Industrial & Scientific": "industrial",
    "Kindle Store": "digital-text",
    "Movies & TV": "movies-tv",
    "Music, CDs & Vinyl": "music",
    "Office Products": "office-products",
    "Pet Supplies": "pets",
    "Sports & Outdoors": "sporting",
    "Tools & Home Improvement": "tools",
    "Toys & Games": "toys",
    "Video Games": "videogames",
}

# Default request parameters
DEFAULT_ITEMS_PER_PAGE = 10  # Default items per page for PA-API
WEB_ITEMS_PER_PAGE = 48  # Default items shown on web search page
MAX_PAGES = 20  # Maximum pages to fetch in pagination

# HTTP headers for web scraping
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
}

# Mobile headers to mimic mobile device
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}

# Cookies needed for certain regions
DEFAULT_COOKIES = {
    "session-id": "123-4567890-1234567",  # Will be replaced with real session
    "i18n-prefs": "USD",  # Currency
    "lc-main": "en_US",  # Language
}

# HTML selectors for web scraping - main elements
class Selectors:
    """HTML selectors for Amazon pages."""
    
    # Search results selectors
    SEARCH_RESULTS_CONTAINER = "div.s-main-slot"
    SEARCH_RESULT_ITEM = "div.s-result-item[data-asin]"
    SEARCH_RESULT_TITLE = "h2 a.a-text-normal"
    SEARCH_RESULT_LINK = "h2 a.a-text-normal"
    SEARCH_RESULT_PRICE = "span.a-price:not(.a-text-price) .a-offscreen"
    SEARCH_RESULT_ORIGINAL_PRICE = "span.a-price.a-text-price .a-offscreen"
    SEARCH_RESULT_RATING = "span.a-icon-alt"
    SEARCH_RESULT_REVIEWS_COUNT = "span.a-size-base.s-underline-text"
    SEARCH_RESULT_IMAGE = "img.s-image"
    SEARCH_RESULT_PRIME = "i.a-icon-prime"
    
    # Pagination selectors
    PAGINATION_CONTAINER = "ul.a-pagination"
    PAGINATION_CURRENT = "li.a-selected"
    PAGINATION_NEXT = "li.a-last a"
    PAGINATION_PREV = "li.a-first a"
    
    # Product detail selectors
    PRODUCT_TITLE = "span#productTitle"
    PRODUCT_PRICE = "span.a-price span.a-offscreen"
    PRODUCT_AVAILABILITY = "div#availability span"
    PRODUCT_DESCRIPTION = "div#productDescription"
    PRODUCT_DETAILS = "div#detailBullets_feature_div"
    PRODUCT_FEATURES = "div#feature-bullets"
    PRODUCT_IMAGES = "img#landingImage, ul.a-unordered-list li.image img"
    PRODUCT_RATING = "span.a-icon-alt"
    PRODUCT_REVIEW_COUNT = "span#acrCustomerReviewText"
    PRODUCT_VARIATIONS = "div#variation_"
    PRODUCT_SELLER = "div#merchant-info"
    PRODUCT_BRAND = "a#bylineInfo"
    
    # Review selectors
    REVIEWS_CONTAINER = "div#cm_cr-review_list"
    REVIEW_ITEM = "div.review"
    REVIEW_RATING = "i.review-rating"
    REVIEW_TITLE = "a.review-title"
    REVIEW_BODY = "span.review-text"
    REVIEW_AUTHOR = "span.a-profile-name"
    REVIEW_DATE = "span.review-date"
    
    # Mobile selectors (simpler structure)
    MOBILE_SEARCH_RESULT_ITEM = "div.s-result-item"
    MOBILE_PRODUCT_TITLE = "span.a-text-normal"
    MOBILE_PRODUCT_PRICE = "span.a-price span.a-offscreen"
    MOBILE_PRODUCT_LINK = "a.a-link-normal.a-text-normal"

# Error messages
ERROR_MESSAGES = {
    "CONNECTION_ERROR": "Failed to connect to Amazon",
    "TIMEOUT_ERROR": "Request timed out while connecting to Amazon",
    "PARSING_ERROR": "Failed to parse Amazon response",
    "RATE_LIMIT_ERROR": "Rate limit exceeded for Amazon",
    "ITEM_NOT_FOUND": "Item not found on Amazon",
    "INVALID_RESPONSE": "Received invalid response from Amazon",
    "CAPTCHA_DETECTED": "Captcha detection triggered on Amazon",
    "REGION_BLOCKED": "Access from your region may be restricted by Amazon",
    "API_ERROR": "Amazon API returned an error",
    "INVALID_CREDENTIALS": "Invalid Amazon API credentials",
    "MISSING_PARAMETERS": "Required parameters are missing",
}

# Anti-bot detection strings
ANTI_BOT_MARKERS = [
    "captcha",
    "robot",
    "human",
    "puzzle",
    "verify your identity",
    "verify you're a human",
    "automated access",
    "suspicious activity",
    "unusual traffic",
    "solve this puzzle",
]

# PA-API error codes
API_ERROR_CODES = {
    "InvalidInput": "The request contains an invalid parameter or combination of parameters",
    "InvalidSignature": "The signature for the request is invalid",
    "MissingParameter": "A required parameter is missing from the request",
    "TooManyRequests": "The request rate exceeds the limit",
    "RequestExpired": "The request timestamp is too old",
    "UnrecognizedClient": "The Access Key ID or security token is invalid",
    "AccessDenied": "The AWS access key ID or security token used in the request is invalid",
    "ItemNotAccessible": "The item requested is not accessible through the Product Advertising API",
    "IncompleteSignature": "The request signature does not conform to AWS standards",
    "InvalidParameterValue": "The specified parameter value is invalid",
    "ServiceUnavailable": "The service is currently unavailable or busy",
}

# Language support
class Language(str, Enum):
    """Supported languages for Amazon."""
    ENGLISH = "en_US"
    SPANISH = "es_ES"
    FRENCH = "fr_FR"
    GERMAN = "de_DE"
    ITALIAN = "it_IT"
    PORTUGUESE = "pt_BR"
    JAPANESE = "ja_JP"
    CHINESE = "zh_CN"
    ARABIC = "ar_AE"
