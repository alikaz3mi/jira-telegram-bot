"""Use case for summarizing a Jira board's tasks grouped by components and epics."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from jira_telegram_bot.entities.ai_agent_models.board_summarizer import BoardSummarizerInput
from jira_telegram_bot.entities.ai_agent_models.board_summarizer import BoardSummarizerResult
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.base_ai_agent_use_case import BaseAIAgentUseCase
from jira_telegram_bot.use_cases.interfaces.task_grouper_interface import ITaskGrouper


class BoardSummarizerUseCase(BaseAIAgentUseCase):
    """Use case for summarizing a Jira board's tasks grouped by components and epics."""
    
    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
        task_grouper: ITaskGrouper = None,
    ) -> None:
        """Initialize the use case with dependencies.
        
        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
            task_grouper: Component for grouping tasks by component and epic.
        """
        super().__init__(prompt_catalog, ai_service)
        self.prompt_name = PromptNames.BOARD_SUMMARIZER
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
        
        # Process with AI service
        ai_inputs = {"grouped_tasks": tasks_str}
        ai_response = await self._process_with_ai(ai_inputs)
        
        return ai_response.get("summary", "")
        
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