"""JSON-based calendar repository implementation."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Set

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.utils.exceptions import RepositoryError


class JsonCalendarRepository(CalendarRepositoryInterface):
    """JSON file-based calendar repository."""

    def __init__(self, data_path: str = "data/storage"):
        """Initialize the repository.
        
        Args:
            data_path: Path to the directory containing calendar JSON files
        """
        self.data_path = Path(data_path)

    async def get_holidays(self, year: int) -> Set[date]:
        """Get holidays for a given year.
        
        Args:
            year: The year to get holidays for
            
        Returns:
            Set of holiday dates
        """
        try:
            calendar_data = await self._load_calendar_data(year)
            holidays = set()
            
            for month_data in calendar_data.get("months", {}).values():
                for day_str, day_info in month_data.get("days", {}).items():
                    if day_info.get("is_holiday", False):
                        try:
                            day = int(day_str)
                            month = month_data.get("month", 1)
                            holidays.add(date(year, month, day))
                        except (ValueError, TypeError) as e:
                            LOGGER.warning(f"Invalid date format in calendar: {day_str}, {e}")
                            continue
            
            LOGGER.debug(f"Found {len(holidays)} holidays for year {year}")
            return holidays
            
        except Exception as e:
            LOGGER.error(f"Error loading holidays for year {year}: {e}")
            raise RepositoryError(f"Failed to load holidays: {e}")

    async def get_disabled_days(self, year: int) -> Set[date]:
        """Get disabled/non-working days for a given year.
        
        Args:
            year: The year to get disabled days for
            
        Returns:
            Set of disabled dates
        """
        try:
            calendar_data = await self._load_calendar_data(year)
            disabled_days = set()
            
            for month_data in calendar_data.get("months", {}).values():
                for day_str, day_info in month_data.get("days", {}).items():
                    if day_info.get("is_disabled", False):
                        try:
                            day = int(day_str)
                            month = month_data.get("month", 1)
                            disabled_days.add(date(year, month, day))
                        except (ValueError, TypeError) as e:
                            LOGGER.warning(f"Invalid date format in calendar: {day_str}, {e}")
                            continue
            
            LOGGER.debug(f"Found {len(disabled_days)} disabled days for year {year}")
            return disabled_days
            
        except Exception as e:
            LOGGER.error(f"Error loading disabled days for year {year}: {e}")
            raise RepositoryError(f"Failed to load disabled days: {e}")

    async def get_calendar_header(self, year: int, month: int) -> Dict:
        """Get calendar header information for a specific month.
        
        Args:
            year: The year
            month: The month (1-12)
            
        Returns:
            Dictionary containing calendar metadata
        """
        try:
            calendar_data = await self._load_calendar_data(year)
            months_data = calendar_data.get("months", {})
            
            # Find month data (keys could be month names or numbers)
            month_data = None
            for key, data in months_data.items():
                if (isinstance(key, int) and key == month) or data.get("month") == month:
                    month_data = data
                    break
            
            if not month_data:
                LOGGER.warning(f"No data found for month {month} in year {year}")
                return {}
            
            return {
                "year": year,
                "month": month,
                "month_name": month_data.get("name", f"Month {month}"),
                "total_days": month_data.get("total_days", 30),
                "working_days": month_data.get("working_days", 0)
            }
            
        except Exception as e:
            LOGGER.error(f"Error loading calendar header for {year}/{month}: {e}")
            raise RepositoryError(f"Failed to load calendar header: {e}")

    async def _load_calendar_data(self, year: int) -> Dict:
        """Load calendar data from JSON file.
        
        Args:
            year: The year to load data for
            
        Returns:
            Dictionary containing calendar data
        """
        calendar_file = self.data_path / f"{year}.json"
        
        if not calendar_file.exists():
            LOGGER.warning(f"Calendar file not found: {calendar_file}")
            return {}
        
        try:
            with open(calendar_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            LOGGER.debug(f"Loaded calendar data for year {year}")
            return data
        except json.JSONDecodeError as e:
            LOGGER.error(f"Invalid JSON in calendar file {calendar_file}: {e}")
            raise RepositoryError(f"Invalid calendar file format: {e}")
        except Exception as e:
            LOGGER.error(f"Error reading calendar file {calendar_file}: {e}")
            raise RepositoryError(f"Failed to read calendar file: {e}")
