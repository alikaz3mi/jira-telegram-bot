#!/usr/bin/env python3
"""Docker service runner for multi-project SynthPM synchronization."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.services.synth_pm_multi_project_sync import (
    SynthPMMultiProjectSyncService,
)
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


def parse_project_keys(env_value: Optional[str]) -> Optional[List[str]]:
    """Parse project keys from environment variable.

    Args:
        env_value: Comma-separated project keys or JSON array

    Returns:
        List of project keys or None
    """
    if not env_value:
        return None
    
    # Try JSON array first
    if env_value.strip().startswith('['):
        try:
            import json
            return json.loads(env_value)
        except json.JSONDecodeError:
            pass
    
    # Fallback to comma-separated
    return [key.strip() for key in env_value.split(',') if key.strip()]


async def main():
    """Main entry point for Docker service."""
    LOGGER.info("=" * 80)
    LOGGER.info("Starting SynthPM Multi-Project Synchronization Service")
    LOGGER.info("=" * 80)
    
    # Read configuration from environment
    project_keys_env = os.getenv('SYNTH_PM_PROJECT_KEYS')
    project_keys = parse_project_keys(project_keys_env)
    
    if project_keys:
        LOGGER.info(f"Configured to sync projects: {', '.join(project_keys)}")
    else:
        LOGGER.info("Configured to sync all projects in configuration")
    
    try:
        # Initialize container and settings
        container = get_container()
        settings = container[SynthPMSettings]
        
        # Create and start sync service
        sync_service = SynthPMMultiProjectSyncService(
            settings=settings,
            project_keys=project_keys,
        )
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig):
            LOGGER.info(f"Received signal {sig}, initiating graceful shutdown...")
            asyncio.create_task(sync_service.stop())
            loop.stop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        
        # Start the service
        await sync_service.start()
        
        if not sync_service.use_cases:
            LOGGER.error("No projects were initialized. Exiting.")
            sys.exit(1)
        
        # Log initial status
        status = sync_service.get_status()
        LOGGER.info("Service Status:")
        for project_key, project_status in status["projects"].items():
            LOGGER.info(
                f"  - {project_key}: "
                f"Sync every {project_status['sync_interval_minutes']}min, "
                f"PM Board: {'enabled' if project_status['pm_board_enabled'] else 'disabled'}"
            )
        
        LOGGER.info("=" * 80)
        LOGGER.info("Service started successfully. Running continuous sync...")
        LOGGER.info("=" * 80)
        
        # Keep the service running
        try:
            while sync_service.running:
                await asyncio.sleep(60)
                
                # Periodic status check
                if int(asyncio.get_event_loop().time()) % 3600 < 60:  # Log every hour
                    status = sync_service.get_status()
                    running_count = sum(
                        1 for p in status["projects"].values() if p["task_running"]
                    )
                    LOGGER.info(
                        f"Heartbeat: {running_count}/{len(status['projects'])} "
                        f"projects actively syncing"
                    )
        except asyncio.CancelledError:
            LOGGER.info("Main loop cancelled")
        
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
