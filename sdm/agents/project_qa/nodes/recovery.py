"""Шаг дополнительного поиска и выбор следующего шага графа."""

from __future__ import annotations

from time import monotonic
from typing import Literal
from uuid import uuid4

from langchain_core.messages import AIMessage

from sdm.agents.budget import MIN_RECOVERY_BUDGET_SECONDS
from sdm.agents.streaming import emit_stream_event, streamed_stage

from ..recovery import recovery_calls
from ..state import ProjectQuestionState


def route_after_review(state: ProjectQuestionState) -> Literal["recover", "finalize"]:
    if not recovery_calls(state):
        return "finalize"
    deadline = state.get("request_deadline")
    if deadline is not None:
        remaining = max(0.0, deadline - monotonic())
        if remaining < MIN_RECOVERY_BUDGET_SECONDS:
            emit_stream_event(
                "recovery_skipped",
                reason="time_budget",
                remaining_seconds=round(remaining, 1),
                required_seconds=MIN_RECOVERY_BUDGET_SECONDS,
            )
            return "finalize"
    return "recover"


def request_evidence_recovery(state: ProjectQuestionState) -> ProjectQuestionState:
    with streamed_stage("recover_evidence"):
        calls = recovery_calls(state)
        if not calls:
            raise ValueError("Recovery was scheduled without an eligible evidence request")
        round_number = state.get("recovery_rounds", 0) + 1
        emit_stream_event(
            "evidence_recovery",
            round=round_number,
            queries=[call["args"]["query"] for call in calls if "query" in call["args"]],
            context_source_ids=[
                call["args"]["evidence_id"] for call in calls if "evidence_id" in call["args"]
            ],
        )
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{**call, "id": f"recovery_{uuid4().hex}"} for call in calls],
                )
            ],
            "recovery_rounds": round_number,
        }
