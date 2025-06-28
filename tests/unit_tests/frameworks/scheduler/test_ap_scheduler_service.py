"""Unit tests for APSchedulerService."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import APSchedulerService


class TestAPSchedulerService(unittest.IsolatedAsyncioTestCase):
    """Test cases for APSchedulerService."""

    def setUp(self):
        """Set up test dependencies."""
        with patch('jira_telegram_bot.frameworks.scheduler.ap_scheduler_service.AsyncIOScheduler'):
            self.mock_scheduler = MagicMock()
            self.service = APSchedulerService()
            self.service._scheduler = self.mock_scheduler

    async def test_a_schedule_recurring_job_success(self):
        """Test successful job scheduling."""
        job_func = AsyncMock()
        interval_minutes = 30
        job_name = "test_job"
        
        self.mock_scheduler.add_job.return_value = None

        await self.service.schedule_recurring_job(job_func, interval_minutes, job_name)

        self.mock_scheduler.add_job.assert_called_once_with(
            job_func,
            'interval',
            minutes=interval_minutes,
            id=job_name,
            replace_existing=True,
        )

    async def test_a_schedule_recurring_job_failure(self):
        """Test job scheduling failure."""
        job_func = AsyncMock()
        interval_minutes = 30
        job_name = "test_job"
        
        self.mock_scheduler.add_job.side_effect = Exception("Scheduler error")

        with self.assertRaises(Exception) as context:
            await self.service.schedule_recurring_job(job_func, interval_minutes, job_name)
        
        self.assertIn("Scheduler error", str(context.exception))

    async def test_a_schedule_recurring_job_replace_existing(self):
        """Test job scheduling with replacement."""
        job_func = AsyncMock()
        interval_minutes = 60
        job_name = "existing_job"

        await self.service.schedule_recurring_job(job_func, interval_minutes, job_name)

        call_args = self.mock_scheduler.add_job.call_args
        self.assertTrue(call_args.kwargs['replace_existing'])

    async def test_a_start_scheduler_success(self):
        """Test successful scheduler start."""
        self.service._is_running = False
        self.mock_scheduler.start.return_value = None
        
        # Mock the while loop to exit immediately
        with patch('asyncio.sleep', side_effect=Exception('Break loop')):
            with self.assertRaises(Exception):
                await self.service.start_scheduler()

        self.mock_scheduler.start.assert_called_once()
        self.assertTrue(self.service._is_running)

    async def test_a_start_scheduler_already_running(self):
        """Test starting scheduler when already running."""
        self.service._is_running = True
        
        # Should not start if already running
        with patch('asyncio.sleep', side_effect=Exception('Break loop')):
            with self.assertRaises(Exception):
                await self.service.start_scheduler()

        self.mock_scheduler.start.assert_not_called()

    async def test_a_start_scheduler_failure(self):
        """Test scheduler start failure."""
        self.service._is_running = False
        self.mock_scheduler.start.side_effect = Exception("Start error")

        with self.assertRaises(Exception) as context:
            await self.service.start_scheduler()
        
        self.assertIn("Start error", str(context.exception))

    async def test_a_stop_scheduler_success(self):
        """Test successful scheduler stop."""
        self.service._is_running = True
        self.mock_scheduler.shutdown.return_value = None

        await self.service.stop_scheduler()

        self.mock_scheduler.shutdown.assert_called_once()
        self.assertFalse(self.service._is_running)

    async def test_a_stop_scheduler_not_running(self):
        """Test stopping scheduler when not running."""
        self.service._is_running = False

        await self.service.stop_scheduler()

        self.mock_scheduler.shutdown.assert_not_called()

    async def test_a_stop_scheduler_failure(self):
        """Test scheduler stop failure."""
        self.service._is_running = True
        self.mock_scheduler.shutdown.side_effect = Exception("Stop error")

        with self.assertRaises(Exception) as context:
            await self.service.stop_scheduler()
        
        self.assertIn("Stop error", str(context.exception))

    def test_initialization(self):
        """Test service initialization."""
        with patch('jira_telegram_bot.frameworks.scheduler.ap_scheduler_service.AsyncIOScheduler') as mock_scheduler_class:
            service = APSchedulerService()
            
            mock_scheduler_class.assert_called_once()
            self.assertFalse(service._is_running)

    async def test_a_schedule_multiple_jobs(self):
        """Test scheduling multiple jobs."""
        job1 = AsyncMock()
        job2 = AsyncMock()
        
        await self.service.schedule_recurring_job(job1, 30, "job1")
        await self.service.schedule_recurring_job(job2, 60, "job2")

        self.assertEqual(self.mock_scheduler.add_job.call_count, 2)

    async def test_a_schedule_job_with_zero_interval(self):
        """Test scheduling job with zero interval."""
        job_func = AsyncMock()

        await self.service.schedule_recurring_job(job_func, 0, "zero_job")

        call_args = self.mock_scheduler.add_job.call_args
        self.assertEqual(call_args.kwargs['minutes'], 0)

    async def test_a_schedule_job_with_large_interval(self):
        """Test scheduling job with large interval."""
        job_func = AsyncMock()
        large_interval = 10080  # 1 week in minutes

        await self.service.schedule_recurring_job(job_func, large_interval, "weekly_job")

        call_args = self.mock_scheduler.add_job.call_args
        self.assertEqual(call_args.kwargs['minutes'], large_interval)


if __name__ == "__main__":
    unittest.main()
