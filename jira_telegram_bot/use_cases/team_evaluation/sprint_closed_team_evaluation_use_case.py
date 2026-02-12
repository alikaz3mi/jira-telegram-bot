"""Sprint closed team evaluation use case."""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.team_evaluation import (
    SprintClosedEvent,
    TeamEvaluationRow,
    IssueSnapshot,
    WorklogSlice,
    ChangeLogEvent,
    Department
)
from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog
)
from jira_telegram_bot.entities.constants import (
    DONE_STATUSES,
    DEFAULT_WEEKLY_HOURS,
    DEADLINE_GRACE_PERIOD_DAYS
)
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface
from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import GoogleSheetGatewayInterface
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.team_evaluation_repository_interface import TeamEvaluationRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.team_evaluation_calculation_log_repository_interface import (
    TeamEvaluationCalculationLogRepositoryInterface
)
from jira_telegram_bot.use_cases.team_evaluation.services import (
    CalendarService,
    ChangelogService,
    ClassificationService,
    DeadlineService,
    DefectService,
    ScoreService
)
from jira_telegram_bot.use_cases.team_evaluation.calculation_logger import CalculationLogger


class SprintClosedTeamEvaluationUseCase:
    """Use case for processing sprint closure and generating team evaluation data."""

    def __init__(
        self,
        task_manager_repo: TaskManagerRepositoryInterface,
        user_config_service: UserConfigInterface,
        google_sheet_gateway: GoogleSheetGatewayInterface,
        calendar_repo: CalendarRepositoryInterface,
        leave_repo: LeaveRepositoryInterface,
        team_evaluation_repo: TeamEvaluationRepositoryInterface,
        calculation_log_repo: TeamEvaluationCalculationLogRepositoryInterface,
        settings: TeamEvaluationSettings
    ):
        """Initialize the use case.
        
        Args:
            task_manager_repo: Jira repository
            user_config_service: User configuration service
            google_sheet_gateway: Google Sheets gateway (deprecated, kept for backward compatibility)
            calendar_repo: Calendar repository
            leave_repo: Leave repository
            team_evaluation_repo: Team evaluation repository for database storage
            calculation_log_repo: Calculation log repository for detailed audit trail
            settings: Team evaluation settings
        """
        self.task_manager_repo = task_manager_repo
        self.user_config_service = user_config_service
        self.google_sheet_gateway = google_sheet_gateway
        self.team_evaluation_repo = team_evaluation_repo
        self.calculation_log_repo = calculation_log_repo
        self.settings = settings
        
        # Initialize services
        self.calendar_service = CalendarService(calendar_repo, leave_repo)
        self.changelog_service = ChangelogService()
        self.classification_service = ClassificationService()
        self.deadline_service = DeadlineService()
        self.defect_service = DefectService()
        self.score_service = ScoreService()

    async def process_sprint_closed(self, event: SprintClosedEvent) -> None:
        """Process a sprint closed event and update team evaluation sheet.
        
        Args:
            event: Sprint closed event data
        """
        try:
            LOGGER.info(f"Processing sprint closed event: {event.sprint_name} (ID: {event.sprint_id})")
            
            # Get sprint information
            sprint = await self.task_manager_repo.get_sprint(event.sprint_id)
            if not sprint:
                LOGGER.error(f"Sprint {event.sprint_id} not found")
                return
            
            # Set sprint dates from the sprint object, ensuring they are datetime objects
            if hasattr(sprint, 'startDate') and sprint.startDate:
                event.started_at = sprint.startDate if isinstance(sprint.startDate, datetime) else datetime.fromisoformat(str(sprint.startDate))
            if hasattr(sprint, 'endDate') and sprint.endDate:
                event.ended_at = sprint.endDate if isinstance(sprint.endDate, datetime) else datetime.fromisoformat(str(sprint.endDate))

            # Use actual sprint name from the sprint object if available
            actual_sprint_name = getattr(sprint, 'name', event.sprint_name) or event.sprint_name
            
            # Get all issues in the sprint
            sprint_issues = await self.task_manager_repo.get_sprint_issues(
                project_keys=event.project_keys,
                sprint_id=event.sprint_id
            )
            
            if not sprint_issues:
                LOGGER.warning(f"No issues found for sprint {event.sprint_id}")
                return
            
            LOGGER.info(f"Found {len(sprint_issues)} issues in sprint")
            
            # Get additional data
            issue_keys = [issue.key for issue in sprint_issues if issue]
            worklogs = await self.task_manager_repo.get_issue_worklogs(issue_keys)
            changelogs = await self.task_manager_repo.get_issue_changelogs(issue_keys)
            
            # Process data per developer and department
            evaluation_rows = await self._compute_evaluation(
                sprint_issues=sprint_issues,
                worklogs=worklogs,
                changelogs=changelogs,
                sprint_name=actual_sprint_name,
                event=event
            )
            
            if evaluation_rows:
                # Save to database instead of Google Sheets
                await self._save_to_database(evaluation_rows, event.sprint_id)
                LOGGER.info(f"Successfully processed and saved {len(evaluation_rows)} evaluation rows")
            else:
                LOGGER.warning("No evaluation rows generated")
                
        except Exception as e:
            LOGGER.error(f"Error processing sprint closed event: {e}")
            raise

    async def _compute_evaluation(
        self,
        sprint_name: str,
        sprint_issues: List[IssueSnapshot],
        worklogs: List[WorklogSlice],
        changelogs: Dict[str, List[ChangeLogEvent]],
        event: SprintClosedEvent
    ) -> List[Tuple[TeamEvaluationRow, Dict]]:
        """Compute evaluation for all developers.
        
        Args:
            sprint_name: Name of the sprint
            sprint_issues: List of issues in the sprint
            worklogs: List of worklog entries
            changelogs: Dictionary of changelog events per issue
            event: Sprint closed event
            
        Returns:
            List of tuples (TeamEvaluationRow, calculation_details)
        """
        # Group data by developer and department
        developer_department_data = await self._group_by_developer_and_department(sprint_issues, worklogs, changelogs)
        
        evaluation_rows = []
        
        for (developer, department), data in developer_department_data.items():
            try:
                # Process each project separately for this developer/department
                for project_key in event.project_keys:
                    project_issues = [
                        issue for issue in data["issues"] 
                        if issue.project_key == project_key
                    ]
                    
                    if not project_issues:
                        continue
                    
                    # Compute evaluation row for this developer/department/project
                    result = await self._compute_developer_evaluation(
                        developer=developer,
                        department=department,
                        project_key=project_key,
                        sprint_name=sprint_name,
                        issues=project_issues,
                        worklogs=[w for w in data["worklogs"] if any(i.key in w.issue_key for i in project_issues)],
                        changelogs={k: v for k, v in data["changelogs"].items() if any(i.key == k for i in project_issues)},
                        sprint_start_date=event.started_at,
                        sprint_end_date=event.ended_at
                    )
                    
                    if result:
                        evaluation_rows.append(result)
                        
            except Exception as e:
                LOGGER.error(f"Error computing evaluation for developer {developer} in department {department}: {e}")
                continue
        
        return evaluation_rows

    async def _group_by_developer_and_department(
        self,
        issues: List[IssueSnapshot],
        worklogs: List[WorklogSlice],
        changelogs: Dict[str, List[ChangeLogEvent]]
    ) -> Dict[Tuple[str, str], Dict]:
        """Group data by developer and department combination.
        
        Args:
            issues: List of all issues
            worklogs: List of all worklogs
            changelogs: Dictionary of all changelogs
            
        Returns:
            Dictionary with (developer, department) tuples as keys
        """
        developer_dept_data = defaultdict(lambda: {
            "issues": [],
            "worklogs": [],
            "changelogs": {}
        })
        
        # Group issues by assignee and their departments
        for issue in issues:
            if issue.assignee:
                # Get departments for this issue
                departments = self.classification_service.get_issue_departments(
                    issue, 
                    strategy=self.settings.dept_inference
                )
                
                # If no departments found, use "Unknown"
                if not departments:
                    departments = ["Unknown"]
                
                # Filter to user's actual department to avoid duplicates
                user_department = self._get_user_department_from_config(
                    issue.assignee, 
                    issue.project_key
                )
                
                # If user has a configured department and it matches one of the issue departments, use only that
                if user_department and user_department in departments:
                    selected_department = user_department
                else:
                    # Otherwise, use the first department (or only one if single)
                    selected_department = list(departments)[0]
                
                key = (issue.assignee, selected_department)
                developer_dept_data[key]["issues"].append(issue)
        
        # Group worklogs by author and match with issue departments
        for worklog in worklogs:
            # Find which issue this worklog belongs to
            matching_issues = [issue for issue in issues if issue.key == worklog.issue_key]
            
            if matching_issues:
                issue = matching_issues[0]
                departments = self.classification_service.get_issue_departments(
                    issue,
                    strategy=self.settings.dept_inference
                )
                
                if not departments:
                    departments = ["Unknown"]
                
                # Filter to user's actual department to avoid duplicates
                user_department = self._get_user_department_from_config(
                    worklog.author,
                    issue.project_key
                )
                
                # If user has a configured department and it matches one of the issue departments, use only that
                if user_department and user_department in departments:
                    selected_department = user_department
                else:
                    # Otherwise, use the first department (or only one if single)
                    selected_department = list(departments)[0]
                
                key = (worklog.author, selected_department)
                developer_dept_data[key]["worklogs"].append(worklog)
        
        # Group changelogs by issue assignee and departments
        for issue_key, events in changelogs.items():
            # Find the issue for this changelog
            matching_issues = [issue for issue in issues if issue.key == issue_key and issue.assignee]
            
            if matching_issues:
                issue = matching_issues[0]
                departments = self.classification_service.get_issue_departments(
                    issue,
                    strategy=self.settings.dept_inference
                )
                
                if not departments:
                    departments = ["Unknown"]
                
                # Filter to user's actual department to avoid duplicates
                user_department = self._get_user_department_from_config(
                    issue.assignee,
                    issue.project_key
                )
                
                # If user has a configured department and it matches one of the issue departments, use only that
                if user_department and user_department in departments:
                    selected_department = user_department
                else:
                    # Otherwise, use the first department (or only one if single)
                    selected_department = list(departments)[0]
                
                key = (issue.assignee, selected_department)
                developer_dept_data[key]["changelogs"][issue_key] = events
        
        return dict(developer_dept_data)

    def _group_by_developer(
        self,
        issues: List[IssueSnapshot],
        worklogs: List[WorklogSlice],
        changelogs: Dict[str, List[ChangeLogEvent]]
    ) -> Dict[str, Dict]:
        """Group data by developer.
        
        Args:
            issues: List of all issues
            worklogs: List of all worklogs
            changelogs: Dictionary of all changelogs
            
        Returns:
            Dictionary of developer data
        """
        developer_data = defaultdict(lambda: {
            "issues": [],
            "worklogs": [],
            "changelogs": {}
        })
        
        # Group issues by assignee
        for issue in issues:
            if issue.assignee:
                developer_data[issue.assignee]["issues"].append(issue)
        
        # Group worklogs by author
        for worklog in worklogs:
            developer_data[worklog.author]["worklogs"].append(worklog)
        
        # Group changelogs by issue assignee (need to match with issues)
        issue_assignees = {issue.key: issue.assignee for issue in issues if issue.assignee}
        
        for issue_key, events in changelogs.items():
            assignee = issue_assignees.get(issue_key)
            if assignee:
                developer_data[assignee]["changelogs"][issue_key] = events
        
        return dict(developer_data)

    def _get_user_department_from_config(
        self,
        username: str,
        project_key: str
    ) -> Optional[str]:
        """Get user's department from user config.
        
        Args:
            username: User's Jira username
            project_key: Project key
            
        Returns:
            Department name if found in user config, None otherwise
        """
        user_config = self.user_config_service.get_user_config_by_jira_username(username)
        if user_config and user_config.user_components:
            # user_components is a dict like {"PROJECT1": "Front-end"}
            return user_config.user_components.get(project_key)
        return None

    async def _get_developer_department(
        self,
        developer: str,
        issues: List[IssueSnapshot]
    ) -> str:
        """Get department for a developer.
        
        Args:
            developer: Developer username
            issues: List of developer's issues
            
        Returns:
            Department name
        """
        if self.settings.dept_inference == "user_config":
            # Try to get from user config
            user_config = self.user_config_service.get_user_config_by_jira_username(developer)
            if user_config and hasattr(user_config, 'department'):
                return user_config.department
        
        # Infer from issues
        all_departments = set()
        for issue in issues:
            departments = self.classification_service.get_issue_departments(
                issue, 
                strategy=self.settings.dept_inference
            )
            all_departments.update(departments)
        
        # Return most common department or first one
        if all_departments:
            return sorted(all_departments)[0]
        
        return "Unknown"

    async def _compute_developer_evaluation(
        self,
        developer: str,
        department: str,
        project_key: str,
        sprint_name: str,
        issues: List[IssueSnapshot],
        worklogs: List[WorklogSlice],
        changelogs: Dict[str, List[ChangeLogEvent]],
        sprint_start_date: datetime,
        sprint_end_date: datetime
    ) -> Optional[Tuple[TeamEvaluationRow, Dict]]:
        """Compute evaluation row for a single developer.
        
        Args:
            developer: Developer username
            department: Developer department
            project_key: Project key
            sprint_name: Sprint name
            issues: Developer's issues in this project
            worklogs: Developer's worklogs
            changelogs: Developer's changelogs
            sprint_start_date: Sprint start date
            sprint_end_date: Sprint end date
            
        Returns:
            Tuple of (TeamEvaluationRow, calculation_details dict) or None if no data
        """
        try:
            if not issues:
                return None
            
            # Normalize sprint dates to ensure timezone consistency
            sprint_start_normalized = self.deadline_service._normalize_datetime(sprint_start_date)
            sprint_end_normalized = self.deadline_service._normalize_datetime(sprint_end_date)
            
            # Filter worklogs to only include those within sprint date range
            sprint_worklogs = [
                w for w in worklogs 
                if sprint_start_normalized <= self.deadline_service._normalize_datetime(w.started_at) <= sprint_end_normalized
            ]
            
            if len(sprint_worklogs) < len(worklogs):
                filtered_count = len(worklogs) - len(sprint_worklogs)
                LOGGER.debug(
                    f"Filtered {filtered_count} worklogs outside sprint range for {developer}. "
                    f"Using {len(sprint_worklogs)}/{len(worklogs)} worklogs."
                )
            
            # Classify issues
            dev_issues = []
            bug_issues = []
            support_issues = []
            high_priority_issues = []
            delivered_issues = []
            
            for issue in issues:
                classification = self.classification_service.classify_issue(issue)
                
                if classification.value == "development":
                    dev_issues.append(issue)
                elif classification.value == "bug":
                    bug_issues.append(issue)
                elif classification.value == "support":
                    support_issues.append(issue)
                
                if self.classification_service.is_high_priority(issue):
                    high_priority_issues.append(issue)
                
                if issue.status in DONE_STATUSES:
                    delivered_issues.append(issue)
            
            # Calculate worklog hours by type (only for worklogs within sprint range)
            total_hours = sum(w.hours for w in sprint_worklogs)
            bug_hours = sum(
                w.hours for w in sprint_worklogs 
                if any(i.key == w.issue_key for i in bug_issues)
            )
            dev_hours = sum(
                w.hours for w in sprint_worklogs 
                if any(i.key == w.issue_key for i in dev_issues)
            )
            support_hours = sum(
                w.hours for w in sprint_worklogs 
                if any(i.key == w.issue_key for i in support_issues)
            )
            
            # Calculate expected hours
            week_start, week_end = self.calendar_service.get_week_bounds(sprint_end_date.date())
            expected_hours = await self.calendar_service.calculate_expected_hours(
                week_start=week_start,
                week_end=week_end,
                weekly_hours=self.settings.weekly_hours,
                workdays=self.settings.workdays,
                username=developer
            )
            expected_hours = round(expected_hours)

            # Handle task overload: select which tasks to evaluate
            tasks_for_eval, extra_tasks = self.deadline_service.select_tasks_for_evaluation(
                issues=issues,
                max_hours=DEFAULT_WEEKLY_HOURS
            )
            
            # Count completed extra tasks
            extra_completed_count = sum(
                1 for task in extra_tasks 
                if task.status in DONE_STATUSES
            )
            
            # Calculate deadline performance using per-task penalties
            # Include ALL tasks with deadlines (delivered AND undelivered)
            # Undelivered tasks are assumed delivered 1 day after sprint end
            tasks_with_deadlines = [
                i for i in tasks_for_eval 
                if i.due_date
            ]
            deadline_penalty_score = self.deadline_service.calculate_per_task_deadline_penalties(
                issues=tasks_with_deadlines,
                changelogs=changelogs,
                grace_period_days=DEADLINE_GRACE_PERIOD_DAYS,
                sprint_end_date=sprint_end_normalized
            )
            
            # Keep average for display purposes (all tasks)
            all_delivered_with_deadlines = [i for i in delivered_issues if i.due_date]
            avg_deadline_delta = self.deadline_service.average_deadline_delta_days(
                all_delivered_with_deadlines, 
                changelogs
            )
            avg_deadline_str = (
                f"{avg_deadline_delta:.1f}d" if avg_deadline_delta is not None 
                else "N/A"
            )
            
            # Calculate changelog metrics
            all_events = []
            for events in changelogs.values():
                all_events.extend(events)
            review_back_count = self.changelog_service.count_review_regressions(all_events)
            
            # Calculate defect metrics
            delivered_dev_stories = [i for i in delivered_issues if i in dev_issues]
            support_bugs_per_story, tester_bugs_per_story = self.defect_service.compute_defect_scores(
                delivered_stories=delivered_dev_stories,
                bugs=bug_issues
            )
            
            # Calculate completed high priority
            completed_high_priority = len([i for i in high_priority_issues if i.status in DONE_STATUSES])
            
            # Calculate quality score with new per-task logic and extra task bonus
            quality_score = self.score_service.compute_hosn_score(
                weights=self.settings.score_weights,
                deadline_penalty_score=deadline_penalty_score,
                registered_hours=total_hours,
                expected_hours=expected_hours,
                all_issues=issues,
                completed_high_priority=completed_high_priority,
                total_high_priority=len(high_priority_issues),
                support_bugs_per_story=support_bugs_per_story,
                tester_bugs_per_story=tester_bugs_per_story,
                defect_thresholds=self.settings.defect_thresholds,
                extra_completed_tasks_count=extra_completed_count
            )
            
            # Collect calculation details for logging
            calculation_details = {
                "dev_count": len(dev_issues),
                "bug_count": len(bug_issues),
                "support_count": len(support_issues),
                "high_priority_count": len(high_priority_issues),
                "total_issues": len(issues),
                "worklog_count": len(worklogs),
                "filtered_worklog_count": len(worklogs) - len(sprint_worklogs),
                "deadline_score": 100 - deadline_penalty_score,
                "deadline_penalty": deadline_penalty_score,
                "tasks_with_deadlines": len(tasks_with_deadlines),
                "avg_deadline_delta": avg_deadline_delta if avg_deadline_delta is not None else 0,
                "worklog_score": (total_hours / expected_hours * 100) if expected_hours > 0 else 0,
                "high_priority_score": (completed_high_priority / len(high_priority_issues) * 100) if high_priority_issues else 0,
                "required_tasks": len(high_priority_issues),
                "completed_required": completed_high_priority,
                "defect_score": 100,  # Default, actual calculation is complex
                "composite_score": quality_score,
                "penalties": deadline_penalty_score,
                "bonuses": extra_completed_count * 5  # 5 points per extra task
            }
            
            # Create evaluation row
            # Translate developer username to Google Sheets display name
            user_config = self.user_config_service.get_user_config_by_jira_username(developer)
            google_sheet_name = (
                user_config.google_sheet_name 
                if user_config and user_config.google_sheet_name 
                else developer
            )
            
            row = TeamEvaluationRow(
                developer_name=google_sheet_name,
                department=department,
                project=project_key,
                sprint=sprint_name,
                development_count=len(dev_issues),
                bug_count=len(bug_issues),
                support_count=len(support_issues),
                high_priority_count=len(high_priority_issues),
                registered_hours_week=total_hours,
                expected_hours_week=expected_hours,
                bug_hours=bug_hours,
                development_hours=dev_hours,
                support_hours=support_hours,
                avg_deadline_delivery_days=avg_deadline_str,
                review_back_count=review_back_count,
                story_test_pass_rate="N/A",  # Not implemented in scope
                acceptance_criteria_pass_rate="N/A",  # Not implemented in scope
                high_priority_completed_count=completed_high_priority,
                avg_support_bugs_per_story=support_bugs_per_story,
                avg_tester_bugs_per_story=tester_bugs_per_story,
                development_delivered_count=len([i for i in dev_issues if i.status in DONE_STATUSES]),
                bug_delivered_count=len([i for i in bug_issues if i.status in DONE_STATUSES]),
                support_delivered_count=len([i for i in support_issues if i.status in DONE_STATUSES]),
                quality_score=quality_score
            )
            
            return (row, calculation_details)
            
        except Exception as e:
            LOGGER.error(f"Error computing evaluation for {developer}: {e}")
            return None

    async def _save_to_database(self, rows_with_details: List[Tuple[TeamEvaluationRow, Dict]], sprint_id: int) -> None:
        """Save team evaluation data to database and calculation logs.
        
        Args:
            rows_with_details: List of tuples (evaluation row, calculation_details)
            sprint_id: Sprint ID for tracking
        """
        try:
            # Extract just the rows for database save
            rows = [row for row, _ in rows_with_details]
            
            if self.settings.dry_run:
                LOGGER.info(f"DRY RUN: Would save {len(rows)} rows to database")
                for row in rows:
                    LOGGER.info(f"DRY RUN: {row.developer_name} - {row.department} - {row.project} - {row.sprint} - Score: {row.quality_score}")
                
                # Also log calculation details in dry run
                for row, calc_details in rows_with_details:
                    LOGGER.info(f"DRY RUN: Would save {len(calc_details)} calculation detail keys for {row.developer_name}")
                return
            
            # Save batch to database
            saved_count = await self.team_evaluation_repo.save_evaluations_batch(rows)
            LOGGER.info(f"Saved {saved_count} team evaluation rows to database for sprint {sprint_id}")
            
            # Save calculation logs for each evaluation (one entry per developer per sprint)
            for row, calc_details in rows_with_details:
                await self._save_calculation_logs_for_evaluation(
                    sprint_id=sprint_id,
                    row=row,
                    calculation_details=calc_details
                )
            
        except Exception as e:
            LOGGER.error(f"Error saving team evaluation to database: {e}")
            raise

    def _create_calculation_log(
        self,
        sprint_id: int,
        sprint_name: str,
        developer_name: str,
        department: str,
        project: str,
        calculation_type: str,
        metric_name: str,
        metric_value: float,
        formula: str,
        details: str,
        weight: Optional[float] = None,
        contribution: Optional[float] = None
    ) -> TeamEvaluationCalculationLog:
        """Create a calculation log entry.
        
        Args:
            sprint_id: Sprint identifier
            sprint_name: Sprint name
            developer_name: Developer name
            department: Department name
            project: Project key
            calculation_type: Type of calculation (metric, score, penalty, bonus)
            metric_name: Name of the metric being calculated
            metric_value: Calculated value
            formula: Formula used for calculation
            details: Detailed explanation of calculation
            weight: Weight applied to metric (if applicable)
            contribution: Contribution to total score (if applicable)
            
        Returns:
            TeamEvaluationCalculationLog entity
        """
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer_name,
            department=department,
            project=project,
            calculation_type=calculation_type,
            metric_name=metric_name,
            metric_value=metric_value,
            calculation_formula=formula,
            calculation_details=details,
            weight=weight,
            contribution_to_total=contribution,
            timestamp=datetime.utcnow()
        )

    async def _save_calculation_logs_for_evaluation(
        self,
        sprint_id: int,
        row: TeamEvaluationRow,
        calculation_details: Dict
    ) -> None:
        """Save detailed calculation logs for an evaluation row.
        
        Args:
            sprint_id: Sprint identifier
            row: Team evaluation row with computed metrics
            calculation_details: Dictionary with intermediate calculation values
        """
        try:
            logs = []
            
            # Extract details from calculation_details
            dev_count = calculation_details.get("dev_count", 0)
            bug_count = calculation_details.get("bug_count", 0)
            support_count = calculation_details.get("support_count", 0)
            high_priority_count = calculation_details.get("high_priority_count", 0)
            total_issues = calculation_details.get("total_issues", 0)
            worklog_count = calculation_details.get("worklog_count", 0)
            filtered_count = calculation_details.get("filtered_worklog_count", 0)
            
            # Task classification logs
            logs.extend(CalculationLogger.log_task_classification(
                sprint_id=sprint_id,
                sprint_name=row.sprint,
                developer=row.developer_name,
                department=row.department,
                project=row.project,
                dev_count=dev_count,
                bug_count=bug_count,
                support_count=support_count,
                high_priority_count=high_priority_count,
                total_issues=total_issues
            ))
            
            # Time metrics logs
            logs.extend(CalculationLogger.log_time_metrics(
                sprint_id=sprint_id,
                sprint_name=row.sprint,
                developer=row.developer_name,
                department=row.department,
                project=row.project,
                total_hours=row.registered_hours_week,
                expected_hours=row.expected_hours_week,
                dev_hours=row.development_hours,
                bug_hours=row.bug_hours,
                support_hours=row.support_hours,
                worklog_count=worklog_count,
                filtered_count=filtered_count
            ))
            
            # Score component logs
            if "deadline_score" in calculation_details:
                logs.append(CalculationLogger.log_deadline_score(
                    sprint_id=sprint_id,
                    sprint_name=row.sprint,
                    developer=row.developer_name,
                    department=row.department,
                    project=row.project,
                    deadline_penalty=calculation_details.get("deadline_penalty", 0),
                    deadline_score=calculation_details["deadline_score"],
                    tasks_with_deadlines=calculation_details.get("tasks_with_deadlines", 0),
                    avg_delta_days=calculation_details.get("avg_deadline_delta", 0),
                    weight=self.settings.score_weights.deadline
                ))
            
            if "worklog_score" in calculation_details:
                logs.append(CalculationLogger.log_worklog_score(
                    sprint_id=sprint_id,
                    sprint_name=row.sprint,
                    developer=row.developer_name,
                    department=row.department,
                    project=row.project,
                    registered_hours=row.registered_hours_week,
                    expected_hours=row.expected_hours_week,
                    worklog_score=calculation_details["worklog_score"],
                    weight=self.settings.score_weights.worklog
                ))
            
            if "high_priority_score" in calculation_details:
                logs.append(CalculationLogger.log_high_priority_score(
                    sprint_id=sprint_id,
                    sprint_name=row.sprint,
                    developer=row.developer_name,
                    department=row.department,
                    project=row.project,
                    required_tasks=calculation_details.get("required_tasks", 0),
                    completed_required=calculation_details.get("completed_required", 0),
                    high_priority_score=calculation_details["high_priority_score"],
                    weight=self.settings.score_weights.high_priority
                ))
            
            if "defect_score" in calculation_details:
                logs.append(CalculationLogger.log_defect_score(
                    sprint_id=sprint_id,
                    sprint_name=row.sprint,
                    developer=row.developer_name,
                    department=row.department,
                    project=row.project,
                    support_bugs_per_story=row.avg_support_bugs_per_story,
                    tester_bugs_per_story=row.avg_tester_bugs_per_story,
                    defect_score=calculation_details["defect_score"],
                    weight=self.settings.score_weights.defects,
                    support_threshold=self.settings.defect_thresholds.get("support_per_story", 0.3),
                    tester_threshold=self.settings.defect_thresholds.get("tester_per_story", 0.4)
                ))
            
            # Final score log
            logs.append(CalculationLogger.log_final_score(
                sprint_id=sprint_id,
                sprint_name=row.sprint,
                developer=row.developer_name,
                department=row.department,
                project=row.project,
                composite_score=calculation_details.get("composite_score", row.quality_score),
                penalties_applied=calculation_details.get("penalties", 0),
                bonuses_applied=calculation_details.get("bonuses", 0),
                final_score=row.quality_score
            ))
            
            # Save all logs in batch
            if logs and not self.settings.dry_run:
                await self.calculation_log_repo.save_logs_batch(logs)
                LOGGER.info(f"Saved {len(logs)} calculation log entries for {row.developer_name}")
            elif self.settings.dry_run:
                LOGGER.info(f"DRY RUN: Would save {len(logs)} calculation logs for {row.developer_name}")
                
        except Exception as e:
            LOGGER.error(f"Error saving calculation logs for {row.developer_name}: {e}")
            # Don't raise - log errors should not break evaluation

