"""Backward-compatible envelope entry point."""
from app.analysis.envelope import analyze_envelope as _analyze_envelope


def analyze_envelope(record: dict, low_hz: float, high_hz: float) -> dict:
    return _analyze_envelope(record, low_hz, high_hz, include_artifacts=True)
