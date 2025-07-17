"""Use case for processing Jira events into metric events."""

from datetime import datetime
from typing import Dict, Any, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType
from jira_telegram_bot.use_cases.interfaces.metrics.metrics_processor_interface import MetricsProcessorInterface


class ProcessJiraEventUseCase:
    """Use case for processing Jira webhook events into metric events."""
    
    def __init__(self, metrics_processor: MetricsProcessorInterface):
        """Initialize the use case.
        
        Args:
            metrics_processor: Processor for handling metric events
        """
        self.metrics_processor = metrics_processor
    
    async def process_jira_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Process Jira webhook data and create metric events.
        
        Args:
            webhook_data: Raw webhook payload from Jira
            
        Returns:
            True if processing was successful, False otherwise
        """
        LOGGER.debug(f"Processing Jira webhook for metrics: {webhook_data}")
        
        try:
            metric_event = self._map_webhook_to_metric_event(webhook_data)
            if metric_event:
                # Check idempotency
                if await self.metrics_processor.is_event_processed(metric_event.event_id):
                    LOGGER.info(f"Event {metric_event.event_id} already processed, skipping")
                    return True
                
                # Process the event
                success = await self.metrics_processor.process_metric_event(metric_event)
                if success:
                    await self.metrics_processor.mark_event_processed(
                        metric_event.event_id, 
                        f"{metric_event.developer_key}:{metric_event.metric_type}"
                    )
                return success
            
            LOGGER.debug("No metric event created from webhook data")
            return True
            
        except Exception as e:
            LOGGER.error(f"Error processing Jira webhook: {e}")
            return False
    
    def _map_webhook_to_metric_event(self, webhook_data: Dict[str, Any]) -> Optional[MetricEvent]:
        """Map Jira webhook data to a MetricEvent.
        
        Args:
            webhook_data: Raw webhook payload from Jira
            
        Returns:
            MetricEvent instance or None if not trackable
        """
        event_type = webhook_data.get("issue_event_type_name")
        issue_data = webhook_data.get("issue", {})
        
        if not event_type or not issue_data:
            return None
        
        # Extract basic information
        issue_key = issue_data.get("key")
        project_key = issue_data.get("fields", {}).get("project", {}).get("key")
        assignee = issue_data.get("fields", {}).get("assignee")
        developer_key = assignee.get("emailAddress") if assignee else None
        
        if not all([issue_key, project_key, developer_key]):
            LOGGER.debug(f"Missing required fields for metric tracking: {issue_key}, {project_key}, {developer_key}")
            return None
        
        # Map event types to metric types
        metric_type = self._map_event_type_to_metric(event_type, webhook_data)
        if not metric_type:
            return None
        
        # Create unique event ID
        timestamp = datetime.now()
        event_id = f"jira_{issue_key}_{event_type}_{timestamp.isoformat()}"
        
        # Extract additional metadata
        metadata = self._extract_metadata(webhook_data, event_type)
        
        # Calculate metric value
        value = self._calculate_metric_value(event_type, webhook_data)
        
        return MetricEvent(
            event_id=event_id,
            metric_type=metric_type,
            developer_key=developer_key,
            timestamp=timestamp,
            value=value,
            project_key=project_key,
            issue_key=issue_key,
            sprint_id=self._extract_sprint_id(issue_data),
            metadata=metadata
        )
    
    def _map_event_type_to_metric(self, event_type: str, webhook_data: Dict[str, Any]) -> Optional[MetricType]:
        """Map Jira event type to MetricType.
        
        Args:
            event_type: Jira event type name
            webhook_data: Full webhook data for context
            
        Returns:
            MetricType or None if not trackable
        """
        event_mapping = {
            "issue_created": MetricType.TASK_CREATED,
            "issue_updated": MetricType.TASK_UPDATED,
            "issue_resolved": MetricType.TASK_RESOLVED,
            "issue_reopened": MetricType.TASK_REOPENED,
            "issue_generic": MetricType.TASK_TRANSITIONED,
        }
        
        # Check for worklog events
        if "worklog" in webhook_data:
            return MetricType.TIME_LOGGED
        
        return event_mapping.get(event_type)
    
    def _calculate_metric_value(self, event_type: str, webhook_data: Dict[str, Any]) -> float:
        """Calculate the numeric value for the metric.
        
        Args:
            event_type: Jira event type name
            webhook_data: Full webhook data
            
        Returns:
            Numeric value for the metric
        """
        # For worklog events, return time spent
        worklog = webhook_data.get("worklog")
        if worklog:
            time_spent_seconds = worklog.get("timeSpentSeconds", 0)
            return time_spent_seconds / 3600.0  # Convert to hours
        
        # For story points, try to extract from issue
        issue_data = webhook_data.get("issue", {})
        fields = issue_data.get("fields", {})
        story_points = fields.get("customfield_10004")  # Common story points field
        if story_points:
            return float(story_points)
        
        # Default value for count-based metrics
        return 1.0
    
    def _extract_sprint_id(self, issue_data: Dict[str, Any]) -> Optional[str]:
        """Extract sprint ID from issue data.
        
        Args:
            issue_data: Issue data from webhook
            
        Returns:
            Sprint ID or None if not found
        """
        fields = issue_data.get("fields", {})
        sprint_field = fields.get("customfield_10005")  # Common sprint field
        
        if sprint_field and isinstance(sprint_field, list) and sprint_field:
            # Extract sprint ID from the first active sprint
            sprint = sprint_field[0]
            if isinstance(sprint, dict):
                return str(sprint.get("id"))
            elif isinstance(sprint, str):
                # Parse sprint string if needed
                return sprint.split("id=")[1].split(",")[0] if "id=" in sprint else None
        
        return None
    
    def _extract_metadata(self, webhook_data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Extract additional metadata from webhook.
        
        Args:
            webhook_data: Full webhook data
            event_type: Jira event type name
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            "event_type": event_type,
            "webhook_timestamp": webhook_data.get("timestamp")
        }
        
        issue_data = webhook_data.get("issue", {})
        fields = issue_data.get("fields", {})
        
        # Add issue metadata
        metadata.update({
            "issue_type": fields.get("issuetype", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "status": fields.get("status", {}).get("name"),
            "summary": fields.get("summary"),
        })
        
        # Add changelog for transition events
        changelog = webhook_data.get("changelog")
        if changelog:
            metadata["changelog"] = changelog
        
        # Add worklog metadata
        worklog = webhook_data.get("worklog")
        if worklog:
            metadata["worklog"] = {
                "author": worklog.get("author", {}).get("emailAddress"),
                "comment": worklog.get("comment"),
                "started": worklog.get("started")
            }
        
        return metadata
