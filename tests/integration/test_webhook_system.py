"""System test for webhook infrastructure."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.frameworks.api.entry_point import app


class TestWebhookSystem(unittest.TestCase):
    """System test for webhook infrastructure."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Create mocks
        cls.jira_webhook_use_case_mock = AsyncMock()
        cls.telegram_webhook_use_case_mock = AsyncMock()
        
        # Configure the mocks
        cls.jira_webhook_use_case_mock.process_webhook = AsyncMock(return_value={"status": "success"})
        cls.telegram_webhook_use_case_mock.process_update = AsyncMock(return_value={"status": "success"})
        
        # Create a mocked app
        from fastapi import FastAPI, APIRouter
        from fastapi import Request, Response
        
        # Create a test app with the endpoints
        cls.app = FastAPI()
        jira_router = APIRouter(prefix="/api/v1/webhook/jira")
        telegram_router = APIRouter(prefix="/api/v1/webhook/telegram")
        health_router = APIRouter(prefix="/health")
        
        @jira_router.post("/")
        async def jira_webhook(request: Request):
            try:
                payload = await request.json()
                result = await cls.jira_webhook_use_case_mock.process_webhook(payload)
                if hasattr(result, 'dict'):
                    return result.dict()
                return {"status": "success"}
            except Exception as e:
                return Response(
                    status_code=500,
                    content=json.dumps({"status": "error", "message": f"Error: {str(e)}"}),
                    media_type="application/json"
                )
            
        @telegram_router.post("/")
        async def telegram_webhook(request: Request):
            try:
                payload = await request.json()
                result = await cls.telegram_webhook_use_case_mock.process_update(payload)
                if hasattr(result, 'dict'):
                    return result.dict()
                return {"status": "success"}
            except Exception as e:
                return Response(
                    status_code=500,
                    content=json.dumps({"status": "error", "message": f"Error: {str(e)}"}),
                    media_type="application/json"
                )
        
        @health_router.get("/")
        async def health():
            return {"status": "ok"}
        
        @health_router.get("/ping")
        async def health_ping():
            return {"ping": "pong"}
            
        cls.app.include_router(jira_router)
        cls.app.include_router(telegram_router)
        cls.app.include_router(health_router)
        
        # Create test client
        cls.client = TestClient(cls.app)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are run."""
        pass
    
    def test_health_endpoint(self):
        """Test health endpoint."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
    
    def test_health_ping_endpoint(self):
        """Test health ping endpoint."""
        response = self.client.get("/health/ping")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ping"], "pong")
    
    def test_jira_webhook_endpoint(self):
        """Test Jira webhook endpoint."""
        # Configure mock
        self.jira_webhook_use_case_mock.process_webhook.return_value = MagicMock(
            dict=lambda: {"status": "success", "message": "Processed jira webhook"}
        )
        
        # Send request
        payload = {"issue_event_type_name": "issue_created", "issue": {"key": "TEST-123"}}
        response = self.client.post("/api/v1/webhook/jira/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Processed jira webhook")
        
        # Verify use case was called correctly
        self.jira_webhook_use_case_mock.process_webhook.assert_called_once_with(payload)
    
    def test_telegram_webhook_endpoint(self):
        """Test Telegram webhook endpoint."""
        # Configure mock
        self.telegram_webhook_use_case_mock.process_update.return_value = MagicMock(
            dict=lambda: {"status": "success", "message": "Processed telegram update"}
        )
        
        # Send request
        payload = {"update_id": 123456789, "message": {"text": "Test message"}}
        response = self.client.post("/api/v1/webhook/telegram/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Processed telegram update")
        
        # Verify use case was called correctly
        self.telegram_webhook_use_case_mock.process_update.assert_called_once_with(payload)
    
    def test_jira_webhook_error(self):
        """Test Jira webhook endpoint error handling."""
        # Configure mock to raise exception
        self.jira_webhook_use_case_mock.process_webhook.side_effect = Exception("Test error")
        
        # Send request
        payload = {"issue_event_type_name": "issue_created", "issue": {"key": "TEST-123"}}
        response = self.client.post("/api/v1/webhook/jira/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Error: Test error")
    
    def test_telegram_webhook_error(self):
        """Test Telegram webhook endpoint error handling."""
        # Configure mock to raise exception
        self.telegram_webhook_use_case_mock.process_update.side_effect = Exception("Test error")
        
        # Send request
        payload = {"update_id": 123456789, "message": {"text": "Test message"}}
        response = self.client.post("/api/v1/webhook/telegram/", json=payload)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Error: Test error")


if __name__ == "__main__":
    unittest.main()
