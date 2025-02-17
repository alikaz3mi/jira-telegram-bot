# jira_telegram_bot/frameworks/fast_api/jira_webhook_controller.py
from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from lagom import Context

from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import (
    HandleJiraWebhookUseCase,
)

router = APIRouter()


@router.post("/jira/webhook")
async def jira_webhook_endpoint(
    request: Request,
    handle_jira_uc: HandleJiraWebhookUseCase = Depends(
        Context.scope(HandleJiraWebhookUseCase),
    ),
):
    """
    FastAPI endpoint receiving Jira webhook events,
    then passing them to the HandleJiraWebhookUseCase.
    """
    try:
        body = await request.json()
        result = handle_jira_uc.run(body)
        return result

    except Exception as e:
        # Log or handle errors
        return {"status": "error", "message": str(e)}
