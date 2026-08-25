"""Task queue manager for sequential daily task processing."""
from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass, field

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)


@dataclass
class UserTaskQueue:
    """Queue of tasks for a user."""
    
    chat_id: int
    tasks: List[DailyTaskCheck] = field(default_factory=list)
    current_index: int = 0
    total_tasks: int = 0
    
    def has_next(self) -> bool:
        """Check if there are more tasks."""
        return self.current_index < len(self.tasks)
    
    def get_current(self) -> Optional[DailyTaskCheck]:
        """Get current task."""
        if self.has_next():
            return self.tasks[self.current_index]
        return None
    
    def move_to_next(self) -> None:
        """Move to next task."""
        self.current_index += 1
    
    def get_progress(self) -> str:
        """Get progress string."""
        return f"{self.current_index + 1} از {self.total_tasks}"


class DailyTaskQueueManager:
    """Manages task queues for users during daily check."""
    
    def __init__(self):
        """Initialize the manager."""
        self._queues: Dict[int, UserTaskQueue] = {}
    
    def create_queue(self, chat_id: int, tasks: List[DailyTaskCheck]) -> None:
        """Create a new task queue for user.
        
        Args:
            chat_id: User's chat ID
            tasks: List of tasks to process
        """
        self._queues[chat_id] = UserTaskQueue(
            chat_id=chat_id,
            tasks=tasks,
            current_index=0,
            total_tasks=len(tasks),
        )
    
    def get_queue(self, chat_id: int) -> Optional[UserTaskQueue]:
        """Get queue for user.
        
        Args:
            chat_id: User's chat ID
            
        Returns:
            UserTaskQueue or None if not found
        """
        return self._queues.get(chat_id)
    
    def move_to_next(self, chat_id: int) -> bool:
        """Move to next task in queue.
        
        Args:
            chat_id: User's chat ID
            
        Returns:
            True if there are more tasks, False otherwise
        """
        queue = self._queues.get(chat_id)
        if not queue:
            return False
        
        queue.move_to_next()
        return queue.has_next()
    
    def clear_queue(self, chat_id: int) -> None:
        """Clear queue for user.
        
        Args:
            chat_id: User's chat ID
        """
        if chat_id in self._queues:
            del self._queues[chat_id]
    
    def has_active_queue(self, chat_id: int) -> bool:
        """Check if user has an active queue.
        
        Args:
            chat_id: User's chat ID
            
        Returns:
            True if queue exists and has tasks
        """
        queue = self._queues.get(chat_id)
        return queue is not None and queue.has_next()
