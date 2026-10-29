"""Independent LLM calls, immutable provenance, and real hand-off synthesis."""
import asyncio
import copy
import json
import types
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.handoff import (
    AgentDraft, Candidate, Finding, Period, analysis_period, evidence_catalog,
    handoff_markdown, hydrate_handoff,
)
from app.agents.orchestrator import MultiAgentAnalysisGateway, SynthesisDraft, ToolBudget, analysis_configuration
from app.ai_analysis import AiAnalysisPeriod, AiAnalysisService, OpenAISettings
from app.equipment_analysis import build_equipment_context
from tests.test_ai_reliability import equipment_result, mixed_trace, response
from tests.test_prefetched_analysis import prepared_context


def context():
    value = prepared_context()
    value.update(datasetId="1", equipment={"id": "V001"}, fftInventory={"start": "2026-01-01 00:00:00", "end": "2026-01-02 00:00:00"},
                 trend={"available": True, "period": {"start": "2026-01-01 00:00:00", "end": "2026-01-02 00:00:00"},
                        "metrics": [{"key": "velocity", "unit": "mm/s", "mean": 1.2, "latestValue": 1.2, "sampleCount": 2}]})
    value["preparedFftEvidence"]["relatedHistory"] = [{"recordId": 1, "relatedHistory": {"cutoffDate": "2026-01-01", "items": [
        {"sourceRecordId": "h1", "date": "2025-12-01", "issue": "회전체 진동", "analysis": "불평형 점검", "result": "청소 후 재측정", "feedback": "추적 점검"}]}}]
    return value


def draft(name, value, catalog=None):
    facts = list((catalog or evidence_catalog(name, value)).values())
    # Select original scalar facts for all records, including numbers and causes.
    chosen = [fact for fact in facts if fact.unit or fact.supports_causes or fact.kind == "history"][:32] or facts[:1]
    return AgentDraft(agent_name=name, equipment_id=value["equipment"]["id"], analysis_period=analysis_period(name, value),
        status="ready", summary="원본 근거를 바탕으로 동일 조건의 점검이 필요합니다.", findings=[],
        evidence_ids=[fact.evidence_id for fact in chosen], source_record_ids=sorted({fact.source_record_id for fact in chosen if fact.source_record_id}),
        candidate_causes=[], limitations=["현장 운전 조건 확인이 필요합니다."], recommended_checks=["같은 조건에서 재측정하세요."])


def synthesis(payload):
    value = equipment_result()
    return SynthesisDraft(headline=value.headline, risk_level=value.risk_level, risk_label=value.risk_label,
        likely_causes=[], counter_evidence=value.counter_evidence, recommended_actions=value.recommended_actions,
        used_agents=[item["agent_name"] for item in payload["handoffs"]],
        evidence_ids=[row[0] for row in payload["evidence_catalog"]["rows"]][:96])


class FakeClient:
    def __init__(self, create):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        self.closed = False

    async def close(self):
        self.closed = True


def gateway(create, tmp_path):
    client = FakeClient(create)
    return MultiAgentAnalysisGateway(OpenAISettings("fake", "test", 2), client_factory=lambda **_: client, trace_dir=tmp_path), client


def test_three_llm_calls_are_parallel_and_synthesis_uses_deduplicated_json(tmp_path):
    value = context()
    requests, entered = [], set()
    original = copy.deepcopy(value)

    async def run():
        barrier = asyncio.Event()
        async def create(**params):
            requests.append(copy.deepcopy(params))
            payload = json.loads(params["messages"][1]["content"])
            if "agent_name" in payload:
                name = payload["agent_name"]
                entered.add(name)
                if len(entered) == 3:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), 1)
                result = draft(name, value)
            else:
                assert entered == {"trend", "fft", "history"}
                assert "markdown" not in json.dumps(payload)
                assert all("evidence" not in item and "evidence_ids" in item for item in payload["handoffs"])
                ids = [row[0] for row in payload["evidence_catalog"]["rows"]]
                assert len(ids) == len(set(ids))
                result = synthesis(payload)
            return response(result.model_dump_json())
        agent, client = gateway(create, tmp_path)
        result = await agent.analyze(value)
        assert client.closed
        return result

    result = asyncio.run(run())
    assert len(requests) == 4
    assert value == original
    assert result.fft_reference_record_ids == [1, 2]
    report = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert len(report['handoffs']) == 3
    assert len(report['metrics']['completions']) == 4
    assert report['metrics']['tool_calls'] == 0
    assert report['metrics']['fallback'] is False
    markdown_path = next(tmp_path.glob('*.md'))
    assert markdown_path.stem == report['request_id']
    markdown = markdown_path.read_text(encoding='utf-8')
    assert f"- Dataset: {report['dataset_id']}" in markdown
    assert '- LLM calls: 4' in markdown
    for item in report['handoffs']:
        assert item['markdown'] in markdown
        agent_file = tmp_path / str(report['dataset_id']) / f"{item['json']['agent_name']}.md"
        agent_markdown = agent_file.read_text(encoding='utf-8')
        assert report['request_id'] in agent_markdown
        assert agent_markdown.endswith(item['markdown'].rstrip() + '\n')


def test_candidate_wording_does_not_require_diagnostic_support():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    fact = next(f for f in catalog.values() if 'unbalance' in f.supports_causes)
    result.candidate_causes=[Candidate(cause='BPFO', confidence='high', rationale='외륜 결함 가능성이 있습니다.', evidence_ids=[fact.evidence_id])]
    assert hydrate_handoff(result,'fft',value,catalog).candidate_causes[0].cause == 'BPFO'
    result.candidate_causes=[Candidate(cause='unbalance', confidence='medium', rationale='불평형 점검이 필요합니다.', evidence_ids=[fact.evidence_id])]
    assert hydrate_handoff(result,'fft',value,catalog).candidate_causes[0].cause == 'unbalance'


def test_condition_comparison_wording_is_not_a_rejection_rule():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    result.findings=[Finding(interpretation='진폭 변화 비교입니다.', evidence_ids=result.evidence_ids[:2], relationship='comparison')]
    assert hydrate_handoff(result,'fft',value,catalog).llm_success


def test_partial_failure_is_explicit_and_not_forwarded_as_a_valid_interpretation(tmp_path):
    value=context(); calls=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); calls.append(payload.get('agent_name','synthesis'))
        if payload.get('agent_name') == 'history': return response('{}')
        if 'agent_name' in payload: return response(draft(payload['agent_name'],value).model_dump_json())
        history=next(item for item in payload['handoffs'] if item['agent_name']=='history')
        assert history['status']=='failed' and not history['llm_success']
        assert history['findings']==[] and history['failure_codes']
        return response(synthesis(payload).model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert calls.count('history')==1 and len(calls)==4
    assert 'HISTORY' in result.counter_evidence[0]


def test_cache_hit_skips_all_specialist_calls_and_force_refreshes():
    value=context(); requests=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); requests.append(payload)
        return response((draft(payload['agent_name'],value) if 'agent_name' in payload else synthesis(payload)).model_dump_json())
    agent,_=gateway(create,None)
    async def run():
        service=AiAnalysisService(agent,'test')
        first=await service.analyze(value)
        second=await service.analyze(value)
        third=await service.analyze(value,force=True)
        assert not first.cached and second.cached and not third.cached
    asyncio.run(run())
    assert len(requests)==8


def test_same_equipment_different_dataset_and_source_caches_call_roles_again(tmp_path):
    value = context() | {'sourceFingerprint': 'source-a'}
    requests = []
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        requests.append(payload.get('agent_name', 'synthesis'))
        return response((draft(payload['agent_name'], value) if 'agent_name' in payload else synthesis(payload)).model_dump_json())
    agent, _ = gateway(create, None)

    async def run():
        service = AiAnalysisService(agent, 'test', cache_dir=tmp_path)
        assert not (await service.analyze(value, dataset_id='1')).cached
        assert (await service.analyze(value, dataset_id='1')).cached
        assert len(requests) == 4
        other_dataset = value | {'datasetId': '2'}
        assert not (await service.analyze(other_dataset, dataset_id='2')).cached
        other_source = value | {'sourceFingerprint': 'source-b'}
        assert not (await service.analyze(other_source, dataset_id='1')).cached
        assert not (await service.analyze(value, dataset_id='1', force=True)).cached
        for name in ('trend', 'fft', 'history', 'synthesis'):
            assert requests.count(name) == 4
        assert len(list(tmp_path.glob('*.json'))) == 3

    asyncio.run(run())


def test_tool_budget_is_shared_and_deduplicates_before_await():
    calls=[]
    async def execute(name,args):
        calls.append(args); await asyncio.sleep(0); return {'status':'ready'}
    async def run():
        budget=ToolBudget(execute)
        results=await asyncio.gather(*[budget.call('get_fft_evidence',{'record_id':rid}) for rid in [1,1,2,3,4,5]])
        assert len(calls)==4 and budget.remaining==0
        assert results[1]['reason']=='duplicate_tool_call'
        assert results[-1]['reason']=='shared_tool_budget_exhausted'
    asyncio.run(run())


def test_missing_schema_fields_fail():
    with pytest.raises(ValidationError): AgentDraft.model_validate_json('{}')


def test_mode_configuration_separates_cache_inputs():
    assert analysis_configuration('multi','test') != analysis_configuration('single','test')


@pytest.mark.parametrize('mode', ['multi', 'single'])
def test_no_validation_policy_separates_old_cache(tmp_path, mode):
    from tests.test_ai_analysis import CountingGateway
    from app.ai_analysis import PROMPT_VERSION
    old_config = {
        'mode': mode, 'agentVersion': 'cms-multi-agent-v4-compact',
        'handoffVersion': 'source-linked-handoff-v6-compact',
        'agents': ['trend', 'fft', 'history', 'synthesis'] if mode == 'multi' else ['single'],
        'models': {name: 'test' for name in ('trend', 'fft', 'history', 'synthesis')},
        'specialistRepairs': 1, 'synthesisRepairs': 1, 'validationPolicyVersion': 'source-facts-only-v2',
        'additionalToolBudget': 4, 'fftCatalogLimit': 128, 'conditionDependencies': True,
        'serverWeeklyFacts': True, 'synthesisRole': 'integration-only',
    }
    old_context = context() | {'agentConfiguration': old_config}
    new_config = analysis_configuration(mode, 'test')
    new_context = context() | {'agentConfiguration': new_config}

    async def run():
        backend = CountingGateway()
        service = AiAnalysisService(backend, 'test', cache_dir=tmp_path)
        await service.analyze(old_context, dataset_id='1')
        old_file = next(tmp_path.glob('*.json'))
        old_bytes = old_file.read_bytes()
        result = await service.analyze(new_context, dataset_id='1')
        assert not result.cached and backend.calls == 2
        assert (await service.analyze(new_context, dataset_id='1')).cached
        assert old_file.read_bytes() == old_bytes
        assert len(list(tmp_path.glob('*.json'))) == 2

    asyncio.run(run())
    assert new_config['specialistRepairs'] == new_config['synthesisRepairs'] == 0
    assert new_config['outputValueValidation'] is False
    assert new_config['validationPolicyVersion'] == 'disabled-poc-v1'
    assert new_config['agentVersion'] == 'cms-multi-agent-v6-linked-measurements'
    assert new_config['handoffVersion'] == 'source-linked-handoff-v8-measurement-bundles'
    assert PROMPT_VERSION == 'cms-dashboard-analysis-v12-narrative-no-value-validation'


def test_trace_reports_completion_without_claiming_validation(tmp_path):
    value = context()
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        result = draft(payload['agent_name'], value) if 'agent_name' in payload else synthesis(payload)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason='stop',
            message=types.SimpleNamespace(content=result.model_dump_json(), refusal=None, tool_calls=None))],
            usage=types.SimpleNamespace(prompt_tokens=11, completion_tokens=7))
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    trace = json.loads(next(tmp_path.glob('*.json')).read_text(encoding='utf-8'))
    assert trace['synthesis']['status'] == 'completed'
    assert trace['synthesis']['diagnosis'] == result.model_dump(mode='json', by_alias=True)
    assert trace['request_id'] and trace['dataset_id'] == '1'
    assert trace['metrics']['tool_calls'] == 0
    for name, metric in trace['metrics']['agents'].items():
        assert metric['seconds'] >= 0 and metric['llm_seconds'] >= 0
        assert metric['llm_calls'] == 1
        assert metric['input_tokens'] == 11 and metric['output_tokens'] == 7
        assert metric['repair_seconds'] == 0
        assert metric.get('validation_seconds', 0) == 0
        assert metric.get('validation_assembly_seconds', 0) == 0
        assert metric['status'] == ('completed' if name == 'synthesis' else 'ready')
    assert '- Status: completed' in (tmp_path / '1' / 'synthesis.md').read_text(encoding='utf-8')
    assert 'validated' not in next(tmp_path.glob('*.md')).read_text(encoding='utf-8')


def test_no_correction_requests_are_logged(tmp_path, caplog):
    value = context(); requests = []; marker = 'PRIVATE_PROVIDER_PAYLOAD'
    async def create(**params):
        requests.append(copy.deepcopy(params))
        payload = json.loads(params['messages'][1]['content'])
        if payload.get('agent_name') == 'history' or 'agent_name' not in payload:
            return response('{"private": "' + marker)
        return response(draft(payload['agent_name'], value).model_dump_json())
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert len(requests) == 4 and all(len(item['messages']) == 2 for item in requests)
    trace = json.loads(next(tmp_path.glob('*.json')).read_text(encoding='utf-8'))
    assert trace['synthesis']['status'] == 'limited'
    assert 'schema_validation' in trace['synthesis']['failure_codes']
    assert result.risk_level == 'unknown'
    assert marker not in caplog.text
    assert all(marker not in path.read_text(encoding='utf-8') for path in tmp_path.rglob('*') if path.is_file())
    assert all('details' not in failure for failure in trace['metrics']['validation_failures'])
    assert all(item['attempt'] == 1 for item in trace['metrics']['completions'])


def test_unknown_citations_do_not_trigger_service_record_queries(tmp_path):
    value = context(); calls = []
    async def execute(name, arguments):
        calls.append((name, arguments))
        pytest.fail('Citations must not cause extra record queries')
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        result = draft(payload['agent_name'], value) if 'agent_name' in payload else synthesis(payload)
        result.evidence_ids.append('fft:999999')
        if 'agent_name' in payload:
            result.source_record_ids.append('fft:999999')
        return response(result.model_dump_json())
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(AiAnalysisService(agent, 'test').analyze(value, execute=execute))
    assert result.analysis.fft_reference_record_ids == [1, 2]
    assert calls == []


def test_specialists_accept_prose_without_value_validation(tmp_path):
    value = context()
    original_context = copy.deepcopy(value)
    requests = []
    returned_trend_text = '2099-01-01 진폭 999.99 g, 1780 rpm에서 측정했습니다.'
    returned_headline = '전문 결과를 종합해 점검하세요.'

    async def create(**params):
        requests.append(copy.deepcopy(params))
        payload = json.loads(params['messages'][1]['content'])
        if 'agent_name' in payload:
            name = payload['agent_name']
            result = draft(name, value)
            result.agent_name = 'history' if name != 'history' else 'fft'
            result.equipment_id = 'other-equipment'
            result.analysis_period = Period(start='2099-01-01', end='2099-01-02')
            result.source_record_ids = ['fft:99999']
            result.summary = returned_trend_text
            result.evidence_ids += ['unknown:top', result.evidence_ids[0]]
            result.findings = [Finding(interpretation='2099-02-03 진동 555 mm/s입니다.',
                evidence_ids=['unknown:finding'], relationship='observation')]
            result.candidate_causes = [Candidate(cause='새 원인', confidence='low',
                rationale='9999 Hz 확인이 필요합니다.', evidence_ids=['unknown:candidate'])]
        else:
            assert {item['agent_name'] for item in payload['handoffs']} == {'trend', 'fft', 'history'}
            assert all(item['equipment_id'] == 'V001' for item in payload['handoffs'])
            result = synthesis(payload)
            result.headline = returned_headline
        return response(result.model_dump_json())

    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert len(requests) == 4
    assert result.trend_summary == returned_trend_text
    assert result.headline == returned_headline
    assert value == original_context
    assert result.trend_findings[0].detail == '2099-02-03 진동 555 mm/s입니다.'
    assert result.fft_analysis_period.start == datetime(2026, 1, 1)
    assert result.fft_reference_record_ids == [1, 2]
    trace = json.loads(next(tmp_path.glob('*.json')).read_text())
    for item in trace['handoffs']:
        handoff = item['json']
        assert handoff['llm_success'] and handoff['equipment_id'] == 'V001'
        assert 'fft:99999' not in handoff['source_record_ids']
        assert all(not fact['evidence_id'].startswith('unknown:') for fact in handoff['evidence'])
        if handoff['agent_name'] == 'history':
            assert handoff['source_queries'][0]['reference_fft_record_id'] == 1
            assert handoff['source_queries'][0]['cutoff_date'] == '2026-01-01'


def test_synthesis_accepts_prose_without_value_validation(tmp_path):
    value = context()
    original_context = copy.deepcopy(value)
    requests = []
    returned_headline = '2099-04-05 진폭 999 mm/s, 9999 Hz를 확인하세요.'
    async def create(**params):
        requests.append(copy.deepcopy(params))
        payload = json.loads(params['messages'][1]['content'])
        if 'agent_name' in payload:
            result = draft(payload['agent_name'], value)
        else:
            result = synthesis(payload)
            result.headline = returned_headline
            result.risk_label = '999 g 확인'
            result.used_agents = ['fft', 'fft']
            result.evidence_ids = ['unknown:synthesis', 'unknown:synthesis']
        return response(result.model_dump_json())
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert len(requests) == 4
    assert result.headline == returned_headline
    assert result.risk_label == '999 g 확인'
    assert value == original_context


@pytest.mark.parametrize('bad_response', ['{', '{}', 'truncated'])
def test_invalid_specialist_json_does_not_retry(tmp_path, bad_response):
    value = context()
    requests = []
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        name = payload.get('agent_name', 'synthesis')
        requests.append(name)
        if name == 'history':
            result = response(bad_response)
            if bad_response == 'truncated':
                result.choices[0].finish_reason = 'length'
            return result
        return response((draft(name, value) if name != 'synthesis' else synthesis(payload)).model_dump_json())
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert requests.count('history') == 1 and len(requests) == 4
    assert result.trend_summary == '원본 근거를 바탕으로 동일 조건의 점검이 필요합니다.'
    trace = json.loads(next(tmp_path.glob('*.json')).read_text())
    history = next(item['json'] for item in trace['handoffs'] if item['json']['agent_name'] == 'history')
    assert history['status'] == 'failed' and not history['llm_success']
    assert history['findings'] == []


@pytest.mark.parametrize('bad_response', ['{', '{}', 'truncated'])
def test_invalid_synthesis_json_preserves_specialist_results(tmp_path, bad_response):
    value = context()
    requests = []
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        name = payload.get('agent_name', 'synthesis')
        requests.append(name)
        if name != 'synthesis':
            result = draft(name, value)
            result.findings = [Finding(interpretation='전문 해석을 보존하세요.',
                evidence_ids=result.evidence_ids[:1], relationship='observation')]
            return response(result.model_dump_json())
        result = response(bad_response)
        if bad_response == 'truncated':
            result.choices[0].finish_reason = 'length'
        return result
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert requests.count('synthesis') == 1 and len(requests) == 4
    assert result.risk_level == 'unknown'
    assert result.trend_summary == '원본 근거를 바탕으로 동일 조건의 점검이 필요합니다.'
    assert result.fft_findings[0].detail == '전문 해석을 보존하세요.'
    assert [item.detail for item in result.history_findings] == [
        '원본 근거를 바탕으로 동일 조건의 점검이 필요합니다.', '전문 해석을 보존하세요.']


@pytest.mark.parametrize('failed_agent', ['history', 'synthesis'])
def test_partial_provider_failure_keeps_other_domains(tmp_path, failed_agent):
    value = context()
    requests = []
    async def create(**params):
        payload = json.loads(params['messages'][1]['content'])
        name = payload.get('agent_name', 'synthesis')
        requests.append(name)
        if name == failed_agent:
            raise RuntimeError('provider failure')
        return response((draft(name, value) if name != 'synthesis' else synthesis(payload)).model_dump_json())
    agent, _ = gateway(create, tmp_path)
    result = asyncio.run(agent.analyze(value))
    assert requests.count(failed_agent) == 1 and len(requests) == 4
    assert result.trend_summary == '원본 근거를 바탕으로 동일 조건의 점검이 필요합니다.'
    if failed_agent == 'history':
        assert 'HISTORY' in '\n'.join(result.counter_evidence)
    else:
        assert result.risk_level == 'unknown'


def test_empty_domain_skips_its_llm_and_mentions_limit(tmp_path):
    value=context(); value['preparedFftEvidence']['relatedHistory']=[]; names=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); names.append(payload.get('agent_name','synthesis'))
        return response((draft(payload['agent_name'],value) if 'agent_name' in payload else synthesis(payload)).model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert names==['trend','fft','synthesis']
    assert 'HISTORY' in result.counter_evidence[0]


def test_all_specialists_invalid_return_limited_without_legacy_gateway(monkeypatch,tmp_path):
    from app.ai_analysis import OpenAIAnalysisGateway
    value=context(); fallback=[]
    async def create(**params): return response('{}')
    async def legacy(self,context,execute=None,**kwargs):
        fallback.append(context); return equipment_result()
    monkeypatch.setattr(OpenAIAnalysisGateway,'analyze',legacy)
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert len(fallback)==0 and result.risk_level == 'unknown'
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert not trace['metrics']['fallback'] and len(trace['metrics']['completions'])==3
    assert trace['synthesis']['status'] == 'limited'
    assert trace['request_id'] in (tmp_path/'1'/'synthesis.md').read_text()
    assert result.headline in (tmp_path/'1'/'synthesis.md').read_text()


def test_provider_outage_is_not_retried_or_fallbacked(monkeypatch,tmp_path):
    from app.ai_analysis import AiProviderError, OpenAIAnalysisGateway
    value=context(); attempts=[]
    async def create(**params): attempts.append(params); raise RuntimeError('provider failure')
    async def legacy(*args,**kwargs): pytest.fail('Do not retry shared service outages')
    monkeypatch.setattr(OpenAIAnalysisGateway,'analyze',legacy)
    agent,_=gateway(create,tmp_path)
    with pytest.raises(AiProviderError): asyncio.run(agent.analyze(value))
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert len(attempts)==3 and len(trace['metrics']['completions'])==3
    assert all(item['input_tokens'] is None for item in trace['metrics']['completions'])
    assert trace['metrics']['fallback'] is False


def test_prefetch_reuse_force_and_source_change_preserve_isolation(tmp_path,monkeypatch):
    from app.data_loader import load_datasets
    from app import equipment_evidence
    from tests.test_app import make_data_dir
    dataset=load_datasets(make_data_dir(tmp_path))['1']; calls=[]
    original=equipment_evidence.prepare_fft_evidence
    def prepare(*args,**kwargs): calls.append(1); return original(*args,**kwargs)
    monkeypatch.setattr(equipment_evidence,'prepare_fft_evidence',prepare)
    first=build_equipment_context('1',dataset,[],None,force=True)
    second=build_equipment_context('1',dataset,[],None)
    assert first==second and len(calls)==1
    second['trend']['metrics'].clear()
    assert build_equipment_context('1',dataset,[],None)['trend']['metrics']
    build_equipment_context('1',dataset,[],None,force=True)
    assert len(calls)==2
    changed=copy.deepcopy(dataset); changed['fft']['_rpm']=1800
    assert build_equipment_context('1',changed,[],None)['sourceFingerprint']!=first['sourceFingerprint']
    assert len(calls)==3


def test_large_catalog_is_bounded_and_represents_all_measurement_groups():
    from app.agents.handoff import Evidence, offered_catalog, catalog_prompt
    catalog={}
    for index in range(600):
        fact=Evidence(evidence_id=f'f:{index}', source=f'fft.groups[{index%3}].monthlyComponents[{index}].maximum.amplitude',
            source_record_id=f'fft:{index}',value=float(index),unit='g',measured_at='2026-01-01',
            period=Period(start='2026-01-01',end='2026-01-02'), group_id=f'group:{index%3}',kind='measurement',supports_causes=[])
        catalog[fact.evidence_id]=fact
    selected=offered_catalog('fft',catalog)
    assert len(selected)==128 and {fact.group_id for fact in selected.values()}=={'group:0','group:1','group:2'}
    assert len(catalog_prompt(selected)['rows'])==128


def test_api_response_contract_and_configured_default_gateway(tmp_path,monkeypatch):
    from app.main import create_app
    from tests.test_app import make_data_dir, post, FakeAiGateway
    monkeypatch.setenv('AI_ANALYSIS_MODE','multi')
    fake=FakeAiGateway()
    app=create_app(make_data_dir(tmp_path),ai_gateway=fake,ai_cache_dir=tmp_path/'cache')
    result=post(app,'/api/dashboard/1/ai-analysis',{'force':True})
    assert result.status_code==200
    assert set(result.json())=={'status','cached','model','generatedAt','analysis','fftSeverityAssessments'}
    assert fake.contexts[-1]['agentConfiguration']['mode']=='multi'
    assert not fake.contexts[-1].get('demoPresentation')


@pytest.mark.parametrize('text', ['외륜 결함입니다.', '현재 설비의 베어링 고장이 확인되었습니다.', '내륜 결함이 존재합니다.', '외륜 결함이 확정되었습니다.'])
def test_definitive_defect_wording_is_not_rejected(text):
    value=context(); result=draft('trend',value)
    result.summary=text
    assert hydrate_handoff(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_certainty_wording_does_not_reject_source_valid_facts():
    value=context(); result=draft('trend',value)
    result.summary='외륜 결함을 확정할 수 없지만, 내륜 결함이 확인되었습니다.'
    assert hydrate_handoff(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_history_query_cutoff_and_reference_are_server_owned():
    value=context(); catalog=evidence_catalog('history',value)
    result=hydrate_handoff(draft('history',value,catalog),'history',value,catalog)
    assert result.source_queries[0].reference_fft_record_id==1
    assert result.source_queries[0].cutoff_date=='2026-01-01'
    assert result.source_queries[0].source_record_ids==['history:h1']
    assert 'strictly before 2026-01-01' in handoff_markdown(result)
    result.source_queries[0].cutoff_date='2099-01-01'
    assert value['preparedFftEvidence']['relatedHistory'][0]['relatedHistory']['cutoffDate'] == '2026-01-01'


def test_server_hydrates_the_union_of_finding_and_top_level_citations():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    fact=next(item for item in catalog.values() if item.evidence_id not in result.evidence_ids and item.source_record_id)
    result.findings=[Finding(interpretation='原本 근거 확인이 필요합니다.', evidence_ids=[fact.evidence_id],relationship='observation')]
    result.source_record_ids=[]
    handoff=hydrate_handoff(result,'fft',value,catalog)
    assert fact in handoff.evidence
    assert fact.source_record_id in handoff.source_record_ids


def test_specialist_calls_existing_fft_tool_and_hands_queried_evidence_to_main(tmp_path):
    value=context(); selected=copy.deepcopy(mixed_trace()[0]['result']['records'][0]['fft'])
    selected.update(recordId=3,measuredAt='2026-01-02 00:00:00')
    requests=[]; tools=[]
    async def execute(name,args):
        tools.append((name,args)); return {'status':'ready','fft':selected}
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); requests.append(params)
        if payload.get('agent_name')=='fft':
            if len([p for p in requests if json.loads(p['messages'][1]['content']).get('agent_name')=='fft'])==1:
                return types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason='tool_calls', message=types.SimpleNamespace(
                    content=None,refusal=None,tool_calls=[types.SimpleNamespace(id='extra',type='function',function=types.SimpleNamespace(
                        name='get_fft_evidence',arguments=json.dumps({'record_id':3})))]))])
            tool_payload=json.loads(next(msg['content'] for msg in params['messages'] if isinstance(msg,dict) and msg.get('role')=='tool'))
            eid=next(row[0] for row in tool_payload['evidence_catalog']['rows'] if row[3]=='fft:3')
            result=draft('fft',value);result.evidence_ids.append(eid)
            return response(result.model_dump_json())
        if 'agent_name' in payload: return response(draft(payload['agent_name'],value).model_dump_json())
        assert any(row[3]=='fft:3' for row in payload['evidence_catalog']['rows'])
        return response(synthesis(payload).model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value,execute))
    assert tools==[('get_fft_evidence',{'record_id':3})]
    assert 3 in result.fft_reference_record_ids


@pytest.mark.parametrize('text',['불평형입니다.','축정렬 불량입니다.','진폭 기준으로 외륜 결함입니다.','불평형이 확실합니다.'])
def test_physical_cause_wording_is_not_rejected(text):
    value=context(); result=draft('trend',value); result.summary=text
    assert hydrate_handoff(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_level_and_sample_metadata_retain_their_rule_units():
    value=context(); value['levelAnalysis']={'normalMean':1.0,'recommended':{'warningThreshold':2.0}}
    catalog=evidence_catalog('trend',value)
    assert next(item for item in catalog.values() if item.source.endswith('.normalMean')).unit=='mm/s'
    assert next(item for item in catalog.values() if item.source.endswith('.warningThreshold')).unit=='mm/s'
    assert next(item for item in catalog.values() if item.source.endswith('.sampleCount')).unit=='count'


def test_unknown_sampling_bins_are_not_relabelled_hz_or_used_for_a_cause():
    value=context(); record=value['preparedFftEvidence']['representativeRecords'][0]
    record['frequencyUnit']='bin'; record['spectrum']={'peaks':[{'frequency':10,'amplitude':1.2}]}
    catalog=evidence_catalog('fft',value)
    frequency=next(item for item in catalog.values() if item.source.endswith('.spectrum.peaks[0].frequency'))
    assert frequency.unit=='bin'
    assert not any('unbalance' in item.supports_causes for item in catalog.values() if item.source_record_id=='fft:1')


def test_failed_specialists_do_not_invoke_legacy_tools(monkeypatch,tmp_path):
    from app.ai_analysis import OpenAIAnalysisGateway
    value=context(); calls=[]
    async def create(**params): return response('{}')
    async def execute(name,args): calls.append(args); return {'status':'ready'}
    async def legacy(self,context,execute=None,**kwargs):
        for rid in range(6): await execute('get_fft_evidence',{'record_id':rid})
        return equipment_result()
    monkeypatch.setattr(OpenAIAnalysisGateway,'analyze',legacy)
    agent,_=gateway(create,tmp_path)
    asyncio.run(agent.analyze(value,execute))
    assert len(calls)==0
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['metrics']['tool_calls']==0


def test_success_synthesis_markdown_matches_completed_result(tmp_path):
    value=context()
    async def create(**params):
        payload=json.loads(params['messages'][1]['content'])
        return response((draft(payload['agent_name'],value) if 'agent_name' in payload else synthesis(payload)).model_dump_json())
    agent,_=gateway(create,tmp_path); result=asyncio.run(agent.analyze(value))
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['synthesis']['status'] == 'completed'
    assert trace['synthesis']['diagnosis'] == result.model_dump(mode='json',by_alias=True)
    assert result.headline in (tmp_path/'1'/'synthesis.md').read_text()


def test_candidate_schema_allows_new_physical_hypotheses():
    assert Candidate(cause='윤활 불량', confidence='low', rationale='윤활 상태를 추가 점검하세요.', evidence_ids=['f:1']).cause == '윤활 불량'


def test_compact_catalog_preserves_every_source_fact():
    from app.agents.handoff import catalog_prompt
    catalog = evidence_catalog('fft', context())
    table = catalog_prompt(catalog)
    for row in table['rows']:
        eid, value, unit, record, stamp, cid, field, support, kind = row
        prefix, pid, group = table['contexts'][cid]
        source = f'{prefix}.{field}' if prefix else field
        original = catalog[eid]
        assert (source, value, unit, record, stamp, group, support, kind) == (
            original.source, original.value, original.unit, original.source_record_id,
            original.measured_at, original.group_id, original.supports_causes, original.kind)
        assert table['periods'][pid] == [original.period.start, original.period.end]


def test_bounded_fft_catalog_keeps_citable_condition_dependencies():
    from app.agents.handoff import Evidence, offered_catalog
    base = dict(source_record_id='fft:1', value=1.0, unit='g', measured_at='2026-01-01',
                period=Period(start=None, end=None), group_id='group:a', kind='measurement', supports_causes=[])
    catalog = {f'f:{i}': Evidence(evidence_id=f'f:{i}', source=f'fft.representativeRecords[0].peak{i}.amplitude', **base) for i in range(150)}
    rpm = Evidence(evidence_id='f:rpm', source='fft.representativeRecords[0].diagnosis.rpm', **(base | {'value': 1780.0, 'unit': 'rpm'}))
    catalog[rpm.evidence_id] = rpm
    selected = offered_catalog('fft', catalog, limit=1)
    assert len(selected) == 2 and selected['f:rpm'] == rpm


def test_server_assembly_preserves_domain_findings_and_all_limitations():
    from app.agents.orchestrator import assemble_diagnosis
    value = context()
    value['requiredCounterEvidence'] = [f'필수 제한 {i}' for i in range(8)]
    handoffs = []
    for name in ('trend', 'fft', 'history'):
        proposed = draft(name, value)
        proposed.findings = [Finding(interpretation='전문 관측 결과입니다.', evidence_ids=proposed.evidence_ids[:1], relationship='conflict')]
        handoffs.append(hydrate_handoff(proposed, name, value, evidence_catalog(name, value)))
    integrated = SynthesisDraft(headline='통합 판단입니다.', risk_level='caution', risk_label='주의',
        likely_causes=[], counter_evidence=['종합 제한'], recommended_actions=[], used_agents=['trend', 'fft', 'history'], evidence_ids=['t:1'])
    result = assemble_diagnosis(value, handoffs, integrated)
    assert result.trend_summary == handoffs[0].summary
    assert result.trend_findings[0].detail == handoffs[0].findings[0].interpretation
    assert result.trend_findings[0].heading == '상충 근거'
    assert len(result.counter_evidence) <= 4
    text = '\n'.join(result.counter_evidence)
    for note in value['requiredCounterEvidence'] + ['종합 제한']:
        assert note in text
    limited = assemble_diagnosis(value, handoffs, None, ['test_failure'])
    assert limited.risk_level == 'unknown' and limited.fft_findings == result.fft_findings
    assert limited.trend_summary == result.trend_summary


def test_integration_schema_cannot_override_server_domain_fields():
    result = SynthesisDraft(headline='점검하세요.', risk_level='unknown', risk_label='확인 필요', likely_causes=[],
        counter_evidence=[], recommended_actions=[], used_agents=['trend'], evidence_ids=['t:1']).model_dump()
    with pytest.raises(ValidationError):
        SynthesisDraft.model_validate(result | {'trend_summary': '덮어쓴 설명'})


def test_server_assembly_preserves_reference_overflow_without_breaking_public_limit():
    from app.agents.orchestrator import assemble_diagnosis
    value = context()
    handoffs = [hydrate_handoff(draft(name, value), name, value, evidence_catalog(name, value)) for name in ('trend', 'fft', 'history')]
    fft = handoffs[1]
    original = next(f for f in fft.evidence if f.source_record_id)
    fft.evidence = [original.model_copy(update={'evidence_id': f'f:{i}', 'source_record_id': f'fft:{i}'}) for i in range(1, 61)]
    result = assemble_diagnosis(value, handoffs, None)
    assert result.fft_reference_record_ids == list(range(1, 51))
    assert 'FFT 추가 참조 기록: ' + ', '.join(map(str, range(51, 61))) in '\n'.join(result.counter_evidence)


def test_long_domain_summary_is_preserved_instead_of_truncated():
    from app.agents.orchestrator import assemble_diagnosis
    value = context()
    handoffs = [hydrate_handoff(draft(name, value), name, value, evidence_catalog(name, value)) for name in ('trend', 'fft', 'history')]
    handoffs[1].summary = '추가 FFT 해석입니다.' * 150
    result = assemble_diagnosis(value, handoffs, None)
    assert handoffs[1].summary in '\n'.join(result.counter_evidence)
    assert len(result.fft_summary) <= 1200


def test_hydrate_handoff_copies_citation_union_and_uses_server_scope():
    from app.agents.handoff import hydrate_handoff
    value = context()
    original_context = copy.deepcopy(value)
    catalog = evidence_catalog('history', value)
    facts = list(catalog.values())
    proposed = draft('history', value)
    proposed.agent_name = 'fft'
    proposed.equipment_id = 'unrelated-equipment'
    proposed.analysis_period = Period(start='2099-01-01', end='2099-01-02')
    proposed.source_record_ids = ['history:invented']
    proposed.evidence_ids = [facts[0].evidence_id, facts[0].evidence_id, 'missing:top']
    proposed.findings = [Finding(interpretation='999 g at 2099-01-01',
        evidence_ids=[facts[1].evidence_id, 'missing:finding'], relationship='observation')]
    proposed.candidate_causes = [Candidate(cause='new cause', confidence='low',
        rationale='12345 rpm', evidence_ids=[facts[2].evidence_id, 'missing:candidate'])]
    result = hydrate_handoff(proposed, 'history', value, catalog)
    assert result.agent_name == 'history' and result.equipment_id == 'V001'
    assert result.analysis_period == Period(start='2025-12-01', end='2025-12-01')
    assert [fact.evidence_id for fact in result.evidence] == [fact.evidence_id for fact in facts[:3]]
    assert result.source_record_ids == ['history:h1']
    assert result.source_queries[0].reference_fft_record_id == 1
    assert result.source_queries[0].cutoff_date == '2026-01-01'
    assert result.findings[0].interpretation == '999 g at 2099-01-01'
    assert result.candidate_causes[0].rationale == '12345 rpm'
    assert result.llm_success and result.failure_codes == []
    result.evidence[0].value = 'changed after assembly'
    result.analysis_period.start = 'changed after assembly'
    assert catalog[facts[0].evidence_id].value != 'changed after assembly'
    assert value == original_context
