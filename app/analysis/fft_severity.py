"""Amplitude grades for shaft and coefficient-adjusted bearing harmonics."""
from __future__ import annotations

import math
from typing import Any

VELOCITY_LIMITS = (4, 10, 20)
ACCELERATION_LIMITS = (0.2, 1)

CAUSE_LABELS = {
    "unbalance": "Unbalance", "misalignment": "Misalignment", "complex": "기타/복합",
    "BPFO": "베어링 외륜(BPFO)", "BPFI": "베어링 내륜(BPFI)",
    "BSF": "베어링 전동체(BSF)", "FTF": "베어링 케이지(FTF)",
}


def amplitude_grade(value: Any, unit: str) -> dict:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return {"label": "판정 불가", "score": None, "state": "neutral"}
    if unit == "mm/s":
        score = 0 if value <= VELOCITY_LIMITS[0] else 1 if value <= VELOCITY_LIMITS[1] else 2 if value <= VELOCITY_LIMITS[2] else 3
        label = ("양호", "초기 결함", "심각", "정지")[score]
    elif unit == "g":
        score = 0 if value <= ACCELERATION_LIMITS[0] else 1 if value < ACCELERATION_LIMITS[1] else 3
        label = {0: "양호", 1: "초기 결함", 3: "베어링 교체"}[score]
    else:
        return {"label": "판정 불가", "score": None, "state": "neutral"}
    return {"label": label, "score": score, "state": "normal" if score == 0 else "caution" if score == 1 else "danger"}


def assess_fft_harmonics(record: dict) -> list[dict]:
    """Use raw diagnostic amplitudes, never spectrum maxima or rounded evidence."""
    diagnosis = (record.get("analysis") or {}).get("diagnosis") or {}
    metadata = record.get("metadata") or {}
    mode = (metadata.get("measureMode") or {}).get("code")
    unit = record.get("amplitudeUnit")
    if record.get("frequencyUnit") == "bin":
        entries = []
    elif mode == "3" and unit == "mm/s":
        cause = diagnosis.get("diagnosis")
        entries = [{"type": cause if cause in CAUSE_LABELS else "complex", "harmonics": diagnosis.get("harmonics", [])}]
    elif mode in {"0", "2"} and unit == "g":
        entries = diagnosis.get("faults") or []
    else:
        entries = []
    assessments = []
    for entry in entries:
        harmonics = []
        source = {item.get("order"): item for item in entry.get("harmonics", [])}
        for order in (1, 2, 3):
            item = source.get(order) or {}
            grade = amplitude_grade(item.get("amplitude"), unit) if item.get("detected") else amplitude_grade(None, unit)
            harmonics.append({"order": order, "amplitude": item.get("amplitude") if grade["score"] is not None else None,
                              "frequency": item.get("detectedFrequency"), **grade})
        valid = [item for item in harmonics if item["score"] is not None]
        highest = max(valid, key=lambda item: (item["score"], item["amplitude"])) if valid else None
        assessments.append({"recordId": record.get("recordId"), "measuredAt": record.get("measuredAt"),
                            "measureMode": mode, "unit": unit, "cause": entry["type"],
                            "causeLabel": CAUSE_LABELS.get(entry["type"], "기타/복합"),
                            "harmonics": harmonics, "grade": highest["label"] if highest else "판정 불가",
                            "score": highest["score"] if highest else None,
                            "state": highest["state"] if highest else "neutral",
                            "maxAmplitude": highest["amplitude"] if highest else None,
                            "partial": len(valid) < 3,
                            "reason": "일부 고조파를 검출하지 못했습니다." if len(valid) < 3 else None})
    if not assessments:
        assessments.append({"recordId": record.get("recordId"), "measuredAt": record.get("measuredAt"),
                            "measureMode": mode, "unit": unit, "cause": None,
                            "causeLabel": "속도" if mode == "3" else "베어링", "harmonics": [],
                            "grade": "판정 불가", "score": None, "state": "neutral", "maxAmplitude": None,
                            "partial": True, "reason": diagnosis.get("message") or "유효한 고조파 근거가 없습니다."})
    return assessments


def grade_criterion(unit: str, score: int) -> str:
    if unit == "mm/s":
        a, b, c = VELOCITY_LIMITS
        return {0: f"{a} mm/s 이하", 1: f"{a} mm/s 초과~{b} mm/s 이하",
                2: f"{b} mm/s 초과~{c} mm/s 이하", 3: f"{c} mm/s 초과"}[score]
    a, b = ACCELERATION_LIMITS
    return {0: f"{a} g 이하", 1: f"{a} g 초과~{b} g 미만", 3: f"{b} g 이상"}[score]
