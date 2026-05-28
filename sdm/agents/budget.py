"""Ограничение времени на один запрос к агенту."""

from __future__ import annotations

import math
import os

DEFAULT_REQUEST_BUDGET_SECONDS = 180.0
# Новый поиск, черновик и обе проверки должны поместиться в оставшееся время.
MIN_RECOVERY_BUDGET_SECONDS = 60.0
RECOVERY_DRAFT_TIMEOUT_SECONDS = 30.0
VERIFICATION_RESERVE_SECONDS = 30.0


def request_budget_seconds() -> float:
    raw_value = os.getenv("AGENTS_REQUEST_BUDGET_SECONDS", "").strip()
    if not raw_value:
        return DEFAULT_REQUEST_BUDGET_SECONDS
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("AGENTS_REQUEST_BUDGET_SECONDS должен быть числом секунд.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("AGENTS_REQUEST_BUDGET_SECONDS должен быть положительным числом.")
    return value
