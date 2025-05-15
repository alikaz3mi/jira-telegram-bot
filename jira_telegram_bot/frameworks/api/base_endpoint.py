"""Base blueprint for API endpoints."""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import APIRouter


class ServiceAPIEndpointBluePrint(ABC):
    """Blueprint for API endpoints following Clean Architecture.
    
    This abstract class defines the contract that all API endpoints must follow
    to maintain clean architecture boundaries between frameworks and use cases.
    """
    
    def __init__(self):
        """Initialize the endpoint with an API router."""
        # This will be populated by the create_rest_api_route method
        self.api_route = None
        # Call the implementation's create_rest_api_route method
        router = self.create_rest_api_route()
        # Store the returned router
        self.api_route = router
    
    @abstractmethod
    def create_rest_api_route(self) -> APIRouter:
        """Create and return a configured APIRouter with route handlers.
        
        This method should be implemented by all endpoint classes to set up
        their specific routes and handlers.
        
        Returns:
            APIRouter with all endpoint routes properly configured
        """
        pass
