"""Main entry point for FastAPI application serving Telegram webhooks."""

import asyncio
import contextlib
import uvicorn
from typing import AsyncGenerator

from fastapi import FastAPI
from contextlib import asynccontextmanager

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import startup, shutdown
from jira_telegram_bot.frameworks.api.entry_point import app


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Define application lifespan events.
    
    Args:
        _app: FastAPI application instance
        
    Yields:
        None
    """
    # Startup: run initialization tasks
    startup()
    LOGGER.info("FastAPI application ready to serve requests")
    
    yield
    
    # Shutdown: clean up resources
    await shutdown()
    LOGGER.info("FastAPI application shutdown complete")


# Update app to use the lifespan context manager
app.router.lifespan_context = lifespan


async def run_app_wrapper() -> None:
    """Wrap application setup in async context.
    
    Returns:
        None
    """
    LOGGER.info("Preparing FastAPI application")
    # No need to run startup here as it will be called in the lifespan context


if __name__ == "__main__":
    # Run async setup
    asyncio.run(run_app_wrapper())
    
    # Start Uvicorn server with app module path for proper reloading
    uvicorn.run(
        "jira_telegram_bot.frameworks.api.entry_point:app",
        host="0.0.0.0",
        port=2316,
        reload=True,
        log_level="info",
    )
