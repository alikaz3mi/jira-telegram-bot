import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.use_cases.telegram_commands.get_current_stories import GetCurrentStoriesUseCase


class TestGetCurrentStoriesUseCase(unittest.TestCase):
    """Test suite for GetCurrentStoriesUseCase."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.task_manager_repository = AsyncMock()
        self.current_stories_service = AsyncMock()
        self.use_case = GetCurrentStoriesUseCase(
            task_manager_repository=self.task_manager_repository,
            current_stories_service=self.current_stories_service,
        )
    
    async def test_get_projects_success(self):
        """Test successful project retrieval."""
        # Arrange
        mock_project = MagicMock()
        mock_project.key = "TEST"
        mock_project.name = "Test Project"
        self.task_manager_repository.get_projects.return_value = [mock_project]
        
        # Act
        result = await self.use_case.get_projects()
        
        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "TEST")
        self.assertEqual(result[0]["name"], "Test Project")
        self.task_manager_repository.get_projects.assert_called_once()
    
    async def test_get_projects_empty(self):
        """Test project retrieval with no projects."""
        # Arrange
        self.task_manager_repository.get_projects.return_value = []
        
        # Act
        result = await self.use_case.get_projects()
        
        # Assert
        self.assertEqual(result, [])
        self.task_manager_repository.get_projects.assert_called_once()
    
    async def test_get_sprints_for_project_success(self):
        """Test successful sprint retrieval for project."""
        # Arrange
        project_key = "TEST"
        board_id = 123
        mock_sprint = MagicMock()
        mock_sprint.id = 456
        mock_sprint.name = "Sprint 1"
        mock_sprint.state = "active"
        
        self.task_manager_repository.get_board_id.return_value = board_id
        self.task_manager_repository.get_sprints.return_value = [mock_sprint]
        
        # Act
        result = await self.use_case.get_sprints_for_project(project_key)
        
        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "456")
        self.assertEqual(result[0]["name"], "Sprint 1")
        self.task_manager_repository.get_board_id.assert_called_once_with(project_key)
        self.task_manager_repository.get_sprints.assert_called_once_with(board_id)
    
    async def test_get_sprints_for_project_no_board(self):
        """Test sprint retrieval when no board found."""
        # Arrange
        project_key = "TEST"
        self.task_manager_repository.get_board_id.return_value = None
        
        # Act
        result = await self.use_case.get_sprints_for_project(project_key)
        
        # Assert
        self.assertEqual(result, [])
        self.task_manager_repository.get_board_id.assert_called_once_with(project_key)
        self.task_manager_repository.get_sprints.assert_not_called()
    
    async def test_get_sprints_for_project_inactive_sprints(self):
        """Test sprint retrieval filtering out inactive sprints."""
        # Arrange
        project_key = "TEST"
        board_id = 123
        mock_sprint_active = MagicMock()
        mock_sprint_active.id = 456
        mock_sprint_active.name = "Sprint 1"
        mock_sprint_active.state = "active"
        
        mock_sprint_closed = MagicMock()
        mock_sprint_closed.id = 457
        mock_sprint_closed.name = "Sprint 2"
        mock_sprint_closed.state = "closed"
        
        self.task_manager_repository.get_board_id.return_value = board_id
        self.task_manager_repository.get_sprints.return_value = [mock_sprint_active, mock_sprint_closed]
        
        # Act
        result = await self.use_case.get_sprints_for_project(project_key)
        
        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "456")
        self.assertEqual(result[0]["name"], "Sprint 1")
    
    async def test_generate_current_stories_report_success(self):
        """Test successful current stories report generation."""
        # Arrange
        project_key = "TEST"
        sprint_id = "123"
        
        mock_story = MagicMock()
        mock_story.key = "TEST-1"
        mock_story.fields.summary = "Test Story"
        mock_story.fields.status.name = "In Progress"
        mock_story.fields.priority.name = "High"
        mock_story.fields.labels = ["feature"]
        mock_story.fields.components = []
        mock_story.fields.fixVersions = []
        mock_story.fields.subtasks = []
        
        # Mock epic field
        mock_story.fields.customfield_10100 = "Test Epic"
        
        self.task_manager_repository.search_issues.return_value = [mock_story]
        self.task_manager_repository.get_board_id.return_value = 456
        
        mock_sprint = MagicMock()
        mock_sprint.id = 123
        mock_sprint.name = "Sprint 1"
        self.task_manager_repository.get_sprints.return_value = [mock_sprint]
        
        self.current_stories_service.create_assignee_abbreviation.return_value = "TE"
        
        # Act
        result = await self.use_case.generate_current_stories_report(project_key, sprint_id)
        
        # Assert
        self.assertIsInstance(result, CurrentStoriesReport)
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.sprint_name, "Sprint 1")
        self.assertEqual(len(result.stories), 1)
        
        story_item = result.stories[0]
        self.assertEqual(story_item.issue_number, "TEST-1")
        self.assertEqual(story_item.issue_name, "Test Story")
        self.assertEqual(story_item.epic_name, "Test Epic")
        self.assertEqual(story_item.label_feature, "feature")
        self.assertEqual(story_item.priority, "High")
        self.assertEqual(story_item.story_status, "In Progress")
    
    async def test_generate_current_stories_report_no_stories(self):
        """Test report generation with no stories found."""
        # Arrange
        project_key = "TEST"
        sprint_id = "123"
        
        self.task_manager_repository.search_issues.return_value = []
        self.task_manager_repository.get_board_id.return_value = 456
        
        mock_sprint = MagicMock()
        mock_sprint.id = 123
        mock_sprint.name = "Sprint 1"
        self.task_manager_repository.get_sprints.return_value = [mock_sprint]
        
        # Act
        result = await self.use_case.generate_current_stories_report(project_key, sprint_id)
        
        # Assert
        self.assertIsInstance(result, CurrentStoriesReport)
        self.assertEqual(result.project_key, project_key)
        self.assertEqual(result.sprint_name, "Sprint 1")
        self.assertEqual(len(result.stories), 0)
    
    async def test_create_assignee_abbreviation_success(self):
        """Test assignee abbreviation creation."""
        # Arrange
        assignee_name = "a_kazemi"
        expected_abbr = "AK"
        
        self.current_stories_service.create_assignee_abbreviation.return_value = expected_abbr
        
        # Act
        result = self.current_stories_service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, expected_abbr)
        self.current_stories_service.create_assignee_abbreviation.assert_called_once_with(assignee_name)
    
    async def test_get_assignees_from_subtasks_success(self):
        """Test getting assignees from subtasks."""
        # Arrange
        mock_story = MagicMock()
        mock_subtask = MagicMock()
        mock_subtask.key = "TEST-2"
        mock_story.fields.subtasks = [mock_subtask]
        
        mock_full_subtask = MagicMock()
        mock_full_subtask.fields.assignee.name = "a_kazemi"
        
        self.task_manager_repository.get_issue_with_expand.return_value = mock_full_subtask
        self.current_stories_service.create_assignee_abbreviation.return_value = "AK"
        
        # Act
        result = await self.use_case._get_assignees_from_subtasks(mock_story)
        
        # Assert
        self.assertEqual(result, ["AK"])
        self.task_manager_repository.get_issue_with_expand.assert_called_once_with("TEST-2", "assignee")
        self.current_stories_service.create_assignee_abbreviation.assert_called_once_with("a_kazemi")
    
    async def test_get_assignees_from_subtasks_no_subtasks(self):
        """Test getting assignees when no subtasks exist."""
        # Arrange
        mock_story = MagicMock()
        mock_story.fields.subtasks = None
        
        # Act
        result = await self.use_case._get_assignees_from_subtasks(mock_story)
        
        # Assert
        self.assertEqual(result, [])
        self.task_manager_repository.get_issue_with_expand.assert_not_called()
    
    async def test_get_task_counts_from_subtasks_success(self):
        """Test getting task counts from subtasks with different statuses."""
        # Arrange
        mock_story = MagicMock()
        
        # Create mock subtasks
        mock_subtask_review = MagicMock()
        mock_subtask_review.key = "TEST-2"
        mock_subtask_done = MagicMock()
        mock_subtask_done.key = "TEST-3"
        mock_subtask_other = MagicMock()
        mock_subtask_other.key = "TEST-4"
        
        mock_story.fields.subtasks = [mock_subtask_review, mock_subtask_done, mock_subtask_other]
        
        # Create mock full subtasks with different statuses
        mock_full_subtask_review = MagicMock()
        mock_full_subtask_review.fields.status.name = "In Review"
        
        mock_full_subtask_done = MagicMock()
        mock_full_subtask_done.fields.status.name = "Done"
        
        mock_full_subtask_other = MagicMock()
        mock_full_subtask_other.fields.status.name = "In Progress"
        
        # Mock the repository calls
        def mock_get_issue_with_expand(key, expand):
            if key == "TEST-2":
                return mock_full_subtask_review
            elif key == "TEST-3":
                return mock_full_subtask_done
            elif key == "TEST-4":
                return mock_full_subtask_other
            return None
        
        self.task_manager_repository.get_issue_with_expand.side_effect = mock_get_issue_with_expand
        
        # Act
        result = await self.use_case._get_task_counts_from_subtasks(mock_story)
        
        # Assert
        self.assertEqual(result["review"], 1)
        self.assertEqual(result["done"], 1)
        self.assertEqual(result["other"], 1)
        self.assertEqual(self.task_manager_repository.get_issue_with_expand.call_count, 3)
    
    async def test_get_task_counts_from_subtasks_no_subtasks(self):
        """Test getting task counts when no subtasks exist."""
        # Arrange
        mock_story = MagicMock()
        mock_story.fields.subtasks = None
        
        # Act
        result = await self.use_case._get_task_counts_from_subtasks(mock_story)
        
        # Assert
        self.assertEqual(result["review"], 0)
        self.assertEqual(result["done"], 0)
        self.assertEqual(result["other"], 0)
        self.task_manager_repository.get_issue_with_expand.assert_not_called()


if __name__ == '__main__':
    unittest.main()
