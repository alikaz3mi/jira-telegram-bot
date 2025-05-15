"""Main entry point for FastAPI application serving Telegram webhooks."""

import uvicorn
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container, create_fastapi_integration
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.frameworks.api.api_endpoint import APIEndpoint, APIEndpointConfig


def main():
    """Main function to start the API server."""
    LOGGER.info("Initializing Jira Telegram Bot API server")
    
    # Get container and retrieve registered endpoints
    container = get_container()
    sub_service_endpoints = container[SubServiceEndpoints]
    
    # Create FastAPI dependency integration
    fastapi_di = create_fastapi_integration()
    
    # Create API endpoint configuration with specific port
    api_config = APIEndpointConfig(port=2316)
    
    # Create and configure API endpoint
    api_endpoint = APIEndpoint(api_config, sub_service_endpoints)
    
    LOGGER.info("Starting FastAPI server")
    # Run the application in the main process
    api_endpoint.start_app(main_process=True)


if __name__ == "__main__":
    main()
