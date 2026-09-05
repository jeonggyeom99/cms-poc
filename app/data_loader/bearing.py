from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .constants import BEARING_FAULT_MASTER_PATH, BEARING_FAULT_TYPES


def _normalise(value: object) -> str:
    return str(value).strip().upper()


@lru_cache(maxsize=4)
def _load_master(path: Path) -> dict[tuple[str, str], dict[str, float] | None]:
    """Read the tab-delimited bearing-order master once per file path."""
    grouped: dict[tuple[str, str], list[dict[str, float]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as master_file:
        reader = csv.DictReader(master_file, delimiter="\t")
        required = {"Number", "Maker", *BEARING_FAULT_TYPES}
        if not required.issubset(reader.fieldnames or []):
            missing = ", ".join(sorted(required - set(reader.fieldnames or [])))
            raise ValueError(f"베어링 마스터 필수 컬럼 누락: {missing}")
        for row in reader:
            coefficients: dict[str, float] = {}
            for fault_type in BEARING_FAULT_TYPES:
                try:
                    coefficient = float(row[fault_type])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(coefficient) and coefficient > 0:
                    coefficients[fault_type] = coefficient
            key = (_normalise(row["Maker"]), _normalise(row["Number"]))
            grouped.setdefault(key, []).append(coefficients)

    # Conflicting duplicate rows cannot be selected safely.
    return {
        key: rows[0] if len(rows) == 1 or all(row == rows[0] for row in rows[1:]) else None
        for key, rows in grouped.items()
    }


def lookup_bearing_coefficients(
    maker: object | None,
    bearing_number: object | None,
    path: Path = BEARING_FAULT_MASTER_PATH,
) -> dict[str, Any]:
    """Return usable fault orders, or a public reason why analysis is unavailable."""
    if not maker or not bearing_number or str(bearing_number).strip() in {"", "-"}:
        return {"available": False, "reason": "bearing_not_configured", "coefficients": {}}
    try:
        master = _load_master(path)
    except (OSError, ValueError) as error:
        return {"available": False, "reason": "bearing_master_unavailable", "detail": str(error), "coefficients": {}}

    key = (_normalise(maker), _normalise(bearing_number))
    match = master.get(key)
    if match is None and key in master:
        return {"available": False, "reason": "bearing_master_ambiguous", "coefficients": {}}
    if match is None:
        return {"available": False, "reason": "bearing_not_found", "coefficients": {}}
    if not match:
        return {"available": False, "reason": "bearing_coefficients_invalid", "coefficients": {}}
    return {
        "available": True,
        "maker": _normalise(maker),
        "bearingNumber": _normalise(bearing_number),
        "coefficients": match,
    }
