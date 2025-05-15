"""Unit tests for health check endpoint."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.frameworks.api.endpoints.health_check import HealthCheckEndpoint


class TestHealthCheckEndpoint(unittest.TestCase):
    """Test suite for HealthCheckEndpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.endpoint = HealthCheckEndpoint()
        
        # Create a FastAPI app for testing the endpoint
        self.app = FastAPI()
        self.app.include_router(self.endpoint.create_rest_api_route())
        self.client = TestClient(self.app)
    
    def test_create_rest_api_route(self):
        """Test creating the REST API route."""
        # Arrange
        
        # Act
        router = self.endpoint.create_rest_api_route()
        
        # Assert
        self.assertIsNotNone(router)
        self.assertEqual(router.prefix, "/health")
        self.assertEqual(router.tags, ["Health"])
    
    def test_health_check(self):
        """Test health check endpoint."""
        # Arrange - Set a fixed start time for testing
        self.endpoint.start_time = datetime.now() - timedelta(days=1, hours=2, minutes=30, seconds=15)
        
        # Act
        response = self.client.get("/health/")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["uptime"], "1d 2h 30m 15s")
        self.assertIn("timestamp", data)
    
    def test_ping(self):
        """Test ping endpoint."""
        # Act
        response = self.client.get("/health/ping")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ping": "pong"})
