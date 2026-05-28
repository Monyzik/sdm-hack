"""Сборка проверенного ответа и проверка итогового API-контракта."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from sdm.agents.text import unique
from sdm.agents.tools.sources import MAX_EVIDENCE_SOURCES

from .evidence.models import AnswerVerification
from .evidence.validation import supported_claims, validate_review
from .schemas import PROJECT_DATA_UNAVAILABLE_ANSWER, ProjectQuestionAnswer
from .state import ProjectQuestionState

INSUFFICIENT_EVIDENCE_ANSWER = (
    "В полученных источниках недостаточно подтверждений для ответа на этот вопрос."
)
VERIFICATION_UNAVAILABLE_ANSWER = (
    "Не удалось завершить проверку подтверждений. Повторите запрос позже."
)
PARTIAL_ANSWER_NOTE = (
    "По остальным частям вопроса подтверждений недостаточно; "
    "неподтверждённые утверждения не включены в ответ."
)


def render_verified_answer(state: ProjectQuestionState) -> ProjectQuestionAnswer:
    """Публикует проверенные утверждения без последующего переписывания моделью."""
    tools = state.get("used_tools", [])
    rounds = state.get("recovery_rounds", 0)
    if state.get("evidence_unavailable") or state.get("verification_failed"):
        return ProjectQuestionAnswer(
            answer=(
                PROJECT_DATA_UNAVAILABLE_ANSWER
                if state.get("evidence_unavailable")
                else VERIFICATION_UNAVAILABLE_ANSWER
            ),
            used_tools=tools,
            verification=AnswerVerification(
                status="unavailable", checked_claims=0, supported_claims=0, recovery_rounds=rounds
            ),
        )
    draft = state.get("answer_draft")
    review = state.get("evidence_review")
    if draft is None or review is None:
        raise ValueError("Project answer cannot bypass claim verification")
    # Повторяем проверку перед публикацией, чтобы её нельзя было обойти.
    review = validate_review(review, draft, state.get("tool_sources", []))
    claims = supported_claims(draft, review)
    complete = bool(claims) and (len(claims) == len(draft.claims) and not review.missing_aspects)
    status = "passed" if complete else "partial" if claims else "abstained"
    if claims:
        text = (
            claims[0].text
            if len(claims) == 1
            else "\n\n".join(f"- {claim.text}" for claim in claims)
        )
        if not complete:
            text += "\n\n" + PARTIAL_ANSWER_NOTE
    else:
        text = INSUFFICIENT_EVIDENCE_ANSWER
    return ProjectQuestionAnswer(
        answer=text,
        evidence_ids=list(
            dict.fromkeys(source for claim in claims for source in claim.evidence_ids)
        ),
        used_tools=tools,
        claims=claims,
        verification=AnswerVerification(
            status=status,
            checked_claims=len(draft.claims),
            supported_claims=len(claims),
            recovery_rounds=rounds,
        ),
    )


def _parse_agent_answer(
    content: str,
    used_tools: list[str],
    *,
    needs_project_tools: bool = True,
    tool_sources: list[dict[str, Any]] | None = None,
) -> ProjectQuestionAnswer:
    actual_tools = unique(used_tools)
    if needs_project_tools and not actual_tools:
        raise ValueError("Q&A-агент ответил по проектному вопросу без вызова инструментов.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Модель вернула невалидный JSON для Q&A.") from error
    try:
        answer = ProjectQuestionAnswer.model_validate(payload)
    except ValidationError as error:
        raise ValueError("Модель вернула JSON не по контракту ProjectQuestionAnswer.") from error

    answer.answer = answer.answer.strip()
    answer.used_tools = actual_tools
    known_ids = {
        str(value).strip().casefold()
        for source in tool_sources or []
        for value in [source.get("id"), *source.get("_match_keys", [])]
        if value
    }
    evidence_ids = unique(answer.evidence_ids)
    if len(evidence_ids) > MAX_EVIDENCE_SOURCES:
        raise ValueError(f"Q&A evidence exceeds limit {MAX_EVIDENCE_SOURCES}.")
    answer.evidence_ids = [value for value in evidence_ids if value.strip().casefold() in known_ids]
    if needs_project_tools:
        fixed_abstention = (
            not answer.claims
            and not answer.evidence_ids
            and answer.verification is not None
            and answer.verification.status in {"abstained", "unavailable"}
            and answer.answer
            in {
                INSUFFICIENT_EVIDENCE_ANSWER,
                VERIFICATION_UNAVAILABLE_ANSWER,
                PROJECT_DATA_UNAVAILABLE_ANSWER,
            }
        )
        if tool_sources and not answer.evidence_ids and not fixed_abstention:
            raise ValueError("Q&A-агент не указал ни одного подтверждённого источника.")
        if (
            not tool_sources
            and answer.answer != PROJECT_DATA_UNAVAILABLE_ANSWER
            and not fixed_abstention
        ):
            raise ValueError("Q&A-агент сформировал проектный ответ без подтверждённых источников.")
    answer.suggested_questions = unique(
        [question.strip() for question in answer.suggested_questions]
    )[:4]
    if not needs_project_tools:
        answer.evidence_ids = []
        answer.used_tools = []
        answer.suggested_questions = []
        answer.claims = []
        answer.verification = None
    return answer
