"""
API routes for site metadata management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import desc, and_, or_, func

from cloudstore.database.models import SiteMetadata, SiteEnum
from cloudstore.schemas.site import (
    SiteMetadataCreate,
    SiteMetadataUpdate,
    SiteMetadataResponse,
)
from cloudstore.api.deps import get_db

# Create router
router = APIRouter(
    prefix="/sites",
    tags=["sites"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Site not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@router.get("/metadata", response_model=List[SiteMetadataResponse])
async def list_sites(
    db: Session = Depends(get_db),
):
    """
    List all configured sites and their metadata.
    
    Args:
        db: Database session
        
    Returns:
        List of site metadata
    """
    sites = db.query(SiteMetadata).all()
    return sites


@router.get("/metadata/{site}", response_model=SiteMetadataResponse)
async def get_site_metadata(
    site: SiteEnum = Path(..., description="Site enum value"),
    db: Session = Depends(get_db),
):
    """
    Get metadata for a specific site.
    
    Args:
        site: Site enum value
        db: Database session
        
    Returns:
        Site metadata
        
    Raises:
        HTTPException: If site not found
    """
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    return site_metadata


@router.post("/metadata", response_model=SiteMetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_site_metadata(
    site_data: SiteMetadataCreate,
    db: Session = Depends(get_db),
):
    """
    Create metadata for a site.
    
    Args:
        site_data: Site metadata
        db: Database session
        
    Returns:
        Created site metadata
        
    Raises:
        HTTPException: If site already exists or creation fails
    """
    # Check if site already exists
    existing = db.query(SiteMetadata).filter(SiteMetadata.site == site_data.site).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Metadata for site {site_data.site.value} already exists",
        )
    
    # Create site metadata
    try:
        # Ensure any sensitive data is properly handled
        if site_data.login_details and "password" in site_data.login_details:
            # In a production system, you'd encrypt the password here
            # For demonstration, we're just acknowledging it
            pass
            
        db_site = SiteMetadata(**site_data.model_dump())
        db.add(db_site)
        db.commit()
        db.refresh(db_site)
        return db_site
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


@router.put("/metadata/{site}", response_model=SiteMetadataResponse)
async def update_site_metadata(
    site_update: SiteMetadataUpdate,
    site: SiteEnum = Path(..., description="Site enum value"),
    db: Session = Depends(get_db),
):
    """
    Update metadata for a site.
    
    Args:
        site_update: Updated site metadata
        site: Site enum value
        db: Database session
        
    Returns:
        Updated site metadata
        
    Raises:
        HTTPException: If site not found or update fails
    """
    # Get existing site metadata
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    # Update site metadata
    try:
        # Filter out None values
        update_data = {
            k: v for k, v in site_update.model_dump().items() 
            if v is not None
        }
        
        # Handle sensitive data
        if "login_details" in update_data and update_data["login_details"] and "password" in update_data["login_details"]:
            # In a production system, you'd encrypt the password here
            # For demonstration, we're just acknowledging it
            pass
            
        # Apply updates
        for key, value in update_data.items():
            setattr(site_metadata, key, value)
        
        # Commit changes
        db.commit()
        db.refresh(site_metadata)
        return site_metadata
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.patch("/metadata/{site}/crawl-settings", response_model=SiteMetadataResponse)
async def update_crawl_settings(
    site: SiteEnum = Path(..., description="Site enum value"),
    crawl_frequency_minutes: Optional[int] = Body(None, description="Crawl frequency in minutes", ge=1),
    rate_limit_requests: Optional[int] = Body(None, description="Number of requests allowed in the rate limit period", ge=1),
    rate_limit_period_seconds: Optional[int] = Body(None, description="Rate limit period in seconds", ge=1),
    requires_proxy: Optional[bool] = Body(None, description="Whether the site requires a proxy"),
    crawl_settings: Optional[Dict[str, Any]] = Body(None, description="Additional crawl settings"),
    db: Session = Depends(get_db),
):
    """
    Update crawl settings for a site.
    
    Args:
        site: Site enum value
        crawl_frequency_minutes: Crawl frequency in minutes
        rate_limit_requests: Number of requests allowed in the rate limit period
        rate_limit_period_seconds: Rate limit period in seconds
        requires_proxy: Whether the site requires a proxy
        crawl_settings: Additional crawl settings
        db: Database session
        
    Returns:
        Updated site metadata
        
    Raises:
        HTTPException: If site not found or update fails
    """
    # Get existing site metadata
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    # Update crawl settings
    try:
        if crawl_frequency_minutes is not None:
            site_metadata.crawl_frequency_minutes = crawl_frequency_minutes
        if rate_limit_requests is not None:
            site_metadata.rate_limit_requests = rate_limit_requests
        if rate_limit_period_seconds is not None:
            site_metadata.rate_limit_period_seconds = rate_limit_period_seconds
        if requires_proxy is not None:
            site_metadata.requires_proxy = requires_proxy
        if crawl_settings is not None:
            # Merge with existing crawl settings instead of replacing
            if site_metadata.crawl_settings:
                site_metadata.crawl_settings = {**site_metadata.crawl_settings, **crawl_settings}
            else:
                site_metadata.crawl_settings = crawl_settings
        
        # Commit changes
        db.commit()
        db.refresh(site_metadata)
        return site_metadata
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.patch("/metadata/{site}/login-details", response_model=SiteMetadataResponse)
async def update_login_details(
    site: SiteEnum = Path(..., description="Site enum value"),
    username: Optional[str] = Body(None, description="Login username"),
    password: Optional[str] = Body(None, description="Login password"),
    additional_details: Optional[Dict[str, Any]] = Body(None, description="Additional login details"),
    db: Session = Depends(get_db),
):
    """
    Update login details for a site.
    
    Args:
        site: Site enum value
        username: Login username
        password: Login password
        additional_details: Additional login details
        db: Database session
        
    Returns:
        Updated site metadata
        
    Raises:
        HTTPException: If site not found or update fails
    """
    # Get existing site metadata
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    # Update login details
    try:
        # Initialize login details if not exists
        if site_metadata.login_details is None:
            site_metadata.login_details = {}
        
        # Update fields
        if username is not None:
            site_metadata.login_details["username"] = username
        if password is not None:
            # In a production system, you'd encrypt the password here
            site_metadata.login_details["password"] = password
        if additional_details is not None:
            site_metadata.login_details = {**site_metadata.login_details, **additional_details}
        
        # Set requires_login to True if login details are provided
        if username or password:
            site_metadata.requires_login = True
        
        # Commit changes
        db.commit()
        db.refresh(site_metadata)
        return site_metadata
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.patch("/metadata/{site}/record-crawl", response_model=SiteMetadataResponse)
async def record_crawl(
    site: SiteEnum = Path(..., description="Site enum value"),
    db: Session = Depends(get_db),
):
    """
    Record a crawl for a site, updating the last crawl time.
    
    Args:
        site: Site enum value
        db: Database session
        
    Returns:
        Updated site metadata
        
    Raises:
        HTTPException: If site not found or update fails
    """
    # Get existing site metadata
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    # Record crawl
    try:
        # Update last crawl time
        site_metadata.last_crawl_time = datetime.utcnow()
        
        # Commit changes
        db.commit()
        db.refresh(site_metadata)
        return site_metadata
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/metadata/{site}/next-crawl", response_model=Dict[str, Any])
async def get_next_crawl_time(
    site: SiteEnum = Path(..., description="Site enum value"),
    db: Session = Depends(get_db),
):
    """
    Get the next scheduled crawl time for a site.
    
    Args:
        site: Site enum value
        db: Database session
        
    Returns:
        Next crawl time information
        
    Raises:
        HTTPException: If site not found
    """
    # Get existing site metadata
    site_metadata = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if not site_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for site {site.value} not found",
        )
    
    # Calculate next crawl time
    now = datetime.utcnow()
    
    if site_metadata.last_crawl_time is None:
        # If never crawled, next crawl is now
        next_crawl = now
        time_until_next_crawl = 0
    else:
        # Calculate next crawl based on frequency
        next_crawl = site_metadata.last_crawl_time + \
            datetime.timedelta(minutes=site_metadata.crawl_frequency_minutes)
        
        # Calculate time until next crawl
        if next_crawl > now:
            time_until_next_crawl = (next_crawl - now).total_seconds() / 60  # in minutes
        else:
            time_until_next_crawl = 0
    
    return {
        "site": site.value,
        "last_crawl_time": site_metadata.last_crawl_time,
        "next_crawl_time": next_crawl,
        "minutes_until_next_crawl": time_until_next_crawl,
        "crawl_frequency_minutes": site_metadata.crawl_frequency_minutes,
    }


@router.get("/due-for-crawl", response_model=List[SiteMetadataResponse])
async def get_sites_due_for_crawl(
    db: Session = Depends(get_db),
):
    """
    Get all sites that are due for crawling.
    
    Args:
        db: Database session
        
    Returns:
        List of sites due for crawling
    """
    now = datetime.utcnow()
    
    # Get sites where:
    # 1. Never crawled (last_crawl_time is NULL) OR
    # 2. Last crawl time + frequency < now
    due_sites = (
        db.query(SiteMetadata)
        .filter(
            or_(
                SiteMetadata.last_crawl_time.is_(None),
                and_(
                    SiteMetadata.last_crawl_time.isnot(None),
                    # Add crawl_frequency_minutes to last_crawl_time
                    func.date_add(
                        SiteMetadata.last_crawl_time,
                        func.interval(SiteMetadata.crawl_frequency_minutes, "MINUTE")
                    ) < now
                )
            )
        )
        .all()
    )
    
    return due_sites

