"""Use case for calculating and backfilling actual start/end dates for Jira issues."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import (
    JiraReportRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class CalculateActualDatesUseCase:
    """Calculate actual start and end dates for Jira issues.
    
    Actual Start Date: Earliest of:
        - First worklog timestamp
        - First status change to "In Progress"
        
    Actual End Date: Latest of:
        - Last status change to "Done"
    """

    def __init__(
        self,
        jira_repository: TaskManagerRepositoryInterface,
        report_repository: JiraReportRepositoryInterface,
    ) -> None:
        """Initialize the use case.
        
        Args:
            jira_repository: Repository for accessing Jira data.
            report_repository: Repository for storing calculated dates.
        """
        self._jira_repository = jira_repository
        self._report_repository = report_repository

    async def calculate_and_update_actual_dates(
        self,
        project_keys: List[str],
    ) -> Dict[str, int]:
        """Calculate actual dates for all issues in specified projects.
        
        Args:
            project_keys: List of Jira project keys to process.
            
        Returns:
            Dictionary with statistics (processed, updated, skipped, failed).
        """
        total_processed = 0
        total_updated = 0
        total_skipped = 0
        total_failed = 0

        for project_key in project_keys:
            LOGGER.info(f"Processing project: {project_key}")
            
            try:
                # Fetch all issues for the project
                jql = f"project = {project_key}"
                issues = self._jira_repository.search_issues(
                    jql=jql,
                    max_results=1000,
                    expand="changelog,worklog"
                )
                
                LOGGER.info(f"Found {len(issues)} issues in {project_key}")
                
                for issue in issues:
                    try:
                        result = await self._process_issue(issue)
                        total_processed += 1
                        
                        if result == "updated":
                            total_updated += 1
                        elif result == "skipped":
                            total_skipped += 1
                            
                    except Exception as e:
                        LOGGER.error(f"Failed to process issue {issue.key}: {e}")
                        total_failed += 1
                        
            except Exception as e:
                LOGGER.error(f"Failed to fetch issues for {project_key}: {e}")
                total_failed += 1

        LOGGER.info(
            f"Completed: {total_processed} processed, "
            f"{total_updated} updated, {total_skipped} skipped, "
            f"{total_failed} failed"
        )

        return {
            "processed": total_processed,
            "updated": total_updated,
            "skipped": total_skipped,
            "failed": total_failed,
        }

    async def _process_issue(self, issue) -> str:
        """Process a single issue to calculate actual dates.
        
        Args:
            issue: Jira issue object with expanded changelog and worklog.
            
        Returns:
            Status string: "updated", "skipped", or "failed".
        """
        # Get existing values from Jira custom fields
        existing_actual_start = getattr(
            issue.fields,
            self._jira_repository.jira_actual_start_id,
            None
        )
        existing_actual_end = getattr(
            issue.fields,
            self._jira_repository.jira_actual_end_id,
            None
        )

        # Calculate actual start date
        calculated_start = None
        if not existing_actual_start:
            calculated_start = self._calculate_actual_start(issue)
            
        # Calculate actual end date
        calculated_end = None
        if not existing_actual_end:
            calculated_end = self._calculate_actual_end(issue)

        # If both are already set, skip
        if existing_actual_start and existing_actual_end:
            LOGGER.debug(f"Issue {issue.key} already has both actual dates set")
            return "skipped"

        # If nothing to update, skip
        if not calculated_start and not calculated_end:
            LOGGER.debug(f"Issue {issue.key} has no calculable actual dates")
            return "skipped"

        # Update Jira fields
        fields_to_update = {}
        
        if calculated_start:
            fields_to_update[self._jira_repository.jira_actual_start_id] = (
                calculated_start.strftime("%Y-%m-%d")
            )
            LOGGER.info(f"Setting actual_start for {issue.key}: {calculated_start}")
            
        if calculated_end:
            fields_to_update[self._jira_repository.jira_actual_end_id] = (
                calculated_end.strftime("%Y-%m-%d")
            )
            LOGGER.info(f"Setting actual_end for {issue.key}: {calculated_end}")

        if fields_to_update:
            try:
                self._jira_repository.update_issue_from_fields(
                    issue_key=issue.key,
                    fields=fields_to_update
                )
                LOGGER.info(f"Updated {issue.key} with calculated actual dates")
                return "updated"
            except Exception as e:
                LOGGER.error(f"Failed to update Jira fields for {issue.key}: {e}")
                return "failed"

        return "skipped"

    def _calculate_actual_start(self, issue) -> Optional[datetime]:
        """Calculate actual start date from worklogs and status changes.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            Calculated actual start datetime or None.
        """
        candidates = []

        # Check first worklog
        if hasattr(issue.fields, 'worklog') and issue.fields.worklog:
            worklogs = issue.fields.worklog.worklogs
            if worklogs:
                # Find earliest worklog start time
                earliest_worklog = min(
                    worklogs,
                    key=lambda w: self._parse_datetime_safe(w.started)
                )
                worklog_start = self._parse_datetime_safe(earliest_worklog.started)
                if worklog_start:
                    candidates.append(worklog_start)
                    LOGGER.debug(
                        f"Issue {issue.key} first worklog: {worklog_start}"
                    )

        # Check status change to "In Progress"
        if hasattr(issue, 'changelog') and issue.changelog:
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        to_status = item.toString.lower() if hasattr(item, 'toString') else ''
                        if 'in progress' in to_status or 'progress' in to_status:
                            changed_at = self._parse_datetime_safe(history.created)
                            if changed_at:
                                candidates.append(changed_at)
                                LOGGER.debug(
                                    f"Issue {issue.key} moved to In Progress: {changed_at}"
                                )
                                break  # Take first occurrence

        # Return earliest date
        if candidates:
            earliest = min(candidates)
            LOGGER.info(f"Calculated actual start for {issue.key}: {earliest}")
            return earliest

        return None

    def _calculate_actual_end(self, issue) -> Optional[datetime]:
        """Calculate actual end date from status changes to Done.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            Calculated actual end datetime or None.
        """
        done_timestamps = []

        # Check status changes to "Done"
        if hasattr(issue, 'changelog') and issue.changelog:
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        to_status = item.toString.lower() if hasattr(item, 'toString') else ''
                        if 'done' in to_status:
                            changed_at = self._parse_datetime_safe(history.created)
                            if changed_at:
                                done_timestamps.append(changed_at)
                                LOGGER.debug(
                                    f"Issue {issue.key} moved to Done: {changed_at}"
                                )

        # Return latest Done timestamp
        if done_timestamps:
            latest = max(done_timestamps)
            LOGGER.info(f"Calculated actual end for {issue.key}: {latest}")
            return latest

        return None

    def _parse_datetime_safe(self, date_input) -> Optional[datetime]:
        """Safely parse datetime from various formats.
        
        Args:
            date_input: Date string or datetime object.
            
        Returns:
            Parsed datetime or None if parsing fails.
        """
        if not date_input:
            return None

        if isinstance(date_input, datetime):
            return date_input

        try:
            import pandas as pd
            parsed = pd.to_datetime(date_input)
            return parsed.to_pydatetime() if hasattr(parsed, 'to_pydatetime') else parsed
        except Exception:
            return None
