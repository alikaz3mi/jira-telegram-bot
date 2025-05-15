"""Registry for API endpoints."""

from __future__ import annotations

from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint


class SubServiceEndpoints:
    """Registry for API endpoint services.
    
    This class collects all endpoint services and makes them available
    for registration with FastAPI.
    """
    
    def __init__(self):
        """Initialize the registry with an empty list of endpoints."""
        self.endpoints: List[ServiceAPIEndpointBluePrint] = []
    
    def register(self, endpoint: ServiceAPIEndpointBluePrint) -> None:
        """Register an endpoint with the registry.
        
        Args:
            endpoint: The endpoint to register
        """
        LOGGER.info(f"Registering endpoint: {endpoint.__class__.__name__}")
        self.endpoints.append(endpoint)
