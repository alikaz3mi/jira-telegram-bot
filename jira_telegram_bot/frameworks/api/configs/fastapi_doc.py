"""FastAPI configuration settings."""

from __future__ import annotations

from typing import Dict, List

# FastAPI tags metadata for API documentation
fastapi_tags_metadata: List[Dict[str, str]] = [
    {
        "name": "Webhooks",
        "description": "Endpoints for handling webhook events from Telegram and Jira",
    },
]
