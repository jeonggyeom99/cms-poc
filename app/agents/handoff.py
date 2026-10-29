"""Server-owned evidence catalog, specialist contracts, and hand-off hydration."""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentName = Literal["trend", "fft", "history"]
CAUSE_TERMS = {
    "unbalance": ("unbalance", "불평형"), "misalignment": ("misalignment", "축정렬 불량", "정렬 불량"),
    "BPFO": ("bpfo", "외륜"), "BPFI": ("bpfi", "내륜"),
    "BSF": ("bsf", "전동체"), "FTF": ("ftf", "케이지"),
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Period(Contract):
    start: str | None
    end: str | None


class Evidence(Contract):
    evidence_id: str
    source: str
    source_record_id: str | None
    value: str | float | bool | None
    unit: str | None
    measured_at: str | None
    period: Period
    group_id: str | None
    kind: Literal["measurement", "aggregate", "rule", "history", "metadata"]
    supports_causes: list[str]
    measure_mode: str | None = None


class Finding(Contract):
    interpretation: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    relationship: Literal["observation", "comparison", "conflict"]


class Candidate(Contract):
    cause: str = Field(min_length=1, max_length=120)
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class AgentDraft(Contract):
    """LLM selects evidence; it never authors or rewrites source measurements."""
    agent_name: AgentName
    equipment_id: str
    analysis_period: Period
    status: Literal["ready", "limited"]
    summary: str = Field(min_length=1, max_length=500)
    findings: list[Finding] = Field(max_length=4)
    evidence_ids: list[str] = Field(min_length=1, max_length=128)
    source_record_ids: list[str] = Field(max_length=50)
    candidate_causes: list[Candidate] = Field(max_length=3)
    limitations: list[str] = Field(max_length=6)
    recommended_checks: list[str] = Field(max_length=4)


class FftAgentDraft(AgentDraft):
    summary: str = Field(min_length=1, max_length=1200)


class HistoryQuery(Contract):
    reference_fft_record_id: int | None
    cutoff_date: str | None
    fault_type: str | None
    selection_policy: str
    source_record_ids: list[str]


def history_queries(context: dict) -> list[HistoryQuery]:
    return [HistoryQuery(reference_fft_record_id=entry.get("recordId"),
              cutoff_date=entry.get("relatedHistory", {}).get("cutoffDate"),
              fault_type=(entry.get("relatedHistory", {}).get("faultTag") or {}).get("faultType"),
              selection_policy="same_equipment_and_same_fault_strictly_before_cutoff_limit_5",
              source_record_ids=[f"history:{item['sourceRecordId']}" for item in entry.get("relatedHistory", {}).get("items", [])
                                 if item.get("sourceRecordId") is not None])
            for entry in context.get("preparedFftEvidence", {}).get("relatedHistory", [])]


class Handoff(Contract):
    agent_name: AgentName
    equipment_id: str
    analysis_period: Period
    status: Literal["ready", "limited", "unavailable", "failed"]
    summary: str
    findings: list[Finding]
    evidence: list[Evidence]
    source_record_ids: list[str]
    candidate_causes: list[Candidate]
    limitations: list[str]
    recommended_checks: list[str]
    generated_at: str
    failure_codes: list[str]
    llm_success: bool
    source_queries: list[HistoryQuery]


def context_with_tool_evidence(context: dict, trace: list[dict]) -> dict:
    """Reconstruct queried History scope without mutating the shared Prefetch."""
    result = copy.deepcopy(context)
    entries = result.setdefault("preparedFftEvidence", {}).setdefault("relatedHistory", [])
    for call in trace:
        payload = call.get("result", {})
        if call.get("name") == "get_related_history" and payload.get("status") == "ready" and "relatedHistory" in payload:
            entry = {"recordId": payload["recordId"], "relatedHistory": payload["relatedHistory"]}
            if entry not in entries:
                entries.append(entry)
    return result


def analysis_period(name: str, context: dict) -> Period:
    if name == "trend":
        value = context.get("trend", {}).get("period", {})
    elif name == "fft":
        value = context.get("fftInventory", {})
    else:
        items = [item for entry in context.get("preparedFftEvidence", {}).get("relatedHistory", [])
                 for item in entry.get("relatedHistory", {}).get("items", [])]
        dates = sorted(item["date"] for item in items if item.get("date"))
        value = {"start": dates[0] if dates else None, "end": dates[-1] if dates else None}
    return Period(start=value.get("start"), end=value.get("end"))


def agent_inputs(name: str, context: dict) -> dict:
    prepared = context.get("preparedFftEvidence", {})
    if name == "trend":
        return {"trend": context.get("trend", {}), "levelAnalysis": context.get("levelAnalysis", {})}
    if name == "fft":
        from app.analysis.fft_severity import VELOCITY_LIMITS, ACCELERATION_LIMITS
        return {"criteria": [{"unit": unit, "amplitudeThreshold": bound} for unit, limits in
                             (("mm/s", VELOCITY_LIMITS), ("g", ACCELERATION_LIMITS)) for bound in limits],"groups": prepared.get("groups", []), "representativeRecords": prepared.get("representativeRecords", []),
                "unavailableRecordIds": prepared.get("unavailableRecordIds", []),
                "weekly": context.get("fftWeeklyDiagnosis", {})}
    return {"relatedHistory": prepared.get("relatedHistory", []),
            "selectionPolicy": "same equipment AND same fault; strictly before min(measured date, until); limit 5 per FFT"}


def evidence_catalog(name: str, context: dict, extra: list[dict] | None = None) -> dict[str, Evidence]:
    """Tie each scalar to its exact source path, physical unit, period and record."""
    catalog: dict[str, Evidence] = {}
    overall = analysis_period(name, context)
    skip = {"recordId", "id", "recordNumber", "sourceRecordId", "recordIds", "representativeRecordIds",
            "unavailableRecordIds", "peakRecordId", "start", "end", "measuredAt", "date",
            "cutoffDate", "generatedAt", "measurementPoint", "selectionPolicy"}
    amplitudes = {"amplitude", "maxAmplitude", "largestPeak", "amplitudeThreshold", "mean", "minimum", "maximum",
                  "latestValue", "normalMean", "warningThreshold", "dangerThreshold", "change30Days", "change90Days", "changeFromPreviousMonth"}
    frequencies = {"frequency", "detectedFrequency", "targetFrequency", "shaftFrequency", "frequencyRange", "frequencyResolution"}

    def walk(value: Any, path: str, unit: str | None = None, record: str | None = None,
             stamp: str | None = None, period: Period = overall, group: str | None = None,
             support: tuple[str, ...] = (), kind: str = "metadata", frequency_unit: str | None = "Hz",
             mode: str | None = None):
        if isinstance(value, dict):
            unit = value.get("amplitudeUnit", value.get("unit", unit))
            if path == "trend.levelAnalysis":
                unit = "mm/s"
                kind = "rule"
            if "frequencyUnit" in value:
                frequency_unit = value["frequencyUnit"]
            raw_mode = value.get("measureMode", ((value.get("measurement") or {}).get("measureMode") or {}).get("code"))
            if isinstance(raw_mode, str):
                mode = raw_mode
            raw_id = value.get("sourceRecordId") if name == "history" else value.get("recordId")
            if raw_id is not None:
                record = f"{name}:{raw_id}"
            stamp = value.get("measuredAt", value.get("date", value.get("latestAt", stamp) if "peakEvidence" not in value else stamp))
            if value.get("start") is not None or value.get("end") is not None:
                period = Period(start=value.get("start"), end=value.get("end"))
            if name == "fft" and "monthlyComponents" in value:
                frequency_unit = "Hz" if value.get("frequencyRange") else None
                group = "group:" + sha256(json.dumps({k: value.get(k) for k in
                    ("measureMode", "amplitudeUnit", "measurementPoint", "rpm", "frequencyRange", "lineCount")}, sort_keys=True).encode()).hexdigest()[:12]
            if name == "fft" and "diagnosis" in value and isinstance(value["diagnosis"], dict):
                diagnosis = value["diagnosis"]
                mode = ((value.get("measurement") or {}).get("measureMode") or {}).get("code")
                if frequency_unit == "Hz" and diagnosis.get("status") == "analyzed" and mode == "3" and diagnosis.get("diagnosis") in CAUSE_TERMS:
                    support = (diagnosis["diagnosis"],)
                # Resolve record's group from deterministic group membership.
                for item in context.get("preparedFftEvidence", {}).get("groups", []):
                    if value.get("recordId") in item.get("representativeRecordIds", []):
                        group = "group:" + sha256(json.dumps({k: item.get(k) for k in
                            ("measureMode", "amplitudeUnit", "measurementPoint", "rpm", "frequencyRange", "lineCount")}, sort_keys=True).encode()).hexdigest()[:12]
            if name == "fft" and value.get("type") in CAUSE_TERMS:
                support = (value["type"],) if frequency_unit == "Hz" and any(h.get("significant") for h in value.get("harmonics", [])) else ()
            if ".criteria" in path:
                kind = "rule"
            elif name == "history":
                kind = "history"
            elif ".analysis" in path or ".diagnosis" in path or ".severityAssessments" in path:
                kind = "rule"
            elif "monthly" in path or ".metrics" in path or path.endswith("weekly"):
                kind = "aggregate"
            elif record:
                kind = "measurement"
            for key, child in value.items():
                if key not in skip:
                    child_record, child_stamp = record, stamp
                    if key == "maxAmplitude" and isinstance(value.get("peakEvidence"), dict):
                        peak = value["peakEvidence"]
                        child_record = f"fft:{peak['recordId']}"
                        child_stamp = peak.get("measuredAt")
                    elif key == "latestAt":
                        child_record, child_stamp = None, child
                    walk(child, f"{path}.{key}", unit, child_record, child_stamp, period, group, support, kind, frequency_unit, mode)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", unit, record, stamp, period, group, support, kind, frequency_unit, mode)
        elif value is not None and isinstance(value, (str, int, float, bool)):
            key = path.rsplit(".", 1)[-1]
            physical = unit if key in amplitudes else frequency_unit if key in frequencies else "rpm" if key == "rpm" else "mm/s/hour" if key in {"slope", "slopeThreshold"} else None
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                if physical is None:
                    if ".countsByMode." in path or key.endswith("Count") or key in {"usedPoints", "requiredPoints", "count", "lineCount"}:
                        physical = "count"
                    elif key.endswith("IntervalHours"):
                        physical = "hour"
                    elif key in {"score", "totalScore", "highestScore"}:
                        physical = "score"
                    elif key in {"order", "harmonicOrder"}:
                        physical = "X"
                if not math.isfinite(value):
                    return
                value = float(value)
            eid = name[0] + ":" + str(len(catalog) + 1)
            catalog[eid] = Evidence(evidence_id=eid, source=path, source_record_id=record,
                value=value, unit=physical, measured_at=None if ".metrics" in path and key in {"mean", "minimum", "maximum"} else stamp, period=period, group_id=group,
                kind=kind, supports_causes=list(support), measure_mode=mode)

    walk(agent_inputs(name, context), name)
    for index, payload in enumerate(extra or []):
        walk(payload, f"{name}.tools[{index}]")
    return catalog


def offered_catalog(name: str, catalog: dict[str, Evidence], limit: int = 128) -> dict[str, Evidence]:
    """Bound prompt size while retaining each representative and condition group's facts.

    Full source compression remains server-side. Omitted detail is obtainable through
    the existing bounded tools; it is not silently exposed as a selectable citation.
    """
    if name != "fft" or len(catalog) <= limit:
        return catalog
    buckets: dict[str, list[Evidence]] = {}
    for fact in catalog.values():
        if "severityAssessments" in fact.source or ".spectrum.status" in fact.source:
            continue
        if fact.source.startswith("fft.representativeRecords"):
            category = "record:" + str(fact.source_record_id)
        elif fact.source.startswith("fft.weekly"):
            category = "weekly"
        else:
            category = "group:" + str(fact.group_id)
        buckets.setdefault(category, []).append(fact)
    def priority(fact: Evidence):
        return (-1 if ".peakEvidence." in fact.source else 0 if fact.supports_causes and fact.unit else
                1 if fact.unit else 2 if fact.source.endswith(("diagnosis", "status", "reason", "grade")) else 3,
                0 if ".latest." in fact.source or ".maximum." in fact.source else 1)
    for bucket in buckets.values():
        bucket.sort(key=priority)
    chosen = {}
    # Round-robin prevents a prolific first measurement mode swallowing all others.
    while len(chosen) < limit and any(buckets.values()):
        for bucket in buckets.values():
            if bucket and len(chosen) < limit:
                fact = bucket.pop(0)
                chosen[fact.evidence_id] = fact
    # Preserve citable measurement conditions alongside selected peaks. Conditions
    # are mandatory dependencies, so the base limit never silently drops them.
    records = {item.source_record_id for item in chosen.values() if item.source_record_id}
    groups = {item.group_id for item in chosen.values() if item.group_id}
    for eid, fact in catalog.items():
        condition = fact.source.endswith((".rpm", ".measureMode.code", ".amplitudeUnit", ".frequencyUnit",
                                          ".frequencyRange", ".frequencyResolution", ".lineCount"))
        if condition and ((fact.source_record_id and fact.source_record_id in records)
                          or (fact.group_id and fact.group_id in groups)):
            chosen[eid] = fact
        if fact.source.startswith("fft.weekly.") and (fact.source.endswith((".cause", ".causeLabel", ".count", ".totalScore", ".latestAt", ".grade"))
                                                      or ".countsByMode." in fact.source
                                                      or fact.source.startswith("fft.weekly.representative.peakEvidence.")):
            chosen[eid] = fact
    return measurement_dependencies(chosen, catalog)


def measurement_dependencies(selected: dict[str, Evidence], catalog: dict[str, Evidence]) -> dict[str, Evidence]:
    """Retain the exact sibling frequency/amplitude when selecting either citation."""
    result = dict(selected)
    prefixes = {f.source.rpartition(".")[0] for f in selected.values()
                if f.source.endswith((".amplitude", ".frequency", ".detectedFrequency"))}
    prefixes.update(f.source.rpartition(".")[0] + ".peakEvidence" for f in selected.values()
                    if f.source.endswith(".maxAmplitude"))
    for eid, fact in catalog.items():
        prefix, _, field = fact.source.rpartition(".")
        if prefix in prefixes and field in {"amplitude", "frequency", "detectedFrequency", "order", "harmonicOrder"}:
            result[eid] = fact
    return result


def measurement_bundles(catalog: dict[str, Evidence]) -> list[dict]:
    """Give the model complete observations without joining independent numeric rows."""
    grouped: dict[str, dict[str, Evidence]] = {}
    for fact in catalog.values():
        if fact.source.startswith("fft."):
            prefix, _, field = fact.source.rpartition(".")
            grouped.setdefault(prefix, {})[field] = fact
    bundles = []
    labels = {"0": "가속도 ALL", "2": "가속도 ENV", "3": "속도"}
    for source, fields in grouped.items():
        amplitude = fields.get("amplitude")
        if amplitude is None or not amplitude.source_record_id:
            continue
        frequency = fields.get("detectedFrequency", fields.get("frequency"))
        order = fields.get("harmonicOrder", fields.get("order"))
        ids = [fact.evidence_id for fact in (amplitude, frequency, order) if fact is not None]
        frequency_text = f"{frequency.value:g}{frequency.unit or ' (주파수 단위 미상)'}" if frequency else "검출 주파수 없음"
        bundles.append({"source": source, "evidence_ids": ids,
            "source_record_id": amplitude.source_record_id, "measured_at": amplitude.measured_at,
            "measure_mode": amplitude.measure_mode, "group_id": amplitude.group_id,
            "frequency": frequency.value if frequency else None, "frequency_unit": frequency.unit if frequency else None,
            "amplitude": amplitude.value, "amplitude_unit": amplitude.unit,
            "description": f"기록 {amplitude.source_record_id.split(':', 1)[1]} / {amplitude.measured_at or '측정일 미상'} / {labels.get(amplitude.measure_mode, '모드 미상')} / {frequency_text} / {amplitude.value:g}{amplitude.unit or ' (진폭 단위 미상)'}"})
    return bundles


def catalog_prompt(catalog: dict[str, Evidence]) -> dict:
    """Lossless table: factor repeated source prefixes, periods and conditions."""
    contexts, periods, rows = [], [], []
    for item in catalog.values():
        prefix, _, field = item.source.rpartition(".")
        period = [item.period.start, item.period.end]
        if period not in periods:
            periods.append(period)
        context = [prefix, periods.index(period), item.group_id]
        if context not in contexts:
            contexts.append(context)
        rows.append([item.evidence_id, item.value, item.unit, item.source_record_id,
                     item.measured_at, contexts.index(context), field, item.supports_causes, item.kind])
    return {"columns": ["evidence_id", "value", "unit", "source_record_id", "measured_at",
                        "context_id", "field", "supports_causes", "kind"],
            "context_columns": ["source_prefix", "period_id", "group_id"],
            "contexts": contexts, "periods": periods, "rows": rows,
            "measurements": measurement_bundles(catalog)}


class HandoffError(ValueError):
    def __init__(self, codes: list[str]):
        self.codes = sorted(set(codes))
        super().__init__(",".join(self.codes))


def hydrate_handoff(draft: AgentDraft, name: AgentName, context: dict, catalog: dict[str, Evidence],
                    period: Period | None = None) -> Handoff:
    """Attach server-owned provenance without comparing generated prose to facts."""
    ids = dict.fromkeys([*draft.evidence_ids,
        *[eid for item in draft.findings for eid in item.evidence_ids],
        *[eid for item in draft.candidate_causes for eid in item.evidence_ids]])
    linked = measurement_dependencies({eid: catalog[eid] for eid in ids if eid in catalog}, catalog)
    selected = [fact.model_copy(deep=True) for fact in linked.values()]
    return Handoff(agent_name=name,
        equipment_id=str(context.get("equipment", {}).get("id") or context.get("datasetId")),
        analysis_period=(period or analysis_period(name, context)).model_copy(deep=True),
        status=draft.status, summary=draft.summary, findings=copy.deepcopy(draft.findings),
        evidence=selected, source_record_ids=sorted({item.source_record_id for item in selected if item.source_record_id}),
        candidate_causes=copy.deepcopy(draft.candidate_causes), limitations=list(draft.limitations),
        recommended_checks=list(draft.recommended_checks), generated_at=datetime.now(timezone.utc).isoformat(),
        failure_codes=[], llm_success=True, source_queries=history_queries(context) if name == "history" else [])


def limited_handoff(name: AgentName, context: dict, catalog: dict[str, Evidence], codes: list[str], unavailable: bool = False) -> Handoff:
    # Source-only degraded result; never recycle an invalid model interpretation.
    facts = [item.model_copy(deep=True) for item in list(catalog.values())[:12]]
    if unavailable:
        limitation = ("HISTORY 자료 없음: 동일 설비·동일 결함이며 기준 측정일 이전인 과거 이력이 없습니다."
                      if name == "history" else f"{name.upper()} 자료 없음: 분석할 측정 자료가 없어 판단이 제한됩니다.")
    elif any(code in {"provider_unavailable", "rate_limited", "not_configured", "timeout"} for code in codes):
        limitation = f"{name.upper()} API 호출 실패: 분석 결과를 받아오지 못해 판단이 제한됩니다."
    else:
        limitation = f"{name.upper()} 분석 응답 처리 실패: 해석을 사용할 수 없어 판단이 제한됩니다."
    return Handoff(agent_name=name, equipment_id=str(context.get("equipment", {}).get("id") or context.get("datasetId")),
        analysis_period=analysis_period(name, context), status="unavailable" if unavailable else "failed",
        summary=limitation, findings=[], evidence=facts,
        source_record_ids=sorted({item.source_record_id for item in facts if item.source_record_id}),
        candidate_causes=[], limitations=[limitation], recommended_checks=["원본 자료와 측정 조건을 확인하세요."],
        generated_at=datetime.now(timezone.utc).isoformat(), failure_codes=codes, llm_success=False,
        source_queries=history_queries(context) if name == "history" else [])


def handoff_markdown(result: Handoff) -> str:
    """Render parsed narratives and server-owned source metadata for trace artifacts."""
    def clean(value: Any) -> str:
        return str(value).replace("\n", " ").replace("|", "\\|")
    lines = [f"## {result.agent_name.title()} Agent Result", "", "### Summary", f"- {clean(result.summary)}",
             f"- Status: {result.status}; LLM success: {result.llm_success}",
             f"- Period: {result.analysis_period.start} ~ {result.analysis_period.end}", "", "### Evidence"]
    for item in result.evidence:
        lines.append(f"- [{item.evidence_id}] {clean(item.source)}: {clean(item.value)} {item.unit or ''}; "
                     f"record={item.source_record_id}; measured={item.measured_at}; period={item.period.start}~{item.period.end}; group={item.group_id}")
    lines += ["", "### Observations"]
    lines += [f"- {clean(item.interpretation)} [{', '.join(item.evidence_ids)}]" for item in result.findings]
    lines += ["", "### Cause Hypotheses"]
    lines += [f"- {item.cause} ({item.confidence}): {clean(item.rationale)} [{', '.join(item.evidence_ids)}]" for item in result.candidate_causes]
    lines += ["", "### Limitations", *[f"- {clean(item)}" for item in result.limitations],
              "", "### Recommended Checks", *[f"- {clean(item)}" for item in result.recommended_checks]]
    if result.source_queries:
        lines += ["", "### Source Queries", *[f"- FFT #{item.reference_fft_record_id}; strictly before {item.cutoff_date}; fault={item.fault_type}; policy={item.selection_policy}; records={','.join(item.source_record_ids)}" for item in result.source_queries]]
    if result.failure_codes:
        lines += ["", "### Output Failures", "- " + ", ".join(result.failure_codes)]
    return "\n".join(lines) + "\n"
