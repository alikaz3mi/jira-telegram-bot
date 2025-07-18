"""Main FastAPI application following Clean Architecture patterns."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container

from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.frameworks.api.entry_point import APIEndpoint, FastAPIConfig
from jira_telegram_bot.settings.fast_api_settings import FastAPISettings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    global _app

    if _app is None:
        container = get_container()
        
        api_endpoint = APIEndpoint(
            configs=container[FastAPIConfig],
            fastapi_settings=container[FastAPISettings],
            sub_service_endpoints=container[SubServiceEndpoints],
        )

        _app = api_endpoint.rest_api_app

    return _app
    return app




if __name__ == "__main__":
    import uvicorn
    app = create_app()
    settings = FastAPISettings()
    LOGGER.info("Starting Jira Telegram Bot API server...")
    uvicorn.run(
        "jira_telegram_bot.frameworks.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )
