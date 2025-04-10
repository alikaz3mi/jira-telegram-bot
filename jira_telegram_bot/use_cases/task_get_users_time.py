from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime

import xlsxwriter
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER


class TaskGetUsersTime:
    """
    A use case to retrieve users' time spent, remote time, and weekend/holiday time
    from Jira issues/worklogs within a specified date range.
    """

    ENTER_FIRST_DAY = 1
    ENTER_DAYS = 2

    def __init__(self, jira, authorized_usernames: list[str]):
        """
        :param jira: An instance of JIRA or your own JiraRepository wrapper
        :param authorized_usernames: List of Telegram usernames who are authorized to generate the report
        """
        self.jira = jira
        self.authorized_usernames = authorized_usernames

    async def start_get_users_time(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """
        Entry point for the conversation. Checks if the user is authorized, then asks for the first day.
        """
        username = update.effective_user.username

        if username not in self.authorized_usernames:
            await update.message.reply_text(
                "You are not authorized to access this report.",
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "Please enter the *first day* in `YYYY-MM-DD` format:",
            parse_mode="Markdown",
        )
        return self.ENTER_FIRST_DAY

    async def get_first_day(self, update: Update, context: CallbackContext) -> int:
        """
        Receives the first day, validates the date format, and moves on to ask for the number of days.
        """
        text = update.message.text.strip()

        try:
            first_day = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            await update.message.reply_text(
                "Invalid date format. Please enter the date in `YYYY-MM-DD` format.",
            )
            return self.ENTER_FIRST_DAY

        context.user_data["first_day"] = first_day
        await update.message.reply_text(
            "Please enter the *number of days* (e.g., 30):",
            parse_mode="Markdown",
        )
        return self.ENTER_DAYS

    async def get_days(self, update: Update, context: CallbackContext) -> int:
        """
        Receives the number of days, validates, then fetches issues/worklogs, generates a report,
        and ends the conversation.
        """
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text(
                "Please enter a valid integer for the number of days.",
            )
            return self.ENTER_DAYS

        days = int(text)
        context.user_data["days"] = days

        first_day: datetime = context.user_data["first_day"]
        jql = (
            f'updated >= "{first_day.strftime("%Y-%m-%d")}" AND worklogDate >= "{first_day.strftime("%Y-%m-%d")}" '
            "ORDER BY updated DESC"
        )

        try:
            issues = self.jira.search_for_issues(jql, max_results=1000)
        except Exception as e:
            LOGGER.error("Error querying JIRA: %s", e)
            await update.message.reply_text(f"Failed to fetch issues: {str(e)}")
            return ConversationHandler.END

        user_data_map = defaultdict(
            lambda: {
                "total_time": 0,
                "remote_time": 0,
                "weekend_holiday_time": 0,
            },
        )

        for issue in issues:
            try:
                worklogs = self.jira.jira.worklogs(issue.key)
            except Exception as e:
                LOGGER.error(f"Failed to fetch worklogs for issue {issue.key}: {e}")
                continue

            for wl in worklogs:
                author_name = wl.author.displayName
                time_spent_seconds = wl.timeSpentSeconds or 0
                comment = (wl.comment or "").lower()
                started_str = wl.started  # e.g. "2023-04-05T10:45:00.000+0300"

                # Update total time
                user_data_map[author_name]["total_time"] += time_spent_seconds

                # Check if "remote" is in the worklog comment
                if "remote" in comment:
                    user_data_map[author_name]["remote_time"] += time_spent_seconds

                # Parse the start date of the worklog
                try:
                    # Adjust parsing if your JIRA date format differs
                    started_date = datetime.strptime(
                        started_str.split(".")[0],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                except ValueError:
                    # Fallback or log parsing errors
                    started_date = None

                # Check if it was a weekend or holiday
                if started_date is not None:
                    if self._is_weekend_or_persian_holiday(started_date):
                        user_data_map[author_name][
                            "weekend_holiday_time"
                        ] += time_spent_seconds

        # Generate and send Excel file
        await self._generate_and_send_excel(update, user_data_map)

        return ConversationHandler.END

    def _is_weekend_or_persian_holiday(self, date_obj: datetime) -> bool:
        """
        Check if the given date is a weekend or a Persian holiday.
        Currently only checks for weekend.
        Replace with your own holiday logic or external library if needed.
        """
        # In Persian calendar, Friday is the weekend day (weekday 4)
        weekday = date_obj.weekday()
        if weekday == 4:  # Friday
            return True
        # TODO: Add logic for Persian holidays if you have a lookup table or API.
        return False

    async def _generate_and_send_excel(
        self,
        update: Update,
        user_data_map: dict,
    ) -> None:
        """
        Generates the Excel file in-memory and sends it to the user.
        """
        output_stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(output_stream, {"in_memory": True})
        worksheet = workbook.add_worksheet("Users Time")

        headers = [
            "Person Name",
            "Total Time (hrs)",
            "Remote Time (hrs)",
            "Weekend/Holiday Time (hrs)",
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)

        row = 1
        for person_name, data in user_data_map.items():
            total_hours = data["total_time"] / 3600
            remote_hours = data["remote_time"] / 3600
            weekend_holiday_hours = data["weekend_holiday_time"] / 3600

            worksheet.write(row, 0, person_name)
            worksheet.write(row, 1, total_hours)
            worksheet.write(row, 2, remote_hours)
            worksheet.write(row, 3, weekend_holiday_hours)
            row += 1

        workbook.close()
        output_stream.seek(0)

        await update.message.reply_document(
            document=output_stream,
            filename="users_time_report.xlsx",
            caption="Here is your users time report.",
        )
