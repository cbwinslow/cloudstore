"""
API routes for price history tracking and analytics.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import desc, func, extract, text

from cloudstore.database.models import Product, PriceHistory
from cloudstore.schemas.price import (
    PriceHistoryCreate,
    PriceHistoryResponse,
    PriceAnalytics,
    PriceTrend,
)
from cloudstore.schemas.base import PaginatedResponse
from cloudstore.api.deps import get_db

# Create router
router = APIRouter(
    prefix="/prices",
    tags=["prices"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Product not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@router.post("/", response_model=PriceHistoryResponse, status_code=status.HTTP_201_CREATED)
async def record_price(
    price_data: PriceHistoryCreate,
    db: Session = Depends(get_db),
):
    """
    Record a new price point for a product.
    
    Args:
        price_data: Price data
        db: Database session
        
    Returns:
        Created price history record
        
    Raises:
        HTTPException: If product not found or creation fails
    """
    # Check if product exists
    product = db.query(Product).filter(Product.id == price_data.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {price_data.product_id} not found",
        )
    
    # Create price history record
    try:
        # If timestamp not provided, use current time
        if price_data.timestamp is None:
            price_data.timestamp = datetime.utcnow()
            
        # Create record
        db_price = PriceHistory(**price_data.model_dump())
        db.add(db_price)
        db.commit()
        db.refresh(db_price)
        return db_price
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Database integrity error: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/history/{product_id}", response_model=PaginatedResponse[PriceHistoryResponse])
async def get_price_history(
    product_id: int = Path(..., description="ID of the product"),
    start_date: Optional[datetime] = Query(None, description="Start date for history"),
    end_date: Optional[datetime] = Query(None, description="End date for history"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Get price history for a product.
    
    Args:
        product_id: ID of the product
        start_date: Start date for history
        end_date: End date for history
        page: Page number
        page_size: Items per page
        db: Database session
        
    Returns:
        Paginated list of price history records
        
    Raises:
        HTTPException: If product not found
    """
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Base query
    query = db.query(PriceHistory).filter(PriceHistory.product_id == product_id)
    
    # Apply date filters
    if start_date:
        query = query.filter(PriceHistory.timestamp >= start_date)
    if end_date:
        query = query.filter(PriceHistory.timestamp <= end_date)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get paginated results ordered by timestamp (newest first)
    items = query.order_by(desc(PriceHistory.timestamp)).offset(offset).limit(page_size).all()
    
    # Return paginated response
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/analytics/{product_id}", response_model=PriceAnalytics)
async def get_price_analytics(
    product_id: int = Path(..., description="ID of the product"),
    days: int = Query(90, ge=1, le=365, description="Number of days for analysis"),
    db: Session = Depends(get_db),
):
    """
    Get price analytics for a product.
    
    Args:
        product_id: ID of the product
        days: Number of days for analysis
        db: Database session
        
    Returns:
        Price analytics
        
    Raises:
        HTTPException: If product not found or no price data available
    """
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get all price history within the date range
    price_history = (
        db.query(PriceHistory)
        .filter(
            PriceHistory.product_id == product_id,
            PriceHistory.timestamp >= start_date,
            PriceHistory.timestamp <= end_date,
        )
        .order_by(PriceHistory.timestamp)
        .all()
    )
    
    # Check if there's any price data
    if not price_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price data available for product with ID {product_id}",
        )
    
    # Get current price (most recent)
    current_price = price_history[-1].total_price
    
    # Calculate metrics
    prices = [record.total_price for record in price_history]
    highest_price = max(prices)
    lowest_price = min(prices)
    average_price = statistics.mean(prices)
    
    # Calculate price changes
    # For 30 days
    thirty_days_ago = end_date - timedelta(days=30)
    price_30d = next(
        (record.total_price for record in price_history if record.timestamp <= thirty_days_ago),
        prices[0],  # Use earliest price if no data from 30 days ago
    )
    price_change_30d = current_price - price_30d
    
    # For 90 days
    ninety_days_ago = end_date - timedelta(days=90)
    price_90d = next(
        (record.total_price for record in price_history if record.timestamp <= ninety_days_ago),
        prices[0],  # Use earliest price if no data from 90 days ago
    )
    price_change_90d = current_price - price_90d
    
    # Generate price trend data
    # Group by week if many data points
    if len(price_history) > 30:
        # Group by week
        weekly_prices = defaultdict(list)
        for record in price_history:
            # Get the week number
            week_key = record.timestamp.isocalendar()[1]
            weekly_prices[week_key].append(record.total_price)
            
        # Average price for each week
        trend_data = [
            PriceTrend(
                timestamp=datetime.strptime(f"{end_date.year}-W{week}-1", "%Y-W%W-%w"),
                price=statistics.mean(prices),
            )
            for week, prices in sorted(weekly_prices.items())
        ]
    else:
        # Use all data points if not too many
        trend_data = [
            PriceTrend(timestamp=record.timestamp, price=record.total_price)
            for record in price_history
        ]
    
    # Return analytics
    return PriceAnalytics(
        product_id=product_id,
        current_price=current_price,
        highest_price=highest_price,
        lowest_price=lowest_price,
        average_price=average_price,
        price_change_30d=price_change_30d,
        price_change_90d=price_change_90d,
        price_trend=trend_data,
    )


@router.get("/stats/daily/{product_id}", response_model=List[Dict[str, Any]])
async def get_daily_price_stats(
    product_id: int = Path(..., description="ID of the product"),
    days: int = Query(30, ge=1, le=365, description="Number of days for stats"),
    db: Session = Depends(get_db),
):
    """
    Get daily price statistics for a product.
    
    Args:
        product_id: ID of the product
        days: Number of days for stats
        db: Database session
        
    Returns:
        List of daily price statistics
        
    Raises:
        HTTPException: If product not found or no price data available
    """
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get daily price statistics using SQL aggregation
    daily_stats = (
        db.query(
            func.date(PriceHistory.timestamp).label("date"),
            func.min(PriceHistory.total_price).label("min_price"),
            func.max(PriceHistory.total_price).label("max_price"),
            func.avg(PriceHistory.total_price).label("avg_price"),
            func.count(PriceHistory.id).label("data_points"),
        )
        .filter(
            PriceHistory.product_id == product_id,
            PriceHistory.timestamp >= start_date,
            PriceHistory.timestamp <= end_date,
        )
        .group_by(func.date(PriceHistory.timestamp))
        .order_by(func.date(PriceHistory.timestamp))
        .all()
    )
    
    # Check if there's any price data
    if not daily_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price data available for product with ID {product_id}",
        )
    
    # Convert to list of dictionaries
    result = [
        {
            "date": stats.date.isoformat(),
            "min_price": stats.min_price,
            "max_price": stats.max_price,
            "avg_price": float(stats.avg_price),  # Convert Decimal to float
            "data_points": stats.data_points,
        }
        for stats in daily_stats
    ]
    
    return result

