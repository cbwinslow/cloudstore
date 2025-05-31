"""
Constants and configuration settings for the eBay API crawler.

This module contains API endpoints, authentication settings, rate limits,
and other configuration constants needed for interacting with eBay's APIs.
"""

from enum import Enum
from typing import Dict, List, Optional, Set

# API Base URLs - Different environments
PRODUCTION_BASE_URL = "https://api.ebay.com"
SANDBOX_BASE_URL = "https://api.sandbox.ebay.com"

# OAuth endpoints
OAUTH_API_SCOPE = "https://api.ebay.com/oauth/api_scope"
OAUTH_API_SCOPE_SELL_INVENTORY = "https://api.ebay.com/oauth/api_scope/sell.inventory"
OAUTH_API_SCOPE_SELL_MARKETING = "https://api.ebay.com/oauth/api_scope/sell.marketing"
OAUTH_API_SCOPE_SELL_ACCOUNT = "https://api.ebay.com/oauth/api_scope/sell.account"
OAUTH_API_SCOPE_COMMERCE_NOTIFICATION = "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription"

# OAuth URLs
OAUTH_PROD_URL = "https://auth.ebay.com/oauth2/authorize"
OAUTH_SANDBOX_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
OAUTH_PROD_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
OAUTH_SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

# API Endpoints
# Finding API (searching for items)
FINDING_API_URL = "/services/search/FindingService/v1"
# Shopping API (getting item details)
SHOPPING_API_URL = "/shopping"
# Browse API (getting item details - newer API)
BROWSE_API_URL = "/buy/browse/v1"
# Inventory API
INVENTORY_API_URL = "/sell/inventory/v1"
# Taxonomy API (categories)
TAXONOMY_API_URL = "/commerce/taxonomy/v1"

# API Version
API_VERSION = "v1.13.0"
COMPATIBILITY_LEVEL = "1155"  # For Shopping API

# HTTP Headers
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_XML = "application/xml"
CONTENT_TYPE_URLENCODED = "application/x-www-form-urlencoded"

# Rate Limits
# As per eBay documentation: https://developer.ebay.com/api-docs/static/api-call-limits.html
FINDING_API_RATE_LIMIT = 5  # Calls per second
FINDING_API_DAILY_LIMIT = 5000  # Calls per day
SHOPPING_API_RATE_LIMIT = 5  # Calls per second
SHOPPING_API_DAILY_LIMIT = 5000  # Calls per day
BROWSE_API_RATE_LIMIT = 5  # Calls per second
BROWSE_API_DAILY_LIMIT = 5000  # Calls per day
TAXONOMY_API_RATE_LIMIT = 5  # Calls per second
TAXONOMY_API_DAILY_LIMIT = 1000  # Calls per day

# Retry Configuration
RETRY_ATTEMPTS = 3  # Number of retry attempts
RETRY_BACKOFF = 2.0  # Exponential backoff multiplier
REQUEST_TIMEOUT = 30  # Seconds

# Default request parameters
DEFAULT_ITEMS_PER_PAGE = 100  # Maximum allowed by eBay
MAX_PAGES = 100  # Maximum pages to fetch in pagination
MAX_ENTRIES_PER_PAGE = 100  # Maximum allowed by eBay for most APIs

# Sorting options
class SortOrder(str, Enum):
    """Sort order options for eBay API."""
    BEST_MATCH = "BestMatch"
    ENDING_SOONEST = "EndTimeSoonest"
    NEWLY_LISTED = "StartTimeNewest"
    PRICE_PLUS_SHIPPING_LOWEST = "PricePlusShippingLowest"
    PRICE_PLUS_SHIPPING_HIGHEST = "PricePlusShippingHighest"
    CURRENT_PRICE_HIGHEST = "CurrentPriceHighest"
    DISTANCE_NEAREST = "DistanceNearest"

# Item condition options
class ConditionId(int, Enum):
    """Item condition IDs for eBay API."""
    NEW = 1000
    NEW_OTHER = 1500
    NEW_WITH_DEFECTS = 1750
    MANUFACTURER_REFURBISHED = 2000
    SELLER_REFURBISHED = 2500
    USED_EXCELLENT = 3000
    USED_VERY_GOOD = 4000
    USED_GOOD = 5000
    USED_ACCEPTABLE = 6000
    FOR_PARTS_OR_NOT_WORKING = 7000

# Item condition names
CONDITION_NAMES = {
    ConditionId.NEW: "New",
    ConditionId.NEW_OTHER: "New - Other",
    ConditionId.NEW_WITH_DEFECTS: "New with defects",
    ConditionId.MANUFACTURER_REFURBISHED: "Manufacturer refurbished",
    ConditionId.SELLER_REFURBISHED: "Seller refurbished",
    ConditionId.USED_EXCELLENT: "Used - Excellent",
    ConditionId.USED_VERY_GOOD: "Used - Very Good",
    ConditionId.USED_GOOD: "Used - Good",
    ConditionId.USED_ACCEPTABLE: "Used - Acceptable",
    ConditionId.FOR_PARTS_OR_NOT_WORKING: "For parts or not working",
}

# Item filters
class ItemFilter(str, Enum):
    """Filter options for eBay API."""
    CONDITION = "Condition"
    PRICE = "Price"
    BEST_OFFER_ONLY = "BestOfferOnly"
    BUY_IT_NOW_ONLY = "BuyItNowOnly"
    CHARITY_ONLY = "CharityOnly"
    FREE_SHIPPING_ONLY = "FreeShippingOnly"
    SOLD_ITEMS_ONLY = "SoldItemsOnly"
    COMPLETED_ITEMS_ONLY = "CompletedItemsOnly"
    LISTED_IN = "ListedIn"
    MAX_BIDS = "MaxBids"
    MIN_BIDS = "MinBids"
    MAX_PRICE = "MaxPrice"
    MIN_PRICE = "MinPrice"
    MAX_DISTANCE = "MaxDistance"
    AUTHORIZED_SELLER_ONLY = "AuthorizedSellerOnly"
    AVAILABLE_TO = "AvailableTo"
    EXCLUDED_SELLER = "ExcludeSeller"
    FEATURED_ONLY = "FeaturedOnly"
    FEEDBACK_SCORE_MIN = "FeedbackScoreMin"
    GET_IT_FAST_ONLY = "GetItFastOnly"
    HIDE_DUPLICATE_ITEMS = "HideDuplicateItems"
    LISTED_ONLY = "ListedOnly"
    LOCAL_PICKUP_ONLY = "LocalPickupOnly"
    LOCAL_SEARCH_ONLY = "LocalSearchOnly"
    LOTS_ONLY = "LotsOnly"
    MAX_HANDLING_TIME = "MaxHandlingTime"
    MAX_QUANTITY = "MaxQuantity"
    MIN_QUANTITY = "MinQuantity"
    PAYMENT_METHOD = "PaymentMethod"
    RETURNS_ACCEPTED_ONLY = "ReturnsAcceptedOnly"
    SELLER = "Seller"
    TOP_RATED_SELLER_ONLY = "TopRatedSellerOnly"

# Global ID values (marketplaces)
class GlobalId(str, Enum):
    """Global IDs for different eBay marketplaces."""
    EBAY_US = "EBAY-US"
    EBAY_AUSTRALIA = "EBAY-AU"
    EBAY_AUSTRIA = "EBAY-AT"
    EBAY_BELGIUM_DUTCH = "EBAY-NLBE"
    EBAY_BELGIUM_FRENCH = "EBAY-FRBE"
    EBAY_CANADA = "EBAY-CA"
    EBAY_CANADA_FRENCH = "EBAY-FRCA"
    EBAY_FRANCE = "EBAY-FR"
    EBAY_GERMANY = "EBAY-DE"
    EBAY_HONG_KONG = "EBAY-HK"
    EBAY_INDIA = "EBAY-IN"
    EBAY_IRELAND = "EBAY-IE"
    EBAY_ITALY = "EBAY-IT"
    EBAY_MALAYSIA = "EBAY-MY"
    EBAY_NETHERLANDS = "EBAY-NL"
    EBAY_PHILIPPINES = "EBAY-PH"
    EBAY_POLAND = "EBAY-PL"
    EBAY_SINGAPORE = "EBAY-SG"
    EBAY_SPAIN = "EBAY-ES"
    EBAY_SWITZERLAND = "EBAY-CH"
    EBAY_UK = "EBAY-GB"

# Error messages and codes
ERROR_MESSAGES = {
    # Authentication errors
    "AUTH_ERROR": "Authentication failed with eBay API",
    "TOKEN_EXPIRED": "OAuth token expired",
    "INVALID_CREDENTIALS": "Invalid eBay API credentials",
    
    # Rate limiting
    "RATE_LIMIT_EXCEEDED": "eBay API rate limit exceeded",
    "DAILY_LIMIT_EXCEEDED": "eBay API daily call limit exceeded",
    
    # Request errors
    "CONNECTION_ERROR": "Failed to connect to eBay API",
    "TIMEOUT_ERROR": "Request timed out while connecting to eBay API",
    "INVALID_REQUEST": "Invalid request parameters",
    
    # Item errors
    "ITEM_NOT_FOUND": "Item not found on eBay",
    "CATEGORY_NOT_FOUND": "Category not found on eBay",
    
    # Response parsing
    "PARSING_ERROR": "Failed to parse eBay API response",
    "UNEXPECTED_RESPONSE": "Received unexpected response from eBay API",
}

# Common eBay API error codes
ERROR_CODES = {
    # System errors
    "1": "Request processing failed due to internal error",
    "10007": "Invalid request parameters",
    "10000": "Unknown eBay internal error",
    
    # Authentication errors
    "931": "Authentication token is invalid or expired",
    "17470": "User credentials invalid",
    "21916884": "Auth token expired",
    
    # Rate limiting
    "218050": "Rate limit exceeded",
    "218053": "Daily call limit exceeded",
    
    # Item errors
    "35": "Item not found",
    "37": "No site ID specified",
    "36": "Category not found",
}

# Default headers for API requests
DEFAULT_HEADERS = {
    "User-Agent": "CloudStore-eBay-Crawler/1.0.0",
    "X-EBAY-API-SITE-ID": "0",  # US site
    "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
    "X-EBAY-API-APP-NAME": "",  # Will be set from config
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# eBay API Operations
class FindingApiOperation(str, Enum):
    """Operations for eBay Finding API."""
    FIND_ITEMS_ADVANCED = "findItemsAdvanced"
    FIND_ITEMS_BY_CATEGORY = "findItemsByCategory"
    FIND_ITEMS_BY_KEYWORDS = "findItemsByKeywords"
    FIND_ITEMS_BY_PRODUCT = "findItemsByProduct"
    FIND_ITEMS_IN_EBAY_STORES = "findItemsIneBayStores"
    GET_SEARCH_KEYWORDS_RECOMMENDATION = "getSearchKeywordsRecommendation"
    GET_HISTOGRAMS = "getHistograms"

class ShoppingApiOperation(str, Enum):
    """Operations for eBay Shopping API."""
    GET_SINGLE_ITEM = "GetSingleItem"
    GET_ITEM_STATUS = "GetItemStatus"
    GET_SHIPPING_COSTS = "GetShippingCosts"
    FIND_PRODUCTS = "FindProducts"
    FIND_HALF_PRODUCTS = "FindHalfProducts"
    GET_CATEGORY_INFO = "GetCategoryInfo"
    GET_EBAY_TIME = "GeteBayTime"
    GET_USER_PROFILE = "GetUserProfile"

