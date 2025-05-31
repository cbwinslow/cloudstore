#!/usr/bin/env python3
"""
Database Initialization Script.

This script initializes the database with default site metadata and proxy configurations.
It is designed to be idempotent, meaning it can be run multiple times without creating duplicates.

Usage:
    python -m cloudstore.scripts.init_db_config

Environment Variables:
    DB_USER: Database username
    DB_PASSWORD: Database password
    DB_HOST: Database host
    DB_PORT: Database port
    DB_NAME: Database name
    PROXY_USERNAME: Default username for proxies (optional)
    PROXY_PASSWORD: Default password for proxies (optional)
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import requests

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from cloudstore.database.config import SessionLocal, engine, Base
from cloudstore.database.models import SiteMetadata, SiteEnum, ProxyConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("db_init.log")
    ]
)
logger = logging.getLogger("db_init")


def create_site_metadata(db: Session, site_data: Dict[str, Any]) -> Optional[SiteMetadata]:
    """
    Create site metadata if it doesn't exist.
    
    Args:
        db: Database session
        site_data: Site metadata
        
    Returns:
        Created site metadata or None if it already exists
    """
    site = site_data.pop("site")
    
    # Check if site already exists
    existing = db.query(SiteMetadata).filter(SiteMetadata.site == site).first()
    if existing:
        logger.info(f"Site metadata for {site.value} already exists, skipping.")
        return None
    
    try:
        logger.info(f"Creating site metadata for {site.value}")
        db_site = SiteMetadata(site=site, **site_data)
        db.add(db_site)
        db.commit()
        db.refresh(db_site)
        logger.info(f"Successfully created site metadata for {site.value}")
        return db_site
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        return None


def create_proxy(db: Session, proxy_data: Dict[str, Any]) -> Optional[ProxyConfig]:
    """
    Create proxy configuration if it doesn't exist.
    
    Args:
        db: Database session
        proxy_data: Proxy configuration
        
    Returns:
        Created proxy configuration or None if it already exists
    """
    # Check if proxy already exists
    existing = (
        db.query(ProxyConfig)
        .filter(
            ProxyConfig.ip_address == proxy_data["ip_address"],
            ProxyConfig.port == proxy_data["port"],
            ProxyConfig.protocol == proxy_data["protocol"],
        )
        .first()
    )
    
    if existing:
        logger.info(f"Proxy {proxy_data['ip_address']}:{proxy_data['port']} already exists, skipping.")
        return None
    
    try:
        logger.info(f"Creating proxy {proxy_data['ip_address']}:{proxy_data['port']}")
        db_proxy = ProxyConfig(**proxy_data)
        db.add(db_proxy)
        db.commit()
        db.refresh(db_proxy)
        logger.info(f"Successfully created proxy {proxy_data['ip_address']}:{proxy_data['port']}")
        return db_proxy
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        return None


def check_proxy_health(proxy_data: Dict[str, Any]) -> bool:
    """
    Check proxy health by making a test request.
    
    Args:
        proxy_data: Proxy configuration
        
    Returns:
        True if proxy is healthy, False otherwise
    """
    test_url = "https://httpbin.org/ip"
    proxy_url = f"{proxy_data['protocol']}://"
    
    # Add authentication if provided
    if proxy_data.get("username") and proxy_data.get("password"):
        proxy_url += f"{proxy_data['username']}:{proxy_data['password']}@"
    
    proxy_url += f"{proxy_data['ip_address']}:{proxy_data['port']}"
    
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }
    
    try:
        logger.info(f"Testing proxy {proxy_data['ip_address']}:{proxy_data['port']}")
        response = requests.get(test_url, proxies=proxies, timeout=10)
        if response.status_code == 200:
            logger.info(f"Proxy {proxy_data['ip_address']}:{proxy_data['port']} is healthy")
            return True
        else:
            logger.warning(f"Proxy {proxy_data['ip_address']}:{proxy_data['port']} returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"Error testing proxy {proxy_data['ip_address']}:{proxy_data['port']}: {str(e)}")
        return False


def get_default_site_metadata() -> List[Dict[str, Any]]:
    """
    Get default site metadata for all supported sites.
    
    Returns:
        List of site metadata dictionaries
    """
    return [
        # eBay
        {
            "site": SiteEnum.EBAY,
            "base_url": "https://www.ebay.com",
            "search_url_template": "https://www.ebay.com/sch/i.html?_nkw={query}",
            "crawl_frequency_minutes": 120,  # 2 hours
            "rate_limit_requests": 5,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": False,
            "crawl_settings": {
                "max_pages": 5,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "cookies_required": True,
                "js_rendering_required": False,
            }
        },
        # Amazon
        {
            "site": SiteEnum.AMAZON,
            "base_url": "https://www.amazon.com",
            "search_url_template": "https://www.amazon.com/s?k={query}",
            "crawl_frequency_minutes": 240,  # 4 hours
            "rate_limit_requests": 2,
            "rate_limit_period_seconds": 60,
            "requires_proxy": True,
            "requires_login": True,
            "login_details": {
                "username": os.getenv("AMAZON_USERNAME", ""),
                "password": os.getenv("AMAZON_PASSWORD", ""),
            },
            "crawl_settings": {
                "max_pages": 3,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "cookies_required": True,
                "js_rendering_required": True,
                "anti_bot_bypass_required": True,
            }
        },
        # ShopGoodwill
        {
            "site": SiteEnum.SHOPGOODWILL,
            "base_url": "https://shopgoodwill.com",
            "search_url_template": "https://shopgoodwill.com/categories?st={query}",
            "crawl_frequency_minutes": 60,  # 1 hour
            "rate_limit_requests": 10,
            "rate_limit_period_seconds": 60,
            "requires_proxy": False,
            "requires_login": False,
            "crawl_settings": {
                "max_pages": 10,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "cookies_required": False,
                "js_rendering_required": False,
            }
        },
        # PublicSurplus
        {
            "site": SiteEnum.PUBLICSURPLUS,
            "base_url": "https://www.publicsurplus.com",
            "search_url_template": "https://www.publicsurplus.com/sms/browse/search?query={query}",
            "crawl_frequency_minutes": 360,  # 6 hours
            "rate_limit_requests": 15,
            "rate_limit_period_seconds": 60,
            "requires_proxy": False,
            "requires_login": False,
            "crawl_settings": {
                "max_pages": 15,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "cookies_required": False,
                "js_rendering_required": False,
            }
        },
    ]


def get_default_proxy_configs() -> List[Dict[str, Any]]:
    """
    Get default proxy configurations.
    
    Returns:
        List of proxy configuration dictionaries
    """
    # Get proxy credentials from environment variables
    proxy_username = os.getenv("PROXY_USERNAME")
    proxy_password = os.getenv("PROXY_PASSWORD", "Temp1234!")
    
    # Default expiration is 30 days from now
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    return [
        # Example proxies - replace these with real proxies in production
        {
            "ip_address": "23.94.180.33",
            "port": 3128,
            "protocol": "http",
            "username": proxy_username,
            "password": proxy_password,
            "provider": "ipburger",
            "country": "US",
            "is_active": True,
            "expires_at": expires_at,
        },
        {
            "ip_address": "35.234.66.55",
            "port": 8080,
            "protocol": "http",
            "username": proxy_username,
            "password": proxy_password,
            "provider": "ipburger",
            "country": "US",
            "is_active": True,
            "expires_at": expires_at,
        },
        {
            "ip_address": "45.79.110.131",
            "port": 3128,
            "protocol": "http",
            "username": proxy_username,
            "password": proxy_password,
            "provider": "ipburger",
            "country": "US",
            "is_active": True,
            "expires_at": expires_at,
        },
        {
            "ip_address": "64.227.107.195",
            "port": 8080,
            "protocol": "http",
            "username": proxy_username,
            "password": proxy_password,
            "provider": "ipburger",
            "country": "US",
            "is_active": True,
            "expires_at": expires_at,
        },
        {
            "ip_address": "206.189.118.101",
            "port": 8080,
            "protocol": "http",
            "username": proxy_username,
            "password": proxy_password,
            "provider": "ipburger",
            "country": "US",
            "is_active": True,
            "expires_at": expires_at,
        },
    ]


def init_db(validate_proxies: bool = False) -> None:
    """
    Initialize the database with default data.
    
    Args:
        validate_proxies: Whether to validate proxies before adding them
    """
    db = SessionLocal()
    try:
        # Create site metadata
        site_metadata_configs = get_default_site_metadata()
        sites_created = 0
        
        logger.info(f"Initializing site metadata for {len(site_metadata_configs)} sites")
        for site_data in site_metadata_configs:
            result = create_site_metadata(db, site_data)
            if result:
                sites_created += 1
        
        logger.info(f"Created {sites_created} site metadata entries")
        
        # Create proxy configurations
        proxy_configs = get_default_proxy_configs()
        proxies_created = 0
        
        logger.info(f"Initializing {len(proxy_configs)} proxy configurations")
        for proxy_data in proxy_configs:
            # Check proxy health if validation is enabled
            if validate_proxies:
                if not check_proxy_health(proxy_data):
                    logger.warning(f"Skipping unhealthy proxy {proxy_data['ip_address']}:{proxy_data['port']}")
                    continue
            
            result = create_proxy(db, proxy_data)
            if result:
                proxies_created += 1
        
        logger.info(f"Created {proxies_created} proxy configurations")
        
    finally:
        db.close()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Initialize database with default configuration")
    parser.add_argument("--validate-proxies", action="store_true", help="Validate proxies before adding them")
    parser.add_argument("--reset", action="store_true", help="Reset database tables before initialization")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.reset:
        logger.warning("Resetting database tables")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    
    logger.info("Starting database initialization")
    init_db(validate_proxies=args.validate_proxies)
    logger.info("Database initialization completed")

