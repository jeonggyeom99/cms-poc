"""Equipment-scoped evidence and bounded, model-selected FFT history queries."""

from __future__ import annotations

import calendar
import json
import math
import re
from datetime import date, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.ai_analysis import (
    AiDiagnosis, _fft_summary, _timestamp, _trend_summary, build_ai_context,
    diagnosis_quality_issues,
)
from app.analysis.trend import analyze_velocity_trend
from app.services.history import _same_equipment
from app.data_loader import load_fft_record


PAGE_SIZE = 50


def recent_trend_evidence(dataset: dict[str, Any]) -> dict[str, Any]:
    source = dataset.get("trend") or {}
    dated = [(stamp, point) for point in source.get("points", [])
             if (stamp := _timestamp(point.get("timestamp"))) is not None]
    if not dated:
        return _trend_summary({})
    end = max(stamp for stamp, _ in dated)
    start = end - timedelta(days=90)
    points = [point for stamp, point in sorted(dated, key=lambda item: item[0]) if stamp >= start]
    velocity_points = [point for point in points if isinstance(point.get("value"), (int, float))
                       and not isinstance(point["value"], bool) and math.isfinite(point["value"])]
    trend = {**source, "points": points, "analysis": analyze_velocity_trend(velocity_points)}
    result = _trend_summary({**dataset, "trend": trend})
    result["window"] = {"days": 90, "start": start.isoformat(sep=" "), "end": end.isoformat(sep=" ")}
    for metric in result["metrics"]:
        definition = next((item for item in source.get("metrics", []) if item.get("key") == metric["key"]), {})
        key = definition.get("pointKey", "value" if metric["key"] == "velocity" else metric["key"])
        months: dict[str, list[tuple[datetime, float]]] = {}
        for point in points:
            value, stamp = point.get(key), _timestamp(point.get("timestamp"))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            months.setdefault(stamp.strftime("%Y-%m"), []).append((stamp, float(value)))
        metric["monthlyAverages"] = [
            {"month": month, "mean": round(sum(value for _, value in samples) / len(samples), 6),
             "sampleCount": len(samples), "start": samples[0][0].isoformat(sep=" "),
             "end": samples[-1][0].isoformat(sep=" "),
             "partialMonth": samples[0][0].day != 1 or samples[-1][0].day != calendar.monthrange(samples[-1][0].year, samples[-1][0].month)[1]}
            for month, samples in sorted(months.items())
        ]
    return result


def build_equipment_context(dataset_id: str, dataset: dict[str, Any], history: list[dict], until: date | None) -> dict:
    fft = dataset.get("fft") or {}
    context = build_ai_context(dataset_id, dataset, fft, history, None, until)
    context["equipmentAnalysis"] = True
    context["scope"] = "설비 전체 이력을 바탕으로 한 CMS 보조 분석"
    context["trend"] = recent_trend_evidence(dataset)
    if not fft:
        context["fft"] = {"available": False}
    records = sorted(fft.get("records", []), key=lambda item: (item["measuredAt"], item["id"]))
    context["fftInventory"] = {
        "count": len(records), "start": records[0]["measuredAt"] if records else None,
        "end": records[-1]["measuredAt"] if records else None,
        "measureModes": sorted({item["measureMode"]["code"] for item in records}),
        "pageSize": PAGE_SIZE,
    }
    # All source records participate in invalidation, including records not yet queried.
    source = {"trend": dataset.get("trend"), "fft": fft.get("_recordsById", fft),
              "history": [item for item in history if _same_equipment(item, dataset.get("equipment"), dataset_id)],
              "equipment": dataset.get("equipment"), "warning": dataset.get("_warningStatus")}
    context["sourceFingerprint"] = sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    context["dataQuality"]["notes"] = [note for note in context["dataQuality"]["notes"] if "Trend" not in note]
    if not context["trend"].get("available"):
        context["dataQuality"]["notes"].append("최근 3개월 추세 데이터가 없습니다.")
    return context


def equipment_tool_definitions() -> list[dict]:
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    query = {"type": "object", "properties": {
        "start": {"type": ["string", "null"], "description": "Inclusive ISO date; null means earliest available measurement."},
        "end": {"type": ["string", "null"], "description": "Inclusive ISO date; null means latest available measurement."},
        "measure_mode": {"type": ["string", "null"], "enum": ["0", "2", "3", None]},
        "offset": {"type": "integer", "minimum": 0, "description": "Pagination offset, initially 0."},
    }, "required": ["start", "end", "measure_mode", "offset"], "additionalProperties": False}
    definitions = [
        ("get_trend_evidence", "Get the latest 90 days of Trend evidence, monthly means and configured thresholds.", empty),
        ("get_fft_evidence", "Get one compact FFT record with peaks and harmonics. null record_id selects the default representative.",
         {"type": "object", "properties": {"record_id": {"type": ["integer", "null"]}}, "required": ["record_id"], "additionalProperties": False}),
        ("get_related_history", "Get prior same-equipment cases matching an inspected FFT record, strictly before its measurement.",
         {"type": "object", "properties": {"record_id": {"type": ["integer", "null"]}}, "required": ["record_id"], "additionalProperties": False}),
        ("list_fft_records", "Discover measurement dates, modes and record IDs for this equipment. Returns at most 50 records per page.", query),
        ("get_fft_history_evidence", "Compare actual shaft 1X/2X/3X or bearing harmonics over a model-selected period. Returns chronological evidence for up to 50 records per page; follow nextOffset for remaining records.", query),
    ]
    return [{"type": "function", "function": {"name": name, "description": description,
             "strict": True, "parameters": schema}} for name, description, schema in definitions]


def build_equipment_tool_executor(dataset_id: str, dataset: dict, history: list[dict], until: date | None, context: dict):
    fft = dataset.get("fft") or {}
    records = sorted(fft.get("records", []), key=lambda item: (item["measuredAt"], item["id"]))
    cache: dict[int, dict] = {}

    def evidence(record_id: int | None) -> dict:
        chosen = record_id if record_id is not None else fft.get("recordId")
        if isinstance(chosen, bool) or not isinstance(chosen, int):
            raise ValueError("invalid_record_id")
        if chosen not in cache:
            if not any(item["id"] == chosen for item in records):
                raise ValueError("record_not_found")
            cache[chosen] = _fft_summary(load_fft_record(fft, chosen))
        return cache[chosen]

    async def execute(name: str, arguments: dict) -> dict:
        try:
            if name == "get_trend_evidence":
                if arguments:
                    raise ValueError("invalid_tool_arguments")
                return {"equipment": context["equipment"], "trend": context["trend"], "levelAnalysis": context["levelAnalysis"]}
            if name in {"get_fft_evidence", "get_related_history"}:
                if set(arguments) != {"record_id"}:
                    raise ValueError("invalid_tool_arguments")
                if not records:
                    return {"status": "unavailable", "reason": "no_fft_data"}
                compact = evidence(arguments["record_id"])
                if name == "get_fft_evidence":
                    return {"status": "ready", "fft": compact}
                record = load_fft_record(fft, compact["recordId"])
                selected = build_ai_context(dataset_id, dataset, record, history, None, until)
                return {"status": "ready", "recordId": compact["recordId"], "relatedHistory": selected["relatedHistory"]}
            if name not in {"list_fft_records", "get_fft_history_evidence"}:
                raise ValueError("unknown_tool")
            if set(arguments) != {"start", "end", "measure_mode", "offset"}:
                raise ValueError("invalid_tool_arguments")
            start = date.fromisoformat(arguments["start"]) if arguments["start"] is not None else None
            end = date.fromisoformat(arguments["end"]) if arguments["end"] is not None else None
            mode, offset = arguments["measure_mode"], arguments["offset"]
            if mode not in {None, "0", "2", "3"} or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError("invalid_tool_arguments")
            if start and end and start > end:
                raise ValueError("invalid_date_range")
            if records and ((start and start < _timestamp(records[0]["measuredAt"]).date())
                            or (end and end > _timestamp(records[-1]["measuredAt"]).date())):
                raise ValueError("date_outside_available_measurements")
            matching = [item for item in records
                        if (not start or _timestamp(item["measuredAt"]).date() >= start)
                        and (not end or _timestamp(item["measuredAt"]).date() <= end)
                        and (mode is None or item["measureMode"]["code"] == mode)]
            page = matching[offset:offset + PAGE_SIZE]
            result = {"status": "ready", "totalCount": len(matching), "offset": offset,
                      "nextOffset": offset + PAGE_SIZE if offset + PAGE_SIZE < len(matching) else None,
                      "period": {"start": matching[0]["measuredAt"] if matching else None,
                                 "end": matching[-1]["measuredAt"] if matching else None}}
            if name == "list_fft_records":
                result["records"] = page
            else:
                result["records"] = [{"recordId": item["id"], "measuredAt": item["measuredAt"],
                                       "measurementPoint": context["equipment"].get("measurementPoint"),
                                       "fft": evidence(item["id"])} for item in page]
            return result
        except (ValueError, TypeError, KeyError, OSError, SyntaxError) as error:
            return {"status": "unavailable", "reason": str(error)[:120]}

    return execute


EQUIPMENT_INSTRUCTIONS = """
Analyze the equipment once using its available history, rather than the user's selected FFT.
Call get_trend_evidence, get_fft_evidence, get_related_history and get_fft_history_evidence
before completing the diagnosis. Choose your own comparison dates, months and representative
records from fftInventory. Use list_fft_records and additional FFT/history calls as needed.
When nextOffset is present, fetch subsequent pages or describe uninspected portions in
counterEvidence. At most 8 tool rounds and 16 calls are allowed; prioritize useful comparisons.
Compare only the same measurement mode, unit and measurement point. Changes in RPM or
frequency resolution limit comparisons. Explain when shaft 1X or other components started
increasing using actual observed dates and amplitudes. Sparse observations bound the onset
interval; they do not establish the exact day deterioration began.
Write all output in natural Korean. headline: 1-2 sentences, at most 140 characters, connecting
main changes, supported cause candidates and a practical inspection action. Detailed numbers
belong in the graph summaries and findings. trendSummary: 1-2 sentences about the latest
90 days (~3 months), monthly average changes and persistence. Only monthlyAverages.mean is a
monthly average; mark partialMonth periods as partial. A reading difference is not an average.
The recent 72-hour rule and the 3-month monthly averages describe different windows. You may
describe long-term increases supported by the monthly averages even when the short-term rule
is stable. Do not call isolated spikes a sustained increase. Describe missing data explicitly.
fftSummary: 1-2 sentences connecting observed historical harmonic changes, dominant components,
supported hypotheses and practical additional checks. A dominant shaft 1X alone does not establish
misalignment: check 2X/3X and their ratios. Bearing defect harmonics and shaft harmonics differ;
never mix acceleration g with velocity mm/s or compare different modes as one time series.
fftAnalysisPeriod.start/end: actual first/last FFT observation timestamps used for comparison,
without adding timezone offsets to timestamps whose timezone is unknown.
fftReferenceRecordIds: unique IDs with inspected FFT evidence, most important representative first.
List metadata alone does not establish harmonic amplitudes. If no FFT evidence is available,
return null period boundaries and an empty reference list. State evidence limitations and never
invent numbers, deterioration dates or causes. These equipment instructions replace the earlier
single-record headline mode requirements and short-term-only rising rule.
"""


def equipment_quality_issues(context: dict, result: AiDiagnosis, trace: list[dict]) -> list[str]:
    issues: list[str] = []
    inspected: dict[int, dict] = {}
    for call in trace:
        payload = call["result"]
        if call["name"] == "get_fft_evidence" and payload.get("fft"):
            inspected[payload["fft"]["recordId"]] = payload["fft"]
        if call["name"] == "get_fft_history_evidence":
            for item in payload.get("records", []):
                inspected[item["recordId"]] = item["fft"]
    refs = result.fft_reference_record_ids
    if len(result.headline) > 140:
        issues.append("종합 요약은 핵심 변화와 점검 행동을 140자 이내로 작성하세요.")
    if not any(word in result.headline for word in ("확인", "점검", "재측정", "검토")):
        issues.append("종합 요약에 실행 가능한 확인 또는 점검 행동을 포함하세요.")
    if len(refs) != len(set(refs)) or any(record_id not in inspected for record_id in refs):
        issues.append("fftReferenceRecordIds는 실제로 조회한 FFT 기록만 중복 없이 지정하세요.")
    period = result.fft_analysis_period
    valid_period = False
    if inspected:
        if not refs:
            issues.append("조회한 대표 FFT 기록 ID를 지정하세요.")
        stamps = {_timestamp(item["measuredAt"]) for item in inspected.values()}
        valid_period = period.start in stamps and period.end in stamps and period.start <= period.end
        if not valid_period:
            issues.append("fftAnalysisPeriod는 조회한 FFT 기록의 실제 관측 시작·종료 일시로 지정하세요.")
        if refs and refs[0] in inspected:
            representative = inspected[refs[0]]
            # Legacy checks enforce physical causes; trend persistence is assessed over the new monthly evidence.
            check_context = {**context, "fft": representative, "trend": {"metrics": [], "analysis": {"status": "rising"}}}
            legacy = diagnosis_quality_issues(check_context, result)
            issues.extend(item for item in legacy if "상승 추세" not in item and "측정 모드" not in item)
    elif refs or period.start is not None or period.end is not None:
        issues.append("FFT 근거가 없으면 기간은 null, 참조 ID는 빈 배열로 작성하세요.")
    supported_causes: set[str] = set()
    for fft in inspected.values():
        diagnosis = fft.get("diagnosis") or {}
        mode = ((fft.get("measurement") or {}).get("measureMode") or {}).get("code")
        if diagnosis.get("status") != "analyzed":
            continue
        if mode == "3" and diagnosis.get("diagnosis") in {"unbalance", "misalignment"}:
            supported_causes.add(diagnosis["diagnosis"])
        if mode in {"0", "2"}:
            supported_causes.update(fault["type"] for fault in diagnosis.get("faults", [])
                                    if any(item.get("significant") for item in fault.get("harmonics", [])))
    cause_terms = {
        "unbalance": ("unbalance", "불평형", "언밸런스"),
        "misalignment": ("misalignment", "축정렬 불량", "축정렬 상태 불량", "정렬 불량", "미스얼라인"),
        "BPFI": ("bpfi", "내륜", "inner race"), "BPFO": ("bpfo", "외륜", "outer race"),
        "BSF": ("bsf", "전동체", "볼 결함", "rolling element"),
        "FTF": ("ftf", "케이지", "cage"),
    }
    diagnostic_texts = [result.headline, result.fft_summary,
                        *[f"{item.heading} {item.detail}" for item in result.fft_findings],
                        *[f"{item.cause} {item.rationale}" for item in result.likely_causes]]
    limitation_phrases = ("판정 불가", "단정할 수 없", "추정할 수 없", "판단할 수 없", "확정할 수 없",
                          "근거가 없", "확인되지", "여부를 확인", "여부는 추가", "판단하기 어렵")
    trend = context.get("trend") or {}
    velocity = next((metric for metric in trend.get("metrics", []) if metric.get("key") == "velocity"), None)
    insufficient_trend = trend.get("available") is False or (
        velocity is not None and velocity.get("sampleCount", 2) < 2
    )
    if insufficient_trend:
        shortage_terms = ("없", "부족", "불가", "어렵", "판단할 수", "제한", "충분하지")
        if not any(term in result.trend_summary for term in shortage_terms):
            issues.append("추세 자료가 없거나 비교 표본이 부족하다는 사유를 trendSummary에 명시하세요.")
        for text in [result.headline, result.trend_summary, *[item.detail for item in result.trend_findings]]:
            for sentence in re.split(r"[.!?\n](?!\d)", text):
                if any(term in sentence for term in ("상승", "증가", "감소", "하락", "우상향", "악화")) and not any(
                    term in sentence for term in (*limitation_phrases, "판단할 수 없", "판정할 수 없", "확인할 수 없", "자료가 부족")
                ):
                    issues.append("추세 비교 근거가 부족하므로 상승·하락 또는 상태 악화를 단정하지 마세요.")
    for text in diagnostic_texts:
        for sentence in re.split(r"[.!?\n](?!\d)", text.lower()):
            for cause, terms in cause_terms.items():
                if not any(term in sentence for term in terms):
                    continue
                if any(term in sentence for term in ("확실", "확정되", "명백", "고장 확정")):
                    issues.append("고장 원인을 확정하지 말고 근거에 따른 가능성과 확인 행동으로 작성하세요.")
                elif cause not in supported_causes and not any(phrase in sentence for phrase in limitation_phrases):
                    issues.append(f"{cause} 원인 후보를 지지하는 조회 FFT 근거가 없습니다. 판단 제한을 명시하세요.")
    # Compare measurements within their physical units, rather than any numeric field.
    trend_values: dict[str, list[float]] = {}
    for metric in context["trend"].get("metrics", []):
        values = [metric.get(key) for key in ("latestValue", "minimum", "maximum", "mean", "warningThreshold", "dangerThreshold")]
        values.extend(month["mean"] for month in metric.get("monthlyAverages", []))
        trend_values.setdefault(metric.get("unit"), []).extend(value for value in values if value is not None)
    fft_values: dict[str, list[float]] = {"Hz": []}
    def collect_fft(value: Any, unit: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, (float, int)) and not isinstance(child, bool):
                    if key in {"amplitude", "maxAmplitude", "largestPeak", "amplitudeThreshold"}:
                        fft_values.setdefault(unit, []).append(child)
                    if key in {"frequency", "targetFrequency", "detectedFrequency", "shaftFrequency"}:
                        fft_values["Hz"].append(child)
                elif isinstance(child, (dict, list)):
                    collect_fft(child, unit)
        elif isinstance(value, list):
            for child in value:
                collect_fft(child, unit)
    for fft in inspected.values():
        collect_fft(fft, fft.get("amplitudeUnit"))
    for summary, values_by_unit in ((result.trend_summary, trend_values), (result.fft_summary, fft_values)):
        for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mm/s|Hz|g)(?![A-Za-z])", summary):
            value = float(match[1])
            if not any(abs(value - actual) <= max(0.055, abs(actual) * 0.01) for actual in values_by_unit.get(match[2], [])):
                issues.append("요약의 측정값은 해당 그래프의 조회 근거 및 단위와 일치시켜 주세요.")
    if valid_period:
        for record_id in refs:
            if record_id in inspected and not period.start <= _timestamp(inspected[record_id]["measuredAt"]) <= period.end:
                issues.append("대표 FFT 기록은 비교 기간 안에 있어야 합니다.")
    return issues
