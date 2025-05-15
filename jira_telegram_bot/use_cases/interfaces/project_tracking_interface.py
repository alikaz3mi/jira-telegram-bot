"""Interface for project tracking use case."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional


class ProjectTrackingInterface(ABC):
    """Interface for managing project status tracking settings."""
    
    @abstractmethod
    async def update_tracking(
        self, 
        project_key: str,
        track: bool,
        notification_channel: Optional[str] = None
    ) -> Dict:
        """Update tracking settings for a project.
        
        Args:
            project_key: Project key
            track: Whether to track this project
            notification_channel: Optional channel ID for notifications
            
        Returns:
            Dictionary with updated tracking settings
        """
        pass
    
    @abstractmethod
    async def get_tracking_status(self, project_key: str) -> Dict:
        """Get tracking status for a project.
        
        Args:
            project_key: Project key
            
        Returns:
            Dictionary with tracking settings
        """
        pass
