"""Unit tests for ProjectStatusEndpoint."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.entities.api_schemas.project_status import (
    ProjectDetailResponse,
    ProjectSummary,
    TaskStatusCount,
)
from jira_telegram_bot.frameworks.api.endpoints.project_status import ProjectStatusEndpoint
from jira_telegram_bot.use_cases.project_status.get_project_status_use_case import GetProjectStatusUseCase
from jira_telegram_bot.use_cases.project_status.update_project_tracking_use_case import UpdateProjectTrackingUseCase


class TestProjectStatusEndpoint(unittest.TestCase):
    """Test suite for ProjectStatusEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.get_project_status_use_case = AsyncMock(spec=GetProjectStatusUseCase)
        self.update_project_tracking_use_case = AsyncMock(spec=UpdateProjectTrackingUseCase)
        
        self.endpoint = ProjectStatusEndpoint(
            get_project_status_use_case=self.get_project_status_use_case,
            update_project_tracking_use_case=self.update_project_tracking_use_case
        )
        
        # Create a FastAPI app for testing the endpoint
        self.app = FastAPI()
        self.app.include_router(self.endpoint.create_rest_api_route())
        self.client = TestClient(self.app)
    
    def test_create_rest_api_route(self):
        """Test creating the REST API route."""
        # Act
        router = self.endpoint.create_rest_api_route()
        
        # Assert
        self.assertIsNotNone(router)
        self.assertEqual(router.prefix, "/projects")
        self.assertEqual(router.tags, ["Projects"])
    
    async def _mock_get_project_list(self, limit=None, status=None):
        """Mock for get_project_status_use_case.get_project_list."""
        return [
            ProjectSummary(
                key="TEST",
                name="Test Project",
                task_count=10,
                status_counts=[
                    TaskStatusCount(status="To Do", count=3),
                    TaskStatusCount(status="In Progress", count=4),
                    TaskStatusCount(status="Done", count=3),
                ],
                last_updated=datetime.now()
            ),
            ProjectSummary(
                key="DEMO",
                name="Demo Project",
                task_count=5,
                status_counts=[
                    TaskStatusCount(status="To Do", count=2),
                    TaskStatusCount(status="In Progress", count=1),
                    TaskStatusCount(status="Done", count=2),
                ],
                last_updated=datetime.now()
            )
        ]
    
    def test_get_projects_success(self):
        """Test successful project list retrieval."""
        # Arrange
        self.get_project_status_use_case.get_project_list = AsyncMock(side_effect=self._mock_get_project_list)
        
        # Act
        response = self.client.get("/projects/")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("projects", data)
        self.assertEqual(len(data["projects"]), 2)
        self.assertEqual(data["projects"][0]["key"], "TEST")
        self.assertEqual(data["projects"][1]["key"], "DEMO")
    
    async def _mock_get_project_detail(self, project_key):
        """Mock for get_project_status_use_case.get_project_detail."""
        if project_key == "TEST":
            project_summary = ProjectSummary(
                key="TEST",
                name="Test Project",
                task_count=10,
                status_counts=[
                    TaskStatusCount(status="To Do", count=3),
                    TaskStatusCount(status="In Progress", count=4),
                    TaskStatusCount(status="Done", count=3),
                ],
                last_updated=datetime.now()
            )
            return ProjectDetailResponse(
                project=project_summary,
                sprint_data={"name": "Sprint 1", "startDate": "2025-05-01", "endDate": "2025-05-15"},
                upcoming_deadlines=[{"key": "TEST-1", "summary": "Task 1", "dueDate": "2025-05-20"}]
            )
        return None
    
    def test_get_project_detail_success(self):
        """Test successful project detail retrieval."""
        # Arrange
        self.get_project_status_use_case.get_project_detail = AsyncMock(side_effect=self._mock_get_project_detail)
        
        # Act
        response = self.client.get("/projects/TEST")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("project", data)
        self.assertEqual(data["project"]["key"], "TEST")
        self.assertEqual(data["project"]["name"], "Test Project")
        self.assertEqual(data["sprint_data"]["name"], "Sprint 1")
        self.assertIn("upcoming_deadlines", data)
    
    def test_get_project_detail_not_found(self):
        """Test project detail not found."""
        # Arrange
        self.get_project_status_use_case.get_project_detail = AsyncMock(side_effect=self._mock_get_project_detail)
        
        # Act
        response = self.client.get("/projects/NOTFOUND")
        
        # Assert
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
    
    def test_update_project_tracking_success(self):
        """Test successful project tracking update."""
        # Arrange
        self.update_project_tracking_use_case.update_tracking = AsyncMock(
            return_value={
                "tracking_enabled": True,
                "notification_channel": "12345678"
            }
        )
        
        # Act
        response = self.client.put(
            "/projects/TEST/tracking",
            json={"track": True, "notification_channel": "12345678"}
        )
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_key"], "TEST")
        self.assertEqual(data["tracking_enabled"], True)
        self.assertEqual(data["notification_channel"], "12345678")
        
        self.update_project_tracking_use_case.update_tracking.assert_called_once_with(
            project_key="TEST",
            track=True,
            notification_channel="12345678"
        )
