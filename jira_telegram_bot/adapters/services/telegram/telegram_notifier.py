from __future__ import annotations

import asyncio
import textwrap
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
        self.base_url = f"https://api.telegram.org/bot{telegram_settings.HOOK_TOKEN}"
    
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
            
            messages = await self._format_group_messages(alerts, mention_users)
            
            # Send all messages
            all_sent = True
            for i, message in enumerate(messages):
                success = await self._send_message(chat_id, message)
                if not success:
                    all_sent = False
                    LOGGER.error(f"Failed to send group notification part {i+1}/{len(messages)} to {chat_id}")
                
                # Small delay between messages to avoid rate limiting
                if i < len(messages) - 1:
                    await asyncio.sleep(0.5)
            
            return all_sent
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
        
        # Build mention text
        mention_text = ""
        if include_mention and telegram_username:
            mention_text = f" @{telegram_username}"
        
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
        
        # Build priority text
        priority_text = ""
        if alert.priority:
            priority_emoji = self._get_priority_emoji(alert.priority)
            priority_text = f"\n<b>🔸 Priority:</b> <code>{alert.priority}</code> {priority_emoji}"
        
        # Build assignee/reporter text based on review status
        assignee_text = ""
        if alert.is_in_review:
            if alert.reporter:
                assignee_text = f"\n<b>🔸 Reporter:</b> <code>{alert.reporter}</code>"
            if alert.assignee:
                assignee_text += f"\n<b>🔸 Assignee:</b> <code>{alert.assignee}</code>"
        elif alert.assignee:
            assignee_text = f"\n<b>🔸 Assignee:</b> <code>{alert.assignee}</code>"
        
        message = f"""<b>{urgency_emoji} Deadline Alert{mention_text}</b>

<b>🔸 Issue:</b> <code>{alert.issue_key}</code>
<b>🔹 Project:</b> <code>{alert.project_key}</code>
<b>🔹 Status:</b> <code>{alert.status}</code>
<b>🔹 Deadline:</b> <code>{deadline_text}</code>{assignee_text}{priority_text}

<b>📄 Summary:</b>
<pre>{alert.summary}</pre>

<a href="{alert.issue_url}">🔗 View Issue in Jira</a>"""
        
        return message
    
    async def _format_group_messages(
        self,
        alerts: List[DeadlineAlert],
        mention_users: bool = True,
    ) -> List[str]:
        """Format multiple alerts for group messages, splitting if needed."""
        if not alerts:
            return [""]
        
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
        
        # Group by urgency level
        urgency_groups = {}
        for alert in sorted_alerts:
            urgency_groups.setdefault(alert.urgency_level, []).append(alert)
        
        messages = []
        current_message_parts = []
        max_length = 4000  # Leave some buffer below Telegram's 4096 limit
        message_count = 1
        
        # Start first message with header
        header = f"<b>🚨 Team Deadline Report ({len(alerts)} issues)</b>"
        current_message_parts = [header, ""]
        
        for urgency_level in ["overdue", "today", "urgent", "high"]:
            if urgency_level not in urgency_groups:
                continue
            
            group_alerts = urgency_groups[urgency_level]
            urgency_emoji = self._get_urgency_emoji(urgency_level)
            
            group_header = f"<b>{urgency_emoji} {urgency_level.upper()} ({len(group_alerts)} issues)</b>"
            
            # Check if we need to start a new message
            current_length = len("\n".join(current_message_parts))
            if current_length + len(group_header) > max_length and current_message_parts:
                # Finalize current message
                messages.append("\n".join(current_message_parts))
                message_count += 1
                
                # Start new message
                new_header = f"<b>🚨 Team Deadline Report (Part {message_count})</b>"
                current_message_parts = [new_header, "", group_header]
            else:
                current_message_parts.append(group_header)
            
            for alert in group_alerts:
                # Get telegram username for mention (reporter for review status, assignee otherwise)
                telegram_username = None
                person_to_mention = alert.reporter if alert.is_in_review else alert.assignee
                if mention_users and person_to_mention:
                    telegram_username = await self._get_telegram_username(person_to_mention)
                
                mention_text = f" @{telegram_username}" if telegram_username else ""
                review_indicator = " 🔍 (In Review)" if alert.is_in_review else ""
                deadline_text = self._get_short_deadline_text(alert)
                summary_text = alert.summary[:40] + ('...' if len(alert.summary) > 40 else '')
                
                issue_line = f"• <a href=\"{alert.issue_url}\">{alert.issue_key}</a>: <code>{summary_text}</code>{review_indicator}"
                deadline_line = f"  {deadline_text}{mention_text}"
                
                # Check if adding this issue would exceed the limit
                issue_text = f"{issue_line}\n{deadline_line}\n"
                current_length = len("\n".join(current_message_parts))
                
                if current_length + len(issue_text) > max_length:
                    # Finalize current message
                    current_message_parts.append("")  # Add spacing before split
                    messages.append("\n".join(current_message_parts))
                    message_count += 1
                    
                    # Start new message
                    new_header = f"<b>🚨 Team Deadline Report (Part {message_count})</b>"
                    current_message_parts = [new_header, "", group_header, issue_line, deadline_line, ""]
                else:
                    current_message_parts.extend([issue_line, deadline_line, ""])
            
            current_message_parts.append("")
        
        # Add the final message if there's content
        if current_message_parts and len(current_message_parts) > 2:  # More than just header
            messages.append("\n".join(current_message_parts))
        
        return messages if messages else ["<b>🚨 No deadline alerts found</b>"]

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
        
        # Group by urgency level
        urgency_groups = {}
        for alert in sorted_alerts:
            urgency_groups.setdefault(alert.urgency_level, []).append(alert)
        
        # Build the message with length control
        message_parts = [f"<b>🚨 Team Deadline Report ({len(alerts)} issues)</b>\n"]
        total_issues_added = 0
        max_issues = 100  # Limit to prevent message being too long
        
        for urgency_level in ["overdue", "today", "urgent", "high"]:
            if urgency_level not in urgency_groups:
                continue
            
            group_alerts = urgency_groups[urgency_level]
            urgency_emoji = self._get_urgency_emoji(urgency_level)
            
            # Check if we have room for this urgency group
            if total_issues_added >= max_issues:
                break
                
            message_parts.append(f"<b>{urgency_emoji} {urgency_level.upper()} ({len(group_alerts)} issues)</b>")
            
            for alert in group_alerts:
                if total_issues_added >= max_issues:
                    break
                    
                # Get telegram username for mention (reporter for review status, assignee otherwise)
                telegram_username = None
                person_to_mention = alert.reporter if alert.is_in_review else alert.assignee
                if mention_users and person_to_mention:
                    telegram_username = await self._get_telegram_username(person_to_mention)
                
                mention_text = f" @{telegram_username}" if telegram_username else ""
                review_indicator = " 🔍 (In Review)" if alert.is_in_review else ""
                deadline_text = self._get_short_deadline_text(alert)
                summary_text = alert.summary[:40] + ('...' if len(alert.summary) > 40 else '')
                
                issue_line = f"• <a href=\"{alert.issue_url}\">{alert.issue_key}</a>: <code>{summary_text}</code>{review_indicator}"
                deadline_line = f"  {deadline_text}{mention_text}"
                
                message_parts.extend([issue_line, deadline_line, ""])
                total_issues_added += 1
            
            message_parts.append("")
        
        # Add truncation notice if there are more issues
        if len(alerts) > max_issues:
            remaining = len(alerts) - max_issues
            message_parts.append(f"<i>... and {remaining} more issues</i>")
        
        return "\n".join(message_parts)
    
    async def _send_message(self, chat_id: int, text: str) -> bool:
        """Send a message via Telegram API."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
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
