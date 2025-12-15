"""Helper for creating detailed calculation logs."""
from typing import List
from datetime import datetime

from jira_telegram_bot.entities.team_evaluation_calculation_log import TeamEvaluationCalculationLog


class CalculationLogger:
    """Helper class to create detailed calculation logs for team evaluation."""

    @staticmethod
    def log_task_classification(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        dev_count: int,
        bug_count: int,
        support_count: int,
        high_priority_count: int,
        total_issues: int
    ) -> List[TeamEvaluationCalculationLog]:
        """Log task classification metrics.
        
        Returns:
            List of calculation log entries for task counts
        """
        logs = []
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="development_task_count",
            metric_value=float(dev_count),
            calculation_formula="COUNT(issues WHERE type IN development_types)",
            calculation_details=f"Counted {dev_count} development tasks out of {total_issues} total issues assigned. Development types include Story, Task, etc.",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="bug_task_count",
            metric_value=float(bug_count),
            calculation_formula="COUNT(issues WHERE type = 'Bug')",
            calculation_details=f"Counted {bug_count} bug tasks out of {total_issues} total issues assigned.",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="support_task_count",
            metric_value=float(support_count),
            calculation_formula="COUNT(issues WHERE type IN support_types)",
            calculation_details=f"Counted {support_count} support tasks out of {total_issues} total issues assigned. Support includes Sub-task, Support Request, etc.",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="high_priority_count",
            metric_value=float(high_priority_count),
            calculation_formula="COUNT(issues WHERE priority IN ['Highest', 'High'])",
            calculation_details=f"Counted {high_priority_count} high/highest priority tasks out of {total_issues} total issues.",
            timestamp=datetime.utcnow()
        ))
        
        return logs

    @staticmethod
    def log_time_metrics(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        total_hours: float,
        expected_hours: float,
        dev_hours: float,
        bug_hours: float,
        support_hours: float,
        worklog_count: int,
        filtered_count: int
    ) -> List[TeamEvaluationCalculationLog]:
        """Log time tracking metrics.
        
        Returns:
            List of calculation log entries for time metrics
        """
        logs = []
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="registered_hours_total",
            metric_value=total_hours,
            calculation_formula="SUM(worklogs.hours WHERE worklog.date IN sprint_range)",
            calculation_details=f"Summed {total_hours:.1f} hours from {worklog_count} worklogs within sprint date range. {filtered_count} worklogs outside sprint range were excluded.",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="expected_hours_week",
            metric_value=expected_hours,
            calculation_formula="workdays_in_week * daily_hours - leave_hours",
            calculation_details=f"Expected hours calculated as {expected_hours:.1f} based on work calendar, considering workdays and any leave taken.",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="development_hours",
            metric_value=dev_hours,
            calculation_formula="SUM(worklogs.hours WHERE issue.type IN development_types)",
            calculation_details=f"Development tasks consumed {dev_hours:.1f} hours out of {total_hours:.1f} total hours ({(dev_hours/total_hours*100 if total_hours > 0 else 0):.1f}%).",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="bug_hours",
            metric_value=bug_hours,
            calculation_formula="SUM(worklogs.hours WHERE issue.type = 'Bug')",
            calculation_details=f"Bug fixes consumed {bug_hours:.1f} hours out of {total_hours:.1f} total hours ({(bug_hours/total_hours*100 if total_hours > 0 else 0):.1f}%).",
            timestamp=datetime.utcnow()
        ))
        
        logs.append(TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="metric",
            metric_name="support_hours",
            metric_value=support_hours,
            calculation_formula="SUM(worklogs.hours WHERE issue.type IN support_types)",
            calculation_details=f"Support tasks consumed {support_hours:.1f} hours out of {total_hours:.1f} total hours ({(support_hours/total_hours*100 if total_hours > 0 else 0):.1f}%).",
            timestamp=datetime.utcnow()
        ))
        
        return logs

    @staticmethod
    def log_deadline_score(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        deadline_penalty: float,
        deadline_score: float,
        tasks_with_deadlines: int,
        avg_delta_days: float,
        weight: float
    ) -> TeamEvaluationCalculationLog:
        """Log deadline performance score calculation.
        
        Returns:
            Calculation log entry for deadline score
        """
        details = (
            f"Deadline score: Started with 100, subtracted penalty of {deadline_penalty:.2f}. "
            f"Final deadline component score: {deadline_score:.2f}. "
            f"Based on {tasks_with_deadlines} tasks with deadlines. "
            f"Average deadline delta: {avg_delta_days:.1f} days. "
            f"Weighted contribution: {deadline_score * weight:.2f}"
        )
        
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="score_component",
            metric_name="deadline_score",
            metric_value=deadline_score,
            calculation_formula="max(0, 100 - per_task_deadline_penalties)",
            calculation_details=details,
            weight=weight,
            contribution_to_total=deadline_score * weight,
            timestamp=datetime.utcnow()
        )

    @staticmethod
    def log_worklog_score(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        registered_hours: float,
        expected_hours: float,
        worklog_score: float,
        weight: float
    ) -> TeamEvaluationCalculationLog:
        """Log worklog score calculation.
        
        Returns:
            Calculation log entry for worklog score
        """
        ratio = min(registered_hours / expected_hours, 1.0) if expected_hours > 0 else (1.0 if registered_hours > 0 else 0.0)
        
        details = (
            f"Worklog score: Registered {registered_hours:.1f} hours vs Expected {expected_hours:.1f} hours. "
            f"Ratio: {ratio:.2f} (capped at 1.0). "
            f"Score: {worklog_score:.2f}. "
            f"Weighted contribution: {worklog_score * weight:.2f}"
        )
        
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="score_component",
            metric_name="worklog_score",
            metric_value=worklog_score,
            calculation_formula="min(registered_hours / expected_hours, 1.0) * 100",
            calculation_details=details,
            weight=weight,
            contribution_to_total=worklog_score * weight,
            timestamp=datetime.utcnow()
        )

    @staticmethod
    def log_high_priority_score(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        required_tasks: int,
        completed_required: int,
        high_priority_score: float,
        weight: float
    ) -> TeamEvaluationCalculationLog:
        """Log high priority task completion score.
        
        Returns:
            Calculation log entry for high priority score
        """
        completion_ratio = completed_required / required_tasks if required_tasks > 0 else 0.0
        
        details = (
            f"High Priority Score: Completed {completed_required} out of {required_tasks} required tasks (50% of capacity). "
            f"Completion ratio: {completion_ratio:.2f}. "
            f"Score: {high_priority_score:.2f}. "
            f"Weighted contribution: {high_priority_score * weight:.2f}"
        )
        
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="score_component",
            metric_name="high_priority_score",
            metric_value=high_priority_score,
            calculation_formula="(completed_required / required_tasks) * 100",
            calculation_details=details,
            weight=weight,
            contribution_to_total=high_priority_score * weight,
            timestamp=datetime.utcnow()
        )

    @staticmethod
    def log_defect_score(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        support_bugs_per_story: float,
        tester_bugs_per_story: float,
        defect_score: float,
        weight: float,
        support_threshold: float,
        tester_threshold: float
    ) -> TeamEvaluationCalculationLog:
        """Log defect quality score calculation.
        
        Returns:
            Calculation log entry for defect score
        """
        support_penalty = (support_bugs_per_story / support_threshold) * 30
        tester_penalty = (tester_bugs_per_story / tester_threshold) * 30
        total_penalty = min(support_penalty + tester_penalty, 60)
        
        details = (
            f"Defect Score: Support bugs/story: {support_bugs_per_story:.2f} (threshold: {support_threshold}), "
            f"Tester bugs/story: {tester_bugs_per_story:.2f} (threshold: {tester_threshold}). "
            f"Support penalty: {support_penalty:.2f}, Tester penalty: {tester_penalty:.2f}. "
            f"Total penalty: {total_penalty:.2f} (max 60). "
            f"Score: {defect_score:.2f}. "
            f"Weighted contribution: {defect_score * weight:.2f}"
        )
        
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="score_component",
            metric_name="defect_score",
            metric_value=defect_score,
            calculation_formula="100 - min((support_penalty + tester_penalty), 60)",
            calculation_details=details,
            weight=weight,
            contribution_to_total=defect_score * weight,
            timestamp=datetime.utcnow()
        )

    @staticmethod
    def log_final_score(
        sprint_id: int,
        sprint_name: str,
        developer: str,
        department: str,
        project: str,
        composite_score: float,
        penalties_applied: float,
        bonuses_applied: float,
        final_score: int
    ) -> TeamEvaluationCalculationLog:
        """Log final composite score calculation.
        
        Returns:
            Calculation log entry for final score
        """
        details = (
            f"Final Score Calculation: Composite score before penalties/bonuses: {composite_score:.2f}. "
            f"Penalties applied: {penalties_applied:.2f}. "
            f"Bonuses applied: {bonuses_applied:.2f}. "
            f"Final score (rounded, capped between -50 and 100+bonuses): {final_score}"
        )
        
        return TeamEvaluationCalculationLog(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            developer_name=developer,
            department=department,
            project=project,
            calculation_type="final_score",
            metric_name="quality_score_total",
            metric_value=float(final_score),
            calculation_formula="max(-50, round(weighted_sum - penalties + bonuses))",
            calculation_details=details,
            timestamp=datetime.utcnow()
        )
