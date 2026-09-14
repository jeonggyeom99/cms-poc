"""Thin orchestration facade for API, AI, reports, and future agent tools."""
from typing import Any

from app.analysis.envelope import analyze_envelope
from app.data_loader import load_fft_record


def select_fft_analysis_record(fft: dict[str, Any], record_id: int) -> dict[str, Any]:
    return load_fft_record(fft, record_id)


def envelope_for_dashboard(record: dict[str, Any], low_hz: float, high_hz: float) -> dict[str, Any]:
    return analyze_envelope(record, low_hz, high_hz, include_artifacts=True)
