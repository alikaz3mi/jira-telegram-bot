from __future__ import annotations

import asyncio
from typing import List
from typing import Optional

import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import TelegramNotifierInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


class TelegramNotifier(TelegramNotifierInterface):
    """Telegram notifier implementation using HTTP API."""
    
    def __init__(
        self,
        telegram_settings: TelegramConnectionSettings,
        user_config_repository: UserConfigInterface,
    ):
        self.telegram_settings = telegram_settings
        self.user_config_repository = user_config_repository
        self.base_url = f"https://api.telegram.org/bot{telegram_settings.TOKEN}"
    
    async def send_personal_notification(
        self,
        chat_id: int,
        alert: DeadlineAlert,
    ) -> bool:
        """Send a deadline alert to a personal chat."""
        try:
            message = await self.format_alert_message(alert)
            return await self._send_message(chat_id, message)
        except Exception as e:
            LOGGER.error(f"Error sending personal notification to {chat_id}: {e}")
            return False
    
    async def send_group_notification(
        self,
        chat_id: int,
        alerts: List[DeadlineAlert],
        mention_users: bool = True,
    ) -> bool:
        """Send deadline alerts to a group chat."""
        try:
            if not alerts:
                return True
            
            message = await self._format_group_message(alerts, mention_users)
            return await self._send_message(chat_id, message)
        except Exception as e:
            LOGGER.error(f"Error sending group notification to {chat_id}: {e}")
            return False
    
    async def format_alert_message(
        self,
        alert: DeadlineAlert,
        include_mention: bool = False,
        telegram_username: Optional[str] = None,
    ) -> str:
        """Format a deadline alert as a Telegram message."""
        urgency_emoji = self._get_urgency_emoji(alert.urgency_level)
        
        # Build message header
        header = f"{urgency_emoji} *Deadline Alert*"
        if include_mention and telegram_username:
            header += f" @{telegram_username}"
        
        # Build deadline info
        deadline_text = "No deadline set"
        if alert.effective_deadline:
            deadline_date = alert.effective_deadline.strftime("%Y-%m-%d")
            if alert.is_overdue:
                deadline_text = f"⚠️ OVERDUE by {abs(alert.days_remaining)} days (was due: {deadline_date})"
            elif alert.days_remaining == 0:
                deadline_text = f"🔥 DUE TODAY ({deadline_date})"
            elif alert.days_remaining == 1:
                deadline_text = f"⏰ Due tomorrow ({deadline_date})"
            else:
                deadline_text = f"📅 Due in {alert.days_remaining} days ({deadline_date})"
        
        # Build message body
        message_parts = [
            header,
            "",
            f"🎫 *Issue:* [{alert.issue_key}]({alert.issue_url})",
            f"📝 *Summary:* {alert.summary}",
            f"⏳ *Deadline:* {deadline_text}",
            f"📊 *Status:* {alert.status}",
            f"🏷️ *Project:* {alert.project_key}",
        ]
        
        if alert.assignee:
            message_parts.append(f"👤 *Assignee:* {alert.assignee}")
        
        if alert.priority:
            priority_emoji = self._get_priority_emoji(alert.priority)
            message_parts.append(f"{priority_emoji} *Priority:* {alert.priority}")
        
        return "\n".join(message_parts)
    
    async def _format_group_message(
        self,
        alerts: List[DeadlineAlert],
        mention_users: bool = True,
    ) -> str:
        """Format multiple alerts for a group message."""
        if not alerts:
            return ""
        
        # Sort alerts by urgency and days remaining
        sorted_alerts = sorted(
            alerts,
            key=lambda a: (
                0 if a.urgency_level == "overdue" else
                1 if a.urgency_level == "today" else
                2 if a.urgency_level == "urgent" else
                3,
                a.days_remaining,
            )
        )
        
        header = f"🚨 *Team Deadline Report* ({len(alerts)} issues)"
        message_parts = [header, ""]
        
        # Group by urgency level
        urgency_groups = {}
        for alert in sorted_alerts:
            urgency_groups.setdefault(alert.urgency_level, []).append(alert)
        
        for urgency_level in ["overdue", "today", "urgent", "high"]:
            if urgency_level not in urgency_groups:
                continue
            
            group_alerts = urgency_groups[urgency_level]
            urgency_emoji = self._get_urgency_emoji(urgency_level)
            
            message_parts.append(f"{urgency_emoji} **{urgency_level.upper()}** ({len(group_alerts)} issues)")
            
            for alert in group_alerts:
                # Get telegram username for mention
                telegram_username = None
                if mention_users and alert.assignee:
                    telegram_username = await self._get_telegram_username(alert.assignee)
                
                mention_text = f" @{telegram_username}" if telegram_username else ""
                deadline_text = self._get_short_deadline_text(alert)
                
                message_parts.append(
                    f"• [{alert.issue_key}]({alert.issue_url}): {alert.summary[:50]}{'...' if len(alert.summary) > 50 else ''}"
                )
                message_parts.append(f"  {deadline_text}{mention_text}")
            
            message_parts.append("")
        
        return "\n".join(message_parts)
    
    async def _send_message(self, chat_id: int, text: str) -> bool:
        """Send a message via Telegram API."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        
        try:
            # Use asyncio to run the blocking request in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, timeout=10)
            )
            
            response.raise_for_status()
            LOGGER.debug(f"Message sent successfully to chat {chat_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Failed to send message to chat {chat_id}: {e}")
            return False
    
    async def _get_telegram_username(self, jira_username: str) -> Optional[str]:
        """Get Telegram username for a Jira user."""
        try:
            user_configs = self.user_config_repository.get_all_user_configs()
            for config in user_configs.values():
                if config.jira_username == jira_username:
                    return config.telegram_username
            return None
        except Exception as e:
            LOGGER.error(f"Error getting telegram username for {jira_username}: {e}")
            return None
    
    def _get_urgency_emoji(self, urgency_level: str) -> str:
        """Get emoji for urgency level."""
        emoji_map = {
            "overdue": "🚨",
            "today": "🔥",
            "urgent": "⚡",
            "high": "⚠️",
            "medium": "📅",
            "low": "ℹ️",
        }
        return emoji_map.get(urgency_level, "📝")
    
    def _get_priority_emoji(self, priority: str) -> str:
        """Get emoji for priority level."""
        priority_lower = priority.lower()
        if "highest" in priority_lower or "critical" in priority_lower:
            return "🔴"
        elif "high" in priority_lower:
            return "🟠"
        elif "medium" in priority_lower:
            return "🟡"
        elif "low" in priority_lower:
            return "🟢"
        else:
            return "⚪"
    
    def _get_short_deadline_text(self, alert: DeadlineAlert) -> str:
        """Get short deadline text for group messages."""
        if alert.is_overdue:
            return f"⚠️ Overdue by {abs(alert.days_remaining)} days"
        elif alert.days_remaining == 0:
            return "🔥 Due today"
        elif alert.days_remaining == 1:
            return "⏰ Due tomorrow"
        else:
            return f"📅 Due in {alert.days_remaining} days"
