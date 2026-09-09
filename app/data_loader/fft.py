from __future__ import annotations

import ast
import math
import struct
from typing import Any

from .constants import (
    BEARING_FAULT_TYPES,
    BEARING_FREQUENCY_TOLERANCE,
    BEARING_PEAK_THRESHOLD,
    FFT_ALERT_AMPLITUDE_THRESHOLD,
    FFT_ALERT_EXTRACTION_TYPES,
    FFT_PEAK_SETTINGS,
    FREQUENCY_RANGES_HZ,
    MEASURE_MODE_DEFINITIONS,
)
from .bearing import lookup_bearing_coefficients
from .metadata import _fft_metadata


def _decode_float32_bytes(raw_value: str) -> list[float]:
    decoded = ast.literal_eval(raw_value)
    if not isinstance(decoded, bytes):
        raise ValueError("FFT ResultData가 bytes 리터럴이 아닙니다.")
    if len(decoded) % 4:
        raise ValueError("FFT ResultData 길이가 float32 크기와 맞지 않습니다.")

    value_count = len(decoded) // 4
    return list(struct.unpack(f"<{value_count}f", decoded))


def _decode_time_wave_samples(row: dict[str, str]) -> list[float] | None:
    """Return a usable time waveform without making the FFT record unavailable."""
    raw_value = row.get("TimeWaveSampling")
    if not raw_value:
        return None
    try:
        samples = _decode_float32_bytes(raw_value)
    except (SyntaxError, TypeError, ValueError):
        return None
    if not samples or not all(math.isfinite(sample) for sample in samples):
        return None
    return samples


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


def _bearing_diagnosis_key(fault_type: str) -> tuple[str, str]:
    return {
        "BPFO": ("bearing_outer_race", "베어링 외륜 결함"),
        "BPFI": ("bearing_inner_race", "베어링 내륜 결함"),
        "BSF": ("bearing_ball", "베어링 볼 결함"),
        "FTF": ("bearing_cage", "베어링 케이지 결함"),
    }[fault_type]


def analyze_acceleration_bearing_fft(
    frequencies: list[float],
    amplitudes: list[float],
    rpm: float | None,
    bearing: dict[str, Any] | None,
) -> dict[str, Any]:
    """Analyse acceleration spectra at bearing-fault 1X/2X/3X orders."""
    maker = (bearing or {}).get("maker")
    bearing_number = (bearing or {}).get("number")
    analysis: dict[str, Any] = {
        "status": "unavailable",
        "diagnosis": "unavailable",
        "label": "가속도 베어링 분석 불가",
        "message": "베어링 분석에 필요한 정보가 없습니다.",
        "rpm": rpm,
        "rpmSource": "equipment_config" if rpm is not None else "unavailable",
        "shaftFrequency": None,
        "frequencyTolerance": BEARING_FREQUENCY_TOLERANCE,
        "amplitudeThreshold": BEARING_PEAK_THRESHOLD,
        "bearing": {"maker": maker, "number": bearing_number},
        "faults": [],
        "defaultFaultType": None,
        "harmonics": [],
        "ratios": {"twoToOne": None, "threeToOne": None},
    }
    if rpm is None or not math.isfinite(rpm) or rpm <= 0:
        analysis["message"] = "설비 RPM이 설정되지 않아 베어링 결함 주파수를 계산할 수 없습니다."
        return analysis
    if len(frequencies) != len(amplitudes) or not frequencies:
        analysis["message"] = "FFT 주파수와 진폭 배열이 유효하지 않습니다."
        return analysis

    master = lookup_bearing_coefficients(maker, bearing_number)
    analysis["bearing"].update(
        {
            "available": master["available"],
            "reason": master.get("reason"),
            "coefficients": master.get("coefficients", {}),
        }
    )
    if not master["available"]:
        messages = {
            "bearing_not_configured": "설비 베어링 제조사 또는 형번이 설정되지 않았습니다.",
            "bearing_not_found": "베어링 마스터에서 제조사와 형번에 일치하는 결함계수를 찾지 못했습니다.",
            "bearing_master_ambiguous": "베어링 마스터에 서로 다른 결함계수를 가진 중복 항목이 있습니다.",
            "bearing_coefficients_invalid": "베어링 마스터의 결함계수가 유효하지 않습니다.",
            "bearing_master_unavailable": "베어링 마스터 파일을 읽을 수 없습니다.",
        }
        analysis["message"] = messages.get(master.get("reason"), analysis["message"])
        return analysis

    shaft_frequency = rpm / 60.0
    valid_points = [
        (float(frequency), float(amplitude))
        for frequency, amplitude in zip(frequencies, amplitudes)
        if math.isfinite(frequency) and math.isfinite(amplitude)
    ]
    if not valid_points:
        analysis["message"] = "분석할 유효 FFT 진폭값이 없습니다."
        return analysis

    def find_peak(target_frequency: float) -> tuple[float | None, float]:
        candidates = [
            point for point in valid_points
            if abs(point[0] - target_frequency) <= BEARING_FREQUENCY_TOLERANCE
        ]
        return max(candidates, key=lambda item: item[1]) if candidates else (None, 0.0)

    faults = []
    for fault_type in BEARING_FAULT_TYPES:
        coefficient = master["coefficients"].get(fault_type)
        if coefficient is None:
            continue
        base_frequency = shaft_frequency * coefficient
        harmonics = []
        weighted_score = 0.0
        sideband_score = 0.0
        for order in range(1, 4):
            target_frequency = base_frequency * order
            detected_frequency, amplitude = find_peak(target_frequency)
            weighted_score += amplitude / order
            harmonics.append(
                {
                    "order": order,
                    "targetFrequency": target_frequency,
                    "detectedFrequency": detected_frequency,
                    "amplitude": amplitude,
                    "detected": detected_frequency is not None,
                    "significant": amplitude >= BEARING_PEAK_THRESHOLD,
                }
            )
            for direction in (-1, 1):
                sideband_frequency = target_frequency + direction * shaft_frequency
                if sideband_frequency > 0:
                    _, sideband_amplitude = find_peak(sideband_frequency)
                    sideband_score += sideband_amplitude * 0.25
        diagnosis, label = _bearing_diagnosis_key(fault_type)
        faults.append(
            {
                "type": fault_type,
                "diagnosis": diagnosis,
                "label": label,
                "coefficient": coefficient,
                "baseFrequency": base_frequency,
                "harmonics": harmonics,
                "score": weighted_score + sideband_score,
                "harmonicScore": weighted_score,
                "sidebandScore": sideband_score,
                "hasAnomaly": any(harmonic["significant"] for harmonic in harmonics),
                "largestPeak": max(harmonic["amplitude"] for harmonic in harmonics),
            }
        )

    if not faults:
        analysis["message"] = "베어링 마스터에 사용할 수 있는 결함계수가 없습니다."
        return analysis
    anomalous = [fault for fault in faults if fault["hasAnomaly"]]
    ranking = anomalous or [fault for fault in faults if fault["type"] == "BPFO"] or faults
    order_index = {fault_type: index for index, fault_type in enumerate(BEARING_FAULT_TYPES)}
    selected = sorted(
        ranking,
        key=lambda fault: (-fault["score"], -fault["largestPeak"], order_index[fault["type"]]),
    )[0]
    highest_scores = sorted((fault["score"] for fault in faults), reverse=True)
    dominance = (
        highest_scores[0] / highest_scores[1]
        if len(highest_scores) > 1 and highest_scores[1] > 0
        else None
    )
    analysis.update(
        {
            "status": "analyzed" if anomalous else "no_anomaly",
            "diagnosis": selected["diagnosis"] if anomalous else "normal",
            "label": selected["label"] if anomalous else "베어링 결함 Peak 없음",
            "message": (
                f"{selected['type']}의 1X/2X/3X 결함 주파수에서 유의 Peak를 확인했습니다."
                if anomalous
                else f"{BEARING_PEAK_THRESHOLD:.1f} g 이상의 결함 1X/2X/3X Peak가 없습니다."
            ),
            "shaftFrequency": shaft_frequency,
            "faults": faults,
            "defaultFaultType": selected["type"],
            "harmonics": selected["harmonics"],
            "dominance": dominance,
        }
    )
    return analysis


def analyze_fft_diagnosis(
    frequencies: list[float], amplitudes: list[float], measure_mode: str, rpm: float | None,
    bearing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if measure_mode == "3":
        return analyze_velocity_fft(frequencies, amplitudes, rpm)
    if measure_mode in {"0", "2"}:
        return analyze_acceleration_bearing_fft(frequencies, amplitudes, rpm, bearing)
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


def _is_alert_fft_record(
    metadata: dict[str, Any],
    maximum_amplitude: float | None,
    diagnosis: dict[str, Any] | None = None,
) -> bool:
    return (
        metadata["extractionType"]["code"] in FFT_ALERT_EXTRACTION_TYPES
        or (
            maximum_amplitude is not None
            and maximum_amplitude > FFT_ALERT_AMPLITUDE_THRESHOLD
        )
        or diagnosis is not None
        and metadata["measureMode"]["code"] == "3"
        and diagnosis.get("status") == "analyzed"
    )


def _has_analysis_anomaly(diagnosis: dict[str, Any] | None) -> bool:
    return diagnosis is not None and diagnosis.get("status") == "analyzed"


def _fft_record_summary(
    row: dict[str, str],
    record_id: int,
    rpm: float | None = None,
    bearing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = _fft_metadata(row)
    amplitudes = _decode_float32_bytes(row["ResultData"])
    maximum_amplitude = _maximum_finite_amplitude(amplitudes)
    diagnosis = None
    if row["MeasureMode"] == "3" and rpm is not None:
        frequency_range = FREQUENCY_RANGES_HZ.get(row["MeasureFreq"])
        line_count = int(row["MeasureLineNum"])
        if frequency_range is not None and line_count > 0 and len(amplitudes) == line_count:
            frequency_step = frequency_range / line_count
            frequencies = [(index + 1) * frequency_step for index in range(line_count)]
            diagnosis = analyze_fft_diagnosis(frequencies, amplitudes, "3", rpm, bearing)
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
        "hasAnalysisAnomaly": _has_analysis_anomaly(diagnosis),
        "isAlertFft": _is_alert_fft_record(metadata, maximum_amplitude, diagnosis),
    }


def _build_fft_record(
    row: dict[str, str], record_id: int, rpm: float | None = None,
    bearing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frequency_code = row["MeasureFreq"]
    measure_mode = row["MeasureMode"]
    amplitudes = _decode_float32_bytes(row["ResultData"])
    time_wave_samples = _decode_time_wave_samples(row)
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
    # CSV ResultData excludes the 0 Hz DC component, so its first value is bin 1.
    frequencies = [(index + 1) * frequency_step for index in range(line_count)]
    diagnosis = analyze_fft_diagnosis(frequencies, amplitudes, measure_mode, rpm, bearing)
    return {
        "recordId": record_id,
        "measuredAt": row["MeasureDate"],
        "metadata": metadata,
        "frequencyUnit": "Hz" if frequency_range is not None else "bin",
        "amplitudeUnit": MEASURE_MODE_DEFINITIONS.get(measure_mode, {}).get("amplitudeUnit"),
        "frequencyRange": frequency_range,
        "lineCount": line_count,
        "maxAmplitude": maximum_amplitude,
        "hasAnalysisAnomaly": _has_analysis_anomaly(diagnosis),
        "isAlertFft": _is_alert_fft_record(metadata, maximum_amplitude, diagnosis),
        "frequencies": frequencies,
        "amplitudes": amplitudes,
        "timeWaveSamples": time_wave_samples,
        "analysis": {
            **analyze_fft_spectrum(frequencies, amplitudes, measure_mode),
            "diagnosis": diagnosis,
        },
    }
