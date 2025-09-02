"""Team evaluation settings."""

from typing import Dict, Tuple, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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

    sheet_id: str = Field(...)
    tab_name: str = Field("Team Evaluation")
    weekly_hours: float = Field(default=DEFAULT_WEEKLY_HOURS)
    workdays: Tuple[int, ...] = Field(default=DEFAULT_WORKDAYS)
    expected_hours_mode: Literal["weekly", "total"] = Field(default=EXPECTED_HOURS_WEEKLY)
    dept_inference: Literal["component", "label", "user_config"] = Field(default=DEPT_INFERENCE_COMPONENT)
    timezone: str = Field(default=DEFAULT_TIMEZONE)
    score_weights: TeamEvaluationScoreWeights = Field(default=TeamEvaluationScoreWeights())
    defect_thresholds: Dict = Field(default=DEFAULT_DEFECT_THRESHOLDS)
    dry_run: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TEAM_EVALUATION_",
        extra="ignore",
        case_sensitive=False
    )