"""Unit tests for ScheduledReportUseCase."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.use_cases.scheduled_report_use_case import ScheduledReportUseCase
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class TestScheduledReportUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for ScheduledReportUseCase."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_report_use_case = AsyncMock()
        self.mock_scheduler_service = AsyncMock()
        self.project_keys = ["TEST1", "TEST2"]
        
        self.use_case = ScheduledReportUseCase(
            report_use_case=self.mock_report_use_case,
            scheduler_service=self.mock_scheduler_service,
            project_keys=self.project_keys,
        )

    async def test_a_setup_scheduled_reports_default_interval(self):
        """Test setting up scheduled reports with default interval."""
        self.mock_scheduler_service.schedule_recurring_job.return_value = None

        await self.use_case.setup_scheduled_reports()

        self.mock_scheduler_service.schedule_recurring_job.assert_called_once()
        call_args = self.mock_scheduler_service.schedule_recurring_job.call_args
        
        self.assertEqual(call_args.kwargs["interval_minutes"], 30)
        self.assertEqual(call_args.kwargs["job_name"], "jira_report_generation")
        self.assertIsNotNone(call_args.kwargs["job_func"])

    async def test_a_setup_scheduled_reports_custom_interval(self):
        """Test setting up scheduled reports with custom interval."""
        custom_interval = 60
        
        await self.use_case.setup_scheduled_reports(custom_interval)

        call_args = self.mock_scheduler_service.schedule_recurring_job.call_args
        self.assertEqual(call_args.kwargs["interval_minutes"], custom_interval)

    async def test_a_setup_scheduled_reports_scheduler_failure(self):
        """Test setup failure when scheduler fails."""
        self.mock_scheduler_service.schedule_recurring_job.side_effect = Exception("Scheduler error")

        with self.assertRaises(Exception) as context:
            await self.use_case.setup_scheduled_reports()
        
        self.assertIn("Scheduler error", str(context.exception))

    async def test_a_start_scheduler(self):
        """Test starting the scheduler service."""
        self.mock_scheduler_service.start_scheduler.return_value = None

        await self.use_case.start_scheduler()

        self.mock_scheduler_service.start_scheduler.assert_called_once()

    async def test_a_start_scheduler_failure(self):
        """Test start scheduler failure."""
        self.mock_scheduler_service.start_scheduler.side_effect = Exception("Start error")

        with self.assertRaises(Exception):
            await self.use_case.start_scheduler()

    async def test_a_stop_scheduler(self):
        """Test stopping the scheduler service."""
        self.mock_scheduler_service.stop_scheduler.return_value = None

        await self.use_case.stop_scheduler()

        self.mock_scheduler_service.stop_scheduler.assert_called_once()

    async def test_a_stop_scheduler_failure(self):
        """Test stop scheduler failure."""
        self.mock_scheduler_service.stop_scheduler.side_effect = Exception("Stop error")

        with self.assertRaises(Exception):
            await self.use_case.stop_scheduler()

    async def test_a_generate_all_reports_success(self):
        """Test successful generation of all reports."""
        mock_reports = [
            JiraReportTestFactory.create_project_report("TEST1", 5),
            JiraReportTestFactory.create_project_report("TEST2", 3),
        ]
        
        self.mock_report_use_case.generate_multi_project_report.return_value = mock_reports

        await self.use_case._generate_all_reports()

        self.mock_report_use_case.generate_multi_project_report.assert_called_once_with(
            self.project_keys
        )

    async def test_a_generate_all_reports_failure(self):
        """Test failure during report generation."""
        self.mock_report_use_case.generate_multi_project_report.side_effect = Exception("Report error")

        with self.assertRaises(Exception) as context:
            await self.use_case._generate_all_reports()
        
        self.assertIn("Report error", str(context.exception))

    async def test_a_generate_all_reports_empty_projects(self):
        """Test report generation with empty project list."""
        empty_use_case = ScheduledReportUseCase(
            report_use_case=self.mock_report_use_case,
            scheduler_service=self.mock_scheduler_service,
            project_keys=[],
        )

        self.mock_report_use_case.generate_multi_project_report.return_value = []

        await empty_use_case._generate_all_reports()

        self.mock_report_use_case.generate_multi_project_report.assert_called_once_with([])

    async def test_a_generate_all_reports_large_project_list(self):
        """Test report generation with many projects."""
        large_project_list = [f"PROJ{i}" for i in range(10)]
        large_use_case = ScheduledReportUseCase(
            report_use_case=self.mock_report_use_case,
            scheduler_service=self.mock_scheduler_service,
            project_keys=large_project_list,
        )

        mock_reports = [
            JiraReportTestFactory.create_project_report(f"PROJ{i}", 1)
            for i in range(10)
        ]
        self.mock_report_use_case.generate_multi_project_report.return_value = mock_reports

        await large_use_case._generate_all_reports()

        self.mock_report_use_case.generate_multi_project_report.assert_called_once_with(
            large_project_list
        )

    def test_initialization_validation(self):
        """Test use case initialization with valid parameters."""
        use_case = ScheduledReportUseCase(
            report_use_case=self.mock_report_use_case,
            scheduler_service=self.mock_scheduler_service,
            project_keys=["VALID"],
        )
        
        self.assertEqual(use_case._project_keys, ["VALID"])
        self.assertEqual(use_case._report_use_case, self.mock_report_use_case)
        self.assertEqual(use_case._scheduler_service, self.mock_scheduler_service)


if __name__ == "__main__":
    unittest.main()
