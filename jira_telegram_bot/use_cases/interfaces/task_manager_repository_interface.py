from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot.entities.release import Release
from jira_telegram_bot.entities.task import TaskData


class TaskManagerRepositoryInterface(ABC):
    @abstractmethod
    def get_projects(self):
        pass

    @abstractmethod
    def get_project_components(self, project_key):
        pass

    @abstractmethod
    def get_epics(self, project_key: str):
        pass

    @abstractmethod
    def get_board_id(self, project_key: str) -> Optional[int]:
        pass

    @abstractmethod
    def get_sprints(self, board_id):
        pass

    @abstractmethod
    def get_project_versions(self, project_key):
        pass

    @abstractmethod
    def get_issue_types_for_project(self, project_key):
        pass

    @abstractmethod
    def get_priorities(self):
        pass

    @abstractmethod
    def get_assignees(self, project_key: str) -> List[str]:
        pass

    @abstractmethod
    def search_users(self, username: str) -> List[str]:
        pass

    @abstractmethod
    def build_issue_fields(self, task_data: TaskData) -> dict:
        pass

    @abstractmethod
    def handle_attachments(self, issue: Issue, attachments: Dict[str, List]):
        pass

    @abstractmethod
    def create_issue(self, fields):
        pass

    @abstractmethod
    def add_attachment(self, issue, attachment, filename):
        pass

    @abstractmethod
    def create_task(self, task_data: TaskData) -> Issue:
        pass

    @abstractmethod
    def add_comment(self, issue_key: str, comment: str):
        pass

    @abstractmethod
    def search_for_issues(self, query: str, max_results: int = 1000) -> List[Issue]:
        pass

    @abstractmethod
    def get_stories_by_epic(self, epic_key: str, project_key: str) -> List[Issue]:
        pass

    @abstractmethod
    def get_stories_by_project(
        self,
        project_key: str,
        epic_link: str = None,
        status: str = None,
        filters: str = None,
    ) -> List[Issue]:
        pass

    @abstractmethod
    def get_labels(self, project_key: str) -> List[str]:
        pass

    @abstractmethod
    def set_labels(self, project_key: str, labels: List[str]) -> bool:
        pass

    @abstractmethod
    def transition_task(self, issue_key: str, status: str) -> None:
        pass

    @abstractmethod
    def assign_issue(self, issue_key: str, assignee: str) -> None:
        pass

    @abstractmethod
    def update_issue(self, issue_key: str, task_data: TaskData) -> None:
        pass

    @abstractmethod
    def update_issue_from_fields(self, issue_key: str, fields: dict) -> None:
        pass

    @abstractmethod
    def is_user_jira_admin(self, username: str) -> bool:
        """
        Check if a user has Jira administrator privileges.

        Args:
            username: Jira username to check

        Returns:
            True if user is Jira admin, False otherwise
        """
        pass

    @abstractmethod
    def get_available_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """
        Get available transitions for an issue.

        Args:
            issue_key: The issue key

        Returns:
            List of transitions with id and name
        """
        pass

    @abstractmethod
    def update_time_estimate(self, issue_key: str, remaining_estimate: str) -> None:
        """
        Update the remaining time estimate for an issue.

        Args:
            issue_key: The issue key
            remaining_estimate: New remaining estimate (e.g., "0h", "2d")
        """
        pass

    @abstractmethod
    def get_issue(self, issue_key: str) -> Optional[Issue]:
        pass

    @abstractmethod
    def build_task_data_from_issue(self, issue: Issue) -> TaskData:
        pass

    @abstractmethod
    def create_task_data_from_jira_issue(self, issue) -> TaskData:
        pass

    @abstractmethod
    def get_issues_with_approaching_deadlines(
        self,
        lookahead_days: int = 7,
        additional_jql: Optional[str] = None,
    ) -> List[Issue]:
        """
        Get issues with deadlines within the specified lookahead period.

        Args:
            lookahead_days: Number of days to look ahead for deadlines
            additional_jql: Additional JQL filter to apply

        Returns:
            List of Jira issues with approaching deadlines
        """
        pass

    @abstractmethod
    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
        expand: Optional[str] = None,
    ) -> List[Issue]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            start_at: Starting index for pagination
            max_results: Maximum number of results to return
            expand: Comma-separated list of fields to expand

        Returns:
            List of matching Jira issues
        """
        pass

    @abstractmethod
    def get_issue_with_expand(self, issue_key: str, expand: str) -> Optional[Issue]:
        """
        Get a single issue with expanded fields.

        Args:
            issue_key: The issue key
            expand: Comma-separated list of fields to expand

        Returns:
            Jira issue with expanded fields or None
        """
        pass

        @abstractmethod
        def get_issue_by_summary(self, summary: str, board: str) -> Optional[Issue]:
            """
            Get a Jira issue by its summary and board.

            Args:
                summary: The summary of the issue
                board: The board/project key

            Returns:
                Jira issue or None
            """
            pass

        @abstractmethod
        def get_issue_url(self, issue: Issue) -> str:
            """
            Get the URL for a Jira issue.

            Args:
                issue: The Jira issue object

            Returns:
                URL string for the issue
            """
            pass

        @abstractmethod
        def get_issue_url_by_key(self, issue_key: str) -> str:
            """
            Get the URL for a Jira issue by its key.

            Args:
                issue_key: The key of the Jira issue

            Returns:
                URL string for the issue
            """
            pass

        @abstractmethod
        def get_transitions(self, issue_key: str) -> List[Dict[str, str]]:
            """
            Get available transitions for an issue.

            Args:
                issue_key: The key of the Jira issue

            Returns:
                List of available transitions with their IDs and names
            """
            pass

        @abstractmethod
        def transition_issue(self, issue_key: str, transition_id: str) -> None:
            """
            Transition an issue to a new status.

            Args:
                issue_key: The key of the Jira issue
                transition_id: The ID of the transition to apply

            Raises:
                Exception if the transition fails
            """
            pass

        @abstractmethod
        def get_sprint_by_id(
            self,
            sprint_id: str,
            board_id: str,
        ) -> Optional[Dict[str, any]]:
            """
            Get sprint details by ID.

            Args:
                sprint_id: The ID of the sprint
                board_id: The ID of the board

            Returns:
                Sprint details as a dictionary or None if not found
            """
            pass

        @abstractmethod
        def get_sprint_by_name(
            self,
            sprint_name: str,
            board_id: str,
        ) -> Optional[Dict[str, any]]:
            """
            Get sprint details by name.

            Args:
                sprint_name: The name of the sprint
                board_id: The ID of the board

            Returns:
                Sprint details as a dictionary or None if not found
            """
            pass

        @abstractmethod
        def create_sprint(
            self,
            board_id: int,
            sprint_name: str,
            start_date: str,
            end_date: str,
            goal: str = None,
        ) -> Optional[Dict[str, any]]:
            """
            Create a new sprint.

            Args:
                board_id: The ID of the board to create the sprint in
                sprint_name: The name of the new sprint
                start_date: The start date of the sprint in ISO format
                end_date: The end date of the sprint in ISO format
                goal: The goal of the sprint (optional)

            Returns:
                Sprint details as a dictionary or None if creation fails
            """
            pass

        @abstractmethod
        def link_issues(
            self,
            dependent_issue_key: str,
            dependency_issue_key: str,
            link_type: str = "Dependency",
        ) -> bool:
            """
            Link two Jira issues with a specified relationship.

            Args:
                dependent_issue_key: The issue that depends on another (inward side, e.g. 'is blocked by')
                dependency_issue_key: The issue that is depended upon (outward side, e.g. 'blocks')
                link_type: The type of link (e.g., "Dependency", "Blocks", "Relates")

            Returns:
                True if linking was successful, False otherwise
            """
            pass

        @abstractmethod
        def get_issue_link_types(self) -> List[Dict[str, str]]:
            """
            Get available issue link types in Jira.

            Returns:
                List of link types with their names and descriptions
            """
            pass

    @abstractmethod
    def get_issue_spent_time_in_seconds(self, issue_key: str) -> int:
        """Get the total time spent on an issue in seconds.

        Args:
            issue_key: The issue key

        Returns:
            Total time spent in seconds
        """
        pass

    @abstractmethod
    def get_issue_by_summary(self, summary: str, board: str) -> Optional[Issue]:
        """
        Get a Jira issue by its summary and board.

        Args:
            summary: The summary of the issue
            board: The board/project key

        Returns:
            Jira issue or None
        """
        pass

    @abstractmethod
    def get_issue_url(self, issue: Issue) -> str:
        """
        Get the URL for a Jira issue.

        Args:
            issue: The Jira issue object

        Returns:
            URL string for the issue
        """
        pass

    @abstractmethod
    def get_issue_url_by_key(self, issue_key: str) -> str:
        """
        Get the URL for a Jira issue by its key.

        Args:
            issue_key: The key of the Jira issue

        Returns:
            URL string for the issue
        """
        pass

    @abstractmethod
    def get_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """
        Get available transitions for an issue.

        Args:
            issue_key: The key of the Jira issue

        Returns:
            List of available transitions with their IDs and names
        """
        pass

    @abstractmethod
    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """
        Transition an issue to a new status.

        Args:
            issue_key: The key of the Jira issue
            transition_id: The ID of the transition to apply

        Raises:
            Exception if the transition fails
        """
        pass

    @abstractmethod
    def get_sprint_by_id(
        self,
        sprint_id: str,
        board_id: str,
    ) -> Optional[Dict[str, any]]:
        """
        Get sprint details by ID.

        Args:
            sprint_id: The ID of the sprint
            board_id: The ID of the board

        Returns:
            Sprint details as a dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_sprint_by_name(
        self,
        sprint_name: str,
        board_id: str,
    ) -> Optional[Dict[str, any]]:
        """
        Get sprint details by name.

        Args:
            sprint_name: The name of the sprint
            board_id: The ID of the board

        Returns:
            Sprint details as a dictionary or None if not found
        """
        pass

    @abstractmethod
    def create_sprint(
        self,
        board_id: int,
        sprint_name: str,
        start_date: str,
        end_date: str,
        goal: str = None,
    ) -> Optional[Dict[str, any]]:
        """
        Create a new sprint.

        Args:
            board_id: The ID of the board to create the sprint in
            sprint_name: The name of the new sprint
            start_date: The start date of the sprint in ISO format
            end_date: The end date of the sprint in ISO format
            goal: The goal of the sprint (optional)

        Returns:
            Sprint details as a dictionary or None if creation fails
        """
        pass

    @abstractmethod
    def get_releases(self, project_key: str) -> List[Release]:
        """Get all releases for a Jira project.

        Args:
            project_key: Key of the Jira project.

        Returns:
            List of Release entities.
        """
        pass

    @abstractmethod
    def release_exist(self, project_key: str, name: str) -> bool:
        """Check if a release exists for a Jira project.

        Args:
            project_key: Key of the Jira project.
            name: Name of the release.

        Returns:
            True if the release exists, False otherwise.
        """
        pass

    @abstractmethod
    def create_release(
        self,
        project_key: str,
        name: str,
        description: Optional[str] = None,
        release_date: Optional[str] = None,
        released: bool = False,
    ) -> Release:
        """Create a new release for a Jira project.

        Args:
            project_key: Key of the Jira project.
            name: Name of the release.
            description: Optional description.
            release_date: Optional release date (YYYY-MM-DD).
            released: Whether the release is marked as released.

        Returns:
            The created Release entity.
        """
        pass

    @abstractmethod
    def update_release(
        self,
        project_key: str,
        release_name: str,
        description: Optional[str] = None,
        released: Optional[bool] = None,
        release_date: Optional[str] = None,
    ) -> bool:
        """Update an existing release for a Jira project.

        Args:
            project_key: Key of the Jira project.
            release_name: Name of the release to update.
            description: Optional new description.
            released: Optional released status.
            release_date: Optional release date (YYYY-MM-DD).

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def link_issues(
        self,
        dependent_issue_key: str,
        dependency_issue_key: str,
        link_type: str = "Dependency",
    ) -> bool:
        """
        Link two Jira issues with a specified relationship.

        Args:
            dependent_issue_key: The issue that depends on another (inward side, e.g. 'is blocked by')
            dependency_issue_key: The issue that is depended upon (outward side, e.g. 'blocks')
            link_type: The type of link (e.g., "Dependency", "Blocks", "Relates")

        Returns:
            True if linking was successful, False otherwise
        """
        pass

    @abstractmethod
    def get_issue_link_types(self) -> List[Dict[str, str]]:
        """
        Get available issue link types in Jira.

        Returns:
            List of link types with their names and descriptions
        """
        pass

    @abstractmethod
    def get_issue_links(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get all issue links for a given issue.

        Args:
            issue_key: The key of the issue

        Returns:
            List of issue links with their type, direction, and linked issues
        """
        pass

    @abstractmethod
    def delete_issue_link(self, link_id: str) -> bool:
        """
        Delete an issue link by its ID.

        Args:
            link_id: The ID of the link to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    def get_issue_subtasks(self, issue_key: str) -> List[Issue]:
        """Get all subtasks for a given Jira issue.

        Args:
            issue_key: The key of the parent issue

        Returns:
            List of subtask issues
        """
        pass

    @abstractmethod
    def delete_issue(self, issue_key: str) -> bool:
        """Delete a Jira issue.

        Args:
            issue_key: The key of the issue to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_sprint(self, sprint_id: int):
        """Get sprint information by ID.

        Args:
            sprint_id: The sprint ID

        Returns:
            Sprint object with dates, name, and ID
        """
        pass

    @abstractmethod
    async def get_sprint_issues(self, project_keys: List[str], sprint_id: int) -> List:
        """Get all issues for a sprint across projects.

        Args:
            project_keys: List of project keys to search
            sprint_id: The sprint ID

        Returns:
            List of IssueSnapshot objects
        """
        pass

    @abstractmethod
    async def get_issue_worklogs(self, issue_keys: List[str]) -> List:
        """Get worklogs for multiple issues.

        Args:
            issue_keys: List of issue keys

        Returns:
            List of WorklogSlice objects
        """
        pass

    @abstractmethod
    async def get_issue_changelogs(self, issue_keys: List[str]) -> Dict[str, List]:
        """Get changelogs for multiple issues.

        Args:
            issue_keys: List of issue keys

        Returns:
            Dictionary mapping issue keys to list of ChangeLogEvent objects
        """
        pass

    @abstractmethod
    async def get_issue_epic(self, issue_key: str) -> Optional[str]:
        """Get epic name for an issue.

        Args:
            issue_key: The issue key

        Returns:
            Epic name if found, None otherwise
        """
        pass

    @abstractmethod
    def get_worklog_data(
        self,
        issue: Issue,
    ) -> tuple[float, List[str], Dict[str, float], Dict[str, float]]:
        """Get worklog data including progress hours and individual hours.

        Note: This method uses UserConfig internally to map Jira usernames
        to Google Sheet names and departments.

        Args:
            issue: Jira issue object.

        Returns:
            Tuple of (progress_hours, involved_people, department_hours, individual_hours).
            - progress_hours: Total hours logged across all worklogs
            - involved_people: Sorted list of Google Sheet display names
            - department_hours: Dict mapping department field names (ai_hours, backend_hours, etc.) to hours
            - individual_hours: Dict mapping person names to their logged hours
        """
        pass

    @abstractmethod
    def get_time_tracking(self, issue: Issue) -> tuple[float, float]:
        """Get ETA and total hours from time tracking.

        Args:
            issue: Jira issue object.

        Returns:
            Tuple of (eta_hours, total_hours).
        """
        pass

    @abstractmethod
    def get_user_actionable_tasks(self, jira_username: str) -> List[Issue]:
        """Get tasks that require user attention today.
        
        Uses JQL filter:
        assignee = {username} AND resolution = Unresolved AND 
        (Sprint in openSprints() AND ("Target start" <= now() OR "Target start" is EMPTY) 
        OR Sprint is EMPTY AND ("Target start" <= now() OR "Target start" is EMPTY)) 
        ORDER BY cf[10109] ASC
        
        Args:
            jira_username: Jira username to filter tasks for.
            
        Returns:
            List of Jira issues requiring attention.
        """
        pass

    @abstractmethod
    def log_work(
        self,
        issue_key: str,
        time_spent_seconds: int,
        comment: Optional[str] = None,
        started_date: Optional[str] = None,
    ) -> None:
        """Log work time on an issue.
        
        Args:
            issue_key: Jira issue key (e.g., "PROJ-123").
            time_spent_seconds: Time spent in seconds.
            comment: Optional work log comment.
            started_date: Optional date when work started (YYYY-MM-DD format).
        """
        pass

    @abstractmethod
    def set_delay_reason(
        self,
        issue_key: str,
        reason: str,
        comment: Optional[str] = None,
    ) -> None:
        """Set delay reason on an issue.
        
        Args:
            issue_key: Jira issue key.
            reason: Delay reason value.
            comment: Optional comment explaining the delay.
        """
        pass

    @abstractmethod
    def get_available_transitions(self, issue_key: str) -> List[dict]:
        """Get available transitions for an issue.
        
        Args:
            issue_key: Jira issue key.
            
        Returns:
            List of available transitions with id and name.
        """
        pass
