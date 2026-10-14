"""Independent LLM calls, immutable provenance, and real hand-off synthesis."""
import asyncio
import copy
import json
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.handoff import (
    AgentDraft, Candidate, Finding, HandoffError, Period, analysis_period, evidence_catalog,
    handoff_markdown, validate_draft, validate_handoff,
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
    refs = sorted({int(fact["source_record_id"].split(":")[1]) for item in payload["handoffs"]
                   for fact in item["json"]["evidence"] if (fact["source_record_id"] or "").startswith("fft:")})
    value = equipment_result().model_copy(update={
        "fft_reference_record_ids": refs,
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-02") if refs else AiAnalysisPeriod(start=None, end=None),
        "fft_summary": "조회 근거를 바탕으로 동일 조건의 재측정이 필요합니다.",
        "likely_causes": [], "history_findings": [],
    })
    return SynthesisDraft(diagnosis=value, used_agents=[item["json"]["agent_name"] for item in payload["handoffs"]],
                          evidence_ids=[fact["evidence_id"] for item in payload["handoffs"] for fact in item["json"]["evidence"]][:96])


class FakeClient:
    def __init__(self, create):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        self.closed = False

    async def close(self):
        self.closed = True


def gateway(create, tmp_path):
    client = FakeClient(create)
    return MultiAgentAnalysisGateway(OpenAISettings("fake", "test", 2), client_factory=lambda **_: client, trace_dir=tmp_path), client


def test_three_llm_calls_are_parallel_and_synthesis_uses_json_and_markdown(tmp_path):
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
                for item in payload["handoffs"]:
                    assert item["markdown"] == handoff_markdown(__import__('app.agents.handoff', fromlist=['Handoff']).Handoff.model_validate(item["json"]))
                    assert '### Evidence' in item["markdown"]
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


@pytest.mark.parametrize('mutation,code', [
    ('identity', 'identity_mismatch'), ('period', 'analysis_period_mismatch'),
    ('evidence', 'unknown_evidence'), ('record', 'source_record_mismatch'),
    ('number', 'unsupported_measurement'), ('date', 'unsupported_date'),
])
def test_specialist_rejects_hallucinations(mutation, code):
    value = context(); catalog = evidence_catalog('fft', value); result = draft('fft', value, catalog)
    if mutation == 'identity': result.equipment_id = 'other'
    if mutation == 'period': result.analysis_period = Period(start='2099-01-01', end='2099-01-02')
    if mutation == 'evidence': result.evidence_ids.append('fft:imaginary')
    if mutation == 'record': result.source_record_ids.append('fft:99999')
    if mutation == 'number': result.summary = '진폭은 99.99 mm/s입니다.'
    if mutation == 'date': result.summary = '2099-01-01에 측정했습니다.'
    with pytest.raises(HandoffError) as rejected:
        validate_draft(result, 'fft', value, catalog)
    assert code in rejected.value.codes


@pytest.mark.parametrize('field,replacement', [('unit','g'), ('value',99.99), ('measured_at','2099-01-01'), ('source_record_id','fft:999'), ('period',Period(start='2099-01-01',end='2099-01-02'))])
def test_hydrated_handoff_cannot_change_original_evidence(field, replacement):
    value = context(); catalog = evidence_catalog('fft', value)
    result = validate_draft(draft('fft', value, catalog), 'fft', value, catalog).model_copy(deep=True)
    setattr(result.evidence[0], field, replacement)
    with pytest.raises(HandoffError):
        validate_handoff(result, catalog, value)


def test_findings_require_their_own_record_measurements():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    amplitude = next(f for f in catalog.values() if f.unit == 'g')
    result.findings = [Finding(interpretation='진폭 1.2 mm/s가 관측됩니다.', evidence_ids=[amplitude.evidence_id], relationship='observation')]
    with pytest.raises(HandoffError, match='unsupported_measurement'):
        validate_draft(result, 'fft', value, catalog)


def test_candidate_wording_does_not_require_diagnostic_support():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    fact = next(f for f in catalog.values() if 'unbalance' in f.supports_causes)
    result.candidate_causes=[Candidate(cause='BPFO', confidence='high', rationale='외륜 결함 가능성이 있습니다.', evidence_ids=[fact.evidence_id])]
    assert validate_draft(result,'fft',value,catalog).candidate_causes[0].cause == 'BPFO'
    result.candidate_causes=[Candidate(cause='unbalance', confidence='medium', rationale='불평형 점검이 필요합니다.', evidence_ids=[fact.evidence_id])]
    assert validate_draft(result,'fft',value,catalog).candidate_causes[0].cause == 'unbalance'


def test_condition_comparison_wording_is_not_a_rejection_rule():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    result.findings=[Finding(interpretation='진폭 변화 비교입니다.', evidence_ids=result.evidence_ids[:2], relationship='comparison')]
    assert validate_draft(result,'fft',value,catalog).llm_success


def test_partial_failure_is_explicit_and_not_forwarded_as_a_valid_interpretation(tmp_path):
    value=context(); calls=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); calls.append(payload.get('agent_name','synthesis'))
        if payload.get('agent_name') == 'history': return response('{}')
        if 'agent_name' in payload: return response(draft(payload['agent_name'],value).model_dump_json())
        history=next(item for item in payload['handoffs'] if item['json']['agent_name']=='history')
        assert history['json']['status']=='failed' and not history['json']['llm_success']
        assert history['json']['findings']==[] and 'Validation Failures' in history['markdown']
        return response(synthesis(payload).model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert calls.count('history')==2 and len(calls)==5
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


def test_specialist_schema_repair_keeps_evidence_and_uses_no_tools(tmp_path):
    value=context(); calls=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content']); name=payload.get('agent_name','synthesis')
        calls.append((name,params))
        if name=='trend' and sum(item[0]=='trend' for item in calls)==1:
            bad=draft(name,value).model_copy(update={'summary':'測定 999 mm/sです。'})
            return response(bad.model_dump_json())
        return response((draft(name,value) if name!='synthesis' else synthesis(payload)).model_dump_json())
    agent,_=gateway(create,tmp_path)
    asyncio.run(agent.analyze(value))
    assert [name for name,_ in calls].count('trend')==2
    repair=next(params for name,params in reversed(calls) if name=='trend')
    assert 'tools' not in repair and 'tool_choice' not in repair
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert next(item for item in trace['handoffs'] if item['json']['agent_name']=='trend')['json']['llm_success']


def test_synthesis_cannot_introduce_a_number_absent_from_handoffs(tmp_path):
    value=context(); synthesis_calls=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content'])
        if 'agent_name' in payload: return response(draft(payload['agent_name'],value).model_dump_json())
        result=synthesis(payload); synthesis_calls.append(params)
        if len(synthesis_calls)==1:
            result.diagnosis.fft_summary='진폭 999 mm/s입니다.'
        return response(result.model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert '999' not in result.fft_summary and len(synthesis_calls)==2


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
    assert not trace['metrics']['fallback'] and len(trace['metrics']['completions'])==6
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
    assert validate_draft(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_date_period_cannot_be_used_as_an_observation_date_for_an_aggregate():
    value=context(); result=draft('trend',value)
    result.summary='2026-01-01 진동 1.2 mm/s가 측정되었습니다.'
    with pytest.raises(HandoffError,match='measurement_date_mismatch'):
        validate_draft(result,'trend',value,evidence_catalog('trend',value))


def test_value_from_one_fft_record_cannot_be_assigned_to_another_date():
    value=context(); result=draft('fft',value)
    result.summary='2026-01-02 진폭 1.2 mm/s가 관측되었습니다.'
    with pytest.raises(HandoffError,match='measurement_date_mismatch'):
        validate_draft(result,'fft',value,evidence_catalog('fft',value))
    result.summary='2026-01-01 진폭 1.2 mm/s가 관측되었습니다.'
    assert validate_draft(result,'fft',value,evidence_catalog('fft',value)).llm_success


def test_observation_date_after_value_is_also_verified():
    value=context(); result=draft('fft',value)
    result.summary='진폭 1.2 mm/s가 2026-01-02에 관측되었습니다.'
    with pytest.raises(HandoffError,match='measurement_date_mismatch'):
        validate_draft(result,'fft',value,evidence_catalog('fft',value))


def test_certainty_wording_does_not_reject_source_valid_facts():
    value=context(); result=draft('trend',value)
    result.summary='외륜 결함을 확정할 수 없지만, 내륜 결함이 확인되었습니다.'
    assert validate_draft(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_history_query_cutoff_and_reference_are_preserved_and_checked():
    value=context(); catalog=evidence_catalog('history',value)
    result=validate_draft(draft('history',value,catalog),'history',value,catalog)
    assert result.source_queries[0].reference_fft_record_id==1
    assert result.source_queries[0].cutoff_date=='2026-01-01'
    assert result.source_queries[0].source_record_ids==['history:h1']
    assert 'strictly before 2026-01-01' in handoff_markdown(result)
    result.source_queries[0].cutoff_date='2099-01-01'
    with pytest.raises(HandoffError,match='history_query_mismatch'):
        validate_handoff(result,catalog,value)


def test_server_hydrates_the_union_of_finding_and_top_level_citations():
    value=context(); catalog=evidence_catalog('fft',value); result=draft('fft',value,catalog)
    fact=next(item for item in catalog.values() if item.evidence_id not in result.evidence_ids and item.source_record_id)
    result.findings=[Finding(interpretation='原本 근거 확인이 필요합니다.', evidence_ids=[fact.evidence_id],relationship='observation')]
    result.source_record_ids=[]
    handoff=validate_draft(result,'fft',value,catalog)
    assert fact in handoff.evidence
    assert fact.source_record_id in handoff.source_record_ids
    validate_handoff(handoff,catalog,value)


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
            eid=next(row[0] for row in tool_payload['evidence_catalog']['rows'] if row[4]=='fft:3')
            result=draft('fft',value);result.evidence_ids.append(eid)
            return response(result.model_dump_json())
        if 'agent_name' in payload: return response(draft(payload['agent_name'],value).model_dump_json())
        assert any(fact['source_record_id']=='fft:3' for h in payload['handoffs'] for fact in h['json']['evidence'])
        return response(synthesis(payload).model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value,execute))
    assert tools==[('get_fft_evidence',{'record_id':3})]
    assert 3 in result.fft_reference_record_ids


def test_source_owned_amplitude_grade_is_not_a_physical_defect_confirmation():
    from app.agents.handoff import prose_issues
    assert prose_issues('이는 진폭 기준 구간이므로 현재 상태는 베어링 케이지(FTF) 초기 결함입니다.',[])==[]
    assert prose_issues('진폭 등급으로 실제 베어링 결함이 확인되었습니다.',[]) == []


@pytest.mark.parametrize('records',[[],['fft:999']])
def test_hydrated_record_list_must_exactly_match_hydrated_evidence(records):
    value=context(); catalog=evidence_catalog('fft',value)
    handoff=validate_draft(draft('fft',value,catalog),'fft',value,catalog)
    handoff.source_record_ids=records
    with pytest.raises(HandoffError,match='source_record_mismatch'):
        validate_handoff(handoff,catalog,value)


@pytest.mark.parametrize('text',['불평형입니다.','축정렬 불량입니다.','진폭 기준으로 외륜 결함입니다.','불평형이 확실합니다.'])
def test_physical_cause_wording_is_not_rejected(text):
    value=context(); result=draft('trend',value); result.summary=text
    assert validate_draft(result,'trend',value,evidence_catalog('trend',value)).llm_success


def test_boolean_cannot_replace_an_equal_numeric_measurement():
    value=context(); value['trend']['metrics'][0]['mean']=1.0
    catalog=evidence_catalog('trend',value); handoff=validate_draft(draft('trend',value,catalog),'trend',value,catalog)
    fact=next(item for item in handoff.evidence if item.value==1.0 and item.unit=='mm/s')
    fact.value=True
    with pytest.raises(HandoffError,match='source_evidence_mismatch'):
        validate_handoff(handoff,catalog,value)


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


@pytest.mark.parametrize('field', ['headline', 'risk_label', 'trend_heading', 'fft_heading', 'history_heading'])
def test_synthesis_persistent_failure_is_limited_after_one_repair(tmp_path, field):
    value=context(); calls=[]
    async def create(**params):
        payload=json.loads(params['messages'][1]['content'])
        name=payload.get('agent_name','synthesis'); calls.append(name)
        if name != 'synthesis': return response(draft(name,value).model_dump_json())
        from app.ai_analysis import AiFinding
        result=synthesis(payload)
        if field.endswith('_heading'):
            setattr(result.diagnosis, field.replace('_heading', '_findings'),
                    [AiFinding(heading='진폭 999 mm/s', detail='원본을 확인하세요.')])
        else:
            setattr(result.diagnosis, field, '진폭 999 mm/s')
        return response(result.model_dump_json())
    agent,_=gateway(create,tmp_path)
    result=asyncio.run(agent.analyze(value))
    assert calls.count('synthesis') == 2 and len(calls) == 5
    assert result.risk_level == 'unknown' and not result.likely_causes
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['synthesis']['status'] == 'limited'
    assert 'unsupported_measurement' in trace['synthesis']['failure_codes']
    latest=(tmp_path/'1'/'synthesis.md').read_text()
    assert trace['request_id'] in latest and result.headline in latest
    assert latest.split('\n\n',1)[1] in (tmp_path/f"{trace['request_id']}.md").read_text()


def test_success_synthesis_markdown_matches_validated_result(tmp_path):
    value=context()
    async def create(**params):
        payload=json.loads(params['messages'][1]['content'])
        return response((draft(payload['agent_name'],value) if 'agent_name' in payload else synthesis(payload)).model_dump_json())
    agent,_=gateway(create,tmp_path); result=asyncio.run(agent.analyze(value))
    trace=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['synthesis']['status'] == 'validated'
    assert trace['synthesis']['diagnosis'] == result.model_dump(mode='json',by_alias=True)
    assert result.headline in (tmp_path/'1'/'synthesis.md').read_text()


def test_prose_counts_and_scores_match_source_arithmetic():
    from app.agents.handoff import Evidence, prose_issues
    fact=Evidence(evidence_id='f:count',source='fft.weekly.count',source_record_id=None,
                  value=2.0,unit='count',measured_at=None,period=Period(start=None,end=None),
                  group_id=None,kind='aggregate',supports_causes=[])
    assert prose_issues('이상 기록 2건', [fact]) == []
    assert prose_issues('이상 기록 9건', [fact]) == ['unsupported_measurement']
    assert prose_issues('누적 점수 2점', [fact]) == ['unsupported_measurement']


def test_synthesis_keeps_previous_rounding_allowance():
    from app.agents.orchestrator import synthesis_prose_issues
    facts=list(evidence_catalog('trend',context()).values())
    assert synthesis_prose_issues('진동 1.25 mm/s',facts) == []
    assert 'unsupported_measurement' in synthesis_prose_issues('진동 9 mm/s',facts)
