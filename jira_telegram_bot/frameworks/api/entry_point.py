"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import create_fastapi_integration, startup, shutdown
from jira_telegram_bot.frameworks.api.configs import fastapi_tags_metadata
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle manager for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    
    Yields:
        None when setup is complete
    """
    # Startup
    LOGGER.info("Starting API server...")
    await startup()
    yield
    # Shutdown
    LOGGER.info("Shutting down API server...")
    await shutdown()


# Create FastAPI application
app = FastAPI(
    title="Jira Telegram Bot API",
    description="API for Jira Telegram Bot integration",
    version="1.0.0",
    openapi_tags=fastapi_tags_metadata,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up dependency injection
deps = create_fastapi_integration()

# Register endpoints from SubServiceEndpoints
# Use depends() method instead of subscription notation
# endpoints_registry = deps.depends(SubServiceEndpoints)
for endpoint in deps[SubServiceEndpoints].endpoints:
    LOGGER.info(f"Registering endpoint: {endpoint.__class__.__name__}")
    app.include_router(endpoint.create_rest_api_route())
