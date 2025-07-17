"""Metrics processor interface for handling metric events."""

from abc import ABC, abstractmethod

from jira_telegram_bot.entities.metrics.metric_event import MetricEvent


class MetricsProcessorInterface(ABC):
    """Interface for processing metric events and updating sheets."""
    
    @abstractmethod
    async def process_metric_event(self, event: MetricEvent) -> bool:
        """Process a metric event and update appropriate sheets.
        
        Args:
            event: Metric event to process
            
        Returns:
            True if processing was successful, False otherwise
            
        Raises:
            MetricsProcessingError: If processing fails
        """
        pass
    
    @abstractmethod
    async def is_event_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed (idempotency).
        
        Args:
            event_id: Unique event identifier
            
        Returns:
            True if event was already processed, False otherwise
        """
        pass
    
    @abstractmethod
    async def mark_event_processed(self, event_id: str, metric_key: str) -> None:
        """Mark an event as processed for idempotency.
        
        Args:
            event_id: Unique event identifier
            metric_key: Key identifying the specific metric/row updated
        """
        pass
