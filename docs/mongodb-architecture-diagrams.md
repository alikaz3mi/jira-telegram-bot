# 🏛️ MongoDB Database Architecture Diagrams

This document contains detailed mermaid diagrams showing the complete architecture of the MongoDB database ecosystem for the jira-telegram-bot application.

## 📊 High-Level System Architecture

### Complete System Overview
```mermaid
graph TB
    subgraph "External Services"
        subgraph "Jira Instances"
            JS[Jira Server: jira.parstechai.com]
            JC[Jira Cloud: atlassian.net]
        end

        subgraph "Google Services"
            GS[Google Sheets API]
            GD[Google Docs API]
            GDR[Google Drive API]
            GAC[Google Service Accounts]
        end

        subgraph "Telegram Services"
            TB[Telegram Bot API]
            TCH[Telegram Channels]
            TGR[Telegram Groups]
        end

        subgraph "Analytics"
            GR[Grafana Dashboards]
            PM[Prometheus Metrics]
        end
    end

    subgraph "Application Layer"
        subgraph "API Gateway"
            WH[Webhook Endpoints]
            REST[REST API]
            CLI[CLI Interface]
        end

        subgraph "Business Logic"
            UC[Use Cases]
            SVC[Services]
            WF[Workflows]
        end

        subgraph "Data Access"
            REPO[Repositories]
            GW[Gateways]
            CACHE[Cache Layer]
        end
    end

    subgraph "MongoDB Atlas Cluster"
        subgraph "Development"
            DEV[(jira_bot_dev)]
        end

        subgraph "Staging"
            STG[(jira_bot_staging)]
        end

        subgraph "Production"
            PROD[(jira_bot_prod)]
        end
    end

    %% External to Application
    JS --> WH
    JC --> WH
    TB --> WH

    WH --> UC
    REST --> UC
    CLI --> UC

    UC --> SVC
    SVC --> WF

    WF --> REPO
    REPO --> GW
    GW --> CACHE

    %% Database connections
    CACHE --> DEV
    CACHE --> STG
    CACHE --> PROD

    %% Application to External
    REPO --> JS
    REPO --> JC
    GW --> GS
    GW --> GD
    GW --> GDR
    GW --> TB

    %% Analytics
    PROD --> PM
    PM --> GR

    %% Styling
    classDef external fill:#1565c0,stroke:#0d47a1,stroke-width:3px,color:#fff
    classDef application fill:#6a1b9a,stroke:#4a148c,stroke-width:3px,color:#fff
    classDef database fill:#2e7d32,stroke:#1b5e20,stroke-width:3px,color:#fff
    classDef analytics fill:#e65100,stroke:#bf360c,stroke-width:3px,color:#fff

    class JS,JC,GS,GD,GDR,TB,TCH,TGR external
    class WH,REST,CLI,UC,SVC,WF,REPO,GW,CACHE application
    class DEV,STG,PROD database
    class GR,PM analytics
```

## 🗄️ Database Collections Architecture

### Core Collections Overview
```mermaid
graph TB
    subgraph "Configuration Layer"
        subgraph "Connection Management"
            JC[jira_connections<br/>🔗 Jira Server/Cloud configs]
            GS[google_services_config<br/>📊 Sheets/Docs/Drive configs]
            TI[telegram_integrations<br/>📱 Bot/Channel/Group configs]
        end

        subgraph "Application Settings"
            AS[application_settings<br/>⚙️ Global configurations]
            UA[user_authentication<br/>🔐 Auth tokens & sessions]
        end
    end

    subgraph "Project Ecosystem Layer"
        PEM[project_ecosystem_mappings<br/>🎯 Project hub configurations]
        NR[notification_routing<br/>📢 Smart routing rules]
        ID[integration_dependencies<br/>🔗 Cross-service linking]
    end

    subgraph "User Management Layer"
        UP[user_profiles<br/>👤 User identity & preferences]
        UPref[user_preferences<br/>⚙️ Personal settings]
        TS[telegram_sessions<br/>💬 Active chat sessions]
        UAL[user_activity_logs<br/>📝 Activity tracking]
    end

    subgraph "Business Data Layer"
        PR[progress_reports<br/>📈 Sprint/Task progress]
        NT[notification_tracking<br/>📬 Message delivery logs]
        PM[project_metadata<br/>📋 Project information]
        WS[workflow_states<br/>🔄 Issue state tracking]
        IA[integration_activity<br/>🔄 Cross-service events]
    end

    subgraph "Analytics Layer"
        CC[calendar_cache<br/>📅 Holiday/workday data]
        AM[analytics_metrics<br/>📊 Computed metrics]
        DM[dashboard_metadata<br/>📈 Dashboard configurations]
    end

    %% Primary relationships
    PEM --> JC
    PEM --> GS
    PEM --> TI
    PEM --> NR

    UP --> UAL
    UP --> UPref
    UP --> TS
    UP --> PR

    PR --> PEM
    NT --> PEM
    WS --> PM
    IA --> ID

    %% Analytics relationships
    PR --> AM
    UAL --> AM
    WS --> AM
    AM --> DM

    %% Styling
    classDef config fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef ecosystem fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#fff
    classDef user fill:#c62828,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef business fill:#f57c00,stroke:#e65100,stroke-width:2px,color:#fff
    classDef analytics fill:#6a1b9a,stroke:#4a148c,stroke-width:2px,color:#fff

    class JC,GS,TI,AS,UA config
    class PEM,NR,ID ecosystem
    class UP,UPref,TS,UAL user
    class PR,NT,PM,WS,IA business
    class CC,AM,DM analytics
```

## 🔄 Project Ecosystem Data Flow

### Project-Centric Integration Model
```mermaid
graph TB
    subgraph "Project: PARSCHAT"
        subgraph "Project Configuration"
            PC[Project Ecosystem Mapping<br/>Key: PARSCHAT]
        end

        subgraph "Jira Integration"
            JI[Jira Server Connection<br/>jira.parstechai.com]
            JP[Project Keys: PARSCHAT, PCD]
            JW[Workflows & Issues]
        end

        subgraph "Telegram Integration"
            TC[Channel: #parschat-updates<br/>ID: -1001234567890]
            TG[Group: Development Team<br/>ID: -1001234567892]
            TB[Bot: @parschat_bot]
        end

        subgraph "Google Services"
            GSheet[Team Evaluation Sheet<br/>ID: 1TCvcE_IsP6...]
            GDocs[Project Documentation]
            GDrive[File Storage]
        end

        subgraph "Team Members"
            U1[👤 alikaz3mi<br/>DevOps Lead]
            U2[👤 msameim181<br/>Backend Dev]
            U3[👤 jhamed<br/>Frontend Dev]
        end

        subgraph "Notification Routing"
            NDeadline[🚨 Deadline Alerts<br/>→ #parschat-updates]
            NProgress[📊 Progress Updates<br/>→ Development Team]
            NStatus[🔄 Status Changes<br/>→ Google Sheet + Channel]
            NError[❌ Error Alerts<br/>→ Admin Group]
        end

        subgraph "Data Tracking"
            DT1[📈 Progress Reports]
            DT2[📬 Notification Logs]
            DT3[💬 Telegram Sessions]
            DT4[🔄 Workflow States]
        end
    end

    %% Configuration flows
    PC --> JI
    PC --> TC
    PC --> GSheet
    PC --> U1
    PC --> NDeadline

    %% Integration flows
    JW --> TB
    TB --> TC
    TC --> GSheet
    GSheet --> NDeadline

    %% User interactions
    U1 --> JW
    U1 --> TB
    U2 --> JW
    U2 --> TB
    U3 --> JW
    U3 --> TB

    %% Data tracking
    JW --> DT4
    TB --> DT3
    NDeadline --> DT2
    U1 --> DT1

    %% Notification flows
    DT4 --> NStatus
    DT1 --> NProgress
    DT2 --> NError

    %% Styling
    classDef project fill:#2e7d32,stroke:#1b5e20,stroke-width:3px,color:#fff
    classDef jira fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef telegram fill:#0277bd,stroke:#01579b,stroke-width:2px,color:#fff
    classDef google fill:#388e3c,stroke:#2e7d32,stroke-width:2px,color:#fff
    classDef user fill:#d32f2f,stroke:#c62828,stroke-width:2px,color:#fff
    classDef notification fill:#f57c00,stroke:#ef6c00,stroke-width:2px,color:#fff
    classDef data fill:#7b1fa2,stroke:#6a1b9a,stroke-width:2px,color:#fff

    class PC,JI,JP,JW project
    class JI,JP,JW jira
    class TC,TG,TB telegram
    class GSheet,GDocs,GDrive google
    class U1,U2,U3 user
    class NDeadline,NProgress,NStatus,NError notification
    class DT1,DT2,DT3,DT4 data
```

## 🔗 Entity Relationship Flows

### Core Entity Relationships
```mermaid
erDiagram
    PROJECT_ECOSYSTEM_MAPPINGS {
        string project_key PK "PARSCHAT"
        string project_name "ParsChat Development"
        string jira_connection_id FK "jira_server_main"
        object google_services "Service configs"
        object telegram_integration "Bot configs"
        array team_assignments "User roles"
        object notification_routing "Routing rules"
        boolean is_active "true"
        datetime created_at
        datetime updated_at
    }

    JIRA_CONNECTIONS {
        string connection_id PK "jira_server_main"
        string connection_type "server|cloud"
        string domain "jira.parstechai.com"
        string username "ali_kazemi"
        string password "encrypted"
        string token "for cloud"
        boolean is_primary "true"
        array projects "PARSCHAT,PCD"
        datetime created_at
        datetime updated_at
    }

    TELEGRAM_INTEGRATIONS {
        string integration_id PK "parschat_bot_main"
        string bot_token "encrypted"
        string bot_username "parschat_bot"
        array channels "Channel configs"
        array groups "Group configs"
        array project_associations "PARSCHAT"
        array notification_rules "Routing rules"
        boolean is_active "true"
        datetime created_at
        datetime updated_at
    }

    GOOGLE_SERVICES_CONFIG {
        string service_id PK "parschat_sheets_svc"
        string service_type "sheets|docs|drive"
        object credentials_json "Service account"
        array project_associations "PARSCHAT"
        array scope_permissions "Sheets read/write"
        boolean is_active "true"
        datetime created_at
        datetime updated_at
    }

    USER_PROFILES {
        string user_id PK "alikaz3mi"
        string telegram_username "alikaz3mi"
        int telegram_user_chat_id "123456789"
        string jira_username "ali_kazemi"
        string google_sheet_name "Ali Kazemi"
        object user_components "DevOps,Backend"
        boolean is_active "true"
        datetime last_seen
        int version "1"
    }

    PROGRESS_REPORTS {
        string report_id PK "auto-generated"
        string assignee FK "alikaz3mi"
        string project_key FK "PARSCHAT"
        string sprint_id "PARSCHAT Sprint 1"
        datetime reported_at
        object report_period "2025-09-01 to 2025-09-07"
        array completed_tasks "Task IDs"
        array in_progress_tasks "Task IDs"
        float hours_logged "40.5"
        object productivity_metrics "Computed scores"
        datetime created_at
        int version "1"
    }

    TELEGRAM_SESSIONS {
        string session_id PK "auto-generated"
        int channel_post_id "123"
        string issue_key "PARSCHAT-123"
        int channel_chat_id "-1001234567890"
        string user_id FK "alikaz3mi"
        string message_type "deadline_notification"
        object metadata "Issue details"
        boolean is_active "true"
        datetime expires_at
    }

    NOTIFICATION_TRACKING {
        string notification_id PK "auto-generated"
        string notification_type "deadline_alert"
        object target_entity "Issue PARSCHAT-123"
        object recipient "Channel/User info"
        string channel "telegram|email|sms"
        datetime sent_at
        string delivery_status "delivered|failed"
        object metadata "Message content"
        datetime expires_at
    }

    WORKFLOW_STATES {
        string state_id PK "auto-generated"
        string issue_key "PARSCHAT-123"
        string project_key FK "PARSCHAT"
        string from_status "In Progress"
        string to_status "Done"
        string assignee FK "alikaz3mi"
        datetime transition_at
        object transition_metadata "User, reason"
        datetime created_at
    }

    %% Primary relationships
    PROJECT_ECOSYSTEM_MAPPINGS ||--|| JIRA_CONNECTIONS : "connects_to"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ GOOGLE_SERVICES_CONFIG : "uses_services"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ TELEGRAM_INTEGRATIONS : "integrates_with"

    %% User relationships
    USER_PROFILES ||--o{ PROGRESS_REPORTS : "creates"
    USER_PROFILES ||--o{ TELEGRAM_SESSIONS : "owns"
    USER_PROFILES ||--o{ WORKFLOW_STATES : "triggers"

    %% Project relationships
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ PROGRESS_REPORTS : "contains"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ WORKFLOW_STATES : "tracks"
    PROJECT_ECOSYSTEM_MAPPINGS ||--o{ NOTIFICATION_TRACKING : "generates"

    %% Cross-linking relationships
    TELEGRAM_SESSIONS ||--|| WORKFLOW_STATES : "linked_by_issue"
    WORKFLOW_STATES ||--o{ NOTIFICATION_TRACKING : "triggers"
    PROGRESS_REPORTS ||--o{ NOTIFICATION_TRACKING : "reports_via"
```

## 🔄 Cross-Service Integration Flow

### Multi-Service Event Propagation
```mermaid
sequenceDiagram
    participant J as Jira Issue
    participant WH as Webhook Handler
    participant DB as MongoDB
    participant PEM as Project Ecosystem Manager
    participant T as Telegram Bot
    participant G as Google Sheets
    participant N as Notification Tracker

    Note over J,N: Issue Status Change Event

    %% Initial event
    J->>+WH: Issue PARSCHAT-123 status: In Progress → Done
    WH->>+DB: Find project ecosystem mapping

    Note over DB: Query: project_ecosystem_mappings.find({project_key: "PARSCHAT"})

    DB-->>WH: Project config with integrations
    WH->>+PEM: Process status change event

    %% Project ecosystem processing
    PEM->>+DB: Store workflow state transition
    DB-->>PEM: State stored with ID

    PEM->>+DB: Check notification routing rules
    DB-->>PEM: Routing: update sheet + notify channel

    %% Parallel service updates
    par Telegram Update
        PEM->>+T: Find linked telegram session
        T->>DB: Query: telegram_sessions.find({issue_key: "PARSCHAT-123"})
        DB-->>T: Session with message_id: 456
        T->>T: Edit message with new status
        T->>+N: Log telegram notification
    and Google Sheets Update
        PEM->>+G: Update team evaluation sheet
        G->>G: Find row by issue assignee
        G->>G: Update status column
        G->>+N: Log sheet update notification
    end

    %% Notification tracking
    N->>+DB: Store notification records
    DB-->>N: Notifications logged

    %% Cross-reference linking
    PEM->>+DB: Create cross-service links
    Note over DB: Links: workflow_state_id ↔ telegram_session_id ↔ sheet_row_id
    DB-->>PEM: Links established

    PEM-->>WH: Event processed successfully
    WH-->>J: 200 OK

    Note over J,N: All services synchronized with cross-references
```

### Notification Routing Decision Tree
```mermaid
graph TD
    A[📨 Event Triggered] --> B{Identify Event Type}

    B -->|Issue Deadline| C[🚨 Deadline Event]
    B -->|Status Change| D[🔄 Status Event]
    B -->|Progress Update| E[📊 Progress Event]
    B -->|System Error| F[❌ Error Event]

    C --> G{Check Project Config}
    D --> G
    E --> G
    F --> G

    G --> H[📋 Get Project Ecosystem Mapping]
    H --> I{Project: PARSCHAT?}

    I -->|Yes| J[Load PARSCHAT Config]
    I -->|No| K[Load Default Config]

    J --> L{Event Severity}
    K --> L

    L -->|Critical| M[🔴 Critical Path]
    L -->|High| N[🟡 High Priority Path]
    L -->|Normal| O[🟢 Normal Path]

    M --> P[Send to Channel + Group + Admin]
    N --> Q[Send to Channel + Group]
    O --> R[Send to Channel Only]

    P --> S[📝 Log to notification_tracking]
    Q --> S
    R --> S

    S --> T{Cross-Service Updates Required?}

    T -->|Yes| U[Update Google Sheet]
    T -->|Yes| V[Update Telegram Message]
    T -->|Yes| W[Update Jira Comment]
    T -->|No| X[End]

    U --> Y[Create Cross-Links]
    V --> Y
    W --> Y
    Y --> X

    %% Styling
    classDef event fill:#fff3e0
    classDef decision fill:#e3f2fd
    classDef action fill:#e8f5e8
    classDef critical fill:#ffebee
    classDef normal fill:#f1f8e9

    class A,C,D,E,F event
    class B,G,I,L,T decision
    class H,J,K,P,Q,R,S,U,V,W,Y,X action
    class M critical
    class N,O normal
```

## 📊 Analytics & Dashboard Data Flow

### Multi-Level Analytics Architecture
```mermaid
graph TB
    subgraph "Raw Data Sources"
        subgraph "User Activity"
            PR[progress_reports]
            UAL[user_activity_logs]
            TS[telegram_sessions]
        end

        subgraph "System Events"
            WS[workflow_states]
            NT[notification_tracking]
            IA[integration_activity]
        end

        subgraph "Project Data"
            PEM[project_ecosystem_mappings]
            PM[project_metadata]
        end
    end

    subgraph "Aggregation Pipeline"
        subgraph "Time-Based Aggregation"
            DA[📅 Daily Aggregator]
            WA[📅 Weekly Aggregator]
            MA[📅 Monthly Aggregator]
        end

        subgraph "Entity-Based Aggregation"
            UA[👤 User Aggregator]
            PA[🎯 Project Aggregator]
            TA[👥 Team Aggregator]
        end

        subgraph "Metric Computation"
            PC[📊 Performance Calculator]
            QC[✅ Quality Calculator]
            EC[⚡ Efficiency Calculator]
        end
    end

    subgraph "Aggregated Collections"
        subgraph "Dashboard Collections"
            HDM[hr_dashboard_metrics<br/>📊 HR KPIs]
            FDM[financial_dashboard_metrics<br/>💰 Financial KPIs]
            EDM[executive_dashboard_metrics<br/>📈 Executive KPIs]
        end

        subgraph "Real-Time Collections"
            RTM[real_time_metrics<br/>⚡ Live data]
            ALR[alert_rules<br/>🚨 Threshold monitoring]
        end

        subgraph "Historical Collections"
            HAM[historical_analytics_metrics<br/>📈 Trends]
            BAM[benchmark_analytics_metrics<br/>🎯 Baselines]
        end
    end

    subgraph "External Dashboards"
        subgraph "Grafana Dashboards"
            GHR[📊 HR Dashboard<br/>Team Performance]
            GFN[💰 Financial Dashboard<br/>Project Costs]
            GEX[📈 Executive Dashboard<br/>Business Metrics]
        end

        subgraph "Alerts & Monitoring"
            GA[🚨 Grafana Alerts]
            PM[📊 Prometheus Metrics]
            SL[📱 Slack Notifications]
        end
    end

    %% Data flow from sources to aggregators
    PR --> DA
    UAL --> DA
    TS --> WA
    WS --> DA
    NT --> WA
    IA --> MA
    PEM --> PA
    PM --> PA

    %% Aggregation flows
    DA --> UA
    WA --> UA
    MA --> UA
    DA --> PA
    WA --> PA
    MA --> PA
    UA --> TA
    PA --> TA

    %% Metric computation
    UA --> PC
    PA --> PC
    TA --> PC
    PC --> QC
    PC --> EC
    QC --> EC

    %% Dashboard data flows
    PC --> HDM
    QC --> FDM
    EC --> EDM
    PC --> RTM
    QC --> RTM
    EC --> RTM

    %% Historical flows
    HDM --> HAM
    FDM --> HAM
    EDM --> HAM
    RTM --> BAM

    %% External dashboard flows
    HDM --> GHR
    FDM --> GFN
    EDM --> GEX
    RTM --> GA
    RTM --> PM
    GA --> SL

    %% Alert flows
    ALR --> GA
    RTM --> ALR

    %% Styling
    classDef source fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef aggregator fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#fff
    classDef collection fill:#f57c00,stroke:#ef6c00,stroke-width:2px,color:#fff
    classDef dashboard fill:#7b1fa2,stroke:#6a1b9a,stroke-width:2px,color:#fff
    classDef alert fill:#c62828,stroke:#b71c1c,stroke-width:2px,color:#fff

    class PR,UAL,TS,WS,NT,IA,PEM,PM source
    class DA,WA,MA,UA,PA,TA,PC,QC,EC aggregator
    class HDM,FDM,EDM,RTM,ALR,HAM,BAM collection
    class GHR,GFN,GEX dashboard
    class GA,PM,SL alert
```

### Real-Time Metrics Flow
```mermaid
sequenceDiagram
    participant US as User Action
    participant WF as Workflow Engine
    participant DB as MongoDB Collections
    participant AGG as Aggregation Pipeline
    participant CACHE as Redis Cache
    participant GRAF as Grafana Dashboard
    participant ALERT as Alert System

    Note over US,ALERT: Real-Time Metrics Pipeline

    %% User action triggers
    US->>+WF: Complete task PARSCHAT-123
    WF->>+DB: Update workflow_states
    WF->>+DB: Log to user_activity_logs
    WF->>+DB: Update progress_reports

    %% Immediate aggregation trigger
    DB->>+AGG: Trigger real-time aggregation

    par User Metrics
        AGG->>AGG: Calculate user productivity
        AGG->>AGG: Update completion rate
        AGG->>+DB: Store in real_time_metrics
    and Project Metrics
        AGG->>AGG: Calculate project progress
        AGG->>AGG: Update velocity metrics
        AGG->>+DB: Store in real_time_metrics
    and Team Metrics
        AGG->>AGG: Calculate team performance
        AGG->>AGG: Update collaboration score
        AGG->>+DB: Store in real_time_metrics
    end

    %% Cache update
    DB->>+CACHE: Update cached metrics
    CACHE-->>DB: Cache refreshed

    %% Dashboard update
    CACHE->>+GRAF: Push metrics update
    GRAF->>GRAF: Refresh dashboard panels

    %% Alert checking
    AGG->>+ALERT: Check threshold rules

    alt Threshold Exceeded
        ALERT->>ALERT: Generate alert
        ALERT->>+DB: Log alert to notification_tracking
        ALERT->>GRAF: Send to Grafana alerting
        GRAF->>GRAF: Display alert notification
    else Normal Range
        ALERT->>ALERT: No action needed
    end

    GRAF-->>US: Dashboard shows updated metrics

    Note over US,ALERT: Metrics updated in <2 seconds
```

This architecture documentation provides a complete visual representation of how the MongoDB database ecosystem integrates with all external services and maintains real-time synchronization across the entire project ecosystem.
