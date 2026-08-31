"""Use case for getting user's daily tasks that need attention."""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from typing import List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


# How long a finished blocker still counts as news worth mentioning.
BLOCKER_RECENCY_DAYS = 3


class GetUserDailyTasksUseCase:
    """Use case for fetching tasks that need daily attention."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            task_manager_repository: Repository for task management
        """
        self.task_manager_repository = task_manager_repository

    async def execute(
        self,
        jira_username: str,
        project_keys: Optional[List[str]] = None,
    ) -> List[DailyTaskCheck]:
        """Get tasks needing attention for a user.

        Args:
            jira_username: User's Jira username
            project_keys: Optional list of project keys to filter

        Returns:
            List of daily task checks
        """
        try:
            tasks_needing_attention = []
            
            # Build JQL query based on user's recommendation:
            # resolution = Unresolved AND (Sprint in openSprints() AND ("Target start" <= now() OR "Target start" is EMPTY) OR Sprint is EMPTY AND ("Target start" <= now() OR "Target start" is EMPTY))
            # Note: Sprint is EMPTY is for Kanban board tasks
            
            jql_parts = [
                f'assignee = "{jira_username}"',
                'resolution = Unresolved',
                '(Sprint in openSprints() AND ("Target start" <= now() OR "Target start" is EMPTY) OR Sprint is EMPTY AND ("Target start" <= now() OR "Target start" is EMPTY))'
            ]
            
            if project_keys:
                project_filter = " OR ".join(
                    [f'project = "{key}"' for key in project_keys]
                )
                jql_parts.append(f"({project_filter})")
            
            jql = " AND ".join(jql_parts)
            jql += " ORDER BY cf[10109] ASC"  # Order by Target End date
            
            LOGGER.info(f"Daily task tracker JQL query: {jql}")
            
            issues = self.task_manager_repository.search_for_issues(
                jql,
                max_results=100,
            )
            
            skipped = 0
            for issue in issues:
                task_check = await self._evaluate_task(issue)
                if task_check is None:
                    skipped += 1
                    continue
                if task_check.check_status != TaskCheckStatus.OK:
                    tasks_needing_attention.append(task_check)
            
            if skipped:
                # A transient Jira error silently shortens the list otherwise,
                # and the user is told about tasks they no longer appear to have.
                LOGGER.warning(
                    f"Dropped {skipped} of {len(issues)} issues for "
                    f"{jira_username}; the list below is incomplete"
                )
            
            LOGGER.info(
                f"Found {len(tasks_needing_attention)} tasks needing attention for {jira_username}"
            )
            
            return tasks_needing_attention
            
        except Exception as e:
            LOGGER.error(f"Error getting daily tasks for {jira_username}: {e}")
            raise

    async def _evaluate_task(self, issue) -> Optional[DailyTaskCheck]:
        """Evaluate a single task.

        Args:
            issue: Jira issue object

        Returns:
            DailyTaskCheck if task needs attention, None otherwise
        """
        try:
            issue_key = issue.key
            summary = getattr(issue.fields, "summary", "")
            status = getattr(issue.fields.status, "name", "")
            assignee_name = (
                getattr(issue.fields.assignee, "name", None)
                if issue.fields.assignee
                else None
            )
            
            if not assignee_name:
                return None
            
            target_start = self._get_custom_date_field(issue, "target_start")
            target_end = self._get_custom_date_field(issue, "target_end")
            
            sprint_name = self._extract_sprint_name(issue)
            
            project_key = issue.fields.project.key
            
            dependencies = self._get_dependencies(issue)
            dependencies_completed, cleared_recently = self._inspect_dependencies(
                dependencies,
            )
            
            worklog_hours = self._get_total_worklog_hours(issue)
            
            issue_type = getattr(issue.fields.issuetype, "name", None)
            priority = (
                getattr(issue.fields.priority, "name", None)
                if hasattr(issue.fields, "priority") and issue.fields.priority
                else None
            )
            
            description = getattr(issue.fields, "description", None)
            
            check_status = self._determine_check_status(
                status,
                target_start,
                dependencies_completed,
                worklog_hours,
            )
            
            return DailyTaskCheck(
                issue_key=issue_key,
                summary=summary,
                status=status,
                assignee=assignee_name,
                check_status=check_status,
                target_start=target_start,
                target_end=target_end,
                sprint_name=sprint_name,
                project_key=project_key,
                dependencies=dependencies,
                dependencies_completed=dependencies_completed,
                blockers_cleared_recently=cleared_recently,
                worklog_hours=worklog_hours,
                parent_key=getattr(
                    getattr(issue.fields, "parent", None), "key", None,
                ),
                issue_type=issue_type,
                priority=priority,
                description=description,
            )
            
        except Exception as e:
            LOGGER.error(f"Error evaluating task {getattr(issue, 'key', 'unknown')}: {e}")
            return None

    def _get_custom_date_field(
        self,
        issue,
        field_name: str,
    ) -> Optional[datetime]:
        """Get custom date field value.

        Args:
            issue: Jira issue
            field_name: Field name (target_start, target_end)

        Returns:
            Datetime if field exists, None otherwise
        """
        try:
            field_mapping = {
                "target_start": getattr(
                    self.task_manager_repository,
                    "jira_target_start_id",
                    "customfield_10111",
                ),
                "target_end": getattr(
                    self.task_manager_repository,
                    "jira_target_end_id",
                    "customfield_10110",
                ),
            }
            
            field_id = field_mapping.get(field_name)
            if not field_id:
                return None
            
            value = getattr(issue.fields, field_id, None)
            if value:
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                elif isinstance(value, datetime):
                    return value
                elif isinstance(value, date):
                    return datetime.combine(value, datetime.min.time())
            
            return None
            
        except Exception as e:
            LOGGER.debug(f"Error getting {field_name} for {issue.key}: {e}")
            return None

    def _extract_sprint_name(self, issue) -> Optional[str]:
        """Extract active sprint name from issue.

        Args:
            issue: Jira issue

        Returns:
            Sprint name if found
        """
        try:
            sprint_field_id = getattr(
                self.task_manager_repository,
                "jira_sprint_id",
                "customfield_10104",
            )
            sprint_field = getattr(issue.fields, sprint_field_id, None)
            
            if not sprint_field:
                return None
            
            if isinstance(sprint_field, list):
                for sprint in sprint_field:
                    if sprint and "state=ACTIVE" in str(sprint):
                        sprint_str = str(sprint)
                        if "name=" in sprint_str:
                            start = sprint_str.find("name=") + 5
                            end = sprint_str.find(",", start)
                            if end == -1:
                                end = sprint_str.find("]", start)
                            return sprint_str[start:end]
            
            return None
            
        except Exception as e:
            LOGGER.debug(f"Error extracting sprint for {issue.key}: {e}")
            return None

    def _get_dependencies(self, issue) -> List[str]:
        """Get list of dependency issue keys.

        Args:
            issue: Jira issue

        Returns:
            List of dependency issue keys
        """
        dependencies = []

        try:
            if hasattr(issue.fields, "issuelinks"):
                for link in issue.fields.issuelinks:
                    if not hasattr(link, "type"):
                        continue

                    link_type = getattr(link.type, "name", "")
                    if not (
                        "blocks" in link_type.lower()
                        or "depends" in link_type.lower()
                    ):
                        continue

                    # Direction decides meaning. Jira puts the issue this one
                    # waits on in `inwardIssue` ("is blocked by"); an
                    # `outwardIssue` is what this issue blocks, which is the
                    # reverse and is not a prerequisite. Treating both alike
                    # made a task that blocks others look like it depended
                    # on them.
                    inward = getattr(link, "inwardIssue", None)
                    if inward is not None:
                        dependencies.append(inward.key)

        except Exception as e:
            LOGGER.debug(f"Error getting dependencies for {issue.key}: {e}")

        return dependencies

    async def _check_dependencies_completed(
        self,
        dependency_keys: List[str],
    ) -> bool:
        """Check if all dependencies are completed.

        Args:
            dependency_keys: List of dependency issue keys

        Returns:
            True if all dependencies completed or no dependencies
        """
        completed, _ = self._inspect_dependencies(dependency_keys)
        return completed

    def _inspect_dependencies(
        self,
        dependency_keys: List[str],
    ) -> tuple:
        """Check dependencies and note which of them finished recently.

        "All clear" is a state; "this finished yesterday" is news. Only the
        second is worth telling somebody about, so both come back here.

        Args:
            dependency_keys: Issues this task waits on

        Returns:
            Whether every dependency is done, and the keys of those that
            reached done within the recency window.
        """
        if not dependency_keys:
            return True, []

        completed = True
        recent: List[str] = []
        horizon = datetime.now(timezone.utc) - timedelta(
            days=BLOCKER_RECENCY_DAYS,
        )

        for dep_key in dependency_keys:
            try:
                dep_issue = self.task_manager_repository.get_issue(dep_key)
                status = getattr(dep_issue.fields.status, "name", "").lower()

                if status not in ["done", "closed", "resolved"]:
                    completed = False
                    continue

                if self._finished_since(dep_issue, horizon):
                    recent.append(dep_key)

            except Exception as e:
                LOGGER.debug(f"Error checking dependency {dep_key}: {e}")
                completed = False

        return completed, recent

    @staticmethod
    def _finished_since(issue, horizon: datetime) -> bool:
        """Whether an issue reached its done state after a given moment.

        ``resolutiondate`` is empty on workflows here that reach a Done
        status without setting a resolution, so ``updated`` stands in for
        it. That is looser — an edit counts as a change — but it errs
        towards mentioning a blocker rather than staying silent about one.

        Args:
            issue: The dependency issue
            horizon: The earliest moment that still counts as recent

        Returns:
            True when the issue looks to have finished since the horizon.
        """
        for field in ("resolutiondate", "updated"):
            stamp = getattr(issue.fields, field, None)
            if not stamp:
                continue
            try:
                moment = datetime.fromisoformat(str(stamp))
            except ValueError:
                continue
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return moment >= horizon
        return False

    def _get_total_worklog_hours(self, issue) -> float:
        """Get total worklog hours for an issue.

        Args:
            issue: Jira issue

        Returns:
            Total hours logged
        """
        try:
            worklogs = self.task_manager_repository.jira.worklogs(issue.key)
            total_seconds = sum(
                getattr(wl, "timeSpentSeconds", 0) for wl in worklogs
            )
            return total_seconds / 3600.0
            
        except Exception as e:
            LOGGER.debug(f"Error getting worklogs for {issue.key}: {e}")
            return 0.0

    def _determine_check_status(
        self,
        status: str,
        target_start: Optional[datetime],
        dependencies_completed: bool,
        worklog_hours: float,
    ) -> TaskCheckStatus:
        """Determine the check status for a task.

        Args:
            status: Current task status
            target_start: Target start date
            dependencies_completed: Whether dependencies are completed
            worklog_hours: Total worklog hours

        Returns:
            TaskCheckStatus
        """
        status_lower = status.lower()
        today = datetime.now()
        
        if status_lower in ["done", "closed", "resolved"]:
            if worklog_hours == 0:
                return TaskCheckStatus.NEEDS_WORKLOG
            return TaskCheckStatus.OK
        
        if status_lower in ["review", "in review", "code review"]:
            if worklog_hours == 0:
                return TaskCheckStatus.NEEDS_WORKLOG
            return TaskCheckStatus.OK
        
        if status_lower in ["in progress", "doing"]:
            return TaskCheckStatus.IN_PROGRESS
        
        if target_start and target_start.date() > today.date():
            # Genuinely scheduled for later; nothing to ask about yet.
            return TaskCheckStatus.OK

        # No Target start means undated, not "not yet due". The JQL already
        # limited this to the person's unresolved work in an open sprint, so
        # an undated To Do belongs in the list — leaving it out made real
        # sprint work invisible to the assistant.
        if dependencies_completed:
            return TaskCheckStatus.SHOULD_BE_STARTED

        return TaskCheckStatus.OK
