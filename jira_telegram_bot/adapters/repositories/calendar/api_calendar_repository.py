"""API-based calendar repository implementation using holidayapi.ir."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Set

import aiohttp
import jdatetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import (
    CalendarRepositoryInterface,
)
from jira_telegram_bot.utils.exceptions import RepositoryError


class ApiCalendarRepository(CalendarRepositoryInterface):
    """API-based calendar repository using holidayapi.ir."""

    def __init__(self, base_url: str = "https://holidayapi.ir/jalali"):
        """Initialize the repository.

        Args:
            base_url: Base URL for the holiday API
        """
        self.base_url = base_url.rstrip("/")
        self._cache = {}  # Cache API responses to avoid repeated calls

    async def get_holidays(self, year: int) -> Set[date]:
        """Get holidays for a given Gregorian year using the API.

        Args:
            year: The Gregorian year to get holidays for

        Returns:
            Set of holiday dates in Gregorian calendar
        """
        try:
            holidays = set()

            # Convert Gregorian year to Jalali year range
            # A Gregorian year can span across two Jalali years
            jalali_years = self._get_jalali_years_for_gregorian_year(year)

            for jalali_year in jalali_years:
                year_holidays = await self._get_holidays_for_jalali_year(jalali_year)

                # Filter to only include dates that fall in the target Gregorian year
                for holiday_date in year_holidays:
                    if holiday_date.year == year:
                        holidays.add(holiday_date)

            LOGGER.info(f"Found {len(holidays)} holidays for Gregorian year {year}")
            return holidays

        except Exception as e:
            LOGGER.error(f"Error loading holidays for year {year}: {e}")
            raise RepositoryError(f"Failed to load holidays: {e}")

    async def get_disabled_days(self, year: int) -> Set[date]:
        """Get disabled/non-working days for a given Gregorian year.

        For this API-based implementation, disabled days are empty since
        the API only provides holiday information.

        Args:
            year: The Gregorian year to get disabled days for

        Returns:
            Empty set (no disabled days from API)
        """
        # The Holiday API doesn't provide "disabled" days concept
        # This could be extended to include weekends or other non-working days
        return set()

    async def is_holiday_or_weekend(self, check_date: date) -> bool:
        """Check if a specific date is a holiday or weekend in Iran.

        Args:
            check_date: The date to check

        Returns:
            True if the date is a holiday or weekend (Friday/Saturday)
        """
        try:
            # Check if it's a weekend (Friday/Saturday in Iran)
            # In Python datetime, Friday is 4, Saturday is 5
            if check_date.weekday() in [4, 5]:  # Friday, Saturday
                LOGGER.debug(f"{check_date} is a weekend")
                return True

            # Check if it's a holiday using the API
            url = f"https://holidayapi.ir/gregorian/{check_date.year}/{check_date.month:02d}/{check_date.day:02d}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_holiday = data.get("is_holiday", False)

                        if is_holiday:
                            # Log the holiday details
                            events = data.get("events", [])
                            holiday_descriptions = [
                                event.get("description", "")
                                for event in events
                                if event.get("is_holiday", False)
                            ]
                            LOGGER.info(
                                f"{check_date} is a holiday: {', '.join(holiday_descriptions)}",
                            )

                        return is_holiday
                    else:
                        LOGGER.warning(
                            f"Failed to check holiday status for {check_date}: HTTP {response.status}",
                        )
                        # Default to not a holiday if API fails
                        return False

        except Exception as e:
            LOGGER.error(f"Error checking holiday status for {check_date}: {e}")
            # Default to not a holiday if there's an error
            return False

    async def get_calendar_header(self, year: int, month: int) -> dict:
        """Get calendar header information for a given Gregorian year/month.

        Args:
            year: Gregorian year
            month: Gregorian month (1-12)

        Returns:
            Dictionary with calendar header information
        """
        try:
            # Convert to Jalali equivalent
            gregorian_date = date(year, month, 1)
            jalali_date = jdatetime.date.fromgregorian(
                year=gregorian_date.year,
                month=gregorian_date.month,
                day=gregorian_date.day,
            )

            return {
                "gregorian": {
                    "year": year,
                    "month": month,
                    "month_name": gregorian_date.strftime("%B"),
                },
                "jalali": {
                    "year": jalali_date.year,
                    "month": jalali_date.month,
                    "month_name": jalali_date.strftime("%B"),
                },
            }

        except Exception as e:
            LOGGER.error(f"Error getting calendar header for {year}/{month}: {e}")
            raise RepositoryError(f"Failed to get calendar header: {e}")

    async def _get_holidays_for_jalali_year(self, jalali_year: int) -> Set[date]:
        """Get all holidays for a specific Jalali year.

        Args:
            jalali_year: The Jalali year

        Returns:
            Set of holiday dates (Gregorian) for the Jalali year
        """
        cache_key = f"holidays_{jalali_year}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        holidays = set()

        # For efficiency, we'll use a sampling approach:
        # 1. Check every Friday (day 6 in Jalali week)
        # 2. Check specific known holiday dates
        # 3. Sample some other days throughout the year

        # This is more efficient than checking every single day
        sample_dates = self._get_sample_dates_for_jalali_year(jalali_year)

        # Execute API calls with rate limiting
        results = await self._execute_with_rate_limit(
            [self._check_holiday_for_date(jalali_date) for jalali_date in sample_dates],
        )

        for result in results:
            if result:
                holidays.add(result)

        # Cache the result
        self._cache[cache_key] = holidays
        return holidays

    def _get_sample_dates_for_jalali_year(
        self,
        jalali_year: int,
    ) -> list[jdatetime.date]:
        """Get a representative sample of dates for a Jalali year.

        This includes:
        - All Fridays (traditional weekend)
        - First and last day of each month
        - 15th of each month (mid-month sampling)
        - Some additional strategic dates

        Args:
            jalali_year: The Jalali year

        Returns:
            List of Jalali dates to check
        """
        import jdatetime

        sample_dates = []

        for month in range(1, 13):  # 12 months
            # Get the number of days in this month
            try:
                # Try to create the last possible day to find month length
                if month <= 6:  # First 6 months have 31 days
                    days_in_month = 31
                elif month <= 11:  # Months 7-11 have 30 days
                    days_in_month = 30
                else:  # Month 12 has 29 or 30 days depending on leap year
                    try:
                        jdatetime.date(jalali_year, 12, 30)
                        days_in_month = 30
                    except ValueError:
                        days_in_month = 29

                # Sample strategic dates in each month
                strategic_days = [1, 15, days_in_month]  # First, middle, last

                # Add Fridays (sample every Friday in the month)
                for day in range(1, days_in_month + 1):
                    try:
                        date_obj = jdatetime.date(jalali_year, month, day)
                        # In jdatetime, Friday is weekday() == 4
                        if date_obj.weekday() == 4:  # Friday
                            strategic_days.append(day)
                    except ValueError:
                        continue

                # Create date objects for all strategic days
                for day in set(strategic_days):
                    try:
                        sample_dates.append(jdatetime.date(jalali_year, month, day))
                    except ValueError:
                        continue

            except Exception as e:
                LOGGER.debug(
                    f"Error processing month {month} in year {jalali_year}: {e}",
                )
                continue

        LOGGER.debug(
            f"Generated {len(sample_dates)} sample dates for Jalali year {jalali_year}",
        )
        return sample_dates

    async def _check_holiday_for_date(self, jalali_date: jdatetime.date) -> date | None:
        """Check if a specific Jalali date is a holiday.

        Args:
            jalali_date: The Jalali date to check

        Returns:
            Gregorian date if it's a holiday, None otherwise
        """
        try:
            url = f"{self.base_url}/{jalali_date.year}/{jalali_date.month:02d}/{jalali_date.day:02d}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("is_holiday", False):
                            # Convert Jalali date to Gregorian
                            gregorian_date = jalali_date.togregorian()
                            return gregorian_date

                    return None

        except Exception as e:
            LOGGER.debug(f"Error checking holiday for {jalali_date}: {e}")
            return None

    async def _execute_with_rate_limit(
        self,
        tasks,
        batch_size: int = 5,
        delay: float = 0.2,
    ):
        """Execute tasks with rate limiting to avoid overwhelming the API.

        Args:
            tasks: List of coroutines to execute
            batch_size: Number of concurrent requests (reduced for API respect)
            delay: Delay between batches in seconds

        Returns:
            List of results
        """
        results = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)

            # Filter out exceptions and None results
            valid_results = [
                r
                for r in batch_results
                if r is not None and not isinstance(r, Exception)
            ]
            results.extend(valid_results)

            # Rate limiting delay
            if i + batch_size < len(tasks):
                await asyncio.sleep(delay)

        return results

    def _get_jalali_years_for_gregorian_year(self, gregorian_year: int) -> list[int]:
        """Get the Jalali years that correspond to a Gregorian year.

        Args:
            gregorian_year: The Gregorian year

        Returns:
            List of Jalali years (usually 1-2 years)
        """
        # Start and end of Gregorian year
        start_of_year = date(gregorian_year, 1, 1)
        end_of_year = date(gregorian_year, 12, 31)

        # Convert to Jalali
        start_jalali = jdatetime.date.fromgregorian(
            year=start_of_year.year,
            month=start_of_year.month,
            day=start_of_year.day,
        )
        end_jalali = jdatetime.date.fromgregorian(
            year=end_of_year.year,
            month=end_of_year.month,
            day=end_of_year.day,
        )

        # Get unique Jalali years
        jalali_years = list(set([start_jalali.year, end_jalali.year]))
        return sorted(jalali_years)
