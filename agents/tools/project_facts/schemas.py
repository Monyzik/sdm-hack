from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL_ARGUMENT_ALIASES = {
    "assignee_in": "assignee",
    "criticality_in": "criticality",
    "limit_in": "limit",
    "min_score_gte": "min_score",
    "owner_in": "owner",
    "priority_in": "priority",
    "status_in": "status",
    "team_in": "team",
}


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_arguments(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        for source, target in TOOL_ARGUMENT_ALIASES.items():
            if target in normalized or source not in normalized:
                continue
            normalized[target] = _first_argument_value(normalized[source])
        return normalized


class NoArgs(ToolArgsModel):
    pass


class ProblemContextArgs(ToolArgsModel):
    max_depth: int | None = Field(default=None, ge=1, le=4)


class CriticalTasksArgs(ToolArgsModel):
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchTasksArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchRisksArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=25)
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchCommunicationsArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    team: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDecisionsArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    owner: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDependenciesArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    criticality: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class EvidenceSearchArgs(ToolArgsModel):
    query: str = Field(min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, max_length=64)
    limit: int | None = Field(default=None, ge=1, le=20)


class CalculateDelayCostArgs(ToolArgsModel):
    delay_days: int = Field(ge=0, le=365)
    include_resource_burn: bool = True


def _first_argument_value(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            if item is not None and item != "":
                return item
        return None
    return value
