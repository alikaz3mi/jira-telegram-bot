"""Interface for board summarizer services."""

from __future__ import annotations

from typing import Protocol


class BoardSummarizerServiceInterface(Protocol):
    """Interface for the board summarizer service."""
    
    async def run(self, grouped_tasks: str) -> str:
        """Generate a summary of tasks grouped by component and epic.
        
        Args:
            grouped_tasks: String representation of grouped tasks data
            
        Returns:
            A formatted summary text
        """
        ...