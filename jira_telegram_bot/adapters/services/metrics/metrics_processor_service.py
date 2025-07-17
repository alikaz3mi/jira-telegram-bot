"""Metrics processor service implementation."""

from typing import Dict, Set

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType
from jira_telegram_bot.use_cases.interfaces.metrics.metrics_processor_interface import MetricsProcessorInterface
from jira_telegram_bot.use_cases.metrics.update_sheet_use_case import UpdateSheetUseCase
from jira_telegram_bot.utils.exceptions import MetricsProcessingError


class MetricsProcessorService(MetricsProcessorInterface):
    """Service for processing metric events and updating appropriate sheets."""
    
    def __init__(self, update_sheet_use_case: UpdateSheetUseCase):
        """Initialize the metrics processor.
        
        Args:
            update_sheet_use_case: Use case for updating Google Sheets
        """
        self.update_sheet_use_case = update_sheet_use_case
        self._processed_events: Set[str] = set()  # In-memory cache for demo
        
        # Define which metrics should update which sheets
        self._daily_metrics = {
            MetricType.TASK_RESOLVED,
            MetricType.TIME_LOGGED,
            MetricType.COMMIT_MADE,
            MetricType.DEADLINE_HIT,
            MetricType.DEADLINE_MISSED,
        }
        
        self._sprint_metrics = {
            MetricType.TASK_CREATED,
            MetricType.TASK_RESOLVED,
            MetricType.TIME_LOGGED,
            MetricType.MERGE_REQUEST_OPENED,
            MetricType.MERGE_REQUEST_MERGED,
            MetricType.MERGE_REQUEST_CLOSED,
        }
    
    async def process_metric_event(self, event: MetricEvent) -> bool:
        """Process a metric event and update appropriate sheets.
        
        Args:
            event: Metric event to process
            
        Returns:
            True if processing was successful, False otherwise
            
        Raises:
            MetricsProcessingError: If processing fails
        """
        LOGGER.debug(f"Processing metric event: {event.event_id} - {event.metric_type}")
        
        try:
            success_daily = True
            success_sprint = True
            
            # Update daily scoreboard if applicable
            if event.metric_type in self._daily_metrics:
                success_daily = await self.update_sheet_use_case.update_daily_scoreboard(event)
                if not success_daily:
                    LOGGER.error(f"Failed to update daily scoreboard for event: {event.event_id}")
            
            # Update sprint matrix if applicable
            if event.metric_type in self._sprint_metrics and event.sprint_id:
                success_sprint = await self.update_sheet_use_case.update_sprint_matrix(event)
                if not success_sprint:
                    LOGGER.error(f"Failed to update sprint matrix for event: {event.event_id}")
            
            # Consider processing successful if at least one update succeeded
            # or if the event doesn't require any updates
            overall_success = success_daily and success_sprint
            
            if overall_success:
                LOGGER.info(f"Successfully processed metric event: {event.event_id}")
            else:
                LOGGER.error(f"Partial or complete failure processing event: {event.event_id}")
            
            return overall_success
            
        except Exception as e:
            LOGGER.error(f"Error processing metric event {event.event_id}: {e}")
            raise MetricsProcessingError(f"Failed to process event {event.event_id}: {e}")
    
    async def is_event_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed (idempotency).
        
        Args:
            event_id: Unique event identifier
            
        Returns:
            True if event was already processed, False otherwise
        """
        # In a production system, this would check a persistent store
        # For now, using in-memory cache
        return event_id in self._processed_events
    
    async def mark_event_processed(self, event_id: str, metric_key: str) -> None:
        """Mark an event as processed for idempotency.
        
        Args:
            event_id: Unique event identifier
            metric_key: Key identifying the specific metric/row updated
        """
        # In a production system, this would store in a persistent store
        # For now, using in-memory cache
        self._processed_events.add(event_id)
        LOGGER.debug(f"Marked event as processed: {event_id} -> {metric_key}")
    
    def get_supported_daily_metrics(self) -> Set[MetricType]:
        """Get the set of metrics that update daily scoreboard.
        
        Returns:
            Set of MetricType values
        """
        return self._daily_metrics.copy()
    
    def get_supported_sprint_metrics(self) -> Set[MetricType]:
        """Get the set of metrics that update sprint matrix.
        
        Returns:
            Set of MetricType values
        """
        return self._sprint_metrics.copy()
    
    def is_daily_metric(self, metric_type: MetricType) -> bool:
        """Check if a metric type should update daily scoreboard.
        
        Args:
            metric_type: Type of metric to check
            
        Returns:
            True if metric should update daily scoreboard
        """
        return metric_type in self._daily_metrics
    
    def is_sprint_metric(self, metric_type: MetricType) -> bool:
        """Check if a metric type should update sprint matrix.
        
        Args:
            metric_type: Type of metric to check
            
        Returns:
            True if metric should update sprint matrix
        """
        return metric_type in self._sprint_metrics
