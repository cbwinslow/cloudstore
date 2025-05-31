"""
API routes for proxy configuration management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import desc, asc, and_, or_, func

from cloudstore.database.models import ProxyConfig, SiteMetadata, SiteEnum
from cloudstore.schemas.proxy import (
    ProxyConfigCreate,
    ProxyConfigUpdate,
    ProxyConfigResponse,
    ProxyStatusResponse,
)
from cloudstore.schemas.base import PaginatedResponse
from cloudstore.api.deps import get_db

# Create router
router = APIRouter(
    prefix="/proxies",
    tags=["proxies"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Proxy not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@router.get("/", response_model=PaginatedResponse[ProxyConfigResponse])
async def list_proxies(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    protocol: Optional[str] = Query(None, description="Filter by protocol"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db),
):
    """
    List proxy configurations with filtering and pagination.
    
    Args:
        is_active: Filter by active status
        provider: Filter by provider
        country: Filter by country code
        protocol: Filter by protocol
        page: Page number
        page_size: Items per page
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        db: Database session
        
    Returns:
        Paginated list of proxy configurations
    """
    # Base query
    query = db.query(ProxyConfig)
    
    # Apply filters
    if is_active is not None:
        query = query.filter(ProxyConfig.is_active == is_active)
    if provider:
        query = query.filter(ProxyConfig.provider == provider)
    if country:
        query = query.filter(ProxyConfig.country == country)
    if protocol:
        query = query.filter(ProxyConfig.protocol == protocol)
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(ProxyConfig, sort_by, ProxyConfig.created_at)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))
    
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


@router.post("/", response_model=ProxyConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy(
    proxy: ProxyConfigCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new proxy configuration.
    
    Args:
        proxy: Proxy configuration data
        db: Database session
        
    Returns:
        Created proxy configuration
        
    Raises:
        HTTPException: If proxy already exists or creation fails
    """
    # Check if proxy already exists
    existing = (
        db.query(ProxyConfig)
        .filter(
            ProxyConfig.ip_address == proxy.ip_address,
            ProxyConfig.port == proxy.port,
            ProxyConfig.protocol == proxy.protocol,
        )
        .first()
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proxy with IP {proxy.ip_address}, port {proxy.port}, and protocol {proxy.protocol} already exists",
        )
    
    # Create proxy
    try:
        db_proxy = ProxyConfig(**proxy.model_dump())
        db.add(db_proxy)
        db.commit()
        db.refresh(db_proxy)
        return db_proxy
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


@router.get("/{proxy_id}", response_model=ProxyConfigResponse)
async def get_proxy(
    proxy_id: int = Path(..., description="ID of the proxy"),
    db: Session = Depends(get_db),
):
    """
    Get a proxy configuration by ID.
    
    Args:
        proxy_id: ID of the proxy
        db: Database session
        
    Returns:
        Proxy configuration
        
    Raises:
        HTTPException: If proxy not found
    """
    proxy = db.query(ProxyConfig).filter(ProxyConfig.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy with ID {proxy_id} not found",
        )
    
    return proxy


@router.put("/{proxy_id}", response_model=ProxyConfigResponse)
async def update_proxy(
    proxy_update: ProxyConfigUpdate,
    proxy_id: int = Path(..., description="ID of the proxy to update"),
    db: Session = Depends(get_db),
):
    """
    Update a proxy configuration.
    
    Args:
        proxy_update: Updated proxy data
        proxy_id: ID of the proxy to update
        db: Database session
        
    Returns:
        Updated proxy configuration
        
    Raises:
        HTTPException: If proxy not found or update fails
    """
    # Get existing proxy
    proxy = db.query(ProxyConfig).filter(ProxyConfig.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy with ID {proxy_id} not found",
        )
    
    # Update proxy
    try:
        # Filter out None values
        update_data = {
            k: v for k, v in proxy_update.model_dump().items() 
            if v is not None
        }
        
        # Apply updates
        for key, value in update_data.items():
            setattr(proxy, key, value)
        
        # Commit changes
        db.commit()
        db.refresh(proxy)
        return proxy
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


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(
    proxy_id: int = Path(..., description="ID of the proxy to delete"),
    db: Session = Depends(get_db),
):
    """
    Delete a proxy configuration.
    
    Args:
        proxy_id: ID of the proxy to delete
        db: Database session
        
    Returns:
        No content
        
    Raises:
        HTTPException: If proxy not found or deletion fails
    """
    # Get existing proxy
    proxy = db.query(ProxyConfig).filter(ProxyConfig.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy with ID {proxy_id} not found",
        )
    
    # Delete proxy
    try:
        db.delete(proxy)
        db.commit()
        return None
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/status", response_model=ProxyStatusResponse)
async def get_proxy_status(
    db: Session = Depends(get_db),
):
    """
    Get overall proxy status and statistics.
    
    Args:
        db: Database session
        
    Returns:
        Proxy status and statistics
    """
    # Get proxy counts
    total = db.query(func.count(ProxyConfig.id)).scalar() or 0
    active = db.query(func.count(ProxyConfig.id)).filter(ProxyConfig.is_active == True).scalar() or 0
    inactive = total - active
    
    # Calculate success rate
    total_requests = db.query(func.sum(ProxyConfig.success_count + ProxyConfig.failure_count)).scalar() or 0
    total_success = db.query(func.sum(ProxyConfig.success_count)).scalar() or 0
    success_rate = (total_success / total_requests) * 100 if total_requests > 0 else 0
    
    # Get banned proxies count
    banned_count = db.query(func.count(ProxyConfig.id)).filter(ProxyConfig.banned_sites.isnot(None)).scalar() or 0
    
    # Get proxies expiring soon (within 7 days)
    expiry_threshold = datetime.utcnow() + timedelta(days=7)
    expiring_soon = (
        db.query(func.count(ProxyConfig.id))
        .filter(
            ProxyConfig.expires_at.isnot(None),
            ProxyConfig.expires_at <= expiry_threshold,
            ProxyConfig.expires_at > datetime.utcnow(),
        )
        .scalar() or 0
    )
    
    return ProxyStatusResponse(
        total=total,
        active=active,
        inactive=inactive,
        success_rate=success_rate,
        banned_count=banned_count,
        expiring_soon=expiring_soon,
    )


@router.patch("/{proxy_id}/record-success", response_model=ProxyConfigResponse)
async def record_proxy_success(
    proxy_id: int = Path(..., description="ID of the proxy"),
    site: Optional[SiteEnum] = Query(None, description="Site where proxy was used"),
    db: Session = Depends(get_db),
):
    """
    Record a successful proxy use.
    
    Args:
        proxy_id: ID of the proxy
        site: Site where proxy was used
        db: Database session
        
    Returns:
        Updated proxy configuration
        
    Raises:
        HTTPException: If proxy not found or update fails
    """
    # Get existing proxy
    proxy = db.query(ProxyConfig).filter(ProxyConfig.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy with ID {proxy_id} not found",
        )
    
    # Update proxy
    try:
        # Increment success count
        proxy.success_count += 1
        
        # Update last used time
        proxy.last_used = datetime.utcnow()
        
        # Remove site from banned sites if it was banned
        if proxy.banned_sites and site:
            site_value = site.value
            if site_value in proxy.banned_sites:
                proxy.banned_sites.remove(site_value)
        
        # Commit changes
        db.commit()
        db.refresh(proxy)
        return proxy
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.patch("/{proxy_id}/record-failure", response_model=ProxyConfigResponse)
async def record_proxy_failure(
    proxy_id: int = Path(..., description="ID of the proxy"),
    site: Optional[SiteEnum] = Query(None, description="Site where proxy failed"),
    failure_reason: str = Body(..., description="Reason for failure"),
    deactivate: bool = Body(False, description="Whether to deactivate the proxy"),
    ban_from_site: bool = Body(False, description="Whether to ban the proxy from the site"),
    db: Session = Depends(get_db),
):
    """
    Record a failed proxy use.
    
    Args:
        proxy_id: ID of the proxy
        site: Site where proxy failed
        failure_reason: Reason for failure
        deactivate: Whether to deactivate the proxy
        ban_from_site: Whether to ban the proxy from the site
        db: Database session
        
    Returns:
        Updated proxy configuration
        
    Raises:
        HTTPException: If proxy not found or update fails
    """
    # Get existing proxy
    proxy = db.query(ProxyConfig).filter(ProxyConfig.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy with ID {proxy_id} not found",
        )
    
    # Update proxy
    try:
        # Increment failure count
        proxy.failure_count += 1
        
        # Update last failure time and reason
        proxy.last_failure = datetime.utcnow()
        proxy.failure_reason = failure_reason
        
        # Deactivate proxy if requested
        if deactivate:
            proxy.is_active = False
        
        # Ban proxy from site if requested
        if ban_from_site and site:
            site_value = site.value
            if proxy.banned_sites is None:
                proxy.banned_sites = [site_value]
            elif site_value not in proxy.banned_sites:
                proxy.banned_sites.append(site_value)
        
        # Commit changes
        db.commit()
        db.refresh(proxy)
        return proxy
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/next/{site}", response_model=ProxyConfigResponse)
async def get_next_proxy(
    site: SiteEnum = Path(..., description="Site to get proxy for"),
    db: Session = Depends(get_db),
):
    """
    Get the next available proxy for a site.
    
    This endpoint implements a simple proxy rotation strategy
    based on last use time, success rate, and banned status.
    
    Args:
        site: Site to get proxy for
        db: Database session
        
    Returns:
        Next available proxy
        
    Raises:
        HTTPException: If no proxy is available
    """
    # Check if site requires proxy
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if site_metadata and not site_metadata.requires_proxy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Site {site.value} does not require a proxy",
        )
    
    # Get next available proxy
    # Priority:
    # 1. Active
    # 2. Not banned for this site
    # 3. Not expired
    # 4. Has high success rate
    # 5. Not used recently
    
    site_value = site.value
    now = datetime.utcnow()
    
    # Build query
    query = (
        db.query(ProxyConfig)
        .filter(ProxyConfig.is_active == True)
        .filter(
            or_(
                ProxyConfig.banned_sites.is_(None),
                ~ProxyConfig.banned_sites.contains([site_value])
            )
        )
        .filter(
            or_(
                ProxyConfig.expires_at.is_(None),
                ProxyConfig.expires_at > now
            )
        )
    )
    
    # Calculate success rate for each proxy
    # We'll do this in Python since it's complex to do in SQL
    eligible_proxies = query.all()
    if not eligible_proxies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No proxy available for site {site.value}",
        )
    
    # Calculate score for each proxy
    # Higher score = better proxy
    proxy_scores = []
    for proxy in eligible_proxies:
        # Calculate success rate (0-100)
        total_requests = proxy.success_count + proxy.failure_count
        success_rate = (proxy.success_count / total_requests) * 100 if total_requests > 0 else 50  # Default to 50%
        
        # Calculate recency score (0-100)
        # 0 = used very recently, 100 = never used
        recency_score = 100
        if proxy.last_used:
            # Calculate hours since last used
            hours_since_used = (now - proxy.last_used).total_seconds() / 3600
            # Score decreases with recency, maxing out at 24 hours
            recency_score = min(100, hours_since_used * 4.17)  # 100/24 = 4.17
        
        # Calculate final score
        # Weight: 70% success rate, 30% recency
        final_score = (success_rate * 0.7) + (recency_score * 0.3)
        
        proxy_scores.append((proxy, final_score))
    
    # Sort by score descending
    proxy_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Return the proxy with the highest score
    return proxy_scores[0][0]


@router.get("/health-check", response_model=List[Dict[str, Any]])
async def check_proxy_health(
    limit: int = Query(10, ge=1, le=100, description="Number of proxies to check"),
    db: Session = Depends(get_db),
):
    """
    Get proxies that should be health checked.
    
    This endpoint returns a list of proxies that haven't been used recently
    and should be checked for health.
    
    Args:
        limit: Number of proxies to check
        db: Database session
        
    Returns:
        List of proxies to check
    """
    # Get active proxies that haven't been used in a while
    # or have had recent failures
    threshold_time = datetime.utcnow() - timedelta(hours=6)
    
    proxies_to_check = (
        db.query(ProxyConfig)
        .filter(ProxyConfig.is_active == True)
        .filter(
            or_(
                ProxyConfig.last_used.is_(None),
                ProxyConfig.last_used < threshold_time,
                and_(
                    ProxyConfig.last_failure.isnot(None),
                    ProxyConfig.last_failure > ProxyConfig.last_used
                )
            )
        )
        .order_by(
            # Prioritize proxies that have never been used
            ProxyConfig.last_used.asc().nullsfirst(),
            # Then prioritize proxies with recent failures
            ProxyConfig.last_failure.desc().nullslast()
        )
        .limit(limit)
        .all()
    )
    
    # Convert to response format
    result = []
    for proxy in proxies_to_check:
        proxy_data = {
            "id": proxy.id,
            "ip_address": proxy.ip_address,
            "port": proxy.port,
            "protocol": proxy.protocol,
            "username": proxy.username,
            "password": proxy.password,  # This would be masked in the actual response
            "last_used": proxy.last_used,
            "last_failure": proxy.last_failure,
            "failure_reason": proxy.failure_reason,
            "check_priority": "high" if proxy.last_failure and (proxy.last_used is None or proxy.last_failure > proxy.last_used) else "normal",
        }
        result.append(proxy_data)
    
    return result


@router.post("/batch", response_model=List[ProxyConfigResponse], status_code=status.HTTP_201_CREATED)
async def create_proxies_batch(
    proxies: List[ProxyConfigCreate],
    db: Session = Depends(get_db),
):
    """
    Create multiple proxy configurations in a batch.
    
    Args:
        proxies: List of proxy configurations
        db: Database session
        
    Returns:
        List of created proxy configurations
        
    Raises:
        HTTPException: If any proxy already exists or creation fails
    """
    created_proxies = []
    
    # Start transaction
    try:
        for proxy in proxies:
            # Check if proxy already exists
            existing = (
                db.query(ProxyConfig)
                .filter(
                    ProxyConfig.ip_address == proxy.ip_address,
                    ProxyConfig.port == proxy.port,
                    ProxyConfig.protocol == proxy.protocol,
                )
                .first()
            )
            
            if existing:
                # Skip existing proxy
                continue
            
            # Create proxy
            db_proxy = ProxyConfig(**proxy.model_dump())
            db.add(db_proxy)
            created_proxies.append(db_proxy)
        
        # Commit transaction
        db.commit()
        
        # Refresh objects to get their IDs
        for proxy in created_proxies:
            db.refresh(proxy)
        
        return created_proxies
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

