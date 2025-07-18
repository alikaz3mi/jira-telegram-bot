"""Jira data service implementation."""
from __future__ import annotations

from datetime import datetime
from typing import List

import pandas as pd
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import LinkedIssue
from jira_telegram_bot.entities.jira_report import WorklogEntry
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface


class JiraDataService(JiraDataServiceInterface):
    """Service for fetching comprehensive data from Jira."""

    def __init__(self, task_manager_repository: TaskManagerRepositoryInterface) -> None:
        """Initialize the service with Jira repository.
        
        Args:
            task_manager_repository: Injected Jira repository interface.
        """
        self._jira_repository = task_manager_repository

    async def fetch_project_issues(self, project_key: str) -> List[JiraIssueDetail]:
        """Fetch all issues for a project with comprehensive details.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            List of detailed issue information including worklogs and links.
        """
        LOGGER.info(f"Fetching issues for project: {project_key}")
        
        start_at = 0
        max_results = 100
        issues = []

        while True:
            batch = self._jira_repository.search_issues(
                f"project = {project_key}",
                start_at=start_at,
                max_results=max_results,
                expand="changelog,worklog,issuelinks"
            )
            if not batch:
                break
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results

        LOGGER.info(f"Found {len(issues)} issues for project {project_key}")
        
        epics = self._extract_epics(issues)
        detailed_issues = []

        for issue in tqdm(issues, desc=f"Processing {project_key} issues"):
            if issue.fields.issuetype.name == "Epic":
                continue
                
            detailed_issue = await self._convert_to_detailed_issue(issue, epics)
            detailed_issues.append(detailed_issue)

        return detailed_issues

    async def fetch_issue_details(self, issue_key: str) -> JiraIssueDetail:
        """Fetch detailed information for a specific issue.
        
        Args:
            issue_key: The Jira issue key.
            
        Returns:
            Detailed issue information.
        """
        issue = self._jira_repository.get_issue_with_expand(
            issue_key, 
            "changelog,worklog,issuelinks"
        )
        
        epics = {}
        if hasattr(issue.fields, 'customfield_10100') and issue.fields.customfield_10100:
            epic_issue = self._jira_repository.get_issue(issue.fields.customfield_10100)
            if epic_issue:
                epics[epic_issue.key] = epic_issue.fields.summary

        return await self._convert_to_detailed_issue(issue, epics)

    def _extract_epics(self, issues) -> dict:
        """Extract epic information from issues list.
        
        Args:
            issues: List of Jira issues.
            
        Returns:
            Dictionary mapping epic keys to epic names.
        """
        epics = {}
        for issue in issues:
            if issue.fields.issuetype.name == "Epic":
                epics[issue.key] = issue.fields.summary
        return epics

    async def _convert_to_detailed_issue(
        self, 
        issue, 
        epics: dict
    ) -> JiraIssueDetail:
        """Convert Jira issue to detailed issue entity.
        
        Args:
            issue: Jira issue object.
            epics: Dictionary of epic keys to names.
            
        Returns:
            Detailed issue information.
        """
        comments_text = self._extract_comments(issue)
        sprint_info = self._extract_sprint_info(issue)
        worklog_entries = self._extract_worklog_entries(issue)
        linked_issues = self._extract_linked_issues(issue)
        
        story_points = getattr(issue.fields, "customfield_10106", None)
        
        fix_versions = issue.fields.fixVersions
        release_list = [fv.name for fv in fix_versions] if fix_versions else []
        
        timetracking = getattr(issue.fields, "timetracking", None)
        if timetracking:
            original_estimate = getattr(timetracking, "originalEstimate", None)
            remaining_estimate = getattr(timetracking, "remainingEstimate", None)
        else:
            original_estimate = None
            remaining_estimate = None

        return JiraIssueDetail(
            key=issue.key,
            summary=issue.fields.summary,
            description=issue.fields.description or "",
            epic_name=epics.get(getattr(issue.fields, 'customfield_10100', None)),
            comments="\n".join(comments_text),
            task_type=issue.fields.issuetype.name,
            assignee=(
                issue.fields.assignee.displayName if issue.fields.assignee else None
            ),
            reporter=issue.fields.reporter.displayName,
            priority=(issue.fields.priority.name if issue.fields.priority else None),
            status=issue.fields.status.name,
            created_at=self._parse_datetime(issue.fields.created),
            updated_at=self._parse_datetime(issue.fields.updated),
            resolved_at=self._parse_datetime(issue.fields.resolutiondate),
            target_start=self._parse_datetime(
                getattr(issue.fields, "customfield_10109", None)
            ),
            target_end=self._parse_datetime(
                getattr(issue.fields, "customfield_10110", None)
            ),
            due_date=self._parse_datetime(issue.fields.duedate),
            project=issue.fields.project.key,
            story_points=story_points,
            components=(
                [c.name for c in issue.fields.components]
                if issue.fields.components
                else []
            ),
            labels=issue.fields.labels if issue.fields.labels else [],
            last_sprint=sprint_info["name"],
            sprint_repeats=sprint_info["count"],
            release=release_list,
            original_estimate=original_estimate,
            remaining_estimate=remaining_estimate,
            worklog_entries=worklog_entries,
            linked_issues=linked_issues,
        )

    def _extract_comments(self, issue) -> List[str]:
        """Extract comments from issue.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            List of comment strings.
        """
        comments_text = []
        if issue.fields.comment:
            for comment in issue.fields.comment.comments:
                commenter = comment.author.displayName
                if commenter != issue.fields.reporter.displayName:
                    comments_text.append(f"{commenter}: {comment.body}")
        return comments_text

    def _extract_sprint_info(self, issue) -> dict:
        """Extract sprint information from issue.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            Dictionary with sprint name and count.
        """
        sprint_field = getattr(issue.fields, "customfield_10104", None)
        if sprint_field and len(sprint_field) > 0:
            sprint_str = str(sprint_field[-1])
            name_start = sprint_str.find("name=") + 5
            name_end = sprint_str.find(",startDate")
            last_sprint_name = sprint_str[name_start:name_end]
        else:
            last_sprint_name = "Backlog"
        
        sprint_count = len(sprint_field) if sprint_field else 0
        
        return {"name": last_sprint_name, "count": sprint_count}

    def _extract_worklog_entries(self, issue) -> List[WorklogEntry]:
        """Extract worklog entries from issue.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            List of worklog entries.
        """
        worklog_entries = []
        
        if hasattr(issue.fields, 'worklog') and issue.fields.worklog:
            for worklog in issue.fields.worklog.worklogs:
                entry = WorklogEntry(
                    id=worklog.id,
                    author=worklog.author.displayName,
                    time_spent=worklog.timeSpent,
                    time_spent_seconds=worklog.timeSpentSeconds,
                    created=self._parse_datetime(worklog.created),
                    updated=self._parse_datetime(worklog.updated),
                    started=self._parse_datetime(worklog.started),
                    comment=getattr(worklog, 'comment', None),
                )
                worklog_entries.append(entry)
        
        return worklog_entries

    def _extract_linked_issues(self, issue) -> List[LinkedIssue]:
        """Extract linked issues from issue.
        
        Args:
            issue: Jira issue object.
            
        Returns:
            List of linked issues.
        """
        linked_issues = []
        
        if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks:
            for link in issue.fields.issuelinks:
                if hasattr(link, 'outwardIssue'):
                    linked_issue = link.outwardIssue
                    relationship = link.type.outward
                elif hasattr(link, 'inwardIssue'):
                    linked_issue = link.inwardIssue
                    relationship = link.type.inward
                else:
                    continue
                
                linked = LinkedIssue(
                    key=linked_issue.key,
                    summary=linked_issue.fields.summary,
                    status=linked_issue.fields.status.name,
                    issue_type=linked_issue.fields.issuetype.name,
                    relationship=relationship,
                )
                linked_issues.append(linked)
        
        return linked_issues

    def _parse_datetime(self, date_str) -> datetime:
        """Parse datetime string to datetime object.
        
        Args:
            date_str: Date string from Jira.
            
        Returns:
            Parsed datetime object or None.
        """
        if not date_str:
            return None
        
        try:
            parsed_dt = pd.to_datetime(date_str)
            return parsed_dt.to_pydatetime() if hasattr(parsed_dt, 'to_pydatetime') else parsed_dt
        except Exception:
            return None
