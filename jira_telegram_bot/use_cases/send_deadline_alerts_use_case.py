from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
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
    ):
        self.task_manager_repository = task_manager_repository
        self.user_config_repository = user_config_repository
        self.telegram_notifier = telegram_notifier
        self.notification_log_repository = notification_log_repository
        self.calendar_repository = calendar_repository
        self.telegram_notifier = telegram_notifier
        self.notification_log_repository = notification_log_repository

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
            # Check if today is a holiday or weekend in Iran
            today = datetime.now().date()
            is_holiday_or_weekend = (
                await self.calendar_repository.is_holiday_or_weekend(today)
            )

            if is_holiday_or_weekend:
                LOGGER.info(
                    f"Skipping deadline notifications - today ({today}) is a holiday or weekend in Iran",
                )
                return {
                    "issues_processed": 0,
                    "personal_notifications_sent": 0,
                    "group_notifications_sent": 0,
                    "notifications_skipped": 0,
                    "skipped_reason": "holiday_or_weekend",
                }

            stats = {
                "issues_processed": 0,
                "personal_notifications_sent": 0,
                "group_notifications_sent": 0,
                "notifications_skipped": 0,
            }

            # Get issues with approaching deadlines
            LOGGER.debug(
                f"additional_jql: {additional_jql}, lookahead_days: {lookahead_days}",
            )
            issues = self.task_manager_repository.get_issues_with_approaching_deadlines(
                lookahead_days=lookahead_days,
                additional_jql=additional_jql,
            )

            if not issues:
                LOGGER.info("No issues with approaching deadlines found")
                return stats

            # Convert issues to deadline alerts
            alerts = await self._convert_issues_to_alerts(issues)

            # Filter to only include issues in active sprints
            active_sprint_alerts = [
                alert for alert in alerts if alert.is_in_active_sprint
            ]
            stats["issues_processed"] = len(active_sprint_alerts)

            if not active_sprint_alerts:
                LOGGER.info(
                    "No issues in active sprints with approaching deadlines found",
                )
                return stats

            # Send personal notifications
            personal_stats = await self._send_personal_notifications(
                active_sprint_alerts,
            )
            stats["personal_notifications_sent"] = personal_stats["sent"]
            stats["notifications_skipped"] += personal_stats["skipped"]

            # Send group notifications
            group_stats = await self._send_group_notifications(active_sprint_alerts)
            stats["group_notifications_sent"] = group_stats["sent"]
            stats["notifications_skipped"] += group_stats["skipped"]

            LOGGER.info(f"Deadline alerts completed: {stats}")
            return stats

        except Exception as e:
            LOGGER.error(f"Error executing deadline alerts: {e}")
            raise

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
        due_date = self._parse_date_field(getattr(issue.fields, "duedate", None))
        target_end = self._parse_date_field(
            getattr(issue.fields, "customfield_10110", None),
        )

        effective_deadline = due_date or target_end
        if not effective_deadline:
            return None

        days_remaining = (effective_deadline.date() - now.date()).days

        # Build issue URL
        base_url = getattr(issue, "_options", {}).get("server", "")
        issue_url = f"{base_url}/browse/{issue.key}" if base_url else issue.key

        # Get issue type
        issue_type = getattr(issue.fields, "issuetype", None)
        issue_type_name = issue_type.name if issue_type else None

        # Get sprint information to check if in active sprint
        sprint_info = None
        sprint_field = getattr(
            issue.fields,
            "customfield_10020",
            None,
        )  # Common sprint field
        if sprint_field:
            # Sprint field is usually a list, check if any are active
            if isinstance(sprint_field, list):
                for sprint in sprint_field:
                    if sprint and "state=ACTIVE" in str(sprint):
                        sprint_info = str(sprint)
                        break
            elif sprint_field and "state=ACTIVE" in str(sprint_field):
                sprint_info = str(sprint_field)

        return DeadlineAlert(
            issue_key=issue.key,
            summary=issue.fields.summary,
            assignee=getattr(issue.fields.assignee, "name", None)
            if issue.fields.assignee
            else None,
            due_date=due_date,
            target_end=target_end,
            days_remaining=days_remaining,
            project_key=issue.fields.project.key,
            status=issue.fields.status.name,
            priority=issue.fields.priority.name if issue.fields.priority else None,
            issue_url=issue_url,
            issue_type=issue_type_name,
            sprint_info=sprint_info,
        )

    async def _send_personal_notifications(
        self,
        alerts: List[DeadlineAlert],
    ) -> Dict[str, int]:
        """Send personal notifications to assignees."""
        stats = {"sent": 0, "skipped": 0}
        today = datetime.now().date()

        # Group alerts by assignee
        alerts_by_assignee = {}
        for alert in alerts:
            if alert.assignee:
                alerts_by_assignee.setdefault(alert.assignee, []).append(alert)

        for jira_username, assignee_alerts in alerts_by_assignee.items():
            try:
                user_config = (
                    self.user_config_repository.get_user_config_by_jira_username(
                        jira_username,
                    )
                )
                if not user_config or not user_config.telegram_user_chat_id:
                    LOGGER.warning(f"No telegram config found for user {jira_username}")
                    continue

                # Send notification for each alert
                for alert in assignee_alerts:
                    # Check if already sent today
                    already_sent = await self.notification_log_repository.has_notification_been_sent(
                        alert.issue_key,
                        user_config.telegram_user_chat_id,
                        datetime.combine(today, datetime.min.time()),
                    )

                    if already_sent:
                        stats["skipped"] += 1
                        continue

                    # Send notification
                    success = await self.telegram_notifier.send_personal_notification(
                        user_config.telegram_user_chat_id,
                        alert,
                    )

                    if success:
                        await self.notification_log_repository.log_notification_sent(
                            alert.issue_key,
                            user_config.telegram_user_chat_id,
                            datetime.combine(today, datetime.min.time()),
                            alert,
                        )
                        stats["sent"] += 1
                    else:
                        stats["skipped"] += 1

            except Exception as e:
                LOGGER.error(
                    f"Error sending personal notification to {jira_username}: {e}",
                )
                continue

        return stats

    async def _send_group_notifications(
        self,
        alerts: List[DeadlineAlert],
    ) -> Dict[str, int]:
        """Send group notifications to configured group chats."""
        stats = {"sent": 0, "skipped": 0}
        # TODO: add group chat id later
        # group_chat_ids = self.user_config_repository.get_group_chat_ids()
        group_chat_ids = [
            self.user_config_repository.get_user_config_by_jira_username(
                "ali_kazemi",
            ).telegram_user_chat_id,
            self.user_config_repository.get_user_config_by_jira_username(
                "a_heravi",
            ).telegram_user_chat_id,
        ]

        today = datetime.now().date()

        if not group_chat_ids:
            LOGGER.info("No group chat IDs configured")
            return stats

        for chat_id in group_chat_ids:
            try:
                # Check if group notification already sent today
                group_key = f"GROUP_{chat_id}"
                already_sent = (
                    await self.notification_log_repository.has_notification_been_sent(
                        group_key,
                        chat_id,
                        datetime.combine(today, datetime.min.time()),
                    )
                )

                if already_sent:
                    stats["skipped"] += 1
                    continue

                # Filter alerts that should be sent to groups (e.g., urgent ones)
                urgent_alerts = [
                    alert
                    for alert in alerts
                    if alert.urgency_level in ["overdue", "today", "urgent"]
                ]

                # For heravi and alikaz3mi group notifications, exclude subtasks
                heravi_user = (
                    self.user_config_repository.get_user_config_by_jira_username(
                        "a_heravi",
                    )
                )
                alikaz3mi_user = (
                    self.user_config_repository.get_user_config_by_jira_username(
                        "ali_kazemi",
                    )
                )

                if chat_id in [
                    heravi_user.telegram_user_chat_id,
                    alikaz3mi_user.telegram_user_chat_id,
                ]:
                    # Filter to only stories and tasks (exclude subtasks)
                    urgent_alerts = [
                        alert for alert in urgent_alerts if alert.is_story_or_task
                    ]

                if not urgent_alerts:
                    continue

                # Send group notification
                success = await self.telegram_notifier.send_group_notification(
                    chat_id,
                    urgent_alerts,
                    mention_users=True,
                )

                if success:
                    await self.notification_log_repository.log_notification_sent(
                        group_key,
                        chat_id,
                        datetime.combine(today, datetime.min.time()),
                        urgent_alerts[0],  # Log first alert as representative
                    )
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1

            except Exception as e:
                LOGGER.error(f"Error sending group notification to {chat_id}: {e}")
                continue

        return stats

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
