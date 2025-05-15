"""End-to-end tests for project status API."""

import unittest
import requests
import os
import time
from unittest.mock import patch

class TestProjectStatusAPIE2E(unittest.TestCase):
    """End-to-end tests for project status API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Base URL for API
        cls.base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
        
        # Wait for API to be available
        cls._wait_for_api()
    
    @classmethod
    def _wait_for_api(cls, max_retries=5, delay=1):
        """Wait for the API to become available.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds
        """
        for i in range(max_retries):
            try:
                response = requests.get(f"{cls.base_url}/health/ping")
                if response.status_code == 200:
                    return
            except requests.exceptions.ConnectionError:
                pass
            
            time.sleep(delay)
        
        raise Exception(f"API at {cls.base_url} is not available after {max_retries} retries")
    
    def test_api_flow(self):
        """Test the complete API flow from listing projects to updating tracking."""
        # Step 1: Get list of projects
        response = requests.get(f"{self.base_url}/projects/")
        self.assertEqual(response.status_code, 200)
        projects_data = response.json()
        self.assertIn("projects", projects_data)
        
        # If no projects available, we can't continue the test
        if not projects_data["projects"]:
            self.skipTest("No projects available for testing")
            return
        
        # Step 2: Get details of first project
        first_project = projects_data["projects"][0]
        project_key = first_project["key"]
        
        response = requests.get(f"{self.base_url}/projects/{project_key}")
        self.assertEqual(response.status_code, 200)
        project_details = response.json()
        self.assertIn("project", project_details)
        self.assertEqual(project_details["project"]["key"], project_key)
        
        # Step 3: Update tracking for the project
        tracking_data = {"track": True, "notification_channel": "test_channel"}
        response = requests.put(
            f"{self.base_url}/projects/{project_key}/tracking",
            json=tracking_data
        )
        self.assertEqual(response.status_code, 200)
        tracking_result = response.json()
        self.assertEqual(tracking_result["project_key"], project_key)
        self.assertEqual(tracking_result["tracking_enabled"], True)
        self.assertEqual(tracking_result["notification_channel"], "test_channel")
        
        # Step 4: Disable tracking for the project
        tracking_data = {"track": False}
        response = requests.put(
            f"{self.base_url}/projects/{project_key}/tracking",
            json=tracking_data
        )
        self.assertEqual(response.status_code, 200)
        tracking_result = response.json()
        self.assertEqual(tracking_result["project_key"], project_key)
        self.assertEqual(tracking_result["tracking_enabled"], False)


if __name__ == "__main__":
    unittest.main()
