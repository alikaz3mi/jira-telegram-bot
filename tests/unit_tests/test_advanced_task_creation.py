from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import (
    AdvancedTaskCreation,
)


class TestAdvancedTaskCreation(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock task manager repository
        self.mock_jira_repo = Mock()
        self.mock_jira_repo.create_task = Mock()
        self.mock_jira_repo.get_issue = AsyncMock()
        
        # Mock user config
        self.mock_user_config = Mock()
        
        # Mock AI service
        self.mock_ai_service = Mock()
        self.mock_ai_service.run = AsyncMock()
        
        # Mock prompt catalog
        self.mock_prompt_catalog = Mock()
        self.mock_prompt_catalog.get_prompt = AsyncMock()
        
        # Mock story generator
        self.mock_story_generator = Mock()
        self.mock_story_generator.generate = AsyncMock()
        
        # Mock story decomposition service
        self.mock_story_decomposition = Mock()
        self.mock_story_decomposition.decompose_story = AsyncMock()
        
        # Mock subtask creation service
        self.mock_subtask_creation = Mock()
        self.mock_subtask_creation.create_subtasks = AsyncMock()

        # Setup mock project info
        self.projects_info = {
            "RADTHARN": {
                "project_info": {
                    "description": "AI Chat Bot Project",
                    "key": "RADTHARN",
                    "objective": "Create a seamless user experience",
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
                "personas": ["Customer", "Admin", "Developer"],
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
        
        # Mock project info repository
        self.mock_project_info_repo = Mock()
        self.mock_project_info_repo.get_project_info = AsyncMock()

        # Create the class under test with all the mocked dependencies
        self.creator = AdvancedTaskCreation(
            task_manager_repository=self.mock_jira_repo,
            user_config=self.mock_user_config,
            project_info_repository=self.mock_project_info_repo,
            story_generator=self.mock_story_generator,
            story_decomposition_service=self.mock_story_decomposition,
            subtask_creation_service=self.mock_subtask_creation,
        )
        
        # Patch the project_info_repository.get_project_info method to return our mock data
        self.patcher = patch.object(
            self.mock_project_info_repo,
            'get_project_info',
            AsyncMock(return_value=self.projects_info["RADTHARN"])
        )
        self.mock_get_project_info = self.patcher.start()
        
    async def asyncTearDown(self):
        # Stop all patches
        self.patcher.stop()

    async def test_task_decomposition_with_services(self):
        """Test that tasks are properly decomposed using the service interfaces"""
        description = """
        We need to implement a user authentication system with the following features:
        - Login page with email/password
        - Password reset functionality
        - User profile management
        """
        
        # Setup mock story decomposition service response
        mock_story_response = {
            "stories": [
                {
                    "summary": "Implement user authentication system",
                    "description": "As a user, I want to securely authenticate...",
                    "story_points": 8,
                    "priority": "High",
                    "component_tasks": [
                        {
                            "component": "frontend",
                            "subtasks": [
                                {
                                    "summary": "Create login page UI",
                                    "description": "Implement the login form with email/password fields",
                                    "story_points": 3,
                                },
                                {
                                    "summary": "Implement password reset UI",
                                    "description": "Create password reset request form",
                                    "story_points": 2,
                                },
                            ],
                        },
                        {
                            "component": "backend",
                            "subtasks": [
                                {
                                    "summary": "Implement authentication API",
                                    "description": "Create API endpoints for login/logout",
                                    "story_points": 5,
                                },
                                {
                                    "summary": "Implement password reset API",
                                    "description": "Create password reset flow and email sending",
                                    "story_points": 3,
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        
        # Configure the mock story decomposition service
        self.mock_story_decomposition.decompose_story.return_value = mock_story_response
        
        # Mock the create_task response with a proper async mock
        def mock_create_task(task_data):
            return Mock(
                key=f"TEST-{hash(task_data.summary)%100}",
                fields=Mock(
                    issuetype=Mock(name=task_data.task_type),
                    components=[Mock(name=c) for c in (task_data.components or [])],
                ),
            )
        self.mock_jira_repo.create_task = Mock(side_effect=mock_create_task)

        # Call the method under test
        tasks = await self.creator.create_tasks(description, "RADTHARN")

        # Verify that the story decomposition service was called with the correct arguments
        self.mock_story_decomposition.decompose_story.assert_awaited_once()
        call_args = self.mock_story_decomposition.decompose_story.call_args[1]
        self.assertEqual(call_args["description"], description)
        self.assertIn("project_context", call_args)
        self.assertIn("departments", call_args)
        self.assertIn("department_details", call_args)
        self.assertIn("assignee_details", call_args)
        
        # Verify structure of created tasks
        self.assertGreater(len(tasks), 0, "Should create multiple tasks")

        # Check story and subtask creation
        story_tasks = [t for t in tasks if t.fields.issuetype._mock_name == "Story"]
        subtasks = [t for t in tasks if t.fields.issuetype._mock_name == "Sub-task"]

        self.assertGreater(len(story_tasks), 0, "Should have at least one story")
        self.assertGreater(len(subtasks), 0, "Should have at least one subtask")

        # Verify task assignments by department
        frontend_tasks = [
            t for t in tasks if "frontend" in [c._mock_name for c in t.fields.components]
        ]
        backend_tasks = [
            t for t in tasks if "backend" in [c._mock_name for c in t.fields.components]
        ]
        
        self.assertGreater(len(frontend_tasks), 0, "Should have frontend tasks")
        self.assertGreater(len(backend_tasks), 0, "Should have backend tasks")
        
    async def test_create_structured_user_story(self):
        """Test creating a structured user story using the story generator service"""
        description = "Implement user profile page with editable fields"
        project_key = "RADTHARN"
        epic_key = "RADTHARN-123"
        
        # Setup mock user story
        mock_user_story = UserStory(
            project_key=project_key,
            summary="User Profile Management",
            description="""As a user, I want to manage my profile so that I can keep my information up to date.

**Acceptance Criteria:**
- User can view their profile information
- User can edit their name, email, and preferences
- Changes are saved when user clicks 'Save'

**Definition of Done:**
- Code is written and tested
- UI is responsive on all devices
- Changes are persisted to the database""",
            components=["frontend"],
            story_points=5,
            priority="Medium",
        )
        
        # Configure the mock story generator
        self.mock_story_generator.generate.return_value = mock_user_story
        
        # Setup mock issue for epic context
        mock_epic_issue = Mock()
        mock_epic_issue.fields.summary = "User Account Management Epic"
        mock_epic_issue.fields.description = "This epic covers all user account related features"
        self.mock_jira_repo.get_issue = Mock(return_value=mock_epic_issue)
        
        # Mock the create_task response
        self.mock_jira_repo.create_task = Mock(return_value=Mock(
            key="RADTHARN-456"
        ))

        # Call the method under test
        result = await self.creator.create_structured_user_story(
            description=description,
            project_key=project_key,
            epic_key=epic_key,
        )

        # Verify that the story generator was called with the correct arguments
        self.mock_story_generator.generate.assert_awaited_once()
        call_args = self.mock_story_generator.generate.call_args[1]
        self.assertEqual(call_args["raw_text"], description)
        self.assertEqual(call_args["project"], project_key)
        self.assertIn("product_area", call_args)
        self.assertIn("business_goal", call_args)
        self.assertIn("primary_persona", call_args)
        self.assertIn("epic_context", call_args)
        
        # Verify the returned task data
        self.assertEqual(result.summary, mock_user_story.summary)
        self.assertEqual(result.description, mock_user_story.description)
        self.assertEqual(result.components, mock_user_story.components)
        self.assertEqual(result.story_points, mock_user_story.story_points)
        self.assertEqual(result.priority, mock_user_story.priority)
        
        # Verify that the task was created in Jira
        self.mock_jira_repo.create_task.assert_called_once_with(result)

        # No need to duplicate assertions here

    async def test_voice_input_processing(self):
        """Test that voice input is properly processed into tasks"""
        voice_text = (
            "Create a dashboard showing user statistics with graphs and data tables"
        )

        def mock_create_task(task_data):
            return Mock(
                key=f"TEST-{hash(task_data.summary)%100}",
                fields=Mock(
                    issuetype=Mock(name=task_data.task_type),
                    summary=task_data.summary,
                    description=task_data.description,
                    components=[Mock(name=c) for c in (task_data.components or [])],
                ),
            )
        self.mock_jira_repo.create_task = Mock(side_effect=mock_create_task)

        tasks = await self.creator.create_tasks(voice_text, "RADTHARN")

        # Verify appropriate task breakdown
        self.assertGreater(len(tasks), 0, "Should create multiple tasks")

        # Check component distribution
        components_used = set()
        for task in tasks:
            for comp in task.fields.components:
                components_used.add(comp.name)

        self.assertIn("frontend", components_used, "Should have frontend tasks")
        self.assertIn("backend", components_used, "Should have backend tasks")
        
        # Verify that we got appropriate task types
        stories = [t for t in tasks if t.fields.issuetype._mock_name == "Story"]
        subtasks = [t for t in tasks if t.fields.issuetype._mock_name == "Sub-task"]
        
        self.assertGreaterEqual(len(stories), 1, "Should have at least one story")
        self.assertGreaterEqual(len(subtasks), 1, "Should have at least one subtask")
        
        # Verify that tasks have appropriate information
        for task in tasks:
            self.assertIsNotNone(task.fields.summary, "Task should have a summary")
            self.assertIsNotNone(task.fields.description, "Task should have a description")
            self.assertTrue(len(task.fields.components) > 0, "Task should have at least one component")

    async def test_story_point_allocation(self):
        """Test that story points are allocated within valid ranges"""
        description = "Implement OAuth2 authentication with Google and Facebook"

        def mock_create_task(task_data):
            return Mock(
                key=f"TEST-{hash(task_data.summary)%100}",
                fields=Mock(
                    issuetype=Mock(name=task_data.task_type),
                    customfield_10106=task_data.story_points,
                ),
            )
        self.mock_jira_repo.create_task = Mock(side_effect=mock_create_task)

        tasks = await self.creator.create_tasks(description, "RADTHARN")

        for task in tasks:
            points = task.fields.customfield_10106
            if task.fields.issuetype._mock_name == "Story":
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

        async def mock_create_task(task_data):
            return Mock(
                key=f"TEST-{hash(task_data.summary)%100}",
                fields=Mock(
                    issuetype=Mock(name=task_data.task_type),
                    customfield_10106=task_data.story_points,
                    assignee=Mock(name=task_data.assignee) if task_data.assignee else None,
                ),
            )
        self.mock_jira_repo.create_task = AsyncMock(side_effect=mock_create_task)

        tasks = await self.creator.create_tasks(description, "RADTHARN")

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

        def mock_create_task(task_data):
            return Mock(
                key=f"RADTHARN-{hash(task_data.summary)%1000}",
                fields=Mock(
                    summary=task_data.summary,
                    description=task_data.description,
                    issuetype=Mock(name=task_data.task_type),
                    customfield_10106=task_data.story_points,
                    components=[Mock(name=c) for c in (task_data.components or [])],
                ),
            )
        self.mock_jira_repo.create_task = Mock(side_effect=mock_create_task)

        tasks = await self.creator.create_tasks(description, "RADTHARN")

        # Verify structure and distribution
        self.assertGreaterEqual(len(tasks), 4, "Should create multiple tasks")

        stories = [t for t in tasks if t.fields.issuetype._mock_name == "Story"]
        subtasks = [t for t in tasks if t.fields.issuetype._mock_name == "Sub-task"]

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

    async def test_create_subtasks(self):
        """Test creating subtasks for an existing story using the subtask creation service"""
        description = "Add pagination to the existing user list table"
        project_key = "RADTHARN"
        parent_story_key = "RADTHARN-789"
        
        # Setup mock subtasks response
        mock_subtasks_response = {
            "subtasks": [
                {
                    "summary": "Implement backend pagination API",
                    "description": "Create pagination endpoints with limit and offset parameters",
                    "story_points": 3,
                    "component": "backend",
                },
                {
                    "summary": "Implement frontend pagination UI",
                    "description": "Add pagination controls to the user list table",
                    "story_points": 2,
                    "component": "frontend",
                },
                {
                    "summary": "Write pagination integration tests",
                    "description": "Test pagination end-to-end with backend and frontend",
                    "story_points": 1,
                    "component": "backend",
                },
            ],
        }
        
        # Configure the mock subtask creation service
        self.mock_subtask_creation.create_subtasks.return_value = mock_subtasks_response
        
        # Mock the create_task response with a proper async mock
        def mock_create_task(task_data):
            return Mock(
                key=f"TEST-{hash(task_data.summary)%100}",
                fields=Mock(
                    issuetype=Mock(name=task_data.task_type),
                    components=[Mock(name=c) for c in (task_data.components or [])],
                ),
            )
        self.mock_jira_repo.create_task = Mock(side_effect=mock_create_task)

        # Call the method under test
        tasks = await self.creator.create_tasks(
            description=description,
            project_key=project_key,
            parent_story_key=parent_story_key,
            task_type="subtask",
        )

        # Verify that the subtask creation service was called with the correct arguments
        self.mock_subtask_creation.create_subtasks.assert_awaited_once()
        call_args = self.mock_subtask_creation.create_subtasks.call_args[1]
        self.assertEqual(call_args["description"], description)
        self.assertIn("project_context", call_args)
        self.assertIn("departments", call_args)
        self.assertIn("department_details", call_args)
        self.assertIn("assignee_details", call_args)
        
        # Verify structure of created tasks
        self.assertEqual(len(tasks), 3, "Should create exactly 3 subtasks")
        
        # All tasks should be subtasks
        for task in tasks:
            self.assertEqual(task.fields.issuetype._mock_name, "Sub-task", "All tasks should be subtasks")
        
        # Verify component distribution
        frontend_tasks = [t for t in tasks if any(comp._mock_name == "frontend" for comp in t.fields.components)]
        backend_tasks = [t for t in tasks if any(comp._mock_name == "backend" for comp in t.fields.components)]
        
        self.assertEqual(len(frontend_tasks), 1, "Should have 1 frontend subtask")
        self.assertEqual(len(backend_tasks), 2, "Should have 2 backend subtasks")

    async def test_story_decomposition_direct_call(self):
        """Test direct use of story decomposition service"""
        description = "Create a user profile edit page with avatar upload"
        project_key = "RADTHARN"
        
        # Setup mock story decomposition response
        mock_story_response = {
            "stories": [
                {
                    "summary": "User Profile Edit Page",
                    "description": "As a user, I want to edit my profile details...",
                    "story_points": 8,
                    "priority": "Medium",
                    "component_tasks": [
                        {
                            "component": "frontend",
                            "subtasks": [
                                {
                                    "summary": "Create profile edit form UI",
                                    "description": "Implement form with all user fields",
                                    "story_points": 3,
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Configure the mock services
        self.mock_story_decomposition.decompose_story.return_value = mock_story_response
        
        # Create a sample project info dictionary
        project_info = self.projects_info["RADTHARN"]
        
        # Call the story decomposition service directly
        result = await self.mock_story_decomposition.decompose_story(
            description=description,
            project_context=project_info["project_info"]["description"],
            departments=", ".join(project_info["departments"].keys()),
            department_details=self.creator._format_department_details(project_info),
            assignee_details=self.creator._format_assignee_details(project_info)
        )
        
        # Verify that the story decomposition service was called with correct arguments
        self.mock_story_decomposition.decompose_story.assert_awaited_once()
        call_args = self.mock_story_decomposition.decompose_story.call_args[1]
        self.assertEqual(call_args["description"], description)
        self.assertEqual(call_args["project_context"], "AI Chat Bot Project")
        self.assertEqual(call_args["departments"], "frontend, backend")
        
        # Verify that the result contains the expected structure
        self.assertIn("stories", result)
        self.assertEqual(len(result["stories"]), 1)
        self.assertEqual(result["stories"][0]["summary"], "User Profile Edit Page")
        self.assertEqual(result["stories"][0]["story_points"], 8)
        
        # Verify component tasks
        component_tasks = result["stories"][0]["component_tasks"]
        self.assertEqual(len(component_tasks), 1)
        self.assertEqual(component_tasks[0]["component"], "frontend")
        
        # Verify subtasks
        subtasks = component_tasks[0]["subtasks"]
        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0]["summary"], "Create profile edit form UI")

    async def test_task_assignment_algorithm(self):
        """Test the task assignment algorithm for assigning tasks to appropriate team members"""
        project_info = self.projects_info["RADTHARN"]
        
        # Create a mock task structure to test the assignment logic
        tasks_data = {
            "stories": [
                {
                    "summary": "Complex Feature Implementation",
                    "description": "Implement a complex feature requiring senior expertise",
                    "story_points": 8,
                    "priority": "High",
                    "component_tasks": [
                        {
                            "component": "frontend",
                            "subtasks": [
                                {
                                    "summary": "Implement complex UI component",
                                    "description": "Create a complex UI component with state management",
                                    "story_points": 5,
                                },
                                {
                                    "summary": "Implement simple styling",
                                    "description": "Add CSS styling to the component",
                                    "story_points": 2,
                                },
                            ],
                        },
                        {
                            "component": "backend",
                            "subtasks": [
                                {
                                    "summary": "Implement complex API endpoint",
                                    "description": "Create a sophisticated API endpoint with validation",
                                    "story_points": 6,
                                },
                                {
                                    "summary": "Write basic unit tests",
                                    "description": "Write simple unit tests for the API",
                                    "story_points": 1,
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        
        # Call the _assign_tasks method
        result = self.creator._assign_tasks(tasks_data, project_info)
        
        # Verify assignments were made based on complexity (story points)
        for story in result["stories"]:
            for comp_task in story["component_tasks"]:
                component = comp_task["component"]
                for subtask in comp_task["subtasks"]:
                    # High story point tasks should go to senior developers
                    if subtask["story_points"] >= 5:
                        if component == "frontend":
                            self.assertEqual(
                                subtask.get("assignee"), 
                                "frontend_lead",
                                "Complex frontend tasks should be assigned to frontend_lead"
                            )
                        elif component == "backend":
                            self.assertEqual(
                                subtask.get("assignee"), 
                                "backend_lead",
                                "Complex backend tasks should be assigned to backend_lead"
                            )
                    # Low story point tasks can go to any dev, including junior devs
                    else:
                        if component == "backend" and subtask.get("assignee") == "junior_dev":
                            self.assertLessEqual(
                                subtask["story_points"], 
                                3,
                                "Junior devs should only be assigned simple tasks"
                            )
    
    async def test_error_handling_with_invalid_project(self):
        """Test that proper error handling occurs when an invalid project is specified"""
        description = "Create a simple feature"
        invalid_project_key = "NONEXISTENT"
        
        # Configure project info repository to raise an exception
        self.mock_project_info_repo.get_project_info.side_effect = KeyError(f"Project {invalid_project_key} not found")
        
        # Verify that the method raises an appropriate exception
        with self.assertRaises(Exception) as context:
            await self.creator.create_tasks(description, invalid_project_key)
        
        # Verify that the exception message mentions the invalid project key
        self.assertIn(invalid_project_key, str(context.exception))
    
    async def test_error_handling_missing_parent_story(self):
        """Test error handling when creating subtasks without a parent story"""
        description = "Implement new feature components"
        project_key = "RADTHARN"
        
        # Verify that trying to create subtasks without a parent story raises an error
        with self.assertRaises(ValueError) as context:
            await self.creator.create_tasks(
                description=description,
                project_key=project_key,
                parent_story_key=None,
                task_type="subtask"
            )
            
        self.assertIn("Parent story key is required", str(context.exception))
