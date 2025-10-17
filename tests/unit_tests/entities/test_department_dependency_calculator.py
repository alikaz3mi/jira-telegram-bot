"""Tests for Department Dependency Calculator."""
from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timedelta

from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import (
    DepartmentDependencyCalculator,
)


class TestDepartmentDependencyCalculator(unittest.TestCase):
    """Test cases for DepartmentDependencyCalculator."""

    def test_parse_department_deps_single(self):
        """Test parsing a single dependency."""
        deps_str = "UI/UX -> Frontend"
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        self.assertEqual(result, {"Frontend": ["UI/UX"]})

    def test_parse_department_deps_multiple(self):
        """Test parsing multiple dependencies."""
        deps_str = "UI/UX -> Frontend, Backend -> AI"
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        self.assertEqual(result, {
            "Frontend": ["UI/UX"],
            "AI": ["Backend"]
        })

    def test_parse_department_deps_multiple_blockers(self):
        """Test parsing multiple blockers for one department."""
        deps_str = "UI/UX -> Frontend, Backend -> Frontend"
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        self.assertEqual(result, {"Frontend": ["UI/UX", "Backend"]})

    def test_parse_department_deps_empty(self):
        """Test parsing empty dependency string."""
        result = DepartmentDependencyCalculator.parse_department_deps(None)
        self.assertEqual(result, {})
        
        result = DepartmentDependencyCalculator.parse_department_deps("")
        self.assertEqual(result, {})

    def test_calculate_working_days_from_hours_simple(self):
        """Test calculating working days from hours without holidays."""
        start_date = datetime(2025, 10, 19)  # Sunday
        hours = 16  # 2 days
        holidays = set()
        
        actual_start, actual_end = DepartmentDependencyCalculator.calculate_working_days_from_hours(
            hours, start_date, holidays
        )
        
        # Should be Sun Oct 19 to Mon Oct 20
        self.assertEqual(actual_start.date(), datetime(2025, 10, 19).date())
        self.assertEqual(actual_end.date(), datetime(2025, 10, 20).date())

    def test_calculate_working_days_from_hours_with_friday(self):
        """Test calculating working days skipping Friday."""
        start_date = datetime(2025, 10, 23)  # Thursday
        hours = 16  # 2 days
        holidays = set()
        
        actual_start, actual_end = DepartmentDependencyCalculator.calculate_working_days_from_hours(
            hours, start_date, holidays
        )
        
        # Should be Thu Oct 23 to Sat Oct 25 (skipping Friday)
        self.assertEqual(actual_start.date(), datetime(2025, 10, 23).date())
        self.assertEqual(actual_end.date(), datetime(2025, 10, 25).date())

    def test_calculate_working_days_from_hours_with_holiday(self):
        """Test calculating working days with holidays."""
        start_date = datetime(2025, 10, 19)  # Sunday
        hours = 24  # 3 days
        holidays = {datetime(2025, 10, 20).date()}  # Monday is holiday
        
        actual_start, actual_end = DepartmentDependencyCalculator.calculate_working_days_from_hours(
            hours, start_date, holidays
        )
        
        # Should skip Monday and include Sun, Tue, Wed
        self.assertEqual(actual_start.date(), datetime(2025, 10, 19).date())
        self.assertEqual(actual_end.date(), datetime(2025, 10, 22).date())

    def test_calculate_department_deadlines_simple_chain(self):
        """Test calculating deadlines for simple dependency chain."""
        feature_deadline = datetime(2025, 10, 30, 23, 59, 59)
        dept_deps = {"Frontend": ["UI/UX"]}  # Frontend depends on (is blocked by) UI/UX
        department_hours = {
            "UI/UX": 16,      # 2 days
            "Frontend": 24,   # 3 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Frontend depends on UI/UX, so:
        # - Frontend ends on Oct 30 (feature deadline)
        # - Frontend starts 3 working days before Oct 30
        # - UI/UX must complete BEFORE Frontend starts
        # - UI/UX takes 2 working days
        self.assertIn("Frontend", result)
        self.assertIn("UI/UX", result)
        
        # UI/UX must complete before Frontend starts
        frontend_start = result["Frontend"]["start"]
        ui_ux_end = result["UI/UX"]["end"]
        
        # UI/UX end date should be <= Frontend start date
        self.assertLessEqual(ui_ux_end, frontend_start)

    def test_calculate_department_deadlines_with_friday(self):
        """Test calculating deadlines considering Friday weekend."""
        # Set deadline to Saturday Oct 25
        feature_deadline = datetime(2025, 10, 25, 23, 59, 59)
        dept_deps = {}
        department_hours = {"Backend": 8}  # 1 day
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        backend_dates = result["Backend"]
        # Should complete on Saturday
        self.assertEqual(backend_dates["end"].date(), datetime(2025, 10, 25).date())
        # Should start on Thursday (skipping Friday)
        self.assertEqual(backend_dates["start"].date(), datetime(2025, 10, 23).date())

    def test_get_department_from_component(self):
        """Test component name normalization."""
        self.assertEqual(
            DepartmentDependencyCalculator.get_department_from_component("Front-end"),
            "Frontend"
        )
        self.assertEqual(
            DepartmentDependencyCalculator.get_department_from_component("UI / UX"),
            "UI/UX"
        )
        self.assertEqual(
            DepartmentDependencyCalculator.get_department_from_component("DevOPS"),
            "DevOps"
        )


if __name__ == "__main__":
    unittest.main()
