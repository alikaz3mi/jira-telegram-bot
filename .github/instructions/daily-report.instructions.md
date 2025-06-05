---
mode: agent
description: Daily random “stand-up reporter” via speech-to-text & Telegram; AI-agent driven
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
---

# 🛠️ Goal
Create a feature that **once per day between 14:00-16:00 (local time)** randomly prompts each team member (via Telegram DM) to submit a brief progress report **by voice or text** for one or more in-sprint tasks.

* If the user chooses tasks → list current-sprint issues for selection. The use can select multi-tasks at once. Each task is a keyboard button of telegram.
* If the user skips → agent must infer mapping based on the information of the tasks in active sprint (their summary, description, and the summary of the story if the task is a sub-task)
* All interactions are conversational; speech audio is converted to text via the existing Speech-to-Text service located in `jira_telegram_bot/adapters/ai_models/speech_to_text.py` (but the use case will see only its interface)
* Final structured report is stored and optionally posted back to team/group.

## 📝 Interactive variables
* `${input:sprint_label:Name or JQL label that denotes the active sprint}`
* `${input:report_channel_id:Telegram chat/group ID for aggregated reports}`

## 🔄 Workflow
1. **Prompt Template**  
   * Path: `jira_telegram_bot/adapters/ai_models/ai_agents/prompts/generate_progress_report.yaml`
   * Inputs: `raw_transcript`, `selected_issue_keys`, `assignee`, `sprint_label`, `list of task_summaries and their descriptions`
   * Output schema: `{"issue_key": str, "progress": str, "blockers": strl, "time_spent": str }` (JSON)
2. **AI-Agent Service**  
   * File: `jira_telegram_bot/adapters/ai_models/ai_agents/generate_progress_report_service.py`
   * Implements `AiAgentServiceInterface` → loads prompt → calls LLM → parses JSON via `StructuredOutputParser`
3. **Domain Use Case**  
   * `GenerateProgressReportUseCase` in `use_cases/ai_agents`
     * Validates STT output, calls service, persists results through `ProgressReportRepositoryInterface`
4. **Scheduler**  
   * `jira_telegram_bot/frameworks/scheduler/daily_report_job.py`
     * Uses APScheduler `CronTrigger(hour=14, hour=15, minute='*')` with a random delay
5. **Telegram Conversation Handler**
   * `jira_telegram_bot/frameworks/telegram/daily_report_handler.py`
     * State machine: prompt → task selection → receive voice/text → delegate to use case
6. **Speech-to-Text Adapter**
   * `jira_telegram_bot/adapters/stt/speech_recogniser.py` (wraps existing micro-service HTTP)
7. **Dependency Injection & Wiring**
   * Bind all new interfaces & services
   * Register handler in bot startup
8. **Docs**
   * `docs/architecture/daily_report_flow.md` (sequence + statechart)
9. **Tests**
   * Mock STT & LLM; unit + integration; concurrency scenario with overlapping user prompts
10. **CI / Quality Gates**
    * Same standards: PEP-8, Clean Architecture, ≥ 90 % coverage

## 📤 Meta-commands
/implement-prompt-use-case: use_case_name=generate_progress_report,prompt_author=bot,model_hint=gemini-2.0-flash
/write-unit-tests
/write-integrated-tests
/generate-docs
