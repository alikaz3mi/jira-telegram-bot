from typing import List

from jira_telegram_bot.entities.jira.issue import JiraIssue
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface


class GetSprintIssuesUseCase:
    """Use case for retrieving issues from a specific sprint."""

    def __init__(self, task_repository: TaskManagerRepositoryInterface):
        """Initialize the use case with dependencies.

        Args:
            task_repository: Repository for accessing JIRA tasks.
        """
        self._task_repository = task_repository

    async def execute(self, sprint_label: str) -> List[JiraIssue]:
        """Retrieve all issues from the specified sprint.

        Args:
            sprint_label: The sprint label or JQL identifier.

        Returns:
            List of JiraIssue entities from the sprint.

        Raises:
            Exception: If retrieval fails.
        """
        try:
            # Build JQL query for sprint issues
            if sprint_label.startswith("Sprint "):
                # Handle "Sprint X" format
                jql_query = f'sprint = "{sprint_label}"'
            else:
                # Handle custom sprint labels or names
                jql_query = f'sprint = "{sprint_label}" OR sprint in openSprints()'
            
            # Search for issues in the sprint
            jira_issues = self._task_repository.search_for_issues(jql_query, max_results=100)
            
            # Convert JIRA Issue objects to JiraIssue entities
            sprint_issues = []
            for issue in jira_issues:
                task_data = self._task_repository.create_task_data_from_jira_issue(issue)
                
                jira_issue = JiraIssue(
                    key=issue.key,
                    summary=task_data.summary or "",
                    description=task_data.description,
                    assignee=task_data.assignee,
                    status=getattr(issue.fields, 'status', None) and issue.fields.status.name,
                    issue_type=task_data.task_type,
                    project_key=task_data.project_key,
                    priority=task_data.priority,
                    created=getattr(issue.fields, 'created', None),
                    updated=getattr(issue.fields, 'updated', None),
                    due_date=getattr(issue.fields, 'duedate', None),
                    story_points=task_data.story_points,
                    sprint_name=task_data.sprint_name,
                    epic_link=task_data.epic_link,
                    labels=getattr(issue.fields, 'labels', []),
                    components=task_data.components or [],
                )
                sprint_issues.append(jira_issue)
                
            return sprint_issues
            
        except Exception as e:
            raise Exception(f"Failed to retrieve sprint issues: {str(e)}")
