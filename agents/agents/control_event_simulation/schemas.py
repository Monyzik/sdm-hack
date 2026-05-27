from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SimulationStageStatus = Literal["pending", "running", "success", "error"]
SimulationJobStatus = Literal["queued", "running", "completed", "failed"]


class SimulationStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    detail: str | None = None
    status: SimulationStageStatus
    timestamp: datetime


class SimulationEventResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    event_label: str
    project_id: str | None = None
    notification_id: str | None = None
    error: str | None = None


class SimulationJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: SimulationJobStatus
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    stages: list[SimulationStage]
    results: list[SimulationEventResult]
    output_file: str | None = None
    error: str | None = None


class SimulationClearResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_notifications: int
    output_file_removed: bool
