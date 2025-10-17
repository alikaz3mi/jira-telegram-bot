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

        Args:
            department_deps_str: String in format "UI/UX -> Frontend, Backend -> AI"

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
                if "->" not in pair:
                    continue
                    
                parts = pair.split("->")
                if len(parts) != 2:
                    continue
                    
                blocking_dept = parts[0].strip()
                blocked_dept = parts[1].strip()
                
                if blocked_dept not in dependencies:
                    dependencies[blocked_dept] = []
                    
                dependencies[blocked_dept].append(blocking_dept)
                
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
    ) -> Dict[str, Dict[str, datetime]]:
        """Calculate start and end dates for each department considering dependencies.

        Args:
            feature_deadline: Overall feature deadline
            department_deps: Dictionary of dependencies (blocked -> [blockers])
            department_hours: Dictionary of hours per department
            holidays: Set of holiday dates

        Returns:
            Dictionary mapping department to {"start": datetime, "end": datetime}
        """
        if not feature_deadline or not department_hours:
            return {}

        department_dates = {}

        # Build dependency graph
        blocking_graph = {}  # Maps department to list of departments it blocks
        blocked_by_count = {}  # Count of dependencies for each department

        all_departments = set(department_hours.keys())

        for dept in all_departments:
            blocking_graph[dept] = []
            blocked_by_count[dept] = 0

        # Populate blocking graph
        for blocked_dept, blocking_depts in department_deps.items():
            if blocked_dept not in all_departments:
                continue
            blocked_by_count[blocked_dept] = len(blocking_depts)
            for blocking_dept in blocking_depts:
                if blocking_dept in all_departments:
                    blocking_graph[blocking_dept].append(blocked_dept)

        # Work backwards from feature deadline
        # Start with departments that are NOT blocked by anyone (leaf nodes in dependency tree)
        processed = set()
        department_deadlines = {}

        # Initialize all departments with the feature deadline
        for dept in all_departments:
            department_deadlines[dept] = feature_deadline

        # Process departments in reverse dependency order (from leaf to root)
        # Departments that depend on others must be processed first
        while len(processed) < len(all_departments):
            # Find departments ready to process (all departments they block are already processed)
            ready_departments = []
            for dept in all_departments:
                if dept in processed:
                    continue
                # Check if all departments this one blocks have been processed
                blocked_by_this = blocking_graph.get(dept, [])
                if all(blocked_dept in processed for blocked_dept in blocked_by_this):
                    ready_departments.append(dept)

            if not ready_departments:
                # Handle remaining departments (shouldn't happen with valid dependencies)
                ready_departments = [dept for dept in all_departments if dept not in processed]

            for dept in ready_departments:
                dept_hours = department_hours.get(dept, 0)

                # Get the earliest deadline from departments this one blocks
                earliest_dependent_deadline = feature_deadline
                for blocked_dept in blocking_graph.get(dept, []):
                    if blocked_dept in department_dates:
                        blocked_start = department_dates[blocked_dept]["start"]
                        if blocked_start < earliest_dependent_deadline:
                            earliest_dependent_deadline = blocked_start

                if dept_hours > 0:
                    # Calculate backwards from the earliest dependent deadline
                    end_date = earliest_dependent_deadline
                    start_date = DepartmentDependencyCalculator._calculate_start_date_backwards(
                        end_date,
                        dept_hours,
                        holidays,
                    )

                    department_dates[dept] = {
                        "start": start_date,
                        "end": end_date,
                    }
                else:
                    # No hours allocated, use earliest dependent deadline
                    department_dates[dept] = {
                        "start": earliest_dependent_deadline,
                        "end": earliest_dependent_deadline,
                    }

                processed.add(dept)

        return department_dates

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
