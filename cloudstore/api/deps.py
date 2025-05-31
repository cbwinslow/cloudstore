"""
Dependencies for API routes.

This module provides dependencies for the API routes, including
database session management and authentication.
"""

from typing import Generator, Optional
import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cloudstore.core.config import settings
from cloudstore.database.config import Base

# Configure logging
logger = logging.getLogger(__name__)

# Create database engine
try:
    engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.SQL_ECHO
    )
    # Create sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.
    
    Yields:
        Database session
        
    Raises:
        HTTPException: If database connection fails
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
    finally:
        db.close()


# Additional dependencies can be added here, such as:
# - Authentication dependencies
# - Permission checking
# - Rate limiting
# - Caching

