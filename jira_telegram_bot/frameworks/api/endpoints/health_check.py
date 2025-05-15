"""Health check endpoint for API service."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint


class HealthCheckEndpoint(ServiceAPIEndpointBluePrint):
    """Health check endpoint for API service status monitoring."""
    
    def __init__(self):
        """Initialize the health check endpoint."""
        self.start_time = datetime.now()
    
    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for health checks.
        
        Returns:
            Configured APIRouter for health check endpoints
        """
        api_route = APIRouter(
            prefix="/health",
            tags=["Health"]
        )
        
        @api_route.get(
            "/",
            summary="Health check endpoint",
            description="Returns the current status of the API service"
        )
        async def health_check():
            """Health check endpoint.
            
            Returns:
                Dictionary with service status information
            """
            uptime = datetime.now() - self.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            return {
                "status": "ok",
                "version": "1.0.0",
                "uptime": f"{days}d {hours}h {minutes}m {seconds}s",
                "timestamp": datetime.now().isoformat()
            }
        
        @api_route.get(
            "/ping",
            summary="Simple ping endpoint",
            description="Returns a simple pong response to verify the service is running"
        )
        async def ping():
            """Simple ping endpoint.
            
            Returns:
                Pong response
            """
            return {"ping": "pong"}
        
        return api_route
