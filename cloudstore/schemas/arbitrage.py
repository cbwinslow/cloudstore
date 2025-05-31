"""
Schemas for ArbitrageOpportunity model validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from cloudstore.schemas.base import BaseSchema, BaseResponseSchema
from cloudstore.schemas.product import ProductResponse


class ArbitrageOpportunityBase(BaseSchema):
    """
    Base schema for ArbitrageOpportunity with common fields.
    
    Attributes:
        source_product_id: ID of the source product
        target_product_id: ID of the target product
        source_price: Price of the source product
        target_price: Price of the target product
        price_difference: Difference between target and source prices
        profit_margin: Profit margin percentage
        currency: Currency code
        shipping_source_to_customer: Estimated shipping cost
        other_fees: Other fees
        estimated_net_profit: Estimated net profit
        confidence_score: Match confidence score (0-100)
        is_active: Whether the opportunity is active
        is_verified: Whether the opportunity has been verified
        notes: Additional notes
    """
    source_product_id: int = Field(..., description="ID of the source product")
    target_product_id: int = Field(..., description="ID of the target product")
    source_price: float = Field(..., description="Price of the source product", ge=0)
    target_price: float = Field(..., description="Price of the target product", ge=0)
    price_difference: float = Field(..., description="Difference between target and source prices")
    profit_margin: float = Field(..., description="Profit margin percentage")
    currency: str = Field("USD", description="Currency code", min_length=3, max_length=3)
    shipping_source_to_customer: Optional[float] = Field(None, description="Estimated shipping cost", ge=0)
    other_fees: Optional[float] = Field(None, description="Other fees", ge=0)
    estimated_net_profit: float = Field(..., description="Estimated net profit")
    confidence_score: Optional[float] = Field(None, description="Match confidence score (0-100)", ge=0, le=100)
    is_active: bool = Field(True, description="Whether the opportunity is active")
    is_verified: bool = Field(False, description="Whether the opportunity has been verified")
    notes: Optional[str] = Field(None, description="Additional notes")


class ArbitrageOpportunityCreate(ArbitrageOpportunityBase):
    """Schema for creating a new arbitrage opportunity."""
    
    @model_validator(mode='after')
    def validate_opportunity(self) -> 'ArbitrageOpportunityCreate':
        """Validate arbitrage opportunity data."""
        # Ensure source and target products are different
        if self.source_product_id == self.target_product_id:
            raise ValueError("Source and target products must be different")
        
        # Calculate price difference if not provided
        if self.price_difference is None:
            self.price_difference = self.target_price - self.source_price
        
        # Calculate profit margin if not provided
        if self.profit_margin is None and self.source_price > 0:
            self.profit_margin = (self.price_difference / self.source_price) * 100
        
        # Calculate estimated net profit if not provided
        if self.estimated_net_profit is None:
            shipping = self.shipping_source_to_customer or 0
            fees = self.other_fees or 0
            self.estimated_net_profit = self.price_difference - shipping - fees
        
        # Validate that there's a positive arbitrage opportunity
        if self.estimated_net_profit <= 0:
            raise ValueError("Estimated net profit must be positive")
            
        return self


class ArbitrageOpportunityUpdate(BaseSchema):
    """
    Schema for updating an existing arbitrage opportunity.
    All fields are optional.
    """
    source_price: Optional[float] = Field(None, description="Price of the source product", ge=0)
    target_price: Optional[float] = Field(None, description="Price of the target product", ge=0)
    price_difference: Optional[float] = Field(None, description="Difference between target and source prices")
    profit_margin: Optional[float] = Field(None, description="Profit margin percentage")
    shipping_source_to_customer: Optional[float] = Field(None, description="Estimated shipping cost", ge=0)
    other_fees: Optional[float] = Field(None, description="Other fees", ge=0)
    estimated_net_profit: Optional[float] = Field(None, description="Estimated net profit")
    confidence_score: Optional[float] = Field(None, description="Match confidence score (0-100)", ge=0, le=100)
    is_active: Optional[bool] = Field(None, description="Whether the opportunity is active")
    is_verified: Optional[bool] = Field(None, description="Whether the opportunity has been verified")
    notes: Optional[str] = Field(None, description="Additional notes")


class ArbitrageOpportunityResponse(ArbitrageOpportunityBase, BaseResponseSchema):
    """Schema for arbitrage opportunity response including ID and timestamps."""
    
    class Config:
        """Configuration for the ArbitrageOpportunityResponse schema."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "source_product_id": 1,
                "target_product_id": 2,
                "source_price": 199.99,
                "target_price": 299.99,
                "price_difference": 100.0,
                "profit_margin": 50.0,
                "currency": "USD",
                "shipping_source_to_customer": 15.0,
                "other_fees": 10.0,
                "estimated_net_profit": 75.0,
                "confidence_score": 85.0,
                "is_active": True,
                "is_verified": False,
                "notes": "Good opportunity with high confidence score",
                "identified_at": "2025-05-31T00:00:00Z",
                "created_at": "2025-05-31T00:00:00Z",
                "updated_at": None
            }
        }


class ArbitrageOpportunityDetailResponse(ArbitrageOpportunityResponse):
    """
    Schema for detailed arbitrage opportunity response including source and target products.
    
    Attributes:
        source_product: Source product details
        target_product: Target product details
    """
    source_product: ProductResponse
    target_product: ProductResponse


class ArbitrageAnalysisRequest(BaseSchema):
    """
    Schema for arbitrage analysis request.
    
    Attributes:
        product_ids: List of product IDs to analyze
        min_profit_margin: Minimum profit margin to consider
        max_shipping_cost: Maximum shipping cost to consider
        confidence_threshold: Minimum confidence score to consider
    """
    product_ids: Optional[List[int]] = Field(None, description="List of product IDs to analyze")
    min_profit_margin: float = Field(10.0, description="Minimum profit margin to consider", ge=0)
    max_shipping_cost: Optional[float] = Field(None, description="Maximum shipping cost to consider", ge=0)
    confidence_threshold: float = Field(70.0, description="Minimum confidence score to consider", ge=0, le=100)


class ArbitrageAnalysisResponse(BaseSchema):
    """
    Schema for arbitrage analysis response.
    
    Attributes:
        opportunities: List of arbitrage opportunities
        total_found: Total number of opportunities found
        total_profit_potential: Total potential profit
        average_profit_margin: Average profit margin
    """
    opportunities: List[ArbitrageOpportunityResponse]
    total_found: int
    total_profit_potential: float
    average_profit_margin: float

