"""
Database configuration for CloudStore.

This module provides utilities for connecting to the PostgreSQL database.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection settings
DB_USER = os.getenv("DB_USER", "cbwinslow")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cloudstore")

# Synchronous database URL
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Asynchronous database URL
ASYNC_SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine for synchronous operations
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "False").lower() == "true"),
    pool_pre_ping=True
)

# Create engine for asynchronous operations
async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "False").lower() == "true"),
    pool_pre_ping=True
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    bind=async_engine
)

# Base class for models
Base = declarative_base()

# Function to get a database session
def get_db():
    """
    Get a database session and ensure it's closed after use.
    
    Yields:
        session (Session): A SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to get an async database session
async def get_async_db():
    """
    Get an async database session and ensure it's closed after use.
    
    Yields:
        session (AsyncSession): A SQLAlchemy async session.
    """
    async_session = AsyncSessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()

