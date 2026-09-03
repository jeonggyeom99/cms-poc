from __future__ import annotations

import math
from typing import Any


def _optional_finite_float(raw_value: Any) -> float | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None
