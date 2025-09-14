"""Tests for SynthPM services."""
from __future__ import annotations

import unittest
from datetime import datetime

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.services import SynthPMColumnMappingService
from jira_telegram_bot.entities.synth_pm.services import SynthPMComponentService
from jira_telegram_bot.entities.synth_pm.services import SynthPMDateService
from jira_telegram_bot.entities.synth_pm.services import SynthPMStatusService


class TestSynthPMDateService(unittest.TestCase):
    """Test cases for SynthPMDateService."""

    def test_parse_date_string_valid_formats(self):
        """Test parsing various valid date formats."""
        service = SynthPMDateService()

        # Test different formats
        self.assertIsNotNone(service.parse_date_string("2024-01-15"))
        self.assertIsNotNone(service.parse_date_string("15/01/2024"))
        self.assertIsNotNone(service.parse_date_string("01/15/2024"))
        self.assertIsNotNone(service.parse_date_string("2024/01/15"))
        self.assertIsNotNone(service.parse_date_string("15-01-2024"))

    def test_parse_date_string_invalid_formats(self):
        """Test parsing invalid date formats."""
        service = SynthPMDateService()

        self.assertIsNone(service.parse_date_string("invalid-date"))
        self.assertIsNone(service.parse_date_string(""))
        self.assertIsNone(service.parse_date_string(None))

    def test_extract_dates_from_feature(self):
        """Test extracting dates from feature."""
        service = SynthPMDateService()

        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            deadline=datetime(2024, 1, 15),
            implementation_start_date=datetime(2024, 1, 1),
        )

        dates = service.extract_dates_from_feature(feature)

        self.assertEqual(dates["due_date"], "2024-01-15")
        self.assertEqual(dates["target_start"], "2024-01-01")
        self.assertEqual(dates["target_end"], "2024-01-15")


class TestSynthPMStatusService(unittest.TestCase):
    """Test cases for SynthPMStatusService."""

    def test_map_sheet_status_to_jira(self):
        """Test mapping sheet status to Jira status."""
        service = SynthPMStatusService()

        self.assertEqual(service.map_sheet_status_to_jira("۱"), "BACKLOG")
        self.assertEqual(service.map_sheet_status_to_jira("۶"), "IN PROGRESS")
        self.assertEqual(service.map_sheet_status_to_jira("invalid"), "TO DO")

    def test_map_priority(self):
        """Test mapping priority values."""
        service = SynthPMStatusService()

        self.assertEqual(service.map_priority("Highest"), "Highest")
        self.assertEqual(service.map_priority("بالاترین"), "Highest")
        self.assertEqual(service.map_priority("invalid"), "Medium")

    def test_determine_jira_status(self):
        """Test determining Jira status from feature."""
        service = SynthPMStatusService()

        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            status="۶",
        )

        status = service.determine_jira_status(feature)
        self.assertEqual(status, "IN PROGRESS")


class TestSynthPMComponentService(unittest.TestCase):
    """Test cases for SynthPMComponentService."""

    def test_map_components(self):
        """Test mapping feature components."""
        service = SynthPMComponentService()

        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            ai="1",
            backend="1",
            frontend="0",
            devops=None,
            ui_ux="1",
        )

        components = service.map_components(feature)

        self.assertIn("AI", components)
        self.assertIn("Backend", components)
        self.assertNotIn("Frontend", components)
        self.assertNotIn("DevOps", components)
        self.assertIn("UI/UX", components)


class TestSynthPMColumnMappingService(unittest.TestCase):
    """Test cases for SynthPMColumnMappingService."""

    def test_create_column_mapping(self):
        """Test creating column mapping from headers."""
        service = SynthPMColumnMappingService()

        headers = ["ردیف", "وظیفه", "Epic", "اولویت", "وضعیت"]
        mapping = service.create_column_mapping(headers)

        self.assertEqual(mapping["row_number"], 0)
        self.assertEqual(mapping["task_title"], 1)
        self.assertEqual(mapping["epic"], 2)
        self.assertEqual(mapping["priority"], 3)
        self.assertEqual(mapping["status"], 4)

    def test_number_to_column_letter(self):
        """Test converting numbers to column letters."""
        service = SynthPMColumnMappingService()

        self.assertEqual(service.number_to_column_letter(1), "A")
        self.assertEqual(service.number_to_column_letter(26), "Z")
        self.assertEqual(service.number_to_column_letter(27), "AA")
        self.assertEqual(service.number_to_column_letter(28), "AB")


if __name__ == "__main__":
    unittest.main()
