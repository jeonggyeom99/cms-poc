"""Regression contracts for linked FFT measurements and bounded narratives."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.agents.handoff import catalog_prompt, evidence_catalog, hydrate_handoff, limited_handoff, offered_catalog
from app.services.fft_status import weekly_explanation_facts
from tests.test_multi_agent import context, draft, gateway, synthesis
from tests.test_ai_reliability import response
from tests.test_fft_severity import bearing_record, weekly


@pytest.fixture(scope="module")
def csv_contexts():
    from app.data_loader import load_datasets, load_history
    from app.equipment_analysis import build_equipment_context

    data = Path(__file__).resolve().parents[1] / "data"
    datasets, history = load_datasets(data), load_history(data)["items"]
    return {key: build_equipment_context(key, datasets[key], history, None) for key in ("2", "5", "9")}


def test_weekly_peak_keeps_its_measurement_date_and_record(csv_contexts):
    catalog = evidence_catalog("fft", csv_contexts["2"])
    peak = next(f for f in catalog.values() if f.source == "fft.weekly.representative.maxAmplitude")
    assert peak.source_record_id == "fft:51"
    assert peak.measured_at == "2026-06-18 21:46:39.127"
    latest = next(f for f in catalog.values() if f.source == "fft.weekly.representative.latestAt")
    assert latest.value == "2026-06-21 21:46:39.127"
    assert latest.source_record_id is None


@pytest.mark.parametrize("dataset_id, date", [("2", "2026-06-18"), ("9", "2026-09-02")])
def test_offered_measurement_bundles_link_frequency_amplitude_date_mode_and_ids(csv_contexts, dataset_id, date):
    value = csv_contexts[dataset_id]
    original = deepcopy(value)
    catalog = offered_catalog("fft", evidence_catalog("fft", value))
    table = catalog_prompt(catalog)
    bundle = next(b for b in table["measurements"] if b["source"] == "fft.weekly.representative.peakEvidence")
    assert bundle["source_record_id"] == "fft:51"
    assert bundle["measured_at"].startswith(date)
    assert bundle["measure_mode"] == "3"
    assert bundle["frequency"] == 20.0 and bundle["frequency_unit"] == "Hz"
    assert bundle["amplitude"] == pytest.approx(4.073579788208008)
    assert bundle["amplitude_unit"] == "mm/s"
    assert "속도" in bundle["description"] and "20" in bundle["description"]
    cited = [catalog[eid] for eid in bundle["evidence_ids"]]
    assert {f.source.rsplit(".", 1)[-1] for f in cited} >= {"frequency", "amplitude"}
    assert value == original


def test_offered_catalog_keeps_frequency_for_selected_monthly_amplitude(csv_contexts):
    full = evidence_catalog("fft", csv_contexts["2"])
    amplitude = next(f for f in full.values() if ".monthlyComponents" in f.source and f.source.endswith(".maximum.amplitude")
                     and ".shaft1X." in f.source)
    sibling = amplitude.source.rsplit(".", 1)[0] + ".frequency"
    frequency = next(f for f in full.values() if f.source == sibling)
    offered = offered_catalog("fft", {f.evidence_id: f for f in (amplitude, frequency)}, limit=1)
    assert amplitude.evidence_id in offered and frequency.evidence_id in offered


def test_weekly_maximum_citation_forwards_complete_peak_bundle_to_synthesis(csv_contexts):
    value = csv_contexts["2"]
    catalog = evidence_catalog("fft", value)
    amplitude = next(f for f in catalog.values() if f.source == "fft.weekly.representative.maxAmplitude")
    proposed = draft("fft", value, catalog)
    proposed.evidence_ids = [amplitude.evidence_id]
    proposed.findings = proposed.candidate_causes = []
    handoff = hydrate_handoff(proposed, "fft", value, catalog)
    table = catalog_prompt({f.evidence_id: f for f in handoff.evidence})
    bundle = next(b for b in table["measurements"] if b["source"] == "fft.weekly.representative.peakEvidence")
    assert bundle["frequency"] == 20.0 and bundle["measured_at"].startswith("2026-06-18")
    assert handoff.source_record_ids == ["fft:51"]


def test_weekly_total_explicitly_includes_all_and_env(monkeypatch):
    env = bearing_record()
    all_mode = deepcopy(env)
    all_mode.update(recordId=2, measuredAt="2026-04-30 13:00:00")
    all_mode["metadata"]["measureMode"]["code"] = "0"
    result = weekly(monkeypatch, [env, all_mode])
    bpfi = next(c for c in result["causes"] if c["cause"] == "BPFI")
    assert bpfi["count"] == 2 and bpfi["countsByMode"] == {"2": 1, "0": 1}
    assert bpfi["totalScore"] == 6 and bpfi["grade"] == "베어링 교체"
    facts = "\n".join(weekly_explanation_facts(result))
    assert "전체" in facts and "ENV 1건" in facts and "ALL 1건" in facts
    assert "최신 발생일" in facts


def test_v191_csv_bpfi_total_is_not_an_env_count(csv_contexts):
    value = csv_contexts["5"]
    bpfi = next(c for c in value["fftWeeklyDiagnosis"]["causes"] if c["cause"] == "BPFI")
    assert bpfi["count"] == 2
    assert bpfi["countsByMode"] == {"2": 1, "0": 1}
    assert bpfi["peakEvidence"]["recordId"] == 2
    assert bpfi["peakEvidence"]["frequency"] == 141.25
    assert bpfi["peakEvidence"]["measuredAt"].startswith("2026-05-25")
    assert any("전체 BPFI 2건 = ENV 1건 + ALL 1건" in fact for fact in value["weeklyExplanationFacts"])


def test_tool_fft_bundle_keeps_mode_unit_date_and_paired_citations(csv_contexts):
    from app.agents.handoff import measurement_dependencies
    from app.data_loader import load_datasets, load_fft_record
    from app.ai_analysis import _fft_summary

    value = csv_contexts["2"]
    fft = load_datasets(Path(__file__).resolve().parents[1] / "data")["2"]["fft"]
    extra = {"status": "ready", "fft": _fft_summary(load_fft_record(fft, 51))}
    catalog = evidence_catalog("fft", value, [extra])
    amplitude = next(f for f in catalog.values() if f.source == "fft.tools[0].fft.spectrum.peaks[0].amplitude")
    selected = measurement_dependencies({amplitude.evidence_id: amplitude}, catalog)
    bundles = catalog_prompt(selected)["measurements"]
    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle["measure_mode"] == "3" and bundle["amplitude_unit"] == "mm/s"
    assert bundle["source_record_id"] == "fft:51" and bundle["measured_at"].startswith("2026-06-18")
    assert bundle["frequency"] == 20.0 and bundle["amplitude"] == pytest.approx(4.07358)


@pytest.mark.parametrize("length, ready", [(501, True), (1200, True), (1201, False)])
def test_fft_summary_limit_applies_through_gateway_and_assembly(tmp_path, length, ready):
    value = context()
    prefix, suffix = "관측한 회전 성분을 확인했습니다.\n\n", " 동일 조건에서 재측정하세요."
    text = prefix + "가" * (length-len(prefix)-len(suffix)) + suffix
    assert len(text) == length
    requests = {}

    async def create(**params):
        payload = json.loads(params["messages"][1]["content"])
        name = payload.get("agent_name", "synthesis")
        requests[name] = params
        result = draft(name, value) if name != "synthesis" else synthesis(payload)
        if name == "fft":
            result.summary = text
        return response(result.model_dump_json())

    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    trace = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    fft = next(h["json"] for h in trace["handoffs"] if h["json"]["agent_name"] == "fft")
    assert fft["llm_success"] == ready
    if ready:
        assert result.fft_summary == text
    else:
        assert fft["failure_codes"] == ["schema_validation"]
    assert len(trace["metrics"]["completions"]) == 4
    assert requests["fft"]["response_format"]["json_schema"]["schema"]["properties"]["summary"]["maxLength"] == 1200
    assert requests["trend"]["response_format"]["json_schema"]["schema"]["properties"]["summary"]["maxLength"] == 500
    assert requests["fft"]["max_completion_tokens"] > requests["trend"]["max_completion_tokens"]


def test_history_absence_and_provider_failure_have_distinct_server_messages():
    value = context()
    empty = limited_handoff("history", value, {}, ["no_source_data"], True)
    failed = limited_handoff("history", value, {}, ["provider_unavailable"])
    assert "자료 없음" in empty.summary and "LLM" not in empty.summary
    assert "API 호출 실패" in failed.summary and "자료 없음" not in failed.summary
