"""
Tests for eBay API client functionality.

This module contains tests for the eBay API client, including
authentication, search, item details, and categories.
"""

import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from decimal import Decimal

import aiohttp
from aiohttp import ClientResponse, RequestInfo
from yarl import URL

from crawlers.ebay.api import (
    EbayApiClient, SyncEbayApiClient,
    EbayApiError, AuthenticationError, RateLimitError, 
    ItemNotFoundError, InvalidRequestError, RateLimiter
)
from crawlers.ebay.constants import (
    SortOrder, ConditionId, GlobalId, FindingApiOperation
)
from crawlers.ebay.models import (
    OAuthToken, Item, SearchResult, PaginationInfo, CategoryHierarchy,
    Category, Amount
)

# Directory for test fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Create fixtures directory if it doesn't exist
os.makedirs(FIXTURES_DIR, exist_ok=True)

# Test constants
TEST_APP_ID = "test-app-id"
TEST_CERT_ID = "test-cert-id"
TEST_DEV_ID = "test-dev-id"
TEST_REDIRECT_URI = "https://example.com/callback"
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_ITEM_ID = "123456789"

# Sample responses
OAUTH_TOKEN_RESPONSE = {
    "access_token": "test_access_token",
    "token_type": "Bearer",
    "expires_in": 7200,
    "refresh_token": "test_refresh_token",
    "scope": "https://api.ebay.com/oauth/api_scope"
}

FINDING_API_RESPONSE = {
    "findItemsByKeywordsResponse": {
        "ack": ["Success"],
        "version": ["1.13.0"],
        "timestamp": ["2025-05-31T12:00:00.000Z"],
        "searchResult": {
            "@count": "2",
            "item": [
                {
                    "itemId": ["123456789"],
                    "title": ["Test Item 1"],
                    "primaryCategory": {
                        "categoryId": ["12345"],
                        "categoryName": ["Test Category"]
                    },
                    "galleryURL": ["https://example.com/img1.jpg"],
                    "viewItemURL": ["https://example.com/item/123456789"],
                    "sellingStatus": {
                        "currentPrice": {
                            "@currencyId": "USD",
                            "__value__": "10.99"
                        },
                        "sellingState": ["Active"]
                    },
                    "sellerInfo": {
                        "sellerUserName": ["test_seller"],
                        "feedbackScore": ["100"],
                        "positiveFeedbackPercent": ["99.5"],
                        "topRatedSeller": ["true"]
                    },
                    "shippingInfo": {
                        "shippingServiceCost": {
                            "@currencyId": "USD",
                            "__value__": "3.99"
                        },
                        "shippingType": ["Flat"]
                    },
                    "listingInfo": {
                        "listingType": ["FixedPrice"],
                        "startTime": ["2025-05-25T12:00:00.000Z"],
                        "endTime": ["2025-06-25T12:00:00.000Z"],
                        "watchCount": ["5"]
                    },
                    "condition": {
                        "conditionId": ["1000"],
                        "conditionDisplayName": ["New"]
                    }
                },
                {
                    "itemId": ["987654321"],
                    "title": ["Test Item 2"],
                    "primaryCategory": {
                        "categoryId": ["67890"],
                        "categoryName": ["Another Category"]
                    },
                    "galleryURL": ["https://example.com/img2.jpg"],
                    "viewItemURL": ["https://example.com/item/987654321"],
                    "sellingStatus": {
                        "currentPrice": {
                            "@currencyId": "USD",
                            "__value__": "24.99"
                        },
                        "sellingState": ["Active"]
                    }
                }
            ]
        },
        "paginationOutput": {
            "pageNumber": ["1"],
            "entriesPerPage": ["2"],
            "totalPages": ["10"],
            "totalEntries": ["20"]
        }
    }
}

SHOPPING_API_RESPONSE = {
    "Ack": "Success",
    "Timestamp": "2025-05-31T12:00:00.000Z",
    "Version": "1155",
    "Build": "E1155_CORE_APIXO_19130372_R1",
    "Item": {
        "ItemID": "123456789",
        "Title": "Test Item Details",
        "Subtitle": "Item Subtitle",
        "PrimaryCategory": {
            "CategoryID": "12345",
            "CategoryName": "Test Category"
        },
        "GalleryURL": "https://example.com/img1.jpg",
        "ViewItemURLForNaturalSearch": "https://example.com/item/123456789",
        "CurrentPrice": {
            "Value": 10.99,
            "CurrencyID": "USD"
        },
        "ShippingCostSummary": {
            "ShippingServiceCost": {
                "Value": 3.99,
                "CurrencyID": "USD"
            },
            "ShippingType": "Flat"
        },
        "Seller": {
            "UserID": "test_seller",
            "FeedbackScore": 100,
            "PositiveFeedbackPercent": 99.5,
            "TopRatedSeller": true
        },
        "ConditionID": 1000,
        "ConditionDisplayName": "New",
        "ItemSpecifics": {
            "NameValueList": [
                {
                    "Name": "Brand",
                    "Value": "Test Brand"
                },
                {
                    "Name": "Model",
                    "Value": "Test Model"
                }
            ]
        },
        "Description": "This is a test item description."
    }
}

TAXONOMY_API_RESPONSE = {
    "categoryTreeId": "0",
    "categoryTreeVersion": "2.0",
    "rootCategoryNode": {
        "category": {
            "categoryId": "1",
            "categoryName": "Root Category"
        },
        "childCategoryTreeNodes": [
            {
                "category": {
                    "categoryId": "100",
                    "categoryName": "Electronics"
                },
                "childCategoryTreeNodes": [
                    {
                        "category": {
                            "categoryId": "110",
                            "categoryName": "Cameras"
                        },
                        "childCategoryTreeNodes": []
                    },
                    {
                        "category": {
                            "categoryId": "120",
                            "categoryName": "Computers"
                        },
                        "childCategoryTreeNodes": []
                    }
                ]
            },
            {
                "category": {
                    "categoryId": "200",
                    "categoryName": "Clothing"
                },
                "childCategoryTreeNodes": []
            }
        ]
    }
}

ERROR_RESPONSE = {
    "errors": [
        {
            "errorId": "35",
            "domain": "API",
            "message": "Item not found",
            "longMessage": "The requested item could not be found."
        }
    ]
}

# Save sample responses as fixtures
def save_fixture(filename, content):
    """Save fixture to file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        if isinstance(content, dict):
            json.dump(content, f, indent=2)
        else:
            f.write(content)

# Save fixtures if they don't exist
if not os.path.exists(os.path.join(FIXTURES_DIR, "oauth_token.json")):
    save_fixture("oauth_token.json", OAUTH_TOKEN_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "finding_api_response.json")):
    save_fixture("finding_api_response.json", FINDING_API_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "shopping_api_response.json")):
    save_fixture("shopping_api_response.json", SHOPPING_API_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "taxonomy_api_response.json")):
    save_fixture("taxonomy_api_response.json", TAXONOMY_API_RESPONSE)

if not os.path.exists(os.path.join(FIXTURES_DIR, "error_response.json")):
    save_fixture("error_response.json", ERROR_RESPONSE)


# Helper functions
def create_mock_response(status=200, content=None, content_type="application/json"):
    """Create a mock aiohttp response."""
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.status = status
    mock_response.headers = {"Content-Type": content_type}
    
    # Create text method
    if isinstance(content, dict):
        text_content = json.dumps(content)
    else:
        text_content = content or "{}"
    
    mock_response.text = AsyncMock(return_value=text_content)
    
    # Create json method
    json_content = content if isinstance(content, dict) else {}
    mock_response.json = AsyncMock(return_value=json_content)
    
    # Setup __aenter__ and __aexit__
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    # Setup raise_for_status
    if status >= 400:
        request_info = RequestInfo(
            url=URL("http://example.com"), 
            method="GET", 
            headers={}, 
            real_url=URL("http://example.com")
        )
        mock_response.raise_for_status = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=request_info,
                history=(),
                status=status,
                message=f"HTTP Error {status}",
            )
        )
    else:
        mock_response.raise_for_status = AsyncMock()
    
    return mock_response


# Fixtures
@pytest.fixture
def ebay_client_params():
    """Fixture for eBay API client parameters."""
    return {
        "app_id": TEST_APP_ID,
        "cert_id": TEST_CERT_ID,
        "dev_id": TEST_DEV_ID,
        "redirect_uri": TEST_REDIRECT_URI,
        "client_id": TEST_CLIENT_ID,
        "client_secret": TEST_CLIENT_SECRET,
        "use_sandbox": True,
        "global_id": GlobalId.EBAY_US,
        "timeout": 10,
        "retry_attempts": 2,
        "retry_backoff": 1.0
    }


@pytest.fixture
def mock_session():
    """Fixture for mock aiohttp ClientSession."""
    mock = MagicMock()
    
    # Setup basic mocks
    mock.closed = False
    mock.close = AsyncMock()
    
    # Setup request methods
    mock.get = AsyncMock(return_value=create_mock_response(content=OAUTH_TOKEN_RESPONSE))
    mock.post = AsyncMock(return_value=create_mock_response(content=OAUTH_TOKEN_RESPONSE))
    
    # Setup context manager
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    
    return mock


@pytest.fixture
async def ebay_client(ebay_client_params, mock_session):
    """Fixture for EbayApiClient with mocked session."""
    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = EbayApiClient(**ebay_client_params)
        client.session = mock_session
        
        # Initialize the client
        await client._init_session()
        
        # Mock the OAuth token
        client.oauth_token = OAuthToken(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=7200,
            refresh_token="test_refresh_token",
            scope="https://api.ebay.com/oauth/api_scope",
            expires_at=datetime.now() + timedelta(hours=2)
        )
        
        yield client
        
        # Clean up
        await client._close_session()


@pytest.fixture
def sync_ebay_client(ebay_client_params):
    """Fixture for SyncEbayApiClient."""
    with patch('crawlers.ebay.api.EbayApiClient'):
        client = SyncEbayApiClient(**ebay_client_params)
        yield client


# Tests for API client functionality
class TestEbayApiClient:
    """Tests for EbayApiClient."""
    
    @pytest.mark.asyncio
    async def test_authentication(self, ebay_client, mock_session):
        """Test authentication flow."""
        # Setup mock response
        mock_response = create_mock_response(content=OAUTH_TOKEN_RESPONSE)
        mock_session.post.return_value = mock_response
        
        # Test authentication
        token = await ebay_client.authenticate(refresh=True)
        
        # Verify the token
        assert token.access_token == "test_access_token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 7200
        assert token.refresh_token == "test_refresh_token"
        
        # Verify the request
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert ebay_client.token_url in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, ebay_client, mock_session):
        """Test authentication error handling."""
        # Setup mock response for error
        mock_response = create_mock_response(status=401, content={"error": "invalid_client"})
        mock_session.post.return_value = mock_response
        
        # Test authentication error
        with pytest.raises(AuthenticationError):
            await ebay_client.authenticate(refresh=True)
    
    @pytest.mark.asyncio
    async def test_token_validity(self, ebay_client):
        """Test token validity check."""
        # Valid token
        ebay_client.oauth_token = OAuthToken(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=7200,
            expires_at=datetime.now() + timedelta(hours=2)
        )
        assert ebay_client.is_token_valid() is True
        
        # Expired token
        ebay_client.oauth_token = OAuthToken(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=7200,
            expires_at=datetime.now() - timedelta(hours=1)
        )
        assert ebay_client.is_token_valid() is False
        
        # No token
        ebay_client.oauth_token = None
        assert ebay_client.is_token_valid() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test rate limiter functionality."""
        # Create a rate limiter with 2 requests per second
        rate_limiter = RateLimiter(rate_limit=2, burst_limit=3)
        
        # Should be able to make 3 requests immediately (burst limit)
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        
        # Fourth request should fail due to rate limit
        with pytest.raises(RateLimitError):
            await rate_limiter.acquire()
        
        # Wait a bit for tokens to refill
        await asyncio.sleep(1.1)  # Wait for ~2 tokens to refill
        
        # Should be able to make 2 more requests
        await rate_limiter.acquire()
        await rate_limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_search_items(self, ebay_client, mock_session):
        """Test searching for items."""
        # Setup mock response
        mock_response = create_mock_response(content=FINDING_API_RESPONSE)
        mock_session.post.return_value = mock_response
        
        # Test search
        results = await ebay_client.search_items(
            keywords="test",
            sort_order=SortOrder.BEST_MATCH,
            page=1,
            items_per_page=10
        )
        
        # Verify results
        assert isinstance(results, SearchResult)
        assert len(results.items) == 2
        assert results.pagination.page_number == 1
        assert results.pagination.total_pages == 10
        assert results.items[0].item_id == "123456789"
        assert results.items[0].title == "Test Item 1"
        
        # Verify request
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/services/search/FindingService/v1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_search_invalid_request(self, ebay_client):
        """Test searching with invalid parameters."""
        # Test search with no keywords or category
        with pytest.raises(InvalidRequestError):
            await ebay_client.search_items()
    
    @pytest.mark.asyncio
    async def test_get_item(self, ebay_client, mock_session):
        """Test getting item details."""
        # Setup mock response
        mock_response = create_mock_response(content=SHOPPING_API_RESPONSE)
        mock_session.get.return_value = mock_response
        
        # Test get item
        item = await ebay_client.get_item(TEST_ITEM_ID)
        
        # Verify item
        assert isinstance(item, Item)
        assert item.item_id == TEST_ITEM_ID
        assert item.title == "Test Item Details"
        assert item.subtitle == "Item Subtitle"
        assert item.current_price is not None
        assert item.current_price.value == Decimal("10.99")
        assert item.current_price.currency_id == "USD"
        
        # Verify request
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert "/shopping" in call_args[0][0]
        assert TEST_ITEM_ID in str(call_args[1]["params"])
    
    @pytest.mark.asyncio
    async def test_get_item_not_found(self, ebay_client, mock_session):
        """Test getting a non-existent item."""
        # Setup mock response for error
        mock_response = create_mock_response(content={
            "Ack": "Failure",
            "Errors": [
                {
                    "ErrorCode": "35",
                    "LongMessage": "Item not found"
                }
            ]
        })
        mock_session.get.return_value = mock_response
        
        # Test get item
        with pytest.raises(ItemNotFoundError):
            await ebay_client.get_item("nonexistent")
    
    @pytest.mark.asyncio
    async def test_get_categories(self, ebay_client, mock_session):
        """Test getting categories."""
        # Setup mock response
        mock_response = create_mock_response(content=TAXONOMY_API_RESPONSE)
        mock_session.get.return_value = mock_response
        
        # Test get categories
        categories = await ebay_client.get_categories()
        
        # Verify categories
        assert isinstance(categories, CategoryHierarchy)
        assert len(categories.categories) > 0
        assert categories.categories[0].category_id == "1"
        assert categories.categories[0].category_name == "Root Category"
        
        # Verify request
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert "/commerce/taxonomy/v1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_categories_with_parent(self, ebay_client, mock_session):
        """Test getting categories with parent ID."""
        # Setup mock response
        mock_response = create_mock_response(content=TAXONOMY_API_RESPONSE)
        mock_session.get.return_value = mock_response
        
        # Test get categories with parent ID
        categories = await ebay_client.get_categories(parent_id="100")
        
        # Verify categories
        assert isinstance(categories, CategoryHierarchy)
        
        # Verify request
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert "/commerce/taxonomy/v1/get_category_subtree" in call_args[0][0]
        assert "100" in str(call_args[1]["params"])


# Tests for synchronous wrapper
class TestSyncEbayApiClient:
    """Tests for SyncEbayApiClient."""
    
    def test_sync_search(self, sync_ebay_client):
        """Test synchronous search."""
        # Mock the async result
        mock_result = SearchResult(
            items=[],
            pagination=PaginationInfo(entry_per_page=10, page_number=1, total_pages=1),
            timestamp=datetime.now(),
            total_items_count=0
        )
        
        with patch.object(sync_ebay_client, '_run_async', return_value=mock_result):
            # Test sync search
            result = sync_ebay_client.search_items(keywords="test")
            
            # Verify result
            assert result == mock_result
    
    def test_sync_get_item(self, sync_ebay_client):
        """Test synchronous get item."""
        # Mock the async result
        mock_item = Item(
            item_id=TEST_ITEM_ID,
            title="Test Item"
        )
        
        with patch.object(sync_ebay_client, '_run_async', return_value=mock_item):
            # Test sync get item
            item = sync_ebay_client.get_item(TEST_ITEM_ID)
            
            # Verify item
            assert item == mock_item
    
    def test_sync_get_categories(self, sync_ebay_client):
        """Test synchronous get categories."""
        # Mock the async result
        mock_categories = CategoryHierarchy(
            categories=[],
            timestamp=datetime.now()
        )
        
        with patch.object(sync_ebay_client, '_run_async', return_value=mock_categories):
            # Test sync get categories
            categories = sync_ebay_client.get_categories()
            
            # Verify categories
            assert categories == mock_categories


# Skip real network tests by default
@pytest.mark.skip("Skip real network tests")
class TestIntegration:
    """Integration tests with real network requests."""
    
    def test_real_search(self):
        """Test real search using synchronous client."""
        # This test requires real API credentials
        client = SyncEbayApiClient(
            app_id=os.environ.get("EBAY_APP_ID", ""),
            cert_id=os.environ.get("EBAY_CERT_ID", ""),
            dev_id=os.environ.get("EBAY_DEV_ID", ""),
            redirect_uri=os.environ.get("EBAY_REDIRECT_URI", ""),
            use_sandbox=True
        )
        
        try:
            results = client.search_items(keywords="vintage camera", page=1, items_per_page=5)
            
            assert isinstance(results, SearchResult)
            assert len(results.items) > 0
            
            # Save a sample result for debugging
            save_fixture("real_search_results.json", {
                "total_items": len(results.items),
                "items": [
                    {
                        "item_id": item.item_id,
                        "title": item.title,
                        "current_price": str(item.current_price) if item.current_price else None
                    }
                    for item in results.items[:3]  # Save just a few items
                ]
            })
        finally:
            client.close()
    
    def test_real_get_item(self):
        """Test real item retrieval using synchronous client."""
        # This test requires real API credentials and a valid item ID
        client = SyncEbayApiClient(
            app_id=os.environ.get("EBAY_APP_ID", ""),
            cert_id=os.environ.get("EBAY_CERT_ID", ""),
            dev_id=os.environ.get("EBAY_DEV_ID", ""),
            redirect_uri=os.environ.get("EBAY_REDIRECT_URI", ""),
            use_sandbox=True
        )
        
        try:
            # Use a real item ID from a sandbox environment
            real_item_id = os.environ.get("EBAY_TEST_ITEM_ID", "")
            
            if not real_item_id:
                pytest.skip("No EBAY_TEST_ITEM_ID provided for integration test")
                
            item = client.get_item(real_item_id)
            
            assert isinstance(item, Item)
            assert item.item_id == real_item_id
            
            # Save a sample result for debugging
            save_fixture("real_item_details.json", {
                "item_id": item.item_id,
                "title": item.title,
                "current_price": str(item.current_price) if item.current_price else None,
                "condition": item.condition.condition_name if item.condition else None
            })
        finally:
            client.close()

