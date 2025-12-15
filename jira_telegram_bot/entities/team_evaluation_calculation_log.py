"""Team evaluation calculation log entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TeamEvaluationCalculationLog:
    """Detailed log of team evaluation score calculation.

    Tracks every metric and calculation step for transparency and audit purposes.
    """

    sprint_id: int
    sprint_name: str
    developer_name: str
    department: str
    project: str
    calculation_type: str
    metric_name: str
    metric_value: float
    calculation_formula: str
    calculation_details: str
    weight: Optional[float] = None
    contribution_to_total: Optional[float] = None
    timestamp: Optional[datetime] = None
    evaluation_id: Optional[int] = None
