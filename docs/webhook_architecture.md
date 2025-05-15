# Webhook Integration Architecture

This document provides a technical overview of the webhook integration architecture for the Jira Telegram Bot project.

## Architecture Overview

The webhook integration follows Clean Architecture principles with distinct layers:

1. **Entities Layer** - Core business models
2. **Use Cases Layer** - Application business rules
3. **Interface Layer** - Interfaces/protocols defining boundaries
4. **Frameworks Layer** - External systems & delivery mechanisms

## Component Breakdown

### Entities Layer

The entities layer contains the core business objects as Pydantic models:

```
jira_telegram_bot/entities/api_schemas/webhook_schemas.py
```

- `WebhookResponse` - Standard response format for all webhook endpoints
- `JiraWebhookRequest` - Schema for incoming Jira webhook events
- `TelegramUpdate` - Schema for incoming Telegram webhook events

### Use Cases Layer

The use cases layer contains the business logic for processing webhooks:

```
jira_telegram_bot/use_cases/webhooks/jira_webhook_use_case.py
jira_telegram_bot/use_cases/webhooks/telegram_webhook_use_case.py
```

- `JiraWebhookUseCase` processes Jira events and sends notifications via Telegram
- `TelegramWebhookUseCase` processes Telegram updates and creates/updates Jira issues

### Interface Layer

The interface layer defines contracts that the use cases must implement:

```
jira_telegram_bot/use_cases/interfaces/jira_webhook_handler_interface.py
jira_telegram_bot/use_cases/interfaces/telegram_webhook_handler_interface.py
```

- `JiraWebhookHandlerInterface` defines the contract for handling Jira webhooks
- `TelegramWebhookHandlerInterface` defines the contract for handling Telegram updates

### Frameworks Layer

The frameworks layer contains FastAPI endpoints and configuration:

```
jira_telegram_bot/frameworks/api/endpoints/jira_webhook.py
jira_telegram_bot/frameworks/api/endpoints/telegram_webhook.py
jira_telegram_bot/frameworks/api/endpoints/health_check.py
jira_telegram_bot/frameworks/api/base_endpoint.py
jira_telegram_bot/frameworks/api/entry_point.py
jira_telegram_bot/frameworks/api/registry.py
```

- `JiraWebhookEndpoint` handles HTTP requests for Jira webhooks
- `TelegramWebhookEndpoint` handles HTTP requests for Telegram webhooks
- `HealthCheckEndpoint` provides system status monitoring
- `ServiceAPIEndpointBluePrint` defines the contract for all API endpoints
- `entry_point.py` configures the FastAPI application
- `registry.py` manages endpoint registration

## Dependency Injection

The system uses Lagom for dependency injection:

```
jira_telegram_bot/config_dependency_injection.py
jira_telegram_bot/app_container.py
```

- Use cases are injected into endpoints
- Dependencies follow the Dependency Inversion Principle
- Container is configured during application startup

## Webhook Data Flow

### Jira Webhook Flow

1. Jira sends an HTTP POST to `/webhook/jira/`
2. `JiraWebhookEndpoint` receives the request
3. `JiraWebhookUseCase.process_webhook()` extracts issue info and event type
4. Use case finds any Telegram messages related to the issue
5. Use case sends appropriate notifications via `NotificationGatewayInterface`
6. Endpoint returns standardized `WebhookResponse`

### Telegram Webhook Flow

1. Telegram sends an HTTP POST to `/webhook/telegram/`
2. `TelegramWebhookEndpoint` receives the request
3. `TelegramWebhookUseCase.process_update()` processes the update
4. Use case creates/updates Jira issues via `TaskManagerRepositoryInterface`
5. Endpoint returns standardized `WebhookResponse`

## Configuration and Setup

Webhook configuration is managed by:

```
scripts/configure_webhooks.py
scripts/run_api_server.py
```

- `configure_webhooks.py` registers webhooks with Jira and Telegram
- `run_api_server.py` starts the FastAPI server

## Testing

The system is tested at multiple levels:

```
tests/unit_tests/frameworks/api/endpoints/test_jira_webhook_endpoint.py
tests/unit_tests/frameworks/api/endpoints/test_telegram_webhook_endpoint.py
tests/unit_tests/frameworks/api/endpoints/test_health_check_endpoint.py
tests/unit_tests/use_cases/webhooks/test_jira_webhook_use_case.py
tests/unit_tests/use_cases/webhooks/test_telegram_webhook_use_case.py
tests/integration/test_webhook_endpoints.py
tests/integration/test_webhook_system.py
```

- Unit tests for individual components
- Integration tests for API endpoints
- System tests for end-to-end functionality

## SOLID Principles Implementation

1. **Single Responsibility Principle**: Each class has a single responsibility
   - `JiraWebhookUseCase` only handles Jira webhook processing
   - `TelegramWebhookUseCase` only handles Telegram update processing

2. **Open/Closed Principle**: Code is open for extension but closed for modification
   - New webhook types can be added without modifying existing code
   - `ServiceAPIEndpointBluePrint` can be extended for new endpoints

3. **Liskov Substitution Principle**: Subtypes are substitutable for their base types
   - `JiraWebhookUseCase` can be substituted with any implementation of `JiraWebhookHandlerInterface`
   - `TelegramWebhookUseCase` can be substituted with any implementation of `TelegramWebhookHandlerInterface`

4. **Interface Segregation Principle**: Clients depend only on methods they use
   - `JiraWebhookHandlerInterface` defines only the methods needed for Jira webhook handling
   - `TelegramWebhookHandlerInterface` defines only the methods needed for Telegram update handling

5. **Dependency Inversion Principle**: High-level modules depend on abstractions
   - Endpoints depend on interface abstractions, not concrete implementations
   - Use cases depend on repository and gateway interfaces

## Clean Architecture Implementation

1. **Independence from Frameworks**: Core business logic is independent of frameworks
   - Use cases don't import from FastAPI or other frameworks
   - Business logic can be tested without HTTP requests

2. **Testability**: All components are independently testable
   - Use cases can be tested without endpoints
   - Endpoints can be tested with mocked use cases

3. **Independence from UI**: Business rules don't depend on UI
   - Use cases don't know they're being called by FastAPI endpoints

4. **Independence from Database**: Business rules don't depend on database
   - Use cases operate through repository interfaces
   - Storage implementation details are hidden

5. **Independence from External Agencies**: Business rules don't depend on external systems
   - Use cases interact with Jira and Telegram through interfaces
   - External dependencies are injected

## Summary

The webhook integration architecture follows Clean Architecture and SOLID principles to create a maintainable, testable, and loosely coupled system. The separation of concerns allows for independent development and testing of components, while dependency injection ensures proper inversion of control.
