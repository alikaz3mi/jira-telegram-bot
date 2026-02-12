from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSheetRow
from jira_telegram_bot.entities.synth_pm.constants import JIRA_TO_GOOGLE_SHEET_STATUS
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class FetchBugImprovementDataUseCase:
    """Use case for fetching bug and improvement data from Jira."""

    def __init__(
        self,
        task_manager: TaskManagerRepositoryInterface,
        jira_base_url: str,
        user_config: UserConfigInterface,
    ):
        self.task_manager = task_manager
        self.jira_base_url = jira_base_url
        self.user_config = user_config

    def execute(
        self,
        board_key: str,
        days_back: Optional[int] = None,
    ) -> List[BugImprovementSheetRow]:
        """Fetch bug and improvement issues from Jira.

        Args:
            board_key: Jira board/project key.
            days_back: Number of days to look back for updated issues.
                      If None, fetch all bugs and improvements.

        Returns:
            List of BugImprovementSheetRow entities.
        """
        jql = self._build_jql(board_key, days_back)
        LOGGER.info(f"Fetching issues with JQL: {jql}")

        issues = self.task_manager.search_for_issues(jql)
        LOGGER.info(f"Found {len(issues)} bugs/improvements")

        rows = []
        for idx, issue in enumerate(issues, start=1):
            row = self._convert_issue_to_row(issue, idx)
            rows.append(row)

        return rows

    def _build_jql(self, board_key: str, days_back: Optional[int]) -> str:
        """Build JQL query for fetching bugs and improvements.

        Args:
            board_key: Jira board/project key.
            days_back: Number of days to look back.

        Returns:
            JQL query string.
        """
        jql = f'project = "{board_key}" AND issuetype in (Bug, Improvement)'

        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            date_str = cutoff_date.strftime("%Y-%m-%d")
            jql += f' AND updated >= "{date_str}"'
            LOGGER.info(f"Filtering by updated >= {date_str} ({days_back} days back from {datetime.now().strftime('%Y-%m-%d')})")

        jql += " ORDER BY created DESC"
        return jql

    def _convert_issue_to_row(
        self,
        issue: Issue,
        row_number: int,
    ) -> BugImprovementSheetRow:
        """Convert Jira issue to BugImprovementSheetRow.

        Args:
            issue: Jira issue object.
            row_number: Row number for the sheet.

        Returns:
            BugImprovementSheetRow entity.
        """
        epic_name = self._get_epic_name(issue)
        linked_story = self._get_linked_story(issue)
        departments = self._get_departments(issue)
        total_hours, involved_people = self._get_subtask_data(issue)
        implementation_start = self._get_implementation_start_date(issue)
        initial_delivery_time = self._get_initial_delivery_time(issue)
        status = self._map_jira_status_to_sheet(issue.fields.status.name)
        reporter = self._get_reporter_name(issue)
        board_name = self._get_board_name(issue)
        involved_user_from_label = self._get_user_id_from_labels(issue)

        return BugImprovementSheetRow(
            row_number=row_number,
            task_title=issue.fields.summary,
            description=issue.fields.description or "",
            reporter=reporter,
            board_name=board_name,
            involved_people=involved_people,
            sprint=self._get_sprint_name(issue),
            epic_name=epic_name,
            linked_story=linked_story,
            priority=getattr(issue.fields.priority, "name", None),
            status=status,
            departments=departments,
            release=self._get_release(issue),
            total_hours=total_hours,
            created_date=self._parse_jira_datetime(issue.fields.created),
            implementation_start_date=implementation_start,
            deadline=self._parse_jira_datetime(getattr(issue.fields, "duedate", None)),
            involved_user_from_label=involved_user_from_label,
            initial_delivery_time=initial_delivery_time,
            issue_key=issue.key,
        )

    def _get_epic_name(self, issue: Issue) -> Optional[str]:
        """Get epic name for the issue."""
        try:
            epic_link = getattr(
                issue.fields,
                self.task_manager.jira_epic_link_id,
                None,
            )
            if epic_link:
                epic_issue = self.task_manager.get_issue(epic_link)
                if epic_issue:
                    return getattr(
                        epic_issue.fields,
                        self.task_manager.jira_epic_name_id,
                        None,
                    )
        except Exception as e:
            LOGGER.error(f"Error getting epic name for {issue.key}: {e}")
        return None

    def _get_linked_story(self, issue: Issue) -> Optional[str]:
        """Get linked story key from issue links."""
        try:
            if hasattr(issue.fields, "issuelinks"):
                for link in issue.fields.issuelinks:
                    if hasattr(link, "outwardIssue"):
                        linked = link.outwardIssue
                        if linked.fields.issuetype.name == "Story":
                            return linked.key
                    elif hasattr(link, "inwardIssue"):
                        linked = link.inwardIssue
                        if linked.fields.issuetype.name == "Story":
                            return linked.key
        except Exception as e:
            LOGGER.error(f"Error getting linked story for {issue.key}: {e}")
        return None

    def _get_departments(self, issue: Issue) -> List[str]:
        """Get departments (components) for the issue.

        Maps component names to standardized format:
        - 'Front-end' -> 'Frontend'
        """
        try:
            if hasattr(issue.fields, "components") and issue.fields.components:
                departments = []
                for comp in issue.fields.components:
                    dept_name = comp.name
                    if dept_name == "Front-end":
                        dept_name = "Frontend"
                    departments.append(dept_name)
                return departments
        except Exception as e:
            LOGGER.error(f"Error getting departments for {issue.key}: {e}")
        return []

    def _get_subtask_data(self, issue: Issue) -> tuple[float, List[str]]:
        """Get total hours and involved people from subtasks.

        Args:
            issue: Jira issue object.

        Returns:
            Tuple of (total_hours, list_of_assignees).
        """
        total_hours = 0.0
        involved_people = set()

        try:
            original_estimate = self._get_original_estimate_hours(issue)
            total_hours += original_estimate

            if hasattr(issue.fields, "subtasks") and issue.fields.subtasks:
                for subtask in issue.fields.subtasks:
                    full_subtask = self.task_manager.get_issue(subtask.key)
                    if full_subtask:
                        subtask_estimate = self._get_original_estimate_hours(full_subtask)
                        total_hours += subtask_estimate

                        if hasattr(full_subtask.fields, "assignee") and full_subtask.fields.assignee:
                            assignee_name = self._get_google_sheet_name(
                                full_subtask.fields.assignee.name,
                            )
                            if assignee_name:
                                involved_people.add(assignee_name)

            if hasattr(issue.fields, "assignee") and issue.fields.assignee:
                assignee_name = self._get_google_sheet_name(issue.fields.assignee.name)
                if assignee_name:
                    involved_people.add(assignee_name)

        except Exception as e:
            LOGGER.error(f"Error getting subtask data for {issue.key}: {e}")

        return total_hours, sorted(list(involved_people))

    def _get_original_estimate_hours(self, issue: Issue) -> float:
        """Get original time estimate on an issue in hours.

        Args:
            issue: Jira issue object.

        Returns:
            Original time estimate in hours.
        """
        try:
            time_estimate_seconds = getattr(
                issue.fields,
                "timeoriginalestimate",
                0,
            ) or 0
            return time_estimate_seconds / 3600.0
        except Exception as e:
            LOGGER.error(f"Error getting original estimate for {issue.key}: {e}")
            return 0.0

    def _get_release(self, issue: Issue) -> Optional[str]:
        """Get release/fix version for the issue."""
        try:
            if hasattr(issue.fields, "fixVersions") and issue.fields.fixVersions:
                return issue.fields.fixVersions[0].name
        except Exception as e:
            LOGGER.error(f"Error getting release for {issue.key}: {e}")
        return None

    def _get_sprint_name(self, issue: Issue) -> Optional[str]:
        """Get sprint name formatted as '55: 07-26 to 08-02'.

        Extracts sprint number and date range from sprint goal or name.
        Expected format in goal: dates like '07-26 to 08-02'.
        """
        try:
            sprints = getattr(
                issue.fields,
                self.task_manager.jira_sprint_id,
                None,
            )
            if sprints and len(sprints) > 0:
                last_sprint = sprints[-1]
                sprint_name = None
                sprint_goal = None
                sprint_id = None

                if isinstance(last_sprint, str):
                    import re

                    name_match = re.search(r"name=([^,]+)", last_sprint)
                    goal_match = re.search(r"goal=([^,]+)", last_sprint)
                    id_match = re.search(r"id=(\d+)", last_sprint)
                    
                    if name_match:
                        sprint_name = name_match.group(1)
                    if goal_match:
                        sprint_goal = goal_match.group(1)
                    if id_match:
                        sprint_id = id_match.group(1)
                else:
                    sprint_name = getattr(last_sprint, "name", None)
                    sprint_goal = getattr(last_sprint, "goal", None)
                    sprint_id = getattr(last_sprint, "id", None)

                sprint_number = self._extract_sprint_number(sprint_name, sprint_id)
                date_range = self._extract_date_range(sprint_goal)

                if sprint_number and date_range:
                    return f"{sprint_number}: {date_range}"
                elif sprint_number:
                    return sprint_number
                elif sprint_name:
                    return sprint_name

        except Exception as e:
            LOGGER.error(f"Error getting sprint name for {issue.key}: {e}")
        return None

    def _extract_sprint_number(
        self,
        sprint_name: Optional[str],
        sprint_id: Optional[str],
    ) -> Optional[str]:
        """Extract sprint number from name or ID.

        Args:
            sprint_name: Sprint name (e.g., 'Sprint 55', 'Project Sprint 55').
            sprint_id: Sprint ID.

        Returns:
            Sprint number as string or None.
        """
        import re

        if sprint_name:
            match = re.search(r"(\d+)", sprint_name)
            if match:
                return match.group(1)
        
        if sprint_id:
            return sprint_id
        
        return None

    def _extract_date_range(self, sprint_goal: Optional[str]) -> Optional[str]:
        """Extract date range from sprint goal.

        Args:
            sprint_goal: Sprint goal text containing dates.

        Returns:
            Date range in format 'MM-DD to MM-DD' or None.
        """
        import re

        if not sprint_goal:
            return None

        date_pattern = r"(\d{2}-\d{2})\s+to\s+(\d{2}-\d{2})"
        match = re.search(date_pattern, sprint_goal)
        if match:
            return f"{match.group(1)} to {match.group(2)}"

        alt_pattern = r"(\d{1,2}/\d{1,2})\s+to\s+(\d{1,2}/\d{1,2})"
        match = re.search(alt_pattern, sprint_goal)
        if match:
            start = match.group(1).replace("/", "-").zfill(5)
            end = match.group(2).replace("/", "-").zfill(5)
            return f"{start} to {end}"

        return None

    def _get_implementation_start_date(self, issue: Issue) -> Optional[datetime]:
        """Get implementation start date from changelog.

        Args:
            issue: Jira issue object.

        Returns:
            Datetime when issue was moved to 'In Progress' or similar.
        """
        try:
            issue_with_changelog = self.task_manager.get_issue_with_expand(
                issue.key,
                "changelog",
            )
            if issue_with_changelog and hasattr(issue_with_changelog, "changelog"):
                for history in issue_with_changelog.changelog.histories:
                    for item in history.items:
                        if item.field == "status" and item.toString in [
                            "In Progress",
                            "In Development",
                        ]:
                            return self._parse_jira_datetime(history.created)
        except Exception as e:
            LOGGER.error(
                f"Error getting implementation start date for {issue.key}: {e}",
            )
        return None

    def _get_initial_delivery_time(self, issue: Issue) -> Optional[datetime]:
        """Get initial delivery time from changelog.

        Args:
            issue: Jira issue object.

        Returns:
            Datetime when issue was first moved to 'Done'.
        """
        try:
            issue_with_changelog = self.task_manager.get_issue_with_expand(
                issue.key,
                "changelog",
            )
            if issue_with_changelog and hasattr(issue_with_changelog, "changelog"):
                for history in issue_with_changelog.changelog.histories:
                    for item in history.items:
                        if item.field == "status" and item.toString in [
                            "Done",
                            "Closed",
                            "Resolved",
                        ]:
                            return self._parse_jira_datetime(history.created)
        except Exception as e:
            LOGGER.error(
                f"Error getting initial delivery time for {issue.key}: {e}",
            )
        return None

    def _parse_jira_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Jira datetime string.

        Args:
            date_str: Jira datetime string.

        Returns:
            Datetime object or None.
        """
        if not date_str:
            return None

        try:
            if "T" in date_str:
                if "." in date_str:
                    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                else:
                    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
            else:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception as e:
            LOGGER.error(f"Error parsing datetime {date_str}: {e}")
            return None

    def _get_google_sheet_name(self, jira_username: str) -> Optional[str]:
        """Get Google Sheet display name for a Jira username.

        Args:
            jira_username: Jira username.

        Returns:
            Google Sheet name from user_config or Jira username if not found.
        """
        try:
            user_config = self.user_config.get_user_config_by_jira_username(jira_username)
            if user_config and user_config.google_sheet_name:
                return user_config.google_sheet_name
            return jira_username
        except Exception as e:
            LOGGER.debug(f"Error getting Google Sheet name for {jira_username}: {e}")
            return jira_username

    def _map_jira_status_to_sheet(self, jira_status: str) -> str:
        """Map Jira status to Google Sheet Persian workflow status.

        Args:
            jira_status: Jira status name (e.g., "IN PROGRESS", "DONE").

        Returns:
            Persian workflow status or original status if no mapping found.
        """
        status_upper = jira_status.upper().replace(" ", " ")
        mapped_status = JIRA_TO_GOOGLE_SHEET_STATUS.get(status_upper)
        if mapped_status:
            return mapped_status
        LOGGER.warning(f"No status mapping found for '{jira_status}', using original")
        return jira_status

    def _get_reporter_name(self, issue: Issue) -> Optional[str]:
        """Get reporter name from user_config.

        Args:
            issue: Jira issue object.

        Returns:
            Reporter's Google Sheet name or Jira username.
        """
        try:
            if hasattr(issue.fields, "reporter") and issue.fields.reporter:
                return self._get_google_sheet_name(issue.fields.reporter.name)
        except Exception as e:
            LOGGER.error(f"Error getting reporter for {issue.key}: {e}")
        return None

    def _get_board_name(self, issue: Issue) -> Optional[str]:
        """Get board name from issue project.

        Args:
            issue: Jira issue object.

        Returns:
            Board/Project name.
        """
        try:
            if hasattr(issue.fields, "project") and issue.fields.project:
                return issue.fields.project.name
        except Exception as e:
            LOGGER.error(f"Error getting board name for {issue.key}: {e}")
        return None

    def _get_user_id_from_labels(self, issue: Issue) -> Optional[str]:
        """Extract user ID from labels that match #ID pattern.

        Args:
            issue: Jira issue object.

        Returns:
            User ID if found in labels (e.g., "#123" -> "123"), None otherwise.
        """
        try:
            if hasattr(issue.fields, "labels") and issue.fields.labels:
                import re

                for label in issue.fields.labels:
                    match = re.match(r"#(\d+)", label)
                    if match:
                        return match.group(1)
        except Exception as e:
            LOGGER.error(f"Error extracting user ID from labels for {issue.key}: {e}")
        return None
