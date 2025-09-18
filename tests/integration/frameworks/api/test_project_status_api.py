"""Integration tests for project status API."""

import unittest
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.entities.api_schemas.project_status import (
    ProjectDetailResponse, 
    ProjectListResponse,
    ProjectStatusUpdateRequest,
    ProjectStatusUpdateResponse,
    ProjectSummary, 
    TaskStatusCount
)
from jira_telegram_bot.frameworks.api.endpoints.project_status import ProjectStatusEndpoint
from jira_telegram_bot.use_cases.project_status.get_project_status_use_case import GetProjectStatusUseCase
from jira_telegram_bot.use_cases.project_status.update_project_tracking_use_case import UpdateProjectTrackingUseCase


class TestProjectStatusAPI(unittest.TestCase):
    """Integration tests for project status API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Create a test FastAPI app
        cls.app = FastAPI()
        
        # Create mock use cases
        cls.get_project_status_use_case = MagicMock(spec=GetProjectStatusUseCase)
        cls.update_project_tracking_use_case = MagicMock(spec=UpdateProjectTrackingUseCase)
        
        # Create project status endpoint and add its router
        project_status_endpoint = ProjectStatusEndpoint(
            get_project_status_use_case=cls.get_project_status_use_case,
            update_project_tracking_use_case=cls.update_project_tracking_use_case
        )
        
        # Add the router with api/v1 prefix to match test expectations
        cls.app.include_router(project_status_endpoint.create_rest_api_route(), prefix="/api/v1")
        
        # Create a test client
        cls.client = TestClient(cls.app)
    
    def test_get_projects_endpoint(self):
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
        
        self.get_project_status_use_case.get_project_list.return_value = project_summaries
        
        # Act
        response = self.client.get("/api/v1/projects/")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("projects", data)
        self.assertEqual(len(data["projects"]), 2)
        self.assertEqual(data["projects"][0]["key"], "TEST")
        self.assertEqual(data["projects"][1]["key"], "DEMO")
    
    def test_get_project_detail_endpoint(self):
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
        
        self.get_project_status_use_case.get_project_detail.return_value = project_detail
        
        # Act
        response = self.client.get("/api/v1/projects/TEST")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("project", data)
        self.assertEqual(data["project"]["key"], "TEST")
        self.assertIn("sprint_data", data)
        self.assertEqual(data["sprint_data"]["name"], "Sprint 1")
        self.assertIn("upcoming_deadlines", data)
        self.assertEqual(len(data["upcoming_deadlines"]), 1)
    
    def test_get_project_detail_not_found(self):
        """Test the GET /projects/{project_key} endpoint for non-existent project."""
        # Arrange
        self.get_project_status_use_case.get_project_detail.return_value = None
        
        # Act
        response = self.client.get("/api/v1/projects/NOTFOUND")
        
        # Assert
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("NOT FOUND", data["detail"].upper())
    
    def test_update_project_tracking_endpoint(self):
        """Test the PUT /projects/{project_key}/tracking endpoint."""
        # Arrange
        self.update_project_tracking_use_case.update_tracking.return_value = {
            "tracking_enabled": True,
            "notification_channel": "123456789"
        }
        
        # Act
        response = self.client.put(
            "/api/v1/projects/TEST/tracking",
            json={"track": True, "notification_channel": "123456789"}
        )
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["project_key"], "TEST")
        self.assertEqual(data["tracking_enabled"], True)
        self.assertEqual(data["notification_channel"], "123456789")
        
        self.update_project_tracking_use_case.update_tracking.assert_called_once_with(
            project_key="TEST", 
            track=True,
            notification_channel="123456789"
        )
    
    def test_update_project_tracking_error(self):
        """Test the PUT /projects/{project_key}/tracking endpoint with error."""
        # Arrange
        self.update_project_tracking_use_case.update_tracking.side_effect = ValueError("Project not found")
        
        # Act
        response = self.client.put(
            "/api/v1/projects/NOTFOUND/tracking",
            json={"track": True}
        )
        
        # Assert
        self.assertEqual(response.status_code, 500)
        data = response.json()
        
        self.assertIn("detail", data)
        self.assertIn("Error updating project tracking", data["detail"])


if __name__ == "__main__":
    unittest.main()
