"""
API routes for product management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import or_, and_, desc, asc

from cloudstore.database.models import Product, PriceHistory, SiteEnum, ConditionEnum
from cloudstore.schemas.product import (
    ProductCreate, 
    ProductUpdate, 
    ProductResponse, 
    ProductSearchParams,
)
from cloudstore.schemas.base import PaginatedResponse
from cloudstore.api.deps import get_db

# Create router
router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Product not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@router.get("/", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    db: Session = Depends(get_db),
    site: Optional[SiteEnum] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """
    List products with pagination.
    
    Args:
        db: Database session
        site: Filter by site
        is_active: Filter by active status
        page: Page number
        page_size: Items per page
        
    Returns:
        Paginated list of products
    """
    # Base query
    query = db.query(Product)
    
    # Apply filters
    if site:
        query = query.filter(Product.site == site)
    query = query.filter(Product.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get paginated results
    items = query.order_by(desc(Product.created_at)).offset(offset).limit(page_size).all()
    
    # Return paginated response
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int = Path(..., description="ID of the product to get"),
    db: Session = Depends(get_db),
):
    """
    Get a product by ID.
    
    Args:
        product_id: ID of the product to get
        db: Database session
        
    Returns:
        Product details
        
    Raises:
        HTTPException: If product not found
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    return product


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new product.
    
    Args:
        product: Product data
        db: Database session
        
    Returns:
        Created product
        
    Raises:
        HTTPException: If product already exists or creation fails
    """
    # Check if product with same site and site_id already exists
    existing_product = (
        db.query(Product)
        .filter(Product.site == product.site, Product.site_id == product.site_id)
        .first()
    )
    
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product from {product.site.value} with site_id {product.site_id} already exists",
        )
    
    # Create new product
    try:
        db_product = Product(**product.model_dump())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
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


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_update: ProductUpdate,
    product_id: int = Path(..., description="ID of the product to update"),
    db: Session = Depends(get_db),
):
    """
    Update a product.
    
    Args:
        product_update: Product update data
        product_id: ID of the product to update
        db: Database session
        
    Returns:
        Updated product
        
    Raises:
        HTTPException: If product not found or update fails
    """
    # Get existing product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Update product
    try:
        # Filter out None values
        update_data = {
            k: v for k, v in product_update.model_dump().items() 
            if v is not None
        }
        
        # Apply updates
        for key, value in update_data.items():
            setattr(product, key, value)
        
        # Commit changes
        db.commit()
        db.refresh(product)
        return product
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


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int = Path(..., description="ID of the product to delete"),
    db: Session = Depends(get_db),
):
    """
    Delete a product.
    
    Args:
        product_id: ID of the product to delete
        db: Database session
        
    Returns:
        No content
        
    Raises:
        HTTPException: If product not found or deletion fails
    """
    # Get existing product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Delete product
    try:
        db.delete(product)
        db.commit()
        return None
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/search/", response_model=PaginatedResponse[ProductResponse])
async def search_products(
    search_params: ProductSearchParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Search products with filtering and pagination.
    
    Args:
        search_params: Search parameters
        db: Database session
        
    Returns:
        Paginated list of products matching search criteria
    """
    # Base query
    query = db.query(Product)
    
    # Apply filters
    filters = []
    
    # Text search
    if search_params.query:
        search_term = f"%{search_params.query}%"
        filters.append(
            or_(
                Product.title.ilike(search_term),
                Product.description.ilike(search_term),
                Product.brand.ilike(search_term),
                Product.model.ilike(search_term),
            )
        )
    
    # Categorical filters
    if search_params.site:
        filters.append(Product.site == search_params.site)
    
    if search_params.category:
        filters.append(Product.category == search_params.category)
    
    if search_params.brand:
        filters.append(Product.brand == search_params.brand)
    
    if search_params.condition:
        filters.append(Product.condition == search_params.condition)
    
    # Price filters - requires a join with the most recent price history
    if search_params.min_price is not None or search_params.max_price is not None:
        # This subquery gets the most recent price for each product
        price_subquery = (
            db.query(
                PriceHistory.product_id,
                PriceHistory.total_price.label("price"),
            )
            .distinct(PriceHistory.product_id)
            .order_by(
                PriceHistory.product_id,
                desc(PriceHistory.timestamp),
            )
            .subquery()
        )
        
        query = query.join(
            price_subquery,
            Product.id == price_subquery.c.product_id,
        )
        
        if search_params.min_price is not None:
            filters.append(price_subquery.c.price >= search_params.min_price)
        
        if search_params.max_price is not None:
            filters.append(price_subquery.c.price <= search_params.max_price)
    
    # Apply all filters
    if filters:
        query = query.filter(and_(*filters))
    
    # Get total count
    total = query.count()
    
    # Sort
    if search_params.sort_by:
        sort_column = getattr(Product, search_params.sort_by, Product.created_at)
        if search_params.sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(desc(Product.created_at))
    
    # Pagination
    offset = (search_params.page - 1) * search_params.page_size
    items = query.offset(offset).limit(search_params.page_size).all()
    
    # Calculate total pages
    total_pages = (total + search_params.page_size - 1) // search_params.page_size
    
    # Return paginated response
    return PaginatedResponse(
        items=items,
        total=total,
        page=search_params.page,
        page_size=search_params.page_size,
        total_pages=total_pages,
    )

