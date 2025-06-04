from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from jira import Issue  # type: ignore
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"


@dataclass
class SubtaskReport:
    key: str
    title: str
    assignee: Optional[str]
    status: str
    description: str
    moved_to_in_progress: Optional[str] = None
    moved_to_reviewed: Optional[str] = None
    moved_to_done: Optional[str] = None

    @classmethod
    def from_issue(cls, issue: Issue, status_dates: Dict[str, Optional[str]]) -> "SubtaskReport":
        return cls(
            key=issue.key,
            title=issue.fields.summary,
            assignee=getattr(issue.fields.assignee, "displayName", None),
            status=issue.fields.status.name,
            description=_first_n_words(issue.fields.description or "", 120),
            moved_to_in_progress=status_dates.get("In Progress"),
            moved_to_reviewed=status_dates.get("Review"),
            moved_to_done=status_dates.get("Done"),
        )


@dataclass
class StoryReport:
    key: str
    title: str
    description: str
    status: str
    time_tracking: Dict[str, float]
    remaining_time: float
    subtasks: List[SubtaskReport] = field(default_factory=list)
    comments: Dict[str, List[str]] = field(default_factory=dict)


class JiraTaskReportGenerator:
    """Builds a JSON report of Jira stories according to the given filters.

    Parameters
    ----------
    repo : JiraServerRepository
        An instance connected to the Jira Server.
    """

    def __init__(self, repo: "JiraServerRepository") -> None:
        self.repo = repo

    def __call__(
        self,
        *,
        project: str,
        start_date: str,
        end_date: str,
        sprint_name: Optional[str] = None,
    ) -> Dict[str, StoryReport]:
        """Return a JSON‑serialisable structure of stories matching the filters.

        Parameters
        ----------
        project : str
            Project key (e.g., "ABC").
        start_date : str
            ISO date (YYYY‑MM‑DD) – inclusive lower bound for worklogs / comments.
        end_date : str
            ISO date (YYYY‑MM‑DD) – inclusive upper bound for worklogs / comments.
        sprint_name : str, optional
            Exact sprint name to match.
        """
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        jql = [f'project = "{project}"', "issuetype = Story"]
        if sprint_name:
            jql.append(f'Sprint = "{sprint_name}"')
        query = " AND ".join(jql)
        query = f'project = "{project}" AND status in (Review, Done, "In Progress") AND updated >= -72h AND issuetype in (Story, Task, Sub-task, Bug)'


        print(f"getting stories for JQL: {query}")

        stories = self.repo.search_for_issues(query)
        report: Dict[str, StoryReport] = {}

        for story in stories:
            full_story = self.repo.jira.issue(
                story.key, expand="worklog,changelog,comments,subtasks"
            )

            # Build subtask reports and accumulate tracking
            user_hours: Dict[str, float] = defaultdict(float)
            original_estimate_seconds = (
                full_story.fields.timeoriginalestimate or 0
            )
            spent_seconds = self._collect_worklog_hours(
                full_story, start_dt, end_dt, user_hours
            )
            subtasks_reports: List[SubtaskReport] = []

            for sub_ref in full_story.fields.subtasks or []:
                sub_issue = self.repo.jira.issue(
                    sub_ref.key, expand="worklog,changelog"
                )
                original_estimate_seconds += (
                    sub_issue.fields.timeoriginalestimate or 0
                )
                spent_seconds += self._collect_worklog_hours(
                    sub_issue, start_dt, end_dt, user_hours
                )
                status_dates = _status_change_dates(sub_issue)
                subtasks_reports.append(SubtaskReport.from_issue(sub_issue, status_dates))

            remaining_hours = (
                original_estimate_seconds - spent_seconds
            ) / 3600.0

            comments = _comments_by_author(full_story, start_dt, end_dt)

            report[full_story.key] = StoryReport(
                key=full_story.key,
                title=full_story.fields.summary,
                description=_first_n_words(full_story.fields.description or "", 120),
                status=full_story.fields.status.name,
                time_tracking=dict(user_hours),
                remaining_time=round(remaining_hours, 2),
                subtasks=subtasks_reports,
                comments=comments,
            )

        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _collect_worklog_hours(
        self,
        issue: Issue,
        start_dt: datetime,
        end_dt: datetime,
        user_hours: Dict[str, float],
    ) -> int:
        """Accumulate worklog seconds into *user_hours* and return seconds spent."""
        spent = 0
        for wl in issue.fields.worklog.worklogs:  # type: ignore
            wl_dt = datetime.strptime(wl.started, ISO_FMT).replace(tzinfo=None)
            if start_dt <= wl_dt and wl_dt <= end_dt:
                seconds = wl.timeSpentSeconds  # type: ignore
                spent += seconds
                author = wl.author.displayName  # type: ignore
                user_hours[author] += seconds / 3600.0
        return spent


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def _first_n_words(text: str, n: int) -> str:
    words = text.split()
    return " ".join(words[:n])


def _status_change_dates(issue: Issue) -> Dict[str, Optional[str]]:
    """Return mapping from status name to first date it was set (YYYY‑MM‑DD)."""
    dates: Dict[str, str] = {}
    for history in getattr(issue, "changelog").histories:
        for item in history.items:
            if item.field == "status":
                to_status = item.toString
                if to_status not in dates:
                    dates[to_status] = history.created[:10]
    return dates


def _comments_by_author(issue: Issue, start_dt: datetime, end_dt: datetime) -> Dict[str, List[str]]:
    comments_by_user: Dict[str, List[str]] = defaultdict(list)
    for c in issue.fields.comment.comments:  # type: ignore
        c_dt = datetime.fromisoformat(c.created[:-5])  # strip timezone
        if start_dt <= c_dt <= end_dt:
            author = c.author.displayName  # type: ignore
            comments_by_user[author].append(c.body)
    return comments_by_user


# ----------------------------------------------------------------------
# Convenience wrapper for JSON serialisation
# ----------------------------------------------------------------------

def generate_report_json(
    repo: "JiraServerRepository",
    project: str,
    start_date: str,
    end_date: str,
    sprint_name: Optional[str] = None,
    **dumps_kwargs,
) -> str:
    """Utility for one‑liner JSON generation."""
    generator = JiraTaskReportGenerator(repo)
    report = generator(
        project=project,
        start_date=start_date,
        end_date=end_date,
        sprint_name=sprint_name,
    )
    return json.dumps({k: r.__dict__ for k, r in report.items()}, default=lambda o: o.__dict__, **dumps_kwargs)



if __name__ == "__main__":
    # Example usage
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(hours=90)
    from jira_telegram_bot.app_container import get_container
    container = get_container()
    repo = container[JiraServerRepository]

    report_json = generate_report_json(
        repo=repo,
        project="PARSCHAT",
        start_date=start_dt.strftime("%Y-%m-%d"),  # e.g. "2025-05-24"
        end_date=end_dt.strftime("%Y-%m-%d"),      # e.g. "2025-05-28"
        # sprint_name="185",
        indent=2,                                  # pretty print
    )
    # Save the report JSON to a file
    output_filename = f"jira_report_{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}.json"
    with open(output_filename, "w") as f:
        f.write(report_json)
    print(f"Report saved to {output_filename}")
    print(report_json)