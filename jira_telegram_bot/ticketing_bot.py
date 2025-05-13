"""Main entry point for FastAPI application serving Telegram webhooks."""

import asyncio
import uvicorn
from functools import partial

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import startup, shutdown
from jira_telegram_bot.frameworks.fast_api.create_ticket_controller import app


async def run_app_wrapper():
    """Wrap application startup and shutdown in async context."""
    # Run startup tasks
    await startup()
    
    # The actual application will be run by uvicorn
    LOGGER.info("FastAPI application ready to serve requests")


def on_shutdown():
    """Run shutdown tasks when Uvicorn exits."""
    asyncio.run(shutdown())
    LOGGER.info("FastAPI application shutdown complete")


if __name__ == "__main__":
    # Run startup tasks
    asyncio.run(run_app_wrapper())
    
    # Register shutdown handler with Uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=2315,
        reload=True,
        log_level="info",
        on_shutdown=[on_shutdown],
    )
