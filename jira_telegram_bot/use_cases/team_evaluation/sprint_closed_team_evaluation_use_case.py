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
from jira_telegram_bot.entities.constants import DONE_STATUSES
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface
from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import GoogleSheetGatewayInterface
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface
from jira_telegram_bot.use_cases.team_evaluation.services import (
    CalendarService,
    ChangelogService,
    ClassificationService,
    DeadlineService,
    DefectService,
    ScoreService
)


class SprintClosedTeamEvaluationUseCase:
    """Use case for processing sprint closure and generating team evaluation data."""

    def __init__(
        self,
        task_manager_repo: TaskManagerRepositoryInterface,
        user_config_service: UserConfigInterface,
        google_sheet_gateway: GoogleSheetGatewayInterface,
        calendar_repo: CalendarRepositoryInterface,
        leave_repo: LeaveRepositoryInterface,
        settings: TeamEvaluationSettings
    ):
        """Initialize the use case.
        
        Args:
            task_manager_repo: Jira repository
            user_config_service: User configuration service
            google_sheet_gateway: Google Sheets gateway
            calendar_repo: Calendar repository
            leave_repo: Leave repository  
            settings: Team evaluation settings
        """
        self.task_manager_repo = task_manager_repo
        self.user_config_service = user_config_service
        self.google_sheet_gateway = google_sheet_gateway
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
                # Update Google Sheet
                await self._update_sheet(evaluation_rows)
                LOGGER.info(f"Successfully processed {len(evaluation_rows)} evaluation rows")
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
    ) -> List[TeamEvaluationRow]:
        """Compute evaluation for all developers.
        
        Args:
            sprint_name: Name of the sprint
            sprint_issues: List of issues in the sprint
            worklogs: List of worklog entries
            changelogs: Dictionary of changelog events per issue
            event: Sprint closed event
            
        Returns:
            List of team evaluation rows
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
                    row = await self._compute_developer_evaluation(
                        developer=developer,
                        department=department,
                        project_key=project_key,
                        sprint_name=sprint_name,
                        issues=project_issues,
                        worklogs=[w for w in data["worklogs"] if any(i.key in w.issue_key for i in project_issues)],
                        changelogs={k: v for k, v in data["changelogs"].items() if any(i.key == k for i in project_issues)},
                        sprint_end_date=event.ended_at
                    )
                    
                    if row:
                        evaluation_rows.append(row)
                        
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
                
                # Create separate entries for each department
                for department in departments:
                    key = (issue.assignee, department)
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
                
                # Add worklog to each department this issue belongs to
                for department in departments:
                    key = (worklog.author, department)
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
                
                # Add changelog to each department this issue belongs to
                for department in departments:
                    key = (issue.assignee, department)
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
        sprint_end_date: datetime
    ) -> Optional[TeamEvaluationRow]:
        """Compute evaluation row for a single developer.
        
        Args:
            developer: Developer username
            department: Developer department
            project_key: Project key
            sprint_name: Sprint name
            issues: Developer's issues in this project
            worklogs: Developer's worklogs
            changelogs: Developer's changelogs
            sprint_end_date: Sprint end date
            
        Returns:
            Team evaluation row or None if no data
        """
        try:
            if not issues:
                return None
            
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
            
            # Calculate worklog hours by type
            total_hours = sum(w.hours for w in worklogs)
            bug_hours = sum(
                w.hours for w in worklogs 
                if any(i.key == w.issue_key for i in bug_issues)
            )
            dev_hours = sum(
                w.hours for w in worklogs 
                if any(i.key == w.issue_key for i in dev_issues)
            )
            support_hours = sum(
                w.hours for w in worklogs 
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

            # Calculate deadline performance
            delivered_with_deadlines = [i for i in delivered_issues if i.due_date]
            avg_deadline_delta = self.deadline_service.average_deadline_delta_days(
                delivered_with_deadlines, 
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
            
            # Calculate quality score
            quality_score = self.score_service.compute_hosn_score(
                weights=self.settings.score_weights,
                avg_deadline_delta_days=avg_deadline_delta or 0.0,
                registered_hours=total_hours,
                expected_hours=expected_hours,
                completed_high_priority=completed_high_priority,
                total_high_priority=len(high_priority_issues),
                support_bugs_per_story=support_bugs_per_story,
                tester_bugs_per_story=tester_bugs_per_story,
                defect_thresholds=self.settings.defect_thresholds
            )
            
            # Create evaluation row
            # Translate developer username to Google Sheets display name
            user_config = self.user_config_service.get_user_config_by_jira_username(developer)
            google_sheet_name = (
                user_config.google_sheet_name 
                if user_config and user_config.google_sheet_name 
                else developer
            )
            
            return TeamEvaluationRow(
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
            
        except Exception as e:
            LOGGER.error(f"Error computing evaluation for {developer}: {e}")
            return None

    async def _update_sheet(self, rows: List[TeamEvaluationRow]) -> None:
        """Update Google Sheet with evaluation data.
        
        Args:
            rows: List of evaluation rows to write
        """
        try:
            if self.settings.dry_run:
                LOGGER.info(f"DRY RUN: Would write {len(rows)} rows to sheet")
                for row in rows:
                    LOGGER.info(f"DRY RUN: {row.developer_name} - {row.department} - {row.project} - {row.sprint}")
                return
            
            # Use developer name, department, project, and sprint as unique keys for upsert
            upsert_keys = ("توسعه دهنده", "دپارتمان", "پروژه", "اسپرینت")
            
            await self.google_sheet_gateway.upsert_rows(
                sheet_id=self.settings.sheet_id,
                tab_name=self.settings.tab_name,
                rows=rows,
                upsert_keys=upsert_keys
            )
            
        except Exception as e:
            LOGGER.error(f"Error updating Google Sheet: {e}")
            raise
