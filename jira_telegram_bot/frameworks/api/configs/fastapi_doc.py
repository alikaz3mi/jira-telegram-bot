"""FastAPI configuration settings."""

from __future__ import annotations

from typing import Dict, List, Any

# API version prefix
api_prefix: str = "/api/v1"

# FastAPI information dictionary
fastapi_information: Dict[str, Any] = {
    "title": "Jira Telegram Bot API",
    "description": "API for Jira Telegram Bot integration",
    "version": "1.0.0",
    "openapi_url": f"{api_prefix}/openapi.json",
    "docs_url": f"{api_prefix}/docs",
    "redoc_url": f"{api_prefix}/redoc",
}

# FastAPI tags metadata for API documentation
fastapi_tags_metadata: List[Dict[str, str]] = [
    {
        "name": "Main",
        "description": "Main API endpoints and navigation",
    },
    {
        "name": "Webhooks",
        "description": "Endpoints for handling webhook events from Telegram and Jira",
    },
    {
        "name": "Projects",
        "description": "Endpoints for project status and management operations",
    },
    {
        "name": "Health",
        "description": "Health check endpoints for monitoring service status",
    },
]
