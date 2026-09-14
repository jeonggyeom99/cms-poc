from __future__ import annotations

import math
from typing import Any

from .rules import BEARING_FAULT_TYPES, BEARING_FFT_SIGNIFICANT_AMPLITUDE, BEARING_FFT_TOLERANCE_HZ, FFT_PEAK_SETTINGS, RULESET_VERSION, VELOCITY_FFT_MINIMUM_1X, VELOCITY_FFT_TOLERANCE_HZ


def _peak(points: list[tuple[float, float]], target: float, tolerance: float) -> tuple[float | None, float]:
    candidates = [point for point in points if abs(point[0] - target) <= tolerance]
    return max(candidates, key=lambda item: item[1]) if candidates else (None, 0.0)


def analyze_velocity_fft(frequencies: list[float], amplitudes: list[float], rpm: float | None) -> dict[str, Any]:
    result: dict[str, Any] = {"status":"unavailable","diagnosis":"unavailable","label":"회전수 미설정","message":"설비 RPM이 설정되지 않아 회전 주파수 기반 진단을 보류했습니다.","rpm":rpm,"rpmSource":"equipment_config" if rpm is not None else "unavailable","shaftFrequency":None,"frequencyTolerance":VELOCITY_FFT_TOLERANCE_HZ,"harmonics":[],"ratios":{"twoToOne":None,"threeToOne":None},"ruleId":"fft.velocity.harmonics","rulesetVersion":RULESET_VERSION}
    if rpm is None or not math.isfinite(rpm) or rpm <= 0: return result
    if len(frequencies) != len(amplitudes):
        result.update({"label":"분석 불가","message":"FFT 주파수와 진폭 배열의 길이가 일치하지 않습니다."}); return result
    points = [(frequency, amplitude) for frequency, amplitude in zip(frequencies, amplitudes) if math.isfinite(frequency) and math.isfinite(amplitude)]
    shaft = rpm / 60.0; harmonics = []
    for order in range(1, 4):
        frequency, amplitude = _peak(points, shaft * order, VELOCITY_FFT_TOLERANCE_HZ)
        harmonics.append({"order":order,"targetFrequency":shaft * order,"detectedFrequency":frequency,"amplitude":amplitude,"detected":frequency is not None})
    one, two, three = (entry["amplitude"] for entry in harmonics)
    result.update({"shaftFrequency":shaft,"harmonics":harmonics})
    if one < VELOCITY_FFT_MINIMUM_1X:
        result.update({"status":"insufficient_1x","diagnosis":"inconclusive","label":"판정 불가","message":"1X 회전 주파수 주변에서 0.5 mm/s 이상의 피크를 찾지 못했습니다."}); return result
    ratios={"twoToOne":two/one,"threeToOne":three/one}; result["ratios"] = ratios
    if ratios["twoToOne"] > .4 or ratios["threeToOne"] > .3: diagnosis,label="misalignment","Misalignment"
    elif ratios["twoToOne"] < .2 and ratios["threeToOne"] < .1: diagnosis,label="unbalance","Unbalance"
    else: diagnosis,label="complex","복합 또는 판정 불확실"
    result.update({"status":"analyzed","diagnosis":diagnosis,"label":label,"message":f"1X 대비 2X 비율 {ratios['twoToOne']:.2f}, 3X 비율 {ratios['threeToOne']:.2f}를 기준으로 판정했습니다."})
    return result


def _bearing_key(fault_type: str) -> tuple[str, str]:
    return {"BPFO":("bearing_outer_race","베어링 외륜 결함"),"BPFI":("bearing_inner_race","베어링 내륜 결함"),"BSF":("bearing_ball","베어링 볼 결함"),"FTF":("bearing_cage","베어링 케이지 결함")}[fault_type]


def analyze_acceleration_bearing_fft(frequencies: list[float], amplitudes: list[float], rpm: float | None, bearing: dict[str, Any] | None, bearing_master: dict[str, Any] | None = None) -> dict[str, Any]:
    maker, number = (bearing or {}).get("maker"), (bearing or {}).get("number")
    result: dict[str, Any] = {"status":"unavailable","diagnosis":"unavailable","label":"가속도 베어링 분석 불가","message":"베어링 분석에 필요한 정보가 없습니다.","rpm":rpm,"rpmSource":"equipment_config" if rpm is not None else "unavailable","shaftFrequency":None,"frequencyTolerance":BEARING_FFT_TOLERANCE_HZ,"amplitudeThreshold":BEARING_FFT_SIGNIFICANT_AMPLITUDE,"bearing":{"maker":maker,"number":number},"faults":[],"defaultFaultType":None,"harmonics":[],"ratios":{"twoToOne":None,"threeToOne":None},"ruleId":"fft.bearing.harmonics","rulesetVersion":RULESET_VERSION}
    if rpm is None or not math.isfinite(rpm) or rpm <= 0: result["message"]="설비 RPM이 설정되지 않아 베어링 결함 주파수를 계산할 수 없습니다."; return result
    if len(frequencies) != len(amplitudes) or not frequencies: result["message"]="FFT 주파수와 진폭 배열이 유효하지 않습니다."; return result
    master = bearing_master or {"available":False,"reason":"bearing_not_configured","coefficients":{}}
    result["bearing"].update({"available":master["available"],"reason":master.get("reason"),"coefficients":master.get("coefficients",{})})
    if not master["available"]:
        result["message"]={"bearing_not_configured":"설비 베어링 제조사 또는 형번이 설정되지 않았습니다.","bearing_not_found":"베어링 마스터에서 제조사와 형번에 일치하는 결함계수를 찾지 못했습니다.","bearing_master_ambiguous":"베어링 마스터에 서로 다른 결함계수를 가진 중복 항목이 있습니다.","bearing_coefficients_invalid":"베어링 마스터의 결함계수가 유효하지 않습니다.","bearing_master_unavailable":"베어링 마스터 파일을 읽을 수 없습니다."}.get(master.get("reason"), result["message"]); return result
    points=[(float(f),float(a)) for f,a in zip(frequencies,amplitudes) if math.isfinite(f) and math.isfinite(a)]
    if not points: result["message"]="분석할 유효 FFT 진폭값이 없습니다."; return result
    shaft=rpm/60.; faults=[]
    for fault_type in BEARING_FAULT_TYPES:
        coefficient=master["coefficients"].get(fault_type)
        if coefficient is None: continue
        base=shaft*coefficient; harmonics=[]; harmonic_score=0.; sideband_score=0.; evidence=[]
        for order in range(1,4):
            target=base*order; detected, amplitude=_peak(points,target,BEARING_FFT_TOLERANCE_HZ); harmonic_score += amplitude/order
            harmonics.append({"order":order,"targetFrequency":target,"detectedFrequency":detected,"amplitude":amplitude,"detected":detected is not None,"significant":amplitude >= BEARING_FFT_SIGNIFICANT_AMPLITUDE})
            for direction in (-1,1):
                sideband=target+direction*shaft
                if sideband > 0:
                    found, value=_peak(points,sideband,BEARING_FFT_TOLERANCE_HZ); sideband_score += value*.25
                    if found is not None: evidence.append({"targetFrequency":sideband,"detectedFrequency":found,"amplitude":value})
        diagnosis,label=_bearing_key(fault_type); faults.append({"type":fault_type,"diagnosis":diagnosis,"label":label,"coefficient":coefficient,"baseFrequency":base,"harmonics":harmonics,"score":harmonic_score+sideband_score,"harmonicScore":harmonic_score,"sidebandScore":sideband_score,"sidebandEvidence":evidence,"hasAnomaly":any(item["significant"] for item in harmonics),"largestPeak":max(item["amplitude"] for item in harmonics)})
    if not faults: result["message"]="베어링 마스터에 사용할 수 있는 결함계수가 없습니다."; return result
    anomalous=[fault for fault in faults if fault["hasAnomaly"]]; ranking=anomalous or [fault for fault in faults if fault["type"]=="BPFO"] or faults; order={fault:index for index,fault in enumerate(BEARING_FAULT_TYPES)}
    selected=sorted(ranking,key=lambda fault:(-fault["score"],-fault["largestPeak"],order[fault["type"]]))[0]; scores=sorted((fault["score"] for fault in faults),reverse=True); dominance=scores[0]/scores[1] if len(scores)>1 and scores[1]>0 else None
    result.update({"status":"analyzed" if anomalous else "no_anomaly","diagnosis":selected["diagnosis"] if anomalous else "normal","label":selected["label"] if anomalous else "베어링 결함 Peak 없음","message":f"{selected['type']}의 1X/2X/3X 결함 주파수에서 유의 Peak를 확인했습니다." if anomalous else f"{BEARING_FFT_SIGNIFICANT_AMPLITUDE:.1f} g 이상의 결함 1X/2X/3X Peak가 없습니다.","shaftFrequency":shaft,"faults":faults,"defaultFaultType":selected["type"],"harmonics":selected["harmonics"],"dominance":dominance})
    return result


def analyze_fft_diagnosis(frequencies: list[float], amplitudes: list[float], measure_mode: str, rpm: float | None, bearing: dict[str, Any] | None = None, bearing_master: dict[str, Any] | None = None) -> dict[str, Any]:
    if measure_mode == "3": return analyze_velocity_fft(frequencies,amplitudes,rpm)
    if measure_mode in {"0","2"}: return analyze_acceleration_bearing_fft(frequencies,amplitudes,rpm,bearing,bearing_master)
    return {"status":"unavailable","diagnosis":"unavailable","label":"분석 불가","message":"지원하지 않는 FFT 측정모드입니다.","rpm":rpm,"rpmSource":"equipment_config" if rpm is not None else "unavailable","shaftFrequency":None,"frequencyTolerance":None,"harmonics":[],"ratios":{"twoToOne":None,"threeToOne":None},"rulesetVersion":RULESET_VERSION}


def analyze_fft_spectrum(frequencies: list[float], amplitudes: list[float], measure_mode: str) -> dict[str, Any]:
    settings=FFT_PEAK_SETTINGS.get(measure_mode); result={"status":"unavailable","amplitudeThreshold":None,"frequencyTolerance":None,"peaks":[],"message":"지원하지 않는 측정모드 또는 주파수 범위입니다.","ruleId":"fft.spectrum.peaks","rulesetVersion":RULESET_VERSION}
    if settings is None or len(frequencies)!=len(amplitudes): return result
    candidates=[(f,a) for f,a in zip(frequencies,amplitudes) if f>0 and math.isfinite(f) and math.isfinite(a)]
    if not candidates: result.update({"status":"no_data","message":"분석할 유효 FFT 진폭값이 없습니다."}); return result
    ordered=sorted(sorted(candidates,key=lambda item:item[1],reverse=True)[:10],key=lambda item:item[0]); groups=[[ordered[0]]]
    for item in ordered[1:]:
        (groups[-1].append(item) if item[0]-groups[-1][-1][0] <= settings["frequencyTolerance"] else groups.append([item]))
    peaks=[]
    for group in groups:
        frequency,amplitude=max(group,key=lambda item:item[1])
        if amplitude >= settings["amplitudeThreshold"]: peaks.append({"frequency":frequency,"amplitude":amplitude,"groupFrequencies":[f for f,_ in group],"groupAmplitudes":[a for _,a in group],"count":len(group)})
    peaks.sort(key=lambda peak:peak["amplitude"],reverse=True); result.update({"status":"analyzed" if peaks else "no_significant_peak","amplitudeThreshold":settings["amplitudeThreshold"],"frequencyTolerance":settings["frequencyTolerance"],"peaks":peaks[:5],"message":"진폭 기준을 만족하는 주요 피크를 검출했습니다." if peaks else "설정된 진폭 기준을 만족하는 주요 피크가 없습니다."}); return result
