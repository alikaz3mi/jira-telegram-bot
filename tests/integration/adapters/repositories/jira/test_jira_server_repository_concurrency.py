"""Concurrency integration tests for JiraServerRepository.

This test suite runs high-load concurrent tests against a Jira instance
to verify the repository's behavior under load.
"""

import asyncio
import os
import time
import unittest
from datetime import datetime
from typing import Dict, List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS


class TestJiraServerRepositoryConcurrency(unittest.TestCase):
    """Concurrency integration tests for JiraServerRepository.
    
    This test suite focuses on testing the JiraServerRepository under high load
    with many concurrent operations.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment with real Jira credentials."""
        # Project key for testing - the only environment variable we need
        cls.test_project_key = os.environ.get("JIRA_TEST_PROJECT_KEY")
        
        # Verify that we have the required environment variable
        if not cls.test_project_key:
            raise EnvironmentError(
                "JIRA_TEST_PROJECT_KEY environment variable must be set"
            )
        
        # Initialize repository with the global JIRA_SETTINGS
        cls.repository = JiraServerRepository(settings=JIRA_SETTINGS)
        
        # Store created issues to clean up after tests
        cls.created_issues = []
        
        # Create a unique identifier for this test run to group issues
        cls.test_run_id = f"concurrency-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    @classmethod
    def tearDownClass(cls):
        """Clean up any test issues created during testing."""
        # Create a cleanup task to mark all test issues as Done
        LOGGER.info(f"Cleaning up {len(cls.created_issues)} test issues...")
        
        # Use JQL to find all issues with our test run ID in case we missed some
        try:
            query = f'project = "{cls.test_project_key}" AND labels = "{cls.test_run_id}"'
            additional_issues = cls.repository.search_for_issues(query)
            for issue in additional_issues:
                if issue.key not in cls.created_issues:
                    cls.created_issues.append(issue.key)
        except Exception as e:
            LOGGER.error(f"Error finding additional test issues: {e}")
        
        # Transition all issues to Done
        for issue_key in cls.created_issues:
            try:
                cls.repository.transition_task(issue_key, "Done")
                LOGGER.info(f"Marked issue {issue_key} as Done")
            except Exception as e:
                LOGGER.error(f"Error cleaning up issue {issue_key}: {e}")
    
    def test_concurrent_task_creation_50(self):
        """Test creating 50 tasks concurrently."""
        async def create_task(index: int) -> Dict:
            """Create a task asynchronously.
            
            Args:
                index: The index of the task to create.
                
            Returns:
                Dict with success status and key or error information.
            """
            task_data = TaskData(
                project_key=self.test_project_key,
                summary=f"Concurrent Task {self.test_run_id} - {index}",
                description=f"Task created in concurrent test {index} of test run {self.test_run_id}",
                task_type="Task",
                labels=[self.test_run_id, "integration-test", "concurrent"],
            )
            
            try:
                # Create the task
                new_issue = self.repository.create_task(task_data)
                return {"success": True, "key": new_issue.key}
            except Exception as e:
                return {"success": False, "error": str(e), "index": index}
        
        async def run_concurrent_tasks() -> List[Dict]:
            """Run multiple task creation operations concurrently.
            
            Returns:
                List of dictionaries with task creation results.
            """
            # Create 50 tasks concurrently
            tasks = [create_task(i) for i in range(50)]
            return await asyncio.gather(*tasks)
        
        # Measure execution time
        start_time = time.time()
        results = asyncio.run(run_concurrent_tasks())
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Count successes and failures
        successes = [r for r in results if r.get("success", False)]
        failures = [r for r in results if not r.get("success", False)]
        
        LOGGER.info(f"Concurrent task creation completed in {execution_time:.2f} seconds")
        LOGGER.info(f"Successful creations: {len(successes)}")
        LOGGER.info(f"Failed creations: {len(failures)}")
        
        if failures:
            LOGGER.warning("Failures encountered:")
            for failure in failures:
                LOGGER.warning(f"  Task {failure.get('index')}: {failure.get('error')}")
        
        # Add successful issue keys to cleanup list
        self.created_issues.extend([r["key"] for r in successes])
        
        # Assert that most tasks were created successfully (allow for some rate limiting)
        success_ratio = len(successes) / 50
        self.assertGreaterEqual(success_ratio, 0.8, 
                              f"Expected at least 80% success rate, got {success_ratio * 100:.1f}%")
    
    def test_concurrent_reads_and_writes(self):
        """Test concurrent read and write operations."""
        # First create a set of test issues to work with
        test_issues = []
        for i in range(5):
            task_data = TaskData(
                project_key=self.test_project_key,
                summary=f"Read/Write Test {self.test_run_id} - {i}",
                description=f"Task for read/write concurrency test {i}",
                task_type="Task",
                labels=[self.test_run_id, "integration-test", "concurrent-rw"],
            )
            
            new_issue = self.repository.create_task(task_data)
            test_issues.append(new_issue.key)
            self.created_issues.append(new_issue.key)
        
        async def update_issue(issue_key: str, index: int) -> Dict:
            """Update an existing issue asynchronously.
            
            Args:
                issue_key: The key of the issue to update.
                index: The index for this update operation.
                
            Returns:
                Dict with success status and operation information.
            """
            try:
                updated_fields = {
                    "summary": f"Updated Task {self.test_run_id} - {index} - {datetime.now().strftime('%H:%M:%S')}",
                    "description": f"This task was updated in concurrent test at {datetime.now().isoformat()}"
                }
                self.repository.update_issue_from_fields(issue_key, updated_fields)
                return {"success": True, "operation": "update", "key": issue_key}
            except Exception as e:
                return {"success": False, "operation": "update", "error": str(e), "key": issue_key}
        
        async def read_issue(issue_key: str) -> Dict:
            """Read an issue asynchronously.
            
            Args:
                issue_key: The key of the issue to read.
                
            Returns:
                Dict with success status and read operation data.
            """
            try:
                issue = self.repository.get_issue(issue_key)
                return {
                    "success": True,
                    "operation": "read",
                    "key": issue_key,
                    "summary": issue.fields.summary
                }
            except Exception as e:
                return {"success": False, "operation": "read", "error": str(e), "key": issue_key}
        
        async def add_comment(issue_key: str, index: int) -> Dict:
            """Add a comment to an issue asynchronously.
            
            Args:
                issue_key: The key of the issue to comment on.
                index: The index for this comment operation.
                
            Returns:
                Dict with success status and comment operation data.
            """
            try:
                comment = f"Comment added in concurrent test at {datetime.now().isoformat()} - {index}"
                self.repository.add_comment(issue_key, comment)
                return {"success": True, "operation": "comment", "key": issue_key}
            except Exception as e:
                return {"success": False, "operation": "comment", "error": str(e), "key": issue_key}
        
        async def run_mixed_operations() -> List[Dict]:
            """Run a mix of read and write operations concurrently.
            
            Returns:
                List of dictionaries with operation results.
            """
            # Create a mix of operations:
            # - 20 reads of random issues
            # - 15 updates of random issues
            # - 15 comment additions to random issues
            read_tasks = [read_issue(test_issues[i % len(test_issues)]) for i in range(20)]
            update_tasks = [update_issue(test_issues[i % len(test_issues)], i) for i in range(15)]
            comment_tasks = [add_comment(test_issues[i % len(test_issues)], i) for i in range(15)]
            
            # Mix all operations together
            all_tasks = read_tasks + update_tasks + comment_tasks
            return await asyncio.gather(*all_tasks)
        
        # Measure execution time
        start_time = time.time()
        results = asyncio.run(run_mixed_operations())
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Count successes and failures by operation type
        reads = [r for r in results if r.get("operation") == "read"]
        updates = [r for r in results if r.get("operation") == "update"]
        comments = [r for r in results if r.get("operation") == "comment"]
        
        read_success = len([r for r in reads if r.get("success", False)])
        update_success = len([r for r in updates if r.get("success", False)])
        comment_success = len([r for r in comments if r.get("success", False)])
        
        LOGGER.info(f"Concurrent mixed operations completed in {execution_time:.2f} seconds")
        LOGGER.info(f"Read operations: {read_success}/{len(reads)} successful")
        LOGGER.info(f"Update operations: {update_success}/{len(updates)} successful")
        LOGGER.info(f"Comment operations: {comment_success}/{len(comments)} successful")
        
        # Calculate overall success rate
        total_success = read_success + update_success + comment_success
        total_operations = len(reads) + len(updates) + len(comments)
        success_ratio = total_success / total_operations
        
        # Assert that most operations were successful (allow for some rate limiting)
        self.assertGreaterEqual(success_ratio, 0.8, 
                              f"Expected at least 80% success rate, got {success_ratio * 100:.1f}%")
    
    def test_high_volume_search(self):
        """Test high-volume concurrent search operations."""
        async def search_issues(query_index: int) -> Dict:
            """Perform a search operation asynchronously.
            
            Args:
                query_index: Index to determine which query variation to use.
                
            Returns:
                Dict with search operation results.
            """
            try:
                # Create varied queries
                if query_index % 3 == 0:
                    query = f'project = "{self.test_project_key}" AND labels = "{self.test_run_id}"'
                elif query_index % 3 == 1:
                    query = f'project = "{self.test_project_key}" AND issuetype = Task'
                else:
                    query = f'project = "{self.test_project_key}"'
                
                issues = self.repository.search_for_issues(query, max_results=10)
                return {
                    "success": True,
                    "query_type": query_index % 3,
                    "count": len(issues)
                }
            except Exception as e:
                return {
                    "success": False,
                    "query_type": query_index % 3,
                    "error": str(e)
                }
        
        async def run_concurrent_searches() -> List[Dict]:
            """Run multiple search operations concurrently.
            
            Returns:
                List of dictionaries with search results.
            """
            # Perform 50 concurrent search operations
            search_tasks = [search_issues(i) for i in range(50)]
            return await asyncio.gather(*search_tasks)
        
        # Measure execution time
        start_time = time.time()
        results = asyncio.run(run_concurrent_searches())
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Count successes and failures
        successes = [r for r in results if r.get("success", False)]
        failures = [r for r in results if not r.get("success", False)]
        
        LOGGER.info(f"Concurrent search operations completed in {execution_time:.2f} seconds")
        LOGGER.info(f"Successful searches: {len(successes)}")
        LOGGER.info(f"Failed searches: {len(failures)}")
        
        if failures:
            LOGGER.warning("Failures encountered:")
            for failure in failures:
                LOGGER.warning(f"  Query type {failure.get('query_type')}: {failure.get('error')}")
        
        # Assert that most searches were successful (allow for some rate limiting)
        success_ratio = len(successes) / 50
        self.assertGreaterEqual(success_ratio, 0.8, 
                              f"Expected at least 80% success rate, got {success_ratio * 100:.1f}%")


if __name__ == "__main__":
    unittest.main()