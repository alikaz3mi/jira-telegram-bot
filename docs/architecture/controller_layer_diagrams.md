# Controller Layer Implementation - Mermaid Diagrams

## Architecture Overview

```mermaid
graph TD
    A[FastAPI Request] --> B[Generic Webhook Endpoint]
    B --> C{Controller Type}
    C -->|Jira| D[Jira Webhook Controller]
    C -->|GitLab| E[GitLab Webhook Controller]
    
    D --> F[Base Webhook Controller]
    E --> F
    
    F --> G[Validate Webhook Data]
    G --> H[Route to Use Cases]
    
    H --> I[Jira Webhook Use Case]
    H --> J[Process Jira Event Use Case]
    H --> K[Process GitLab Event Use Case]
    
    I --> L[Generate Response]
    J --> L
    K --> L
    
    L --> M[WebhookResponse]
    M --> N[FastAPI Response]
```

## Before vs After Architecture

### Before (Duplicated Code)

```mermaid
graph TD
    A1[Jira Webhook Endpoint] --> B1[Duplicate Validation]
    A2[GitLab Webhook Endpoint] --> B2[Duplicate Validation]
    A3[Metrics Webhook Endpoint] --> B3[Duplicate Validation]
    
    B1 --> C1[Duplicate Error Handling]
    B2 --> C2[Duplicate Error Handling]
    B3 --> C3[Duplicate Error Handling]
    
    C1 --> D1[Duplicate Response Creation]
    C2 --> D2[Duplicate Response Creation]
    C3 --> D3[Duplicate Response Creation]
    
    D1 --> E1[Use Case Call]
    D2 --> E2[Use Case Call]
    D3 --> E3[Use Case Call]
    
    classDef duplicate fill:#ffcccc,stroke:#ff0000,stroke-width:2px
    class B1,B2,B3,C1,C2,C3,D1,D2,D3 duplicate
```

### After (Controller Layer)

```mermaid
graph TD
    A1[Jira Webhook Endpoint] --> B[Generic Webhook Endpoint]
    A2[GitLab Webhook Endpoint] --> B
    A3[Metrics Webhook Endpoint] --> B
    
    B --> C[Base Webhook Controller]
    C --> D[Unified Validation]
    C --> E[Unified Error Handling]
    C --> F[Unified Response Creation]
    
    D --> G[Specialized Controllers]
    E --> G
    F --> G
    
    G --> H[Use Case Routing]
    H --> I[Business Logic]
    
    classDef unified fill:#ccffcc,stroke:#00ff00,stroke-width:2px
    class B,C,D,E,F unified
```

## Controller Class Hierarchy

```mermaid
classDiagram
    class BaseWebhookController {
        <<abstract>>
        +process_webhook(webhook_data)
        +_validate_webhook_data(webhook_data)*
        +_route_to_use_case(webhook_data)*
        +_create_success_response(message)
        +_create_error_response(error)
        +_create_validation_error_response(error)
    }
    
    class JiraWebhookController {
        -jira_webhook_use_case: JiraWebhookUseCase
        -process_jira_event_use_case: ProcessJiraEventUseCase
        +_validate_webhook_data(webhook_data)
        +_route_to_use_case(webhook_data)
    }
    
    class GitlabWebhookController {
        -process_gitlab_event_use_case: ProcessGitlabEventUseCase
        +_validate_webhook_data(webhook_data)
        +_route_to_use_case(webhook_data)
    }
    
    BaseWebhookController <|-- JiraWebhookController
    BaseWebhookController <|-- GitlabWebhookController
```

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant WebhookEndpoint
    participant Controller
    participant BaseController
    participant UseCase
    
    Client->>FastAPI: POST /webhook/jira
    FastAPI->>WebhookEndpoint: webhook_handler(request)
    WebhookEndpoint->>Controller: process_webhook(webhook_data)
    Controller->>BaseController: process_webhook(webhook_data)
    
    BaseController->>Controller: _validate_webhook_data(webhook_data)
    Controller->>BaseController: validation_result
    
    BaseController->>Controller: _route_to_use_case(webhook_data)
    Controller->>UseCase: execute(webhook_data)
    UseCase->>Controller: use_case_result
    Controller->>BaseController: combined_result
    
    BaseController->>WebhookEndpoint: WebhookResponse
    WebhookEndpoint->>FastAPI: Response
    FastAPI->>Client: HTTP Response
```

## Error Handling Flow

```mermaid
graph TD
    A[Webhook Request] --> B[Controller Processing]
    B --> C{Validation}
    C -->|Valid| D[Route to Use Case]
    C -->|Invalid| E[Create Validation Error Response]
    
    D --> F{Use Case Execution}
    F -->|Success| G[Create Success Response]
    F -->|Business Error| H[Create Business Error Response]
    F -->|System Error| I[Create System Error Response]
    
    E --> J[Log Error]
    H --> J
    I --> J
    
    G --> K[Return Response]
    J --> K
    
    classDef error fill:#ffcccc,stroke:#ff0000,stroke-width:2px
    classDef success fill:#ccffcc,stroke:#00ff00,stroke-width:2px
    
    class E,H,I,J error
    class G,K success
```

## Testing Strategy

```mermaid
graph TD
    A[Controller Tests] --> B[Base Controller Tests]
    A --> C[Jira Controller Tests]
    A --> D[GitLab Controller Tests]
    
    B --> E[Abstract Method Testing]
    B --> F[Common Functionality Testing]
    B --> G[Error Handling Testing]
    
    C --> H[Jira Validation Testing]
    C --> I[Dual Use Case Testing]
    C --> J[Response Combination Testing]
    
    D --> K[GitLab Validation Testing]
    D --> L[Event Type Testing]
    D --> M[Metrics Processing Testing]
    
    E --> N[Mock Implementations]
    F --> N
    G --> N
    H --> N
    I --> N
    J --> N
    K --> N
    L --> N
    M --> N
    
    classDef test fill:#ffffcc,stroke:#ffaa00,stroke-width:2px
    class B,C,D,E,F,G,H,I,J,K,L,M test
```

## Dependency Injection Flow

```mermaid
graph TD
    A[Application Container] --> B[Controller Registration]
    B --> C[Jira Webhook Controller]
    B --> D[GitLab Webhook Controller]
    
    C --> E[Jira Webhook Use Case]
    C --> F[Process Jira Event Use Case]
    D --> G[Process GitLab Event Use Case]
    
    H[Endpoint Registration] --> I[Jira Webhook Endpoint]
    H --> J[Metrics Webhook Endpoint]
    
    I --> C
    J --> C
    J --> D
    
    classDef container fill:#e6f3ff,stroke:#0066cc,stroke-width:2px
    classDef controller fill:#fff0e6,stroke:#ff6600,stroke-width:2px
    classDef endpoint fill:#f0e6ff,stroke:#6600cc,stroke-width:2px
    classDef usecase fill:#e6ffe6,stroke:#00cc00,stroke-width:2px
    
    class A,B,H container
    class C,D controller
    class I,J endpoint
    class E,F,G usecase
```

## Performance Comparison

```mermaid
graph LR
    A[Before Implementation] --> B[Code Duplication: 80%]
    A --> C[Files: 8 webhook handlers]
    A --> D[Lines of Code: 400+]
    A --> E[Test Files: 3]
    
    F[After Implementation] --> G[Code Duplication: 0%]
    F --> H[Files: 4 controllers + 1 base]
    F --> I[Lines of Code: 240]
    F --> J[Test Files: 3 + 3 controller tests]
    
    classDef before fill:#ffcccc,stroke:#ff0000,stroke-width:2px
    classDef after fill:#ccffcc,stroke:#00ff00,stroke-width:2px
    
    class A,B,C,D,E before
    class F,G,H,I,J after
```
