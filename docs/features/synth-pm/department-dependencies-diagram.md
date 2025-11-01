# Department Dependencies - Visual Diagrams

## System Architecture

```mermaid
graph TB
    subgraph "Google Sheets"
        A[PM Board Sheet]
        A1[Row: Task Title]
        A2[Column: Department Deps]
        A3[Column: ETA Hours]
        A4[Column: Deadline]
        A --> A1
        A --> A2
        A --> A3
        A --> A4
    end

    subgraph "Processing"
        B[SynthPM UseCase]
        C[SynthPM Repository]
        D[DepartmentDependencyCalculator]
        
        B --> C
        C --> D
    end

    subgraph "Jira Output"
        E[Parent Story]
        F1[UI/UX Subtask]
        F2[Frontend Subtask]
        F3[Backend Subtask]
        F4[AI Subtask]
        
        E --> F1
        E --> F2
        E --> F3
        E --> F4
        
        F1 -.blocks.-> F2
    end

    A --> B
    D --> E

    style A fill:#e1f5fe
    style B fill:#fff3e0
    style C fill:#fff3e0
    style D fill:#fff3e0
    style E fill:#f1f8e9
    style F1 fill:#e8f5e9
    style F2 fill:#e8f5e9
    style F3 fill:#e8f5e9
    style F4 fill:#e8f5e9
```

## Dependency Parsing Flow

```mermaid
graph LR
    A["Input String<br/>'UI/UX blocks Frontend, Backend blocks AI'"]
    B[Split by comma]
    C["'UI/UX blocks Frontend'"]
    D["'Backend blocks AI'"]
    E["Split by 'blocks' or '->'"]
    F[Parse pairs]
    G["Result:<br/>{<br/>  'Frontend': ['UI/UX'],<br/>  'AI': ['Backend']<br/>}"]
    
    A --> B
    B --> C
    B --> D
    C --> E
    D --> E
    E --> F
    F --> G

    style A fill:#ffebee
    style G fill:#e8f5e9
```

## Timeline Calculation Example

### Example 1: Simple Chain (UI/UX blocks Frontend)

```mermaid
gantt
    title Feature Timeline: 10 Nov - 17 Nov (UI/UX -> Frontend)
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    
    section Feature
    Overall Deadline    :milestone, 2025-11-17, 0d
    
    section UI/UX (24h)
    UI/UX Task         :active, uiux, 2025-11-10, 3d
    
    section Frontend (24h)
    Frontend Task      :frontend, 2025-11-14, 3d
    
    section AI (24h)
    AI Task (Independent) :ai, 2025-11-10, 3d
```

**Explanation:**
- UI/UX starts immediately (10 Nov) and takes 3 days → ends 13 Nov
- Frontend **depends on** UI/UX, so starts 14 Nov → ends 17 Nov
- AI has no dependencies, starts 10 Nov (parallel with UI/UX) → ends 13 Nov

### Example 2: Multiple Blockers (UI/UX blocks Frontend, Backend blocks Frontend)

```mermaid
gantt
    title Feature Timeline with Multiple Dependencies
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    
    section Feature
    Deadline    :milestone, 2025-11-17, 0d
    
    section Blockers
    UI/UX (24h)         :active, uiux, 2025-11-10, 3d
    Backend (24h)       :active, backend, 2025-11-10, 3d
    
    section Blocked
    Frontend (24h)      :crit, frontend, 2025-11-14, 3d
```

**Explanation:**
- Both UI/UX and Backend start at 10 Nov (parallel)
- Frontend can only start after **both** complete (14 Nov)
- Frontend ends at deadline (17 Nov)

### Example 3: Complex Chain (UI/UX blocks Frontend blocks Backend blocks AI)

```mermaid
gantt
    title Sequential Dependencies Chain
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    
    section Departments
    UI/UX (16h)        :uiux, 2025-11-10, 2d
    Frontend (16h)     :frontend, 2025-11-12, 2d
    Backend (16h)      :backend, 2025-11-14, 2d
    AI (16h)           :ai, 2025-11-18, 2d
    
    section Deadline
    Feature End    :milestone, 2025-11-20, 0d
```

**Explanation:**
- Each department depends on the previous one completing
- Working backwards from 20 Nov deadline:
  - AI: 18-20 Nov
  - Backend: 14-16 Nov (skipping Friday 17th)
  - Frontend: 12-14 Nov
  - UI/UX: 10-12 Nov

## Dependency Graph Structures

### Parallel Work (No Dependencies)

```mermaid
graph LR
    Start[Feature Start<br/>10 Nov]
    UI[UI/UX<br/>24h]
    FE[Frontend<br/>24h]
    BE[Backend<br/>24h]
    AI[AI<br/>24h]
    End[Feature End<br/>17 Nov]
    
    Start --> UI
    Start --> FE
    Start --> BE
    Start --> AI
    UI --> End
    FE --> End
    BE --> End
    AI --> End

    style Start fill:#e3f2fd
    style End fill:#e8f5e9
    style UI fill:#fff9c4
    style FE fill:#fff9c4
    style BE fill:#fff9c4
    style AI fill:#fff9c4
```

### Sequential Work (Chain Dependencies)

```mermaid
graph LR
    Start[Feature Start]
    UI[UI/UX<br/>10-13 Nov]
    FE[Frontend<br/>14-17 Nov]
    End[Feature End]
    
    Start --> UI
    UI -->|blocks| FE
    FE --> End

    style Start fill:#e3f2fd
    style End fill:#e8f5e9
    style UI fill:#fff9c4
    style FE fill:#ffccbc
```

### Mixed Dependencies

```mermaid
graph TB
    Start[Feature Start<br/>10 Nov]
    
    UI[UI/UX<br/>10-13 Nov]
    BE[Backend<br/>10-13 Nov]
    
    FE[Frontend<br/>14-17 Nov]
    AI[AI<br/>10-13 Nov]
    
    End[Feature End<br/>17 Nov]
    
    Start --> UI
    Start --> BE
    Start --> AI
    
    UI -->|blocks| FE
    BE -->|blocks| FE
    
    FE --> End
    AI --> End

    style Start fill:#e3f2fd
    style End fill:#e8f5e9
    style UI fill:#fff9c4
    style BE fill:#fff9c4
    style FE fill:#ffccbc
    style AI fill:#fff9c4
```

**Key:**
- 🟨 Yellow: Independent tasks (start immediately)
- 🟧 Orange: Dependent tasks (wait for blockers)
- 🔵 Blue: Start milestone
- 🟢 Green: End milestone

## Jira Subtask Structure

```mermaid
graph TB
    subgraph "Jira Developer Board"
        Story["Parent Story<br/>Feature: User Authentication<br/>Epic: Security<br/>Deadline: 17 Nov"]
        
        SubUI["Subtask: UI/UX<br/>Assignee: Designer<br/>Story Points: 24h<br/>Start: 10 Nov<br/>End: 13 Nov"]
        
        SubFE["Subtask: Frontend<br/>Assignee: FE Dev<br/>Story Points: 24h<br/>Start: 14 Nov<br/>End: 17 Nov"]
        
        SubAI["Subtask: AI<br/>Assignee: AI Dev<br/>Story Points: 24h<br/>Start: 10 Nov<br/>End: 13 Nov"]
        
        Story --> SubUI
        Story --> SubFE
        Story --> SubAI
        
        SubUI -.blocks.-> SubFE
    end

    style Story fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style SubUI fill:#fff9c4
    style SubFE fill:#ffccbc
    style SubAI fill:#fff9c4
```

## Date Calculation Algorithm

```mermaid
flowchart TD
    Start([Start: Parse Feature])
    A[Get Feature Deadline]
    B[Get Department Hours]
    C[Parse Department Deps]
    D{Has Dependencies?}
    E[Build Dependency Graph]
    F[Work Backwards from Deadline]
    G[Calculate for Each Dept]
    H{Is Blocked?}
    I[End = Earliest Dependent Start]
    J[End = Feature Deadline]
    K[Calculate Start from End<br/>Subtract Working Days]
    L{All Depts<br/>Processed?}
    M[Create Subtasks with Dates]
    N[Create Blocking Links]
    End([End: Subtasks Created])
    
    Start --> A
    A --> B
    B --> C
    C --> D
    D -->|Yes| E
    D -->|No| F
    E --> F
    F --> G
    G --> H
    H -->|Yes| I
    H -->|No| J
    I --> K
    J --> K
    K --> L
    L -->|No| G
    L -->|Yes| M
    M --> N
    N --> End

    style Start fill:#e8f5e9
    style End fill:#e8f5e9
    style H fill:#fff3e0
    style D fill:#fff3e0
    style L fill:#fff3e0
```

## Working Day Calculation

```mermaid
flowchart LR
    A[End Date: 17 Nov]
    B{Is Working Day?}
    C[Count Working Day]
    D[Skip Day]
    E{Counted<br/>Enough Days?}
    F[Start Date Found]
    
    A --> B
    B -->|Yes| C
    B -->|No - Friday/Holiday| D
    C --> E
    D --> E
    E -->|No| B
    E -->|Yes| F

    style A fill:#e3f2fd
    style F fill:#e8f5e9
```

**Working Day Rules:**
- 1 day = 8 hours
- Friday is excluded (Iranian weekend)
- Holidays are excluded (from Jira settings)
- Algorithm works backwards from end date

## Integration Flow

```mermaid
sequenceDiagram
    participant GS as Google Sheets
    participant UC as SynthPM UseCase
    participant Repo as SynthPM Repository
    participant Calc as DepartmentDependencyCalculator
    participant Jira as Jira API
    
    GS->>UC: Feature Data (deps, hours, deadline)
    UC->>Repo: sync_developer_board_features()
    Repo->>Calc: parse_department_deps(deps_string)
    Calc-->>Repo: dependency_dict
    
    Repo->>Calc: calculate_department_deadlines(...)
    Calc->>Calc: Build dependency graph
    Calc->>Calc: Work backwards from deadline
    Calc->>Calc: Calculate each department dates
    Calc-->>Repo: department_dates
    
    loop For Each Assignee
        Repo->>Jira: Create Subtask with dates
        Jira-->>Repo: subtask_key
    end
    
    Repo->>Jira: Create blocking links
    Jira-->>Repo: Success
    
    Repo-->>UC: Sync Complete
    UC-->>GS: Update sync status
```

## Error Handling Flow

```mermaid
flowchart TD
    A[Parse Dependencies]
    B{Valid Format?}
    C{Circular Dependency?}
    D{Missing Department?}
    E[Calculate Dates]
    F[Log Error: Invalid Format]
    G[Log Error: Circular Dependency]
    H[Log Error: Missing Department]
    I[Return Empty Dependencies]
    J[Continue with Valid Deps]
    
    A --> B
    B -->|No| F
    B -->|Yes| C
    C -->|Yes| G
    C -->|No| D
    D -->|Yes| H
    D -->|No| E
    F --> I
    G --> I
    H --> J

    style F fill:#ffcdd2
    style G fill:#ffcdd2
    style H fill:#fff9c4
    style E fill:#e8f5e9
```

---

**Usage Notes:**
- These diagrams use Mermaid syntax and will render in GitHub, VS Code, and most modern documentation tools
- Colors indicate different states and dependency relationships
- Timeline diagrams show actual working days excluding Fridays
- All examples assume 8-hour workdays and Friday weekends

