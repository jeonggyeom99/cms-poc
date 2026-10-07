"""Recent seven-calendar-day diagnosis, independent of the selected FFT record."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from app.analysis.fft_severity import assess_fft_harmonics, grade_criterion
from app.data_loader import load_fft_record


def weekly_fft_diagnosis(fft: dict | None) -> dict:
    records = (fft or {}).get("records") or []
    result = {"start": None, "end": None, "recordCount": 0, "evaluatedRecordCount": 0,
              "excludedRecordCount": 0, "partialRecordCount": 0, "causes": [], "representative": None,
              "label": "판정 불가", "state": "neutral", "limitation": None}
    if not records:
        result["limitation"] = "주파수 측정 데이터가 없습니다."
        return result
    end = max(datetime.fromisoformat(item["measuredAt"]) for item in records)
    start = datetime.combine(end.date() - timedelta(days=6), time.min)
    window = [item for item in records if start <= datetime.fromisoformat(item["measuredAt"]) <= end]
    result.update(start=start.isoformat(sep=" "), end=end.isoformat(sep=" "), recordCount=len(window))
    causes = {}
    for item in window:
        try:
            assessments = assess_fft_harmonics(load_fft_record(fft, item["id"]))
        except (KeyError, ValueError, OSError, SyntaxError, TypeError):
            assessments = []
        valid = [entry for entry in assessments if entry["score"] is not None]
        if not valid:
            result["excludedRecordCount"] += 1
            continue
        result["evaluatedRecordCount"] += 1
        if any(entry["partial"] for entry in assessments):
            result["partialRecordCount"] += 1
        for entry in valid:
            if entry["score"] == 0:
                continue
            cause = causes.setdefault(entry["cause"], {
                "cause": entry["cause"], "causeLabel": entry["causeLabel"], "count": 0, "totalScore": 0,
                "highestScore": 0, "grade": entry["grade"], "state": entry["state"], "unit": entry["unit"],
                "maxAmplitude": 0, "latestAt": item["measuredAt"], "recordIds": [], "peakRecordId": None, "peakEvidence": None,
            })
            cause["count"] += 1
            cause["totalScore"] += entry["score"]
            cause["recordIds"].append(item["id"])
            cause["latestAt"] = max(cause["latestAt"], item["measuredAt"])
            if (entry["score"], entry["maxAmplitude"]) > (cause["highestScore"], cause["maxAmplitude"]):
                harmonic = max((h for h in entry["harmonics"] if h["score"] is not None),
                               key=lambda h: (h["score"], h["amplitude"]))
                cause["peakEvidence"] = {"recordId": item["id"], "measuredAt": entry["measuredAt"],
                                         "measureMode": entry["measureMode"], "harmonicOrder": harmonic["order"],
                                         "amplitude": harmonic["amplitude"], "frequency": harmonic["frequency"], "unit": entry["unit"]}
                cause.update(highestScore=entry["score"], grade=entry["grade"], state=entry["state"],
                             maxAmplitude=entry["maxAmplitude"], peakRecordId=item["id"])
    # Stable code order settles exact ties without comparing mm/s with g.
    ranked = sorted(causes.values(), key=lambda entry: entry["cause"])
    ranked.sort(key=lambda entry: (entry["count"], entry["totalScore"], entry["highestScore"],
                                   datetime.fromisoformat(entry["latestAt"])), reverse=True)
    result["causes"] = ranked
    if ranked:
        result.update(representative=ranked[0], label=f"{ranked[0]['causeLabel']} {ranked[0]['grade']}", state=ranked[0]["state"])
    elif result["evaluatedRecordCount"]:
        result.update(label="양호", state="normal")
    if result["excludedRecordCount"] or result["partialRecordCount"]:
        result["limitation"] = f"판정 제외 {result['excludedRecordCount']}건 · 고조파 일부 누락 {result['partialRecordCount']}건"
    return result


def weekly_explanation_facts(weekly: dict) -> list[str]:
    """Server-authored facts to integrate into the AI's frequency narrative."""
    cause = weekly.get("representative")
    if not weekly.get("start"):
        return ["최근 7일 주파수 측정 데이터가 없어 현재 상태는 판정 불가입니다."]
    period = f"{weekly['start'][:10]}~{weekly['end'][:10]}"
    if not cause:
        facts = [f"최근 7일({period})의 유효한 판정 기록 {weekly['evaluatedRecordCount']}건에서 초기 결함 이상은 없으므로 현재 상태는 양호입니다."] if weekly['evaluatedRecordCount'] else [f"최근 7일({period})에 유효한 고조파 근거가 없어 현재 상태는 판정 불가입니다."]
    else:
        peak = cause['peakEvidence']
        mode = {'0': '가속도 ALL', '2': '가속도 ENV', '3': '속도'}[peak['measureMode']]
        comparisons = ', '.join(f"{item['causeLabel']} {item['count']}건·{item['totalScore']}점" for item in weekly['causes'])
        facts = [f"최근 7일({period})의 초기 결함 이상 발생은 {comparisons}입니다.",
                 f"발생 횟수 우선, 동률이면 누적 점수·최고 등급·최근 발생 시각 순으로 비교해 {cause['causeLabel']}를 대표 원인으로 선정했습니다.",
                 f"선택 원인의 주간 최고값은 {peak['measuredAt'][:10]} {mode} {cause['cause']} {peak['harmonicOrder']}X의 {peak['amplitude']:.4f} {peak['unit']}입니다.",
                 f"이는 진폭 기준 {grade_criterion(cause['unit'], cause['highestScore'])} 구간이므로 현재 상태는 {cause['causeLabel']} {cause['grade']}입니다.",
                 "표시 등급은 선택 원인의 주간 최고 등급이며, 진폭 등급만으로 물리적 결함을 확정하지 않습니다."]
    if weekly.get('limitation'):
        facts.append(f"집계에는 {weekly['limitation']}의 제한이 있습니다.")
    return facts
