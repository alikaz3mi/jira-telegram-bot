from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import CurrentStoriesServiceInterface
from jira_telegram_bot.utils.jalali_georgian_calendar import JalaliGregorianCalendar


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
        for story in stories:
            story_item = await self._create_story_item(story)
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
    
    async def _create_story_item(self, story) -> CurrentStoryItem:
        """Create story item from Jira issue.
        
        Args:
            story: Jira story issue
            
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
        
        story_status = story.fields.status.name if story.fields.status else None
        
        # Calculate dates
        creation_date_jalali = await self._convert_to_jalali(story.fields.created)
        real_start_date_jalali = await self._get_real_start_date_jalali(story)
        complete_date_jalali = await self._get_complete_date_jalali(story)
        weeks_passed = await self._calculate_weeks_passed(story.fields.created)
        
        return CurrentStoryItem(
            issue_number=story.key,
            issue_name=story.fields.summary,
            story_status=story_status,
            remaining_hours=remaining_hours,
            priority=priority,
            assignees_abbr=assignees_abbr,
            release=release,
            label_feature=label_feature,
            epic_name=epic_name,
            creation_date_jalali=creation_date_jalali,
            real_start_date_jalali=real_start_date_jalali,
            complete_date_jalali=complete_date_jalali,
            weeks_passed=weeks_passed
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
            
            return 0  # Return 0 instead of None for no remaining time
            
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
    
    async def _convert_to_jalali(self, date_string: Optional[str]) -> Optional[str]:
        """Convert Jira date string to Jalali calendar format.
        
        Args:
            date_string: ISO format date string from Jira
            
        Returns:
            Jalali date string or None
        """
        if not date_string:
            return None
            
        try:
            # Parse the ISO date string
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            
            # Get calendar data for the month
            calendar_json = await self._get_calendar_data(dt.year, dt.month)
            if not calendar_json:
                return None
                
            calendar = JalaliGregorianCalendar(calendar_json)
            
            # Convert to Jalali
            jalali_day = calendar.jalali_from_gregorian(dt.day)
            if jalali_day:
                return f"{calendar._header['jalali']}/{jalali_day:02d}"
            
            return None
            
        except Exception as e:
            LOGGER.warning(f"Failed to convert date {date_string} to Jalali: {e}")
            return None
    
    async def _get_calendar_data(self, year: int, month: int) -> Optional[Dict]:
        """Get calendar data from API for date conversion.
        
        Args:
            year: Gregorian year
            month: Gregorian month
            
        Returns:
            Calendar JSON data or None
        """
        try:
            url = f"https://calendar-api.heydarihamed.ir/api/calendar/{year}/{month}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            LOGGER.warning(f"Failed to get calendar data for {year}/{month}: {e}")
            return None
    
    async def _get_real_start_date_jalali(self, story) -> Optional[str]:
        """Get the real start date (first transition to in-progress) in Jalali.
        
        Args:
            story: Jira story issue
            
        Returns:
            Jalali date string when first moved to in-progress
        """
        try:
            # Get issue with changelog
            full_story = self.task_manager_repository.get_issue_with_expand(
                story.key, "changelog"
            )
            
            if not full_story or not hasattr(full_story, 'changelog'):
                return None
            
            # Look for first transition to "In Progress" status
            for history in full_story.changelog.histories:
                for item in history.items:
                    if (item.field == 'status' and 
                        item.toString and 
                        'progress' in item.toString.lower()):
                        return await self._convert_to_jalali(history.created)
            
            return None
            
        except Exception as e:
            LOGGER.warning(f"Failed to get real start date for story {story.key}: {e}")
            return None
    
    async def _get_complete_date_jalali(self, story) -> Optional[str]:
        """Get the completion date (transition to done) in Jalali.
        
        Args:
            story: Jira story issue
            
        Returns:
            Jalali date string when moved to done
        """
        try:
            # Get issue with changelog
            full_story = self.task_manager_repository.get_issue_with_expand(
                story.key, "changelog"
            )
            
            if not full_story or not hasattr(full_story, 'changelog'):
                return None
            
            # Look for transition to "Done" status
            for history in full_story.changelog.histories:
                for item in history.items:
                    if (item.field == 'status' and 
                        item.toString and 
                        'done' in item.toString.lower()):
                        return await self._convert_to_jalali(history.created)
            
            return None
            
        except Exception as e:
            LOGGER.warning(f"Failed to get complete date for story {story.key}: {e}")
            return None
    
    async def _calculate_weeks_passed(self, created_date: Optional[str]) -> Optional[float]:
        """Calculate weeks passed since creation date.
        
        Args:
            created_date: ISO format creation date string
            
        Returns:
            Number of weeks passed as float
        """
        if not created_date:
            return None
            
        try:
            created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
            now = datetime.now(created_dt.tzinfo)
            delta = now - created_dt
            return round(delta.days / 7.0, 1)
            
        except Exception as e:
            LOGGER.warning(f"Failed to calculate weeks passed for date {created_date}: {e}")
            return None
