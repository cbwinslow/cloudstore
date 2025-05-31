"""
Tests for ShopGoodwill crawler and parser functionality.

This module contains tests for the crawler, parsers, and utilities
for the ShopGoodwill scraping package.
"""

import os
import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock
from decimal import Decimal

from crawlers.shopgoodwill import (
    ShopGoodwillCrawler,
    SyncShopGoodwillCrawler,
    ProductListingParser,
    ItemDetailParser,
    CategoryParser,
    ParsingError,
    ShopGoodwillError,
    ItemNotFoundError,
    SortOptions,
)

# Define constants for testing
TEST_ITEM_ID = "123456"  # Replace with a real item ID if needed for integration tests
SEARCH_QUERY = "vintage camera"
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Skip real network tests by default
# Run with pytest -xvs --run-network-tests to enable them
@pytest.fixture(scope="session")
def skip_network_tests(request):
    return not request.config.getoption("--run-network-tests")

# Create fixtures directory if it doesn't exist
os.makedirs(FIXTURES_DIR, exist_ok=True)


# Helper functions for loading and saving test fixtures
def load_fixture(filename):
    """Load a test fixture from file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None


def save_fixture(filename, content):
    """Save a test fixture to file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# Mock responses for testing without network requests
MOCK_SEARCH_RESPONSE = """
<!DOCTYPE html>
<html>
<head>
    <title>ShopGoodwill - Search Results</title>
</head>
<body>
    <div class="mb-4 p-3 border rounded">
        <a href="/item/123456" class="font-weight-bold mb-2">Vintage Camera</a>
        <div class="d-flex justify-content-between align-items-center">
            <span class="h5">$24.99</span>
        </div>
        <div class="small text-muted">5 bids</div>
        <div class="small text-muted">Time Left: 1d 4h 30m</div>
        <div class="small text-muted">Shipping: $8.99</div>
        <div class="small text-muted">Seller: Seattle Goodwill</div>
        <img src="https://shopgoodwill.com/images/items/123456.jpg" class="card-img-top" alt="Vintage Camera">
    </div>
    <div class="mb-4 p-3 border rounded">
        <a href="/item/789012" class="font-weight-bold mb-2">Antique Camera</a>
        <div class="d-flex justify-content-between align-items-center">
            <span class="h5">$35.50</span>
        </div>
        <div class="small text-muted">3 bids</div>
        <div class="small text-muted">Time Left: 2d 6h 15m</div>
        <div class="small text-muted">Shipping: $10.99</div>
        <div class="small text-muted">Seller: Portland Goodwill</div>
        <img src="https://shopgoodwill.com/images/items/789012.jpg" class="card-img-top" alt="Antique Camera">
    </div>
    <nav>
        <ul class="pagination">
            <li class="page-item"><a class="page-link" href="#">1</a></li>
            <li class="page-item"><a class="page-link" href="#">2</a></li>
            <li class="page-item"><a class="page-link" href="#">3</a></li>
        </ul>
    </nav>
</body>
</html>
"""

MOCK_ITEM_RESPONSE = """
<!DOCTYPE html>
<html>
<head>
    <title>ShopGoodwill - Item Details</title>
    <link rel="canonical" href="https://shopgoodwill.com/item/123456">
</head>
<body>
    <h1 class="h4 mb-3">Vintage Camera</h1>
    <div class="h3 font-weight-bold">$24.99</div>
    <div class="mb-2">Condition: Good</div>
    <div class="mb-2">Shipping: $8.99</div>
    <div class="mb-2">Seller: Seattle Goodwill</div>
    <div class="mb-2">End Date: 2025-06-02 18:00:00</div>
    <div id="item-description">
        <p>Vintage camera in good working condition. Includes original case and manual.</p>
    </div>
    <div class="carousel-item">
        <img src="https://shopgoodwill.com/images/items/123456_1.jpg" alt="Image 1">
    </div>
    <div class="carousel-item">
        <img src="https://shopgoodwill.com/images/items/123456_2.jpg" alt="Image 2">
    </div>
    <table id="bid-history-table">
        <tbody>
            <tr>
                <td>user123</td>
                <td>$24.99</td>
                <td>2025-05-30 15:30:45</td>
            </tr>
            <tr>
                <td>user456</td>
                <td>$22.50</td>
                <td>2025-05-30 14:15:22</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

MOCK_CATEGORIES_RESPONSE = """
<!DOCTYPE html>
<html>
<head>
    <title>ShopGoodwill - Categories</title>
</head>
<body>
    <div class="list-group-item">
        <a href="/categories?categoryId=18">
            <span class="font-weight-bold">Electronics</span>
            <span class="badge">2345</span>
        </a>
    </div>
    <div class="list-group-item">
        <a href="/categories?categoryId=22">
            <span class="font-weight-bold">Collectibles</span>
            <span class="badge">1876</span>
        </a>
    </div>
    <div class="list-group-item">
        <a href="/categories?categoryId=33">
            <span class="font-weight-bold">Jewelry</span>
            <span class="badge">3421</span>
        </a>
    </div>
</body>
</html>
"""


# Save mock responses as fixtures if they don't exist
if not os.path.exists(os.path.join(FIXTURES_DIR, "search_results.html")):
    save_fixture("search_results.html", MOCK_SEARCH_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "item_details.html")):
    save_fixture("item_details.html", MOCK_ITEM_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "categories.html")):
    save_fixture("categories.html", MOCK_CATEGORIES_RESPONSE)


# Parser Tests
class TestParsers:
    """Tests for the HTML parser classes."""
    
    def test_product_listing_parser(self):
        """Test parsing product listings from search results."""
        parser = ProductListingParser(MOCK_SEARCH_RESPONSE)
        results = parser.parse_listings()
        
        assert len(results) == 2
        assert results[0]["item_id"] == "123456"
        assert results[0]["title"] == "Vintage Camera"
        assert results[0]["current_price"] == Decimal("24.99")
        assert results[0]["shipping_cost"] == Decimal("8.99")
        assert results[0]["seller"] == "Seattle Goodwill"
        assert results[0]["bids_count"] == 5
        
        assert results[1]["item_id"] == "789012"
        assert results[1]["title"] == "Antique Camera"
    
    def test_total_pages_extraction(self):
        """Test extracting total pages from search results."""
        parser = ProductListingParser(MOCK_SEARCH_RESPONSE)
        total_pages = parser.get_total_pages()
        
        assert total_pages == 3
    
    def test_item_detail_parser(self):
        """Test parsing item details."""
        parser = ItemDetailParser(MOCK_ITEM_RESPONSE)
        item = parser.parse_item()
        
        assert item["item_id"] == "123456"
        assert item["title"] == "Vintage Camera"
        assert item["current_price"] == Decimal("24.99")
        assert item["condition"] == "Good"
        assert item["shipping_cost"] == Decimal("8.99")
        assert item["seller"] == "Seattle Goodwill"
        assert "Vintage camera in good working condition" in item["description"]
        assert len(item["images"]) == 2
        assert len(item["bids"]) == 2
        assert item["end_date"] == "2025-06-02 18:00:00"
    
    def test_category_parser(self):
        """Test parsing categories."""
        parser = CategoryParser(MOCK_CATEGORIES_RESPONSE)
        categories = parser.parse_categories()
        
        assert len(categories) == 3
        assert categories[0]["category_id"] == "18"
        assert categories[0]["name"] == "Electronics"
        assert categories[0]["count"] == 2345
        
        assert categories[1]["category_id"] == "22"
        assert categories[1]["name"] == "Collectibles"
        
        assert categories[2]["category_id"] == "33"
        assert categories[2]["name"] == "Jewelry"
    
    def test_parsing_error_handling(self):
        """Test handling of invalid HTML."""
        with pytest.raises(ParsingError):
            parser = ItemDetailParser("<html><body>Invalid content</body></html>")
            parser.parse_item()


# Crawler Tests with Mocks
class TestCrawlerWithMocks:
    """Tests for the crawler using mocked responses."""
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        
        # Create a future for text() method
        text_future = asyncio.Future()
        text_future.set_result(MOCK_SEARCH_RESPONSE)
        mock_resp.text = MagicMock(return_value=text_future)
        
        # Create a future for __aenter__
        enter_future = asyncio.Future()
        enter_future.set_result(mock_resp)
        mock_resp.__aenter__ = MagicMock(return_value=enter_future)
        
        # Create a future for __aexit__
        exit_future = asyncio.Future()
        exit_future.set_result(None)
        mock_resp.__aexit__ = MagicMock(return_value=exit_future)
        
        return mock_resp
    
    @pytest.fixture
    def mock_session(self, mock_response):
        """Create a mock aiohttp ClientSession."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.closed = False
        
        # Create a future for close() method
        close_future = asyncio.Future()
        close_future.set_result(None)
        mock_session.close = MagicMock(return_value=close_future)
        
        # Create a future for __aenter__
        enter_future = asyncio.Future()
        enter_future.set_result(mock_session)
        mock_session.__aenter__ = MagicMock(return_value=enter_future)
        
        # Create a future for __aexit__
        exit_future = asyncio.Future()
        exit_future.set_result(None)
        mock_session.__aexit__ = MagicMock(return_value=exit_future)
        
        return mock_session
    
    @pytest.mark.asyncio
    async def test_search(self, mock_session):
        """Test search functionality with mocks."""
        with patch('aiohttp.ClientSession', return_value=mock_session):
            async with ShopGoodwillCrawler() as crawler:
                crawler.session = mock_session
                
                # Override the search response
                mock_response = crawler.session.get.return_value
                
                # Update the text future for this test
                text_future = asyncio.Future()
                text_future.set_result(MOCK_SEARCH_RESPONSE)
                mock_response.text.return_value = text_future
                
                results = await crawler.search(query=SEARCH_QUERY)
                
                assert len(results["items"]) == 2
                assert results["page"] == 1
                assert results["total_pages"] == 3
                assert results["query"] == SEARCH_QUERY
    
    @pytest.mark.asyncio
    async def test_get_item(self, mock_session):
        """Test get_item functionality with mocks."""
        with patch('aiohttp.ClientSession', return_value=mock_session):
            async with ShopGoodwillCrawler() as crawler:
                crawler.session = mock_session
                
                # Override the item response
                mock_response = crawler.session.get.return_value
                
                # Update the text future for this test
                text_future = asyncio.Future()
                text_future.set_result(MOCK_ITEM_RESPONSE)
                mock_response.text.return_value = text_future
                
                item = await crawler.get_item(TEST_ITEM_ID)
                
                assert item["item_id"] == TEST_ITEM_ID
                assert item["title"] == "Vintage Camera"
                assert item["current_price"] == Decimal("24.99")
    
    @pytest.mark.asyncio
    async def test_get_categories(self, mock_session):
        """Test get_categories functionality with mocks."""
        with patch('aiohttp.ClientSession', return_value=mock_session):
            async with ShopGoodwillCrawler() as crawler:
                crawler.session = mock_session
                
                # Override the categories response
                mock_response = crawler.session.get.return_value
                
                # Update the text future for this test
                text_future = asyncio.Future()
                text_future.set_result(MOCK_CATEGORIES_RESPONSE)
                mock_response.text.return_value = text_future
                
                categories = await crawler.get_categories()
                
                assert len(categories) == 3
                assert categories[0]["name"] == "Electronics"
    
    def test_sync_crawler(self):
        """Test the synchronous wrapper functionality."""
        with patch('asyncio.get_event_loop'):
            with patch.object(ShopGoodwillCrawler, 'search', return_value={"items": []}):
                crawler = SyncShopGoodwillCrawler()
                with patch.object(crawler, '_run_async', return_value={"items": []}):
                    results = crawler.search(query=SEARCH_QUERY)
                    assert "items" in results


# Integration Tests with real network requests
@pytest.mark.skipif("not config.getoption('--run-network-tests')", reason="Network tests disabled")
class TestIntegration:
    """Integration tests with real network requests."""
    
    def test_sync_search(self):
        """Test real search using synchronous crawler."""
        crawler = SyncShopGoodwillCrawler()
        results = crawler.search(query=SEARCH_QUERY, page=1, items_per_page=5)
        
        assert "items" in results
        assert isinstance(results["items"], list)
        assert "total_pages" in results
        
        # Save a sample result for debugging/updating mocks
        save_fixture("real_search_results.json", json.dumps(results, default=str, indent=2))
    
    def test_sync_get_item(self):
        """Test real item retrieval using synchronous crawler."""
        # This test requires a real item ID to work
        if not TEST_ITEM_ID.isdigit():
            pytest.skip("No valid TEST_ITEM_ID provided for integration test")
            
        crawler = SyncShopGoodwillCrawler()
        item = crawler.get_item(TEST_ITEM_ID)
        
        assert item["item_id"] == TEST_ITEM_ID
        assert "title" in item
        assert "current_price" in item
        
        # Save a sample result for debugging/updating mocks
        save_fixture("real_item_details.json", json.dumps(item, default=str, indent=2))
    
    def test_sync_get_categories(self):
        """Test real category retrieval using synchronous crawler."""
        crawler = SyncShopGoodwillCrawler()
        categories = crawler.get_categories()
        
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "name" in categories[0]
        assert "category_id" in categories[0]
        
        # Save a sample result for debugging/updating mocks
        save_fixture("real_categories.json", json.dumps(categories, default=str, indent=2))

