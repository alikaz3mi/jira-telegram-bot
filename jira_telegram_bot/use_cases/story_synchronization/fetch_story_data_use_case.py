"""Use case for fetching story data from Jira for synchronization."""
from datetime import datetime
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.story_synchronization.constants import (
    JIRA_TO_STORY_SYNC_STATUS,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class FetchStoryDataUseCase:
    """Use case for fetching story data from Jira."""

    def __init__(
        self,
        task_manager: TaskManagerRepositoryInterface,
        jira_base_url: str,
        user_config: UserConfigInterface,
        pm_project_key: str = "",
    ):
        """Initialize the use case.

        Args:
            task_manager: Task manager repository interface.
            jira_base_url: Base URL for Jira.
            user_config: User configuration interface.
            pm_project_key: Project key prefix for the PM board (e.g. "PM").
        """
        self.task_manager = task_manager
        self.jira_base_url = jira_base_url
        self.user_config = user_config
        self.pm_project_key = pm_project_key

    def execute(
        self,
        board_key: str,
        days_back: Optional[int] = None,
    ) -> List[SynthPMFeatureEntity]:
        """Fetch story issues from Jira.

        Args:
            board_key: Jira board/project key.
            days_back: Number of days to look back for updated issues.

        Returns:
            List of SynthPMFeatureEntity entities.
        """
        jql = self._build_jql(board_key, days_back)
        LOGGER.info(f"Fetching stories with JQL: {jql}")

        issues = self.task_manager.search_for_issues(jql)
        LOGGER.info(f"Found {len(issues)} stories")

        rows = []
        for idx, issue in enumerate(issues, start=1):
            row = self._convert_issue_to_feature(issue, idx)
            rows.append(row)

        return rows

    def _build_jql(self, board_key: str, days_back: Optional[int]) -> str:
        """Build JQL query for fetching stories.

        Args:
            board_key: Jira board/project key.
            days_back: Number of days to look back.

        Returns:
            JQL query string.
        """
        jql = f'project = "{board_key}" AND issuetype = Story'

        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            date_str = cutoff_date.strftime("%Y-%m-%d")
            jql += f' AND updated >= "{date_str}"'

        jql += " ORDER BY created DESC"
        return jql

    def _convert_issue_to_feature(
        self,
        issue: Issue,
        row_number: int,
    ) -> SynthPMFeatureEntity:
        """Convert Jira issue to SynthPMFeatureEntity.

        Args:
            issue: Jira issue object.
            row_number: Row number for the sheet.

        Returns:
            SynthPMFeatureEntity entity.
        """
        epic_name = self._get_epic_name(issue)
        departments_list = self._get_departments(issue)
        departments = ", ".join(departments_list) if departments_list else None
        status = self._map_jira_status_to_sheet(issue.fields.status.name)
        implementation_start = self._get_implementation_start_date(issue)
        initial_delivery_time = self._get_initial_delivery_time(issue)
        
        eta_hours, total_hours = self.task_manager.get_time_tracking(issue)
        progress_hours, involved_people_list, dept_hours, individual_hours = (
            self.task_manager.get_worklog_data(issue)
        )
        
        pm_board_issue_key = self._get_linked_pm_issue(issue)

        involved_people = ", ".join(involved_people_list) if involved_people_list else None

        times = {}
        for person, hours in individual_hours.items():
            if hours > 0:
                times[person] = int(round(hours))

        return SynthPMFeatureEntity(
            row_number=row_number,
            sheet_row_number=row_number,
            task_title=issue.fields.summary,
            epic=epic_name,
            release=self._get_release(issue),
            necessity=None,
            priority=getattr(issue.fields.priority, "name", None),
            status=status,
            eta_hours=int(eta_hours) if eta_hours else None,
            total_hours=int(total_hours) if total_hours else None,
            departments=departments,
            involved_people=involved_people,
            ai=str(int(dept_hours.get("ai_hours", 0))) if dept_hours.get("ai_hours") else None,
            backend=str(int(dept_hours.get("backend_hours", 0))) if dept_hours.get("backend_hours") else None,
            frontend=str(int(dept_hours.get("frontend_hours", 0))) if dept_hours.get("frontend_hours") else None,
            devops=str(int(dept_hours.get("devops_hours", 0))) if dept_hours.get("devops_hours") else None,
            ui_ux=str(int(dept_hours.get("ui_ux_hours", 0))) if dept_hours.get("ui_ux_hours") else None,
            creation_date=self._parse_jira_datetime(issue.fields.created),
            implementation_start_date=implementation_start,
            deadline=self._parse_jira_datetime(getattr(issue.fields, "duedate", None)),
            sprint=self._get_sprint_name(issue),
            dependencies=None,
            department_deps=None,
            initial_delivery_time=initial_delivery_time,
            description=issue.fields.description or "",
            acceptance_criteria=None,
            test_cases=None,
            po_notes=None,
            jira_issue_key=pm_board_issue_key,
            developer_board_issue_key=issue.key,
            version=None,
            times=times,
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

    def _get_departments(self, issue: Issue) -> List[str]:
        """Get departments (components) for the issue."""
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

    def _get_release(self, issue: Issue) -> Optional[str]:
        """Get release/fix version for the issue."""
        try:
            if hasattr(issue.fields, "fixVersions") and issue.fields.fixVersions:
                return issue.fields.fixVersions[0].name
        except Exception as e:
            LOGGER.error(f"Error getting release for {issue.key}: {e}")
        return None

    def _get_sprint_name(self, issue: Issue) -> Optional[str]:
        """Get sprint name formatted as '55: 07-26 to 08-02'."""
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
        """Extract sprint number from name or ID."""
        import re

        if sprint_name:
            match = re.search(r"(\d+)", sprint_name)
            if match:
                return match.group(1)

        if sprint_id:
            return sprint_id

        return None

    def _extract_date_range(self, sprint_goal: Optional[str]) -> Optional[str]:
        """Extract date range from sprint goal."""
        import re

        if not sprint_goal:
            return None

        date_pattern = r"(\d{2}-\d{2})\s+to\s+(\d{2}-\d{2})"
        match = re.search(date_pattern, sprint_goal)
        if match:
            return f"{match.group(1)} to {match.group(2)}"

        return None

    def _get_implementation_start_date(self, issue: Issue) -> Optional[datetime]:
        """Get implementation start date from changelog."""
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
            LOGGER.error(f"Error getting implementation start date for {issue.key}: {e}")
        return None

    def _get_initial_delivery_time(self, issue: Issue) -> Optional[datetime]:
        """Get initial delivery time from changelog."""
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
            LOGGER.error(f"Error getting initial delivery time for {issue.key}: {e}")
        return None

    def _get_linked_pm_issue(self, issue: Issue) -> Optional[str]:
        """Get linked PM board issue key from issue links.

        Args:
            issue: Jira issue object (developer board).

        Returns:
            PM board issue key or None.
        """
        try:
            if hasattr(issue.fields, "issuelinks"):
                pm_prefix = f"{self.pm_project_key}-" if self.pm_project_key else ""
                for link in issue.fields.issuelinks:
                    if hasattr(link, "outwardIssue"):
                        linked = link.outwardIssue
                        if pm_prefix and linked.key.startswith(pm_prefix):
                            return linked.key
                    elif hasattr(link, "inwardIssue"):
                        linked = link.inwardIssue
                        if pm_prefix and linked.key.startswith(pm_prefix):
                            return linked.key
        except Exception as e:
            LOGGER.error(f"Error getting linked PM issue for {issue.key}: {e}")
        return None

    def _parse_jira_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Jira datetime string."""
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

    def _map_jira_status_to_sheet(self, jira_status: str) -> str:
        """Map Jira status to Google Sheet Persian workflow status."""
        status_upper = jira_status.upper().strip()
        mapped_status = JIRA_TO_STORY_SYNC_STATUS.get(status_upper)
        if mapped_status:
            LOGGER.debug(f"Mapped Jira status '{jira_status}' -> '{mapped_status}'")
            return mapped_status
        LOGGER.warning(
            f"No status mapping found for Jira status '{jira_status}' (normalized: '{status_upper}'), "
            f"using original. Available mappings: {list(JIRA_TO_STORY_SYNC_STATUS.keys())}"
        )
        return jira_status
