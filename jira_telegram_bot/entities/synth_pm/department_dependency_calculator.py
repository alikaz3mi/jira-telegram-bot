"""Department dependency calculator for SynthPM."""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import jdatetime

from jira_telegram_bot import LOGGER


class DepartmentDependencyCalculator:
    """Calculate deadlines and dependencies for department tasks."""

    HOURS_PER_DAY = 8
    FRIDAY_WEEKDAY = 4

    @staticmethod
    def parse_department_deps(department_deps_str: Optional[str]) -> Dict[str, List[str]]:
        """Parse department dependencies string into a dictionary.

        Supports two formats:
        1. Arrow format: "UI/UX -> Frontend, Backend -> AI"
        2. Blocks format: "UI/UX blocks Frontend, Backend blocks AI"

        Args:
            department_deps_str: String in format "Blocker blocks Blocked" or "Blocker -> Blocked"

        Returns:
            Dictionary where key is blocked department and value is list of blocking departments
            Example: {"Frontend": ["UI/UX"], "AI": ["Backend"]}
        """
        if not department_deps_str:
            return {}

        dependencies = {}
        
        try:
            # Split by comma to get individual dependency pairs
            pairs = [p.strip() for p in department_deps_str.split(",")]
            
            for pair in pairs:
                separator = None
                parts = None
                
                # Try "blocks" format first
                if " blocks " in pair.lower():
                    # Split case-insensitively
                    import re
                    parts = re.split(r'\s+blocks\s+', pair, flags=re.IGNORECASE)
                    separator = "blocks"
                elif "->" in pair:
                    # Try arrow format
                    parts = pair.split("->")
                    separator = "->"
                else:
                    # No valid separator found
                    LOGGER.warning(f"No valid separator found in dependency pair: '{pair}'")
                    continue
                    
                if not parts or len(parts) != 2:
                    LOGGER.warning(f"Invalid dependency pair format: '{pair}'")
                    continue
                    
                blocking_dept = parts[0].strip()
                blocked_dept = parts[1].strip()
                
                if not blocking_dept or not blocked_dept:
                    LOGGER.warning(f"Empty department name in dependency pair: '{pair}'")
                    continue
                
                if blocked_dept not in dependencies:
                    dependencies[blocked_dept] = []
                    
                dependencies[blocked_dept].append(blocking_dept)
                LOGGER.debug(f"Parsed dependency: {blocking_dept} blocks {blocked_dept}")
                
        except Exception as e:
            LOGGER.error(f"Error parsing department dependencies '{department_deps_str}': {e}")
            return {}
            
        return dependencies

    @staticmethod
    def calculate_working_days_from_hours(
        hours: int,
        start_date: datetime,
        holidays: set,
    ) -> Tuple[datetime, datetime]:
        """Calculate start and end dates based on story points (hours) and working days.

        Args:
            hours: Number of hours (story points)
            start_date: Start date for calculation
            holidays: Set of holiday dates

        Returns:
            Tuple of (calculated_start_date, calculated_end_date)
        """
        if hours <= 0:
            return start_date, start_date

        # Calculate number of working days needed
        days_needed = (hours + DepartmentDependencyCalculator.HOURS_PER_DAY - 1) // DepartmentDependencyCalculator.HOURS_PER_DAY

        current_date = start_date
        working_days_counted = 0

        # Find the actual start date (skip weekends/holidays)
        while DepartmentDependencyCalculator._is_non_working_day(current_date, holidays):
            current_date += timedelta(days=1)

        actual_start_date = current_date

        # Calculate end date by counting working days
        while working_days_counted < days_needed:
            if not DepartmentDependencyCalculator._is_non_working_day(current_date, holidays):
                working_days_counted += 1
                if working_days_counted < days_needed:
                    current_date += timedelta(days=1)
            else:
                current_date += timedelta(days=1)

        actual_end_date = current_date

        return actual_start_date, actual_end_date

    @staticmethod
    def _is_non_working_day(check_date: datetime, holidays: set) -> bool:
        """Check if a date is a non-working day (Friday or holiday).

        Args:
            check_date: Date to check
            holidays: Set of holiday dates

        Returns:
            True if non-working day, False otherwise
        """
        # Check if Friday (weekday 4)
        if check_date.weekday() == DepartmentDependencyCalculator.FRIDAY_WEEKDAY:
            return True

        # Check if holiday
        if check_date.date() in holidays:
            return True

        return False

    @staticmethod
    def calculate_department_deadlines(
        feature_deadline: Optional[datetime],
        department_deps: Dict[str, List[str]],
        department_hours: Dict[str, int],
        holidays: set,
        implementation_start_date: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, datetime]]:
        """Calculate start and end dates for each department considering dependencies.
        
        Strategy: Work FORWARD from implementation_start_date, scheduling each department
        to start after all its blockers complete. Then work BACKWARD to fit within deadline.

        Args:
            feature_deadline: Overall feature deadline
            department_deps: Dictionary of dependencies (blocked -> [blockers])
            department_hours: Dictionary of hours per department
            holidays: Set of holiday dates
            implementation_start_date: Earliest date any department can start (optional)

        Returns:
            Dictionary mapping department to {"start": datetime, "end": datetime}
        """
        if not feature_deadline or not department_hours:
            return {}

        all_departments = set(department_hours.keys())
        
        # PHASE 1: Calculate forward schedule
        # This gives us the minimum time needed and correct dependency order
        forward_schedule = {}
        processed = set()
        
        # Determine earliest start date
        if implementation_start_date:
            earliest_start = implementation_start_date
        else:
            # Calculate from deadline if no implementation start date provided
            total_hours = sum(department_hours.values())
            total_days = (total_hours + DepartmentDependencyCalculator.HOURS_PER_DAY - 1) // DepartmentDependencyCalculator.HOURS_PER_DAY
            
            # Start from a point early enough to fit all work
            earliest_start = feature_deadline
            days_back = 0
            while days_back < total_days * 2:  # Add buffer for holidays and dependencies
                earliest_start = earliest_start - timedelta(days=1)
                if not DepartmentDependencyCalculator._is_non_working_day(earliest_start, holidays):
                    days_back += 1
        
        # Ensure earliest_start is a working day
        while DepartmentDependencyCalculator._is_non_working_day(earliest_start, holidays):
            earliest_start = earliest_start + timedelta(days=1)
        
        # Process departments in dependency order (forward scheduling)
        while len(processed) < len(all_departments):
            # Find departments that can start now (all blockers completed)
            ready_departments = []
            
            for dept in all_departments:
                if dept in processed:
                    continue
                
                # Check if all blockers are processed
                blocking_depts = department_deps.get(dept, [])
                if all(blocker in processed or blocker not in all_departments for blocker in blocking_depts):
                    ready_departments.append(dept)
            
            if not ready_departments:
                LOGGER.error(
                    f"No ready departments found. This indicates circular dependencies. "
                    f"Processed: {processed}, Remaining: {all_departments - processed}"
                )
                break
            
            # Schedule each ready department
            for dept in ready_departments:
                dept_hours = department_hours.get(dept, 0)
                if dept_hours == 0:
                    # No work, just mark as processed
                    forward_schedule[dept] = {
                        "start": earliest_start,
                        "end": earliest_start,
                    }
                    processed.add(dept)
                    continue
                
                # Find the latest end time among all blockers
                latest_blocker_end = None
                blocking_depts = department_deps.get(dept, [])
                for blocker in blocking_depts:
                    if blocker in forward_schedule:
                        blocker_end = forward_schedule[blocker]["end"]
                        if latest_blocker_end is None or blocker_end > latest_blocker_end:
                            latest_blocker_end = blocker_end
                
                # Determine start date
                if latest_blocker_end is not None:
                    # Start the day after the latest blocker completes
                    start_date = latest_blocker_end + timedelta(days=1)
                    # Move to next working day if needed
                    while DepartmentDependencyCalculator._is_non_working_day(start_date, holidays):
                        start_date += timedelta(days=1)
                else:
                    # No blockers, start from earliest_start
                    start_date = earliest_start
                
                # Calculate end date forward from start
                end_date = DepartmentDependencyCalculator._calculate_end_date_forward(
                    start_date,
                    dept_hours,
                    holidays,
                )
                
                forward_schedule[dept] = {
                    "start": start_date,
                    "end": end_date,
                }
                
                LOGGER.debug(
                    f"Forward schedule {dept}: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} "
                    f"({dept_hours}h)"
                )
                
                processed.add(dept)
        
        # PHASE 2: Adjust schedule to fit within deadline (if needed)
        # Find the latest end date in forward schedule
        max_end_date = max(dates["end"] for dates in forward_schedule.values())
        
        if max_end_date > feature_deadline:
            # Schedule doesn't fit within deadline
            days_over = 0
            current = max_end_date
            while current > feature_deadline:
                current = current - timedelta(days=1)
                if not DepartmentDependencyCalculator._is_non_working_day(current, holidays):
                    days_over += 1
            
            LOGGER.warning(
                f"Schedule exceeds deadline by {days_over} working days. "
                f"Latest completion: {max_end_date.strftime('%Y-%m-%d')}, "
                f"Deadline: {feature_deadline.strftime('%Y-%m-%d')}. "
                f"Work cannot be completed on time with the given dependencies and hours."
            )
            
            # Return forward schedule as-is (cannot fit within deadline)
            # It's better to show the realistic timeline than give impossible dates
            final_schedule = forward_schedule
        else:
            # Schedule fits! Use as-is
            final_schedule = forward_schedule
        
        # Verify no department starts before implementation_start_date
        if implementation_start_date:
            for dept, dates in final_schedule.items():
                if dates["start"] < implementation_start_date:
                    LOGGER.warning(
                        f"{dept} scheduled to start {dates['start'].strftime('%Y-%m-%d')} "
                        f"before implementation start date {implementation_start_date.strftime('%Y-%m-%d')}. "
                        f"This indicates insufficient time between implementation start and deadline."
                    )
        
        return final_schedule

    @staticmethod
    def _calculate_start_date_backwards(
        end_date: datetime,
        hours: int,
        holidays: set,
    ) -> datetime:
        """Calculate start date by working backwards from end date.

        Args:
            end_date: End date to work backwards from
            hours: Number of hours needed
            holidays: Set of holiday dates

        Returns:
            Calculated start date
        """
        if hours <= 0:
            return end_date

        days_needed = (hours + DepartmentDependencyCalculator.HOURS_PER_DAY - 1) // DepartmentDependencyCalculator.HOURS_PER_DAY

        current_date = end_date
        working_days_counted = 0

        # Move backwards, counting working days
        while working_days_counted < days_needed:
            current_date -= timedelta(days=1)
            if not DepartmentDependencyCalculator._is_non_working_day(current_date, holidays):
                working_days_counted += 1

        # Ensure start date is on a working day
        while DepartmentDependencyCalculator._is_non_working_day(current_date, holidays):
            current_date -= timedelta(days=1)

        return current_date

    @staticmethod
    def _calculate_end_date_forward(
        start_date: datetime,
        hours: int,
        holidays: set,
    ) -> datetime:
        """Calculate end date by working forward from start date.

        Args:
            start_date: Start date to work forward from
            hours: Number of hours needed
            holidays: Set of holiday dates

        Returns:
            Calculated end date
        """
        if hours <= 0:
            return start_date

        days_needed = (hours + DepartmentDependencyCalculator.HOURS_PER_DAY - 1) // DepartmentDependencyCalculator.HOURS_PER_DAY

        current_date = start_date
        working_days_counted = 0

        # Count forward through working days
        while working_days_counted < days_needed:
            if not DepartmentDependencyCalculator._is_non_working_day(current_date, holidays):
                working_days_counted += 1
                if working_days_counted < days_needed:
                    current_date += timedelta(days=1)
            else:
                current_date += timedelta(days=1)

        return current_date

    @staticmethod
    def get_department_from_component(component: str) -> Optional[str]:
        """Normalize component name to department name.

        Args:
            component: Component name from Jira

        Returns:
            Normalized department name
        """
        # Mapping between common variations
        mapping = {
            "front-end": "Frontend",
            "frontend": "Frontend",
            "Front-end": "Frontend",
            "backend": "Backend",
            "Backend": "Backend",
            "ai": "AI",
            "AI": "AI",
            "devops": "DevOps",
            "DevOps": "DevOps",
            "DevOPS": "DevOps",
            "ui/ux": "UI/UX",
            "UI/UX": "UI/UX",
            "UI / UX": "UI/UX",
        }

        return mapping.get(component, component)
