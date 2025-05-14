"""Use case for summarizing a Jira board's tasks grouped by components and epics."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.board_summarizer_service_interface import (
    BoardSummarizerServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_grouper_interface import ITaskGrouper


class BoardSummarizerUseCase:
    """Use case for summarizing a Jira board's tasks grouped by components and epics."""
    
    def __init__(
        self,
        summarizer_service: BoardSummarizerServiceInterface,
        task_grouper: ITaskGrouper = None
    ) -> None:
        """Initialize the use case with dependencies.
        
        Args:
            summarizer_service: Service to generate summaries using AI
            task_grouper: Component for grouping tasks by component and epic
        """
        self._summarizer_service = summarizer_service
        self._task_grouper = task_grouper if task_grouper else TaskGrouper()
        
    async def execute(self, tasks: List[TaskData]) -> str:
        """Process a list of tasks and generate a summary.
        
        Args:
            tasks: List of task data objects
            
        Returns:
            A formatted summary text
        """
        # Group tasks by component and epic
        grouped_tasks = self._task_grouper.group_tasks(tasks)
        
        # Convert grouped tasks to a string representation
        tasks_str = self._format_grouped_tasks(grouped_tasks)
        
        # Generate summary using AI service
        summary = await self._summarizer_service.run(tasks_str)
        
        return summary
        
    def _format_grouped_tasks(self, grouped_tasks: Dict[str, Dict[str, List[TaskData]]]) -> str:
        """Format grouped tasks into a string representation.
        
        Args:
            grouped_tasks: Tasks grouped by component and epic
            
        Returns:
            String representation of the grouped tasks
        """
        result = []
        
        for component, epics in grouped_tasks.items():
            component_section = f"**executive department: {component}**\n"
            
            for epic, tasks in epics.items():
                epic_section = f"  - **epic: {epic}**\n"
                
                for task in tasks:
                    assignee_info = f"{task.assignee}" if task.assignee else "Unassigned"
                    release_info = f", نسخه: {task.release}" if task.release else ""
                    
                    task_summary = (
                        f"    - task: {task.summary}\n"
                        f"      assignee: {assignee_info}{release_info}\n"
                    )
                    epic_section += task_summary
                
                component_section += epic_section
            
            result.append(component_section)
        
        return "\n".join(result)


class TaskGrouper(ITaskGrouper):
    """Component for grouping tasks by component and epic."""
    
    def group_tasks(
        self,
        tasks: List[TaskData],
    ) -> Dict[str, Dict[str, List[TaskData]]]:
        """Group tasks by component and epic.
        
        Args:
            tasks: List of task data objects
            
        Returns:
            Dictionary with components as keys, each containing a dictionary with
            epics as keys and lists of tasks as values
        """
        component_groups = defaultdict(lambda: defaultdict(list))
        
        for task in tasks:
            component_key = (
                task.component if task.component else "no executive department"
            )
            epic_key = task.epics if task.epics else "no epic"
            component_groups[component_key][epic_key].append(task)
            
        return component_groups