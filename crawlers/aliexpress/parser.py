"""
HTML and JSON Parser for AliExpress.

This module provides parser classes for extracting structured data from 
AliExpress HTML pages and JSON responses, with support for both desktop and mobile versions.
"""

import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
import jmespath

from .constants import (
    Selectors, BASE_URL, MOBILE_BASE_URL, ANTI_BOT_MARKERS, PRODUCT_URL_PATTERN,
    ERROR_MESSAGES, Currency, Language
)
from .models import (
    Money, Price, Image, ShippingMethod, ShippingInfo, SellerInfo, 
    ReviewRating, Review, VariationOption, Variation, BasicProduct, 
    DetailedProduct, Category, SearchPagination, SearchResult
)

# Configure logger
logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Exception raised when parsing fails."""
    pass


class AntiBot(Exception):
    """Exception raised when anti-bot measures are detected."""
    pass


def clean_text(text: Optional[str]) -> str:
    """
    Clean text by removing extra whitespace and normalizing.
    
    Args:
        text: The text to clean
        
    Returns:
        Cleaned text string
    """
    if text is None:
        return ""
    return " ".join(text.strip().split())


def extract_price(price_text: Optional[str]) -> Optional[Decimal]:
    """
    Extract a price value from text containing a price.
    
    Args:
        price_text: Text containing a price (e.g., "$10.99", "US $15.99")
        
    Returns:
        Decimal price or None if no valid price found
    """
    if not price_text:
        return None
    
    # Extract digits and decimal point
    price_match = re.search(r'(?:US)?\s*\$?\s*(\d+(?:[.,]\d{1,2})?)', price_text)
    if price_match:
        try:
            # Replace comma with dot for decimal separator in some regions
            price_str = price_match.group(1).replace(',', '.')
            return Decimal(price_str)
        except Exception as e:
            logger.warning(f"Failed to parse price from '{price_text}': {e}")
    
    return None


def extract_currency(price_text: Optional[str]) -> Currency:
    """
    Extract currency from price text.
    
    Args:
        price_text: Text containing a price with currency
        
    Returns:
        Currency enum value (defaults to USD if not found)
    """
    if not price_text:
        return Currency.USD
    
    currency_map = {
        '$': Currency.USD,
        '€': Currency.EUR,
        '£': Currency.GBP,
        '¥': Currency.JPY,
        '₽': Currency.RUB,
        'C$': Currency.CAD,
        'A$': Currency.AUD,
        '₹': Currency.INR,
        'R$': Currency.BRL,
        '₺': Currency.TRY,
        '₩': Currency.KRW,
        'MX$': Currency.MXN,
    }
    
    for symbol, currency in currency_map.items():
        if symbol in price_text:
            return currency
    
    # Default to USD
    return Currency.USD


def extract_product_id(url: str) -> Optional[str]:
    """
    Extract the product ID from an AliExpress item URL.
    
    Args:
        url: URL of the item
        
    Returns:
        Product ID as string or None if no valid ID found
    """
    if not url:
        return None
    
    # Extract item ID from URL like /item/12345.html or /i/12345.html
    item_match = re.search(r'/(?:item|i)/(\d+)\.html', url)
    if item_match:
        return item_match.group(1)
    
    return None


def check_for_anti_bot(html_content: str) -> bool:
    """
    Check if the response contains anti-bot measures.
    
    Args:
        html_content: HTML content to check
        
    Returns:
        True if anti-bot measures detected, False otherwise
    """
    if not html_content:
        return False
    
    html_lower = html_content.lower()
    
    # Check for common anti-bot markers
    for marker in ANTI_BOT_MARKERS:
        if marker.lower() in html_lower:
            return True
    
    # Check for captcha forms
    if 'captcha' in html_lower or 'g-recaptcha' in html_lower:
        return True
    
    # Check for suspicious redirects
    if 'suspicious' in html_lower and ('activity' in html_lower or 'behavior' in html_lower):
        return True
    
    # Check for blocks
    if 'blocked' in html_lower or 'banned' in html_lower:
        return True
    
    return False


def normalize_url(url: str, base_url: str = BASE_URL) -> str:
    """
    Normalize a URL by ensuring it has the proper base URL.
    
    Args:
        url: URL to normalize
        base_url: Base URL to use if the URL is relative
        
    Returns:
        Normalized URL
    """
    if not url:
        return ""
    
    # Check if the URL is relative
    if not url.startswith(('http://', 'https://')):
        # Check if it's a root-relative URL
        if url.startswith('/'):
            return urljoin(base_url, url)
        else:
            return f"{base_url}/{url}"
    
    return url


def extract_json_data(html_content: str, pattern: str = r'window\._init_data_\s*=\s*({.*?});') -> Optional[Dict]:
    """
    Extract JSON data embedded in the HTML.
    
    Args:
        html_content: HTML content
        pattern: Regex pattern to extract JSON
        
    Returns:
        Extracted JSON data as dictionary or None if not found
    """
    if not html_content:
        return None
    
    try:
        # Find the JavaScript data
        matches = re.search(pattern, html_content, re.DOTALL)
        if not matches:
            logger.warning("No embedded JSON data found")
            return None
        
        # Extract and parse the JSON
        json_str = matches.group(1)
        data = json.loads(json_str)
        return data
    except Exception as e:
        logger.warning(f"Failed to extract JSON data: {e}")
        return None


class BaseParser:
    """Base class for all AliExpress parsers."""
    
    def __init__(self, html_content: str, is_mobile: bool = False):
        """
        Initialize the parser with HTML content.
        
        Args:
            html_content: Raw HTML content to parse
            is_mobile: Whether the content is from the mobile site
        """
        self.html_content = html_content
        self.is_mobile = is_mobile
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.base_url = MOBILE_BASE_URL if is_mobile else BASE_URL
        
        # Detect anti-bot measures
        if check_for_anti_bot(html_content):
            logger.warning("Anti-bot measures detected in response")
            raise AntiBot(ERROR_MESSAGES["CAPTCHA_DETECTED"])
        
        # Extract embedded JSON data
        self.json_data = extract_json_data(html_content)
        
    def _get_text(self, selector: str, default: str = "") -> str:
        """
        Get text content from an element.
        
        Args:
            selector: CSS selector for the element
            default: Default value if element not found
            
        Returns:
            Text content of the element or default value
        """
        element = self.soup.select_one(selector)
        if element:
            return clean_text(element.text)
        return default
    
    def _get_attribute(self, selector: str, attribute: str, default: str = "") -> str:
        """
        Get attribute value from an element.
        
        Args:
            selector: CSS selector for the element
            attribute: Name of the attribute to get
            default: Default value if element or attribute not found
            
        Returns:
            Attribute value or default
        """
        element = self.soup.select_one(selector)
        if element and element.has_attr(attribute):
            return element[attribute]
        return default
    
    def _get_json_value(self, path: str, default: Any = None) -> Any:
        """
        Get a value from the extracted JSON data using jmespath.
        
        Args:
            path: JMESPath expression to extract data
            default: Default value if path not found
            
        Returns:
            Extracted value or default
        """
        if not self.json_data:
            return default
        
        try:
            result = jmespath.search(path, self.json_data)
            return result if result is not None else default
        except Exception as e:
            logger.warning(f"Failed to extract JSON value at path '{path}': {e}")
            return default
    
    def validate_response(self) -> bool:
        """
        Validate that the HTML response is a valid AliExpress page.
        
        Returns:
            True if valid, False otherwise
        """
        # Check if page contains AliExpress header or common elements
        if self.soup.title and "AliExpress" in self.soup.title.text:
            return True
        
        # Check if page contains AliExpress logo or navigation
        logo = self.soup.select_one("a.logo-base")
        if logo:
            return True
        
        # Check for common AliExpress page elements
        common_elements = [
            ".top-lighthouse", 
            ".ali-header", 
            ".site-nav-aliexpress",
            ".mobile-header"  # Mobile site
        ]
        
        for selector in common_elements:
            if self.soup.select_one(selector):
                return True
        
        return False


class ProductListingParser(BaseParser):
    """Parser for AliExpress search results/listings."""
    
    def parse_listings(self) -> SearchResult:
        """
        Parse product listings from search results page.
        
        Returns:
            SearchResult object with parsed products and pagination info
        """
        if not self.validate_response():
            logger.error("Invalid AliExpress search results page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        products = []
        
        # Choose selectors based on site version
        container_selector = Selectors.MOBILE_PRODUCT_ITEM if self.is_mobile else Selectors.PRODUCT_ITEM
        product_elements = self.soup.select(container_selector)
        
        if not product_elements:
            # Try to parse from JSON data if available
            if self.json_data:
                return self._parse_listings_from_json()
            
            logger.warning("No product listings found on page")
            return SearchResult(
                products=[],
                pagination=SearchPagination(page=1, total_pages=1, items_per_page=0)
            )
        
        for product_element in product_elements:
            try:
                product_data = self._parse_product(product_element)
                if product_data:
                    products.append(product_data)
            except Exception as e:
                logger.warning(f"Error parsing product listing: {e}")
                continue
        
        # Parse pagination info
        pagination = self._parse_pagination()
        
        # Create search result
        search_query = self._get_text("input[name='SearchText']")
        category_id = None
        category_name = None
        
        # Try to extract category info
        category_breadcrumb = self.soup.select_one(".breadcrumb-list")
        if category_breadcrumb:
            last_category = category_breadcrumb.select("a")[-1] if category_breadcrumb.select("a") else None
            if last_category:
                category_name = clean_text(last_category.text)
                category_url = last_category.get("href", "")
                category_match = re.search(r'category/(\d+)', category_url)
                if category_match:
                    category_id = category_match.group(1)
        
        return SearchResult(
            products=products,
            pagination=pagination,
            query=search_query,
            category_id=category_id,
            category_name=category_name,
            sort_by=self._extract_sort_order()
        )
    
    def _parse_listings_from_json(self) -> SearchResult:
        """
        Parse product listings from embedded JSON data.
        
        Returns:
            SearchResult object with parsed products and pagination info
        """
        products = []
        
        # Try different JSON paths for products
        product_items = self._get_json_value("items", []) or self._get_json_value("data.items", [])
        
        if not product_items:
            logger.warning("No product items found in JSON data")
            return SearchResult(
                products=[],
                pagination=SearchPagination(page=1, total_pages=1, items_per_page=0)
            )
        
        for item in product_items:
            try:
                product = self._parse_product_from_json(item)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing product from JSON: {e}")
                continue
        
        # Parse pagination
        page = self._get_json_value("page.currentPage", 1)
        total_pages = self._get_json_value("page.totalPage", 1)
        items_per_page = len(product_items)
        total_items = self._get_json_value("page.totalResults", len(product_items))
        
        pagination = SearchPagination(
            page=page,
            total_pages=total_pages,
            items_per_page=items_per_page,
            total_items=total_items
        )
        
        # Extract query and category
        search_query = self._get_json_value("query", "")
        category_id = self._get_json_value("categoryId")
        category_name = self._get_json_value("categoryName")
        
        return SearchResult(
            products=products,
            pagination=pagination,
            query=search_query,
            category_id=category_id,
            category_name=category_name
        )
    
    def _parse_product(self, product_element: Tag) -> Optional[BasicProduct]:
        """
        Parse a single product element from search results.
        
        Args:
            product_element: BeautifulSoup Tag containing product data
            
        Returns:
            BasicProduct object or None if parsing fails
        """
        # Choose selectors based on site version
        link_selector = Selectors.MOBILE_PRODUCT_LINK if self.is_mobile else Selectors.PRODUCT_LINK
        title_selector = Selectors.MOBILE_PRODUCT_TITLE if self.is_mobile else Selectors.PRODUCT_TITLE
        price_selector = Selectors.MOBILE_PRODUCT_PRICE if self.is_mobile else Selectors.PRODUCT_PRICE
        
        # Extract link and ID
        link_element = product_element.select_one(link_selector)
        if not link_element or not link_element.has_attr('href'):
            return None
        
        relative_url = link_element['href']
        full_url = normalize_url(relative_url, self.base_url)
        product_id = extract_product_id(relative_url)
        
        if not product_id:
            logger.warning(f"Couldn't extract product ID from URL: {relative_url}")
            return None
        
        # Extract title
        title = clean_text(product_element.select_one(title_selector).text) if product_element.select_one(title_selector) else ""
        
        # Extract price
        price_element = product_element.select_one(price_selector)
        current_price = extract_price(price_element.text if price_element else None)
        currency = extract_currency(price_element.text if price_element else None)
        
        # Extract original price
        original_price_element = product_element.select_one(Selectors.PRODUCT_ORIGINAL_PRICE)
        original_price = None
        if original_price_element:
            original_price = extract_price(original_price_element.text)
        
        # Create price object
        price = Price(
            current=Money(value=current_price or Decimal('0'), currency=currency),
            original=Money(value=original_price, currency=currency) if original_price else None
        )
        
        # Extract image
        image_element = product_element.select_one(Selectors.PRODUCT_IMAGE if not self.is_mobile else "img")
        image_url = ""
        if image_element:
            image_url = image_element.get('src', image_element.get('data-src', ''))
            # Handle lazy-loaded images
            if not image_url and image_element.has_attr('data-lazy'):
                image_url = image_element['data-lazy']
        
        # Extract shipping info
        shipping_element = product_element.select_one(Selectors.PRODUCT_SHIPPING)
        shipping_text = clean_text(shipping_element.text) if shipping_element else ""
        shipping_price = None
        free_shipping = False
        
        if shipping_text:
            if "free shipping" in shipping_text.lower() or "free delivery" in shipping_text.lower():
                free_shipping = True
            else:
                shipping_price = extract_price(shipping_text)
        
        # Extract ratings
        rating_element = product_element.select_one(Selectors.PRODUCT_RATINGS)
        rating = None
        reviews_count = None
        
        if rating_element:
            rating_text = clean_text(rating_element.text)
            rating_match = re.search(r'([\d.]+)', rating_text)
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                    # Normalize rating to 5-star scale if it's on a different scale
                    if rating > 5:
                        rating = rating / 2
                except ValueError:
                    pass
            
            # Try to extract reviews count
            reviews_match = re.search(r'(\d+)\s+reviews', rating_text)
            if reviews_match:
                reviews_count = int(reviews_match.group(1))
        
        # Extract orders count
        orders_element = product_element.select_one(Selectors.PRODUCT_ORDERS)
        orders_count = None
        
        if orders_element:
            orders_text = clean_text(orders_element.text)
            orders_match = re.search(r'(\d+)\s+orders', orders_text)
            if orders_match:
                orders_count = int(orders_match.group(1))
        
        # Extract seller name
        seller_name = ""  # Not always available in search results
        
        return BasicProduct(
            product_id=product_id,
            title=title,
            url=full_url,
            price=price,
            image_url=image_url,
            shipping_price=Money(value=shipping_price, currency=currency) if shipping_price else None,
            free_shipping=free_shipping,
            rating=rating,
            reviews_count=reviews_count,
            orders_count=orders_count,
            seller_name=seller_name
        )
    
    def _parse_product_from_json(self, item_data: Dict[str, Any]) -> Optional[BasicProduct]:
        """
        Parse a product from JSON data.
        
        Args:
            item_data: Product data from JSON
            
        Returns:
            BasicProduct object or None if parsing fails
        """
        # Extract product ID
        product_id = str(item_data.get("productId", ""))
        if not product_id:
            logger.warning("No product ID found in JSON data")
            return None
        
        # Extract title
        title = item_data.get("title", "")
        
        # Extract URL
        url_path = item_data.get("productDetailUrl", "")
        if not url_path:
            url_path = f"/item/{product_id}.html"
        full_url = normalize_url(url_path, self.base_url)
        
        # Extract price
        price_data = item_data.get("prices", {})
        current_price_str = price_data.get("salePrice", {}).get("formattedPrice", "")
        current_price = extract_price(current_price_str) or Decimal(str(price_data.get("salePrice", {}).get("value", 0)))
        
        currency_str = price_data.get("salePrice", {}).get("currency", "USD")
        try:
            currency = Currency(currency_str)
        except ValueError:
            currency = Currency.USD
        
        # Extract original price
        original_price_str = price_data.get("originalPrice", {}).get("formattedPrice", "")
        original_price = extract_price(original_price_str) or Decimal(str(price_data.get("originalPrice", {}).get("value", 0)))
        
        if original_price == 0 or original_price <= current_price:
            original_price = None
        
        # Create price object
        price = Price(
            current=Money(value=current_price, currency=currency),
            original=Money(value=original_price, currency=currency) if original_price else None
        )
        
        # Extract image
        image_url = item_data.get("imageUrl", "")
        
        # Extract shipping info
        shipping_data = item_data.get("shipping", {})
        shipping_price = None
        free_shipping = shipping_data.get("freeShipping", False)
        
        if not free_shipping and "price" in shipping_data:
            shipping_price = extract_price(shipping_data.get("price", {}).get("formattedPrice", "")) or \
                             Decimal(str(shipping_data.get("price", {}).get("value", 0)))
        
        # Extract ratings
        rating = item_data.get("evaluation", {}).get("starRating", None)
        reviews_count = item_data.get("evaluation", {}).get("totalCount", None)
        
        # Extract orders count
        orders_count = item_data.get("tradeCount", None) or item_data.get("orders", None)
        
        # Extract seller name
        seller_name = item_data.get("store", {}).get("storeName", "")
        
        return BasicProduct(
            product_id=product_id,
            title=title,
            url=full_url,
            price=price,
            image_url=image_url,
            shipping_price=Money(value=shipping_price, currency=currency) if shipping_price else None,
            free_shipping=free_shipping,
            rating=rating,
            reviews_count=reviews_count,
            orders_count=orders_count,
            seller_name=seller_name
        )
    
    def _parse_pagination(self) -> SearchPagination:
        """
        Parse pagination information.
        
        Returns:
            SearchPagination object
        """
        current_page = 1
        total_pages = 1
        
        # Try to find pagination elements
        pagination = self.soup.select_one(Selectors.PAGINATION_CONTAINER)
        if pagination:
            # Find current page
            current_page_element = pagination.select_one(Selectors.PAGINATION_CURRENT)
            if current_page_element:
                try:
                    current_page = int(clean_text(current_page_element.text))
                except ValueError:
                    pass
            
            # Find total pages
            total_pages_element = pagination.select_one(Selectors.PAGINATION_TOTAL)
            if total_pages_element:
                try:
                    total_pages_match = re.search(r'(\d+)', clean_text(total_pages_element.text))
                    if total_pages_match:
                        total_pages = int(total_pages_match.group(1))
                except ValueError:
                    pass
            else:
                # Count pagination elements
                page_links = pagination.select("a.pagination-item")
                if page_links:
                    page_numbers = []
                    for link in page_links:
                        try:
                            page_numbers.append(int(clean_text(link.text)))
                        except ValueError:
                            continue
                    if page_numbers:
                        total_pages = max(page_numbers)
        
        # Count products on the page
        product_elements = self.soup.select(Selectors.PRODUCT_ITEM if not self.is_mobile else Selectors.MOBILE_PRODUCT_ITEM)
        items_per_page = len(product_elements)
        
        return SearchPagination(
            page=current_page,
            total_pages=total_pages,
            items_per_page=items_per_page
        )
    
    def _extract_sort_order(self) -> Optional[str]:
        """
        Extract the current sort order.
        
        Returns:
            Sort order string or None if not found
        """
        # Try to find sort option elements
        sort_elements = self.soup.select(".sort-options a")
        for sort_element in sort_elements:
            if "active" in sort_element.get("class", []):
                return clean_text(sort_element.text)
        
        return None


class ItemDetailParser(BaseParser):
    """Parser for AliExpress item detail pages."""
    
    def parse_item(self) -> DetailedProduct:
        """
        Parse an item detail page.
        
        Returns:
            DetailedProduct object with item details
        """
        if not self.validate_response():
            logger.error("Invalid AliExpress item detail page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        # Try to parse from JSON data first (more reliable)
        if self.json_data:
            try:
                return self._parse_item_from_json()
            except Exception as e:
                logger.warning(f"Failed to parse item from JSON: {e}, falling back to HTML parsing")
        
        # Extract product ID from URL
        canonical = self.soup.select_one("link[rel='canonical']")
        product_id = None
        if canonical and canonical.has_attr('href'):
            product_id = extract_product_id(canonical['href'])
        
        if not product_id:
            # Try to extract from URL or other elements
            product_id = self._extract_product_id_from_page()
        
        if not product_id:
            logger.error("Could not extract product ID from item detail page")
            raise ParsingError(ERROR_MESSAGES["PARSING_ERROR"])
        
        # Extract basic item details
        title = self._get_text(Selectors.PRODUCT_DETAIL_TITLE)
        
        # Extract price information
        current_price = extract_price(self._get_text(Selectors.PRODUCT_DETAIL_PRICE))
        original_price = extract_price(self._get_text(Selectors.PRODUCT_DETAIL_ORIGINAL_PRICE))
        currency = extract_currency(self._get_text(Selectors.PRODUCT_DETAIL_PRICE))
        
        price = Price(
            current=Money(value=current_price or Decimal('0'), currency=currency),
            original=Money(value=original_price, currency=currency) if original_price else None
        )
        
        # Extract images
        images = self._parse_images()
        
        # Extract shipping information
        shipping = self._parse_shipping()
        
        # Extract seller information
        seller = self._parse_seller()
        
        # Extract ratings and reviews
        rating, reviews = self._parse_reviews()
        
        # Extract variations
        variations = self._parse_variations()
        
        # Extract description
        description = self._get_text(Selectors.PRODUCT_DESCRIPTION)
        
        # Extract specifications
        specifications = self._parse_specifications()
        
        # Extract order counts
        orders_count_element = self.soup.select_one(Selectors.PRODUCT_DETAIL_ORDERS_COUNT)
        orders_count = None
        if orders_count_element:
            orders_match = re.search(r'(\d+)', clean_text(orders_count_element.text))
            if orders_match:
                orders_count = int(orders_match.group(1))
        
        # Extract category info
        category_id = None
        category_name = None
        breadcrumb = self.soup.select(".breadcrumb a")
        if breadcrumb and len(breadcrumb) > 1:
            category_element = breadcrumb[-1]
            category_name = clean_text(category_element.text)
            category_url = category_element.get("href", "")
            category_match = re.search(r'category/(\d+)', category_url)
            if category_match:
                category_id = category_match.group(1)
        
        return DetailedProduct(
            product_id=product_id,
            title=title,
            url=f"{PRODUCT_URL_PATTERN}{product_id}.html",
            price=price,
            images=images,
            description=description,
            specifications=specifications,
            variations=variations,
            shipping=shipping,
            seller=seller,
            rating=rating,
            reviews=reviews,
            orders_count=orders_count,
            category_id=category_id,
            category_name=category_name
        )
    
    def _parse_item_from_json(self) -> DetailedProduct:
        """
        Parse item details from embedded JSON data.
        
        Returns:
            DetailedProduct object with item details
        """
        # Extract product ID
        product_id = str(self._get_json_value("data.productId") or 
                       self._get_json_value("productId") or 
                       self._get_json_value("pageModule.productId"))
        
        if not product_id:
            logger.error("Could not extract product ID from JSON data")
            raise ParsingError(ERROR_MESSAGES["PARSING_ERROR"])
        
        # Extract title
        title = self._get_json_value("data.titleModule.subject") or self._get_json_value("titleModule.subject", "")
        
        # Extract price information
        price_data = self._get_json_value("data.priceModule") or self._get_json_value("priceModule", {})
        
        current_price = Decimal(str(price_data.get("formatedActivityPrice", "").replace("US $", "").strip() or 
                                   price_data.get("formatedPrice", "").replace("US $", "").strip() or 
                                   price_data.get("minActivityPrice", "0")))
        
        original_price_str = price_data.get("formatedMaxPrice", "") or price_data.get("formatedOriginalPrice", "")
        original_price = None
        if original_price_str:
            original_price = Decimal(str(original_price_str.replace("US $", "").strip()))
        
        currency_str = price_data.get("currencyCode", "USD")
        try:
            currency = Currency(currency_str)
        except ValueError:
            currency = Currency.USD
        
        price = Price(
            current=Money(value=current_price, currency=currency),
            original=Money(value=original_price, currency=currency) if original_price else None
        )
        
        # Extract images
        image_data = self._get_json_value("data.imageModule") or self._get_json_value("imageModule", {})
        images = []
        
        image_list = image_data.get("imagePathList", []) or image_data.get("images", [])
        for i, img_url in enumerate(image_list):
            images.append(Image(
                url=img_url,
                thumbnail_url=img_url.replace('.jpg_', '.jpg_50x50.jpg_'),
                position=i
            ))
        
        # Extract shipping information
        shipping_data = self._get_json_value("data.shippingModule") or self._get_json_value("shippingModule", {})
        shipping_methods = []
        
        shipping_options = shipping_data.get("shippingList", []) or shipping_data.get("freightList", [])
        for shipping_option in shipping_options:
            shipping_price = Decimal(str(shipping_option.get("freightAmount", {}).get("value", "0")))
            shipping_currency = shipping_option.get("freightAmount", {}).get("currencyCode", currency_str)
            
            try:
                shipping_currency_enum = Currency(shipping_currency)
            except ValueError:
                shipping_currency_enum = currency
            
            shipping_methods.append(ShippingMethod(
                name=shipping_option.get("serviceName", ""),
                company=shipping_option.get("company", ""),
                cost=Money(value=shipping_price, currency=shipping_currency_enum),
                delivery_time=shipping_option.get("deliveryTime", ""),
                tracking_available=shipping_option.get("tracking", False)
            ))
        
        ships_from = shipping_data.get("shipFrom", "") or shipping_data.get("countryName", "")
        ships_to = shipping_data.get("shipToCountries", []) or []
        free_shipping = any(method.cost.value == 0 for method in shipping_methods)
        
        shipping = ShippingInfo(
            methods=shipping_methods,
            free_shipping=free_shipping,
            ships_from=ships_from,
            ships_to=ships_to
        )
        
        # Extract seller information
        seller_data = self._get_json_value("data.storeModule") or self._get_json_value("storeModule", {})
        
        seller = SellerInfo(
            id=str(seller_data.get("storeNum", "") or seller_data.get("storeId", "")),
            name=seller_data.get("storeName", ""),
            url=seller_data.get("storeURL", ""),
            positive_feedback_percentage=seller_data.get("positiveRate", None),
            feedback_score=seller_data.get("score", None),
            top_rated=seller_data.get("topRated", False),
            years_active=seller_data.get("openTime", None),
            followers_count=seller_data.get("followingNumber", None)
        )
        
        # Extract ratings and reviews
        review_data = self._get_json_value("data.feedbackModule") or self._get_json_value("feedbackModule", {})
        
        rating = None
        if review_data and "averageStar" in review_data:
            rating = ReviewRating(
                average=float(review_data.get("averageStar", 0)),
                count=int(review_data.get("totalValidNum", 0)),
                five_star=int(review_data.get("fiveStarNum", 0)),
                four_star=int(review_data.get("fourStarNum", 0)),
                three_star=int(review_data.get("threeStarNum", 0)),
                two_star=int(review_data.get("twoStarNum", 0)),
                one_star=int(review_data.get("oneStarNum", 0))
            )
        
        reviews = []
        review_list = review_data.get("feedbackList", [])
        for review_item in review_list:
            try:
                review_date = datetime.fromtimestamp(review_item.get("date", 0) / 1000)
            except:
                review_date = datetime.now()
            
            reviews.append(Review(
                id=str(review_item.get("id", "")),
                author=review_item.get("name", ""),
                date=review_date,
                rating=float(review_item.get("rating", 0)),
                content=review_item.get("content", ""),
                images=[img for img in review_item.get("images", []) if img],
                country=review_item.get("country", ""),
                helpful_votes=review_item.get("helpfulCount", None)
            ))
        
        # Extract variations
        sku_data = self._get_json_value("data.skuModule") or self._get_json_value("skuModule", {})
        variations = []
        
        if sku_data:
            sku_props = sku_data.get("productSKUPropertyList", [])
            for prop in sku_props:
                prop_name = prop.get("skuPropertyName", "")
                options = []
                
                for value in prop.get("skuPropertyValues", []):
                    prop_id = value.get("propertyValueId", "")
                    prop_value = value.get("propertyValueName", "")
                    prop_image = value.get("skuPropertyImagePath", "")
                    
                    price_adjustment = None
                    if "skuPropertyValueTips" in value:
                        price_str = value.get("skuPropertyValueTips", "")
                        price_value = extract_price(price_str)
                        if price_value:
                            price_adjustment = Money(value=price_value, currency=currency)
                    
                    options.append(VariationOption(
                        id=str(prop_id),
                        name=prop_value,
                        image=prop_image,
                        price_adjustment=price_adjustment,
                        available=True  # Default to true, will be updated later
                    ))
                
                if options:
                    variations.append(Variation(
                        name=prop_name,
                        options=options
                    ))
        
        # Extract description
        description = self._get_json_value("data.descriptionModule.description") or ""
        
        # Extract specifications
        spec_data = self._get_json_value("data.specsModule") or self._get_json_value("specsModule", {})
        specifications = []
        
        for spec in spec_data.get("props", []):
            specifications.append({
                "name": spec.get("name", ""),
                "value": spec.get("value", "")
            })
        
        # Extract orders count
        orders_count = self._get_json_value("data.titleModule.tradeCount") or self._get_json_value("titleModule.tradeCount")
        
        # Extract category info
        category_id = None
        category_name = None
        breadcrumb_data = self._get_json_value("data.breadcrumbModule") or self._get_json_value("breadcrumbModule", {})
        if breadcrumb_data:
            breadcrumb_list = breadcrumb_data.get("pathList", [])
            if breadcrumb_list and len(breadcrumb_list) > 0:
                last_category = breadcrumb_list[-1]
                category_name = last_category.get("name", "")
                category_url = last_category.get("url", "")
                category_match = re.search(r'category/(\d+)', category_url)
                if category_match:
                    category_id = category_match.group(1)
        
        return DetailedProduct(
            product_id=product_id,
            title=title,
            url=f"{PRODUCT_URL_PATTERN}{product_id}.html",
            price=price,
            images=images,
            description=description,
            specifications=[{"name": spec["name"], "value": spec["value"]} for spec in specifications],
            variations=variations,
            shipping=shipping,
            seller=seller,
            rating=rating,
            reviews=reviews,
            orders_count=orders_count,
            category_id=category_id,
            category_name=category_name
        )
    
    def _extract_product_id_from_page(self) -> Optional[str]:
        """
        Extract product ID from the page.
        
        Returns:
            Product ID as string or None if not found
        """
        # Try to extract from URL
        url = self._get_attribute("link[rel='canonical']", "href")
        if url:
            product_id = extract_product_id(url)
            if product_id:
                return product_id
        
        # Try to extract from meta tags
        for meta in self.soup.select("meta"):
            if meta.has_attr("property") and meta["property"] == "og:url":
                if meta.has_attr("content"):
                    product_id = extract_product_id(meta["content"])
                    if product_id:
                        return product_id
        
        # Try to extract from JavaScript
        scripts = self.soup.select("script")
        for script in scripts:
            script_text = script.string
            if script_text:
                product_match = re.search(r'productId["\s:=]+[\'"]?(\d+)[\'"]?', script_text)
                if product_match:
                    return product_match.group(1)
        
        return None
    
    def _parse_images(self) -> List[Image]:
        """
        Parse product images.
        
        Returns:
            List of Image objects
        """
        images = []
        
        # Try to find gallery images
        image_elements = self.soup.select(".product-image img")
        if not image_elements:
            image_elements = self.soup.select(".image-view-magnifier-container img")
        
        for i, img in enumerate(image_elements):
            img_url = img.get('src', img.get('data-src', ''))
            if img_url:
                # Clean up URL and convert to full-size if needed
                img_url = img_url.replace('_50x50.jpg', '.jpg')
                img_url = normalize_url(img_url)
                
                thumbnail_url = img_url.replace('.jpg', '_50x50.jpg')
                
                images.append(Image(
                    url=img_url,
                    thumbnail_url=thumbnail_url,
                    position=i
                ))
        
        return images
    
    def _parse_shipping(self) -> ShippingInfo:
        """
        Parse shipping information.
        
        Returns:
            ShippingInfo object
        """
        shipping_methods = []
        free_shipping = False
        ships_from = ""
        ships_to = []
        
        # Try to find shipping info
        shipping_container = self.soup.select_one(Selectors.PRODUCT_DETAIL_SHIPPING_INFO)
        if shipping_container:
            # Check for free shipping
            free_shipping_element = shipping_container.select_one(".product-shipping-free")
            if free_shipping_element:
                free_shipping = True
            
            # Extract ships from
            ships_from_element = shipping_container.select_one(".product-shipping-from")
            if ships_from_element:
                ships_from = clean_text(ships_from_element.text).replace("From ", "")
            
            # Extract shipping methods
            shipping_options = shipping_container.select(".product-shipping-option")
            for option in shipping_options:
                method_name = ""
                company = ""
                cost = Money(value=Decimal("0"), currency=Currency.USD)
                delivery_time = ""
                
                name_element = option.select_one(".shipping-name")
                if name_element:
                    method_text = clean_text(name_element.text)
                    # Try to extract company and method name
                    method_parts = method_text.split(" via ")
                    if len(method_parts) > 1:
                        method_name = method_parts[0]
                        company = method_parts[1]
                    else:
                        method_name = method_text
                
                price_element = option.select_one(".shipping-cost")
                if price_element:
                    price_text = clean_text(price_element.text)
                    if "free" in price_text.lower():
                        cost = Money(value=Decimal("0"), currency=Currency.USD)
                    else:
                        price_value = extract_price(price_text)
                        currency = extract_currency(price_text)
                        cost = Money(value=price_value or Decimal("0"), currency=currency)
                
                time_element = option.select_one(".shipping-time")
                if time_element:
                    delivery_time = clean_text(time_element.text)
                
                shipping_methods.append(ShippingMethod(
                    name=method_name,
                    company=company,
                    cost=cost,
                    delivery_time=delivery_time,
                    tracking_available=None
                ))
        
        return ShippingInfo(
            methods=shipping_methods,
            free_shipping=free_shipping,
            ships_from=ships_from,
            ships_to=ships_to
        )
    
    def _parse_seller(self) -> SellerInfo:
        """
        Parse seller information.
        
        Returns:
            SellerInfo object
        """
        seller_id = ""
        seller_name = ""
        seller_url = ""
        positive_feedback = None
        feedback_score = None
        top_rated = False
        years_active = None
        followers = None
        
        # Try to find seller info
        seller_container = self.soup.select_one(Selectors.SELLER_INFO_CONTAINER)
        if seller_container:
            # Extract seller name and URL
            name_element = seller_container.select_one(Selectors.SELLER_NAME)
            if name_element:
                seller_name = clean_text(name_element.text)
                if name_element.name == "a" and name_element.has_attr("href"):
                    seller_url = normalize_url(name_element["href"])
                    # Try to extract seller ID from URL
                    seller_id_match = re.search(r'store/(\d+)', seller_url)
                    if seller_id_match:
                        seller_id = seller_id_match.group(1)
            
            # Extract positive feedback
            feedback_element = seller_container.select_one(Selectors.SELLER_POSITIVE_FEEDBACK)
            if feedback_element:
                feedback_text = clean_text(feedback_element.text)
                feedback_match = re.search(r'([\d.]+)%', feedback_text)
                if feedback_match:
                    try:
                        positive_feedback = float(feedback_match.group(1))
                    except ValueError:
                        pass
            
            # Extract followers
            followers_element = seller_container.select_one(Selectors.SELLER_FOLLOWERS)
            if followers_element:
                followers_text = clean_text(followers_element.text)
                followers_match = re.search(r'(\d+)', followers_text)
                if followers_match:
                    followers = int(followers_match.group(1))
            
            # Check if top rated
            top_rated_element = seller_container.select_one(".top-rated-badge")
            if top_rated_element:
                top_rated = True
        
        return SellerInfo(
            id=seller_id,
            name=seller_name,
            url=seller_url,
            positive_feedback_percentage=positive_feedback,
            feedback_score=feedback_score,
            top_rated=top_rated,
            years_active=years_active,
            followers_count=followers
        )
    
    def _parse_reviews(self) -> Tuple[Optional[ReviewRating], List[Review]]:
        """
        Parse ratings and reviews.
        
        Returns:
            Tuple of (ReviewRating, List[Review])
        """
        rating = None
        reviews = []
        
        # Try to find rating info
        rating_element = self.soup.select_one(Selectors.PRODUCT_DETAIL_RATING)
        reviews_count_element = self.soup.select_one(Selectors.PRODUCT_DETAIL_REVIEWS_COUNT)
        
        if rating_element:
            try:
                average_rating = float(clean_text(rating_element.text))
                reviews_count = 0
                
                if reviews_count_element:
                    reviews_text = clean_text(reviews_count_element.text)
                    reviews_match = re.search(r'(\d+)', reviews_text)
                    if reviews_match:
                        reviews_count = int(reviews_match.group(1))
                
                rating = ReviewRating(
                    average=average_rating,
                    count=reviews_count
                )
            except ValueError:
                pass
        
        # Try to find reviews
        reviews_container = self.soup.select_one(Selectors.REVIEWS_CONTAINER)
        if reviews_container:
            review_items = reviews_container.select(Selectors.REVIEW_ITEM)
            for review_item in review_items:
                review_id = review_item.get("data-id", "")
                
                # Extract author
                author_element = review_item.select_one(Selectors.REVIEW_AUTHOR)
                author = clean_text(author_element.text) if author_element else ""
                
                # Extract rating
                rating_element = review_item.select_one(Selectors.REVIEW_RATING)
                review_rating = 0
                if rating_element:
                    stars = rating_element.select(".star-view")
                    full_stars = rating_element.select(".star-view.full")
                    review_rating = len(full_stars) if full_stars else 0
                
                # Extract content
                content_element = review_item.select_one(Selectors.REVIEW_CONTENT)
                content = clean_text(content_element.text) if content_element else ""
                
                # Extract date
                date_element = review_item.select_one(Selectors.REVIEW_DATE)
                review_date = datetime.now()
                if date_element:
                    date_text = clean_text(date_element.text)
                    try:
                        # Try to parse various date formats
                        date_formats = [
                            "%b %d, %Y",
                            "%d %b %Y",
                            "%Y-%m-%d",
                            "%d/%m/%Y"
                        ]
                        for fmt in date_formats:
                            try:
                                review_date = datetime.strptime(date_text, fmt)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                
                # Extract images
                images = []
                image_elements = review_item.select(".feedback-images img")
                for img in image_elements:
                    img_url = img.get("src", "")
                    if img_url:
                        images.append(normalize_url(img_url))
                
                # Extract country
                country = ""
                country_element = review_item.select_one(".user-country")
                if country_element:
                    country = clean_text(country_element.text)
                
                reviews.append(Review(
                    id=review_id,
                    author=author,
                    date=review_date,
                    rating=float(review_rating),
                    content=content,
                    images=images,
                    country=country,
                    helpful_votes=None
                ))
        
        return rating, reviews
    
    def _parse_variations(self) -> List[Variation]:
        """
        Parse product variations.
        
        Returns:
            List of Variation objects
        """
        variations = []
        
        # Try to find variations container
        variants_container = self.soup.select_one(Selectors.PRODUCT_VARIANTS_CONTAINER)
        if variants_container:
            variant_groups = variants_container.select(".sku-property")
            for group in variant_groups:
                # Extract variation name
                name_element = group.select_one(Selectors.PRODUCT_VARIANT_NAME)
                if not name_element:
                    continue
                
                variation_name = clean_text(name_element.text)
                
                # Extract options
                options = []
                option_elements = group.select(Selectors.PRODUCT_VARIANT_VALUE)
                for i, option_elem in enumerate(option_elements):
                    option_id = option_elem.get("data-sku-id", str(i))
                    
                    # Extract option name
                    option_name = ""
                    name_span = option_elem.select_one(".sku-value-name")
                    if name_span:
                        option_name = clean_text(name_span.text)
                    else:
                        option_name = clean_text(option_elem.text)
                    
                    # Extract option image
                    option_image = None
                    img = option_elem.select_one("img")
                    if img:
                        option_image = normalize_url(img.get("src", ""))
                    
                    # Check if option is available
                    available = True
                    if "disabled" in option_elem.get("class", []):
                        available = False
                    
                    # Try to extract price adjustment
                    price_adjustment = None
                    price_span = option_elem.select_one(".sku-price")
                    if price_span:
                        price_text = clean_text(price_span.text)
                        price_value = extract_price(price_text)
                        if price_value:
                            currency = extract_currency(price_text)
                            price_adjustment = Money(value=price_value, currency=currency)
                    
                    options.append(VariationOption(
                        id=option_id,
                        name=option_name,
                        image=option_image,
                        price_adjustment=price_adjustment,
                        available=available
                    ))
                
                if options:
                    variations.append(Variation(
                        name=variation_name,
                        options=options
                    ))
        
        return variations
    
    def _parse_specifications(self) -> List[Dict[str, str]]:
        """
        Parse product specifications.
        
        Returns:
            List of specification dictionaries
        """
        specs = []
        
        # Try to find specifications
        specs_container = self.soup.select_one(Selectors.PRODUCT_SPECS)
        if specs_container:
            spec_rows = specs_container.select("li") or specs_container.select("tr")
            for row in spec_rows:
                name = ""
                value = ""
                
                # Try different formats
                name_elem = row.select_one(".name") or row.select_one("th") or row.select_one("td:first-child")
                value_elem = row.select_one(".value") or row.select_one("td:last-child")
                
                if name_elem and value_elem:
                    name = clean_text(name_elem.text)
                    value = clean_text(value_elem.text)
                elif ":" in row.text:
                    # Try to split by colon
                    parts = clean_text(row.text).split(":", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                
                if name and value:
                    specs.append({"name": name, "value": value})
        
        return specs


class CategoryParser(BaseParser):
    """Parser for AliExpress category pages."""
    
    def parse_categories(self) -> List[Category]:
        """
        Parse categories from the category page.
        
        Returns:
            List of Category objects
        """
        if not self.validate_response():
            logger.error("Invalid AliExpress categories page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        # Try to parse from JSON data first (more reliable)
        if self.json_data:
            try:
                return self._parse_categories_from_json()
            except Exception as e:
                logger.warning(f"Failed to parse categories from JSON: {e}, falling back to HTML parsing")
        
        categories = []
        
        # Find category lists
        category_lists = self.soup.select(".categories-list") or self.soup.select(".category-list")
        for category_list in category_lists:
            category_elements = category_list.select("li") or category_list.select(".category-item")
            for category_element in category_elements:
                try:
                    category_data = self._parse_category(category_element)
                    if category_data:
                        categories.append(category_data)
                except Exception as e:
                    logger.warning(f"Error parsing category: {e}")
                    continue
        
        # If no categories found, try other selectors
        if not categories:
            category_elements = self.soup.select(".category-items a") or self.soup.select(".category-tree a")
            for category_element in category_elements:
                try:
                    category_data = self._parse_category(category_element)
                    if category_data:
                        categories.append(category_data)
                except Exception as e:
                    logger.warning(f"Error parsing category: {e}")
                    continue
        
        return categories
    
    def _parse_categories_from_json(self) -> List[Category]:
        """
        Parse categories from embedded JSON data.
        
        Returns:
            List of Category objects
        """
        categories = []
        
        # Try different JSON paths for categories
        category_data = self._get_json_value("categories") or self._get_json_value("data.categories") or []
        
        for cat in category_data:
            cat_id = str(cat.get("categoryId", ""))
            name = cat.get("name", "")
            url_path = cat.get("url", "")
            parent_id = str(cat.get("parentCategoryId", "")) if "parentCategoryId" in cat else None
            
            if cat_id and name:
                # Normalize URL
                url = normalize_url(url_path) if url_path else f"{BASE_URL}/category/{cat_id}"
                
                # Create category object
                category = Category(
                    id=cat_id,
                    name=name,
                    url=url,
                    parent_id=parent_id,
                    level=cat.get("level", None),
                    product_count=cat.get("productCount", None)
                )
                
                # Process child categories if available
                children = []
                child_cats = cat.get("children", []) or cat.get("childCategories", [])
                for child in child_cats:
                    child_id = str(child.get("categoryId", ""))
                    child_name = child.get("name", "")
                    child_url_path = child.get("url", "")
                    
                    if child_id and child_name:
                        child_url = normalize_url(child_url_path) if child_url_path else f"{BASE_URL}/category/{child_id}"
                        
                        children.append(Category(
                            id=child_id,
                            name=child_name,
                            url=child_url,
                            parent_id=cat_id,
                            level=(cat.get("level", 0) or 0) + 1,
                            product_count=child.get("productCount", None)
                        ))
                
                category.children = children
                categories.append(category)
        
        return categories
    
    def _parse_category(self, category_element: Tag) -> Optional[Category]:
        """
        Parse a single category element.
        
        Args:
            category_element: BeautifulSoup Tag containing category data
            
        Returns:
            Category object or None if parsing fails
        """
        # If element is a link, extract directly
        if category_element.name == "a":
            name = clean_text(category_element.text)
            url = category_element.get("href", "")
            
            # Extract category ID from URL
            cat_id = None
            if url:
                id_match = re.search(r'category/(\d+)', url)
                if id_match:
                    cat_id = id_match.group(1)
            
            if not cat_id or not name:
                return None
            
            # Normalize URL
            full_url = normalize_url(url)
            
            return Category(
                id=cat_id,
                name=name,
                url=full_url,
                parent_id=None,
                level=None
            )
        
        # Otherwise, look for link inside element
        link = category_element.select_one("a")
        if not link:
            return None
        
        name = clean_text(link.text)
        url = link.get("href", "")
        
        # Extract category ID from URL
        cat_id = None
        if url:
            id_match = re.search(r'category/(\d+)', url)
            if id_match:
                cat_id = id_match.group(1)
        
        if not cat_id or not name:
            return None
        
        # Normalize URL
        full_url = normalize_url(url)
        
        # Try to extract product count
        count = None
        count_element = category_element.select_one(".count") or category_element.select_one(".category-count")
        if count_element:
            count_text = clean_text(count_element.text)
            count_match = re.search(r'(\d+)', count_text)
            if count_match:
                count = int(count_match.group(1))
        
        # Extract parent ID if available
        parent_id = None
        parent_link = None
        
        # Look for parent in breadcrumbs
        breadcrumb = self.soup.select_one(".breadcrumb")
        if breadcrumb:
            parent_links = breadcrumb.select("a")
            if len(parent_links) > 1:
                parent_link = parent_links[-2]
                parent_url = parent_link.get("href", "")
                parent_match = re.search(r'category/(\d+)', parent_url)
                if parent_match:
                    parent_id = parent_match.group(1)
        
        return Category(
            id=cat_id,
            name=name,
            url=full_url,
            parent_id=parent_id,
            level=None,
            product_count=count
        )
