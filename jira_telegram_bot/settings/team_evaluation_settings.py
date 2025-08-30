"""Team evaluation settings."""

from typing import Dict, Tuple, Literal
from pydantic_settings import BaseSettings

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.entities.constants import (
    DEFAULT_WEEKLY_HOURS,
    DEFAULT_WORKDAYS,
    DEFAULT_TIMEZONE,
    DEFAULT_DEFECT_THRESHOLDS,
    EXPECTED_HOURS_WEEKLY,
    DEPT_INFERENCE_COMPONENT
)


class TeamEvaluationSettings(BaseSettings):
    """Settings for team evaluation functionality."""
    
    sheet_id: str
    tab_name: str = "Team Evaluation"
    weekly_hours: float = DEFAULT_WEEKLY_HOURS
    workdays: Tuple[int, ...] = DEFAULT_WORKDAYS
    expected_hours_mode: Literal["weekly", "total"] = EXPECTED_HOURS_WEEKLY
    dept_inference: Literal["component", "label", "user_config"] = DEPT_INFERENCE_COMPONENT
    timezone: str = DEFAULT_TIMEZONE
    score_weights: TeamEvaluationScoreWeights = TeamEvaluationScoreWeights()
    defect_thresholds: Dict = DEFAULT_DEFECT_THRESHOLDS
    dry_run: bool = False

    class Config:
        """Pydantic config."""
        env_prefix = "TEAM_EVALUATION_"
