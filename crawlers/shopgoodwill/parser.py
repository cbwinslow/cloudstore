"""
HTML Parser for ShopGoodwill.com.

This module provides parser classes for extracting structured data from 
ShopGoodwill.com HTML pages using BeautifulSoup.
"""

import re
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from decimal import Decimal
from bs4 import BeautifulSoup, Tag

from .constants import Selectors, ERROR_MESSAGES, BASE_URL

# Configure logger
logger = logging.getLogger(__name__)

class ParsingError(Exception):
    """Exception raised when parsing fails."""
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
        price_text: Text containing a price (e.g., "$10.99")
        
    Returns:
        Decimal price or None if no valid price found
    """
    if not price_text:
        return None
    
    # Extract digits and decimal point
    price_match = re.search(r'\$?(\d+(?:\.\d{1,2})?)', price_text)
    if price_match:
        try:
            return Decimal(price_match.group(1))
        except Exception as e:
            logger.warning(f"Failed to parse price from '{price_text}': {e}")
    
    return None

def extract_item_id(url: str) -> Optional[str]:
    """
    Extract the item ID from a ShopGoodwill item URL.
    
    Args:
        url: URL of the item
        
    Returns:
        Item ID as string or None if no valid ID found
    """
    if not url:
        return None
    
    # Extract item ID from URL like /item/123456
    item_match = re.search(r'/item/(\d+)', url)
    if item_match:
        return item_match.group(1)
    
    return None

class BaseParser:
    """Base class for all ShopGoodwill parsers."""
    
    def __init__(self, html_content: str):
        """
        Initialize the parser with HTML content.
        
        Args:
            html_content: Raw HTML content to parse
        """
        self.soup = BeautifulSoup(html_content, 'html.parser')
        
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
    
    def validate_response(self) -> bool:
        """
        Validate that the HTML response is a valid ShopGoodwill page.
        
        Returns:
            True if valid, False otherwise
        """
        # Check if page contains ShopGoodwill header or common elements
        return bool(self.soup.title and "ShopGoodwill" in self.soup.title.text)


class ProductListingParser(BaseParser):
    """Parser for ShopGoodwill search results/listings."""
    
    def parse_listings(self) -> List[Dict[str, Any]]:
        """
        Parse product listings from search results page.
        
        Returns:
            List of product dictionaries with extracted data
        """
        if not self.validate_response():
            logger.error("Invalid ShopGoodwill search results page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        products = []
        product_elements = self.soup.select(Selectors.SEARCH_RESULTS)
        
        if not product_elements:
            logger.warning("No product listings found on page")
            return []
        
        for product_element in product_elements:
            try:
                product_data = self._parse_product(product_element)
                if product_data:
                    products.append(product_data)
            except Exception as e:
                logger.warning(f"Error parsing product listing: {e}")
                continue
                
        return products
    
    def _parse_product(self, product_element: Tag) -> Dict[str, Any]:
        """
        Parse a single product element from search results.
        
        Args:
            product_element: BeautifulSoup Tag containing product data
            
        Returns:
            Dictionary with product data
        """
        # Extract link and ID first as they're most essential
        link_element = product_element.select_one(Selectors.PRODUCT_LINK)
        if not link_element or not link_element.has_attr('href'):
            logger.warning("Product element missing link")
            return {}
        
        relative_url = link_element['href']
        full_url = f"{BASE_URL}{relative_url}" if relative_url.startswith('/') else relative_url
        item_id = extract_item_id(relative_url)
        
        if not item_id:
            logger.warning(f"Couldn't extract item ID from URL: {relative_url}")
            return {}
        
        # Extract other product details
        title = clean_text(product_element.select_one(Selectors.PRODUCT_TITLE).text) if product_element.select_one(Selectors.PRODUCT_TITLE) else ""
        
        price_element = product_element.select_one(Selectors.PRODUCT_PRICE)
        price = extract_price(price_element.text if price_element else None)
        
        image_element = product_element.select_one(Selectors.PRODUCT_IMAGE)
        image_url = image_element['src'] if image_element and image_element.has_attr('src') else ""
        
        # Extract shipping info
        shipping_element = product_element.select_one(Selectors.PRODUCT_SHIPPING)
        shipping_text = clean_text(shipping_element.text) if shipping_element else ""
        shipping_cost = None
        if shipping_text:
            shipping_cost = extract_price(shipping_text)
        
        # Extract seller info
        seller_element = product_element.select_one(Selectors.PRODUCT_SELLER)
        seller = ""
        if seller_element:
            seller_match = re.search(r'Seller:\s*(.+)', clean_text(seller_element.text))
            seller = seller_match.group(1) if seller_match else ""
        
        # Extract bids info
        bids_element = product_element.select_one(Selectors.PRODUCT_BIDS_COUNT)
        bids_count = 0
        if bids_element:
            bids_match = re.search(r'(\d+)\s+bids?', clean_text(bids_element.text))
            if bids_match:
                bids_count = int(bids_match.group(1))
        
        # Time left
        time_left_element = product_element.select_one(Selectors.PRODUCT_TIME_LEFT)
        time_left = clean_text(time_left_element.text).replace("Time Left:", "").strip() if time_left_element else ""
        
        return {
            "item_id": item_id,
            "title": title,
            "current_price": price,
            "shipping_cost": shipping_cost,
            "seller": seller,
            "bids_count": bids_count,
            "time_left": time_left,
            "image_url": image_url,
            "url": full_url,
        }
    
    def get_total_pages(self) -> int:
        """
        Extract the total number of pages from pagination.
        
        Returns:
            Total number of pages or 1 if not found
        """
        pagination = self.soup.select(".page-item a.page-link")
        if not pagination:
            return 1
        
        # Try to find the last page number
        page_numbers = []
        for page_link in pagination:
            if page_link.text.isdigit():
                page_numbers.append(int(page_link.text))
        
        return max(page_numbers) if page_numbers else 1


class ItemDetailParser(BaseParser):
    """Parser for ShopGoodwill item detail pages."""
    
    def parse_item(self) -> Dict[str, Any]:
        """
        Parse an item detail page.
        
        Returns:
            Dictionary with item details
        """
        if not self.validate_response():
            logger.error("Invalid ShopGoodwill item detail page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        # Extract item ID from URL in the canonical link
        canonical = self.soup.select_one("link[rel='canonical']")
        item_id = None
        if canonical and canonical.has_attr('href'):
            item_id = extract_item_id(canonical['href'])
        
        if not item_id:
            logger.error("Could not extract item ID from item detail page")
            raise ParsingError(ERROR_MESSAGES["PARSING_ERROR"])
        
        # Extract basic item details
        title = self._get_text(Selectors.ITEM_TITLE)
        current_price = extract_price(self._get_text(Selectors.ITEM_CURRENT_PRICE))
        
        # Extract condition
        condition_element = self.soup.select_one(Selectors.ITEM_CONDITION)
        condition = ""
        if condition_element:
            condition_match = re.search(r'Condition:\s*(.+)', clean_text(condition_element.text))
            condition = condition_match.group(1) if condition_match else ""
        
        # Extract shipping cost
        shipping_element = self.soup.select_one(Selectors.ITEM_SHIPPING_COST)
        shipping_cost = None
        if shipping_element:
            shipping_cost = extract_price(shipping_element.text)
        
        # Extract seller
        seller_element = self.soup.select_one(Selectors.ITEM_SELLER)
        seller = ""
        if seller_element:
            seller_match = re.search(r'Seller:\s*(.+)', clean_text(seller_element.text))
            seller = seller_match.group(1) if seller_match else ""
        
        # Extract description
        description = self._get_text(Selectors.ITEM_DESCRIPTION)
        
        # Extract images
        image_elements = self.soup.select(Selectors.ITEM_IMAGES)
        images = []
        for img in image_elements:
            if img.has_attr('src'):
                images.append(img['src'])
        
        # Extract bid history
        bid_elements = self.soup.select(Selectors.ITEM_BIDS)
        bids = []
        for bid_element in bid_elements:
            bid_cells = bid_element.select("td")
            if len(bid_cells) >= 3:
                bid_info = {
                    "bidder": clean_text(bid_cells[0].text),
                    "amount": extract_price(bid_cells[1].text),
                    "date": clean_text(bid_cells[2].text)
                }
                bids.append(bid_info)
        
        # Extract end date
        end_date_element = self.soup.select_one(Selectors.ITEM_END_DATE)
        end_date = ""
        if end_date_element:
            end_date_match = re.search(r'End Date:\s*(.+)', clean_text(end_date_element.text))
            end_date = end_date_match.group(1) if end_date_match else ""
        
        return {
            "item_id": item_id,
            "title": title,
            "current_price": current_price,
            "condition": condition,
            "shipping_cost": shipping_cost,
            "seller": seller,
            "description": description,
            "images": images,
            "bids": bids,
            "end_date": end_date,
            "url": f"{BASE_URL}/item/{item_id}"
        }


class CategoryParser(BaseParser):
    """Parser for ShopGoodwill category pages."""
    
    def parse_categories(self) -> List[Dict[str, Any]]:
        """
        Parse categories from the categories page.
        
        Returns:
            List of category dictionaries
        """
        if not self.validate_response():
            logger.error("Invalid ShopGoodwill categories page")
            raise ParsingError(ERROR_MESSAGES["INVALID_RESPONSE"])
        
        categories = []
        category_elements = self.soup.select(Selectors.CATEGORY_LIST)
        
        if not category_elements:
            logger.warning("No categories found on page")
            return []
        
        for category_element in category_elements:
            try:
                category_data = self._parse_category(category_element)
                if category_data:
                    categories.append(category_data)
            except Exception as e:
                logger.warning(f"Error parsing category: {e}")
                continue
                
        return categories
    
    def _parse_category(self, category_element: Tag) -> Dict[str, Any]:
        """
        Parse a single category element.
        
        Args:
            category_element: BeautifulSoup Tag containing category data
            
        Returns:
            Dictionary with category data
        """
        name_element = category_element.select_one(Selectors.CATEGORY_NAME)
        name = clean_text(name_element.text) if name_element else ""
        
        # Extract category URL
        link = ""
        if category_element.name == "a" and category_element.has_attr('href'):
            link = category_element['href']
        else:
            link_element = category_element.find("a")
            if link_element and link_element.has_attr('href'):
                link = link_element['href']
                
        full_url = f"{BASE_URL}{link}" if link.startswith('/') else link
        
        # Extract item count
        count_element = category_element.select_one(Selectors.CATEGORY_COUNT)
        count = 0
        if count_element:
            count_match = re.search(r'(\d+)', clean_text(count_element.text))
            if count_match:
                count = int(count_match.group(1))
        
        # Extract category ID from URL
        category_id = ""
        if link:
            category_match = re.search(r'categoryId=(\d+)', link)
            if category_match:
                category_id = category_match.group(1)
        
        return {
            "category_id": category_id,
            "name": name,
            "count": count,
            "url": full_url
        }

