"""Sampling rule shared by waveform display and envelope analysis."""
from .constants import FREQUENCY_RANGES_HZ


def sampling_metadata(code: str, sample_count: int, line_count: int) -> dict:
    fmax = FREQUENCY_RANGES_HZ.get(code)
    reason = None
    if fmax is None:
        reason = "등록되지 않은 MeasureFreq 코드입니다."
    elif not sample_count or line_count <= 0 or sample_count * 100 != line_count * 256:
        reason = "파형 길이/FFT 라인 수가 2.56이 아니므로 샘플링 규칙을 적용할 수 없습니다."
    return {
        "valid": reason is None,
        "frequencyHz": fmax * 2.56 if reason is None else None,
        "rule": "Fs = Fmax × 2.56",
        "sampleCount": sample_count,
        "reason": reason,
    }
