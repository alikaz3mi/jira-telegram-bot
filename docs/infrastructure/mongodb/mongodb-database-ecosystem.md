# 🌐 MongoDB Database Ecosystem Documentation

This document provides a comprehensive overview of the MongoDB database ecosystem for the jira-telegram-bot application, including all collections, relationships, and integration patterns.

## 📋 Table of Contents

1. [Database Overview](#database-overview)
2. [Collection Architecture](#collection-architecture)
3. [Entity Relationships](#entity-relationships)
4. [Project Ecosystem Flow](#project-ecosystem-flow)
5. [Integration Patterns](#integration-patterns)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Schema Definitions](#schema-definitions)

## 🗄️ Database Overview

The MongoDB ecosystem is organized around **project-centric architecture** where each project becomes a self-contained integration hub connecting multiple services.

```mermaid
graph TB
    subgraph "MongoDB Atlas Cluster"
        subgraph "Development Database"
            D1[jira_bot_dev]
        end
        subgraph "Staging Database"
            S1[jira_bot_staging]
        end
        subgraph "Production Database"
            P1[jira_bot_prod]
        end
    end

    subgraph "Application Layers"
        APP[Application Layer]
        CACHE[Cache Layer]
        API[API Gateway]
    end

    APP --> CACHE
    CACHE --> D1
    CACHE --> S1
    CACHE --> P1
    API --> APP
```

### Database Structure Per Environment

| Environment | Database Name | Purpose | Collections |
|------------|---------------|---------|-------------|
| Development | `jira_bot_dev` | Development and testing | All collections |
| Staging | `jira_bot_staging` | Pre-production testing | All collections |
| Production | `jira_bot_prod` | Live production data | All collections |

## 🏗️ Collection Architecture

The database is organized into logical groups based on functionality and relationships:

```mermaid
graph TB
    subgraph "Core Configuration Collections"
        JC[jira_connections]
        GS[google_services_config]
        TI[telegram_integrations]
        AS[application_settings]
        UA[user_authentication]
    end

    subgraph "Project Ecosystem Collections"
        PEM[project_ecosystem_mappings]
        NR[notification_routing]
        ID[integration_dependencies]
    end

    subgraph "User Management Collections"
        UP[user_profiles]
        UPref[user_preferences]
        TS[telegram_sessions]
        UAL[user_activity_logs]
    end

    subgraph "Business Data Collections"
        PR[progress_reports]
        NT[notification_tracking]
        PM[project_metadata]
        WS[workflow_states]
        IA[integration_activity]
    end

    subgraph "Analytics Collections"
        CC[calendar_cache]
        AM[analytics_metrics]
        DM[dashboard_metadata]
    end

    PEM --> JC
    PEM --> GS
    PEM --> TI
    UP --> UAL
    PR --> UP
    NT --> PEM
    WS --> PM
```

## 🔗 Entity Relationships

### Core Entity Relationship Diagram

```mermaid
erDiagram
    PROJECT_ECOSYSTEM_MAPPINGS {
        string project_key PK
        string project_name
        string jira_connection_id FK
        object google_services
        object telegram_integration
        array team_assignments
        object notification_routing
        datetime created_at
        datetime updated_at
        boolean is_active
    }

    JIRA_CONNECTIONS {
        string connection_id PK
        string connection_type
        string domain
        string username
        string password
        string token
        string email
        boolean is_primary
        boolean is_active
        array projects
        datetime created_at
        datetime updated_at
    }

    GOOGLE_SERVICES_CONFIG {
        string service_id PK
        string service_type
        string service_account_file
        object credentials_json
        array project_associations
        array scope_permissions
        object quota_limits
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    TELEGRAM_INTEGRATIONS {
        string integration_id PK
        string bot_token
        string bot_username
        string integration_type
        array channels
        array groups
        array project_associations
        array notification_rules
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    USER_PROFILES {
        string user_id PK
        string telegram_username
        int telegram_user_chat_id
        string jira_username
        string gitlab_username
        string google_sheet_name
        object user_components
        datetime created_at
        datetime updated_at
        boolean is_active
        datetime last_seen
        int version
    }

    PROGRESS_REPORTS {
        string report_id PK
        string assignee FK
        string project_key FK
        string sprint_id
        datetime reported_at
        object report_period
        array completed_tasks
        array in_progress_tasks
        array blocked_tasks
        float hours_logged
        object productivity_metrics
        datetime created_at
        datetime updated_at
        int version
    }

    NOTIFICATION_TRACKING {
        string notification_id PK
        string notification_type
        object target_entity
        object recipient
        string channel
        datetime sent_at
        string delivery_status
        string content_hash
        object metadata
        array related_notifications
        datetime created_at
        datetime expires_at
    }

    TELEGRAM_SESSIONS {
        string session_id PK
        int channel_post_id
        string issue_key
        int channel_chat_id
        int group_chat_id
        string user_id FK
        string message_type
        object metadata
        datetime created_at
        datetime updated_at
        datetime expires_at
        boolean is_active
    }

    PROJECT_ECOSYSTEM_MAPPINGS ||--|| JIRA_CONNECTIONS : "connects to"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ GOOGLE_SERVICES_CONFIG : "uses"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ TELEGRAM_INTEGRATIONS : "integrates with"
    USER_PROFILES ||--o{ PROGRESS_REPORTS : "creates"
    USER_PROFILES ||--o{ TELEGRAM_SESSIONS : "owns"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ PROGRESS_REPORTS : "contains"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ NOTIFICATION_TRACKING : "generates"
    TELEGRAM_SESSIONS ||--|| NOTIFICATION_TRACKING : "triggers"
```

## 🎯 Project Ecosystem Flow

### Project-Centric Integration Model

```mermaid
graph TB
    subgraph "Project: MYPROJECT"
        P1[Project Key: MYPROJECT]

        subgraph "Jira Integration"
            J1[Jira Server: jira.example.com]
            J2[Projects: MYPROJECT, PROJ2]
            J3[Issues & Workflows]
        end

        subgraph "Telegram Integration"
            T1[Channel: #myproject-updates]
            T2[Group: Development Team]
            T3[Bot: @myproject_bot]
            T4[Notifications & Messages]
        end

        subgraph "Google Services"
            G1[Sheets: Team Evaluation]
            G2[Docs: Project Documentation]
            G3[Drive: Project Files]
            G4[Service Account: myproject-svc]
        end

        subgraph "Team Members"
            U1[Backend Developers]
            U2[Frontend Developers]
            U3[AI Specialists]
            U4[DevOps Engineers]
        end

        subgraph "Notification Routing"
            N1[Deadline Alerts → Channel]
            N2[Progress Updates → Group]
            N3[Status Changes → Sheet]
            N4[Error Alerts → Admin Group]
        end
    end

    P1 --> J1
    P1 --> T1
    P1 --> G1
    P1 --> U1
    P1 --> N1

    J3 --> T4
    T4 --> G1
    G1 --> N1
    U1 --> J3
    U1 --> T4
```

### Multi-Project Ecosystem

```mermaid
graph LR
    subgraph "Project A: MYPROJECT"
        PA[MYPROJECT]
        JA[Jira Server A]
        TA[Telegram Bot A]
        GA[Google Sheets A]
        TeA[Team A]
    end

    subgraph "Project B: RADTHARN"
        PB[RADTHARN]
        JB[Jira Cloud B]
        TB[Telegram Bot B]
        GB[Google Sheets B]
        TeB[Team B]
    end

    subgraph "Project C: PROJ2"
        PC[PROJ2]
        JC[Jira Server C]
        TC[Telegram Bot C]
        GC[Google Sheets C]
        TeC[Team C]
    end

    subgraph "Shared Resources"
        SR[Shared Users]
        SC[Central Notification Hub]
        SA[Analytics Dashboard]
        SM[Management Console]
    end

    PA --> JA
    PA --> TA
    PA --> GA
    PA --> TeA

    PB --> JB
    PB --> TB
    PB --> GB
    PB --> TeB

    PC --> JC
    PC --> TC
    PC --> GC
    PC --> TeC

    TeA --> SR
    TeB --> SR
    TeC --> SR

    PA --> SC
    PB --> SC
    PC --> SC

    SC --> SA
    SA --> SM
```

## 🔄 Integration Patterns

### Cross-Service Entity Linking

```mermaid
sequenceDiagram
    participant J as Jira Issue
    participant T as Telegram Message
    participant G as Google Sheet Row
    participant N as Notification System
    participant DB as MongoDB

    Note over J,DB: Issue Creation Flow
    J->>+DB: Create Issue MYPROJECT-123
    DB->>+N: Trigger notification routing
    N->>+T: Post to #myproject-updates channel
    T-->>DB: Store telegram_session mapping
    N->>+G: Update Team Evaluation sheet
    G-->>DB: Store sheet row reference

    Note over J,DB: Cross-Service Linking
    DB->>DB: Create cross_service_link
    Note right of DB: Links: issue_key, message_id, sheet_row

    Note over J,DB: Status Update Flow
    J->>+DB: Update Issue Status
    DB->>+N: Check notification rules
    N->>T: Edit original message
    N->>G: Update sheet status
    DB->>DB: Update all linked entities
```

### Notification Routing Flow

```mermaid
graph TD
    A[Event Trigger] --> B{Event Type?}

    B -->|Deadline Alert| C[Check Project Config]
    B -->|Progress Update| D[Check Team Assignment]
    B -->|Status Change| E[Check Workflow Rules]
    B -->|Error Alert| F[Check Escalation Rules]

    C --> G{Project: MYPROJECT?}
    D --> H{Team: Backend?}
    E --> I{Status: Done?}
    F --> J{Severity: Critical?}

    G -->|Yes| K[Route to #myproject-updates]
    G -->|No| L[Route to default channel]

    H -->|Yes| M[Route to Backend Group]
    H -->|No| N[Route to All Team Group]

    I -->|Yes| O[Update Google Sheet + Notify]
    I -->|No| P[Update Telegram Only]

    J -->|Yes| Q[Escalate to Admin + SMS]
    J -->|No| R[Standard Channel Notification]

    K --> S[Store in notification_tracking]
    L --> S
    M --> S
    N --> S
    O --> S
    P --> S
    Q --> S
    R --> S

    %% Styling
    classDef trigger fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#fff
    classDef decision fill:#ff9800,stroke:#f57c00,stroke-width:2px,color:#fff
    classDef check fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef route fill:#7b1fa2,stroke:#6a1b9a,stroke-width:2px,color:#fff
    classDef store fill:#388e3c,stroke:#2e7d32,stroke-width:2px,color:#fff

    class A trigger
    class B,G,H,I,J decision
    class C,D,E,F check
    class K,L,M,N,O,P,Q,R route
    class S store
```

## 📊 Data Flow Diagrams

### User Action Data Flow

```mermaid
graph TB
    subgraph "User Interaction"
        U1[User creates Jira issue]
        U2[User posts in Telegram]
        U3[User updates Google Sheet]
    end

    subgraph "Event Processing"
        E1[Jira Webhook]
        E2[Telegram Bot Handler]
        E3[Google Sheets API]
    end

    subgraph "MongoDB Operations"
        M1[Update workflow_states]
        M2[Create telegram_session]
        M3[Log notification_tracking]
        M4[Update progress_reports]
    end

    subgraph "Cross-Service Sync"
        S1[Update linked Telegram message]
        S2[Update linked Google Sheet row]
        S3[Update linked Jira issue]
        S4[Send notifications]
    end

    U1 --> E1
    U2 --> E2
    U3 --> E3

    E1 --> M1
    E2 --> M2
    E3 --> M4

    M1 --> S1
    M1 --> S2
    M2 --> S3
    M2 --> S4
    M3 --> S4
    M4 --> S1

    %% Styling
    classDef user fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef event fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#fff
    classDef mongo fill:#ff9800,stroke:#f57c00,stroke-width:2px,color:#fff
    classDef sync fill:#7b1fa2,stroke:#6a1b9a,stroke-width:2px,color:#fff

    class U1,U2,U3 user
    class E1,E2,E3 event
    class M1,M2,M3,M4 mongo
    class S1,S2,S3,S4 sync
```

### Analytics Data Aggregation

```mermaid
graph LR
    subgraph "Data Sources"
        DS1[progress_reports]
        DS2[notification_tracking]
        DS3[telegram_sessions]
        DS4[workflow_states]
        DS5[user_activity_logs]
    end

    subgraph "Aggregation Pipeline"
        AP1[Daily Aggregation]
        AP2[Weekly Aggregation]
        AP3[Monthly Aggregation]
        AP4[Project Aggregation]
        AP5[Team Aggregation]
    end

    subgraph "Dashboard Collections"
        DC1[hr_dashboard_metrics]
        DC2[financial_dashboard_metrics]
        DC3[executive_dashboard_metrics]
        DC4[real_time_metrics]
    end

    subgraph "External Dashboards"
        ED1[Grafana HR Dashboard]
        ED2[Grafana Financial Dashboard]
        ED3[Grafana Executive Dashboard]
    end

    DS1 --> AP1
    DS2 --> AP1
    DS3 --> AP2
    DS4 --> AP3
    DS5 --> AP4

    AP1 --> DC1
    AP2 --> DC2
    AP3 --> DC3
    AP4 --> DC4
    AP5 --> DC4

    DC1 --> ED1
    DC2 --> ED2
    DC3 --> ED3
    DC4 --> ED1
    DC4 --> ED2
    DC4 --> ED3

    %% Styling
    classDef source fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef pipeline fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#fff
    classDef collection fill:#ff9800,stroke:#f57c00,stroke-width:2px,color:#fff
    classDef dashboard fill:#7b1fa2,stroke:#6a1b9a,stroke-width:2px,color:#fff

    class DS1,DS2,DS3,DS4,DS5 source
    class AP1,AP2,AP3,AP4,AP5 pipeline
    class DC1,DC2,DC3,DC4 collection
    class ED1,ED2,ED3 dashboard
```

## 📋 Schema Definitions

### Core Collections Schema

#### project_ecosystem_mappings
```json
{
  "_id": "ObjectId",
  "project_key": "MYPROJECT",
  "project_name": "MyProject Development",
  "jira_connection_id": "jira_server_main",
  "google_services": {
    "sheets_service_id": "myproject_sheets_svc",
    "docs_service_id": "myproject_docs_svc",
    "primary_sheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
    "project_folder_id": "1BxYZ9876543210abcdef"
  },
  "telegram_integration": {
    "primary_channel_id": -1001234567890,
    "notification_channel_id": -1001234567891,
    "team_group_id": -1001234567892,
    "bot_integration_id": "myproject_bot_main"
  },
  "team_assignments": [
    {
      "user_id": "admin_user",
      "role": "DevOps Lead",
      "department": "DevOps",
      "access_level": "admin"
    },
    {
      "user_id": "dev_user_1",
      "role": "Backend Developer",
      "department": "Backend",
      "access_level": "developer"
    }
  ],
  "notification_routing": {
    "deadline_notifications": {
      "channel_id": -1001234567890,
      "mention_groups": ["@backend-team"],
      "severity_escalation": true
    },
    "progress_notifications": {
      "group_id": -1001234567892,
      "frequency": "daily",
      "include_metrics": true
    },
    "status_change_notifications": {
      "channel_id": -1001234567890,
      "update_google_sheet": true,
      "notify_stakeholders": true
    }
  },
  "created_at": "2025-09-01T00:00:00Z",
  "updated_at": "2025-09-01T00:00:00Z",
  "is_active": true
}
```

#### jira_connections
```json
{
  "_id": "ObjectId",
  "connection_id": "jira_server_main",
  "connection_type": "server",
  "domain": "https://jira.example.com",
  "username": "admin_user",
  "password": "encrypted_password_hash",
  "token": null,
  "email": null,
  "is_primary": true,
  "is_active": true,
  "projects": ["MYPROJECT", "PROJ2", "RADTHARN"],
  "api_config": {
    "timeout": 30,
    "retry_attempts": 3,
    "rate_limit": 100
  },
  "created_at": "2025-09-01T00:00:00Z",
  "updated_at": "2025-09-01T00:00:00Z"
}
```

#### telegram_integrations
```json
{
  "_id": "ObjectId",
  "integration_id": "myproject_bot_main",
  "bot_token": "encrypted_bot_token",
  "bot_username": "myproject_bot",
  "integration_type": "project",
  "channels": [
    {
      "channel_id": -1001234567890,
      "channel_name": "myproject-updates",
      "channel_type": "public",
      "project_associations": ["MYPROJECT"],
      "allowed_operations": ["post", "edit", "delete"],
      "notification_types": ["deadlines", "progress", "status"]
    }
  ],
  "groups": [
    {
      "group_id": -1001234567892,
      "group_name": "MyProject Development Team",
      "team_associations": ["Backend", "Frontend", "DevOps"],
      "allowed_users": ["admin_user", "dev_user_1", "dev_user_2"],
      "permissions": {
        "can_create_issues": true,
        "can_update_status": true,
        "can_assign_tasks": false
      }
    }
  ],
  "project_associations": ["MYPROJECT"],
  "notification_rules": [
    {
      "rule_id": "deadline_alerts",
      "trigger": "issue_deadline_approaching",
      "target_channel": -1001234567890,
      "conditions": {
        "days_before": 2,
        "priority": ["High", "Highest"],
        "project": "MYPROJECT"
      }
    }
  ],
  "is_active": true,
  "created_at": "2025-09-01T00:00:00Z",
  "updated_at": "2025-09-01T00:00:00Z"
}
```

### Index Strategy

#### Core Indexes
```javascript
// project_ecosystem_mappings
db.project_ecosystem_mappings.createIndex({ "project_key": 1 }, { unique: true })
db.project_ecosystem_mappings.createIndex({ "is_active": 1, "created_at": -1 })
db.project_ecosystem_mappings.createIndex({ "team_assignments.user_id": 1 })

// jira_connections
db.jira_connections.createIndex({ "connection_id": 1 }, { unique: true })
db.jira_connections.createIndex({ "is_active": 1, "is_primary": -1 })
db.jira_connections.createIndex({ "projects": 1 })

// telegram_integrations
db.telegram_integrations.createIndex({ "integration_id": 1 }, { unique: true })
db.telegram_integrations.createIndex({ "project_associations": 1 })
db.telegram_integrations.createIndex({ "channels.channel_id": 1 })
db.telegram_integrations.createIndex({ "groups.group_id": 1 })

// user_profiles
db.user_profiles.createIndex({ "user_id": 1 }, { unique: true })
db.user_profiles.createIndex({ "telegram_username": 1 }, { unique: true })
db.user_profiles.createIndex({ "jira_username": 1 })
db.user_profiles.createIndex({ "is_active": 1, "last_seen": -1 })

// progress_reports
db.progress_reports.createIndex({ "report_id": 1 }, { unique: true })
db.progress_reports.createIndex({ "assignee": 1, "reported_at": -1 })
db.progress_reports.createIndex({ "project_key": 1, "reported_at": -1 })
db.progress_reports.createIndex({ "sprint_id": 1 })

// telegram_sessions
db.telegram_sessions.createIndex({ "session_id": 1 }, { unique: true })
db.telegram_sessions.createIndex({ "channel_post_id": 1 }, { unique: true })
db.telegram_sessions.createIndex({ "issue_key": 1 })
db.telegram_sessions.createIndex({ "user_id": 1, "created_at": -1 })
db.telegram_sessions.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })

// notification_tracking
db.notification_tracking.createIndex({ "notification_id": 1 }, { unique: true })
db.notification_tracking.createIndex({ "target_entity.entity_id": 1, "sent_at": -1 })
db.notification_tracking.createIndex({ "recipient.user_id": 1, "sent_at": -1 })
db.notification_tracking.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })
```

## 🔍 Query Patterns

### Common Query Examples

#### Get Project Ecosystem
```javascript
// Get complete ecosystem for a project
db.project_ecosystem_mappings.aggregate([
  { $match: { "project_key": "MYPROJECT", "is_active": true } },
  {
    $lookup: {
      from: "jira_connections",
      localField: "jira_connection_id",
      foreignField: "connection_id",
      as: "jira_config"
    }
  },
  {
    $lookup: {
      from: "telegram_integrations",
      localField: "telegram_integration.bot_integration_id",
      foreignField: "integration_id",
      as: "telegram_config"
    }
  },
  {
    $lookup: {
      from: "google_services_config",
      localField: "google_services.sheets_service_id",
      foreignField: "service_id",
      as: "google_sheets_config"
    }
  }
])
```

#### Get User's Project Assignments
```javascript
// Get all projects assigned to a user
db.project_ecosystem_mappings.find({
  "team_assignments.user_id": "admin_user",
  "is_active": true
}, {
  "project_key": 1,
  "project_name": 1,
  "team_assignments.$": 1
})
```

#### Get Notification Routing Rules
```javascript
// Get notification routing for project deadlines
db.project_ecosystem_mappings.aggregate([
  { $match: { "project_key": "MYPROJECT" } },
  {
    $lookup: {
      from: "telegram_integrations",
      localField: "telegram_integration.bot_integration_id",
      foreignField: "integration_id",
      as: "telegram_config"
    }
  },
  {
    $project: {
      "project_key": 1,
      "deadline_routing": "$notification_routing.deadline_notifications",
      "telegram_channels": "$telegram_config.channels"
    }
  }
])
```

This ecosystem documentation provides a complete view of how all the services, data, and integrations work together in a project-centric model. Each project becomes its own self-contained integration hub while maintaining flexibility for cross-project shared resources and users.
