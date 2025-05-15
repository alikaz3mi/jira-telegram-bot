"""Base blueprint for API endpoints."""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import APIRouter


class ServiceAPIEndpointBluePrint(ABC):
    """Blueprint for API endpoints following Clean Architecture.
    
    This abstract class defines the contract that all API endpoints must follow
    to maintain clean architecture boundaries between frameworks and use cases.
    """
    
    @abstractmethod
    def create_rest_api_route(self) -> APIRouter:
        """Create and return a configured APIRouter with route handlers.
        
        Returns:
            APIRouter with all endpoint routes properly configured
        """
        pass
