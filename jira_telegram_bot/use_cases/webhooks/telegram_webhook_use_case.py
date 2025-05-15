"""Use case for handling Telegram webhook events."""

from __future__ import annotations

from typing import Dict, Any

from telegram import Update

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.use_cases.interfaces.telegram_webhook_handler_interface import TelegramWebhookHandlerInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.create_task_usecase import CreateTaskUseCase
from jira_telegram_bot.use_cases.ai_agents.parse_jira_prompt_usecase import ParseJiraPromptUseCase
from jira_telegram_bot.utils.data_store import get_issue_key_from_channel_post
from jira_telegram_bot.utils.data_store import save_comment
from jira_telegram_bot.utils.data_store import save_mapping


class TelegramWebhookUseCase(TelegramWebhookHandlerInterface):
    """Use case for processing Telegram webhook events.
    
    This use case handles Telegram webhook events and creates Jira tasks
    or manages replies based on the message type.
    """
    
    def __init__(
        self,
        create_task_use_case: CreateTaskUseCase,
        parse_prompt_use_case: ParseJiraPromptUseCase,
        task_manager_repository: TaskManagerRepositoryInterface
    ):
        """Initialize the use case.
        
        Args:
            create_task_use_case: Use case for creating Jira tasks
            parse_prompt_use_case: Use case for parsing Jira prompts
            task_manager_repository: Repository for task management operations
        """
        self.create_task_use_case = create_task_use_case
        self.parse_prompt_use_case = parse_prompt_use_case
        self.task_manager_repository = task_manager_repository
    
    async def process_update(self, update_data: Dict[str, Any]) -> WebhookResponse:
        """Process a Telegram update event.
        
        Args:
            update_data: The update payload from Telegram
            
        Returns:
            Response with status and message
        """
        try:
            # Convert to telegram.Update object
            update = Update.de_json(update_data, None)
            
            if not update:
                return WebhookResponse(status="error", message="Invalid update data")
            
            # Handle channel posts (new tasks)
            if update.channel_post:
                return await self._handle_channel_post(update)
            
            # Handle replies on channel posts (comments)
            elif update.message and update.message.reply_to_message:
                return await self._handle_reply(update)
                
            # Handle direct messages (fallback)
            elif update.message:
                return await self._handle_direct_message(update)
            
            return WebhookResponse(status="ignored", message="Unsupported update type")
            
        except Exception as e:
            LOGGER.error(f"Error processing Telegram update: {str(e)}", exc_info=True)
            return WebhookResponse(status="error", message=f"Error: {str(e)}")
    
    async def _handle_channel_post(self, update: Update) -> WebhookResponse:
        """Handle a new channel post, creating a Jira task.
        
        Args:
            update: The Telegram update
            
        Returns:
            Response with status and message
        """
        channel_post = update.channel_post
        
        if not channel_post or not channel_post.text:
            return WebhookResponse(status="ignored", message="Empty channel post")
        
        # Create task from channel post
        try:
            # Parse the prompt using AI
            parsed_data = await self.parse_prompt_use_case.run(channel_post.text)
            
            # Create the task
            issue = await self.create_task_use_case.execute_task_creation(
                project_key=parsed_data.get("project_key", "DEFAULT"),
                summary=parsed_data.get("summary", channel_post.text[:50] + "..."),
                description=channel_post.text,
                issue_type=parsed_data.get("issue_type", "Task"),
                components=parsed_data.get("components", []),
                labels=parsed_data.get("labels", [])
            )
            
            if not issue:
                return WebhookResponse(status="error", message="Failed to create task")
            
            # Save mapping between channel post and Jira issue
            save_mapping(
                issue_key=issue.key,
                channel_chat_id=str(channel_post.chat_id),
                channel_post_id=channel_post.message_id,
                message_id=channel_post.message_id
            )
            
            return WebhookResponse(
                status="success", 
                message=f"Created issue {issue.key}"
            )
            
        except Exception as e:
            LOGGER.error(f"Error creating task: {str(e)}", exc_info=True)
            return WebhookResponse(status="error", message=f"Error creating task: {str(e)}")
    
    async def _handle_reply(self, update: Update) -> WebhookResponse:
        """Handle a reply to a channel post, adding a comment to Jira.
        
        Args:
            update: The Telegram update
            
        Returns:
            Response with status and message
        """
        message = update.message
        reply_to = message.reply_to_message
        
        if not message.text:
            return WebhookResponse(status="ignored", message="Empty reply")
        
        # Find the corresponding Jira issue
        issue_key = get_issue_key_from_channel_post(
            chat_id=str(reply_to.chat_id),
            message_id=reply_to.message_id
        )
        
        if not issue_key:
            return WebhookResponse(status="ignored", message="No associated issue found")
        
        # Add comment to Jira
        try:
            username = message.from_user.username or message.from_user.first_name
            comment_text = f"{username}: {message.text}"
            
            # Add comment to Jira issue
            self.task_manager_repository.add_comment(issue_key, comment_text)
            
            # Save comment mapping
            save_comment(
                issue_key=issue_key,
                telegram_message_id=message.message_id,
                telegram_chat_id=str(message.chat_id)
            )
            
            return WebhookResponse(
                status="success",
                message=f"Added comment to {issue_key}"
            )
            
        except Exception as e:
            LOGGER.error(f"Error adding comment: {str(e)}", exc_info=True)
            return WebhookResponse(
                status="error",
                message=f"Error adding comment: {str(e)}"
            )
    
    async def _handle_direct_message(self, update: Update) -> WebhookResponse:
        """Handle a direct message to the bot.
        
        Args:
            update: The Telegram update
            
        Returns:
            Response with status and message
        """
        # For webhook API, we only process channel posts and replies
        # Direct messages should be handled by the bot framework
        return WebhookResponse(
            status="ignored",
            message="Direct messages should be handled by the bot framework"
        )
