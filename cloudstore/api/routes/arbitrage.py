"""
API routes for arbitrage opportunity management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import desc, and_, or_, func

from cloudstore.database.models import ArbitrageOpportunity, Product, PriceHistory
from cloudstore.schemas.arbitrage import (
    ArbitrageOpportunityCreate,
    ArbitrageOpportunityUpdate,
    ArbitrageOpportunityResponse,
    ArbitrageOpportunityDetailResponse,
    ArbitrageAnalysisRequest,
    ArbitrageAnalysisResponse,
)
from cloudstore.schemas.base import PaginatedResponse
from cloudstore.api.deps import get_db

# Create router
router = APIRouter(
    prefix="/arbitrage",
    tags=["arbitrage"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@router.get("/opportunities", response_model=PaginatedResponse[ArbitrageOpportunityResponse])
async def list_opportunities(
    min_profit: Optional[float] = Query(None, description="Minimum profit margin"),
    max_profit: Optional[float] = Query(None, description="Maximum profit margin"),
    min_confidence: Optional[float] = Query(None, description="Minimum confidence score"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verified status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("profit_margin", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db),
):
    """
    List arbitrage opportunities with filtering and pagination.
    
    Args:
        min_profit: Minimum profit margin
        max_profit: Maximum profit margin
        min_confidence: Minimum confidence score
        is_active: Filter by active status
        is_verified: Filter by verified status
        page: Page number
        page_size: Items per page
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        db: Database session
        
    Returns:
        Paginated list of arbitrage opportunities
    """
    # Base query
    query = db.query(ArbitrageOpportunity)
    
    # Apply filters
    if min_profit is not None:
        query = query.filter(ArbitrageOpportunity.profit_margin >= min_profit)
    if max_profit is not None:
        query = query.filter(ArbitrageOpportunity.profit_margin <= max_profit)
    if min_confidence is not None:
        query = query.filter(ArbitrageOpportunity.confidence_score >= min_confidence)
    if is_active is not None:
        query = query.filter(ArbitrageOpportunity.is_active == is_active)
    if is_verified is not None:
        query = query.filter(ArbitrageOpportunity.is_verified == is_verified)
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(ArbitrageOpportunity, sort_by, ArbitrageOpportunity.profit_margin)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size
    
    # Return paginated response
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/opportunities/{opportunity_id}", response_model=ArbitrageOpportunityDetailResponse)
async def get_opportunity(
    opportunity_id: int = Path(..., description="ID of the opportunity"),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about an arbitrage opportunity.
    
    Args:
        opportunity_id: ID of the opportunity
        db: Database session
        
    Returns:
        Detailed arbitrage opportunity information
        
    Raises:
        HTTPException: If opportunity not found
    """
    # Query with joined load to get products
    opportunity = (
        db.query(ArbitrageOpportunity)
        .options(
            joinedload(ArbitrageOpportunity.source_product),
            joinedload(ArbitrageOpportunity.target_product),
        )
        .filter(ArbitrageOpportunity.id == opportunity_id)
        .first()
    )
    
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arbitrage opportunity with ID {opportunity_id} not found",
        )
    
    return opportunity


@router.post("/opportunities", response_model=ArbitrageOpportunityResponse, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    opportunity: ArbitrageOpportunityCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new arbitrage opportunity.
    
    Args:
        opportunity: Arbitrage opportunity data
        db: Database session
        
    Returns:
        Created arbitrage opportunity
        
    Raises:
        HTTPException: If products not found or creation fails
    """
    # Check if source product exists
    source_product = db.query(Product).filter(Product.id == opportunity.source_product_id).first()
    if not source_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source product with ID {opportunity.source_product_id} not found",
        )
    
    # Check if target product exists
    target_product = db.query(Product).filter(Product.id == opportunity.target_product_id).first()
    if not target_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target product with ID {opportunity.target_product_id} not found",
        )
    
    # Check if opportunity already exists
    existing = (
        db.query(ArbitrageOpportunity)
        .filter(
            ArbitrageOpportunity.source_product_id == opportunity.source_product_id,
            ArbitrageOpportunity.target_product_id == opportunity.target_product_id,
        )
        .first()
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Arbitrage opportunity between products {opportunity.source_product_id} and {opportunity.target_product_id} already exists",
        )
    
    # Create opportunity
    try:
        db_opportunity = ArbitrageOpportunity(**opportunity.model_dump())
        db_opportunity.identified_at = datetime.utcnow()
        
        db.add(db_opportunity)
        db.commit()
        db.refresh(db_opportunity)
        
        return db_opportunity
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


@router.put("/opportunities/{opportunity_id}", response_model=ArbitrageOpportunityResponse)
async def update_opportunity(
    opportunity_update: ArbitrageOpportunityUpdate,
    opportunity_id: int = Path(..., description="ID of the opportunity to update"),
    db: Session = Depends(get_db),
):
    """
    Update an arbitrage opportunity.
    
    Args:
        opportunity_update: Updated opportunity data
        opportunity_id: ID of the opportunity to update
        db: Database session
        
    Returns:
        Updated arbitrage opportunity
        
    Raises:
        HTTPException: If opportunity not found or update fails
    """
    # Get existing opportunity
    opportunity = db.query(ArbitrageOpportunity).filter(ArbitrageOpportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arbitrage opportunity with ID {opportunity_id} not found",
        )
    
    # Update opportunity
    try:
        # Filter out None values
        update_data = {
            k: v for k, v in opportunity_update.model_dump().items() 
            if v is not None
        }
        
        # Apply updates
        for key, value in update_data.items():
            setattr(opportunity, key, value)
        
        # Commit changes
        db.commit()
        db.refresh(opportunity)
        return opportunity
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.post("/analyze", response_model=ArbitrageAnalysisResponse)
async def analyze_arbitrage_opportunities(
    analysis_request: ArbitrageAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze products for potential arbitrage opportunities.
    
    Args:
        analysis_request: Analysis parameters
        db: Database session
        
    Returns:
        Analysis results with identified opportunities
    """
    # Start with the base product query
    product_query = db.query(Product)
    
    # If specific product IDs are provided, filter by them
    if analysis_request.product_ids:
        product_query = product_query.filter(Product.id.in_(analysis_request.product_ids))
    
    # Only include active products
    product_query = product_query.filter(Product.is_active == True)
    
    # Get all products
    products = product_query.all()
    
    if not products:
        # Return empty results if no products found
        return ArbitrageAnalysisResponse(
            opportunities=[],
            total_found=0,
            total_profit_potential=0.0,
            average_profit_margin=0.0,
        )
    
    # Get the latest price for each product
    # This could be optimized with a subquery for better performance
    product_prices = {}
    for product in products:
        latest_price = (
            db.query(PriceHistory)
            .filter(PriceHistory.product_id == product.id)
            .order_by(desc(PriceHistory.timestamp))
            .first()
        )
        
        if latest_price:
            product_prices[product.id] = latest_price.total_price
    
    # Identify potential opportunities
    opportunities = []
    for source_product in products:
        if source_product.id not in product_prices:
            continue  # Skip products without price data
            
        for target_product in products:
            # Skip self-comparison
            if source_product.id == target_product.id:
                continue
                
            # Skip if target product has no price
            if target_product.id not in product_prices:
                continue
                
            source_price = product_prices[source_product.id]
            target_price = product_prices[target_product.id]
            
            # Skip if target price is not higher than source price
            if target_price <= source_price:
                continue
                
            # Calculate price difference and profit margin
            price_difference = target_price - source_price
            profit_margin = (price_difference / source_price) * 100
            
            # Skip if profit margin is below threshold
            if profit_margin < analysis_request.min_profit_margin:
                continue
                
            # Estimate shipping cost (simplified, in real-world this would be more complex)
            shipping_cost = analysis_request.max_shipping_cost if analysis_request.max_shipping_cost is not None else 0
            
            # Calculate estimated net profit
            estimated_net_profit = price_difference - shipping_cost
            
            # Skip if not profitable after shipping
            if estimated_net_profit <= 0:
                continue
                
            # Calculate confidence score
            # In a real system, this would use more sophisticated matching and analysis
            # For simplicity, we'll use a basic algorithm
            confidence_score = calculate_confidence_score(source_product, target_product)
            
            # Skip if confidence score is below threshold
            if confidence_score < analysis_request.confidence_threshold:
                continue
                
            # Check if opportunity already exists in database
            existing = (
                db.query(ArbitrageOpportunity)
                .filter(
                    ArbitrageOpportunity.source_product_id == source_product.id,
                    ArbitrageOpportunity.target_product_id == target_product.id,
                )
                .first()
            )
            
            if existing:
                # Update existing opportunity
                existing.source_price = source_price
                existing.target_price = target_price
                existing.price_difference = price_difference
                existing.profit_margin = profit_margin
                existing.shipping_source_to_customer = shipping_cost
                existing.estimated_net_profit = estimated_net_profit
                existing.confidence_score = confidence_score
                db.add(existing)
                opportunities.append(existing)
            else:
                # Create new opportunity
                new_opportunity = ArbitrageOpportunity(
                    source_product_id=source_product.id,
                    target_product_id=target_product.id,
                    source_price=source_price,
                    target_price=target_price,
                    price_difference=price_difference,
                    profit_margin=profit_margin,
                    currency="USD",  # Assuming USD for simplicity
                    shipping_source_to_customer=shipping_cost,
                    estimated_net_profit=estimated_net_profit,
                    confidence_score=confidence_score,
                    is_active=True,
                    is_verified=False,
                    identified_at=datetime.utcnow(),
                )
                db.add(new_opportunity)
                opportunities.append(new_opportunity)
    
    # Commit changes
    try:
        db.commit()
        
        # Refresh objects to get their IDs
        for opportunity in opportunities:
            db.refresh(opportunity)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving arbitrage opportunities",
        )
    
    # Calculate summary statistics
    total_found = len(opportunities)
    total_profit_potential = sum(o.estimated_net_profit for o in opportunities)
    average_profit_margin = sum(o.profit_margin for o in opportunities) / total_found if total_found > 0 else 0.0
    
    # Return analysis results
    return ArbitrageAnalysisResponse(
        opportunities=opportunities,
        total_found=total_found,
        total_profit_potential=total_profit_potential,
        average_profit_margin=average_profit_margin,
    )


@router.patch("/opportunities/{opportunity_id}/status", response_model=ArbitrageOpportunityResponse)
async def update_opportunity_status(
    opportunity_id: int = Path(..., description="ID of the opportunity"),
    is_active: Optional[bool] = Query(None, description="Active status"),
    is_verified: Optional[bool] = Query(None, description="Verified status"),
    notes: Optional[str] = Body(None, description="Additional notes"),
    db: Session = Depends(get_db),
):
    """
    Update the status of an arbitrage opportunity.
    
    Args:
        opportunity_id: ID of the opportunity
        is_active: Active status
        is_verified: Verified status
        notes: Additional notes
        db: Database session
        
    Returns:
        Updated arbitrage opportunity
        
    Raises:
        HTTPException: If opportunity not found or update fails
    """
    # Get existing opportunity
    opportunity = db.query(ArbitrageOpportunity).filter(ArbitrageOpportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arbitrage opportunity with ID {opportunity_id} not found",
        )
    
    # Update status
    try:
        if is_active is not None:
            opportunity.is_active = is_active
        if is_verified is not None:
            opportunity.is_verified = is_verified
        if notes is not None:
            opportunity.notes = notes
        
        db.commit()
        db.refresh(opportunity)
        return opportunity
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


def calculate_confidence_score(source_product: Product, target_product: Product) -> float:
    """
    Calculate confidence score for matching products.
    
    In a real system, this would be a sophisticated algorithm using
    various product attributes, NLP, and possibly ML models.
    
    For this example, we'll use a simplified approach.
    
    Args:
        source_product: Source product
        target_product: Target product
        
    Returns:
        Confidence score (0-100)
    """
    score = 0.0
    
    # Check if products are from different sites
    if source_product.site != target_product.site:
        score += 20.0  # Different sites are good for arbitrage
    
    # Compare titles (very basic)
    title_similarity = calculate_title_similarity(source_product.title, target_product.title)
    score += title_similarity * 30.0
    
    # Compare brands
    if source_product.brand and target_product.brand:
        if source_product.brand.lower() == target_product.brand.lower():
            score += 20.0
    
    # Compare models
    if source_product.model and target_product.model:
        if source_product.model.lower() == target_product.model.lower():
            score += 20.0
    
    # Compare categories
    if source_product.category and target_product.category:
        if source_product.category.lower() == target_product.category.lower():
            score += 10.0
    
    # Cap score at 100
    return min(score, 100.0)


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between product titles.
    
    In a real system, this would use NLP techniques like TF-IDF,
    word embeddings, or even more advanced ML models.
    
    For this example, we'll use a very basic approach.
    
    Args:
        title1: First title
        title2: Second title
        
    Returns:
        Similarity score (0-1)
    """
    # Convert to lowercase
    t1 = title1.lower()
    t2 = title2.lower()
    
    # Count matching words
    words1 = set(t1.split())
    words2 = set(t2.split())
    
    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
        
    return intersection / union

