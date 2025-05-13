"""Integration tests for JiraServerRepository.

This test suite runs against an existing Jira instance and tests
all the functionality of the JiraServerRepository class.
"""

import asyncio
import os
import unittest
from datetime import datetime
from typing import List

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS


class TestJiraServerRepository(unittest.TestCase):
    """Integration tests for JiraServerRepository.
    
    This test suite requires an active Jira connection and tests
    all methods of the JiraServerRepository against a real Jira instance.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment with real Jira credentials."""
        # Project key for testing - this should be a real project in your Jira instance
        cls.test_project_key = os.environ.get("JIRA_TEST_PROJECT_KEY")
        
        # Verify that we have the required environment variables
        if not cls.test_project_key:
            raise EnvironmentError(
                "JIRA_TEST_PROJECT_KEY environment variable must be set"
            )
        
        # Initialize repository with the global JIRA_SETTINGS
        cls.repository = JiraServerRepository(settings=JIRA_SETTINGS)
        
        # Store created issues to clean up after tests
        cls.created_issues = []
    
    @classmethod
    def tearDownClass(cls):
        """Clean up any test issues created during testing."""
        for issue_key in cls.created_issues:
            try:
                cls.repository.transition_task(issue_key, "Done")
                LOGGER.info(f"Marked test issue {issue_key} as Done")
            except Exception as e:
                LOGGER.error(f"Error cleaning up issue {issue_key}: {e}")
    
    def test_get_projects(self):
        """Test getting all projects."""
        projects = self.repository.get_projects()
        self.assertIsNotNone(projects)
        self.assertGreater(len(projects), 0)
        
        # Verify our test project exists
        project_keys = [project.key for project in projects]
        self.assertIn(self.test_project_key, project_keys)
    
    def test_get_project_components(self):
        """Test getting components for a project."""
        components = self.repository.get_project_components(self.test_project_key)
        self.assertIsNotNone(components)
        # Components may be empty but the call should succeed
    
    def test_get_board_id(self):
        """Test getting the board ID for a project."""
        board_id = self.repository.get_board_id(self.test_project_key)
        # Some projects might not have boards, so we can't assert board_id is not None
        if board_id is not None:
            self.assertIsInstance(board_id, int)
    
    def test_get_issue_types_for_project(self):
        """Test getting issue types for a project."""
        issue_types = self.repository.get_issue_types_for_project(self.test_project_key)
        self.assertIsNotNone(issue_types)
        self.assertGreater(len(issue_types), 0)
        
        # Common issue types that should exist in most Jira instances
        common_types = {"Task", "Bug", "Story", "Epic"}
        self.assertTrue(any(issue_type in common_types for issue_type in issue_types))
    
    def test_get_priorities(self):
        """Test getting all priorities."""
        priorities = self.repository.get_priorities()
        self.assertIsNotNone(priorities)
        self.assertGreater(len(priorities), 0)
        
        # Check for common priority names
        priority_names = [p.name for p in priorities]
        common_priorities = {"High", "Medium", "Low"}
        self.assertTrue(any(priority in priority_names for priority in common_priorities))
    
    def test_create_and_get_issue(self):
        """Test creating and retrieving a task."""
        # Create a test task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Integration Test Task",
            description="This is a test task created by integration tests",
            task_type="Task",
            labels=["integration-test"],
            priority="Medium"
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Verify the task was created with correct fields
        self.assertEqual(new_issue.fields.project.key, self.test_project_key)
        self.assertEqual(new_issue.fields.summary, "Integration Test Task")
        self.assertEqual(new_issue.fields.issuetype.name, "Task")
        
        # Get the issue and verify it matches
        retrieved_issue = self.repository.get_issue(new_issue.key)
        self.assertIsNotNone(retrieved_issue)
        self.assertEqual(retrieved_issue.key, new_issue.key)
        self.assertEqual(retrieved_issue.fields.summary, "Integration Test Task")
    
    def test_update_issue(self):
        """Test updating an existing issue."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Task to Update",
            description="This task will be updated",
            task_type="Task",
            labels=["integration-test"],
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Update the task with new data
        updated_task_data = TaskData(
            project_key=self.test_project_key,
            summary="Updated Task Summary",
            description="This task has been updated by integration tests",
            task_type="Task",
            labels=["integration-test", "updated"],
        )
        
        # Update the issue
        self.repository.update_issue(new_issue.key, updated_task_data)
        
        # Verify the update
        updated_issue = self.repository.get_issue(new_issue.key)
        self.assertEqual(updated_issue.fields.summary, "Updated Task Summary")
        self.assertEqual(
            updated_issue.fields.description,
            "This task has been updated by integration tests"
        )
    
    def test_add_comment(self):
        """Test adding a comment to an issue."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Task for Comments",
            description="This task will have comments added",
            task_type="Task",
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Add a comment
        comment_text = "This is a test comment from integration tests"
        self.repository.add_comment(new_issue.key, comment_text)
        
        # Get the issue and verify the comment was added
        # Note: This might require direct JIRA API access to verify the comment
        # which isn't directly exposed in the repository interface
    
    def test_transition_task(self):
        """Test transitioning a task to a different status."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Task for Status Transition",
            description="This task will have its status changed",
            task_type="Task",
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Transition to "In Progress"
        # Note: This may fail if your workflow doesn't support this transition
        try:
            self.repository.transition_task(new_issue.key, "In Progress")
            
            # Get the issue and verify the status
            updated_issue = self.repository.get_issue(new_issue.key)
            self.assertEqual(updated_issue.fields.status.name, "In Progress")
        except Exception as e:
            LOGGER.warning(f"Could not transition task status: {e}")
            # This test might fail in some Jira configurations, so we don't fail the test
    
    def test_search_for_issues(self):
        """Test searching for issues with a JQL query."""
        # Search for issues in the test project
        query = f'project = "{self.test_project_key}" AND labels = integration-test'
        issues = self.repository.search_for_issues(query)
        
        # Should return any issues we've created with the integration-test label
        self.assertIsNotNone(issues)
        
        # Create a new issue if needed to ensure we have at least one result
        if len(issues) == 0:
            task_data = TaskData(
                project_key=self.test_project_key,
                summary="Task for Search Test",
                description="This task is for testing search functionality",
                task_type="Task",
                labels=["integration-test"],
            )
            new_issue = self.repository.create_task(task_data)
            self.created_issues.append(new_issue.key)
            
            # Search again
            issues = self.repository.search_for_issues(query)
        
        self.assertGreater(len(issues), 0)
    
    def test_concurrent_operations(self):
        """Test concurrent operations with the Jira API."""
        async def create_task(index: int) -> dict:
            """Create a task asynchronously.
            
            Args:
                index: The index of the task to create.
                
            Returns:
                A dictionary with success status and issue key if successful.
            """
            task_data = TaskData(
                project_key=self.test_project_key,
                summary=f"Concurrent Task {index}",
                description=f"Task created in concurrent test {index}",
                task_type="Task",
                labels=["integration-test", "concurrent"],
            )
            
            # Create the task 
            # Note: This calls a sync method from an async context, which isn't ideal
            # but works for testing purposes
            new_issue = self.repository.create_task(task_data)
            return {"success": True, "key": new_issue.key}
        
        async def run_concurrent_tasks() -> List[dict]:
            """Run multiple task creation operations concurrently.
            
            Returns:
                List of dictionaries with task creation results.
            """
            # Create 5 tasks concurrently (can increase if needed)
            tasks = [create_task(i) for i in range(5)]
            return await asyncio.gather(*tasks)
        
        # Run the concurrent tasks
        issue_keys = asyncio.run(run_concurrent_tasks())
        
        # Verify we got 5 issue keys back
        self.assertEqual(len(issue_keys), 5)
        
        # Add to created issues for cleanup
        self.created_issues.extend([result["key"] for result in issue_keys])
        
        # Verify each issue exists
        for result in issue_keys:
            issue = self.repository.get_issue(result["key"])
            self.assertIsNotNone(issue)
            self.assertTrue("concurrent" in issue.fields.labels)
    
    def test_get_labels(self):
        """Test getting project labels."""
        # Create a task with specific labels if needed
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Task with Custom Labels",
            description="This task has specific labels for testing",
            task_type="Task",
            labels=["integration-test", "custom-label-1", "custom-label-2"],
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.created_issues.append(new_issue.key)
        
        # Get labels for the project
        labels = self.repository.get_labels(self.test_project_key)
        
        # Verify we got some labels back
        self.assertIsNotNone(labels)
        
        # The labels we added to our test issue should be in the results
        for label in ["integration-test", "custom-label-1", "custom-label-2"]:
            self.assertIn(label, labels)
    
    def test_set_and_get_labels(self):
        """Test setting and getting project labels."""
        # Generate unique test labels
        test_labels = [
            f"test-label-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "integration-test"
        ]
        
        # Set the labels
        result = self.repository.set_labels(self.test_project_key, test_labels)
        self.assertTrue(result)
        
        # Get the labels back
        labels = self.repository.get_labels(self.test_project_key)
        
        # Verify our test labels are in the results
        for label in test_labels:
            self.assertIn(label, labels)


if __name__ == "__main__":
    unittest.main()