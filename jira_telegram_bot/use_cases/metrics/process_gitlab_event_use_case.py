"""Use case for processing GitLab events into metric events."""

from datetime import datetime
from typing import Dict, Any, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType
from jira_telegram_bot.use_cases.interfaces.metrics.metrics_processor_interface import MetricsProcessorInterface


class ProcessGitlabEventUseCase:
    """Use case for processing GitLab webhook events into metric events."""
    
    def __init__(self, metrics_processor: MetricsProcessorInterface):
        """Initialize the use case.
        
        Args:
            metrics_processor: Processor for handling metric events
        """
        self.metrics_processor = metrics_processor
    
    async def process_gitlab_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Process GitLab webhook data and create metric events.
        
        Args:
            webhook_data: Raw webhook payload from GitLab
            
        Returns:
            True if processing was successful, False otherwise
        """
        LOGGER.debug(f"Processing GitLab webhook for metrics: {webhook_data}")
        
        try:
            metric_events = self._map_webhook_to_metric_events(webhook_data)
            
            for metric_event in metric_events:
                # Check idempotency
                if await self.metrics_processor.is_event_processed(metric_event.event_id):
                    LOGGER.info(f"Event {metric_event.event_id} already processed, skipping")
                    continue
                
                # Process the event
                success = await self.metrics_processor.process_metric_event(metric_event)
                if success:
                    await self.metrics_processor.mark_event_processed(
                        metric_event.event_id, 
                        f"{metric_event.developer_key}:{metric_event.metric_type}"
                    )
                else:
                    LOGGER.error(f"Failed to process metric event: {metric_event.event_id}")
                    return False
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error processing GitLab webhook: {e}")
            return False
    
    def _map_webhook_to_metric_events(self, webhook_data: Dict[str, Any]) -> list[MetricEvent]:
        """Map GitLab webhook data to MetricEvent instances.
        
        Args:
            webhook_data: Raw webhook payload from GitLab
            
        Returns:
            List of MetricEvent instances
        """
        events = []
        event_type = webhook_data.get("event_type")
        object_kind = webhook_data.get("object_kind")
        
        if object_kind == "push":
            # Handle push events (commits)
            commits = webhook_data.get("commits", [])
            for commit in commits:
                event = self._create_commit_event(commit, webhook_data)
                if event:
                    events.append(event)
        
        elif object_kind == "merge_request":
            # Handle merge request events
            event = self._create_merge_request_event(webhook_data)
            if event:
                events.append(event)
        
        return events
    
    def _create_commit_event(self, commit: Dict[str, Any], webhook_data: Dict[str, Any]) -> Optional[MetricEvent]:
        """Create a metric event for a commit.
        
        Args:
            commit: Commit data from webhook
            webhook_data: Full webhook data for context
            
        Returns:
            MetricEvent instance or None
        """
        author_email = commit.get("author", {}).get("email")
        commit_id = commit.get("id")
        
        if not all([author_email, commit_id]):
            return None
        
        # Extract project information
        project_info = webhook_data.get("project", {})
        project_key = self._extract_project_key_from_gitlab(project_info)
        
        if not project_key:
            return None
        
        timestamp = datetime.now()
        event_id = f"gitlab_commit_{commit_id}_{timestamp.isoformat()}"
        
        return MetricEvent(
            event_id=event_id,
            metric_type=MetricType.COMMIT_MADE,
            developer_key=author_email,
            timestamp=self._parse_gitlab_timestamp(commit.get("timestamp")) or timestamp,
            value=1.0,
            project_key=project_key,
            metadata={
                "commit_id": commit_id,
                "commit_message": commit.get("message"),
                "added": commit.get("added", []),
                "modified": commit.get("modified", []),
                "removed": commit.get("removed", []),
                "repository": project_info.get("name"),
                "branch": webhook_data.get("ref", "").replace("refs/heads/", "")
            }
        )
    
    def _create_merge_request_event(self, webhook_data: Dict[str, Any]) -> Optional[MetricEvent]:
        """Create a metric event for a merge request.
        
        Args:
            webhook_data: Full webhook data
            
        Returns:
            MetricEvent instance or None
        """
        mr_data = webhook_data.get("object_attributes", {})
        if not mr_data:
            return None
        
        author_email = mr_data.get("author", {}).get("email")
        mr_id = mr_data.get("id")
        action = mr_data.get("action")
        state = mr_data.get("state")
        
        if not all([author_email, mr_id, action]):
            return None
        
        # Map GitLab actions to metric types
        metric_type = self._map_mr_action_to_metric(action, state)
        if not metric_type:
            return None
        
        # Extract project information
        project_info = webhook_data.get("project", {})
        project_key = self._extract_project_key_from_gitlab(project_info)
        
        if not project_key:
            return None
        
        timestamp = datetime.now()
        event_id = f"gitlab_mr_{mr_id}_{action}_{timestamp.isoformat()}"
        
        return MetricEvent(
            event_id=event_id,
            metric_type=metric_type,
            developer_key=author_email,
            timestamp=self._parse_gitlab_timestamp(mr_data.get("created_at")) or timestamp,
            value=1.0,
            project_key=project_key,
            metadata={
                "merge_request_id": mr_id,
                "title": mr_data.get("title"),
                "description": mr_data.get("description"),
                "source_branch": mr_data.get("source_branch"),
                "target_branch": mr_data.get("target_branch"),
                "state": state,
                "action": action,
                "repository": project_info.get("name"),
                "url": mr_data.get("url")
            }
        )
    
    def _map_mr_action_to_metric(self, action: str, state: str) -> Optional[MetricType]:
        """Map GitLab merge request action to MetricType.
        
        Args:
            action: GitLab action (open, merge, close, etc.)
            state: GitLab state (opened, merged, closed, etc.)
            
        Returns:
            MetricType or None
        """
        if action == "open" or state == "opened":
            return MetricType.MERGE_REQUEST_OPENED
        elif action == "merge" or state == "merged":
            return MetricType.MERGE_REQUEST_MERGED
        elif action == "close" or state == "closed":
            return MetricType.MERGE_REQUEST_CLOSED
        
        return None
    
    def _extract_project_key_from_gitlab(self, project_info: Dict[str, Any]) -> Optional[str]:
        """Extract project key from GitLab project info.
        
        Args:
            project_info: GitLab project information
            
        Returns:
            Project key or None if not found
        """
        # Try to extract from namespace or name
        namespace = project_info.get("namespace")
        name = project_info.get("name", "")
        
        # Common patterns for project key extraction
        if namespace:
            return f"{namespace}-{name}".upper().replace(" ", "").replace("-", "")
        
        # Fallback to project name
        return name.upper().replace(" ", "").replace("-", "") if name else None
    
    def _parse_gitlab_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse GitLab timestamp string to datetime.
        
        Args:
            timestamp_str: ISO timestamp string from GitLab
            
        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        
        try:
            # GitLab typically uses ISO format
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            LOGGER.warning(f"Failed to parse GitLab timestamp: {timestamp_str}")
            return None
