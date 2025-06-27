import asyncio
from datetime import datetime, time
from typing import List

from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import TelegramNotifierInterface
from jira_telegram_bot.frameworks.scheduler.cron_job import CronJob
from jira_telegram_bot.use_cases.jira.get_sprint_issues_usecase import GetSprintIssuesUseCase
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


class DailyReportJob(CronJob):
    """Scheduler job for sending daily progress report prompts to team members."""

    def __init__(
        self,
        telegram_notifier: TelegramNotifierInterface,
        get_sprint_issues_usecase: GetSprintIssuesUseCase,
        user_config: UserConfigInterface,
        sprint_label: str,
        report_channel_id: str,
        prompt_start_hour: int = 14,
        prompt_end_hour: int = 16,
    ):
        """Initialize the daily report job.

        Args:
            telegram_notifier: Service for sending Telegram notifications.
            get_sprint_issues_usecase: Use case for fetching sprint issues.
            user_config: Interface for accessing user configuration.
            sprint_label: The current sprint label or JQL.
            report_channel_id: Channel ID for aggregated reports.
            prompt_start_hour: Hour to start sending prompts (24-hour format).
            prompt_end_hour: Hour to stop sending prompts (24-hour format).
        """
        super().__init__(
            name="daily_report_job",
            schedule="0 14-16 * * 1-5",  # Every hour between 14:00-16:00, Monday-Friday
            timezone="UTC"
        )
        self._telegram_notifier = telegram_notifier
        self._get_sprint_issues_usecase = get_sprint_issues_usecase
        self._user_config = user_config
        self._sprint_label = sprint_label
        self._report_channel_id = report_channel_id
        self._prompt_start_hour = prompt_start_hour
        self._prompt_end_hour = prompt_end_hour

    async def run(self) -> None:
        """Execute the daily report job."""
        current_hour = datetime.now().hour
        
        # Only run during the specified time window
        if not (self._prompt_start_hour <= current_hour <= self._prompt_end_hour):
            return

        try:
            # Get team members from the report channel
            team_members = await self._get_team_members()
            
            # Send progress report prompts to each team member
            for member in team_members:
                await self._send_progress_prompt(member)
                
        except Exception as e:
            self.logger.error(f"Daily report job failed: {str(e)}")

    async def _get_team_members(self) -> List[str]:
        """Get team members from user configuration.

        Returns:
            List of team member usernames.
        """
        try:
            user_configs = self._user_config.get_all_user_configs()
            
            # Return all telegram usernames from user configs
            return [
                config.telegram_username for config in user_configs.values()
                if config.telegram_username
            ]
            
        except Exception as e:
            self.logger.warning(f"Could not get team members: {str(e)}")
            return []

    async def _send_progress_prompt(self, username: str) -> None:
        """Send a progress report prompt to a team member.

        Args:
            username: The team member's username.
        """
        try:
            # Get user config to find chat ID
            user_config = self._user_config.get_user_config(username)
            if not user_config or not user_config.telegram_user_chat_id:
                self.logger.warning(f"No chat ID found for user {username}")
                return

            # Get user's assigned tasks in the current sprint
            assigned_tasks = await self._get_user_assigned_tasks(user_config.jira_username)
            
            message = self._create_progress_prompt_message(username, assigned_tasks)
            
            # Send direct message to the user using telegram notifier
            # Note: We'll need to create a simple alert-like message structure
            # This is a simplified approach - in production you might want a dedicated method
            await self._send_message_via_notifier(
                user_config.telegram_user_chat_id,
                message
            )
            
        except Exception as e:
            self.logger.warning(f"Could not send prompt to {username}: {str(e)}")

    async def _send_message_via_notifier(self, chat_id: int, message: str) -> None:
        """Send a simple message using the telegram notifier.
        
        Args:
            chat_id: Telegram chat ID
            message: Message text to send
        """
        # This is a workaround since TelegramNotifier is designed for deadline alerts
        # In production, you might want to add a general message sending method to the interface
        try:
            # We'll use the notifier's internal method if available
            if hasattr(self._telegram_notifier, '_send_message'):
                await self._telegram_notifier._send_message(chat_id, message)
            else:
                self.logger.warning("Telegram notifier doesn't support direct message sending")
        except Exception as e:
            self.logger.error(f"Failed to send message to {chat_id}: {str(e)}")

    async def _get_user_assigned_tasks(self, jira_username: str) -> List[str]:
        """Get tasks assigned to a specific user in the current sprint.

        Args:
            jira_username: The team member's Jira username.

        Returns:
            List of assigned task keys.
        """
        try:
            sprint_issues = await self._get_sprint_issues_usecase.execute(
                sprint_label=self._sprint_label
            )
            
            # Filter tasks assigned to the user
            user_tasks = [
                issue.key for issue in sprint_issues
                if issue.assignee and issue.assignee.lower() == jira_username.lower()
            ]
            
            return user_tasks
            
        except Exception as e:
            self.logger.warning(f"Could not get assigned tasks for {jira_username}: {str(e)}")
            return []

    def _create_progress_prompt_message(self, username: str, assigned_tasks: List[str]) -> str:
        """Create the progress report prompt message.

        Args:
            username: The team member's username.
            assigned_tasks: List of assigned task keys.

        Returns:
            Formatted prompt message.
        """
        greeting = f"Hi {username}! 👋"
        
        if assigned_tasks:
            tasks_text = "\n".join([f"• {task}" for task in assigned_tasks])
            message = f"""{greeting}

Time for your daily progress report! 📋

**Your assigned tasks in {self._sprint_label}:**
{tasks_text}

Please share your progress by:
🎤 Recording a voice message, or
💬 Typing your update

What have you accomplished today? Any blockers?"""
        else:
            message = f"""{greeting}

Time for your daily progress report! 📋

I couldn't find any tasks specifically assigned to you in {self._sprint_label}, but feel free to share your progress on any work you've been doing.

Please share your progress by:
🎤 Recording a voice message, or
💬 Typing your update

What have you accomplished today? Any blockers?"""

        return message

    def _create_progress_prompt_keyboard(self):
        """Create inline keyboard for progress report options.

        Returns:
            Telegram inline keyboard markup.
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [
                InlineKeyboardButton("🎤 Voice Report", callback_data="progress_voice"),
                InlineKeyboardButton("💬 Text Report", callback_data="progress_text"),
            ],
            [
                InlineKeyboardButton("📋 Select Tasks", callback_data="progress_select_tasks"),
            ],
            [
                InlineKeyboardButton("⚰️ Skip Today", callback_data="progress_skip"),
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
