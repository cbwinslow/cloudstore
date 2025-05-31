"""
Database initialization script.

This script creates the database, initializes the schema,
and adds initial data for site metadata.
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from cloudstore.database.config import async_engine, Base, AsyncSessionLocal
from cloudstore.database.models import SiteMetadata, SiteEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all database tables."""
    async with async_engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")


async def add_initial_data(session: AsyncSession):
    """Add initial data to the database."""
    # Add site metadata
    logger.info("Adding initial site metadata...")
    
    # Check if site metadata already exists
    result = await session.execute(select(SiteMetadata))
    if result.scalars().first() is not None:
        logger.info("Site metadata already exists. Skipping initialization.")
        return

    # Create site metadata for each supported site
    site_data = [
        {
            "site": SiteEnum.EBAY,
            "base_url": "https://www.ebay.com",
            "search_url_template": "https://www.ebay.com/sch/i.html?_nkw={keyword}",
            "crawl_frequency_minutes": 240,  # 4 hours
            "rate_limit_requests": 10,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": False,
        },
        {
            "site": SiteEnum.AMAZON,
            "base_url": "https://www.amazon.com",
            "search_url_template": "https://www.amazon.com/s?k={keyword}",
            "crawl_frequency_minutes": 360,  # 6 hours
            "rate_limit_requests": 5,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": False,
        },
        {
            "site": SiteEnum.SHOPGOODWILL,
            "base_url": "https://shopgoodwill.com",
            "search_url_template": "https://shopgoodwill.com/search?query={keyword}",
            "crawl_frequency_minutes": 180,  # 3 hours
            "rate_limit_requests": 15,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": False,
        },
        {
            "site": SiteEnum.PUBLICSURPLUS,
            "base_url": "https://www.publicsurplus.com",
            "search_url_template": "https://www.publicsurplus.com/sms/browse/search?query={keyword}",
            "crawl_frequency_minutes": 480,  # 8 hours
            "rate_limit_requests": 20,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": False,
        }
    ]

    # Add site metadata to the database
    for data in site_data:
        site_metadata = SiteMetadata(**data)
        session.add(site_metadata)
    
    await session.commit()
    logger.info("Initial site metadata added successfully.")


async def init_db():
    """Initialize the database with tables and initial data."""
    try:
        # Create tables
        await create_tables()
        
        # Add initial data
        async with AsyncSessionLocal() as session:
            await add_initial_data(session)
            
        logger.info("Database initialization completed successfully.")
    except SQLAlchemyError as e:
        logger.error(f"Error initializing database: {e}")
        raise


def main():
    """Run the database initialization."""
    asyncio.run(init_db())


if __name__ == "__main__":
    main()

