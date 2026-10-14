"""Equipment-scoped evidence and bounded, model-selected FFT history queries."""

from __future__ import annotations

import calendar
import copy
from collections import OrderedDict
from threading import RLock
from time import monotonic
import json
import math
import re
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
Write all output in natural Korean. headline: 1-2 sentences, at most 140 characters, connecting
main changes, supported cause candidates and a practical inspection action. Detailed numbers
belong in the graph summaries and findings. trendSummary: 1-2 sentences about the latest
90 days (~3 months), monthly average changes and persistence. Only monthlyAverages.mean is a
monthly average; mark partialMonth periods as partial. A reading difference is not an average.
The recent 72-hour rule and the 3-month monthly averages describe different windows. You may
describe long-term increases supported by the monthly averages even when the short-term rule
is stable. Do not call isolated spikes a sustained increase. Describe missing data explicitly.
fftSummary: 2-3 connected paragraphs (up to 1200 Korean characters) connecting the historical
analysis and why the current weekly status was selected. Integrate ALL weeklyExplanationFacts
into this narrative (you may copy their exact sentences); do not use a separate heading.
Preserve dates, counts, grade points, competing causes, the peak date/mode/harmonic/value,
and the criterion range. Explain the count-first ranking and the selected cause's highest weekly
grade. Mention missing/partial data. Keep grade explanations separate from physical fault certainty.
Then connect observed historical harmonic changes, dominant components,
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
Keep all summaries and findings concise so the complete JSON fits the output budget.
Do not expose internal field names such as thresholdState, change30Days or recordId in prose.
Translate states into Korean and describe changes explicitly as 변화량, 증가 or 감소.
Round displayed readings to one or two decimals; retain the correct units and direction.
Only describe bearing faults supported by significant acceleration harmonics and shaft faults
supported by velocity evidence. Mention missing bearing metadata in counterEvidence when observed.
Include every requiredCounterEvidence limitation explicitly in counterEvidence; keep the
provided limitation labels so missing bearing 모델/제조사/형번 or 마스터/계수 remains clear.
Keep each findings list and recommendedActions to one or two essential items.
For changes, cite change30Days/change90Days or monthlyAverages.changeFromPreviousMonth from
the supplied Trend evidence; do not invent derived amounts. For FFT, report observed endpoints and the direction
of change rather than computing new differences or averages. Absence of a fault peak is a negative
finding, not a supported cause candidate; state that explicitly without naming it as a likely cause.

Style example only (fictional evidence; never copy its numbers or conclusions):
Trend has three full months with velocity means 3.5, 4.0, 4.5 mm/s. A velocity FFT has
shaft 1X=2.4 mm/s, 2X=1.2 mm/s, 3X=0.8 mm/s; ratios=0.5 and 0.333; deterministic
diagnosis=misalignment. Only when the actual evidence supports that diagnosis, write:
headline: 진동값의 지속적인 상승과 1X·2X·3X 성분이 확인되어 축정렬 상태 불량 가능성이 있습니다. 정렬 상태와 볼트 체결을 우선 점검하고, 조치 후 진동 추세를 재확인하세요.
trendSummary: 최근 3개월간 진동 속도 월평균이 약 3.5 → 4.5 mm/s로 점진적으로 상승했습니다. 일시적 변동보다 지속적인 상승이 관찰되어 설비 상태 변화를 점검할 필요가 있습니다.
fftSummary: 회전 주파수 1X 성분이 약 2.4 mm/s로 가장 크며, 2X·3X 성분과 비율도 축정렬 불량 가능성을 지지합니다. 커플링과 볼트 체결, 설치 조건을 추가 점검하세요.
If only shaft 1X supports unbalance, use 불평형 instead; do not infer misalignment from 1X alone.
If bearing metadata or comparable history is missing, clearly state the limitation instead
of copying the example's cause. Return the complete requested JSON schema, not just these three fields.
"""


def equipment_quality_issues(context: dict, result: AiDiagnosis, trace: list[dict]) -> list[str]:
    issues: list[str] = []
    prepared = context.get("preparedFftEvidence", {})
    groups = prepared.get("groups", [])
    inspected: dict[int, dict] = {item["recordId"]: item for item in prepared.get("representativeRecords", [])}
    for call in trace:
        payload = call["result"]
        if call["name"] == "get_fft_evidence" and payload.get("fft"):
            inspected[payload["fft"]["recordId"]] = payload["fft"]
        if call["name"] == "get_fft_history_evidence":
            for item in payload.get("records", []):
                inspected[item["recordId"]] = item["fft"]
    refs = result.fft_reference_record_ids
    if prepared.get("unavailableRecordIds") and not any(
        term in " ".join(result.counter_evidence) for term in ("해석", "읽지", "손상", "누락", "일부 FFT", "일부 주파수")
    ):
        issues.append("해석하지 못한 FFT 기록의 제한을 counterEvidence에 명시하세요.")
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
        stamps.update(_timestamp(sample["measuredAt"]) for group in groups
                      for month in group["monthlyComponents"] for component in month["components"].values()
                      for sample in (component["first"], component["latest"], component["minimum"], component["maximum"]))
        observed_dates = {stamp.date() for stamp in stamps if stamp is not None}
        valid_period = bool(
            period.start and period.end
            and period.start.date() in observed_dates and period.end.date() in observed_dates
            and period.start <= period.end
        )
        if not valid_period:
            allowed_dates = ", ".join(day.isoformat() for day in sorted(observed_dates))
            issues.append(
                "fftAnalysisPeriod는 조회한 FFT 기록의 실제 관측 날짜로 지정하세요. "
                f"사용 가능한 관측 날짜: {allowed_dates or '없음'}. "
                "start/end는 비교한 첫째/마지막 날짜로 지정하세요."
            )
    elif refs or period.start is not None or period.end is not None:
        issues.append("FFT 근거가 없으면 기간은 null, 참조 ID는 빈 배열로 작성하세요.")
    supported_causes: set[str] = set()
    for group in groups:
        supported_causes.update(cause for cause, count in group["supportedCauses"].items() if count > 0)
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
    amplitude_grades: dict[str, set[str]] = {}
    for fft in inspected.values():
        for assessment in fft.get("severityAssessments", []):
            if assessment.get("score") is not None:
                amplitude_grades.setdefault(assessment["cause"], set()).add(assessment["grade"])
    for cause in context.get("fftWeeklyDiagnosis", {}).get("causes", []):
        amplitude_grades.setdefault(cause["cause"], set()).add(cause["grade"])
    cause_terms = {
        "unbalance": ("unbalance", "불평형", "언밸런스"),
        "misalignment": ("misalignment", "축정렬 불량", "축정렬 상태 불량", "정렬 불량", "미스얼라인"),
        "BPFI": ("bpfi", "내륜", "inner race"), "BPFO": ("bpfo", "외륜", "outer race"),
        "BSF": ("bsf", "전동체", "볼 결함", "rolling element"),
        "FTF": ("ftf", "케이지", "cage"),
    }
    diagnostic_texts = [("headline", result.headline), ("fftSummary", result.fft_summary),
                        *[(f"fftFindings[{index}]", f"{item.heading} {item.detail}") for index, item in enumerate(result.fft_findings)],
                        *[(f"likelyCauses[{index}]", f"{item.cause} {item.rationale}") for index, item in enumerate(result.likely_causes)]]
    limitation_phrases = ("판정 불가", "단정할 수 없", "추정할 수 없", "판단할 수 없", "확정할 수 없",
                          "근거가 없", "확인되지", "여부를 확인", "여부는 추가", "판단하기 어렵",
                          "단정하기 어렵", "확정하기 어렵", "판정할 수 없", "확인할 수 없",
                          "확정하지", "단정하지", "지지하지")
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
    negative_findings = ("검출되지", "관측되지", "발견되지", "유의하지", "피크 없음", "피크가 없", "미만", "뚜렷하지")
    positive_claim = re.compile(
        r"가능성(?:이|은)?\s*(?:있|높|크|우선)|불량(?:이|은)?\s*우선|"
        r"의심(?:됩|된|돼|되므로|스럽)|추정(?:됩|된|되므로)|"
        r"후보(?:입니다|로|가\s*있|를\s*지지)|결함(?:이|은)\s*(?:확인되|확인됩|발생했|존재)|"
        r"(?:외륜|내륜|케이지|전동체|bpfo|bpfi|ftf|bsf|물리적)\s*결함입니다|"
        r"원인(?:입니다|일\s*가능|으로\s*판단)"
    )
    inspection_request = re.compile(r"(?:의\s*)?(?:여부|상태)(?:를|는|에\s*대한)?\s*(?:(?:추가|우선)\s*)?(?:확인|점검|검사)")
    for field, text in diagnostic_texts:
        for sentence in re.split(r"[.!?\n](?!\d)", text.lower()):
            # A negated support clause is a limitation, while later positive claims
            # in the same sentence must still be rejected.
            claim_text = re.sub(
                r"후보를\s*지지(?:하는)?[^,;]{0,80}?근거가\s*없",
                "", sentence,
            )
            claim_text = re.sub(r"원인으로\s*판단할\s*수\s*없", "", claim_text)
            for cause, terms in cause_terms.items():
                mentions = [match for term in terms
                            for match in re.finditer(re.escape(term).replace(r"\ ", r"\s*"), sentence)]
                if not mentions:
                    continue
                if any(term in sentence for term in ("확실", "확정되", "명백", "고장 확정")):
                    issues.append("고장 원인을 확정하지 말고 근거에 따른 가능성과 확인 행동으로 작성하세요.")
                elif cause not in supported_causes:
                    # Amplitude classification does not assert a physical fault cause.
                    grade_only = (not field.startswith("likelyCauses")
                                  and any(label in sentence for label in amplitude_grades.get(cause, set()))
                                  and any(word in sentence for word in ("진폭 기준", "등급", "주간 기준"))
                                  and not positive_claim.search(claim_text))
                    weekly_fact = (not field.startswith("likelyCauses")
                                   and cause in {item["cause"] for item in context.get("fftWeeklyDiagnosis", {}).get("causes", [])}
                                   and any(word in sentence for word in ("발생", "집계", "선정", "최고값", "진폭 등급이 반복"))
                                   and not positive_claim.search(claim_text))
                    observed_harmonic = (not field.startswith("likelyCauses")
                                         and re.search(r"(?:bpfi|bpfo|bsf|ftf)\s*[123]x", sentence)
                                         and re.search(r"\d\s*g(?![a-z])", sentence)
                                         and any(word in sentence for word in ("관찰", "관측", "증가", "감소"))
                                         and not positive_claim.search(claim_text))
                    if grade_only or weekly_fact or observed_harmonic:
                        continue
                    limited = any(phrase in sentence for phrase in (*limitation_phrases, *negative_findings))
                    direct_inspection = any(inspection_request.match(sentence[mention.end():].lstrip())
                                            for mention in mentions)
                    if (limited or direct_inspection) and not positive_claim.search(claim_text):
                        continue
                    issues.append(f"{cause} 원인 후보를 지지하는 조회 FFT 근거가 없습니다. 판단 제한을 명시하세요. ({field})")
    # Compare measurements within their physical units, rather than any numeric field.
    trend_values: dict[str, list[float]] = {}
    trend_changes: dict[str, list[float]] = {}
    for metric in context["trend"].get("metrics", []):
        values = [metric.get(key) for key in ("latestValue", "minimum", "maximum", "mean", "warningThreshold", "dangerThreshold")]
        values.extend(month["mean"] for month in metric.get("monthlyAverages", []))
        trend_values.setdefault(metric.get("unit"), []).extend(value for value in values if value is not None)
        changes = [metric.get("change30Days"), metric.get("change90Days")]
        changes.extend(month.get("changeFromPreviousMonth") for month in metric.get("monthlyAverages", []))
        trend_changes.setdefault(metric.get("unit"), []).extend(value for value in changes if value is not None)
    fft_values: dict[str, list[float]] = {"Hz": []}
    frequency_ranges = [fft["frequencyRange"] for fft in inspected.values()
                        if isinstance(fft.get("frequencyRange"), (float, int))]
    frequency_ranges.extend(group["frequencyRange"] for group in groups
                            if isinstance(group.get("frequencyRange"), (float, int)))
    frequency_resolutions = [group["frequencyResolution"] for group in groups
                            if isinstance(group.get("frequencyResolution"), (float, int))]
    frequency_resolutions.extend(fft["frequencyRange"] / fft["lineCount"] for fft in inspected.values()
                                 if isinstance(fft.get("frequencyRange"), (float, int))
                                 and isinstance(fft.get("lineCount"), int) and fft["lineCount"] > 0)
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
        limitation = (fft.get("diagnosticLimitation") or {}).get("code")
        required_terms = {
            "bearing_not_configured": ("모델", "제조사", "형번"),
            "bearing_not_found": ("마스터", "계수"),
        }.get(limitation)
        if required_terms and not any(term in " ".join(result.counter_evidence) for term in required_terms):
            issues.append("조회한 가속도 FFT의 베어링 정보 제한을 counterEvidence에 명시하세요.")
    for group in groups:
        for month in group["monthlyComponents"]:
            for component in month["components"].values():
                for key in ("first", "latest", "minimum", "maximum"):
                    collect_fft(component[key], group["amplitudeUnit"])
    weekly = context.get("fftWeeklyDiagnosis") or {}
    for cause in weekly.get("causes", []):
        peak = cause.get("peakEvidence") or {}
        if peak.get("amplitude") is not None:
            fft_values.setdefault(peak["unit"], []).append(peak["amplitude"])
        if peak.get("frequency") is not None:
            fft_values["Hz"].append(peak["frequency"])
    combined_values = {unit: list(values) for unit, values in trend_values.items()}
    for unit, values in fft_values.items():
        combined_values.setdefault(unit, []).extend(values)
    trend_parts = [("trendSummary", result.trend_summary), *[(f"trendFindings[{index}].detail", item.detail) for index, item in enumerate(result.trend_findings)]]
    fft_parts = [("fftSummary", result.fft_summary), *[(f"fftFindings[{index}].detail", item.detail) for index, item in enumerate(result.fft_findings)]]
    cause_parts = [("headline", result.headline), *[(f"likelyCauses[{index}].rationale", item.rationale) for index, item in enumerate(result.likely_causes)]]
    fft_text = " ".join(text for _, text in fft_parts)
    for sentence in re.split(r"[.!?\n](?!\d)", fft_text):
        if "mm/s" in sentence and re.search(r"\d\s*g(?![A-Za-z])", sentence) and any(
            word in sentence for word in ("증가", "감소", "상승", "하락")
        ):
            issues.append("서로 다른 측정 단위의 수치를 같은 변화 추세로 비교하지 마세요.")
    for label, parts, values_by_unit in (("추세", trend_parts, trend_values),
                                        ("주파수", fft_parts, fft_values),
                                        ("원인", cause_parts, combined_values)):
        for field, summary in parts:
            for sentence in re.split(r"[.!?\n](?!\d)", summary):
                for match in re.finditer(r"(?<![\w.])([+-]?\d+(?:\.\d+)?)\s*(mm/s|Hz|g)(?![A-Za-z])", sentence):
                    value = float(match[1])
                    candidates = list(values_by_unit.get(match[2], []))
                    # Explicit criterion bounds are policy values, not observations.
                    from app.analysis.fft_severity import VELOCITY_LIMITS, ACCELERATION_LIMITS
                    limits = VELOCITY_LIMITS if match[2] == "mm/s" else ACCELERATION_LIMITS if match[2] == "g" else ()
                    criterion = (match[2] in ("g", "mm/s")
                                 and any(word in sentence for word in ("진폭 기준", "구간", "범위"))
                                 and re.match(r"\s*(?:초과|미만|이하|이상)", sentence[match.end():]))
                    if criterion:
                        if value in limits:
                            continue
                        issues.append(f"{field}에 잘못된 판정 기준 {value:g} {match[2]}가 있습니다. weeklyExplanationFacts의 기준을 사용하세요.")
                        continue
                    metadata_prefix = re.search(r"(?:범위|분해능|해상도|대역)(?:\s*설정)?(?:은|는|이|가|:|=)?\s*(?:약\s*)?$", sentence[:match.start()])
                    metadata_suffix = re.match(r"\s*(?:의\s*)?(?:범위|분해능|해상도|대역|조건)", sentence[match.end():])
                    if match[2] == "Hz" and (metadata_prefix or metadata_suffix):
                        metadata_text = (metadata_prefix[0] if metadata_prefix else "") + (metadata_suffix[0] if metadata_suffix else "")
                        candidates = frequency_resolutions if any(term in metadata_text for term in ("분해능", "해상도")) else frequency_ranges
                    if label != "주파수" and any(term in sentence for term in ("변화", "증가", "감소", "상승", "하락", "차이", "대비", "변동", "차분", "증감", "change30Days", "change90Days", "changeFromPreviousMonth")):
                        candidates.extend(trend_changes.get(match[2], []))
                        if any(term in sentence for term in ("감소", "하락")):
                            candidates.extend(-change for change in trend_changes.get(match[2], []) if change < 0)
                    if any(abs(value - actual) <= max(0.055, abs(actual) * 0.01) for actual in candidates):
                        continue
                    detail = "해당 단위 수치는 삭제하고 근거 한계를 설명하세요."
                    if candidates:
                        nearest = min(candidates, key=lambda candidate: abs(candidate - value))
                        detail = f"{match[2]} 근거값 중 가장 가까운 값은 {nearest:.6g}입니다. 맞는 값을 사용하거나 근거가 없음을 설명하세요."
                    issues.append(f"{label}({field}) 요약에 근거가 없는 {value:g} {match[2]} 값이 있습니다. "
                                  "이 수치 표현을 삭제하거나 실제 도구 근거에 맞게 수정하세요. " + detail)
    if valid_period:
        for record_id in refs:
            if record_id in inspected and not period.start.date() <= _timestamp(inspected[record_id]["measuredAt"]).date() <= period.end.date():
                issues.append("대표 FFT 기록은 비교 기간 안에 있어야 합니다.")
    if inspected and not any(word in " ".join(item.action for item in result.recommended_actions)
                             for word in ("확인", "점검", "재측정", "측정", "검사")):
        issues.append("권장 점검에 실행 가능한 확인 또는 재측정 조치를 포함하세요.")
    issues.extend(weekly_summary_issues(context, result.fft_summary))
    return list(dict.fromkeys(issues))


def equipment_issue_codes(issues: list[str]) -> list[str]:
    """Stable, measurement-free rule identifiers for diagnostic logs."""
    rules = (
        ("140자", "headline_length"), ("종합 요약에", "headline_action"),
        ("fftReferenceRecordIds", "reference_records"), ("대표 FFT 기록 ID", "reference_records"),
        ("fftAnalysisPeriod", "observation_period"), ("비교 기간 안", "reference_period"),
        ("FFT 근거가 없으면", "missing_fft_evidence"), ("고장 원인을 확정", "definitive_cause"),
        ("원인 후보를 지지", "unsupported_cause"), ("추세 자료", "insufficient_trend"),
        ("추세 비교 근거", "unsupported_trend"), ("근거가 없는", "unsupported_measurement"),
        ("다른 측정 단위", "mixed_units"), ("베어링 정보 제한", "bearing_limitation"),
        ("권장 점검", "recommended_action"),
        ("해석하지 못한 FFT", "unavailable_records"),
    )
    codes = {next((code for token, code in rules if token in issue), "evidence_policy") for issue in issues}
    for issue in issues:
        if "원인 후보를 지지" in issue:
            codes.add("unsupported_cause:" + issue.split(" ", 1)[0])
        if "근거가 없는" in issue:
            field = re.search(r"\(([A-Za-z0-9\[\].]+)\)", issue)
            if field:
                codes.add("unsupported_measurement:" + field[1])
    return sorted(codes)


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


def weekly_summary_issues(context: dict, summary: str) -> list[str]:
    weekly = context.get("fftWeeklyDiagnosis")
    if weekly is None:
        return []
    text = re.sub(r"\s+", "", summary).lower()
    required = []
    if weekly.get("start"):
        required.extend((weekly['start'][:10], weekly['end'][:10]))
    cause = weekly.get("representative")
    if cause:
        peak = cause['peakEvidence']
        required.append({"0": "가속도ALL", "2": "가속도ENV", "3": "속도"}[peak["measureMode"]])
        required.extend((cause['causeLabel'].lower(), cause['grade'], f"{cause['count']}건", f"{cause['totalScore']}점",
                         peak['measuredAt'][:10], f"{peak['harmonicOrder']}x", f"{peak['amplitude']:.4f}", "발생횟수", "최고등급"))
        from app.analysis.fft_severity import grade_criterion
        required.append(grade_criterion(cause['unit'], cause['highestScore']))
        for other in weekly['causes']:
            required.extend((other['causeLabel'].lower(), f"{other['count']}건"))
    else:
        required.append(weekly['label'])
    if weekly.get('limitation') and weekly.get('start'):
        required.append('제한')
    missing = [item for item in required if re.sub(r"\s+", "", item).lower() not in text]
    for item in weekly.get("causes", []):
        label = re.escape(re.sub(r"\s+", "", item["causeLabel"]).lower())
        if not re.search(label + rf"(?:은|는|이|가|:)?{item['count']}건.{{0,8}}?{item['totalScore']}점", text):
            missing.append(f"{item['causeLabel']} {item['count']}건·{item['totalScore']}점")
    return ["fftSummary에 주간 상태 선정 근거를 빠짐없이 통합하세요. weeklyExplanationFacts의 문장을 그대로 사용하면 됩니다. 누락: " + ', '.join(missing)] if missing else []
