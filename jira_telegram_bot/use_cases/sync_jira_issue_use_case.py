"""Use case for real-time synchronization of individual Jira issues."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.sync_status import SyncStatus
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import (
    JiraDataServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import (
    JiraReportRepositoryInterface,
)

# TODO: HIGHEST: if an issue is deleted, it must me be deleted across all the tables in here too.
class SyncJiraIssueUseCase:
    """Real-time sync of critical Jira issue updates to PostgreSQL.
    
    This use case handles webhook-triggered updates for individual issues,
    ensuring the database stays current without waiting for batch sync.
    """

    CRITICAL_EVENTS = {
        "issue_created",
        "issue_updated",
        "issue_resolved",
        "issue_reopened",
        "issue_closed",
        "worklog_updated",
    }

    def __init__(
        self,
        jira_service: JiraDataServiceInterface,
        report_repository: JiraReportRepositoryInterface,
    ) -> None:
        """Initialize the use case.
        
        Args:
            jira_service: Service for fetching Jira data.
            report_repository: Repository for storing report data.
        """
        self._jira_service = jira_service
        self._report_repository = report_repository

    async def sync_issue_from_webhook(
        self,
        issue_key: str,
        event_type: str,
    ) -> bool:
        """Sync single issue to PostgreSQL based on webhook event.
        
        Args:
            issue_key: The Jira issue key (e.g., "PROJ-123").
            event_type: The webhook event type (e.g., "issue_updated").
            
        Returns:
            True if sync was successful, False otherwise.
            
        Raises:
            ValueError: If issue_key is empty or invalid.
        """
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key cannot be empty")

        if event_type not in self.CRITICAL_EVENTS:
            LOGGER.debug(
                f"Skipping real-time sync for non-critical event: {event_type}",
            )
            return True

        start_time = time.time()
        project_key = issue_key.split("-")[0]
        
        try:
            LOGGER.info(f"Real-time syncing issue {issue_key} (event: {event_type})")

            issue_detail = await self._jira_service.fetch_issue_details(issue_key)
            await self._report_repository.store_issues([issue_detail])

            await self._update_sync_status_after_webhook(
                project_key=project_key,
                success=True,
                duration=time.time() - start_time,
            )

            LOGGER.info(
                f"Successfully synced {issue_key} to PostgreSQL on {event_type}",
            )
            return True

        except Exception as e:
            LOGGER.error(f"Failed to sync issue {issue_key}: {e}")
            await self._update_sync_status_after_webhook(
                project_key=project_key,
                success=False,
                duration=time.time() - start_time,
                error=str(e),
            )
            return False

    async def bulk_sync_issues(
        self,
        project_key: str,
        issue_keys: Optional[List[str]] = None,
        full_sync: bool = False,
    ) -> Dict[str, int]:
        """Sync multiple issues or entire project.
        
        Args:
            project_key: Jira project key.
            issue_keys: Optional list of specific issue keys to sync.
            full_sync: If True, sync all project issues.
            
        Returns:
            Dictionary with sync statistics (synced, failed).
        """
        start_time = time.time()
        
        try:
            LOGGER.info(
                f"Starting {'full' if full_sync else 'bulk'} sync for {project_key}",
            )
            
            if issue_keys:
                issues = []
                for key in issue_keys:
                    try:
                        issue_detail = await self._jira_service.fetch_issue_details(key)
                        issues.append(issue_detail)
                    except Exception as e:
                        LOGGER.error(f"Failed to fetch {key}: {e}")
            elif full_sync:
                issues = await self._jira_service.fetch_project_issues(project_key)
            else:
                issues = await self._fetch_updated_issues(project_key)
            
            if not issues:
                LOGGER.info(f"No issues to sync for {project_key}")
                return {"synced": 0, "failed": 0}
            
            await self._report_repository.store_issues(issues)
            
            duration = time.time() - start_time
            await self._update_sync_status_after_bulk(
                project_key=project_key,
                full_sync=full_sync,
                issues_synced=len(issues),
                duration=duration,
            )
            
            LOGGER.info(
                f"Sync completed for {project_key}: {len(issues)} issues in {duration:.2f}s",
            )
            
            return {"synced": len(issues), "failed": 0}
            
        except Exception as e:
            duration = time.time() - start_time
            LOGGER.error(f"Sync failed for {project_key}: {e}")
            
            await self._update_sync_status_after_bulk(
                project_key=project_key,
                full_sync=full_sync,
                issues_synced=0,
                duration=duration,
                error=str(e),
            )
            
            return {"synced": 0, "failed": 1}

    async def _fetch_updated_issues(self, project_key: str) -> List:
        """Fetch issues updated since last incremental sync.
        
        Args:
            project_key: Jira project key.
            
        Returns:
            List of updated issues.
        """
        sync_status = await self._report_repository.get_sync_status(project_key)
        
        if not sync_status or not sync_status.last_incremental_sync:
            LOGGER.info(f"No previous sync found for {project_key}, performing full sync")
            return await self._jira_service.fetch_project_issues(project_key)
        
        LOGGER.warning("Incremental sync not yet implemented in JiraDataService")
        return await self._jira_service.fetch_project_issues(project_key)

    async def _update_sync_status_after_webhook(
        self,
        project_key: str,
        success: bool,
        duration: float,
        error: Optional[str] = None,
    ) -> None:
        """Update sync status after webhook-triggered sync.
        
        Args:
            project_key: Jira project key.
            success: Whether sync was successful.
            duration: Sync duration in seconds.
            error: Error message if failed.
        """
        sync_status = await self._report_repository.get_sync_status(project_key)
        
        if not sync_status:
            sync_status = SyncStatus(project_key=project_key)
        
        sync_status.last_incremental_sync = datetime.now()
        sync_status.last_sync_status = "success" if success else "failed"
        sync_status.issues_synced = sync_status.issues_synced + (1 if success else 0)
        sync_status.issues_failed = sync_status.issues_failed + (0 if success else 1)
        sync_status.sync_duration_seconds = duration
        
        if error:
            sync_status.errors = {"webhook_sync_error": error}
        
        await self._report_repository.update_sync_status(sync_status)

    async def _update_sync_status_after_bulk(
        self,
        project_key: str,
        full_sync: bool,
        issues_synced: int,
        duration: float,
        error: Optional[str] = None,
    ) -> None:
        """Update sync status after bulk sync.
        
        Args:
            project_key: Jira project key.
            full_sync: Whether this was a full sync.
            issues_synced: Number of issues synced.
            duration: Sync duration in seconds.
            error: Error message if failed.
        """
        sync_status = await self._report_repository.get_sync_status(project_key)
        
        if not sync_status:
            sync_status = SyncStatus(project_key=project_key)
        
        now = datetime.now()
        
        if full_sync:
            sync_status.last_full_sync = now
        else:
            sync_status.last_incremental_sync = now
        
        sync_status.last_sync_status = "success" if not error else "failed"
        sync_status.issues_synced = issues_synced
        sync_status.issues_failed = 0 if not error else 1
        sync_status.sync_duration_seconds = duration
        
        if error:
            sync_status.errors = {"bulk_sync_error": error}
        
        await self._report_repository.update_sync_status(sync_status)
