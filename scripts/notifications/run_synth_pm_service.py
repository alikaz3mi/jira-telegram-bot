#!/usr/bin/env python3
"""Docker service runner for multi-project SynthPM synchronization."""
from __future__ import annotations

import asyncio
import signal
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.services.synth_pm_multi_project_sync import (
    SynthPMMultiProjectSyncService,
)
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


async def main():
    """Main entry point for Docker service."""
    LOGGER.info("=" * 80)
    LOGGER.info("Starting SynthPM Multi-Project Synchronization Service")
    LOGGER.info("=" * 80)
    
    try:
        # Initialize container and settings
        container = get_container()
        settings = container[SynthPMSettings]
        
        # Read configuration from settings
        project_keys = settings.project_keys
        
        if project_keys:
            LOGGER.info(f"Configured to sync projects: {', '.join(project_keys)}")
        else:
            LOGGER.info("Configured to sync all projects in configuration")
        
        # Create and start sync service
        sync_service = SynthPMMultiProjectSyncService(
            settings=settings,
            project_keys=project_keys,
        )
        
        # Setup signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig):
            LOGGER.info(f"Received signal {sig}, initiating graceful shutdown...")
            shutdown_event.set()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        
        # Initialize and check projects
        await sync_service.initialize()
        
        if not sync_service.use_cases:
            LOGGER.error("No projects were initialized. Exiting.")
            sys.exit(1)
        
        # Log initial status
        status = sync_service.get_status()
        LOGGER.info("Service Configuration:")
        for project_key, project_status in status["projects"].items():
            LOGGER.info(
                f"  - {project_key}: "
                f"Sync every {project_status['sync_interval_minutes']}min, "
                f"PM Board: {'enabled' if project_status['pm_board_enabled'] else 'disabled'}"
            )
        
        LOGGER.info("=" * 80)
        LOGGER.info("Starting APScheduler-based continuous sync...")
        LOGGER.info("=" * 80)
        
        # Start the service (schedules jobs and starts APScheduler)
        await sync_service.start()
        
        # Block until a shutdown signal is received
        LOGGER.info("Service running. Waiting for shutdown signal...")
        await shutdown_event.wait()
        
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt received")
    except Exception as e:
        LOGGER.error(f"Fatal error in sync service: {e}", exc_info=True)
        sys.exit(1)
    finally:
        LOGGER.info("Shutting down SynthPM sync service...")
        if 'sync_service' in locals():
            await sync_service.stop()
        LOGGER.info("Service stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Service interrupted")
        sys.exit(0)
 