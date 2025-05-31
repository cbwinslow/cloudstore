"""
Main FastAPI application module for CloudStore.

This module initializes the FastAPI application, configures middleware,
sets up error handlers, and includes API routes.
"""

import time
from typing import Dict, List, Any, Callable, Optional
from collections import defaultdict

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from cloudstore.core.config import settings

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for tracking and analyzing product prices across e-commerce platforms.",
    version="0.1.0",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory rate limiter
class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        
    def is_rate_limited(self, client_id: str, limit: int, window: int) -> bool:
        """
        Check if client is rate limited.
        
        Args:
            client_id: Identifier for the client (e.g., IP address)
            limit: Maximum number of requests allowed in the window
            window: Time window in seconds
            
        Returns:
            True if client is rate limited, False otherwise
        """
        current_time = time.time()
        
        # Remove old timestamps
        self.requests[client_id] = [
            timestamp for timestamp in self.requests[client_id]
            if current_time - timestamp < window
        ]
        
        # Check if client is rate limited
        if len(self.requests[client_id]) >= limit:
            return True
        
        # Add current request timestamp
        self.requests[client_id].append(current_time)
        return False

# Initialize rate limiter
rate_limiter = RateLimiter()

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    Rate limiting middleware to protect API from abuse.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware or route handler
        
    Returns:
        Response from the next middleware or route handler
    """
    client_id = request.client.host if request.client else "unknown"
    
    # Skip rate limiting for certain paths if needed
    # if request.url.path in ["/docs", "/redoc"]:
    #     return await call_next(request)
    
    # Check if client is rate limited
    if rate_limiter.is_rate_limited(
        client_id, 
        settings.RATE_LIMIT_PER_MINUTE, 
        settings.RATE_LIMIT_WINDOW_SECONDS
    ):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )
    
    return await call_next(request)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions and return standardized JSON response.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle general exceptions and return standardized JSON response.
    """
    # In production, you'd want to log this exception
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# Custom API documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> Response:
    """
    Custom Swagger UI documentation.
    """
    return get_swagger_ui_html(
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        title=f"{settings.PROJECT_NAME} - Swagger UI",
        oauth2_redirect_url=None,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> Response:
    """
    ReDoc documentation.
    """
    return get_redoc_html(
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        title=f"{settings.PROJECT_NAME} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint returning welcome message.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "documentation": "/docs",
        "version": "0.1.0"
    }

# Include API routers
from cloudstore.api.routes import products, price_history, arbitrage, site, proxy

# Add all routers with API version prefix
app.include_router(products.router, prefix=settings.API_V1_STR)
app.include_router(price_history.router, prefix=settings.API_V1_STR)
app.include_router(arbitrage.router, prefix=settings.API_V1_STR)
app.include_router(site.router, prefix=settings.API_V1_STR)
app.include_router(proxy.router, prefix=settings.API_V1_STR)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG,
        workers=settings.API_WORKERS,
    )

