from __future__ import annotations

import re
from typing import Any


def limit_text(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def humanize_agent_text(value: str) -> str:
    replacements = {
        "pending change request": "запрос на изменение, ожидающий решения",
        "open change request": "открытый запрос на изменение",
        "blocked task": "заблокированная задача",
        "pending": "ожидает решения",
        "open": "открыт",
        "blocked": "заблокирован",
        "critical path": "критический путь",
        "critical": "критичный",
        "high": "высокий",
        "medium": "средний",
        "low": "низкий",
        "change request": "запрос на изменение",
        "follow-up": "последующая проверка",
        "status": "статус",
    }
    value = _re_sub(r"\bпакет\s+эскалаци[ия]\b", "набор материалов для решения", value)
    value = _re_sub(r"\bэскалаци\w*\b", "решение на уровне комитета", value)
    value = _re_sub(r"\bescalat\w*\b", "решение на уровне комитета", value)
    for source, replacement in replacements.items():
        value = _re_sub(rf"\b{source}\b", replacement, value)
    return " ".join(value.split())


def bounded_limit(value: Any, default: int, minimum: int = 1, maximum: int = 20) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text not in result:
            result.append(text)
    return result


def _re_sub(pattern: str, replacement: str, value: str) -> str:
    return re.sub(pattern, replacement, value, flags=re.IGNORECASE)
