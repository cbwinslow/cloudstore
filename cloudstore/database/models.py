"""
Database models for CloudStore.

This module defines the database schema using SQLAlchemy ORM.
"""

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Table, Enum, Text, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from cloudstore.database.config import Base


class SiteEnum(enum.Enum):
    """Enum for supported e-commerce sites."""
    EBAY = "ebay"
    AMAZON = "amazon"
    SHOPGOODWILL = "shopgoodwill"
    PUBLICSURPLUS = "publicsurplus"


class ConditionEnum(enum.Enum):
    """Enum for product condition."""
    NEW = "new"
    LIKE_NEW = "like_new"
    VERY_GOOD = "very_good"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    FOR_PARTS = "for_parts"
    UNKNOWN = "unknown"


class Product(Base):
    """
    Product model for storing item details from various sites.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String(50), nullable=False, index=True)  # Original ID from the site
    site = Column(Enum(SiteEnum), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True)
    condition = Column(Enum(ConditionEnum), nullable=True, index=True)
    brand = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True)
    url = Column(String(1000), nullable=False)
    image_urls = Column(JSON, nullable=True)  # Array of image URLs
    product_metadata = Column(JSON, nullable=True)  # Additional site-specific metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    arbitrage_opportunities_source = relationship(
        "ArbitrageOpportunity", 
        foreign_keys="ArbitrageOpportunity.source_product_id",
        back_populates="source_product"
    )
    arbitrage_opportunities_target = relationship(
        "ArbitrageOpportunity", 
        foreign_keys="ArbitrageOpportunity.target_product_id",
        back_populates="target_product"
    )

    # Indexes
    __table_args__ = (
        Index("idx_products_site_site_id", "site", "site_id", unique=True),
        Index("idx_products_title_search", "title"),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, site={self.site}, title={self.title})>"


class PriceHistory(Base):
    """
    Model for tracking product price history.
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    shipping_cost = Column(Float, nullable=True)
    total_price = Column(Float, nullable=False)  # price + shipping_cost
    currency = Column(String(3), nullable=False, default="USD")
    is_sale_price = Column(Boolean, default=False)
    regular_price = Column(Float, nullable=True)  # Original price if on sale
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    product = relationship("Product", back_populates="price_history")

    # Indexes
    __table_args__ = (
        Index("idx_price_history_product_timestamp", "product_id", "timestamp"),
    )

    def __repr__(self):
        return f"<PriceHistory(product_id={self.product_id}, price={self.price}, timestamp={self.timestamp})>"


class SiteMetadata(Base):
    """
    Model for storing site-specific metadata and crawling information.
    """
    __tablename__ = "site_metadata"

    id = Column(Integer, primary_key=True, index=True)
    site = Column(Enum(SiteEnum), nullable=False, unique=True)
    base_url = Column(String(255), nullable=False)
    search_url_template = Column(String(500), nullable=True)
    last_crawl_time = Column(DateTime(timezone=True), nullable=True)
    crawl_frequency_minutes = Column(Integer, default=1440)  # Default to daily
    rate_limit_requests = Column(Integer, default=10)
    rate_limit_period_seconds = Column(Integer, default=60)
    requires_proxy = Column(Boolean, default=True)
    requires_login = Column(Boolean, default=False)
    login_details = Column(JSON, nullable=True)
    crawl_settings = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SiteMetadata(site={self.site}, last_crawl_time={self.last_crawl_time})>"


class ArbitrageOpportunity(Base):
    """
    Model for storing identified arbitrage opportunities.
    """
    __tablename__ = "arbitrage_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    source_product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    target_product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    source_price = Column(Float, nullable=False)  # Including shipping
    target_price = Column(Float, nullable=False)  # Including shipping
    price_difference = Column(Float, nullable=False)  # target_price - source_price
    profit_margin = Column(Float, nullable=False)  # (price_difference / source_price) * 100
    currency = Column(String(3), nullable=False, default="USD")
    shipping_source_to_customer = Column(Float, nullable=True)  # Estimated shipping cost
    other_fees = Column(Float, nullable=True)  # Platform fees, etc.
    estimated_net_profit = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=True)  # 0-100 score for match confidence
    identified_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    # Relationships
    source_product = relationship("Product", foreign_keys=[source_product_id], back_populates="arbitrage_opportunities_source")
    target_product = relationship("Product", foreign_keys=[target_product_id], back_populates="arbitrage_opportunities_target")

    # Indexes
    __table_args__ = (
        Index("idx_arbitrage_product_pair", "source_product_id", "target_product_id", unique=True),
        Index("idx_arbitrage_profit_margin", "profit_margin"),
    )

    def __repr__(self):
        return f"<ArbitrageOpportunity(source_id={self.source_product_id}, target_id={self.target_product_id}, profit_margin={self.profit_margin})>"


class ProxyConfig(Base):
    """
    Model for storing proxy configuration and status.
    """
    __tablename__ = "proxy_configs"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # IPv4 or IPv6
    port = Column(Integer, nullable=False)
    protocol = Column(String(10), nullable=False, default="http")  # http, https, socks5
    username = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    country = Column(String(2), nullable=True)  # ISO country code
    provider = Column(String(50), nullable=True, default="ipburger")
    is_active = Column(Boolean, default=True, index=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_failure = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(String(255), nullable=True)
    banned_sites = Column(JSON, nullable=True)  # List of sites where this proxy is banned
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        UniqueConstraint("ip_address", "port", "protocol", name="uq_proxy_config"),
        Index("idx_proxy_active_last_used", "is_active", "last_used"),
    )

    def __repr__(self):
        return f"<ProxyConfig(ip_address={self.ip_address}, is_active={self.is_active})>"

