from __future__ import annotations

import json
import os
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
from jira_telegram_bot.use_cases.interfaces.notification_log_repository_interface import NotificationLogRepositoryInterface


class FileNotificationLogRepository(NotificationLogRepositoryInterface):
    """File-based implementation of notification log repository using JSON Lines format."""
    
    def __init__(self, log_file_path: str = "data/notifier_log.jsonl"):
        self.log_file_path = Path(log_file_path)
        self._ensure_log_file_exists()
    
    def _ensure_log_file_exists(self) -> None:
        """Ensure the log file and its directory exist."""
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_file_path.exists():
            self.log_file_path.touch()
    
    async def has_notification_been_sent(
        self,
        issue_key: str,
        chat_id: int,
        notification_date: datetime,
    ) -> bool:
        """Check if a notification has already been sent for an issue to a chat on a specific date."""
        try:
            target_date = notification_date.date().isoformat()
            
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        log_entry = json.loads(line.strip())
                        
                        if (
                            log_entry.get("issue_key") == issue_key and
                            log_entry.get("chat_id") == chat_id and
                            log_entry.get("notification_date") == target_date
                        ):
                            return True
                    except json.JSONDecodeError as e:
                        LOGGER.warning(f"Invalid JSON in log file: {e}")
                        continue
            
            return False
            
        except FileNotFoundError:
            return False
        except Exception as e:
            LOGGER.error(f"Error checking notification log: {e}")
            return False
    
    async def log_notification_sent(
        self,
        issue_key: str,
        chat_id: int,
        notification_date: datetime,
        alert: DeadlineAlert,
    ) -> None:
        """Log that a notification has been sent."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "issue_key": issue_key,
                "chat_id": chat_id,
                "notification_date": notification_date.date().isoformat(),
                "alert_data": {
                    "summary": alert.summary,
                    "assignee": alert.assignee,
                    "days_remaining": alert.days_remaining,
                    "urgency_level": alert.urgency_level,
                    "project_key": alert.project_key,
                    "status": alert.status,
                    "priority": alert.priority,
                },
            }
            
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            LOGGER.debug(f"Logged notification: {issue_key} -> {chat_id}")
            
        except Exception as e:
            LOGGER.error(f"Error logging notification: {e}")
            raise
    
    async def get_notification_history(
        self,
        issue_key: Optional[str] = None,
        chat_id: Optional[int] = None,
        days_back: int = 30,
    ) -> List[dict]:
        """Get notification history for debugging purposes."""
        try:
            history = []
            cutoff_date = (datetime.now() - timedelta(days=days_back)).date()
            
            if not self.log_file_path.exists():
                return history
            
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # Parse notification date
                        notification_date_str = log_entry.get("notification_date")
                        if notification_date_str:
                            notification_date = datetime.fromisoformat(notification_date_str).date()
                            if notification_date < cutoff_date:
                                continue
                        
                        # Apply filters
                        if issue_key and log_entry.get("issue_key") != issue_key:
                            continue
                        
                        if chat_id and log_entry.get("chat_id") != chat_id:
                            continue
                        
                        history.append(log_entry)
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        LOGGER.warning(f"Invalid log entry: {e}")
                        continue
            
            # Sort by timestamp (newest first)
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return history
            
        except Exception as e:
            LOGGER.error(f"Error getting notification history: {e}")
            return []
    
    async def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """Clean up old notification logs to prevent file growth."""
        try:
            if not self.log_file_path.exists():
                return 0
            
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date()
            temp_file = self.log_file_path.with_suffix('.tmp')
            entries_removed = 0
            entries_kept = 0
            
            with open(self.log_file_path, 'r', encoding='utf-8') as input_file:
                with open(temp_file, 'w', encoding='utf-8') as output_file:
                    for line in input_file:
                        if not line.strip():
                            continue
                        
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # Check if entry should be kept
                            notification_date_str = log_entry.get("notification_date")
                            if notification_date_str:
                                notification_date = datetime.fromisoformat(notification_date_str).date()
                                if notification_date >= cutoff_date:
                                    output_file.write(line)
                                    entries_kept += 1
                                else:
                                    entries_removed += 1
                            else:
                                # Keep entries without valid dates
                                output_file.write(line)
                                entries_kept += 1
                            
                        except (json.JSONDecodeError, ValueError) as e:
                            LOGGER.warning(f"Invalid log entry during cleanup: {e}")
                            # Keep invalid entries to avoid data loss
                            output_file.write(line)
                            entries_kept += 1
            
            # Replace original file with cleaned version
            if temp_file.exists():
                temp_file.replace(self.log_file_path)
            
            LOGGER.info(f"Log cleanup completed: {entries_removed} entries removed, {entries_kept} entries kept")
            return entries_removed
            
        except Exception as e:
            LOGGER.error(f"Error during log cleanup: {e}")
            # Clean up temp file if it exists
            temp_file = self.log_file_path.with_suffix('.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            return 0
