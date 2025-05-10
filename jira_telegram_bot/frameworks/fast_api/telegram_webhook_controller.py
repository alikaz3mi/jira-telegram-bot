from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import HandleJiraWebhookUseCase
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.telegram_gateway_interface import (
    TelegramGatewayInterface,
)

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import ParseJiraPromptUseCase
from jira_telegram_bot.utils.data_store import get_issue_key_from_channel_post
from jira_telegram_bot.utils.data_store import save_comment
from jira_telegram_bot.utils.data_store import save_mapping


def get_telegram_router(deps):
    router = APIRouter()

    @router.post("/telegram/webhook")
    async def telegram_webhook(
        request: Request,
        create_task_uc: CreateTaskUseCase = Depends(deps.depends(CreateTaskUseCase)),
        parse_prompt_uc: ParseJiraPromptUseCase = Depends(
            deps.depends(ParseJiraPromptUseCase),
        ),
        telegram_gateway: TelegramGatewayInterface = Depends(
            deps.depends(TelegramGatewayInterface),
        ),
        jira_repo: TaskManagerRepositoryInterface = Depends(
            deps.depends(TaskManagerRepositoryInterface),
        ),
    ):
        """
        Your main Telegram webhook entrypoint
        (Requests -> frameworks, frameworks -> use case).
        """
        try:
            data = await request.json()
            LOGGER.debug(f"Incoming Telegram data: {data}")

            # Example: handle "channel_post" for creating tasks
            if "channel_post" in data:
                channel_post = data["channel_post"]
                text = channel_post.get("text") or channel_post.get("caption") or ""

                # If it's a reply => add comment
                if "reply_to_message" in channel_post:
                    parent_msg_id = channel_post["reply_to_message"]["message_id"]
                    issue_key = get_issue_key_from_channel_post(parent_msg_id)
                    if issue_key:
                        jira_repo.add_comment(issue_key, text)
                        save_comment(parent_msg_id, text)
                        return {"status": "success", "message": "Comment added."}

                    return {"status": "ignored", "reason": "No matching issue key."}

                # Otherwise, parse user text with LLM
                parsed_data = parse_prompt_uc.run(text)
                # Then create the Jira task
                issue = create_task_uc.run(
                    project_key="PCT",  # or from your config
                    summary=parsed_data["summary"],
                    description=parsed_data["description"],
                    task_type=parsed_data["task_type"],
                    labels=[parsed_data.get("labels", "")],
                    assignee=None,  # or from your user mapping
                )
                # Save mapping
                save_mapping(
                    channel_post["message_id"],
                    issue.key,
                    channel_post["chat"]["id"],
                    channel_post["chat"]["id"],
                )

                # Possibly call telegram_gateway.send_message to confirm
                telegram_gateway.send_message(
                    chat_id=channel_post["chat"]["id"],
                    text=f"Created Jira task: {JIRA_SETTINGS.domain}/browse/{issue.key}",
                )
                return {"status": "success", "message": "Task created."}

            # ... handle other "message" or group logic ...
            return {"status": "ignored", "reason": "Not a channel_post or message."}

        except Exception as e:
            LOGGER.error(f"Error in telegram_webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
