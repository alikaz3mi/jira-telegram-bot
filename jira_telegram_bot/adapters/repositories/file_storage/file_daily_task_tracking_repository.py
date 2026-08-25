"""File-based repository for daily task tracking."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from jira_telegram_bot import DEFAULT_PATH, LOGGER
from jira_telegram_bot.entities.daily_task_tracking.task_progress_report import (
    UserTaskProgressReport,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_tracking_repository_interface import (
    DailyTaskTrackingRepositoryInterface,
)


class FileDailyTaskTrackingRepository(DailyTaskTrackingRepositoryInterface):
    """File-based implementation of daily task tracking repository."""

    def __init__(self, storage_path: str = None):
        """Initialize the repository.

        Args:
            storage_path: Path to storage file
        """
        self.storage_path = storage_path or os.path.join(
            DEFAULT_PATH,
            "data",
            "storage",
            "daily_task_tracking.jsonl",
        )
        
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        if not os.path.exists(self.storage_path):
            Path(self.storage_path).touch()

    async def save_progress_report(
        self,
        report: UserTaskProgressReport,
    ) -> None:
        """Save a user task progress report.

        Args:
            report: Progress report to save
        """
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                report_dict = report.dict()
                
                if isinstance(report_dict.get("report_date"), datetime):
                    report_dict["report_date"] = report_dict["report_date"].isoformat()
                
                f.write(json.dumps(report_dict, ensure_ascii=False) + "\n")
                
            LOGGER.debug(f"Saved progress report: {report.report_id}")
            
        except Exception as e:
            LOGGER.error(f"Error saving progress report: {e}")
            raise

    async def get_progress_reports_by_user(
        self,
        user_jira_username: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[UserTaskProgressReport]:
        """Get progress reports for a user within a date range.

        Args:
            user_jira_username: User's Jira username
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of progress reports
        """
        try:
            reports = []
            
            if not os.path.exists(self.storage_path):
                return reports
            
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    report_dict = json.loads(line)
                    
                    if report_dict.get("user_jira_username") != user_jira_username:
                        continue
                    
                    if "report_date" in report_dict and isinstance(
                        report_dict["report_date"], str
                    ):
                        report_dict["report_date"] = datetime.fromisoformat(
                            report_dict["report_date"]
                        )
                    
                    report = UserTaskProgressReport(**report_dict)
                    
                    if start_date and report.report_date < start_date:
                        continue
                    if end_date and report.report_date > end_date:
                        continue
                    
                    reports.append(report)
            
            return reports
            
        except Exception as e:
            LOGGER.error(f"Error getting progress reports by user: {e}")
            return []

    async def get_progress_reports_by_issue(
        self,
        issue_key: str,
    ) -> List[UserTaskProgressReport]:
        """Get all progress reports for an issue.

        Args:
            issue_key: Jira issue key

        Returns:
            List of progress reports
        """
        try:
            reports = []
            
            if not os.path.exists(self.storage_path):
                return reports
            
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    report_dict = json.loads(line)
                    
                    if report_dict.get("issue_key") != issue_key:
                        continue
                    
                    if "report_date" in report_dict and isinstance(
                        report_dict["report_date"], str
                    ):
                        report_dict["report_date"] = datetime.fromisoformat(
                            report_dict["report_date"]
                        )
                    
                    report = UserTaskProgressReport(**report_dict)
                    reports.append(report)
            
            return reports
            
        except Exception as e:
            LOGGER.error(f"Error getting progress reports by issue: {e}")
            return []

    async def get_last_report_for_issue(
        self,
        issue_key: str,
        user_jira_username: str,
    ) -> Optional[UserTaskProgressReport]:
        """Get the most recent progress report for an issue and user.

        Args:
            issue_key: Jira issue key
            user_jira_username: User's Jira username

        Returns:
            Most recent progress report or None
        """
        try:
            reports = await self.get_progress_reports_by_issue(issue_key)
            
            user_reports = [
                r for r in reports if r.user_jira_username == user_jira_username
            ]
            
            if not user_reports:
                return None
            
            return max(user_reports, key=lambda r: r.report_date)
            
        except Exception as e:
            LOGGER.error(f"Error getting last report: {e}")
            return None
