"""Equipment-scoped evidence and bounded, model-selected FFT history queries."""

from __future__ import annotations

import calendar
import copy
from collections import OrderedDict
from threading import RLock
from time import monotonic
import json
import math
from datetime import date, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.ai_analysis import (
    AiAnalysisPeriod, AiDiagnosis, _fft_summary, _timestamp, _trend_summary, build_ai_context,
)
from app.analysis.trend import analyze_velocity_trend
from app.services.history import _same_equipment
from app.data_loader import load_fft_record


PAGE_SIZE = 50
_PREFETCH_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_PREFETCH_LOCK = RLock()
_PREFETCH_LIMIT = 32


def _source_fingerprint(dataset_id: str, dataset: dict, history: list[dict], until: date | None) -> str:
    fft = dataset.get("fft") or {}
    source = {"datasetId": dataset_id, "until": str(until), "version": "prefetch-source-v2",
              "trend": dataset.get("trend"), "fft": fft.get("_recordsById", fft),
              "rpm": fft.get("_rpm"), "bearing": fft.get("_bearing"),
              "history": [item for item in history if _same_equipment(item, dataset.get("equipment"), dataset_id)],
              "equipment": dataset.get("equipment"), "level": dataset.get("levelAnalysis"),
              "warning": dataset.get("_warningStatus")}
    return sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()



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
    dated_sorted = sorted(dated, key=lambda item: item[0])
    intervals = [(right[0] - left[0]).total_seconds() / 3600 for left, right in zip(dated_sorted, dated_sorted[1:])
                 if left[0] >= start and right[0] > left[0]]
    result["sampling"] = {"assumedIntervalHours": 1, "minimumIntervalHours": min(intervals) if intervals else None,
                          "maximumIntervalHours": max(intervals) if intervals else None,
                          "hourlyAssumptionMet": bool(intervals) and all(abs(value - 1) < 1e-6 for value in intervals),
                          "operationStateAvailable": False}
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
        for index, month in enumerate(metric["monthlyAverages"]):
            month["changeFromPreviousMonth"] = (
                round(month["mean"] - metric["monthlyAverages"][index - 1]["mean"], 6) if index else None
            )
    return result


def build_equipment_context(dataset_id: str, dataset: dict[str, Any], history: list[dict], until: date | None, *, force: bool = False) -> dict:
    fingerprint = _source_fingerprint(dataset_id, dataset, history, until)
    with _PREFETCH_LOCK:
        cached = _PREFETCH_CACHE.get(fingerprint)
        if not force and cached and monotonic() - cached[0] < 86400:
            _PREFETCH_CACHE.move_to_end(fingerprint)
            return copy.deepcopy(cached[1])
    fft = dataset.get("fft") or {}
    context = build_ai_context(dataset_id, dataset, fft, history, None, until)
    from app.services.fft_status import weekly_fft_diagnosis, weekly_explanation_facts
    context["equipmentAnalysis"] = True
    context["datasetId"] = dataset_id
    context["scope"] = "설비 전체 이력을 바탕으로 한 CMS 보조 분석"
    context["trend"] = recent_trend_evidence(dataset)
    if not fft:
        context["fft"] = {"available": False}
    records = sorted(fft.get("records", []), key=lambda item: (item["measuredAt"], item["id"]))
    context["fftInventory"] = {
        "count": len(records), "start": records[0]["measuredAt"] if records else None,
        "end": records[-1]["measuredAt"] if records else None,
        "measureModes": sorted({item["measureMode"]["code"] for item in records}),
        "observationDatesByMode": {
            mode: sorted({_timestamp(item["measuredAt"]).date().isoformat()
                          for item in records if item["measureMode"]["code"] == mode})
            for mode in sorted({item["measureMode"]["code"] for item in records})
        },
        "pageSize": PAGE_SIZE,
    }
    context["sourceFingerprint"] = fingerprint
    context["dataQuality"]["notes"] = [note for note in context["dataQuality"]["notes"] if "Trend" not in note]
    if not context["trend"].get("available"):
        context["dataQuality"]["notes"].append("최근 3개월 추세 데이터가 없습니다.")
    from app.equipment_evidence import prepare_fft_evidence
    decoded_records: dict[int, dict] = {}
    context["preparedFftEvidence"] = prepare_fft_evidence(dataset_id, dataset, history, until, records_cache=decoded_records)
    context["fftWeeklyDiagnosis"] = weekly_fft_diagnosis(fft, records_cache=decoded_records)
    context["weeklyExplanationFacts"] = weekly_explanation_facts(context["fftWeeklyDiagnosis"])
    context["requiredCounterEvidence"] = list(dict.fromkeys(
        item["diagnosticLimitation"]["label"] for item in
        context["preparedFftEvidence"]["representativeRecords"] if item.get("diagnosticLimitation")
    ))
    if context["preparedFftEvidence"]["unavailableRecordIds"]:
        context["requiredCounterEvidence"].append("일부 FFT 기록을 해석하지 못해 이력 비교에 제한이 있습니다.")
    with _PREFETCH_LOCK:
        _PREFETCH_CACHE[fingerprint] = (monotonic(), copy.deepcopy(context))
        _PREFETCH_CACHE.move_to_end(fingerprint)
        while len(_PREFETCH_CACHE) > _PREFETCH_LIMIT:
            _PREFETCH_CACHE.popitem(last=False)
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
    cache: dict[int, dict] = {item["recordId"]: item for item in
                             context.get("preparedFftEvidence", {}).get("representativeRecords", [])}

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
The initial user context already contains Trend, configured levels, complete FFT history
compression, representative FFT records and their related history. Normally write the diagnosis
immediately without calling tools. Query only missing evidence essential to the diagnosis;
do not retrieve information already supplied. At most 2 additional tool rounds and 4 calls
are allowed. Choose comparison dates and representative records from supplied evidence.
monthlyComponents contain observed first/latest/minimum/maximum samples, NOT averages.
Every sample links a real recordId and measuredAt. All successfully inspected records contribute
to these summaries; unavailableRecordIds identifies uninspected records. Cite only transmitted
samples, representatives or additional tool results. supportedCauses counts deterministic
diagnoses across the complete comparable group, not a diagnosis of every individual record.
When nextOffset is present in additional queries, fetch the next page with identical filters
or describe uninspected portions in counterEvidence. No-data results are limitations, not normality.
Compare only the same measurement mode, unit and measurement point. Changes in RPM or
frequency resolution limit comparisons. Explain when shaft 1X or other components started
increasing using actual observed dates and amplitudes. Sparse observations bound the onset
interval; they do not establish the exact day deterioration began.
Write all output in natural Korean. Use source numbers and dates naturally with correct units.
headline: two connected paragraphs, at most 700 characters. First connect equipment state,
Trend and FFT observations to possible causes; then explain priority inspection and judgment
after remeasurement under the same conditions. trendSummary: 2-3 connected paragraphs within
500 characters, starting with the latest measurement date, velocity and unit and comparison
with configured caution/danger criteria. Follow with observed rise onset/acceleration and
monitoring or additional checks, using the latest 90 days (~3 months), monthly average changes
and persistence. Do not invent a rise onset date. Only monthlyAverages.mean is a
monthly average; mark partialMonth periods as partial. A reading difference is not an average.
The recent 72-hour rule and the 3-month monthly averages describe different windows. You may
describe long-term increases supported by the monthly averages even when the short-term rule
is stable. Do not call isolated spikes a sustained increase. Describe missing data explicitly.
fftSummary: 2-3 connected paragraphs (up to 1200 Korean characters), starting with the
measurement mode and main cause candidates, then interpreting observed harmonic patterns,
and ending with practical inspection. Use relevant weeklyExplanationFacts when useful;
do not repeat every weekly fact or create a citation table. Detailed weekly grades remain
available in the server status cards. Mention missing/partial data and keep grade explanations
separate from physical fault certainty. Connect observed historical harmonic changes,
dominant components, supported hypotheses and practical additional checks.
A dominant shaft 1X alone does not establish
misalignment: check 2X/3X and their ratios. Bearing defect harmonics and shaft harmonics differ;
never mix acceleration g with velocity mm/s or compare different modes as one time series.
fftAnalysisPeriod.start/end: actual first/last FFT observation timestamps used for comparison,
without adding timezone offsets to timestamps whose timezone is unknown.
fftReferenceRecordIds: unique IDs with inspected FFT evidence, most important representative first.
List metadata alone does not establish harmonic amplitudes. If no FFT evidence is available,
return null period boundaries and an empty reference list. State evidence limitations and never
invent numbers, deterioration dates or causes. These equipment instructions replace the earlier
single-record headline mode requirements and short-term-only rising rule.
Keep all summaries and findings concise so the complete JSON fits the output budget.
Do not expose internal field names such as thresholdState, change30Days or recordId in prose.
Translate states into Korean and describe changes explicitly as 변화량, 증가 or 감소.
Round displayed readings to one or two decimals; retain the correct units and direction.
Express physical cause candidates as hypotheses, with additional checks. Do not restrict
hypotheses to deterministic supported cause codes. Mention missing bearing metadata in counterEvidence when observed.
Include every requiredCounterEvidence limitation explicitly in counterEvidence; keep the
provided limitation labels so missing bearing 모델/제조사/형번 or 마스터/계수 remains clear.
historyFindings: up to three items about actual retrieved equipment/fault cases, recorded actions
and post-action checks, followed by conditional recommendations for the current equipment.
When no similar cases or action outcomes were supplied, state the limitation; do not invent them.
Keep each other findings list and recommendedActions to one or two essential items. Avoid
repeating the same conclusion across headline, summaries and findings.
For changes, cite change30Days/change90Days or monthlyAverages.changeFromPreviousMonth from
the supplied Trend evidence; do not invent derived amounts. For FFT, report observed endpoints and the direction
of change rather than computing new differences or averages. Absence of a fault peak is a negative
finding; explain its limits when proposing a physical cause hypothesis.

If only shaft 1X supports unbalance, use 불평형 instead; do not infer misalignment from 1X alone.
If bearing metadata or comparable history is missing, clearly state the limitation instead
of forcing a cause. Return the complete requested JSON schema.
"""


def normalize_equipment_period_timezone(result: AiDiagnosis, trace: list[dict], context: dict | None = None) -> AiDiagnosis:
    """Do not invent timezone information for source measurements stored as naive timestamps."""
    observations = [item["measuredAt"] for item in
                    (context or {}).get("preparedFftEvidence", {}).get("representativeRecords", [])]
    observations.extend(sample["measuredAt"] for group in
                        (context or {}).get("preparedFftEvidence", {}).get("groups", [])
                        for month in group["monthlyComponents"] for component in month["components"].values()
                        for sample in (component["first"], component["latest"], component["minimum"], component["maximum"]))
    for call in trace:
        payload = call["result"]
        if call["name"] == "get_fft_evidence" and payload.get("fft"):
            observations.append(payload["fft"].get("measuredAt"))
        if call["name"] == "get_fft_history_evidence":
            observations.extend(item.get("measuredAt") for item in payload.get("records", []))
    timestamps = [_timestamp(stamp) for stamp in observations]
    timestamps = [stamp for stamp in timestamps if stamp is not None]
    period = result.fft_analysis_period
    if timestamps and all(stamp.tzinfo is None for stamp in timestamps):
        start_day = period.start.date() if period.start else None
        end_day = period.end.date() if period.end else None
        start_observations = [stamp for stamp in timestamps if stamp.date() == start_day]
        end_observations = [stamp for stamp in timestamps if stamp.date() == end_day]
        result.fft_analysis_period = AiAnalysisPeriod(
            start=min(start_observations) if start_observations else period.start.replace(tzinfo=None) if period.start else None,
            end=max(end_observations) if end_observations else period.end.replace(tzinfo=None) if period.end else None,
        )
    return result
