from __future__ import annotations

import ast
import math
import struct
from typing import Any

from .constants import (
    FFT_ALERT_AMPLITUDE_THRESHOLD,
    FFT_ALERT_EXTRACTION_TYPES,
    FFT_PEAK_SETTINGS,
    FREQUENCY_RANGES_HZ,
    MEASURE_MODE_DEFINITIONS,
)
from .metadata import _fft_metadata


def _decode_float32_bytes(raw_value: str) -> list[float]:
    decoded = ast.literal_eval(raw_value)
    if not isinstance(decoded, bytes):
        raise ValueError("FFT ResultData가 bytes 리터럴이 아닙니다.")
    if len(decoded) % 4:
        raise ValueError("FFT ResultData 길이가 float32 크기와 맞지 않습니다.")

    value_count = len(decoded) // 4
    return list(struct.unpack(f"<{value_count}f", decoded))


def analyze_velocity_fft(
    frequencies: list[float], amplitudes: list[float], rpm: float | None
) -> dict[str, Any]:
    """Classify a velocity FFT with the supplied reference 1X/2X/3X ratio rules."""
    analysis: dict[str, Any] = {
        "status": "unavailable",
        "diagnosis": "unavailable",
        "label": "회전수 미설정",
        "message": "설비 RPM이 설정되지 않아 회전 주파수 기반 진단을 보류했습니다.",
        "rpm": rpm,
        "rpmSource": "equipment_config" if rpm is not None else "unavailable",
        "shaftFrequency": None,
        "frequencyTolerance": FFT_PEAK_SETTINGS["3"]["frequencyTolerance"],
        "harmonics": [],
        "ratios": {"twoToOne": None, "threeToOne": None},
    }
    if rpm is None or not math.isfinite(rpm) or rpm <= 0:
        return analysis
    if len(frequencies) != len(amplitudes):
        analysis.update(
            {
                "label": "분석 불가",
                "message": "FFT 주파수와 진폭 배열의 길이가 일치하지 않습니다.",
            }
        )
        return analysis

    tolerance = FFT_PEAK_SETTINGS["3"]["frequencyTolerance"]
    shaft_frequency = rpm / 60.0

    def find_peak(target_frequency: float) -> tuple[float | None, float]:
        candidates = [
            (frequency, amplitude)
            for frequency, amplitude in zip(frequencies, amplitudes)
            if math.isfinite(frequency)
            and math.isfinite(amplitude)
            and abs(frequency - target_frequency) <= tolerance
        ]
        return max(candidates, key=lambda item: item[1]) if candidates else (None, 0.0)

    harmonics = []
    for order in range(1, 4):
        target_frequency = shaft_frequency * order
        detected_frequency, amplitude = find_peak(target_frequency)
        harmonics.append(
            {
                "order": order,
                "targetFrequency": target_frequency,
                "detectedFrequency": detected_frequency,
                "amplitude": amplitude,
                "detected": detected_frequency is not None,
            }
        )

    one_x, two_x, three_x = (harmonic["amplitude"] for harmonic in harmonics)
    analysis.update({"rpm": rpm, "shaftFrequency": shaft_frequency, "harmonics": harmonics})
    if one_x < FFT_PEAK_SETTINGS["3"]["amplitudeThreshold"]:
        analysis.update(
            {
                "status": "insufficient_1x",
                "diagnosis": "inconclusive",
                "label": "판정 불가",
                "message": "1X 회전 주파수 주변에서 0.5 mm/s 이상의 피크를 찾지 못했습니다.",
            }
        )
        return analysis

    ratios = {"twoToOne": two_x / one_x, "threeToOne": three_x / one_x}
    analysis["ratios"] = ratios
    if ratios["twoToOne"] > 0.4 or ratios["threeToOne"] > 0.3:
        diagnosis, label = "misalignment", "Misalignment"
    elif ratios["twoToOne"] < 0.2 and ratios["threeToOne"] < 0.1:
        diagnosis, label = "unbalance", "Unbalance"
    else:
        diagnosis, label = "complex", "복합 또는 판정 불확실"
    analysis.update(
        {
            "status": "analyzed",
            "diagnosis": diagnosis,
            "label": label,
            "message": (
                f"1X 대비 2X 비율 {ratios['twoToOne']:.2f}, "
                f"3X 비율 {ratios['threeToOne']:.2f}를 기준으로 판정했습니다."
            ),
        }
    )
    return analysis


def analyze_fft_diagnosis(
    frequencies: list[float], amplitudes: list[float], measure_mode: str, rpm: float | None
) -> dict[str, Any]:
    if measure_mode == "3":
        return analyze_velocity_fft(frequencies, amplitudes, rpm)
    if measure_mode in {"0", "2"}:
        return {
            "status": "deferred",
            "diagnosis": "deferred",
            "label": "가속도 진단 보류",
            "message": "가속도 FFT의 베어링·기타 결함 진단은 현재 범위에서 보류했습니다.",
            "rpm": rpm,
            "rpmSource": "equipment_config" if rpm is not None else "unavailable",
            "shaftFrequency": None,
            "frequencyTolerance": None,
            "harmonics": [],
            "ratios": {"twoToOne": None, "threeToOne": None},
        }
    return {
        "status": "unavailable",
        "diagnosis": "unavailable",
        "label": "분석 불가",
        "message": "지원하지 않는 FFT 측정모드입니다.",
        "rpm": rpm,
        "rpmSource": "equipment_config" if rpm is not None else "unavailable",
        "shaftFrequency": None,
        "frequencyTolerance": None,
        "harmonics": [],
        "ratios": {"twoToOne": None, "threeToOne": None},
    }


def analyze_fft_spectrum(
    frequencies: list[float], amplitudes: list[float], measure_mode: str
) -> dict[str, Any]:
    """Extract and group the dominant FFT peaks using the reference thresholds."""
    settings = FFT_PEAK_SETTINGS.get(measure_mode)
    analysis: dict[str, Any] = {
        "status": "unavailable",
        "amplitudeThreshold": None,
        "frequencyTolerance": None,
        "peaks": [],
        "message": "지원하지 않는 측정모드 또는 주파수 범위입니다.",
    }
    if settings is None or len(frequencies) != len(amplitudes):
        return analysis

    candidates = [
        (frequency, amplitude)
        for frequency, amplitude in zip(frequencies, amplitudes)
        if frequency > 0 and math.isfinite(frequency) and math.isfinite(amplitude)
    ]
    if not candidates:
        analysis.update({"status": "no_data", "message": "분석할 유효 FFT 진폭값이 없습니다."})
        return analysis

    # The reference logic starts with the ten largest amplitudes, then merges close frequencies.
    top_candidates = sorted(candidates, key=lambda item: item[1], reverse=True)[:10]
    ordered = sorted(top_candidates, key=lambda item: item[0])
    groups: list[list[tuple[float, float]]] = [[ordered[0]]]
    for candidate in ordered[1:]:
        if candidate[0] - groups[-1][-1][0] <= settings["frequencyTolerance"]:
            groups[-1].append(candidate)
        else:
            groups.append([candidate])

    peaks = []
    for group in groups:
        representative_frequency, maximum_amplitude = max(group, key=lambda item: item[1])
        if maximum_amplitude >= settings["amplitudeThreshold"]:
            peaks.append(
                {
                    "frequency": representative_frequency,
                    "amplitude": maximum_amplitude,
                    "groupFrequencies": [frequency for frequency, _ in group],
                    "groupAmplitudes": [amplitude for _, amplitude in group],
                    "count": len(group),
                }
            )
    peaks.sort(key=lambda peak: peak["amplitude"], reverse=True)
    analysis.update(
        {
            "status": "analyzed" if peaks else "no_significant_peak",
            "amplitudeThreshold": settings["amplitudeThreshold"],
            "frequencyTolerance": settings["frequencyTolerance"],
            "peaks": peaks[:5],
            "message": (
                "진폭 기준을 만족하는 주요 피크를 검출했습니다."
                if peaks
                else "설정된 진폭 기준을 만족하는 주요 피크가 없습니다."
            ),
        }
    )
    return analysis


def _maximum_finite_amplitude(amplitudes: list[float]) -> float | None:
    return max((amplitude for amplitude in amplitudes if math.isfinite(amplitude)), default=None)


def _is_alert_fft_record(metadata: dict[str, Any], maximum_amplitude: float | None) -> bool:
    return (
        metadata["extractionType"]["code"] in FFT_ALERT_EXTRACTION_TYPES
        or (
            maximum_amplitude is not None
            and maximum_amplitude > FFT_ALERT_AMPLITUDE_THRESHOLD
        )
    )


def _fft_record_summary(row: dict[str, str], record_id: int) -> dict[str, Any]:
    metadata = _fft_metadata(row)
    amplitudes = _decode_float32_bytes(row["ResultData"])
    maximum_amplitude = _maximum_finite_amplitude(amplitudes)
    return {
        "id": record_id,
        "measuredAt": metadata["measureDate"],
        "extractionType": metadata["extractionType"],
        "diagMode": metadata["diagMode"],
        "measureMode": metadata["measureMode"],
        "measureFreq": metadata["measureFreq"],
        "maxAmplitude": maximum_amplitude,
        "hasHighAmplitude": (
            maximum_amplitude is not None
            and maximum_amplitude > FFT_ALERT_AMPLITUDE_THRESHOLD
        ),
        "isAlertFft": _is_alert_fft_record(metadata, maximum_amplitude),
    }


def _build_fft_record(row: dict[str, str], record_id: int, rpm: float | None = None) -> dict[str, Any]:
    frequency_code = row["MeasureFreq"]
    measure_mode = row["MeasureMode"]
    amplitudes = _decode_float32_bytes(row["ResultData"])
    metadata = _fft_metadata(row)
    maximum_amplitude = _maximum_finite_amplitude(amplitudes)
    line_count = int(row["MeasureLineNum"])
    if line_count <= 0:
        raise ValueError("FFT MeasureLineNum은 1 이상이어야 합니다.")
    if len(amplitudes) != line_count:
        raise ValueError(
            f"FFT 라인 수 불일치: MeasureLineNum={line_count}, ResultData={len(amplitudes)}"
        )

    frequency_range = FREQUENCY_RANGES_HZ.get(frequency_code)
    frequency_step = frequency_range / line_count if frequency_range is not None else 1.0
    frequencies = [index * frequency_step for index in range(line_count)]
    return {
        "recordId": record_id,
        "measuredAt": row["MeasureDate"],
        "metadata": metadata,
        "frequencyUnit": "Hz" if frequency_range is not None else "bin",
        "amplitudeUnit": MEASURE_MODE_DEFINITIONS.get(measure_mode, {}).get("amplitudeUnit"),
        "frequencyRange": frequency_range,
        "lineCount": line_count,
        "maxAmplitude": maximum_amplitude,
        "isAlertFft": _is_alert_fft_record(metadata, maximum_amplitude),
        "frequencies": frequencies,
        "amplitudes": amplitudes,
        "analysis": {
            **analyze_fft_spectrum(frequencies, amplitudes, measure_mode),
            "diagnosis": analyze_fft_diagnosis(frequencies, amplitudes, measure_mode, rpm),
        },
    }
