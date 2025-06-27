"""Base class for AI-agent use cases."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict

from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol


class BaseAIAgentUseCase(ABC):
    """Base class for all AI-agent driven use cases."""
    
    def __init__(
        self,
        prompt_catalog: PromptCatalogProtocol,
        ai_service: AIServiceProtocol,
    ) -> None:
        """Initialize the base AI agent use case.
        
        Args:
            prompt_catalog: Protocol for loading prompts.
            ai_service: Protocol for AI service interactions.
        """
        self.prompt_catalog = prompt_catalog
        self.ai_service = ai_service
        self.prompt_name: str = ""
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the use case with given inputs.
        
        Returns:
            Result of the AI agent processing.
        """
        pass
    
    async def _load_prompt(self, department: str = None, user_id: str = None):
        """Load the prompt for this use case.
        
        Args:
            department: Optional department for prompt customization.
            user_id: Optional user ID for prompt customization.
            
        Returns:
            StructuredPrompt object.
        """
        return await self.prompt_catalog.get_prompt(
            task=self.prompt_name,
            department=department,
            user_id=user_id,
        )
    
    async def _process_with_ai(
        self,
        inputs: Dict[str, Any],
        department: str = None,
        user_id: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Process inputs with AI service.
        
        Args:
            inputs: Input data for the prompt.
            department: Optional department for prompt customization.
            user_id: Optional user ID for prompt customization.
            **kwargs: Additional parameters for AI service.
            
        Returns:
            AI service response.
        """
        prompt = await self._load_prompt(department, user_id)
        return await self.ai_service.run(prompt, inputs, **kwargs)