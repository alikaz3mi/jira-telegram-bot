"""Unit tests for GetProjectStatusUseCase."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.entities.api_schemas.project_status import (
    ProjectDetailResponse,
    ProjectSummary,
    TaskStatusCount,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.project_status.get_project_status_use_case import GetProjectStatusUseCase


class TestGetProjectStatusUseCase(unittest.IsolatedAsyncioTestCase):
    """Test suite for GetProjectStatusUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        try:
            self.task_manager_repository = AsyncMock()
            # Add required methods to the mock
            self.task_manager_repository.get_projects = AsyncMock()
            self.task_manager_repository.get_project = AsyncMock()
            self.task_manager_repository.get_issues_by_status = AsyncMock()
            self.task_manager_repository.get_active_sprint = AsyncMock()
            self.task_manager_repository.get_upcoming_deadlines = AsyncMock()
            
            self.use_case = GetProjectStatusUseCase(
                task_manager_repository=self.task_manager_repository
            )
        except Exception as e:
            import traceback
            print(f"Error in setUp: {e}")
            traceback.print_exc()
    
    async def test_get_project_list_no_filters(self):
        """Test getting project list without filters."""
        # Arrange
        self.task_manager_repository.get_projects.return_value = [
            {"key": "TEST", "name": "Test Project"},
            {"key": "DEMO", "name": "Demo Project"}
        ]
        
        self.task_manager_repository.get_issues_by_status.side_effect = lambda project_key: {
            "To Do": 3,
            "In Progress": 4,
            "Done": 3
        } if project_key == "TEST" else {
            "To Do": 2,
            "In Progress": 1,
            "Done": 2
        }
        
        # Act
        result = await self.use_case.get_project_list()
        
        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].key, "TEST")
        self.assertEqual(result[0].name, "Test Project")
        self.assertEqual(result[0].task_count, 10)
        self.assertEqual(len(result[0].status_counts), 3)
        
        self.assertEqual(result[1].key, "DEMO")
        self.assertEqual(result[1].name, "Demo Project")
        self.assertEqual(result[1].task_count, 5)
        self.assertEqual(len(result[1].status_counts), 3)
        
        self.task_manager_repository.get_projects.assert_called_once()
        self.assertEqual(self.task_manager_repository.get_issues_by_status.call_count, 2)
    
    async def test_get_project_list_with_limit(self):
        """Test getting project list with limit."""
        # Arrange
        self.task_manager_repository.get_projects.return_value = [
            {"key": "TEST", "name": "Test Project"},
            {"key": "DEMO", "name": "Demo Project"},
            {"key": "THIRD", "name": "Third Project"}
        ]
        
        self.task_manager_repository.get_issues_by_status.return_value = {
            "To Do": 3,
            "In Progress": 4,
            "Done": 3
        }
        
        # Act
        result = await self.use_case.get_project_list(limit=2)
        
        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].key, "TEST")
        self.assertEqual(result[1].key, "DEMO")
        
        self.task_manager_repository.get_projects.assert_called_once()
        self.assertEqual(self.task_manager_repository.get_issues_by_status.call_count, 2)
    
    async def test_get_project_list_with_status_filter(self):
        """Test getting project list with status filter."""
        # Arrange
        self.task_manager_repository.get_projects.return_value = [
            {"key": "TEST", "name": "Test Project", "projectStatus": "active"},
            {"key": "DEMO", "name": "Demo Project", "projectStatus": "archived"},
            {"key": "THIRD", "name": "Third Project", "projectStatus": "active"}
        ]
        
        self.task_manager_repository.get_issues_by_status.return_value = {
            "To Do": 3,
            "In Progress": 4,
            "Done": 3
        }
        
        # Act
        result = await self.use_case.get_project_list(status="active")
        
        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].key, "TEST")
        self.assertEqual(result[1].key, "THIRD")
        
        self.task_manager_repository.get_projects.assert_called_once()
        self.assertEqual(self.task_manager_repository.get_issues_by_status.call_count, 2)
    
    async def test_get_project_detail_found(self):
        """Test getting project details when project exists."""
        # Arrange
        self.task_manager_repository.get_project.return_value = {
            "key": "TEST", 
            "name": "Test Project"
        }
        
        self.task_manager_repository.get_issues_by_status.return_value = {
            "To Do": 3,
            "In Progress": 4,
            "Done": 3
        }
        
        self.task_manager_repository.get_active_sprint.return_value = {
            "name": "Sprint 1", 
            "startDate": "2025-05-01", 
            "endDate": "2025-05-15"
        }
        
        self.task_manager_repository.get_upcoming_deadlines.return_value = [
            {"key": "TEST-1", "summary": "Task 1", "dueDate": "2025-05-20"}
        ]
        
        # Act
        result = await self.use_case.get_project_detail("TEST")
        
        # Assert
        self.assertIsInstance(result, ProjectDetailResponse)
        self.assertEqual(result.project.key, "TEST")
        self.assertEqual(result.project.name, "Test Project")
        self.assertEqual(result.project.task_count, 10)
        self.assertIsNotNone(result.sprint_data)
        self.assertEqual(result.sprint_data["name"], "Sprint 1")
        self.assertEqual(len(result.upcoming_deadlines), 1)
        
        self.task_manager_repository.get_project.assert_called_once_with("TEST")
        self.task_manager_repository.get_issues_by_status.assert_called_once_with(project_key="TEST")
        self.task_manager_repository.get_active_sprint.assert_called_once_with("TEST")
        self.task_manager_repository.get_upcoming_deadlines.assert_called_once_with(
            project_key="TEST",
            days=14
        )


if __name__ == "__main__":
    import sys
    try:
        unittest.main()
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()
    
    async def test_get_project_detail_not_found(self):
        """Test getting project details when project does not exist."""
        # Arrange
        self.task_manager_repository.get_project.return_value = None
        
        # Act
        result = await self.use_case.get_project_detail("NOTFOUND")
        
        # Assert
        self.assertIsNone(result)
        self.task_manager_repository.get_project.assert_called_once_with("NOTFOUND")
        self.task_manager_repository.get_issues_by_status.assert_not_called()
        self.task_manager_repository.get_active_sprint.assert_not_called()
        self.task_manager_repository.get_upcoming_deadlines.assert_not_called()
    
    async def test_get_project_detail_with_error(self):
        """Test getting project details with an error."""
        # Arrange
        self.task_manager_repository.get_project.side_effect = Exception("Test error")
        
        # Act/Assert
        with self.assertRaises(Exception) as context:
            await self.use_case.get_project_detail("TEST")
        
        self.assertEqual(str(context.exception), "Test error")
        self.task_manager_repository.get_project.assert_called_once_with("TEST")
