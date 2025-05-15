---
mode: agent
description: Scaffold a new Telegram command with complete Clean Architecture and SOLID principles
tools: [terminalLastCommand, githubRepo]
---

# 🛠️ Goal  
Generate all artifacts required to add a new Telegram command to **jira_telegram_bot**, following strict Clean Architecture and SOLID principles:

1. **Entity models** → `jira_telegram_bot/entities/<domain_model>.py` (if needed)
2. **Interface definitions** → `jira_telegram_bot/use_cases/interfaces/<interface_name>_interface.py`
3. **Use case implementation** → `jira_telegram_bot/use_cases/telegram_commands/<command_name>.py`
4. **Adapter implementation** → `jira_telegram_bot/adapters/services/<service_name>.py` (if needed)
5. **Framework handler** → `jira_telegram_bot/frameworks/telegram/<command_name>_handler.py`
6. **Unit tests** (≥ 90% coverage) for all components
7. **Integration tests** (with concurrency testing)
8. **Dependency injection configuration**

# 📝 Interactive variables  
* `${input:command_name:snake_case command name (e.g. task_assignment)}`
* `${input:command_description:Short description of command functionality}`
* `${input:command_trigger:Command trigger text (e.g. /assign_task)}`

# 🔄 Workflow  

## 1. Domain Entity Models
If needed, create Pydantic models in the entities layer:

```python
# jira_telegram_bot/entities/<domain_model>.py
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class CommandData(BaseModel):
    """Domain model for the command data.
    
    Args:
        field_name: Description of field
    """
    field_name: str = Field(default=None)
    optional_field: Optional[str] = Field(default=None)
```

Entity models should:
- Be pure data objects with no business logic
- Use Pydantic's BaseModel
- Be immutable where possible
- Have proper type hints and docstrings
- Never import from use_cases or other layers

## 2. Interface Definitions
Define interfaces in the use cases layer:

```python
# jira_telegram_bot/use_cases/interfaces/<interface_name>_interface.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

class CommandServiceInterface(ABC):
    """Interface for command-specific operations.
    
    This interface defines the contract for services that handle
    command-specific operations.
    """
    
    @abstractmethod
    async def perform_operation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the main operation for this command.
        
        Args:
            input_data: The input data for the operation
            
        Returns:
            Result of the operation
        """
        pass
```

Interfaces should:
- Use ABC for abstract base classes
- Have clear method signatures with proper typing
- Define the minimal contract needed
- Follow Interface Segregation Principle (small, focused interfaces)

## 3. Use Case Implementation
Implement the core business logic in a use case class:

```python
# jira_telegram_bot/use_cases/telegram_commands/<command_name>.py
from __future__ import annotations

from typing import Dict, List, Optional, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.<domain_model> import CommandData
from jira_telegram_bot.use_cases.interfaces.<interface_name>_interface import CommandServiceInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface

class CommandNameUseCase:
    """Handles the business logic for the command.
    
    This use case implements the command-specific business rules,
    orchestrating the flow between repositories and services.
    """
    
    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        command_service: CommandServiceInterface,
    ):
        """Initialize the use case.
        
        Args:
            task_manager_repository: Repository for task management operations
            command_service: Service for command-specific operations
        """
        self.task_manager_repository = task_manager_repository
        self.command_service = command_service
    
    async def execute_command(self, parameter: str) -> Dict[str, Any]:
        """Execute the command with the given parameter.
        
        Args:
            parameter: Command parameter from user input
            
        Returns:
            Result of the command execution
        """
        # Implementation of business logic
        # Break down into smaller methods when complexity increases
        return result
```

Use cases should:
- Contain pure business logic with no framework dependencies
- Depend only on interfaces, not implementations
- Have methods less than 30 lines
- Break complex operations into smaller methods
- Have comprehensive docstrings and type hints

## 4. Adapter Implementation
If needed, implement adapters that fulfill the interfaces:

```python
# jira_telegram_bot/adapters/services/<service_name>.py
from __future__ import annotations

from typing import Dict, List, Optional, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.<interface_name>_interface import CommandServiceInterface

class CommandService(CommandServiceInterface):
    """Implementation of the command service.
    
    This service handles command-specific operations by implementing
    the CommandServiceInterface.
    """
    
    def __init__(self, dependency1, dependency2):
        """Initialize the service.
        
        Args:
            dependency1: First dependency
            dependency2: Second dependency
        """
        self.dependency1 = dependency1
        self.dependency2 = dependency2
    
    async def perform_operation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the main operation for this command.
        
        Args:
            input_data: The input data for the operation
            
        Returns:
            Result of the operation
        """
        # Implementation specific to this adapter
        return result
```

Adapters should:
- Implement a single interface from the use case layer
- Handle external systems and I/O
- Convert between domain models and external formats
- Follow the Single Responsibility Principle
- Handle specific implementation details

## 5. Framework Handler
Implement the Telegram command handler in the frameworks layer:

```python
# jira_telegram_bot/frameworks/telegram/<command_name>_handler.py
from __future__ import annotations

from typing import Dict, List, Optional, Any, cast

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters

from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.telegram.base_conversation_handler import BaseConversationHandler
from jira_telegram_bot.use_cases.telegram_commands.<command_name> import CommandNameUseCase

class CommandNameHandler(BaseConversationHandler):
    """Telegram handler for the command.
    
    This class handles the Telegram-specific interaction for the command,
    delegating business logic to the use case.
    """
    
    def __init__(
        self,
        command_use_case: CommandNameUseCase,
    ):
        """Initialize the handler.
        
        Args:
            command_use_case: Use case for command business logic
        """
        self.command_use_case = command_use_case
        
        # Define conversation states
        self.WAITING_FOR_INPUT = 0
        
        # Set up conversation handler
        super().__init__(
            entry_points=[CommandHandler("command_trigger", self.start_command)],
            states={
                self.WAITING_FOR_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_input)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the command conversation.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            Next conversation state
        """
        # Implementation for starting the conversation
        return self.WAITING_FOR_INPUT
    
    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process user input and execute use case.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            Next conversation state or ConversationHandler.END
        """
        # Extract input from update
        user_input = update.message.text
        
        # Delegate to use case
        try:
            result = await self.command_use_case.execute_command(user_input)
            await update.message.reply_text(f"Command executed: {result}")
        except Exception as e:
            LOGGER.error(f"Error executing command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the conversation.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            ConversationHandler.END
        """
        await update.message.reply_text("Command cancelled.")
        return ConversationHandler.END
```

Framework handlers should:
- Deal only with framework-specific concerns (Telegram API)
- Delegate all business logic to use cases
- Handle input/output conversions
- Manage conversation state
- Implement error handling for the UI layer

## 6. Dependency Injection Configuration
Update the dependency injection configuration:

```python
# Add to jira_telegram_bot/config_dependency_injection.py
container[CommandServiceInterface] = Singleton(
    lambda c: CommandService(dependency1, dependency2)
)

container[CommandNameUseCase] = Singleton(
    lambda c: CommandNameUseCase(
        task_manager_repository=c[TaskManagerRepositoryInterface],
        command_service=c[CommandServiceInterface],
    )
)

# Add to jira_telegram_bot/app_container.py
child_container[CommandNameHandler] = Singleton(
    lambda c: CommandNameHandler(
        command_use_case=c[CommandNameUseCase],
    )
)

# Register handler in ticketing_bot.py
def setup_telegram_app(self, application: Application) -> None:
    # ...existing handlers...
    application.add_handler(self.container[CommandNameHandler])
```

## 7. Unit Tests
Create unit tests for each component:

```python
# tests/unit_tests/use_cases/telegram_commands/test_<command_name>.py
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.entities.<domain_model> import CommandData
from jira_telegram_bot.use_cases.telegram_commands.<command_name> import CommandNameUseCase

class TestCommandNameUseCase(unittest.TestCase):
    """Test suite for CommandNameUseCase."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.task_manager_repository = AsyncMock()
        self.command_service = AsyncMock()
        self.use_case = CommandNameUseCase(
            task_manager_repository=self.task_manager_repository,
            command_service=self.command_service,
        )
    
    async def test_execute_command_success(self):
        """Test successful command execution."""
        # Arrange
        test_param = "test input"
        expected_result = {"status": "success"}
        self.command_service.perform_operation.return_value = expected_result
        
        # Act
        result = await self.use_case.execute_command(test_param)
        
        # Assert
        self.assertEqual(result, expected_result)
        self.command_service.perform_operation.assert_called_once()
    
    async def test_execute_command_failure(self):
        """Test command execution with failure."""
        # Arrange
        test_param = "invalid input"
        self.command_service.perform_operation.side_effect = ValueError("Invalid input")
        
        # Act & Assert
        with self.assertRaises(ValueError):
            await self.use_case.execute_command(test_param)
```

Tests should:
- Mirror the package structure under tests/
- Test both success and failure cases
- Mock external dependencies
- Follow AAA pattern (Arrange, Act, Assert)
- Achieve ≥90% coverage
- Test asynchronous functions with test_a prefix

## 8. Integration Tests
Create integration tests that test the full flow:

```python
# tests/integration/frameworks/telegram/test_<command_name>_handler.py
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes

from jira_telegram_bot.frameworks.telegram.<command_name>_handler import CommandNameHandler
from jira_telegram_bot.use_cases.telegram_commands.<command_name> import CommandNameUseCase

class TestCommandNameHandler(unittest.IsolatedAsyncioTestCase):
    """Integration tests for CommandNameHandler."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.use_case = AsyncMock(spec=CommandNameUseCase)
        self.handler = CommandNameHandler(command_use_case=self.use_case)
        
        # Mock Telegram objects
        self.update = AsyncMock(spec=Update)
        self.context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        self.update.message.text = "test input"
        
    async def test_a_full_conversation_flow(self):
        """Test the full conversation flow."""
        # Arrange
        self.use_case.execute_command.return_value = {"status": "success"}
        
        # Act - Start conversation
        result = await self.handler.start_command(self.update, self.context)
        
        # Assert
        self.assertEqual(result, self.handler.WAITING_FOR_INPUT)
        self.update.message.reply_text.assert_called_once()
        
        # Act - Process input
        result = await self.handler.process_input(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.use_case.execute_command.assert_called_once_with("test input")
    
    async def test_a_concurrency_handling(self):
        """Test handling multiple concurrent requests."""
        # Arrange
        self.use_case.execute_command.return_value = {"status": "success"}
        
        # Act - Create multiple concurrent requests
        tasks = []
        for i in range(5):
            update_copy = AsyncMock(spec=Update)
            update_copy.message.text = f"test input {i}"
            context_copy = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
            
            tasks.append(self.handler.process_input(update_copy, context_copy))
        
        # Execute all concurrently
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 5)
        self.assertEqual(self.use_case.execute_command.call_count, 5)
```

Integration tests should:
- Test the full flow from UI to use case and back
- Include concurrency tests for race conditions
- Test error handling and recovery
- Ensure proper coordination between components

# 📊 Quality Assurance
Before submitting, ensure:
1. **Architecture Compliance**:
   - No outward imports (entities → use cases → adapters → frameworks)
   - Proper interface definitions and implementations
   - Clear separation of concerns

2. **SOLID Principles**:
   - Single Responsibility: Each class has one reason to change
   - Open-Closed: Extend behavior without modifying code
   - Liskov Substitution: Implementations are substitutable
   - Interface Segregation: Small, focused interfaces
   - Dependency Inversion: Depend on abstractions

3. **Code Quality**:
   - No methods longer than 30 lines
   - No comments inside functions
   - Complete docstrings for all functions
   - Full type hints
   - No magic numbers/strings (use constants)

4. **Testing**:
   - ≥90% test coverage
   - Tests for both sync and async methods
   - Both unit and integration tests
   - Mock external dependencies

# 📤 Deliverables  
Reply with a **change summary** listing all created/updated files.

For more detailed instructions on specific components, refer to the coding instructions in `.github/instructions/copilot-instructions.instructions.md`.
