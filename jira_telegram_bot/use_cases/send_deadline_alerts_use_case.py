from __future__ import annotations

from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
from jira_telegram_bot.settings.deadline_notifier_settings import (
    DeadlineNotifierSettings,
)
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import (
    CalendarRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.notification_log_repository_interface import (
    NotificationLogRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.telegram_notifier_interface import (
    TelegramNotifierInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SendDeadlineAlertsUseCase:
    """Use case for sending deadline alerts to users and groups."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        user_config_repository: UserConfigInterface,
        telegram_notifier: TelegramNotifierInterface,
        notification_log_repository: NotificationLogRepositoryInterface,
        calendar_repository: CalendarRepositoryInterface,
        deadline_notifier_settings: DeadlineNotifierSettings,
    ):
        self.task_manager_repository = task_manager_repository
        self.user_config_repository = user_config_repository
        self.telegram_notifier = telegram_notifier
        self.notification_log_repository = notification_log_repository
        self.calendar_repository = calendar_repository
        self.deadline_notifier_settings = deadline_notifier_settings

    async def execute(
        self,
        lookahead_days: int = 7,
        additional_jql: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Execute the deadline alerts use case.

        Args:
            lookahead_days: Number of days to look ahead for deadlines
            additional_jql: Additional JQL filter to apply

        Returns:
            Dictionary with statistics about notifications sent
        """
        try:
            if await self._should_skip_notifications():
                return self._create_skip_stats("holiday_or_weekend")

            stats = self._initialize_stats() 
            issues = await self._get_approaching_deadline_issues(
                lookahead_days,
                additional_jql,
            ) # TODO: make sure that all issues are returned.

            if not issues:
                LOGGER.info("No issues with approaching deadlines found")
                return stats

            alerts = await self._get_active_sprint_alerts(issues)
            stats["issues_processed"] = len(alerts)

            if not alerts:
                LOGGER.info(
                    "No issues in active sprints with approaching deadlines found",
                )
                return stats

            await self._send_all_notifications(alerts, stats)
            LOGGER.info(f"Deadline alerts completed: {stats}")
            return stats

        except Exception as e:
            LOGGER.error(f"Error executing deadline alerts: {e}")
            raise

    async def _should_skip_notifications(self) -> bool:
        """Check if notifications should be skipped due to holidays or weekends."""
        today = datetime.now().date()
        is_holiday_or_weekend = await self.calendar_repository.is_holiday_or_weekend(
            today,
        )

        if is_holiday_or_weekend:
            LOGGER.info(
                f"Skipping deadline notifications - today ({today}) is a holiday or weekend in Iran",
            )

        return is_holiday_or_weekend

    def _create_skip_stats(self, reason: str) -> Dict[str, int]:
        """Create statistics dictionary for skipped notifications."""
        return {
            "issues_processed": 0,
            "personal_notifications_sent": 0,
            "group_notifications_sent": 0,
            "notifications_skipped": 0,
            "skipped_reason": reason,
        }

    def _initialize_stats(self) -> Dict[str, int]:
        """Initialize statistics dictionary."""
        return {
            "issues_processed": 0,
            "personal_notifications_sent": 0,
            "group_notifications_sent": 0,
            "notifications_skipped": 0,
        }

    async def _get_approaching_deadline_issues(
        self,
        lookahead_days: int,
        additional_jql: Optional[str],
    ) -> List:
        """Get issues with approaching deadlines from the task manager."""
        LOGGER.debug(
            f"additional_jql: {additional_jql}, lookahead_days: {lookahead_days}",
        )
        return self.task_manager_repository.get_issues_with_approaching_deadlines(
            lookahead_days=lookahead_days,
            additional_jql=additional_jql,
        )

    async def _get_active_sprint_alerts(self, issues: List) -> List[DeadlineAlert]:
        """Convert issues to alerts and filter for active sprints only."""
        alerts = await self._convert_issues_to_alerts(issues)
        return [alert for alert in alerts if alert.is_in_active_sprint]

    async def _send_all_notifications(
        self,
        alerts: List[DeadlineAlert],
        stats: Dict[str, int],
    ) -> None:
        """Send both personal and group notifications and update statistics."""
        personal_stats = await self._send_personal_notifications(alerts)
        stats["personal_notifications_sent"] = personal_stats["sent"]
        stats["notifications_skipped"] += personal_stats["skipped"]

        group_stats = await self._send_group_notifications(alerts)
        stats["group_notifications_sent"] = group_stats["sent"]
        stats["notifications_skipped"] += group_stats["skipped"]

    async def _convert_issues_to_alerts(
        self,
        issues: List[Issue],
    ) -> List[DeadlineAlert]:
        """Convert Jira issues to deadline alerts."""
        alerts = []
        now = datetime.now()

        for issue in issues:
            try:
                alert = await self._create_deadline_alert(issue, now)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                LOGGER.error(f"Error creating alert for issue {issue.key}: {e}")
                continue

        return alerts

    async def _create_deadline_alert(
        self,
        issue: Issue,
        now: datetime,
    ) -> Optional[DeadlineAlert]:
        """Create a deadline alert from a Jira issue."""
        effective_deadline = self._extract_effective_deadline(issue)

        if not effective_deadline:
            return None

        days_remaining = (effective_deadline.date() - now.date()).days
        issue_url = self._build_issue_url(issue)
        issue_type_name = self._extract_issue_type(issue)
        sprint_info = self._extract_active_sprint_info(issue)

        return DeadlineAlert(
            issue_key=issue.key,
            summary=issue.fields.summary,
            assignee=self._extract_assignee(issue),
            due_date=self._parse_date_field(getattr(issue.fields, "duedate", None)),
            target_end=self._parse_date_field(
                getattr(issue.fields, self.task_manager_repository.jira_target_end_id, None),
            ),
            days_remaining=days_remaining,
            project_key=issue.fields.project.key,
            status=issue.fields.status.name,
            priority=self._extract_priority(issue),
            issue_url=issue_url,
            issue_type=issue_type_name,
            sprint_info=sprint_info,
        )

    def _extract_effective_deadline(self, issue: Issue) -> Optional[datetime]:
        """Extract the effective deadline from due date or target end fields."""
        due_date = self._parse_date_field(getattr(issue.fields, "duedate", None))
        target_end = self._parse_date_field(
            getattr(issue.fields, self.task_manager_repository.jira_target_end_id, None),
        )
        return due_date or target_end

    def _build_issue_url(self, issue: Issue) -> str:
        """Build the complete URL for the Jira issue."""
        base_url = getattr(issue, "_options", {}).get("server", "")
        return f"{base_url}/browse/{issue.key}" if base_url else issue.key

    def _extract_issue_type(self, issue: Issue) -> Optional[str]:
        """Extract the issue type name from the issue."""
        issue_type = getattr(issue.fields, "issuetype", None)
        return issue_type.name if issue_type else None

    def _extract_assignee(self, issue: Issue) -> Optional[str]:
        """Extract the assignee username from the issue."""
        return (
            getattr(issue.fields.assignee, "name", None)
            if issue.fields.assignee
            else None
        )

    def _extract_priority(self, issue: Issue) -> Optional[str]:
        """Extract the priority name from the issue."""
        return issue.fields.priority.name if issue.fields.priority else None

    def _extract_active_sprint_info(self, issue: Issue) -> Optional[str]:
        """Extract active sprint information from the issue."""
        sprint_field = getattr(issue.fields, self.task_manager_repository.jira_sprint_id, None)

        if not sprint_field:
            return None

        return self._find_active_sprint_in_field(sprint_field)

    def _find_active_sprint_in_field(self, sprint_field) -> Optional[str]:
        """Find active sprint information in the sprint field."""
        if isinstance(sprint_field, list):
            for sprint in sprint_field:
                if sprint and "state=ACTIVE" in str(sprint):
                    return str(sprint)
        elif sprint_field and "state=ACTIVE" in str(sprint_field):
            return str(sprint_field)

        return None

    async def _send_personal_notifications(
        self,
        alerts: List[DeadlineAlert],
    ) -> Dict[str, int]:
        """Send personal notifications to assignees."""
        stats = {"sent": 0, "skipped": 0}
        alerts_by_assignee = self._group_alerts_by_assignee(alerts)

        for jira_username, assignee_alerts in alerts_by_assignee.items():
            await self._send_notifications_to_assignee(
                jira_username,
                assignee_alerts,
                stats,
            )

        return stats

    def _group_alerts_by_assignee(
        self,
        alerts: List[DeadlineAlert],
    ) -> Dict[str, List[DeadlineAlert]]:
        """Group alerts by assignee username."""
        alerts_by_assignee = {}
        for alert in alerts:
            if alert.assignee:
                alerts_by_assignee.setdefault(alert.assignee, []).append(alert)
        return alerts_by_assignee

    async def _send_notifications_to_assignee(
        self,
        jira_username: str,
        assignee_alerts: List[DeadlineAlert],
        stats: Dict[str, int],
    ) -> None:
        """Send notifications for all alerts assigned to a specific user."""
        try:
            user_config = self._get_user_config_for_notifications(jira_username)
            if not user_config:
                return

            for alert in assignee_alerts:
                await self._send_single_personal_notification(
                    alert,
                    user_config,
                    stats,
                )

        except Exception as e:
            LOGGER.error(
                f"Error sending personal notification to {jira_username}: {e}",
            )

    def _get_user_config_for_notifications(self, jira_username: str):
        """Get user configuration needed for sending notifications."""
        user_config = self.user_config_repository.get_user_config_by_jira_username(
            jira_username,
        )

        if not user_config or not user_config.telegram_user_chat_id:
            LOGGER.warning(f"No telegram config found for user {jira_username}")
            return None

        return user_config

    async def _send_single_personal_notification(
        self,
        alert: DeadlineAlert,
        user_config,
        stats: Dict[str, int],
    ) -> None:
        """Send a single personal notification for an alert."""
        today = datetime.now().date()

        if await self._is_personal_notification_already_sent(alert, user_config, today):
            stats["skipped"] += 1
            return

        success = await self._send_personal_notification_message(alert, user_config)

        if success:
            await self._log_personal_notification_sent(alert, user_config, today)
            stats["sent"] += 1
        else:
            stats["skipped"] += 1

    async def _is_personal_notification_already_sent(
        self,
        alert: DeadlineAlert,
        user_config,
        today: datetime.date,
    ) -> bool:
        """Check if personal notification was already sent today."""
        return await self.notification_log_repository.has_notification_been_sent(
            alert.issue_key,
            user_config.telegram_user_chat_id,
            datetime.combine(today, datetime.min.time()),
        )

    async def _send_personal_notification_message(
        self,
        alert: DeadlineAlert,
        user_config,
    ) -> bool:
        """Send the actual personal notification message."""
        return await self.telegram_notifier.send_personal_notification(
            user_config.telegram_user_chat_id,
            alert,
        )

    async def _log_personal_notification_sent(
        self,
        alert: DeadlineAlert,
        user_config,
        today: datetime.date,
    ) -> None:
        """Log that a personal notification was sent."""
        await self.notification_log_repository.log_notification_sent(
            alert.issue_key,
            user_config.telegram_user_chat_id,
            datetime.combine(today, datetime.min.time()),
            alert,
        )

    async def _send_group_notifications(
        self,
        alerts: List[DeadlineAlert],
    ) -> Dict[str, int]:
        """Send group notifications to configured group chats."""
        stats = {"sent": 0, "skipped": 0}

        all_notification_chat_ids = self._get_all_notification_chat_ids()

        if not all_notification_chat_ids:
            LOGGER.info("No group chat IDs configured")
            return stats

        for chat_id in all_notification_chat_ids:
            await self._send_single_group_notification(chat_id, alerts, stats)

        return stats

    def _get_all_notification_chat_ids(self) -> List[str]:
        """Get all chat IDs for group notifications."""
        group_chat_ids = self.user_config_repository.get_group_chat_ids()
        filtered_notification_chat_ids = self._get_filtered_notification_chat_ids()
        return group_chat_ids + filtered_notification_chat_ids

    def _get_filtered_notification_chat_ids(self) -> List[str]:
        """Get chat IDs for specific users configured for filtered notifications."""
        chat_ids = []
        for username in self.deadline_notifier_settings.GROUP_NOTIFICATION_USERNAMES:
            user_config = self.user_config_repository.get_user_config_by_jira_username(
                username,
            )
            if user_config and user_config.telegram_user_chat_id:
                chat_ids.append(user_config.telegram_user_chat_id)
        return chat_ids

    async def _send_single_group_notification(
        self,
        chat_id: str,
        alerts: List[DeadlineAlert],
        stats: Dict[str, int],
    ) -> None:
        """Send notification to a single group chat."""
        try:
            today = datetime.now().date()

            if await self._is_group_notification_already_sent(chat_id, today):
                stats["skipped"] += 1
                return
            # TODO: check that only stories are sent for grups.
            urgent_alerts = self._filter_urgent_alerts_for_chat(chat_id, alerts)

            if not urgent_alerts:
                return

            success = await self._send_group_notification_message(
                chat_id,
                urgent_alerts,
            )

            if success:
                await self._log_group_notification_sent(
                    chat_id,
                    today,
                    urgent_alerts[0],
                )
                stats["sent"] += 1
            else:
                stats["skipped"] += 1

        except Exception as e:
            LOGGER.error(f"Error sending group notification to {chat_id}: {e}")

    async def _is_group_notification_already_sent(
        self,
        chat_id: str,
        today: datetime.date,
    ) -> bool:
        """Check if group notification was already sent today."""
        group_key = f"GROUP_{chat_id}"
        return await self.notification_log_repository.has_notification_been_sent(
            group_key,
            chat_id,
            datetime.combine(today, datetime.min.time()),
        )

    def _filter_urgent_alerts_for_chat(
        self,
        chat_id: str,
        alerts: List[DeadlineAlert],
    ) -> List[DeadlineAlert]:
        """Filter alerts based on urgency and chat type."""
        urgent_alerts = [
            alert
            for alert in alerts
            if alert.urgency_level in ["overdue", "today", "urgent"]
        ]

        # For configured users, exclude subtasks (only send stories and tasks)
        filtered_notification_chat_ids = self._get_filtered_notification_chat_ids()
        if chat_id in filtered_notification_chat_ids:
            urgent_alerts = [alert for alert in urgent_alerts if alert.is_story_or_task]

        return urgent_alerts

    async def _send_group_notification_message(
        self,
        chat_id: str,
        urgent_alerts: List[DeadlineAlert],
    ) -> bool:
        """Send the actual group notification message."""
        return await self.telegram_notifier.send_group_notification(
            chat_id,
            urgent_alerts,
            mention_users=True,
        )

    async def _log_group_notification_sent(
        self,
        chat_id: str,
        today: datetime.date,
        representative_alert: DeadlineAlert,
    ) -> None:
        """Log that a group notification was sent."""
        group_key = f"GROUP_{chat_id}"
        await self.notification_log_repository.log_notification_sent(
            group_key,
            chat_id,
            datetime.combine(today, datetime.min.time()),
            representative_alert,
        )

    def _parse_date_field(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse a date field from Jira."""
        if not date_str:
            return None

        try:
            # Handle different date formats
            if "T" in date_str:
                # ISO format with time
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                # Date only format
                return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError) as e:
            LOGGER.warning(f"Failed to parse date '{date_str}': {e}")
            return None
