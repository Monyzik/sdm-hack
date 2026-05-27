from __future__ import annotations

from datetime import date, datetime
from typing import Any


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
