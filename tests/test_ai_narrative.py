"""Narrative assembly contracts; mocked prose does not establish LLM accuracy."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.handoff import Finding, evidence_catalog, hydrate_handoff, limited_handoff
from app.agents.orchestrator import MultiAgentAnalysisGateway, SynthesisDraft, assemble_diagnosis
from app.ai_analysis import AiDiagnosis, OpenAISettings, SYSTEM_INSTRUCTIONS
from app.equipment_analysis import EQUIPMENT_INSTRUCTIONS
from tests.test_multi_agent import context, draft, gateway, synthesis
from tests.test_ai_reliability import response


@pytest.fixture(autouse=True)
def forbid_real_openai_clients(monkeypatch):
    """A local .env key must never turn these offline regressions into live calls."""
    import openai

    def forbidden(*args, **kwargs):
        pytest.fail("Real OpenAI clients are forbidden in offline narrative tests")

    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    monkeypatch.setattr(openai, "OpenAI", forbidden)
    monkeypatch.setenv("OPENAI_API_KEY", "offline-guard-not-a-provider-key")


@pytest.fixture(scope="module")
def real_csv_sources():
    from app.data_loader import load_datasets, load_history

    data_dir = Path(__file__).resolve().parents[1] / "data"
    return load_datasets(data_dir), load_history(data_dir)["items"]


class OfflineNarrativeGateway(MultiAgentAnalysisGateway):
    """Mock only provider completion; run the actual multi-agent pipeline."""

    def __init__(self, trace_dir, failed_agent=None):
        from tests.test_multi_agent import FakeClient

        self.contexts = []
        self.executors = []
        self.calls = []
        self.offered_tools = {}
        self.synthesis_handoffs = []
        self.failed_agent = failed_agent
        self.client = FakeClient(self.complete)
        super().__init__(
            OpenAISettings("offline", "offline-test", 2),
            client_factory=lambda **_: self.client, trace_dir=trace_dir,
        )

    async def complete(self, **params):
        from app.agents.handoff import AgentDraft

        payload = json.loads(params["messages"][1]["content"])
        name = payload.get("agent_name", "synthesis")
        self.calls.append(name)
        self.offered_tools[name] = [tool["function"]["name"] for tool in params.get("tools", [])]
        if name == self.failed_agent:
            return response("{}")
        marker = payload["equipment"]["line"]
        if name == "synthesis":
            self.synthesis_handoffs = payload["handoffs"]
            result = integrated(f"{marker}의 추세와 FFT 근거를 함께 확인했습니다.\n\n동일 조건에서 재측정하고 현장 점검 후 판단하세요.")
        else:
            selected = {}
            table = payload["evidence_catalog"]
            for row in table["rows"]:
                prefix = table["contexts"][row[5]][0]
                if name != "fft" or prefix.startswith("fft.representativeRecords"):
                    selected.setdefault(row[3] or row[0], row[0])
            result = AgentDraft(
                agent_name=name, equipment_id="V999-model-output", analysis_period={"start": "2099-01-01", "end": "2099-12-31"},
                status="ready", summary=f"{marker}의 {name} 측정 내용을 확인했습니다.\n\n운전 조건과 점검 결과를 함께 확인하세요.",
                findings=[], evidence_ids=["invented-model-citation", *list(selected.values())[:20]], source_record_ids=["fft:999999"],
                candidate_causes=[], limitations=[], recommended_checks=[],
            )
        return response(result.model_dump_json())

    async def analyze(self, value, execute=None):
        self.contexts.append(deepcopy(value))
        self.executors.append(execute)
        return await super().analyze(value, execute)


def offline_client(tmp_path, sources, *, failed_agent=None):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.test_report_endpoints import FakeReportGateway

    class NoChat:
        async def respond(self, *args, **kwargs):
            pytest.fail("This offline integration does not call chat")

    ai = OfflineNarrativeGateway(tmp_path / "traces", failed_agent)
    report = FakeReportGateway()
    app = create_app(ai_gateway=ai, report_gateway=report, ppt_gateway=report,
                     chat_gateway=NoChat(), ai_cache_dir=tmp_path / "cache")
    client = TestClient(app)
    client.__enter__()
    app.state.datasets, app.state.history = sources[0], {"items": sources[1]}
    return client, ai


def test_v032_mock_analysis_preserves_api_and_server_fft_facts(tmp_path, real_csv_sources):
    client, ai = offline_client(tmp_path, real_csv_sources)
    try:
        actual = client.post("/api/dashboard/1/ai-analysis", json={})
        assert actual.status_code == 200
        body = actual.json()
        assert set(body) == {"status", "cached", "model", "generatedAt", "analysis", "fftSeverityAssessments"}
        result = body["analysis"]
        assert "\n\n" in result["headline"] and "\n\n" in result["trendSummary"] and "\n\n" in result["fftSummary"]
        assert "자료 없음" in result["historyFindings"][0]["detail"]
        assert ai.contexts[0]["equipment"]["id"] == "V032"
        assert ai.contexts[0]["preparedFftEvidence"]["recordCount"] == 630
        weekly = ai.contexts[0]["fftWeeklyDiagnosis"]
        assert weekly["evaluatedRecordCount"] == 189
        assert weekly["representative"]["cause"] == "FTF"
        assert weekly["representative"]["peakEvidence"]["recordId"] == 47
        assert weekly["representative"]["maxAmplitude"] == pytest.approx(0.4042252004146576)
        assert result["fftReferenceRecordIds"] == [631, 4, 25, 630, 3, 18, 306, 225, 629, 2, 47]
        assert result["fftAnalysisPeriod"]["start"].startswith("2026-02-09")
        assert result["fftAnalysisPeriod"]["end"].startswith("2026-04-30")
        assert body["fftSeverityAssessments"]
        assert "999999" not in json.dumps(body["fftSeverityAssessments"])
        trace = json.loads(next((tmp_path / "traces").glob("*.json")).read_text(encoding="utf-8"))
        assert all(item["json"]["equipment_id"] == "V032" for item in trace["handoffs"])
        assert ai.calls == ["trend", "fft", "synthesis"]
        assert ai.client.closed
    finally:
        client.__exit__(None, None, None)


def test_same_sensor_datasets_do_not_share_analysis_cache(tmp_path, real_csv_sources):
    client, ai = offline_client(tmp_path, real_csv_sources)
    try:
        results = [client.post(f"/api/dashboard/{dataset_id}/ai-analysis", json={}).json() for dataset_id in ("2", "7", "9")]
        assert all(not item["cached"] for item in results)
        assert [value["datasetId"] for value in ai.contexts] == ["2", "7", "9"]
        assert {value["equipment"]["id"] for value in ai.contexts} == {"V056"}
        assert len({value["sourceFingerprint"] for value in ai.contexts}) == 3
        for dataset_id, result in zip(("2", "7", "9"), results):
            assert f"CSV Dataset #{dataset_id}" in result["analysis"]["headline"]
            repeat = client.post(f"/api/dashboard/{dataset_id}/ai-analysis", json={}).json()
            assert repeat["cached"] and repeat["analysis"] == result["analysis"]
        assert len(ai.contexts) == 3 and len(list((tmp_path / "cache").glob("*.json"))) == 3
    finally:
        client.__exit__(None, None, None)


def test_real_csv_pipeline_keeps_service_tools_without_additional_tool_requests(tmp_path, real_csv_sources):
    client, ai = offline_client(tmp_path, real_csv_sources)
    try:
        actual = client.post("/api/dashboard/1/ai-analysis", json={})
        assert actual.status_code == 200
        assert len(ai.executors) == 1 and callable(ai.executors[0])
        assert ai.offered_tools["fft"] == ["get_fft_evidence", "get_fft_history_evidence"]
        assert ai.offered_tools["trend"] == [] and ai.offered_tools["synthesis"] == []
        assert ai.calls == ["trend", "fft", "synthesis"]
        trace = json.loads(next((tmp_path / "traces").glob("*.json")).read_text(encoding="utf-8"))
        assert trace["metrics"]["tool_calls"] == 0
    finally:
        client.__exit__(None, None, None)


def test_fft_selection_keeps_equipment_analysis_scope(tmp_path, real_csv_sources):
    client, ai = offline_client(tmp_path, real_csv_sources)
    try:
        first = client.post("/api/dashboard/2/ai-analysis", json={"recordId": 2}).json()
        changed = client.post("/api/dashboard/2/ai-analysis", json={"recordId": 3, "selectedFaultType": "BPFI"}).json()
        assert not first["cached"] and changed["cached"]
        assert first["analysis"] == changed["analysis"] and len(ai.contexts) == 1
        refreshed = client.post("/api/dashboard/2/ai-analysis", json={"recordId": 3, "force": True}).json()
        assert not refreshed["cached"] and len(ai.contexts) == 2
        assert ai.contexts[0]["preparedFftEvidence"] == ai.contexts[1]["preparedFftEvidence"]
        assert refreshed["analysis"]["fftReferenceRecordIds"] == first["analysis"]["fftReferenceRecordIds"]
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("case, unavailable_agent", [("no_fft", "fft"), ("unreadable_fft", "fft"), ("no_history", "history"), ("partial_failure", "trend")])
def test_real_csv_missing_sources_and_partial_failure_are_limited(tmp_path, real_csv_sources, case, unavailable_agent):
    datasets, history = real_csv_sources
    dataset = deepcopy(datasets["1"])
    if case == "no_fft":
        dataset["fft"] = None
    elif case == "unreadable_fft":
        for record in dataset["fft"]["_recordsById"].values():
            record["ResultData"] = "unreadable offline FFT"
    sources = ({"1": dataset}, [] if case == "no_history" else history)
    client, ai = offline_client(tmp_path, sources, failed_agent="trend" if case == "partial_failure" else None)
    try:
        actual = client.post("/api/dashboard/1/ai-analysis", json={})
        if case == "unreadable_fft":
            # CSV decoding keeps its existing safe error contract, before LLM calls.
            assert actual.status_code == 422 and isinstance(actual.json()["detail"], str)
            assert not ai.calls and not ai.contexts
            return
        assert actual.status_code == 200
        body = actual.json()["analysis"]
        trace = json.loads(next((tmp_path / "traces").glob("*.json")).read_text(encoding="utf-8"))
        handoffs = {item["json"]["agent_name"]: item["json"] for item in trace["handoffs"]}
        handoff = handoffs[unavailable_agent]
        assert handoff["status"] == ("failed" if case == "partial_failure" else "unavailable")
        assert not handoff["llm_success"]
        assert handoff["failure_codes"] and not handoff["findings"]
        assert ai.calls == (["trend", "synthesis"] if case == "no_fft" else ["trend", "fft", "synthesis"])
        assert trace["metrics"]["agents"]["synthesis"]["llm_calls"] == 1
        assert trace["metrics"]["synthesis"]["status"] == "completed"
        forwarded = {item["agent_name"]: item for item in ai.synthesis_handoffs}
        expected_summaries = {
            "trend": "CSV Dataset #1의 trend 측정 내용을 확인했습니다.\n\n운전 조건과 점검 결과를 함께 확인하세요.",
            "fft": "CSV Dataset #1의 fft 측정 내용을 확인했습니다.\n\n운전 조건과 점검 결과를 함께 확인하세요.",
        }
        for name in ({"trend", "fft"} - {unavailable_agent}):
            assert body[f"{name}Summary"] == expected_summaries[name]
            assert handoffs[name]["summary"] == expected_summaries[name]
            assert handoffs[name]["status"] == "ready" and handoffs[name]["llm_success"]
            assert handoffs[name]["evidence"] and not handoffs[name]["failure_codes"]
            assert forwarded[name]["summary"] == expected_summaries[name]
            assert forwarded[name]["llm_success"] and not forwarded[name]["failure_codes"]
        if case == "no_fft":
            assert body["fftReferenceRecordIds"] == []
        if case == "partial_failure":
            assert "TREND" in " ".join(body["counterEvidence"])
    finally:
        client.__exit__(None, None, None)


def narrative_handoffs(value):
    summaries = {
        "trend": "최근 측정일의 속도 진동은 주의 기준보다 높습니다.\n\n상승이 이어지는지 같은 조건에서 확인하세요.",
        "fft": "속도 FFT의 회전 주파수 성분이 우세해 불평형 가능성이 있습니다.\n\n체결과 오염 상태를 점검하고 동일 조건에서 재측정하세요.",
        "history": "과거 회전체 진동 사례에서는 청소 후 재측정과 추적 점검을 기록했습니다.\n\n현재도 오염이 관찰될 때 해당 조치를 검토하세요.",
    }
    handoffs = []
    for name in ("trend", "fft", "history"):
        proposed = draft(name, value)
        proposed.summary = summaries[name]
        proposed.findings = [Finding(interpretation="실제 관측 내용을 추가 확인하세요.",
                                     evidence_ids=proposed.evidence_ids[:1], relationship="observation")]
        handoffs.append(hydrate_handoff(proposed, name, value, evidence_catalog(name, value)))
    return handoffs


def integrated(headline="추세와 FFT를 함께 보면 설비 상태 변화 가능성이 있습니다.\n\n현장 점검과 같은 조건의 재측정을 우선하세요."):
    return SynthesisDraft(headline=headline, risk_level="caution", risk_label="주의", likely_causes=[],
                          counter_evidence=[], recommended_actions=[], used_agents=["trend", "fft", "history"],
                          evidence_ids=["t:1"])


def test_narrative_paragraphs_survive_assembly():
    value = context()
    value["weeklyExplanationFacts"] = ["서버 주간 집계 설명입니다."]
    trend_handoff, fft_handoff, history_handoff = narrative_handoffs(value)
    synthesis_draft = integrated()
    result = assemble_diagnosis(value, [trend_handoff, fft_handoff, history_handoff], synthesis_draft)
    assert result.trend_summary == trend_handoff.summary
    assert result.fft_summary == fft_handoff.summary
    assert result.headline == synthesis_draft.headline
    assert "\n\n" in result.headline
    assert result.fft_findings
    assert result.history_findings[0].detail == history_handoff.summary
    assert history_handoff.summary not in "\n".join(result.counter_evidence)


@pytest.mark.parametrize("length", [200, 700])
def test_headline_accepts_two_paragraphs_up_to_700_characters(length):
    headline = "가" * (length - 4) + "\n\n점검"
    value = context()
    result = assemble_diagnosis(value, narrative_handoffs(value), integrated(headline))
    assert result.headline == headline
    assert AiDiagnosis.model_validate_json(result.model_dump_json()).headline == headline
    with pytest.raises(ValidationError):
        integrated(headline + "나" * (701 - length))
    with pytest.raises(ValidationError):
        AiDiagnosis.model_validate(result.model_dump() | {"headline": "가" * 701})


def test_weekly_facts_are_not_prepended_to_fft_summary():
    value = context()
    value["weeklyExplanationFacts"] = ["주간 원본 근거입니다." * 100]
    original = value["weeklyExplanationFacts"][:]
    handoffs = narrative_handoffs(value)
    result = assemble_diagnosis(value, handoffs, integrated())
    assert result.fft_summary == handoffs[1].summary
    assert value["weeklyExplanationFacts"] == original


def test_missing_metadata_keeps_limitations_without_forced_cause():
    value = context()
    limitations = ["베어링 모델 정보 누락", "베어링 계수 마스터 미등록 또는 불일치", "일부 FFT 기록 해석 불가"]
    value["requiredCounterEvidence"] = limitations
    result = assemble_diagnosis(value, narrative_handoffs(value), integrated())
    assert all(note in "\n".join(result.counter_evidence) for note in limitations)
    assert result.likely_causes == []


def test_no_history_does_not_create_a_case():
    value = context()
    handoffs = narrative_handoffs(value)[:2]
    value["preparedFftEvidence"]["relatedHistory"] = []
    unavailable = limited_handoff("history", value, evidence_catalog("history", value), ["no_source_data"], True)
    result = assemble_diagnosis(value, [*handoffs, unavailable], integrated())
    assert [finding.detail for finding in result.history_findings] == [unavailable.summary]
    assert "자료 없음" in result.history_findings[0].detail
    assert not unavailable.source_queries and not unavailable.findings


@pytest.mark.parametrize("observations, expected", [
    ([], ["과거 조치와 후속 확인을 검토하세요."]),
    (["청소 기록입니다."], ["과거 조치와 후속 확인을 검토하세요.", "청소 기록입니다."]),
    (["청소 기록입니다.", "재측정 기록입니다."],
     ["과거 조치와 후속 확인을 검토하세요.", "청소 기록입니다.", "재측정 기록입니다."]),
    (["청소 기록입니다.", "재측정 기록입니다.", "조치 후에도 진동이 유지됐습니다."],
     ["청소 기록입니다.", "재측정 기록입니다.", "조치 후에도 진동이 유지됐습니다."]),
    (["청소 기록입니다.", "과거 조치와 후속 확인을 검토하세요.", "재측정 기록입니다."],
     ["청소 기록입니다.", "과거 조치와 후속 확인을 검토하세요.", "재측정 기록입니다."]),
    (["청소 기록입니다.", "청소 기록입니다.", "재측정 기록입니다."],
     ["과거 조치와 후속 확인을 검토하세요.", "청소 기록입니다.", "재측정 기록입니다."]),
    ([" 청소 기록입니다. ", "청소 기록입니다.", "재측정 기록입니다."],
     ["과거 조치와 후속 확인을 검토하세요.", " 청소 기록입니다. ", "재측정 기록입니다."]),
], ids=["summary_only", "summary_one", "summary_two", "three_distinct_observations",
        "summary_duplicate", "observation_duplicate", "whitespace_duplicate"])
def test_history_preserves_observations_and_adds_distinct_summary_only_with_free_slot(observations, expected):
    from app.agents.handoff import AgentDraft

    value = context()
    handoffs = narrative_handoffs(value)
    proposed = draft("history", value)
    proposed.summary = "과거 조치와 후속 확인을 검토하세요."
    proposed.findings = [Finding(interpretation=text, evidence_ids=proposed.evidence_ids[:1],
                                relationship="observation") for text in observations]
    valid = AgentDraft.model_validate_json(proposed.model_dump_json())
    assert len(valid.findings) <= 3
    handoffs[2] = hydrate_handoff(valid, "history", value, evidence_catalog("history", value))
    result = assemble_diagnosis(value, handoffs, integrated())
    assert [finding.detail for finding in result.history_findings] == expected


def test_synthesis_failure_describes_analysis_limit_without_claiming_verification():
    value = context()
    result = assemble_diagnosis(value, narrative_handoffs(value), None, ["schema_validation"])
    text = result.headline + "\n" + "\n".join(result.counter_evidence)
    assert "분석 실패" in text and "제한" in text
    assert "검증된" not in text and "종합 검증 실패" not in text


def test_prompts_allow_source_numbers_and_request_narrative(tmp_path):
    value = context()
    prompts = {}

    async def create(**params):
        payload = json.loads(params["messages"][1]["content"])
        name = payload.get("agent_name", "synthesis")
        prompts[name] = params["messages"][0]["content"]
        result = draft(name, value) if name != "synthesis" else synthesis(payload)
        return response(result.model_dump_json())

    agent, _ = gateway(create, tmp_path)
    asyncio.run(agent.analyze(value))
    for prompt in [*prompts.values(), SYSTEM_INSTRUCTIONS, EQUIPMENT_INSTRUCTIONS]:
        assert "do not restate numeric" not in prompt
        assert "Keep prose qualitative" not in prompt
        assert "140" not in prompt
        assert "paragraph" in prompt.lower() or "문단" in prompt
        assert "numbers and dates" in prompt.lower() or "수치와 날짜" in prompt
    assert "latest measurement date" in prompts["trend"]
    assert "actual recorded actions" in prompts["history"]
    assert "700" in prompts["synthesis"]
    assert "Integrate ALL weeklyExplanationFacts" not in EQUIPMENT_INSTRUCTIONS
