"""FastAPI application entry point."""

from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container, create_fastapi_integration
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.frameworks.api.api_endpoint import APIEndpoint, APIEndpointConfig


# Get container and retrieve registered endpoints
container = get_container()
sub_service_endpoints = container[SubServiceEndpoints]

# Create API endpoint configuration
api_config = APIEndpointConfig()

# Create and configure API endpoint
api_endpoint = APIEndpoint(api_config, sub_service_endpoints)

# Export the FastAPI application
app = api_endpoint.rest_application
