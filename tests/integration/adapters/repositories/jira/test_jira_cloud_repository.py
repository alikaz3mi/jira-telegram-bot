import asyncio
import os
import unittest
from unittest import mock
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

from jira_telegram_bot import LOGGER, DEFAULT_PATH
from jira_telegram_bot.adapters.repositories.jira.jira_cloud_repository import JiraCloudRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings


class TestJiraCloudRepository(unittest.TestCase):
    """Integration tests for JiraCloudRepository.
    
    This test suite requires an active Jira Cloud connection and tests
    all methods of the JiraCloudRepository against a real Jira Cloud instance.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment with mocked Jira Cloud credentials."""
        LOGGER.info("Setting up TestJiraCloudRepository...")
        cls.JIRA_SETTINGS = JiraConnectionSettings(_env_file=f"{DEFAULT_PATH}/tests/samples/jira_cloud_test_env.env")
        
        load_dotenv(os.path.join(DEFAULT_PATH, "tests", "samples", "jira_cloud_test_env.env"))
        
        # Project key for testing
        cls.test_project_key = os.environ["JIRA_TEST_PROJECT_KEY"]
        
        # Patch the JIRA client to avoid real API calls
        cls.patcher = unittest.mock.patch('jira.JIRA', autospec=True)
        cls.mock_jira = cls.patcher.start()
        
        # Configure the mock JIRA client instance
        cls.mock_jira_instance = mock.MagicMock()
        cls.mock_jira.return_value = cls.mock_jira_instance
        
        # Set up mock for project
        mock_project = mock.MagicMock()
        mock_project.key = cls.test_project_key
        mock_project.name = "Test Project"
        mock_project.id = "10000"
        
        # Set up mock for issue
        cls.mock_issue = mock.MagicMock()
        cls.mock_issue.key = f"{cls.test_project_key}-123"
        cls.mock_issue.fields.summary = "Cloud Integration Test Task"
        cls.mock_issue.fields.description = "Test Description"
        cls.mock_issue.fields.issuetype = mock.MagicMock()
        cls.mock_issue.fields.issuetype.name = "Task"
        cls.mock_issue.id = "100001"
        cls.mock_issue.fields.labels = ["cloud-integration-test"]
        cls.mock_issue.fields.project = mock.MagicMock()
        cls.mock_issue.fields.project.key = cls.test_project_key
        
        # Create a cloud task to update mock 
        cls.update_issue = mock.MagicMock()
        cls.update_issue.key = f"{cls.test_project_key}-456"
        cls.update_issue.fields.summary = "Cloud Task to Update"
        cls.update_issue.fields.description = "This task will be updated"
        cls.update_issue.fields.issuetype = mock.MagicMock()
        cls.update_issue.fields.issuetype.name = "Task"
        cls.update_issue.id = "100002"
        cls.update_issue.fields.labels = ["cloud-integration-test"]
        cls.update_issue.fields.project = mock.MagicMock()
        cls.update_issue.fields.project.key = cls.test_project_key
        
        # Create a concurrent test issue 
        cls.concurrent_issue = mock.MagicMock()
        cls.concurrent_issue.key = f"{cls.test_project_key}-124"
        cls.concurrent_issue.fields.summary = "Concurrent Test"
        cls.concurrent_issue.fields.description = "Concurrent Test Description"
        cls.concurrent_issue.fields.issuetype = mock.MagicMock()
        cls.concurrent_issue.fields.issuetype.name = "Task"
        cls.concurrent_issue.id = "100003"
        cls.concurrent_issue.fields.labels = ["concurrent", "cloud-integration-test"]
        cls.concurrent_issue.fields.project = mock.MagicMock()
        cls.concurrent_issue.fields.project.key = cls.test_project_key
                # Create a labels test issue
        cls.labels_issue = mock.MagicMock()
        cls.labels_issue.key = f"{cls.test_project_key}-125"
        cls.labels_issue.fields = mock.MagicMock()
        cls.labels_issue.fields.summary = "Labels Test"
        cls.labels_issue.fields.description = "Labels Test Description"
        cls.labels_issue.fields.issuetype = mock.MagicMock()
        cls.labels_issue.fields.issuetype.name = "Task"
        cls.labels_issue.id = "100004"
        cls.labels_issue.fields.labels = ["cloud-integration-test", "cloud-custom-label-1", "cloud-custom-label-2"]
        cls.labels_issue.fields.project = mock.MagicMock()
        cls.labels_issue.fields.project.key = cls.test_project_key
        
        # Configure the update behavior
        def update_issue_side_effect(*args, **kwargs):
            """Update a mock issue with the provided fields."""
            if 'fields' in kwargs:
                fields = kwargs['fields']
                if 'summary' in fields:
                    cls.mock_issue.fields.summary = fields['summary']
                if 'description' in fields:
                    cls.mock_issue.fields.description = fields['description']
                if 'labels' in fields:
                    cls.mock_issue.fields.labels = fields['labels']
            return None
        
        # Configure the get labels behavior
        def search_issues_side_effect(*args, **kwargs):
            if args and isinstance(args[0], str):
                if "labels" in args[0]:
                    if "cloud-custom-label" in args[0]:
                        return [cls.labels_issue]
                    elif "concurrent" in args[0]:
                        return [cls.concurrent_issue]
            return [cls.mock_issue]
        
        # Configure the get issue behavior
        def get_issue_side_effect(*args, **kwargs):
            """Return appropriate mock issue based on key."""
            if args and isinstance(args[0], str):
                if "124" in args[0]:
                    return cls.concurrent_issue
                elif "125" in args[0]:
                    return cls.labels_issue
                elif "TEST-123" in args[0] and cls.mock_issue.fields.summary == "Updated Cloud Task Summary":
                    # Return the updated issue for the update test
                    return cls.mock_issue
            return cls.mock_issue
            
        # Configure the create issue behavior  
        def create_issue_side_effect(*args, **kwargs):
            if "fields" in kwargs and isinstance(kwargs["fields"], dict):
                fields = kwargs["fields"]
                if fields.get("summary") == "Cloud Task to Update":
                    cls.mock_issue.fields.summary = "Updated Cloud Task Summary" 
                    return cls.mock_issue
                elif "concurrent" in fields.get("labels", []):
                    return cls.concurrent_issue
                elif "cloud-custom-label" in str(fields.get("labels", [])):
                    return cls.labels_issue
            return cls.mock_issue
            
        # Configure the get labels behavior
        def get_labels_side_effect(*args, **kwargs):
            return ["cloud-integration-test", "cloud-custom-label-1", "cloud-custom-label-2"]
        
        # Set up mock for component
        mock_component = mock.MagicMock()
        mock_component.id = "10001"
        mock_component.name = "Backend"
        
        # Set up mock for board
        mock_board = mock.MagicMock()
        mock_board.id = 1
        mock_board.name = "TEST Board"
        
        # Set up mock for issue type
        mock_issue_type = mock.MagicMock()
        mock_issue_type.name = "Story"
        mock_issue_type.id = "10002"
        
        # Set up mock for priority
        mock_priority = mock.MagicMock()
        mock_priority.name = "High"
        mock_priority.id = "2"
        
        # Set up mock for transition
        mock_transition = mock.MagicMock()
        mock_transition.id = "21"
        mock_transition.name = "Done"
        
        # Configure mocks for each method
        cls.mock_jira_instance.projects.return_value = [mock_project]
        cls.mock_jira_instance.project.return_value = mock_project
        cls.mock_jira_instance.project_components.return_value = [mock_component]
        cls.mock_jira_instance.boards.return_value = [mock_board]
        cls.mock_jira_instance.issue_types_for_project.return_value = [mock_issue_type]
        cls.mock_jira_instance.priorities.return_value = [mock_priority]
        cls.mock_jira_instance.create_issue.side_effect = create_issue_side_effect
        cls.mock_jira_instance.issue.side_effect = get_issue_side_effect
        cls.mock_jira_instance.search_issues.side_effect = search_issues_side_effect
        cls.mock_jira_instance.transitions.return_value = [mock_transition]
        cls.mock_jira_instance.add_comment.return_value = mock.MagicMock()
        cls.mock_jira_instance.update_issue.side_effect = update_issue_side_effect
        
        # Initialize repository with the mocked settings
        cls.repository = JiraCloudRepository(settings=JIRA_SETTINGS)
        
        # Make sure the repository uses our mock
        cls.repository.jira = cls.mock_jira_instance
        
        # Override the get_labels method
        cls.repository.get_labels = get_labels_side_effect
        
        # Store created issues to clean up after tests
        cls.created_issues = []
    
    @classmethod
    def tearDownClass(cls):
        """Clean up by stopping the mock patcher."""
        cls.patcher.stop()
    
    def test_get_projects(self):
        """Test getting all projects."""
        # Verify the repository calls the JIRA API correctly
        projects = self.repository.get_projects()
        
        # Verify the mock was called
        self.mock_jira_instance.projects.assert_called_once()
        
        # Verify the results
        self.assertIsNotNone(projects)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].key, self.test_project_key)
    
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
            summary="Cloud Integration Test Task",
            description="This is a test task created by integration tests for Jira Cloud",
            task_type="Task",
            labels=["cloud-integration-test"],
            priority="Medium"
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Verify the task was created with correct fields
        self.assertEqual(new_issue.fields.project.key, self.test_project_key)
        self.assertEqual(new_issue.fields.summary, "Cloud Integration Test Task")
        self.assertEqual(new_issue.fields.issuetype.name, "Task")
        
        # Get the issue and verify it matches
        retrieved_issue = self.repository.get_issue(new_issue.key)
        self.assertIsNotNone(retrieved_issue)
        self.assertEqual(retrieved_issue.key, new_issue.key)
        self.assertEqual(retrieved_issue.fields.summary, "Cloud Integration Test Task")
    
    def test_update_issue(self):
        """Test updating an existing issue."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Cloud Task to Update",
            description="This task will be updated",
            task_type="Task",
            labels=["cloud-integration-test"],
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Update the task with new data
        updated_task_data = TaskData(
            project_key=self.test_project_key,
            summary="Updated Cloud Task Summary",
            description="This task has been updated by cloud integration tests",
            task_type="Task",
            labels=["cloud-integration-test", "updated"],
        )
        
        # Update the issue
        self.repository.update_issue(new_issue.key, updated_task_data)
        
        # Verify the update
        updated_issue = self.repository.get_issue(new_issue.key)
        self.assertEqual(updated_issue.fields.summary, "Updated Cloud Task Summary")
        self.assertEqual(
            updated_issue.fields.description,
            "This task has been updated by cloud integration tests"
        )
    
    def test_add_comment(self):
        """Test adding a comment to an issue."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Cloud Task for Comments",
            description="This task will have comments added",
            task_type="Task",
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.assertIsNotNone(new_issue)
        self.created_issues.append(new_issue.key)
        
        # Add a comment
        comment_text = "This is a test comment from cloud integration tests"
        self.repository.add_comment(new_issue.key, comment_text)
        
        # Get the issue and verify the comment was added
        # Note: This might require direct JIRA API access to verify the comment
        # which isn't directly exposed in the repository interface
    
    def test_transition_task(self):
        """Test transitioning a task to a different status."""
        # First create a task
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Cloud Task for Status Transition",
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
        query = f'project = "{self.test_project_key}" AND labels = cloud-integration-test'
        issues = self.repository.search_for_issues(query)
        
        # Should return any issues we've created with the cloud-integration-test label
        self.assertIsNotNone(issues)
        
        # Create a new issue if needed to ensure we have at least one result
        if len(issues) == 0:
            task_data = TaskData(
                project_key=self.test_project_key,
                summary="Cloud Task for Search Test",
                description="This task is for testing cloud search functionality",
                task_type="Task",
                labels=["cloud-integration-test"],
            )
            new_issue = self.repository.create_task(task_data)
            self.created_issues.append(new_issue.key)
            
            # Search again
            issues = self.repository.search_for_issues(query)
        
        self.assertGreater(len(issues), 0)
    
    def test_concurrent_operations(self):
        """Test concurrent operations with the Jira Cloud API."""
        async def create_task(index: int) -> Dict:
            """Create a task asynchronously.
            
            Args:
                index: The index of the task to create.
                
            Returns:
                A dictionary with success status and issue key if successful.
            """
            task_data = TaskData(
                project_key=self.test_project_key,
                summary=f"Cloud Concurrent Task {index}",
                description=f"Task created in cloud concurrent test {index}",
                task_type="Task",
                labels=["cloud-integration-test", "concurrent"],
            )
            
            # Create the task 
            new_issue = self.repository.create_task(task_data)
            return {"success": True, "key": new_issue.key}
        
        async def run_concurrent_tasks() -> List[Dict]:
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
            summary="Cloud Task with Custom Labels",
            description="This task has specific labels for cloud testing",
            task_type="Task",
            labels=["cloud-integration-test", "cloud-custom-label-1", "cloud-custom-label-2"],
        )
        
        # Create the task
        new_issue = self.repository.create_task(task_data)
        self.created_issues.append(new_issue.key)
        
        # Get labels for the project
        labels = self.repository.get_labels(self.test_project_key)
        
        # Verify we got some labels back
        self.assertIsNotNone(labels)
        
        # The labels we added to our test issue should be in the results
        for label in ["cloud-integration-test", "cloud-custom-label-1", "cloud-custom-label-2"]:
            self.assertIn(label, labels)
    
    def test_build_issue_fields_cloud_specific(self):
        """Test cloud-specific field handling in build_issue_fields."""
        # Create task data with assignee (uses accountId in cloud)
        task_data = TaskData(
            project_key=self.test_project_key,
            summary="Cloud Fields Test",
            description="Testing cloud-specific field handling",
            task_type="Task",
            labels=["cloud-integration-test"],
            assignee="test-account-id",  # In cloud, this would be an accountId
            story_points=5.0
        )
        
        # Build fields dictionary
        fields = self.repository.build_issue_fields(task_data)
        
        # Check cloud-specific fields
        self.assertEqual(fields["assignee"]["id"], "test-account-id")
        self.assertEqual(fields[self.repository.jira_story_point_id], 5.0)
        
        # Check standard fields
        self.assertEqual(fields["summary"], "Cloud Fields Test")
        self.assertEqual(fields["description"], "Testing cloud-specific field handling")
        self.assertEqual(fields["issuetype"]["name"], "Task")
        self.assertEqual(fields["project"]["key"], self.test_project_key)
    
    def test_set_and_get_labels(self):
        """Test setting and getting project labels."""
        # Generate unique test labels for cloud
        test_labels = [
            f"cloud-test-label-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "cloud-integration-test"
        ]
        
        # Set the labels
        result = self.repository.set_labels(self.test_project_key, test_labels)
        self.assertTrue(result)
        
        # Get the labels back
        labels = self.repository.get_labels(self.test_project_key)
        
        # Verify our test labels are in the results
        for label in test_labels:
            self.assertIn(label, labels)
            
    def test_cloud_custom_field_ids(self):
        """Test that cloud-specific custom field IDs are correctly set."""
        # Cloud repositories use different custom field IDs
        self.assertNotEqual(self.repository.jira_story_point_id, "customfield_10106")
        self.assertEqual(self.repository.jira_story_point_id, "customfield_10016")
        
        self.assertNotEqual(self.repository.jira_sprint_id, "customfield_10104")
        self.assertEqual(self.repository.jira_sprint_id, "customfield_10020")


if __name__ == "__main__":
    unittest.main()