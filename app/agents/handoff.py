"""Server-owned evidence catalog, specialist contracts, and hand-off validation."""
from __future__ import annotations

import copy
import json
import math
import re
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


class Finding(Contract):
    interpretation: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    relationship: Literal["observation", "comparison", "conflict"]


class Candidate(Contract):
    cause: Literal["unbalance", "misalignment", "BPFO", "BPFI", "BSF", "FTF"]
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
            "unavailableRecordIds", "peakRecordId", "start", "end", "measuredAt", "date", "latestAt",
            "cutoffDate", "generatedAt", "measurementPoint", "selectionPolicy"}
    amplitudes = {"amplitude", "maxAmplitude", "largestPeak", "amplitudeThreshold", "mean", "minimum", "maximum",
                  "latestValue", "normalMean", "warningThreshold", "dangerThreshold", "change30Days", "change90Days", "changeFromPreviousMonth"}
    frequencies = {"frequency", "detectedFrequency", "targetFrequency", "shaftFrequency", "frequencyRange", "frequencyResolution"}

    def walk(value: Any, path: str, unit: str | None = None, record: str | None = None,
             stamp: str | None = None, period: Period = overall, group: str | None = None,
             support: tuple[str, ...] = (), kind: str = "metadata", frequency_unit: str | None = "Hz"):
        if isinstance(value, dict):
            unit = value.get("amplitudeUnit", value.get("unit", unit))
            if path == "trend.levelAnalysis":
                unit = "mm/s"
                kind = "rule"
            if "frequencyUnit" in value:
                frequency_unit = value["frequencyUnit"]
            raw_id = value.get("sourceRecordId") if name == "history" else value.get("recordId")
            if raw_id is not None:
                record = f"{name}:{raw_id}"
            stamp = value.get("measuredAt", value.get("date", value.get("latestAt", stamp)))
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
                    walk(child, f"{path}.{key}", unit, record, stamp, period, group, support, kind, frequency_unit)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", unit, record, stamp, period, group, support, kind, frequency_unit)
        elif value is not None and isinstance(value, (str, int, float, bool)):
            key = path.rsplit(".", 1)[-1]
            physical = unit if key in amplitudes else frequency_unit if key in frequencies else "rpm" if key == "rpm" else "mm/s/hour" if key in {"slope", "slopeThreshold"} else None
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                if physical is None:
                    if key.endswith("Count") or key in {"usedPoints", "requiredPoints", "count", "lineCount"}:
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
                kind=kind, supports_causes=list(support))

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
        return (0 if fact.supports_causes and fact.unit else
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
    return chosen


def catalog_prompt(catalog: dict[str, Evidence]) -> dict:
    """Compact tabular encoding of immutable facts, with explicit column names."""
    return {"columns": ["evidence_id", "source", "value", "unit", "source_record_id", "measured_at", "period", "group_id", "supports_causes"],
            "rows": [[item.evidence_id, item.source, item.value, item.unit, item.source_record_id,
                      item.measured_at, [item.period.start, item.period.end], item.group_id, item.supports_causes]
                     for item in catalog.values()]}


class HandoffError(ValueError):
    def __init__(self, codes: list[str]):
        self.codes = sorted(set(codes))
        super().__init__(",".join(self.codes))


def prose_issues(text: str, evidence: list[Evidence]) -> list[str]:
    """Check physical values AND their claimed observation date as a single fact.

    An aggregate's period boundary is not a dated observation. Free prose remains
    secondary to exact structured citations; uncertain/negative clauses are allowed.
    """
    issues = []
    measurements = list(re.finditer(r"(?<![\w.])([+-]?\d+(?:\.\d+)?)\s*(mm/s/hour|mm/s|Hz|rpm|g)(?![A-Za-z])", text))
    for match in measurements:
        actual, unit = float(match[1]), match[2]
        allowed = [item for item in evidence if item.unit == unit
                   and isinstance(item.value, (int, float)) and not isinstance(item.value, bool)
                   and abs(actual - float(item.value)) <= max(0.005, abs(float(item.value)) * 0.0001)]
        if not allowed:
            issues.append("unsupported_measurement")
            continue
        # Associate the value with the nearest preceding date in its sentence.
        boundaries = list(re.finditer(r"[。.!?\n](?!\d)", text[:match.start()]))
        sentence_start = boundaries[-1].end() if boundaries else 0
        prefix = text[sentence_start:match.start()]
        date_pattern = r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?"
        dates = list(re.finditer(date_pattern, prefix))
        after_boundary = re.search(r"[。.!?\n](?!\d)", text[match.end():])
        suffix = text[match.end():match.end() + after_boundary.start()] if after_boundary else text[match.end():]
        following_dates = list(re.finditer(date_pattern, suffix))
        if dates or following_dates:
            claimed = (dates[-1][0] if dates else following_dates[0][0]).replace("T", " ")
            aggregate_language = bool(re.search(r"평균|집계|기간|월별|기울기|임계|기준|mean|average", prefix + suffix, re.I))
            dated_observation = any(item.measured_at and item.measured_at.replace("T", " ").startswith(claimed)
                                   and not (item.kind == "aggregate" and item.source.endswith((".mean", ".minimum", ".maximum")))
                                   for item in allowed)
            dated_aggregate = aggregate_language and any(
                item.kind in {"aggregate", "rule"} and item.period.start and item.period.end
                and item.period.start[:10] <= claimed[:10] <= item.period.end[:10] for item in allowed)
            if not dated_observation and not dated_aggregate:
                issues.append("measurement_date_mismatch")
    dates = set()
    for item in evidence:
        for stamp in (item.measured_at, item.period.start, item.period.end):
            if stamp:
                dates.add(stamp[:10])
        if isinstance(item.value, str):
            dates.update(re.findall(r"\d{4}-\d{2}-\d{2}", item.value))
    if any(stamp not in dates for stamp in re.findall(r"\d{4}-\d{2}-\d{2}", text)):
        issues.append("unsupported_date")
    for sentence in re.split(r"[。.!?\n](?!\d)|[,;]|하지만|그러나|반면", text):
        uncertain = bool(re.search(r"확정(?:할 수 없|하지|하기 어렵)|단정(?:할 수 없|하지|하기 어렵)|확인되지|근거가 없", sentence))
        grade_only = bool(re.search(r"진폭\s*기준|등급", sentence)) and bool(re.search(r"초기 결함|심각|정지|베어링 교체|양호", sentence)) and not re.search(r"확정|물리적|실제\s*결함|고장|결함(?:이|은)\s*확인", sentence)
        if not uncertain and not grade_only and re.search(r"(?:불평형|축정렬\s*불량|정렬\s*불량)(?:이|은)?\s*(?:입니다|이다|확실|명백|발생했|존재)|확정(?:되|됩|된|입니다)|고장\s*확정|(?:결함|고장)(?:이|은|으로)?\s*(?:확인되|확인됩|확인했|존재|발생했|입니다)|definitely|confirmed defect", sentence, re.I):
            issues.append("unsupported_certainty")
    return issues


def validate_draft(draft: AgentDraft, name: str, context: dict, catalog: dict[str, Evidence],
                   period: Period | None = None) -> Handoff:
    codes = []
    if draft.agent_name != name or draft.equipment_id != str(context.get("equipment", {}).get("id") or context.get("datasetId")):
        codes.append("identity_mismatch")
    if draft.analysis_period != (period or analysis_period(name, context)):
        codes.append("analysis_period_mismatch")
    # Findings/candidates are themselves selections. Hydrate their union instead
    # of asking the model to duplicate every citation in a second top-level list.
    ids = list(dict.fromkeys([*draft.evidence_ids,
          *[eid for item in draft.findings for eid in item.evidence_ids],
          *[eid for item in draft.candidate_causes for eid in item.evidence_ids]]))
    if len(draft.evidence_ids) != len(set(draft.evidence_ids)):
        codes.append("duplicate_evidence")
    if len(ids) != len(set(ids)) or any(eid not in catalog for eid in ids):
        codes.append("unknown_evidence")
    selected = [catalog[eid].model_copy(deep=True) for eid in ids if eid in catalog]
    expected_records = sorted({item.source_record_id for item in selected if item.source_record_id})
    available_records = {item.source_record_id for item in catalog.values() if item.source_record_id}
    if any(record_id not in available_records for record_id in draft.source_record_ids) or len(draft.source_record_ids) != len(set(draft.source_record_ids)):
        codes.append("source_record_mismatch")
    codes.extend(prose_issues(draft.summary + " " + " ".join(draft.limitations + draft.recommended_checks), selected))
    for finding in draft.findings:
        facts = [catalog[eid] for eid in finding.evidence_ids if eid in ids and eid in catalog]
        if len(facts) != len(finding.evidence_ids):
            codes.append("finding_evidence_mismatch")
        codes.extend(prose_issues(finding.interpretation, facts))
        if finding.relationship == "comparison" and name == "fft":
            groups = {item.group_id for item in facts}
            if None in groups or len(groups) != 1:
                codes.append("incompatible_measurement_conditions")
            source_groups = context.get("preparedFftEvidence", {}).get("groups", [])
            if not source_groups or any(item.get(key) is None for item in source_groups for key in
                                         ("rpm", "measurementPoint", "frequencyRange", "lineCount")
                                         if "group:" + sha256(json.dumps({k: item.get(k) for k in
                                             ("measureMode", "amplitudeUnit", "measurementPoint", "rpm", "frequencyRange", "lineCount")}, sort_keys=True).encode()).hexdigest()[:12] in groups):
                codes.append("unknown_measurement_conditions")
    for cause in draft.candidate_causes:
        facts = [catalog[eid] for eid in cause.evidence_ids if eid in ids and eid in catalog]
        if len(facts) != len(cause.evidence_ids) or not any(cause.cause in item.supports_causes for item in facts):
            codes.append("unsupported_cause")
        codes.extend(prose_issues(cause.rationale, facts))
    # A historical case never establishes the current physical defect.
    if name != "fft" and draft.candidate_causes:
        codes.append("unsupported_cause")
    supported = {cause for item in selected for cause in item.supports_causes}
    positive = r"의심|가능성(?:이|은)?\s*(?:있|높)|결함(?:이|은)?\s*(?:확인|발생)|원인입니다"
    for text, cited_support in [(draft.summary, supported), *[(finding.interpretation,
            {cause for eid in finding.evidence_ids if eid in catalog for cause in catalog[eid].supports_causes})
            for finding in draft.findings]]:
        for cause, terms in CAUSE_TERMS.items():
            if name != "history" and cause not in cited_support and any(term in text.lower() for term in terms) and re.search(positive, text):
                codes.append("unsupported_cause")
    if codes:
        raise HandoffError(codes)
    return Handoff(agent_name=draft.agent_name, equipment_id=draft.equipment_id,
        analysis_period=draft.analysis_period, status=draft.status, summary=draft.summary,
        findings=draft.findings, evidence=selected, source_record_ids=expected_records,
        candidate_causes=draft.candidate_causes, limitations=draft.limitations,
        recommended_checks=draft.recommended_checks, generated_at=datetime.now(timezone.utc).isoformat(),
        failure_codes=[], llm_success=True, source_queries=history_queries(context) if name == "history" else [])


def validate_handoff(result: Handoff, catalog: dict[str, Evidence], context: dict) -> None:
    """Recheck hydrated JSON: altered units, values, dates and IDs cannot cross the boundary."""
    codes = []
    if result.analysis_period != analysis_period(result.agent_name, context):
        codes.append("analysis_period_mismatch")
    if result.equipment_id != str(context.get("equipment", {}).get("id") or context.get("datasetId")):
        codes.append("identity_mismatch")
    if result.source_queries != (history_queries(context) if result.agent_name == "history" else []):
        codes.append("history_query_mismatch")
    expected_records = sorted({item.source_record_id for item in result.evidence if item.source_record_id})
    if result.source_record_ids != expected_records:
        codes.append("source_record_mismatch")
    for item in result.evidence:
        if item.evidence_id not in catalog or item != catalog[item.evidence_id] or type(item.value) is not type(catalog[item.evidence_id].value):
            codes.append("source_evidence_mismatch")
    if result.llm_success:
        draft = AgentDraft(**result.model_dump(exclude={"evidence", "generated_at", "failure_codes", "llm_success", "source_queries"}),
                           evidence_ids=[item.evidence_id for item in result.evidence])
        validate_draft(draft, result.agent_name, context, catalog, result.analysis_period)
    if codes:
        raise HandoffError(codes)


def limited_handoff(name: AgentName, context: dict, catalog: dict[str, Evidence], codes: list[str], unavailable: bool = False) -> Handoff:
    # Source-only degraded result; never recycle an invalid model interpretation.
    facts = [item.model_copy(deep=True) for item in list(catalog.values())[:12]]
    limitation = f"{name.upper()} 분석 {'자료 없음' if unavailable else '실패'}: 전문 LLM 해석을 사용할 수 없어 판단이 제한됩니다."
    return Handoff(agent_name=name, equipment_id=str(context.get("equipment", {}).get("id") or context.get("datasetId")),
        analysis_period=analysis_period(name, context), status="unavailable" if unavailable else "failed",
        summary=limitation, findings=[], evidence=facts,
        source_record_ids=sorted({item.source_record_id for item in facts if item.source_record_id}),
        candidate_causes=[], limitations=[limitation], recommended_checks=["원본 자료와 측정 조건을 확인하세요."],
        generated_at=datetime.now(timezone.utc).isoformat(), failure_codes=codes, llm_success=False,
        source_queries=history_queries(context) if name == "history" else [])


def handoff_markdown(result: Handoff) -> str:
    """Pure rendering of validated JSON; also used verbatim as synthesis input."""
    def clean(value: Any) -> str:
        return str(value).replace("\n", " ").replace("|", "\\|")
    lines = [f"## {result.agent_name.title()} Agent Result", "", "### Summary", f"- {clean(result.summary)}",
             f"- Status: {result.status}; LLM success: {result.llm_success}",
             f"- Period: {result.analysis_period.start} ~ {result.analysis_period.end}", "", "### Evidence"]
    for item in result.evidence:
        lines.append(f"- [{item.evidence_id}] {clean(item.source)}: {clean(item.value)} {item.unit or ''}; "
                     f"record={item.source_record_id}; measured={item.measured_at}; period={item.period.start}~{item.period.end}; group={item.group_id}")
    lines += ["", "### Interpretation"]
    lines += [f"- {clean(item.interpretation)} [{', '.join(item.evidence_ids)}]" for item in result.findings]
    lines += [f"- {item.cause} ({item.confidence}): {clean(item.rationale)} [{', '.join(item.evidence_ids)}]" for item in result.candidate_causes]
    lines += ["", "### Limitations", *[f"- {clean(item)}" for item in result.limitations],
              "", "### Recommended Checks", *[f"- {clean(item)}" for item in result.recommended_checks]]
    if result.source_queries:
        lines += ["", "### Source Queries", *[f"- FFT #{item.reference_fft_record_id}; strictly before {item.cutoff_date}; fault={item.fault_type}; policy={item.selection_policy}; records={','.join(item.source_record_ids)}" for item in result.source_queries]]
    if result.failure_codes:
        lines += ["", "### Validation Failures", "- " + ", ".join(result.failure_codes)]
    return "\n".join(lines) + "\n"
