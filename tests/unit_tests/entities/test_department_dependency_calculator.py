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

    def test_parse_department_deps_single_blocks_format(self):
        """Test parsing a single dependency with 'blocks' format."""
        deps_str = "UI/UX blocks Frontend"
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

    def test_parse_department_deps_multiple_blocks_format(self):
        """Test parsing multiple dependencies with 'blocks' format."""
        deps_str = "UI/UX blocks Frontend, Backend blocks AI"
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        self.assertEqual(result, {
            "Frontend": ["UI/UX"],
            "AI": ["Backend"]
        })

    def test_parse_department_deps_mixed_formats(self):
        """Test parsing mixed arrow and blocks formats."""
        deps_str = "UI/UX blocks Frontend, Backend -> AI"
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

    def test_parse_department_deps_multiple_blockers_blocks_format(self):
        """Test parsing multiple blockers for one department with 'blocks' format."""
        deps_str = "UI/UX blocks Frontend, Backend blocks Frontend"
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
        # With forward scheduling, Backend schedules as early as possible
        # 1 day of work starting early should complete well before deadline
        self.assertLessEqual(backend_dates["end"], feature_deadline)
        # Start should be before or equal to end
        self.assertLessEqual(backend_dates["start"], backend_dates["end"])
        # Verify no Friday dates are used (Oct 24, 2025 is Friday)
        self.assertNotEqual(backend_dates["start"].weekday(), 4)
        self.assertNotEqual(backend_dates["end"].weekday(), 4)

    def test_calculate_department_deadlines_multiple_blockers(self):
        """Test calculating deadlines when one department is blocked by multiple others."""
        # Frontend depends on both UI/UX and Backend completing first
        feature_deadline = datetime(2025, 11, 20, 23, 59, 59)  # Thursday Nov 20
        dept_deps = {
            "Frontend": ["UI/UX", "Backend"]  # Frontend blocked by both
        }
        department_hours = {
            "UI/UX": 16,      # 2 days
            "Backend": 32,    # 4 days
            "Frontend": 24,   # 3 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # All departments should be scheduled
        self.assertIn("UI/UX", result)
        self.assertIn("Backend", result)
        self.assertIn("Frontend", result)
        
        ui_ux_end = result["UI/UX"]["end"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        
        # Frontend must start AFTER both UI/UX and Backend complete
        # It should start after the LATER of the two blockers
        self.assertGreater(frontend_start, ui_ux_end, 
                          "Frontend should start after UI/UX completes")
        self.assertGreater(frontend_start, backend_end, 
                          "Frontend should start after Backend completes")
        
        # Frontend should start after the latest blocker
        latest_blocker_end = max(ui_ux_end, backend_end)
        # Frontend should start on the next working day after latest blocker
        self.assertGreaterEqual(frontend_start, latest_blocker_end)

    def test_calculate_department_deadlines_chain_with_parallel(self):
        """Test a mix: parallel work that converges, then continues."""
        # UI/UX and Backend work in parallel, both block Frontend, Frontend blocks AI
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday Nov 25
        dept_deps = {
            "Frontend": ["UI/UX", "Backend"],
            "AI": ["Frontend"]
        }
        department_hours = {
            "UI/UX": 16,      # 2 days
            "Backend": 24,    # 3 days  
            "Frontend": 16,   # 2 days
            "AI": 16,         # 2 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Verify all scheduled
        self.assertEqual(len(result), 4)
        
        ui_ux_end = result["UI/UX"]["end"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        frontend_end = result["Frontend"]["end"]
        ai_start = result["AI"]["start"]
        
        # Frontend must start after BOTH blockers
        self.assertGreater(frontend_start, ui_ux_end)
        self.assertGreater(frontend_start, backend_end)
        
        # AI must start after Frontend
        self.assertGreater(ai_start, frontend_end)

    def test_calculate_department_deadlines_three_blockers(self):
        """Test a department blocked by three other departments."""
        # Backend, UI/UX, and DevOps all block Frontend
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday
        dept_deps = {
            "Frontend": ["Backend", "UI/UX", "DevOps"]
        }
        department_hours = {
            "Backend": 32,    # 4 days
            "UI/UX": 16,      # 2 days
            "DevOps": 24,     # 3 days
            "Frontend": 16,   # 2 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Verify all scheduled
        self.assertEqual(len(result), 4)
        
        backend_end = result["Backend"]["end"]
        ui_ux_end = result["UI/UX"]["end"]
        devops_end = result["DevOps"]["end"]
        frontend_start = result["Frontend"]["start"]
        
        # Frontend must start after ALL three blockers
        self.assertGreater(frontend_start, backend_end)
        self.assertGreater(frontend_start, ui_ux_end)
        self.assertGreater(frontend_start, devops_end)
        
        # Find the latest blocker
        latest_blocker_end = max(backend_end, ui_ux_end, devops_end)
        
        # Frontend should start after the latest blocker
        self.assertGreater(frontend_start, latest_blocker_end)

    def test_calculate_department_deadlines_long_chain(self):
        """Test a long chain of dependencies: A blocks B blocks C blocks D."""
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday
        dept_deps = {
            "Backend": ["UI/UX"],
            "Frontend": ["Backend"],
            "AI": ["Frontend"]
        }
        department_hours = {
            "UI/UX": 16,      # 2 days
            "Backend": 16,    # 2 days
            "Frontend": 16,   # 2 days
            "AI": 16,         # 2 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Verify all scheduled
        self.assertEqual(len(result), 4)
        
        ui_ux_end = result["UI/UX"]["end"]
        backend_start = result["Backend"]["start"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        frontend_end = result["Frontend"]["end"]
        ai_start = result["AI"]["start"]
        
        # Verify the chain: each starts after previous completes
        self.assertGreater(backend_start, ui_ux_end)
        self.assertGreater(frontend_start, backend_end)
        self.assertGreater(ai_start, frontend_end)

    def test_calculate_department_deadlines_diamond_pattern(self):
        """Test diamond pattern: UI/UX blocks Backend and Frontend, both block AI."""
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday
        dept_deps = {
            "Backend": ["UI/UX"],
            "Frontend": ["UI/UX"],
            "AI": ["Backend", "Frontend"]
        }
        department_hours = {
            "UI/UX": 16,      # 2 days
            "Backend": 24,    # 3 days
            "Frontend": 16,   # 2 days
            "AI": 16,         # 2 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Verify all scheduled
        self.assertEqual(len(result), 4)
        
        ui_ux_end = result["UI/UX"]["end"]
        backend_start = result["Backend"]["start"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        frontend_end = result["Frontend"]["end"]
        ai_start = result["AI"]["start"]
        
        # Backend and Frontend both start after UI/UX
        self.assertGreater(backend_start, ui_ux_end)
        self.assertGreater(frontend_start, ui_ux_end)
        
        # AI starts after BOTH Backend and Frontend
        self.assertGreater(ai_start, backend_end)
        self.assertGreater(ai_start, frontend_end)

    def test_calculate_department_deadlines_with_friday_skip(self):
        """Test that Friday is correctly skipped in calculations."""
        # Friday is Nov 21, 2025
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday
        dept_deps = {
            "Frontend": ["Backend"]
        }
        department_hours = {
            "Backend": 16,    # 2 days
            "Frontend": 16,   # 2 days
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        backend_start = result["Backend"]["start"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        
        # Verify no dates fall on Friday (weekday 4)
        current = backend_start
        while current <= frontend_start:
            if current.weekday() == 4:  # Friday
                # Check that this date is not used as start or end
                self.assertNotEqual(backend_start.date(), current.date())
                self.assertNotEqual(backend_end.date(), current.date())
                self.assertNotEqual(frontend_start.date(), current.date())
            current += timedelta(days=1)

    def test_calculate_department_deadlines_with_holiday(self):
        """Test that holidays are correctly skipped."""
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)  # Tuesday
        dept_deps = {}
        department_hours = {
            "Backend": 24,    # 3 days
        }
        # Mark Nov 20 as holiday
        holidays = {datetime(2025, 11, 20)}
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        backend_start = result["Backend"]["start"]
        backend_end = result["Backend"]["end"]
        
        # Verify the holiday is not used as start date
        self.assertNotEqual(backend_start.date(), datetime(2025, 11, 20).date())
        
        # Verify end date is on or before deadline
        self.assertLessEqual(backend_end, feature_deadline)
        
        # The main point: holiday should be skipped, meaning the start date
        # should be pushed back to accommodate the holiday
        # If Nov 20 is a holiday, and we need 3 working days ending Nov 25,
        # we should start earlier to account for the skipped day

    def test_parse_department_deps_multiple_blockers_same_target(self):
        """Test parsing when multiple departments block the same target."""
        deps_str = "UI/UX blocks Frontend, Backend blocks Frontend"
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        # Frontend should have both blockers in the list
        self.assertIn("Frontend", result)
        self.assertEqual(len(result["Frontend"]), 2)
        self.assertIn("UI/UX", result["Frontend"])
        self.assertIn("Backend", result["Frontend"])

    def test_parse_department_deps_whitespace_handling(self):
        """Test that extra whitespace is handled correctly."""
        deps_str = "  UI/UX  blocks   Frontend  ,  Backend  blocks  AI  "
        result = DepartmentDependencyCalculator.parse_department_deps(deps_str)
        
        self.assertEqual(result, {
            "Frontend": ["UI/UX"],
            "AI": ["Backend"]
        })

    def test_calculate_department_deadlines_no_dependencies(self):
        """Test calculation with no dependencies (all independent work)."""
        feature_deadline = datetime(2025, 11, 25, 23, 59, 59)
        dept_deps = {}
        department_hours = {
            "Backend": 16,
            "Frontend": 16,
            "UI/UX": 16,
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # All departments should be scheduled
        self.assertEqual(len(result), 3)
        
        # All should end on or before the deadline
        for dept in result:
            self.assertLessEqual(result[dept]["end"], feature_deadline)

    def test_calculate_department_deadlines_complex_chain(self):
        """Test the exact scenario from user's bug report.
        
        Dependencies: UI/UX blocks Frontend, Backend blocks Frontend, AI blocks Backend
        This means: AI → Backend → Frontend, UI/UX → Frontend
        """
        feature_deadline = datetime(2025, 11, 16, 23, 59, 59)
        dept_deps = {
            "Frontend": ["UI/UX", "Backend"],
            "Backend": ["AI"]
        }
        department_hours = {
            "UI/UX": 16,      # 2 days
            "AI": 40,         # 5 days
            "Backend": 8,     # 1 day
            "Frontend": 8,    # 1 day
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays
        )
        
        # Verify all scheduled
        self.assertEqual(len(result), 4)
        
        # Extract dates
        ai_start = result["AI"]["start"]
        ai_end = result["AI"]["end"]
        ui_ux_start = result["UI/UX"]["start"]
        ui_ux_end = result["UI/UX"]["end"]
        backend_start = result["Backend"]["start"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        frontend_end = result["Frontend"]["end"]
        
        # Verify start <= end for all departments (no impossible dates!)
        self.assertLessEqual(ai_start, ai_end, "AI start must be <= end")
        self.assertLessEqual(ui_ux_start, ui_ux_end, "UI/UX start must be <= end")
        self.assertLessEqual(backend_start, backend_end, "Backend start must be <= end")
        self.assertLessEqual(frontend_start, frontend_end, "Frontend start must be <= end")
        
        # Verify dependency order
        # Backend must start after AI ends
        self.assertGreater(backend_start, ai_end, "Backend must start after AI completes")
        
        # Frontend must start after BOTH UI/UX and Backend complete
        self.assertGreater(frontend_start, ui_ux_end, "Frontend must start after UI/UX completes")
        self.assertGreater(frontend_start, backend_end, "Frontend must start after Backend completes")
        
        # All must complete by deadline
        self.assertLessEqual(frontend_end, feature_deadline, "Frontend must complete by deadline")

    def test_calculate_department_deadlines_with_implementation_start_date(self):
        """Test that departments respect implementation_start_date.
        
        Scenario from bug report: implementation starts Nov 3, but tasks were
        starting on Nov 2.
        """
        feature_deadline = datetime(2025, 11, 8, 23, 59, 59)
        implementation_start_date = datetime(2025, 11, 3, 0, 0)
        dept_deps = {
            "Frontend": ["UI/UX", "Backend"],
            "Backend": ["AI"]
        }
        department_hours = {
            "UI/UX": 8,   # 1 day
            "AI": 32,     # 4 days
            "Backend": 8, # 1 day
            "Frontend": 8,# 1 day
        }
        holidays = set()
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline, dept_deps, department_hours, holidays, implementation_start_date
        )
        
        # All departments should be scheduled
        self.assertEqual(len(result), 4)
        
        # NO department should start before implementation_start_date
        for dept, dates in result.items():
            self.assertGreaterEqual(
                dates["start"], 
                implementation_start_date,
                f"{dept} starts before implementation_start_date"
            )
        
        # Verify dependencies are still respected
        ai_end = result["AI"]["end"]
        backend_start = result["Backend"]["start"]
        ui_ux_end = result["UI/UX"]["end"]
        backend_end = result["Backend"]["end"]
        frontend_start = result["Frontend"]["start"]
        
        self.assertGreater(backend_start, ai_end, "Backend must start after AI")
        self.assertGreater(frontend_start, ui_ux_end, "Frontend must start after UI/UX")
        self.assertGreater(frontend_start, backend_end, "Frontend must start after Backend")

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

    def test_calculate_daily_capacity_6_workdays(self):
        """Test daily capacity calculation with 6 workdays per week (Friday holiday)."""
        # Week starting Sunday with Friday as holiday
        start_date = datetime(2025, 11, 2)  # Sunday
        end_date = datetime(2025, 11, 8)    # Saturday
        holidays = set()
        weekly_capacity = 28.0
        
        # Calculate daily capacity
        daily_capacity = DepartmentDependencyCalculator.calculate_daily_capacity(
            weekly_capacity, start_date, end_date, holidays
        )
        
        # Should be 28/6 = 4.666... hours per day
        self.assertAlmostEqual(daily_capacity, 4.666666666666667, places=5)

    def test_calculate_daily_capacity_5_workdays(self):
        """Test daily capacity calculation with 5 workdays (Thursday and Friday holidays)."""
        # Week with Thursday and Friday as holidays
        start_date = datetime(2025, 11, 2)  # Sunday
        end_date = datetime(2025, 11, 8)    # Saturday
        # Add Thursday Nov 6 as additional holiday
        holidays = {datetime(2025, 11, 6).date()}
        weekly_capacity = 40.0
        
        daily_capacity = DepartmentDependencyCalculator.calculate_daily_capacity(
            weekly_capacity, start_date, end_date, holidays
        )
        
        # Should be 40/5 = 8.0 hours per day
        self.assertAlmostEqual(daily_capacity, 8.0, places=5)

    def test_calculate_department_deadlines_with_daily_capacity(self):
        """Test department deadlines with custom daily capacity per department."""
        # Scenario: Mousavi has only 28 hours per week for AI department
        # With 6 workdays per week, that's 28/6 = 4.67 hours per day
        # 16 hours of work should take 16/4.67 = 3.43 days, so 4 workdays
        
        feature_deadline = datetime(2025, 11, 10)  # Monday
        implementation_start = datetime(2025, 11, 3)  # Monday
        
        department_deps = {}  # No dependencies
        department_hours = {"AI": 16}  # 16 hours of work
        holidays = set()
        
        # AI department has 28h/week = 4.67h/day capacity
        department_daily_capacity = {"AI": 4.666666666666667}
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline=feature_deadline,
            department_deps=department_deps,
            department_hours=department_hours,
            holidays=holidays,
            implementation_start_date=implementation_start,
            department_daily_capacity=department_daily_capacity,
        )
        
        # With 4.67h/day, 16 hours needs ceil(16/4.67) = 4 workdays
        # Start: Mon Nov 3, End: Thu Nov 6 (skipping Friday Nov 7)
        self.assertIn("AI", result)
        self.assertEqual(result["AI"]["start"].date(), datetime(2025, 11, 3).date())
        # 16 hours / 4.67 hours per day = 3.43 days -> need 4 workdays (Mon, Tue, Wed, Thu)
        self.assertEqual(result["AI"]["end"].date(), datetime(2025, 11, 6).date())

    def test_calculate_department_deadlines_mixed_daily_capacity(self):
        """Test with multiple departments having different daily capacities."""
        feature_deadline = datetime(2025, 11, 15)  # Saturday
        implementation_start = datetime(2025, 11, 3)  # Monday
        
        # UI/UX blocks Frontend
        department_deps = {"Frontend": ["UI/UX"]}
        department_hours = {
            "UI/UX": 42,    # 42 hours
            "Frontend": 36,  # 36 hours
        }
        holidays = set()
        
        # Different daily capacities
        department_daily_capacity = {
            "UI/UX": 7.0,      # 42h/week, 6 workdays = 7h/day
            "Frontend": 6.0,   # 36h/week, 6 workdays = 6h/day
        }
        
        result = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature_deadline=feature_deadline,
            department_deps=department_deps,
            department_hours=department_hours,
            holidays=holidays,
            implementation_start_date=implementation_start,
            department_daily_capacity=department_daily_capacity,
        )
        
        # UI/UX: 42h / 7h/day = 6 workdays (Mon Nov 3 to Mon Nov 10, skipping Fridays)
        # Frontend: starts after UI/UX ends, 36h / 6h/day = 6 workdays
        self.assertIn("UI/UX", result)
        self.assertIn("Frontend", result)
        
        # Verify Frontend starts after UI/UX ends
        uiux_end = result["UI/UX"]["end"]
        frontend_start = result["Frontend"]["start"]
        self.assertGreater(frontend_start, uiux_end)


if __name__ == "__main__":
    unittest.main()
