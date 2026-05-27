from __future__ import annotations

import re
from typing import Any

from agents.core.text import humanize_agent_text

from .schemas import ProjectManagerBrief

TECHNICAL_ID_RE = re.compile(r"\b(?:T|TD|RK|C|D|DEC|CR|R|Р)\d{3}\b")


def clean_brief(brief: ProjectManagerBrief, problem_context: dict[str, Any]) -> ProjectManagerBrief:
    replacements = _build_id_replacements(problem_context)
    risk_level = problem_context.get("metrics", {}).get("risk_level")
    if risk_level == "red":
        brief.status = "критично"
    elif risk_level == "yellow":
        brief.status = "под наблюдением"
    elif risk_level == "green":
        brief.status = "в норме"

    brief.headline = _limit_text(_clean_text_value(brief.headline, replacements), 160)
    brief.management_question = _limit_text(_clean_text_value(brief.management_question, replacements), 260)
    brief.diagnosis = _limit_text(_clean_text_value(brief.diagnosis, replacements), 560)
    brief.bottleneck = _limit_text(_clean_text_value(brief.bottleneck, replacements), 260)
    brief.critical_path = [_limit_text(_clean_text_value(item, replacements), 180) for item in brief.critical_path]
    brief.recommended_move = _limit_text(_clean_text_value(brief.recommended_move, replacements), 360)
    brief.watchouts = [_limit_text(_clean_text_value(item, replacements), 220) for item in brief.watchouts]
    brief.business_impact.impact_summary = _limit_text(
        _clean_text_value(brief.business_impact.impact_summary, replacements),
        260,
    )
    for action in brief.next_actions:
        action.action = _limit_text(_clean_text_value(action.action, replacements), 220)
        action.owner_hint = _limit_text(_clean_text_value(action.owner_hint, replacements), 160)
        action.deadline = _limit_text(_clean_text_value(action.deadline, replacements), 120)
        action.success_signal = _limit_text(_clean_text_value(action.success_signal, replacements), 220)
    brief.draft_message.recipient_hint = _limit_text(
        _clean_text_value(brief.draft_message.recipient_hint, replacements),
        160,
    )
    brief.draft_message.subject = _limit_text(
        _clean_text_value(brief.draft_message.subject, replacements),
        160,
    )
    brief.draft_message.body = _limit_text(_clean_text_value(brief.draft_message.body, replacements), 560)
    brief.follow_up_check.check_after = _limit_text(
        _clean_text_value(brief.follow_up_check.check_after, replacements),
        120,
    )
    brief.follow_up_check.success_condition = _limit_text(
        _clean_text_value(brief.follow_up_check.success_condition, replacements),
        220,
    )
    brief.follow_up_check.escalation_condition = _limit_text(
        _clean_text_value(brief.follow_up_check.escalation_condition, replacements),
        220,
    )
    for option in brief.decision_options:
        option.option = _limit_text(_clean_text_value(option.option, replacements), 160)
        option.when_to_choose = _limit_text(_clean_text_value(option.when_to_choose, replacements), 220)
        option.tradeoff = _limit_text(_clean_text_value(option.tradeoff, replacements), 220)
    return brief


def _strip_technical_ids(value: str) -> str:
    value = re.sub(r"\s*\(\s*(?:T|TD|RK|C|D|DEC|CR|R|Р)\d{3}\s*\)", "", value)
    value = TECHNICAL_ID_RE.sub("", value)
    value = re.sub(r"[/#]\d{3}\b", "", value)
    value = re.sub(r"\s*->\s*(?:->\s*)+", " -> ", value)
    value = re.sub(r"^\s*->\s*|\s*->\s*$", "", value)
    value = re.sub(r"\(\s*\)", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"\s+([,.!?;:])", r"\1", value)
    return value.strip()


def _limit_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value

    sentence_end_positions = [
        value.rfind(".", 0, limit),
        value.rfind("!", 0, limit),
        value.rfind("?", 0, limit),
    ]
    sentence_end = max(sentence_end_positions)
    if sentence_end >= max(40, limit // 2):
        return value[: sentence_end + 1].strip()

    return value


def _clean_text_value(value: str, replacements: dict[str, str]) -> str:
    for source_id, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(_id_pattern(source_id), replacement, value)
    return humanize_agent_text(_strip_technical_ids(value))


def _id_pattern(source_id: str) -> str:
    if source_id.startswith("R"):
        return rf"\b[RР]{re.escape(source_id[1:])}\b"
    return rf"\b{re.escape(source_id)}\b"


def _build_id_replacements(problem_context: dict[str, Any]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for task in problem_context.get("problem_tasks", []):
        replacements[task["id"]] = f"«{task['title']}»"
    for edge in problem_context.get("task_dependency_edges", []):
        replacements[edge["task_id"]] = f"«{edge['task_title']}»"
        replacements[edge["depends_on_task_id"]] = f"«{edge['depends_on_task_title']}»"
        replacements[edge["id"]] = "зависимость критического пути"
    for risk in problem_context.get("linked_risks", []):
        replacements[risk["id"]] = f"риск «{risk['risk_type']}»"
    for communication in problem_context.get("linked_communications", []):
        replacements[communication["id"]] = f"коммуникация «{communication['topic']}»"
    for dependency in problem_context.get("linked_project_dependencies", []):
        replacements[dependency["id"]] = f"зависимость «{dependency['depends_on']}»"
    for decision in problem_context.get("pending_decisions", []):
        replacements[decision["id"]] = f"решение «{decision['description']}»"
    for change_request in problem_context.get("open_change_requests", []):
        replacements[change_request["id"]] = f"запрос на изменение «{change_request['description']}»"
    for resource in problem_context.get("overloaded_resources", []):
        replacements[resource["resource_id"]] = resource["full_name"]
    return replacements
