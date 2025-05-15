"""Integration tests for project status API."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from jira_telegram_bot import app_container
from jira_telegram_bot.entities.api_schemas.project_status import ProjectDetailResponse, ProjectSummary, TaskStatusCount
from jira_telegram_bot.frameworks.api.entry_point import app
from jira_telegram_bot.use_cases.project_status.get_project_status_use_case import GetProjectStatusUseCase
from jira_telegram_bot.use_cases.project_status.update_project_tracking_use_case import UpdateProjectTrackingUseCase


class TestProjectStatusAPI(unittest.TestCase):
    """Integration tests for project status API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Create a test client
        cls.client = TestClient(app)
    
    @patch.object(GetProjectStatusUseCase, 'get_project_list')
    def test_get_projects_endpoint(self, mock_get_project_list):
        """Test the GET /projects/ endpoint."""
        # Arrange
        project_summaries = [
            ProjectSummary(
                key="TEST",
                name="Test Project",
                task_count=10,
                status_counts=[
                    TaskStatusCount(status="To Do", count=3),
                    TaskStatusCount(status="In Progress", count=4),
                    TaskStatusCount(status="Done", count=3)
                ]
            ),
            ProjectSummary(
                key="DEMO",
                name="Demo Project",
                task_count=5,
                status_counts=[
                    TaskStatusCount(status="To Do", count=2),
                    TaskStatusCount(status="In Progress", count=1),
                    TaskStatusCount(status="Done", count=2)
                ]
            )
        ]
        
        mock_get_project_list.return_value = project_summaries
        
        # Act
        response = self.client.get("/projects/")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("projects", data)
        self.assertEqual(len(data["projects"]), 2)
        self.assertEqual(data["projects"][0]["key"], "TEST")
        self.assertEqual(data["projects"][1]["key"], "DEMO")
    
    @patch.object(GetProjectStatusUseCase, 'get_project_detail')
    def test_get_project_detail_endpoint(self, mock_get_project_detail):
        """Test the GET /projects/{project_key} endpoint."""
        # Arrange
        project_summary = ProjectSummary(
            key="TEST",
            name="Test Project",
            task_count=10,
            status_counts=[
                TaskStatusCount(status="To Do", count=3),
                TaskStatusCount(status="In Progress", count=4),
                TaskStatusCount(status="Done", count=3)
            ]
        )
        
        project_detail = ProjectDetailResponse(
            project=project_summary,
            sprint_data={"name": "Sprint 1", "startDate": "2025-05-01", "endDate": "2025-05-15"},
            upcoming_deadlines=[{"key": "TEST-1", "summary": "Task 1", "dueDate": "2025-05-20"}]
        )
        
        mock_get_project_detail.return_value = project_detail
        
        # Act
        response = self.client.get("/projects/TEST")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("project", data)
        self.assertEqual(data["project"]["key"], "TEST")
        self.assertIn("sprint_data", data)
        self.assertEqual(data["sprint_data"]["name"], "Sprint 1")
        self.assertIn("upcoming_deadlines", data)
        self.assertEqual(len(data["upcoming_deadlines"]), 1)
    
    @patch.object(GetProjectStatusUseCase, 'get_project_detail')
    def test_get_project_detail_not_found(self, mock_get_project_detail):
        """Test the GET /projects/{project_key} endpoint for non-existent project."""
        # Arrange
        mock_get_project_detail.return_value = None
        
        # Act
        response = self.client.get("/projects/NOTFOUND")
        
        # Assert
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"])
    
    @patch.object(UpdateProjectTrackingUseCase, 'update_tracking')
    def test_update_project_tracking_endpoint(self, mock_update_tracking):
        """Test the PUT /projects/{project_key}/tracking endpoint."""
        # Arrange
        mock_update_tracking.return_value = {
            "tracking_enabled": True,
            "notification_channel": "123456789"
        }
        
        # Act
        response = self.client.put(
            "/projects/TEST/tracking",
            json={"track": True, "notification_channel": "123456789"}
        )
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["project_key"], "TEST")
        self.assertEqual(data["tracking_enabled"], True)
        self.assertEqual(data["notification_channel"], "123456789")
        
        mock_update_tracking.assert_called_once_with(
            project_key="TEST", 
            track=True,
            notification_channel="123456789"
        )
    
    @patch.object(UpdateProjectTrackingUseCase, 'update_tracking')
    def test_update_project_tracking_error(self, mock_update_tracking):
        """Test the PUT /projects/{project_key}/tracking endpoint with error."""
        # Arrange
        mock_update_tracking.side_effect = ValueError("Project not found")
        
        # Act
        response = self.client.put(
            "/projects/NOTFOUND/tracking",
            json={"track": True}
        )
        
        # Assert
        self.assertEqual(response.status_code, 500)
        data = response.json()
        
        self.assertIn("detail", data)
        self.assertIn("Error updating project tracking", data["detail"])


if __name__ == "__main__":
    unittest.main()
