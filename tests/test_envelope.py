import asyncio
import copy
import struct

import httpx
import numpy as np
import pytest

from app.data_loader.fft import _build_fft_record
from app.data_loader.sampling import sampling_metadata
from app.envelope import analyze_envelope
from app.main import create_app


def waveform_record(n=2048):
    fs = 25600
    t = np.arange(n) / fs
    # Integer-bin modulation with a large low-frequency interferer.
    signal = 5 * np.sin(2 * np.pi * 25 * t) + (1 + .4 * np.cos(2 * np.pi * 100 * t)) * np.cos(2 * np.pi * 1600 * t)
    row = {
        "MeasureFreq": "9", "MeasureMode": "0", "MeasureLineNum": str(n * 100 // 256),
        "MeasureDate": "2026-01-01 00:00:00", "ExtractionType": "2", "DiagMode": "2",
        "TimeWaveSampling": repr(struct.pack(f"<{n}f", *signal)),
        "ResultData": repr(struct.pack(f"<{n * 100 // 256}f", *([0.] * (n * 100 // 256)))),
    }
    return _build_fft_record(row, 2), row


@pytest.mark.parametrize("code,fs", [("5", 1280), ("6", 2560), ("9", 25600), ("10", 51200)])
@pytest.mark.parametrize("n,lines", [(1024, 400), (2048, 800), (4096, 1600)])
def test_sampling_rule(code, fs, n, lines):
    assert sampling_metadata(code, n, lines)["frequencyHz"] == fs


@pytest.mark.parametrize("code,n,lines", [("99", 2048, 800), ("9", 1000, 800), ("9", 0, 800), ("9", 2048, 0)])
def test_sampling_rejects_unknown_rule(code, n, lines):
    result = sampling_metadata(code, n, lines)
    assert not result["valid"]
    assert result["frequencyHz"] is None
    assert result["reason"]


@pytest.mark.parametrize("n", [1024, 2048, 4096])
def test_recovers_envelope_modulation(n):
    record, _ = waveform_record(n)
    result = analyze_envelope(record, 1000, 2200)
    peaks = np.asarray(result["amplitudes"])
    frequency = result["frequencies"][np.argmax(peaks[1:]) + 1]
    assert abs(frequency - 100) <= result["frequencyResolutionHz"]
    assert peaks.max() == pytest.approx(.4, abs=.06)
    assert result["timeSeconds"][1] == 1 / 25600
    assert result["timeSeconds"][-1] == (n - 1) / 25600
    assert result["durationSeconds"] == n / 25600
    assert result["frequencies"][-1] == 12800
    assert np.std(result["filtered"]) < 1
    assert min(result["envelope"]) >= 0
    assert result["faults"] == []  # Missing bearing metadata does not block analysis.


@pytest.mark.parametrize("low,high", [(0, 2200), (2200, 1000), (1000, 10001), (float("nan"), 2200), (1000, float("inf"))])
def test_invalid_band(low, high):
    with pytest.raises(ValueError, match="공진 대역"):
        analyze_envelope(waveform_record()[0], low, high)


def test_invalid_wave_and_mode():
    original, _ = waveform_record()
    for samples in (None, [], [1.] * 1000, [float("nan")] * 2048, [float("inf")] * 2048):
        record = {**original, "timeWaveSamples": samples}
        with pytest.raises(ValueError):
            analyze_envelope(record, 1000, 2200)
    short = {**original, "timeWaveSamples": [0.] * 64, "lineCount": 25}
    assert len(analyze_envelope(short, 1000, 2200)["envelope"]) == 64
    short.update(timeWaveSamples=[0.] * 32, lineCount=12)
    with pytest.raises(ValueError):
        analyze_envelope(short, 1000, 2200)
    for mode in ("2", "3"):
        record = copy.deepcopy(original)
        record["metadata"]["measureMode"]["code"] = mode
        with pytest.raises(ValueError, match="가속도 ALL"):
            analyze_envelope(record, 1000, 2200)


def test_api_and_until(tmp_path):
    async def exercise():
        app = create_app(tmp_path)
        record, row = waveform_record()
        record.update(_recordsById={2: row}, _rpm=None, _bearing=None)
        app.state.datasets = {"test": {"fft": record}}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = "/api/dashboard/test/fft/2/envelope"
            response = await client.get(path)
            assert response.status_code == 200
            assert response.json()["sampling"]["frequencyHz"] == 25600
            assert (await client.get(path + "?low_hz=0")).status_code == 422
            assert (await client.get(path + "?until=2025-12-31")).status_code == 404
            assert (await client.get("/api/dashboard/test/fft/3/envelope")).status_code == 404
            assert (await client.get("/api/dashboard/missing/fft/2/envelope")).status_code == 404
    asyncio.run(exercise())
