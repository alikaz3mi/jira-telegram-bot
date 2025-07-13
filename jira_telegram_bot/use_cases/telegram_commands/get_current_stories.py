from __future__ import annotations

from typing import Dict, List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import CurrentStoriesServiceInterface


class GetCurrentStoriesUseCase:
    """Handles the business logic for getting current stories in a sprint.
    
    This use case implements the command-specific business rules,
    orchestrating the flow between repositories and services.
    """
    
    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        current_stories_service: CurrentStoriesServiceInterface,
    ):
        """Initialize the use case.
        
        Args:
            task_manager_repository: Repository for task management operations
            current_stories_service: Service for current stories operations
        """
        self.task_manager_repository = task_manager_repository
        self.current_stories_service = current_stories_service
    
    async def get_projects(self) -> List[Dict[str, str]]:
        """Get available projects.
        
        Returns:
            List of projects with key and name
        """
        projects = self.task_manager_repository.get_projects()
        return [
            {"key": project.key, "name": project.name} 
            for project in projects
        ]
    
    async def get_sprints_for_project(self, project_key: str) -> List[Dict[str, str]]:
        """Get available sprints for a project.
        
        Args:
            project_key: The project key
            
        Returns:
            List of sprints with id and name
        """
        board_id = self.task_manager_repository.get_board_id(project_key)
        if not board_id:
            return []
        
        sprints = self.task_manager_repository.get_sprints(board_id)
        active_sprints = [
            sprint for sprint in sprints 
            if sprint.state in ("active", "future")
        ]
        
        return [
            {"id": str(sprint.id), "name": sprint.name} 
            for sprint in active_sprints
        ]
    
    async def generate_current_stories_report(
        self, 
        project_key: str, 
        sprint_id: str
    ) -> CurrentStoriesReport:
        """Generate current stories report for a project and sprint.
        
        Args:
            project_key: The project key
            sprint_id: The sprint ID
            
        Returns:
            Current stories report
        """
        jql_query = f'project = "{project_key}" AND sprint = {sprint_id} AND type = Story'
        
        stories = self.task_manager_repository.search_issues(
            jql=jql_query,
            max_results=100,
            expand="subtasks"
        )
        
        sprint_name = await self._get_sprint_name(project_key, sprint_id)
        
        story_items = []
        for idx, story in enumerate(stories, 1):
            story_item = await self._create_story_item(story, idx)
            story_items.append(story_item)
        
        return CurrentStoriesReport(
            project_key=project_key,
            sprint_name=sprint_name,
            stories=story_items
        )
    
    async def _get_sprint_name(self, project_key: str, sprint_id: str) -> str:
        """Get sprint name by ID.
        
        Args:
            project_key: The project key
            sprint_id: The sprint ID
            
        Returns:
            Sprint name
        """
        board_id = self.task_manager_repository.get_board_id(project_key)
        if not board_id:
            return f"Sprint {sprint_id}"
        
        sprints = self.task_manager_repository.get_sprints(board_id)
        for sprint in sprints:
            if str(sprint.id) == sprint_id:
                return sprint.name
        
        return f"Sprint {sprint_id}"
    
    async def _create_story_item(self, story, story_number: int) -> CurrentStoryItem:
        """Create story item from Jira issue.
        
        Args:
            story: Jira story issue
            story_number: Sequential number for the story
            
        Returns:
            CurrentStoryItem instance
        """
        assignees_abbr = await self._get_assignees_from_subtasks(story)
        
        epic_name = await self._get_epic_name(story)
        
        label_feature = None
        if story.fields.labels:
            label_feature = ", ".join(story.fields.labels)
        elif story.fields.components:
            label_feature = ", ".join([c.name for c in story.fields.components])
        
        remaining_hours = await self._calculate_remaining_hours(story)
        
        release = None
        if story.fields.fixVersions:
            release = story.fields.fixVersions[0].name
        
        priority = None
        if story.fields.priority:
            priority = story.fields.priority.name
        
        progress = story.fields.status.name if story.fields.status else None
        story_status = story.fields.status.name if story.fields.status else None
        
        # Calculate task counts from subtasks
        task_counts = await self._get_task_counts_from_subtasks(story)
        
        return CurrentStoryItem(
            story_number=story_number,
            issue_name=story.fields.summary,
            epic_name=epic_name,
            label_feature=label_feature,
            assignees_abbr=assignees_abbr,
            remaining_hours=remaining_hours,
            release=release,
            priority=priority,
            progress=progress,
            story_status=story_status,
            review_tasks_count=task_counts["review"],
            done_tasks_count=task_counts["done"],
            other_tasks_count=task_counts["other"]
        )
    
    async def _get_epic_name(self, story) -> Optional[str]:
        """Get epic name (not ID) for a story.
        
        Args:
            story: Jira story issue
            
        Returns:
            Epic name or None
        """
        try:
            epic_link = None
            if hasattr(story.fields, 'customfield_10100') and story.fields.customfield_10100:
                epic_link = story.fields.customfield_10100
            
            if epic_link:
                epic_issue = self.task_manager_repository.get_issue(epic_link)
                if epic_issue:
                    return epic_issue.fields.summary
            
            return None
        except Exception as e:
            LOGGER.warning(f"Failed to get epic name for story {story.key}: {e}")
            return None
    
    async def _calculate_remaining_hours(self, story) -> Optional[float]:
        """Calculate remaining hours from time tracking of story and its subtasks.
        
        Args:
            story: Jira story issue
            
        Returns:
            Total remaining hours as float
        """
        total_remaining_seconds = 0
        
        try:
            # Get story's own remaining estimate
            if hasattr(story.fields, 'timetracking') and story.fields.timetracking:
                remaining_estimate = getattr(story.fields.timetracking, 'remainingEstimateSeconds', 0)
                if remaining_estimate:
                    total_remaining_seconds += remaining_estimate
            
            # Get remaining estimates from subtasks
            if hasattr(story.fields, 'subtasks') and story.fields.subtasks:
                for subtask in story.fields.subtasks:
                    try:
                        full_subtask = self.task_manager_repository.get_issue_with_expand(
                            subtask.key, "timetracking"
                        )
                        if (full_subtask and 
                            hasattr(full_subtask.fields, 'timetracking') and 
                            full_subtask.fields.timetracking):
                            subtask_remaining = getattr(
                                full_subtask.fields.timetracking, 
                                'remainingEstimateSeconds', 
                                0
                            )
                            if subtask_remaining:
                                total_remaining_seconds += subtask_remaining
                    except Exception as e:
                        LOGGER.warning(f"Failed to get time tracking for subtask {subtask.key}: {e}")
            
            # Convert seconds to hours
            if total_remaining_seconds > 0:
                return round(total_remaining_seconds / 3600.0, 2)
            
            return None
            
        except Exception as e:
            LOGGER.warning(f"Failed to calculate remaining hours for story {story.key}: {e}")
            return None
    
    async def _get_assignees_from_subtasks(self, story) -> List[str]:
        """Get abbreviated assignee names from subtasks.
        
        Args:
            story: Jira story issue with subtasks
            
        Returns:
            List of abbreviated assignee names
        """
        assignees = set()
        
        if hasattr(story.fields, 'subtasks') and story.fields.subtasks:
            for subtask in story.fields.subtasks:
                try:
                    full_subtask = self.task_manager_repository.get_issue_with_expand(
                        subtask.key, "assignee"
                    )
                    if full_subtask and full_subtask.fields.assignee:
                        assignee_name = full_subtask.fields.assignee.name
                        abbr = self.current_stories_service.create_assignee_abbreviation(
                            assignee_name
                        )
                        assignees.add(abbr)
                except Exception as e:
                    LOGGER.warning(f"Failed to get assignee for subtask {subtask.key}: {e}")
        
        return list(assignees)
    
    async def _get_task_counts_from_subtasks(self, story) -> Dict[str, int]:
        """Get task counts by status from subtasks.
        
        Args:
            story: Jira story issue with subtasks
            
        Returns:
            Dictionary with counts for review, done, and other statuses
        """
        task_counts = {"review": 0, "done": 0, "other": 0}
        
        if hasattr(story.fields, 'subtasks') and story.fields.subtasks:
            for subtask in story.fields.subtasks:
                try:
                    full_subtask = self.task_manager_repository.get_issue_with_expand(
                        subtask.key, "status"
                    )
                    if full_subtask and full_subtask.fields.status:
                        status_name = full_subtask.fields.status.name.lower()
                        
                        if "review" in status_name:
                            task_counts["review"] += 1
                        elif "done" in status_name or "closed" in status_name or "resolved" in status_name:
                            task_counts["done"] += 1
                        else:
                            task_counts["other"] += 1
                except Exception as e:
                    LOGGER.warning(f"Failed to get status for subtask {subtask.key}: {e}")
                    task_counts["other"] += 1
        
        return task_counts
