"""
Schemas for PriceHistory model validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from cloudstore.schemas.base import BaseSchema, BaseResponseSchema


class PriceHistoryBase(BaseSchema):
    """
    Base schema for PriceHistory with common fields.
    
    Attributes:
        product_id: ID of the product
        price: Current price
        shipping_cost: Shipping cost
        total_price: Total price (price + shipping_cost)
        currency: Currency code (default: USD)
        is_sale_price: Whether the price is a sale price
        regular_price: Regular price if on sale
        timestamp: Time when the price was recorded
    """
    product_id: int = Field(..., description="ID of the product")
    price: float = Field(..., description="Current price", ge=0)
    shipping_cost: Optional[float] = Field(0.0, description="Shipping cost", ge=0)
    total_price: float = Field(..., description="Total price (price + shipping_cost)", ge=0)
    currency: str = Field("USD", description="Currency code", min_length=3, max_length=3)
    is_sale_price: bool = Field(False, description="Whether the price is a sale price")
    regular_price: Optional[float] = Field(None, description="Regular price if on sale")


class PriceHistoryCreate(PriceHistoryBase):
    """Schema for creating a new price history record."""
    timestamp: Optional[datetime] = Field(None, description="Time when the price was recorded")
    
    @model_validator(mode='after')
    def calculate_total_price(self) -> 'PriceHistoryCreate':
        """Calculate total price if not provided."""
        if self.shipping_cost is None:
            self.shipping_cost = 0.0
            
        if self.total_price is None:
            self.total_price = self.price + self.shipping_cost
        
        # Validate sale price and regular price
        if self.is_sale_price and self.regular_price is None:
            raise ValueError("Regular price must be provided for sale prices")
        
        # Validate regular price is higher than sale price
        if self.is_sale_price and self.regular_price <= self.price:
            raise ValueError("Regular price must be higher than sale price")
            
        return self


class PriceHistoryResponse(PriceHistoryBase, BaseResponseSchema):
    """Schema for price history response including ID and timestamps."""
    
    class Config:
        """Configuration for the PriceHistoryResponse schema."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "product_id": 1,
                "price": 249.99,
                "shipping_cost": 0.0,
                "total_price": 249.99,
                "currency": "USD",
                "is_sale_price": True,
                "regular_price": 299.99,
                "timestamp": "2025-05-31T00:00:00Z",
                "created_at": "2025-05-31T00:00:00Z",
                "updated_at": None
            }
        }


class PriceTrend(BaseSchema):
    """
    Schema for price trend data.
    
    Attributes:
        timestamp: Time point
        price: Price at that time
    """
    timestamp: datetime
    price: float


class PriceAnalytics(BaseSchema):
    """
    Schema for price analytics response.
    
    Attributes:
        product_id: ID of the product
        current_price: Current price
        highest_price: Highest recorded price
        lowest_price: Lowest recorded price
        average_price: Average price
        price_change_30d: Price change in the last 30 days
        price_change_90d: Price change in the last 90 days
        price_trend: Price trend data
    """
    product_id: int
    current_price: float
    highest_price: float
    lowest_price: float
    average_price: float
    price_change_30d: float
    price_change_90d: float
    price_trend: List[PriceTrend]
    
    class Config:
        """Configuration for the PriceAnalytics schema."""
        json_schema_extra = {
            "example": {
                "product_id": 1,
                "current_price": 249.99,
                "highest_price": 299.99,
                "lowest_price": 229.99,
                "average_price": 259.99,
                "price_change_30d": -20.0,
                "price_change_90d": -30.0,
                "price_trend": [
                    {"timestamp": "2025-05-01T00:00:00Z", "price": 279.99},
                    {"timestamp": "2025-05-15T00:00:00Z", "price": 269.99},
                    {"timestamp": "2025-05-31T00:00:00Z", "price": 249.99}
                ]
            }
        }

