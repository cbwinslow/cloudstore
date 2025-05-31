#!/usr/bin/env python3
"""
Proxy Configuration Initialization Script for CloudStore.

This script initializes the database with site metadata and test proxy configurations.
It can also validate the health of proxies before adding them to the database.

Usage:
    python -m cloudstore.scripts.init_proxy_config [--check-proxy-health]
"""

import os
import sys
import time
import logging
import argparse
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from cloudstore.database.config import SessionLocal, engine
from cloudstore.database.models import SiteEnum, SiteMetadata, ProxyConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def initialize_site_metadata(db: Session) -> None:
    """
    Initialize site metadata for all target sites.
    
    Args:
        db: Database session
    """
    logger.info("Initializing site metadata...")
    
    # Define site metadata
    sites_data = [
        {
            "site": SiteEnum.EBAY,
            "base_url": "https://www.ebay.com",
            "search_url_template": "https://www.ebay.com/sch/i.html?_nkw={query}",
            "crawl_frequency_minutes": int(os.getenv("EBAY_CRAWL_FREQUENCY_MINUTES", "720")),  # 12 hours
            "rate_limit_requests": int(os.getenv("EBAY_RATE_LIMIT", "10")),
            "rate_limit_period_seconds": 60,
            "requires_proxy": os.getenv("EBAY_REQUIRES_PROXY", "true").lower() == "true",
            "requires_login": False,
            "crawl_settings": {
                "user_agent_rotation": True,
                "max_pages": 20,
                "items_per_page": 50,
                "proxy_rotation_interval": int(os.getenv("EBAY_PROXY_ROTATION_INTERVAL", "5")),
            },
        },
        {
            "site": SiteEnum.AMAZON,
            "base_url": "https://www.amazon.com",
            "search_url_template": "https://www.amazon.com/s?k={query}",
            "crawl_frequency_minutes": int(os.getenv("AMAZON_CRAWL_FREQUENCY_MINUTES", "1440")),  # 24 hours
            "rate_limit_requests": int(os.getenv("AMAZON_RATE_LIMIT", "5")),
            "rate_limit_period_seconds": 60,
            "requires_proxy": os.getenv("AMAZON_REQUIRES_PROXY", "true").lower() == "true",
            "requires_login": False,
            "crawl_settings": {
                "user_agent_rotation": True,
                "max_pages": 10,
                "items_per_page": 48,
                "proxy_rotation_interval": int(os.getenv("AMAZON_PROXY_ROTATION_INTERVAL", "1")),
            },
        },
        {
            "site": SiteEnum.SHOPGOODWILL,
            "base_url": "https://shopgoodwill.com",
            "search_url_template": "https://shopgoodwill.com/categories?st={query}",
            "crawl_frequency_minutes": int(os.getenv("SHOPGOODWILL_CRAWL_FREQUENCY_MINUTES", "360")),  # 6 hours
            "rate_limit_requests": int(os.getenv("SHOPGOODWILL_RATE_LIMIT", "20")),
            "rate_limit_period_seconds": 60,
            "requires_proxy": os.getenv("SHOPGOODWILL_REQUIRES_PROXY", "false").lower() == "true",
            "requires_login": False,
            "crawl_settings": {
                "user_agent_rotation": False,
                "max_pages": 30,
                "items_per_page": 40,
                "proxy_rotation_interval": int(os.getenv("SHOPGOODWILL_PROXY_ROTATION_INTERVAL", "20")),
            },
        },
        {
            "site": SiteEnum.PUBLICSURPLUS,
            "base_url": "https://www.publicsurplus.com",
            "search_url_template": "https://www.publicsurplus.com/sms/browse/search?query={query}",
            "crawl_frequency_minutes": int(os.getenv("PUBLICSURPLUS_CRAWL_FREQUENCY_MINUTES", "1440")),  # 24 hours
            "rate_limit_requests": int(os.getenv("PUBLICSURPLUS_RATE_LIMIT", "30")),
            "rate_limit_period_seconds": 60,
            "requires_proxy": os.getenv("PUBLICSURPLUS_REQUIRES_PROXY", "false").lower() == "true",
            "requires_login": False,
            "crawl_settings": {
                "user_agent_rotation": False,
                "max_pages": 50,
                "items_per_page": 25,
                "proxy_rotation_interval": int(os.getenv("PUBLICSURPLUS_PROXY_ROTATION_INTERVAL", "30")),
            },
        },
    ]
    
    # Check for existing sites and update or create as needed
    for site_data in sites_data:
        site_enum = site_data["site"]
        existing = db.query(SiteMetadata).filter(SiteMetadata.site == site_enum).first()
        
        if existing:
            logger.info(f"Updating existing site metadata for {site_enum.value}")
            for key, value in site_data.items():
                if key != "site":  # Don't change the primary key
                    setattr(existing, key, value)
        else:
            logger.info(f"Creating new site metadata for {site_enum.value}")
            db.add(SiteMetadata(**site_data))
    
    db.commit()
    logger.info("Site metadata initialization complete")


def check_proxy_health(
    ip_address: str,
    port: int,
    protocol: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Check if a proxy is working properly.
    
    Args:
        ip_address: Proxy IP address
        port: Proxy port
        protocol: Proxy protocol (http, https, socks5)
        username: Optional proxy username
        password: Optional proxy password
        timeout: Request timeout in seconds
        
    Returns:
        Dict with health check results
    """
    proxy_url = f"{protocol}://"
    if username and password:
        proxy_url += f"{username}:{password}@"
    proxy_url += f"{ip_address}:{port}"
    
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }
    
    test_urls = [
        "https://httpbin.org/ip",
        "https://api.ipify.org/?format=json",
        "https://ifconfig.me/all.json"
    ]
    
    start_time = time.time()
    result = {
        "is_working": False,
        "response_time": None,
        "error": None,
        "ip_detected": None,
        "country": None,
    }
    
    for url in test_urls:
        try:
            logger.info(f"Testing proxy {ip_address}:{port} with {url}")
            response = requests.get(
                url,
                proxies=proxies,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            )
            
            if response.status_code == 200:
                result["is_working"] = True
                result["response_time"] = time.time() - start_time
                
                # Parse IP information from response
                ip_data = response.json()
                if "ip" in ip_data:
                    result["ip_detected"] = ip_data["ip"]
                elif "origin" in ip_data:
                    result["ip_detected"] = ip_data["origin"]
                
                # If successful, no need to try other URLs
                break
                
        except requests.RequestException as e:
            result["error"] = str(e)
    
    if not result["is_working"]:
        logger.warning(f"Proxy {ip_address}:{port} health check failed: {result['error']}")
    else:
        logger.info(f"Proxy {ip_address}:{port} is working, response time: {result['response_time']:.2f}s")
    
    return result


def setup_test_proxies(db: Session, check_health: bool = False) -> None:
    """
    Set up test proxy configurations.
    
    Args:
        db: Database session
        check_health: Whether to check proxy health before adding
    """
    logger.info("Setting up test proxy configurations...")
    
    # Define test proxies
    # In a real environment, these would be loaded from a service or configuration
    test_proxies = [
        # Public test proxies - these likely won't work in production
        {
            "ip_address": "51.158.68.133",
            "port": 8811,
            "protocol": "http",
            "country": "FR",
            "provider": "public",
            "is_active": True,
        },
        {
            "ip_address": "176.9.75.42",
            "port": 3128,
            "protocol": "http",
            "country": "DE",
            "provider": "public",
            "is_active": True,
        },
        {
            "ip_address": "46.101.13.77",
            "port": 80,
            "protocol": "http",
            "country": "GB",
            "provider": "public",
            "is_active": True,
        },
        {
            "ip_address": "104.248.15.144",
            "port": 3128,
            "protocol": "http",
            "country": "US",
            "provider": "public",
            "is_active": True,
        },
        # Example authenticated proxies (with fictional credentials)
        {
            "ip_address": "proxy.example.com",
            "port": 8080,
            "protocol": "https",
            "username": "test_user",
            "password": "test_pass",
            "country": "US",
            "provider": "example",
            "is_active": True,
            "expires_at": datetime.now() + timedelta(days=30),
        },
    ]
    
    # Add provider-specific proxies if configuration exists
    provider = os.getenv("PROXY_PROVIDER", "").lower()
    if provider and provider != "public":
        api_key = os.getenv("PROXY_API_KEY", "")
        if api_key:
            logger.info(f"Adding proxies from provider: {provider}")
            # In a real implementation, you would fetch proxies from the provider's API
            # For example: provider_proxies = fetch_proxies_from_provider(provider, api_key)
            # test_proxies.extend(provider_proxies)
    
    added_count = 0
    skipped_count = 0
    failed_count = 0
    
    for proxy_data in test_proxies:
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
            logger.info(f"Proxy {proxy_data['ip_address']}:{proxy_data['port']} already exists, skipping")
            skipped_count += 1
            continue
        
        # Check proxy health if requested
        if check_health:
            health_result = check_proxy_health(
                proxy_data["ip_address"],
                proxy_data["port"],
                proxy_data["protocol"],
                proxy_data.get("username"),
                proxy_data.get("password"),
                timeout=int(os.getenv("PROXY_HEALTH_CHECK_TIMEOUT", "10"))
            )
            
            if not health_result["is_working"]:
                logger.warning(f"Skipping unhealthy proxy {proxy_data['ip_address']}:{proxy_data['port']}")
                failed_count += 1
                continue
            
            # Add health check results to proxy data
            proxy_data["last_used"] = datetime.now()
            proxy_data["success_count"] = 1
        
        # Add proxy to database
        try:
            db.add(ProxyConfig(**proxy_data))
            db.commit()
            logger.info(f"Added proxy {proxy_data['ip_address']}:{proxy_data['port']}")
            added_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add proxy {proxy_data['ip_address']}:{proxy_data['port']}: {e}")
            failed_count += 1
    
    logger.info(f"Proxy setup complete. Added: {added_count}, Skipped: {skipped_count}, Failed: {failed_count}")


def main():
    """Main function to initialize proxy configuration."""
    parser = argparse.ArgumentParser(description="Initialize proxy configuration for CloudStore")
    parser.add_argument("--check-proxy-health", action="store_true", help="Check proxy health before adding")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Create database session
    db = SessionLocal()
    try:
        # Initialize site metadata
        initialize_site_metadata(db)
        
        # Setup test proxies
        setup_test_proxies(db, check_health=args.check_proxy_health)
        
        logger.info("Proxy configuration initialization complete")
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

