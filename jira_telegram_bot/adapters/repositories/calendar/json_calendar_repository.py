"""JSON-based calendar repository implementation."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Set, List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.utils.exceptions import RepositoryError
from jira_telegram_bot.utils.jalali_georgian_calendar import JalaliGregorianCalendar


class JsonCalendarRepository(CalendarRepositoryInterface):
    """JSON file-based calendar repository."""

    def __init__(self, data_path: str = "data/storage"):
        """Initialize the repository.
        
        Args:
            data_path: Path to the directory containing calendar JSON files
        """
        self.data_path = Path(data_path)

    async def get_holidays(self, year: int) -> Set[date]:
        """Get holidays for a given Gregorian year.
        
        Args:
            year: The Gregorian year to get holidays for
            
        Returns:
            Set of holiday dates in Gregorian calendar
        """
        try:
            # Load calendar data (this loads Jalali year data)
            jalali_year = self._gregorian_to_jalali_year(year)
            calendar_months = await self._load_calendar_months(jalali_year)
            
            holidays = set()
            
            for month_data in calendar_months:
                calendar = JalaliGregorianCalendar(month_data)
                
                # Extract Gregorian header info to determine the year/month range
                gregorian_header = month_data["header"]["gregorian"]
                
                 # Get all holidays from this month
                for day in calendar.holidays():
                    gregorian_day = day.g
                    
                    # Determine Gregorian year and month for this day
                    gregorian_date = self._parse_gregorian_date(
                        gregorian_header, gregorian_day
                    )
                    
                    if gregorian_date and gregorian_date.year == year:
                        holidays.add(gregorian_date)
            
            LOGGER.debug(f"Found {len(holidays)} holidays for Gregorian year {year}")
            return holidays
            
        except Exception as e:
            LOGGER.error(f"Error loading holidays for year {year}: {e}")
            raise RepositoryError(f"Failed to load holidays: {e}")

    async def get_disabled_days(self, year: int) -> Set[date]:
        """Get disabled/non-working days for a given Gregorian year.
        
        Args:
            year: The Gregorian year to get disabled days for
            
        Returns:
            Set of disabled dates in Gregorian calendar
        """
        try:
            # Load calendar data (this loads Jalali year data)
            jalali_year = self._gregorian_to_jalali_year(year)
            calendar_months = await self._load_calendar_months(jalali_year)
            
            disabled_days = set()
            
            for month_data in calendar_months:
                calendar = JalaliGregorianCalendar(month_data)
                gregorian_header = month_data["header"]["gregorian"]
                
                # Get disabled days from the month
                for day_json in month_data["days"]:
                    if day_json.get("disabled", False):
                        gregorian_day = int(day_json["day"]["gregorian"])
                        gregorian_date = self._parse_gregorian_date(
                            gregorian_header, gregorian_day
                        )
                        
                        if gregorian_date and gregorian_date.year == year:
                            disabled_days.add(gregorian_date)
            
            LOGGER.debug(f"Found {len(disabled_days)} disabled days for Gregorian year {year}")
            return disabled_days
            
        except Exception as e:
            LOGGER.error(f"Error loading disabled days for year {year}: {e}")
            raise RepositoryError(f"Failed to load disabled days: {e}")

    async def get_calendar_header(self, year: int, month: int) -> Dict:
        """Get calendar header information for a specific Gregorian month.
        
        Args:
            year: The Gregorian year
            month: The Gregorian month (1-12)
            
        Returns:
            Dictionary containing calendar metadata
        """
        try:
            # Convert to approximate Jalali year
            jalali_year = self._gregorian_to_jalali_year(year)
            calendar_months = await self._load_calendar_months(jalali_year)
            
            # Find the month that contains this Gregorian year/month
            for month_data in calendar_months:
                gregorian_header = month_data["header"]["gregorian"]
                if self._month_contains_gregorian_date(gregorian_header, year, month):
                    return {
                        "year": year,
                        "month": month,
                        "jalali_header": month_data["header"]["jalali"],
                        "gregorian_header": gregorian_header,
                        "hijri_header": month_data["header"]["hijri"]
                    }
            
            # Fallback if no matching month found
            LOGGER.warning(f"No calendar data found for Gregorian {year}/{month}")
            return {
                "year": year,
                "month": month,
                "error": "No calendar data available"
            }
            
        except Exception as e:
            LOGGER.error(f"Error loading calendar header for {year}/{month}: {e}")
            raise RepositoryError(f"Failed to load calendar header: {e}")

    def _gregorian_to_jalali_year(self, gregorian_year: int) -> int:
        """Convert Gregorian year to approximate Jalali year.
        
        Args:
            gregorian_year: Gregorian year
            
        Returns:
            Corresponding Jalali year (approximate)
        """
        # Simple conversion: Jalali year is roughly Gregorian year - 621
        # This is approximate and should cover the right range for our data
        return gregorian_year - 621

    def _parse_gregorian_date(self, gregorian_header: str, gregorian_day: int) -> date:
        """Parse Gregorian date from header and day number.
        
        Args:
            gregorian_header: Header like "March - April 2025"
            gregorian_day: Day number in Gregorian calendar
            
        Returns:
            Gregorian date object
        """
        try:
            # Extract year from header (e.g., "March - April 2025" -> 2025)
            year = int(gregorian_header.split()[-1])
            
            # Extract months (e.g., "March - April 2025" -> ["March", "April"])
            month_part = gregorian_header.replace(str(year), "").strip()
            months_str = month_part.split(" - ")
            
            # Map month names to numbers
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            
            # Determine which month this day belongs to
            # This is a simplification - in reality, we'd need to parse the full calendar
            # For now, assume if day <= 15, it's the first month, otherwise second month
            if len(months_str) >= 2:
                first_month = month_names.get(months_str[0].lower())
                second_month = month_names.get(months_str[1].lower())
                
                if first_month and second_month:
                    if gregorian_day <= 15:
                        month = first_month
                    else:
                        month = second_month
                        gregorian_day = gregorian_day - 15  # Adjust day for second month
                else:
                    month = first_month or 1
            else:
                month = month_names.get(months_str[0].lower(), 1)
            
            return date(year, month, gregorian_day)
            
        except Exception as e:
            LOGGER.warning(f"Error parsing Gregorian date from {gregorian_header}, day {gregorian_day}: {e}")
            return None

    def _month_contains_gregorian_date(self, gregorian_header: str, year: int, month: int) -> bool:
        """Check if a calendar month contains a specific Gregorian year/month.
        
        Args:
            gregorian_header: Header like "March - April 2025"
            year: Target Gregorian year
            month: Target Gregorian month
            
        Returns:
            True if the calendar month contains the target date
        """
        try:
            header_year = int(gregorian_header.split()[-1])
            if header_year != year:
                return False
            
            month_part = gregorian_header.replace(str(year), "").strip()
            months_str = month_part.split(" - ")
            
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            
            for month_name in months_str:
                if month_names.get(month_name.lower()) == month:
                    return True
            
            return False
            
        except Exception:
            return False

    async def _load_calendar_months(self, jalali_year: int) -> List[Dict]:
        """Load calendar months from JSON file.
        
        Args:
            jalali_year: The Jalali year to load data for
            
        Returns:
            List of month dictionaries
        """
        calendar_file = self.data_path / f"{jalali_year}.json"
        
        if not calendar_file.exists():
            LOGGER.warning(f"Calendar file not found: {calendar_file}")
            return []
        
        try:
            with open(calendar_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # The JSON file contains a list of months
            if isinstance(data, list):
                LOGGER.debug(f"Loaded {len(data)} months for Jalali year {jalali_year}")
                return data
            else:
                LOGGER.warning(f"Unexpected calendar data format in {calendar_file}")
                return []
                
        except json.JSONDecodeError as e:
            LOGGER.error(f"Invalid JSON in calendar file {calendar_file}: {e}")
            raise RepositoryError(f"Invalid calendar file format: {e}")
        except Exception as e:
            LOGGER.error(f"Error reading calendar file {calendar_file}: {e}")
            raise RepositoryError(f"Failed to read calendar file: {e}")
