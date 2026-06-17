from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime
from datetime import timedelta

import xlsxwriter

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraConnectionSettings, JiraServerRepository
from jira_telegram_bot.app_container import get_container


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
        self.user_data = {}

    def get_first_day(self) -> int:
        """
        Receives the first day, validates the date format, and moves on to ask for the number of days.
        """
        text = input("first date in yyyy-mm-dd format").strip()

        try:
            first_day = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            LOGGER.error(ValueError)
            return self.ENTER_FIRST_DAY

        self.user_data["first_day"] = first_day
        
        text = input("enter number of days").strip()

        days = int(text)
        last_day = first_day + timedelta(days=days)
        
        jql = (
            f'updated >= "{first_day.strftime("%Y-%m-%d")}" AND updated <= "{last_day.strftime("%Y-%m-%d")}" '
            f'AND worklogDate >= "{first_day.strftime("%Y-%m-%d")}" AND worklogDate <= "{last_day.strftime("%Y-%m-%d")}" '
            "ORDER BY updated DESC"
        )

        try:
            issues = self.jira.search_for_issues(jql, max_results=1000)
        except Exception as e:
            LOGGER.error("Error querying JIRA: %s", e)

        user_data_map = defaultdict(
            lambda: {
                "total_time": 0,
                "remote_time": 0,
                "overtime": 0,
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
                started_str = wl.started  # e.g. "2023-04-05T10:45:00.000+0300"
                try:
                    # Parse the start date of the worklog
                    started_date = datetime.strptime(
                        started_str.split(".")[0],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                    # Check if worklog is within the date range
                    if not (first_day <= started_date <= last_day):
                        continue
                except ValueError:
                    # Skip worklogs with unparseable dates
                    continue
                
                author_name = wl.author.displayName
                time_spent_seconds = wl.timeSpentSeconds or 0
                try:
                    comment = (wl.comment or "").lower()
                except:
                    
                    comment = ""

                # Update total time
                user_data_map[author_name]["total_time"] += time_spent_seconds

                # Check for remote work keywords
                remote_keywords = ["remote", "دورکاری", "دور کاری", "دور کار"]
                if any(keyword in comment for keyword in remote_keywords):
                    user_data_map[author_name]["remote_time"] += time_spent_seconds

                # Check for overtime keywords
                overtime_keywords = ["اضافه کاری", "overtime", "overtime work"]
                if any(keyword in comment for keyword in overtime_keywords):
                    user_data_map[author_name]["overtime"] += time_spent_seconds

                # Check if it was a weekend or holiday
                if self._is_weekend_or_persian_holiday(started_date):
                    user_data_map[author_name][
                        "weekend_holiday_time"
                    ] += time_spent_seconds

        # Generate and send Excel file
        self._generate_and_send_excel(user_data_map)

        return 

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

    def _generate_and_send_excel(
        self,
        user_data_map: dict,
    ) -> None:
        """
        Generates the Excel file in-memory and sends it to the user.
        """
        output_stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(output_stream, {"in_memory": True})
        worksheet = workbook.add_worksheet("Users Time")

        headers = [
            "نام فرد",
            "کل زمان ثبت شده در جیرا",
            "زمان دورکاری به ساعت",
            "زمان اضافه کاری به ساعت",
            "زمان کار در تعطیلات به ساعت",
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)

        row = 1
        for person_name, data in user_data_map.items():
            total_hours = data["total_time"] / 3600
            remote_hours = data["remote_time"] / 3600
            overtime_hours = data["overtime"] / 3600
            weekend_holiday_hours = data["weekend_holiday_time"] / 3600

            worksheet.write(row, 0, person_name)
            worksheet.write(row, 1, total_hours)
            worksheet.write(row, 2, remote_hours)
            worksheet.write(row, 3, overtime_hours)
            worksheet.write(row, 4, weekend_holiday_hours)
            row += 1

        workbook.close()
        output_stream.seek(0)
        
        with open("users_time_report.xlsx", "wb") as f:
            f.write(output_stream.read())


if __name__ == '__main__':
    config = JiraConnectionSettings()
    jira = JiraServerRepository(config)
    x = TaskGetUsersTime(jira, None)
    x.get_first_day()
    
    
