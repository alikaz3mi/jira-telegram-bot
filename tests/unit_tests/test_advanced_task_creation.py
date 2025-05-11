from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock

from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import (
    AdvancedTaskCreation,
)


class TestAdvancedTaskCreation(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_jira_repo = Mock()
        self.mock_jira_repo.create_task = AsyncMock()

        self.mock_user_config = Mock()

        # Setup mock project info
        self.projects_info = {
            "PARSCHAT": {
                "project_info": {
                    "description": "AI Chat Bot Project",
                    "key": "PARSCHAT",
                },
                "departments": {
                    "frontend": {
                        "description": "Frontend development",
                        "tools": ["Vue.js"],
                        "time_allocation_weekly_hours": 40,
                    },
                    "backend": {
                        "description": "Backend API development",
                        "tools": ["Python", "FastAPI"],
                        "time_allocation_weekly_hours": 40,
                    },
                },
                "components": [
                    {"name": "frontend", "lead": "frontend_lead"},
                    {"name": "backend", "lead": "backend_lead"},
                ],
                "assignees": [
                    {
                        "username": "frontend_lead",
                        "role": "Senior Developer",
                        "department": "frontend",
                    },
                    {
                        "username": "backend_lead",
                        "role": "Senior Developer",
                        "department": "backend",
                    },
                    {
                        "username": "junior_dev",
                        "role": "Junior Developer",
                        "department": "backend",
                    },
                ],
            },
        }

        self.creator = AdvancedTaskCreation(self.mock_jira_repo, self.mock_user_config)

    async def test_task_decomposition(self):
        """Test that tasks are properly decomposed into stories and subtasks"""
        description = """
        We need to implement a user authentication system with the following features:
        - Login page with email/password
        - Password reset functionality
        - User profile management
        """

        # Mock the create_task response
        self.mock_jira_repo.create_task.side_effect = lambda x: Mock(
            key=f"TEST-{hash(x.summary)%100}",
            fields=Mock(
                issuetype=Mock(name=x.task_type),
                components=[Mock(name=c) for c in (x.components or [])],
            ),
        )

        tasks = await self.creator.create_tasks(description, "PARSCHAT")

        # Verify structure
        self.assertGreater(len(tasks), 0, "Should create multiple tasks")

        # Check story and subtask creation
        story_tasks = [t for t in tasks if t.fields.issuetype.name == "Story"]
        subtasks = [t for t in tasks if t.fields.issuetype.name == "Sub-task"]

        self.assertGreater(len(story_tasks), 0, "Should have at least one story")
        self.assertGreater(len(subtasks), 0, "Should have at least one subtask")

        # Verify task assignments by department
        frontend_tasks = [
            t for t in tasks if "frontend" in [c.name for c in t.fields.components]
        ]
        backend_tasks = [
            t for t in tasks if "backend" in [c.name for c in t.fields.components]
        ]

        self.assertGreater(len(frontend_tasks), 0, "Should have frontend tasks")
        self.assertGreater(len(backend_tasks), 0, "Should have backend tasks")

    async def test_voice_input_processing(self):
        """Test that voice input is properly processed into tasks"""
        voice_text = (
            "Create a dashboard showing user statistics with graphs and data tables"
        )

        self.mock_jira_repo.create_task.side_effect = lambda x: Mock(
            key=f"TEST-{hash(x.summary)%100}",
            fields=Mock(
                issuetype=Mock(name=x.task_type),
                components=[Mock(name=c) for c in (x.components or [])],
            ),
        )

        tasks = await self.creator.create_tasks(voice_text, "PARSCHAT")

        # Verify appropriate task breakdown
        self.assertGreater(len(tasks), 0, "Should create multiple tasks")

        # Check component distribution
        components_used = set()
        for task in tasks:
            for comp in task.fields.components:
                components_used.add(comp.name)

        self.assertIn("frontend", components_used, "Should have frontend tasks")
        self.assertIn("backend", components_used, "Should have backend tasks")

    async def test_story_point_allocation(self):
        """Test that story points are allocated within valid ranges"""
        description = "Implement OAuth2 authentication with Google and Facebook"

        self.mock_jira_repo.create_task.side_effect = lambda x: Mock(
            key=f"TEST-{hash(x.summary)%100}",
            fields=Mock(
                issuetype=Mock(name=x.task_type),
                customfield_10106=x.story_points,
            ),
        )

        tasks = await self.creator.create_tasks(description, "PARSCHAT")

        for task in tasks:
            points = task.fields.customfield_10106
            if task.fields.issuetype.name == "Story":
                self.assertTrue(
                    1 <= points <= 13,
                    f"Story points ({points}) should be between 1-13",
                )
            else:
                self.assertTrue(
                    0.5 <= points <= 8,
                    f"Subtask points ({points}) should be between 0.5-8",
                )

    async def test_skill_based_assignment(self):
        """Test that complex tasks are assigned to senior developers"""
        description = "Implement complex data processing pipeline with ML models"

        self.mock_jira_repo.create_task.side_effect = lambda x: Mock(
            key=f"TEST-{hash(x.summary)%100}",
            fields=Mock(
                issuetype=Mock(name=x.task_type),
                customfield_10106=x.story_points,
                assignee=Mock(name=x.assignee) if x.assignee else None,
            ),
        )

        tasks = await self.creator.create_tasks(description, "PARSCHAT")

        for task in tasks:
            if task.fields.customfield_10106 >= 5:  # High story points
                self.assertIn(
                    task.fields.assignee.name,
                    ["frontend_lead", "backend_lead"],
                    "Complex tasks should be assigned to senior developers",
                )

    async def test_ml_project_task_creation(self):
        """Test creation of ML-specific project tasks"""
        description = """
        Implement a machine learning model for chat message classification with the following:
        - Data preprocessing pipeline
        - Model training infrastructure
        - API endpoints for predictions
        - Frontend interfaces for testing the model
        """

        self.mock_jira_repo.create_task.side_effect = lambda x: Mock(
            key=f"PARSCHAT-{hash(x.summary)%1000}",
            fields=Mock(
                summary=x.summary,
                description=x.description,
                issuetype=Mock(name=x.task_type),
                customfield_10106=x.story_points,
                components=[Mock(name=c) for c in (x.components or [])],
            ),
        )

        tasks = await self.creator.create_tasks(description, "PARSCHAT")

        # Verify structure and distribution
        self.assertGreaterEqual(len(tasks), 4, "Should create multiple tasks")

        stories = [t for t in tasks if t.fields.issuetype.name == "Story"]
        subtasks = [t for t in tasks if t.fields.issuetype.name == "Sub-task"]

        self.assertGreaterEqual(len(stories), 1, "Should have at least one story")
        self.assertGreaterEqual(len(subtasks), 3, "Should have multiple subtasks")

        # Check component distribution
        frontend_tasks = [
            t for t in tasks if "frontend" in [c.name for c in t.fields.components]
        ]
        backend_tasks = [
            t for t in tasks if "backend" in [c.name for c in t.fields.components]
        ]

        self.assertGreater(len(frontend_tasks), 0, "Should have frontend tasks for UI")
        self.assertGreater(
            len(backend_tasks),
            0,
            "Should have backend tasks for ML pipeline",
        )
