"""Deterministic, source-linked compression of the complete FFT history."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.ai_analysis import _diagnostic_limitation, _fft_summary, _related_history_summary
from app.data_loader import load_fft_record


def compact_record(record: dict) -> dict:
    evidence = _fft_summary(record)
    evidence["diagnosticLimitation"] = _diagnostic_limitation(evidence)
    # Repeated labels/messages add no measurement evidence. Retain all significant
    # faults and the default fault's negative evidence when no fault is significant.
    diagnosis = evidence["diagnosis"]
    diagnosis.pop("message", None)
    diagnosis.pop("label", None)
    faults = diagnosis["faults"]
    diagnosis["faults"] = [fault for fault in faults if fault["hasAnomaly"]] or [
        fault for fault in faults if fault["type"] == diagnosis["defaultFaultType"]
    ]
    evidence.pop("recentAlertRecords", None)
    evidence.pop("alertRecordCount", None)
    return evidence


def _components(fft: dict) -> dict[str, dict]:
    components = {"maximum": {"amplitude": fft.get("maxAmplitude")}}
    diagnosis = fft["diagnosis"]
    for harmonic in diagnosis["harmonics"]:
        components[f"shaft{harmonic['order']}X"] = harmonic
    for fault in diagnosis["faults"]:
        for harmonic in fault["harmonics"]:
            components[f"{fault['type']}{harmonic['order']}X"] = harmonic
    return {name: value for name, value in components.items()
            if isinstance(value.get("amplitude"), (int, float))}


def _sample(fft: dict, component: dict) -> dict:
    return {"recordId": fft["recordId"], "measuredAt": fft["measuredAt"],
            "amplitude": component["amplitude"],
            "frequency": component.get("detectedFrequency")}


def _extrema(samples: list[dict]) -> dict:
    return {"sampleCount": len(samples), "first": samples[0], "latest": samples[-1],
            "minimum": min(samples, key=lambda item: item["amplitude"]),
            "maximum": max(samples, key=lambda item: item["amplitude"])}


def prepare_fft_evidence(dataset_id: str, dataset: dict, history: list[dict], until: Any, *, records_cache: dict | None = None) -> dict:
    decoded = records_cache if records_cache is not None else {}
    fft = dataset.get("fft") or {}
    inventory = sorted(fft.get("records", []), key=lambda item: (item["measuredAt"], item["id"]))
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    inspected_ids: set[int] = set()
    unavailable = []
    point = (dataset.get("equipment") or {}).get("measurementPoint")
    for item in inventory:
        try:
            raw = load_fft_record(fft, item["id"])
            decoded[item["id"]] = raw
            # Build the full compact evidence for aggregation, before pruning
            # insignificant faults from the representative records.
            evidence = _fft_summary(raw)
        except (KeyError, ValueError, OSError, SyntaxError, TypeError):
            unavailable.append(item["id"])
            continue
        inspected_ids.add(item["id"])
        key = (item["measureMode"]["code"], evidence["amplitudeUnit"], point,
               evidence["diagnosis"]["rpm"], evidence["frequencyRange"], evidence["lineCount"])
        grouped[key].append(evidence)

    groups, representatives = [], {}
    for key, records in grouped.items():
        mode, unit, point, rpm, frequency_range, line_count = key
        monthly: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        component_records: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
        anomaly_records = [record for record in records if record["hasAnalysisAnomaly"]]
        causes = Counter()
        for record in records:
            diagnosis = record["diagnosis"]
            if mode == "3" and diagnosis["diagnosis"] in {"unbalance", "misalignment"}:
                causes[diagnosis["diagnosis"]] += 1
            for fault in diagnosis["faults"]:
                if any(harmonic.get("significant") for harmonic in fault["harmonics"]):
                    causes[fault["type"]] += 1
            for name, component in _components(record).items():
                monthly[record["measuredAt"][:7]][name].append(_sample(record, component))
                component_records[name].append((record, component))
        candidates = [records[0], records[-1]]
        if anomaly_records:
            candidates.append(anomaly_records[0])
        candidates.append(max(records, key=lambda item: item.get("maxAmplitude") or 0))
        if mode == "3":
            for name in ("shaft1X", "shaft2X", "shaft3X"):
                samples = component_records.get(name, [])
                if samples:
                    candidates.append(max(samples, key=lambda item: item[1]["amplitude"])[0])
        selected = list(dict.fromkeys(record["recordId"] for record in candidates))[:6]
        for record_id in selected:
            representatives[record_id] = compact_record(decoded[record_id])
        groups.append({
            "measureMode": mode, "amplitudeUnit": unit, "measurementPoint": point,
            "rpm": rpm, "frequencyRange": frequency_range,
            "frequencyResolution": frequency_range / line_count if frequency_range and line_count else None,
            "lineCount": line_count, "recordCount": len(records),
            "start": records[0]["measuredAt"], "end": records[-1]["measuredAt"],
            "alertRecordCount": sum(bool(record["isAlertFft"]) for record in records),
            "anomalyRecordCount": len(anomaly_records), "supportedCauses": dict(causes),
            "firstAnomaly": {"recordId": anomaly_records[0]["recordId"], "measuredAt": anomaly_records[0]["measuredAt"]} if anomaly_records else None,
            "monthlyComponents": [{"month": month, "components": {
                name: _extrema(samples) for name, samples in components.items()
            }} for month, components in monthly.items()],
            "representativeRecordIds": selected,
        })
    related = [{"recordId": record_id, "relatedHistory": _related_history_summary(
        dataset_id, dataset, decoded[record_id], history, None, until
    )} for record_id in representatives]
    return {"recordCount": len(inventory), "inspectedCount": len(inspected_ids),
            "unavailableRecordIds": unavailable, "groups": groups,
            "representativeRecords": list(representatives.values()), "relatedHistory": related}
