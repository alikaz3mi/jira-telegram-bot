"""Main FastAPI application following Clean Architecture patterns."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Jira Telegram Bot API",
        description="API for Jira Telegram Bot with Clean Architecture",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Get the dependency injection container
    container = get_container()
    
    # Get the endpoint registry
    endpoint_registry = container[SubServiceEndpoints]
    
    # Register all endpoint routes
    for endpoint in endpoint_registry.endpoints:
        app.include_router(
            endpoint.api_route,
            prefix=f"/{endpoint.__class__.__name__.lower().replace('endpoint', '')}"
        )
        LOGGER.info(f"Registered API routes for {endpoint.__class__.__name__}")
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    LOGGER.info("Starting Jira Telegram Bot API server...")
    uvicorn.run(
        "jira_telegram_bot.frameworks.api.main:app",
        host="0.0.0.0",
        port=2315,
        reload=True,
        log_level="info"
    )
