from __future__ import annotations

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional

from croniter import croniter

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import SendDeadlineAlertsUseCase


class CronJob:
    """Cron-based scheduler for running deadline alerts."""
    
    def __init__(
        self,
        send_deadline_alerts_use_case: SendDeadlineAlertsUseCase,
        cron_schedule: str = "0 9 * * *",  # Daily at 9 AM
        lookahead_days: int = 7,
        additional_jql: Optional[str] = None,
    ):
        self.send_deadline_alerts_use_case = send_deadline_alerts_use_case
        self.cron_schedule = cron_schedule
        self.lookahead_days = lookahead_days
        self.additional_jql = additional_jql
        self.running = False
        self._validate_cron_schedule()
    
    def _validate_cron_schedule(self) -> None:
        """Validate the cron schedule expression."""
        try:
            croniter(self.cron_schedule)
        except Exception as e:
            raise ValueError(f"Invalid cron schedule '{self.cron_schedule}': {e}")
    
    async def start(self) -> None:
        """Start the cron job scheduler."""
        self.running = True
        LOGGER.info(f"Starting deadline notifier cron job with schedule: {self.cron_schedule}")
        
        # Set up signal handlers for graceful shutdown
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)
        
        try:
            await self._run_scheduler()
        except KeyboardInterrupt:
            LOGGER.info("Received keyboard interrupt")
        except Exception as e:
            LOGGER.error(f"Scheduler error: {e}")
            raise
        finally:
            self.running = False
            LOGGER.info("Deadline notifier cron job stopped")
    
    def stop(self) -> None:
        """Stop the cron job scheduler."""
        self.running = False
        LOGGER.info("Stopping deadline notifier cron job...")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        LOGGER.info(f"Received signal {signum}, stopping scheduler...")
        self.stop()
    
    async def _run_scheduler(self) -> None:
        """Run the scheduler loop."""
        cron = croniter(self.cron_schedule, datetime.now())
        
        while self.running:
            try:
                # Calculate next run time
                next_run = cron.get_next(datetime)
                now = datetime.now()
                
                # Calculate sleep duration
                sleep_duration = (next_run - now).total_seconds()
                
                if sleep_duration > 0:
                    LOGGER.info(f"Next deadline alert scheduled for: {next_run} (in {sleep_duration:.1f} seconds)")
                    
                    # Sleep in small intervals to allow for graceful shutdown
                    while sleep_duration > 0 and self.running:
                        sleep_time = min(sleep_duration, 60)  # Check every minute
                        await asyncio.sleep(sleep_time)
                        sleep_duration -= sleep_time
                
                # Run the job if we're still running
                if self.running:
                    await self._execute_job()
                
            except Exception as e:
                LOGGER.error(f"Error in scheduler loop: {e}")
                # Sleep for a minute before retrying
                await asyncio.sleep(60)
    
    async def _execute_job(self) -> None:
        """Execute the deadline alerts job."""
        try:
            LOGGER.info("Executing deadline alerts job...")
            start_time = datetime.now()
            
            stats = await self.send_deadline_alerts_use_case.execute(
                lookahead_days=self.lookahead_days,
                additional_jql=self.additional_jql,
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            LOGGER.info(
                f"Deadline alerts job completed in {duration:.2f}s. "
                f"Stats: {stats}"
            )
            
        except Exception as e:
            LOGGER.error(f"Error executing deadline alerts job: {e}")
    
    async def run_once(self) -> None:
        """Run the deadline alerts job once (for testing/manual execution)."""
        LOGGER.info("Running deadline alerts job once...")
        await self._execute_job()


async def main():
    """Main function for running the cron job standalone."""
    import os
    from jira_telegram_bot.app_container import get_container
    
    # Get configuration from environment
    cron_schedule = os.environ.get("DEADLINE_NOTIFIER_CRON", "0 9 * * *")
    lookahead_days = int(os.environ.get("DEADLINE_NOTIFIER_LOOKAHEAD_DAYS", "7"))
    additional_jql = os.environ.get("DEADLINE_NOTIFIER_ADDITIONAL_JQL")
    
    # Get dependencies from container
    container = get_container()
    use_case = container[SendDeadlineAlertsUseCase]
    
    # Create and start cron job
    cron_job = CronJob(
        send_deadline_alerts_use_case=use_case,
        cron_schedule=cron_schedule,
        lookahead_days=lookahead_days,
        additional_jql=additional_jql,
    )
    
    await cron_job.start()


if __name__ == "__main__":
    asyncio.run(main())
