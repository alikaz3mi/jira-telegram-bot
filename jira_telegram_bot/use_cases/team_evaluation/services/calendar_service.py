"""Calendar service for team evaluation."""

from datetime import date, timedelta
from typing import Set, Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface


class CalendarService:
    """Service for calendar and working hours calculations."""

    def __init__(
        self,
        calendar_repo: CalendarRepositoryInterface,
        leave_repo: LeaveRepositoryInterface
    ):
        """Initialize the service.
        
        Args:
            calendar_repo: Calendar repository
            leave_repo: Leave repository
        """
        self.calendar_repo = calendar_repo
        self.leave_repo = leave_repo

    async def calculate_expected_hours(
        self,
        week_start: date,
        week_end: date,
        weekly_hours: float,
        workdays: Tuple[int, ...],
        username: str = None
    ) -> float:
        """Calculate expected working hours for a week.
        
        Args:
            week_start: Start of the week
            week_end: End of the week
            weekly_hours: Total weekly hours
            workdays: Tuple of working day numbers (0=Monday, 6=Sunday)
            username: Username for leave calculation (optional)
            
        Returns:
            Expected hours for the week
        """
        try:
            # Calculate daily hours
            daily_hours = weekly_hours / len(workdays)
            
            # Get holidays for the year(s) involved
            years = {week_start.year, week_end.year}
            holidays = set()
            for year in years:
                year_holidays = await self.calendar_repo.get_holidays(year)
                holidays.update(year_holidays)
            
            # Get user leaves if username provided
            user_leaves = set()
            if username:
                for year in years:
                    year_leaves = await self.leave_repo.get_user_leaves(username, year)
                    user_leaves.update(year_leaves)
            
            # Count working days in the week
            working_days = 0
            current_date = week_start
            
            while current_date <= week_end:
                # Check if it's a working day
                if current_date.weekday() in workdays:
                    # Check if it's not a holiday or leave day
                    if (current_date not in holidays and 
                        current_date not in user_leaves):
                        working_days += 1
                
                current_date += timedelta(days=1)
            
            expected_hours = working_days * daily_hours
            
            LOGGER.debug(
                f"Expected hours calculation: {working_days} working days × "
                f"{daily_hours:.2f} daily hours = {expected_hours:.2f} hours"
            )
            
            return expected_hours
            
        except Exception as e:
            LOGGER.error(f"Error calculating expected hours: {e}")
            return 0.0

    @staticmethod
    def get_week_bounds(target_date: date) -> Tuple[date, date]:
        """Get the start and end dates of the week containing the target date.
        
        Args:
            target_date: The date to find the week for
            
        Returns:
            Tuple of (week_start, week_end) dates
        """
        # Assuming week starts on Saturday (weekday 5)
        days_since_saturday = (target_date.weekday() + 2) % 7
        week_start = target_date - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=6)
        
        return week_start, week_end
