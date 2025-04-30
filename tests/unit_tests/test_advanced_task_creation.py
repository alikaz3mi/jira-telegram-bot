from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import AdvancedTaskCreation


@pytest.fixture
def mock_jira_repo():
    repo = Mock()
    repo.create_task = AsyncMock()
    return repo


@pytest.fixture
def mock_user_config():
    config = Mock()
    return config


@pytest.fixture
def projects_info():
    return {
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


@pytest.mark.asyncio
async def test_task_decomposition(mock_jira_repo, mock_user_config, projects_info):
    creator = AdvancedTaskCreation(mock_jira_repo, mock_user_config)

    description = """
    We need to implement a user authentication system with the following features:
    - Login page with email/password
    - Password reset functionality
    - User profile management
    """

    # Mock the create_task response
    mock_jira_repo.create_task.side_effect = lambda x: Mock(
        key=f"TEST-{hash(x.summary)%100}",
    )

    # Test task creation
    tasks = await creator.create_tasks(description, "PARSCHAT")

    # Verify structure
    assert len(tasks) > 0

    # Check that story and subtasks were created
    story_tasks = [t for t in tasks if t.fields.issuetype.name == "Story"]
    subtasks = [t for t in tasks if t.fields.issuetype.name == "Sub-task"]

    assert len(story_tasks) > 0
    assert len(subtasks) > 0

    # Verify task assignments by department
    frontend_tasks = [
        t for t in tasks if "frontend" in [c.name for c in t.fields.components]
    ]
    backend_tasks = [
        t for t in tasks if "backend" in [c.name for c in t.fields.components]
    ]

    assert len(frontend_tasks) > 0, "Should have frontend tasks"
    assert len(backend_tasks) > 0, "Should have backend tasks"


@pytest.mark.asyncio
async def test_voice_input_processing(mock_jira_repo, mock_user_config):
    creator = AdvancedTaskCreation(mock_jira_repo, mock_user_config)

    # Mock voice transcription result
    voice_text = (
        "Create a dashboard showing user statistics with graphs and data tables"
    )

    tasks = await creator.create_tasks(voice_text, "PARSCHAT")

    # Verify appropriate task breakdown
    assert len(tasks) > 0

    # Check component distribution
    components_used = set()
    for task in tasks:
        for comp in task.fields.components:
            components_used.add(comp.name)

    # Should involve both frontend and backend
    assert "frontend" in components_used
    assert "backend" in components_used


@pytest.mark.asyncio
async def test_story_point_allocation(mock_jira_repo, mock_user_config):
    creator = AdvancedTaskCreation(mock_jira_repo, mock_user_config)

    description = "Implement OAuth2 authentication with Google and Facebook"

    tasks = await creator.create_tasks(description, "PARSCHAT")

    # Check story points allocation
    for task in tasks:
        if task.fields.issuetype.name == "Story":
            assert (
                1 <= task.fields.customfield_10106 <= 13
            ), "Story points should be between 1-13"
        else:
            assert (
                0.5 <= task.fields.customfield_10106 <= 8
            ), "Subtask points should be between 0.5-8"


@pytest.mark.asyncio
async def test_skill_based_assignment(mock_jira_repo, mock_user_config):
    creator = AdvancedTaskCreation(mock_jira_repo, mock_user_config)

    description = "Implement complex data processing pipeline with ML models"

    tasks = await creator.create_tasks(description, "PARSCHAT")

    # Check that complex tasks are assigned to senior developers
    for task in tasks:
        if task.fields.customfield_10106 >= 5:  # High story points
            assert task.fields.assignee.name in [
                "frontend_lead",
                "backend_lead",
            ], "Complex tasks should be assigned to senior developers"
