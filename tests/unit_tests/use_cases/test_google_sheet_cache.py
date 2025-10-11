"""Tests for Google Sheet caching functionality."""
import time
import unittest
from unittest.mock import MagicMock, patch

from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings


class TestGoogleSheetCache(unittest.TestCase):
    """Test caching functionality in GoogleSheetClient."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('jira_telegram_bot.adapters.google_sheet.ServiceAccountCredentials'), \
             patch('jira_telegram_bot.adapters.google_sheet.gspread'):
            self.settings = GoogleSheetsConnectionSettings(
                token_path="/fake/path/to/token.json"
            )
            self.client = GoogleSheetClient(self.settings)

    def test_cache_key_generation(self):
        """Test cache key generation."""
        spreadsheet_id = "test_sheet_id"
        range_name = "Sheet1!A1:Z100"
        
        cache_key = self.client._get_cache_key(spreadsheet_id, range_name)
        expected_key = f"{spreadsheet_id}:{range_name}"
        
        self.assertEqual(cache_key, expected_key)

    def test_cache_validity_check(self):
        """Test cache validity checking."""
        cache_key = "test_key"
        
        # Initially no cache entry
        self.assertFalse(self.client._is_cache_valid(cache_key))
        
        # Add cache entry
        test_values = [["A1", "B1"], ["A2", "B2"]]
        self.client._set_cache(cache_key, test_values)
        
        # Should be valid immediately
        self.assertTrue(self.client._is_cache_valid(cache_key))

    def test_cache_expiration(self):
        """Test that cache expires after TTL."""
        cache_key = "test_key"
        test_values = [["A1", "B1"], ["A2", "B2"]]
        
        # Set a very short TTL for testing
        original_ttl = self.client._cache_ttl
        self.client._cache_ttl = 0.1  # 0.1 seconds
        
        try:
            # Add cache entry
            self.client._set_cache(cache_key, test_values)
            self.assertTrue(self.client._is_cache_valid(cache_key))
            
            # Wait for expiration
            time.sleep(0.15)
            self.assertFalse(self.client._is_cache_valid(cache_key))
            
        finally:
            # Restore original TTL
            self.client._cache_ttl = original_ttl

    def test_get_from_cache(self):
        """Test retrieving values from cache."""
        cache_key = "test_key"
        test_values = [["A1", "B1"], ["A2", "B2"]]
        
        # No cache entry initially
        self.assertIsNone(self.client._get_from_cache(cache_key))
        
        # Add cache entry
        self.client._set_cache(cache_key, test_values)
        
        # Should retrieve from cache
        cached_values = self.client._get_from_cache(cache_key)
        self.assertEqual(cached_values, test_values)

    def test_cache_cleanup(self):
        """Test cleanup of expired cache entries."""
        # Set short TTL for testing
        original_ttl = self.client._cache_ttl
        self.client._cache_ttl = 0.1
        
        try:
            # Add multiple cache entries
            self.client._set_cache("key1", [["A1", "B1"]])
            self.client._set_cache("key2", [["A2", "B2"]])
            
            # Verify entries exist
            self.assertEqual(len(self.client._values_cache), 2)
            
            # Wait for expiration
            time.sleep(0.15)
            
            # Cleanup should remove expired entries
            self.client._cleanup_expired_cache()
            self.assertEqual(len(self.client._values_cache), 0)
            
        finally:
            # Restore original TTL
            self.client._cache_ttl = original_ttl

    @patch('jira_telegram_bot.adapters.google_sheet.gspread')
    def test_a_get_values_caching_integration(self, mock_gspread):
        """Test that get_values properly uses caching."""
        import asyncio
        
        async def run_test():
            # Mock the gspread client
            mock_spreadsheet = MagicMock()
            mock_worksheet = MagicMock()
            mock_worksheet.get.return_value = [["A1", "B1"], ["A2", "B2"]]
            mock_spreadsheet.worksheet.return_value = mock_worksheet
            self.client.client.open_by_key.return_value = mock_spreadsheet
            
            spreadsheet_id = "test_sheet"
            range_name = "Sheet1!A1:B2"
            
            # First call should hit the API
            result1 = await self.client.get_values(spreadsheet_id, range_name)
            self.assertEqual(result1, [["A1", "B1"], ["A2", "B2"]])
            
            # Second call should hit cache
            result2 = await self.client.get_values(spreadsheet_id, range_name)
            self.assertEqual(result2, [["A1", "B1"], ["A2", "B2"]])
            
            # Verify API was called only once
            mock_spreadsheet.worksheet.assert_called_once()
            mock_worksheet.get.assert_called_once()
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
