"""Envelope calculation. Artifacts are opt-in to keep agent results compact."""
import math
from typing import Any

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

from app.data_loader.sampling import sampling_metadata


def analyze_envelope(record: dict[str, Any], low_hz: float, high_hz: float, *, include_artifacts: bool = False) -> dict[str, Any]:
    if record["metadata"]["measureMode"]["code"] != "0": raise ValueError("가속도 ALL 원시 파형만 포락선 분석할 수 있습니다.")
    samples=record.get("timeWaveSamples") or []; sampling=sampling_metadata(record["metadata"]["measureFreq"]["code"],len(samples),record["lineCount"])
    if not sampling["valid"]: raise ValueError(sampling["reason"])
    fs=sampling["frequencyHz"]
    if not (math.isfinite(low_hz) and math.isfinite(high_hz) and 0 < low_hz < high_hz <= record["frequencyRange"] and high_hz < fs/2): raise ValueError("공진 대역은 0 < 하한 < 상한 ≤ Fmax, 상한 < Fs/2이어야 합니다.")
    raw=np.asarray(samples,dtype=float)
    if len(raw)<64 or not np.isfinite(raw).all(): raise ValueError("분석할 파형이 너무 짧거나 유효하지 않습니다.")
    filtered=sosfiltfilt(butter(4,[low_hz,high_hz],btype="bandpass",fs=fs,output="sos"),raw-raw.mean()); envelope=np.abs(hilbert(filtered)); window=np.hanning(len(raw)); amplitudes=np.abs(np.fft.rfft((envelope-envelope.mean())*window))/window.sum(); amplitudes[1:-1 if len(raw)%2==0 else None]*=2
    result={"recordId":record["recordId"],"measuredAt":record["measuredAt"],"sampling":sampling,"frequencyResolutionHz":fs/len(raw),"durationSeconds":len(raw)/fs,"bandHz":[low_hz,high_hz],"faults":[{"type":fault["type"],"baseFrequency":fault["baseFrequency"]} for fault in record.get("analysis",{}).get("diagnosis",{}).get("faults",[])]}
    if include_artifacts: result.update({"timeSeconds":(np.arange(len(raw))/fs).tolist(),"raw":raw.tolist(),"filtered":filtered.tolist(),"envelope":envelope.tolist(),"frequencies":np.fft.rfftfreq(len(raw),1/fs).tolist(),"amplitudes":amplitudes.tolist()})
    return result
