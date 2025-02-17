from __future__ import annotations

from fastapi import FastAPI

from jira_telegram_bot.app_container import create_fastapi_integration
from jira_telegram_bot.frameworks.fast_api.telegram_webhook_controller import (
    get_telegram_router,
)

# from jira_telegram_bot.frameworks.fast_api.jira_webhook_controller import get_jira_router

# 1) Create the FastAPI app
app = FastAPI()

# 2) Create lagom's FastApiIntegration
deps = create_fastapi_integration()

# 3) Include your routers, passing deps so they can do `deps.depends(...)`
app.include_router(get_telegram_router(deps))
# app.include_router(get_jira_router(deps))
