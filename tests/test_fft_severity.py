import asyncio
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess

import pytest

from app.ai_analysis import AiAnalysisService, _fft_summary
from app.analysis.fft_severity import amplitude_grade, assess_fft_harmonics
from app.services.fft_status import weekly_fft_diagnosis
from tests.test_ai_analysis import diagnosis


@pytest.mark.parametrize(('unit', 'value', 'label'), [
    ('mm/s', 4, '양호'), ('mm/s', 4.000001, '초기 결함'),
    ('mm/s', 10, '초기 결함'), ('mm/s', 10.000001, '심각'),
    ('mm/s', 20, '심각'), ('mm/s', 20.000001, '정지'),
    ('g', .2, '양호'), ('g', .20000001, '초기 결함'),
    ('g', .99999999, '초기 결함'), ('g', 1, '베어링 교체'),
    ('g', 1.000001, '베어링 교체'), ('mm/s', 0, '양호'),
    ('g', None, '판정 불가'), ('g', float('nan'), '판정 불가'),
    ('g', -1, '판정 불가'), ('mm/s', True, '판정 불가'),
])
def test_exact_amplitude_boundaries(unit, value, label):
    assert amplitude_grade(value, unit)['label'] == label


def record(record_id=1, stamp='2026-04-30 12:00:00', cause='unbalance', values=(5, 1, .1)):
    return {'recordId': record_id, 'measuredAt': stamp, 'amplitudeUnit': 'mm/s',
            'metadata': {'measureMode': {'code': '3'}},
            'maxAmplitude': 999, 'analysis': {'diagnosis': {
                'status': 'analyzed', 'diagnosis': cause,
                'harmonics': [{'order': order, 'amplitude': amplitude, 'detected': True,
                              'detectedFrequency': order * 30}
                             for order, amplitude in enumerate(values, 1)],
            }}}


def bearing_record():
    result = record(values=(.20000001, .1, .05))
    result['amplitudeUnit'] = 'g'
    result['metadata']['measureMode']['code'] = '2'
    d = result['analysis']['diagnosis']
    d.update(status='no_anomaly', diagnosis='normal', faults=[
        {'type': 'FTF', 'harmonics': deepcopy(d['harmonics'])},
        {'type': 'BPFI', 'harmonics': deepcopy(d['harmonics'])},
    ])
    d['faults'][1]['harmonics'][2]['amplitude'] = 1
    return result


def test_harmonics_ignore_maximum_and_keep_raw_boundary_values():
    raw = record(values=(4.00000001, 2, 1))
    entry = assess_fft_harmonics(raw)[0]
    assert entry['grade'] == '초기 결함'
    assert entry['maxAmplitude'] == 4.00000001
    assert [h['label'] for h in entry['harmonics']] == ['초기 결함', '양호', '양호']
    assert _fft_summary(raw)['severityAssessments'] == [entry]
    entries = assess_fft_harmonics(bearing_record())
    assert [(e['cause'], e['grade']) for e in entries] == [('FTF', '초기 결함'), ('BPFI', '베어링 교체')]


def test_missing_harmonics_are_not_normal():
    raw = record()
    raw['analysis']['diagnosis']['harmonics'][0]['detected'] = False
    entry = assess_fft_harmonics(raw)[0]
    assert entry['partial'] and entry['harmonics'][0]['label'] == '판정 불가'
    raw['analysis']['diagnosis']['harmonics'] = []
    assert assess_fft_harmonics(raw)[0]['score'] is None
    raw = bearing_record()
    raw['analysis']['diagnosis'] = {'status': 'unavailable', 'message': '베어링 계수 없음'}
    assert assess_fft_harmonics(raw)[0]['reason'] == '베어링 계수 없음'


def weekly(monkeypatch, records):
    indexed = {r['recordId']: r for r in records}
    monkeypatch.setattr('app.services.fft_status.load_fft_record', lambda fft, rid: indexed[rid])
    return weekly_fft_diagnosis({'records': [{'id': r['recordId'], 'measuredAt': r['measuredAt']} for r in records]})


def test_week_window_frequency_first_and_peak_grade(monkeypatch):
    result = weekly(monkeypatch, [
        record(1, '2026-04-23 23:59:59', 'misalignment', (25, 1, 1)),
        record(2, '2026-04-24 00:00:00', 'unbalance', (5, 1, 1)),
        record(3, '2026-04-29 12:00:00', 'unbalance', (11, 1, 1)),
        record(4, '2026-04-30 12:00:00', 'misalignment', (25, 1, 1)),
    ])
    assert result['start'] == '2026-04-24 00:00:00'
    assert result['recordCount'] == 3
    assert result['label'] == 'Unbalance 심각'
    assert result['representative']['count'] == 2
    assert result['representative']['totalScore'] == 3
    assert result['representative']['peakRecordId'] == 3


def test_tied_counts_compare_grade_points_and_latest(monkeypatch):
    result = weekly(monkeypatch, [record(1, cause='unbalance'), record(2, cause='misalignment', values=(11, 1, 1))])
    assert result['representative']['cause'] == 'misalignment'
    result = weekly(monkeypatch, [record(1, '2026-04-29 12:00:00', 'misalignment'), record(2)])
    assert result['representative']['cause'] == 'unbalance'
    result = weekly(monkeypatch, [record(1, cause='unbalance'), record(2, cause='misalignment')])
    assert result['representative']['cause'] == 'misalignment'


def test_all_bearing_types_count_once_per_record(monkeypatch):
    result = weekly(monkeypatch, [bearing_record()])
    assert result['evaluatedRecordCount'] == 1
    assert {c['cause']: c['count'] for c in result['causes']} == {'FTF': 1, 'BPFI': 1}
    assert result['label'] == '베어링 내륜(BPFI) 베어링 교체'


def test_no_data_normal_and_partial_records(monkeypatch):
    assert weekly_fft_diagnosis(None)['label'] == '판정 불가'
    raw = record(values=(1, 1, 1))
    assert weekly(monkeypatch, [raw])['label'] == '양호'
    raw['analysis']['diagnosis']['harmonics'] = []
    result = weekly(monkeypatch, [raw])
    assert result['label'] == '판정 불가' and result['excludedRecordCount'] == 1
    raw = record()
    raw['analysis']['diagnosis']['harmonics'][1]['detected'] = False
    result = weekly(monkeypatch, [raw])
    assert result['partialRecordCount'] == 1 and result['limitation']


def test_server_enforces_grade_even_if_ai_does_not_mention_it():
    evidence = _fft_summary(record())
    class Gateway:
        async def analyze(self, context):
            return diagnosis().model_copy(update={'fft_reference_record_ids': [1]})
    context = {'fft': evidence, 'preparedFftEvidence': {'representativeRecords': [evidence]}}
    service = AiAnalysisService(Gateway(), 'test-model')
    async def run():
        result = await service.analyze(context)
        cached = await service.analyze(context)
        assert result.fft_severity_assessments[0]['grade'] == '초기 결함'
        assert cached.cached and cached.fft_severity_assessments == result.fft_severity_assessments
        assert '초기 결함' not in result.analysis.fft_summary
    asyncio.run(run())


def test_dataset_one_weekly_api_regression():
    from app.main import create_app
    from tests.test_app import get
    result = get(create_app(data_dir=Path('data')), '/api/dashboard/1').json()['fftWeeklyDiagnosis']
    assert result['label'] != '정상'
    assert result['representative']['highestScore'] >= 1
    assert result['representative']['count'] > 0


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js unavailable')
def test_weekly_overview_and_required_ai_grades_render():
    script = r'''
import assert from 'node:assert/strict';
const make = () => ({ children: [], className: '', textContent: '', append(...items) { this.children.push(...items); },
 replaceChildren(...items) { this.children = items; }, setAttribute() {}, removeAttribute() {} });
const ids = ['overview-fft-result', 'overview-fft-measured-at', 'overview-fft-grade', 'overview-fft-stats', 'overview-fft-limitation', 'ai-analysis-description', 'ai-analysis-run',
 'ai-analysis-details', 'trend-ai-summary', 'fft-ai-summary', 'fft-ai-period'];
const nodes = Object.fromEntries(ids.map(id => [id, make()]));
nodes['ai-analysis-run'].dataset = {};
const panel = make();
globalThis.document = { getElementById: id => nodes[id], createElement: () => make(),
 querySelector: () => panel, querySelectorAll: () => [] };
const { renderOverviewFftResult } = await import('./app/static/modules/fft/analysis.js');
const weekly = { label: 'Unbalance 초기 결함', state: 'caution', start: '2026-04-24 00:00:00', end: '2026-04-30 12:00:00',
 representative: { causeLabel: 'Unbalance', grade: '초기 결함', count: 3, totalScore: 3, maxAmplitude: 5, unit: 'mm/s' } };
renderOverviewFftResult({ analysis: { diagnosis: { diagnosis: 'normal' } } }, weekly);
assert.equal(nodes['overview-fft-result'].textContent, 'Unbalance');
assert.equal(nodes['overview-fft-grade'].textContent, '초기 결함');
assert.match(JSON.stringify(nodes['overview-fft-stats']), /3건.*3점/);
renderOverviewFftResult({ recordId: 999 }, weekly);
assert.equal(nodes['overview-fft-result'].textContent, 'Unbalance');
assert.equal(nodes['overview-fft-grade'].textContent, '초기 결함');
const { renderAiAnalysis } = await import('./app/static/modules/analysis/ai.js');
renderAiAnalysis({ analysis: { headline: '점검하세요', fftReferenceRecordIds: [1] }, fftSeverityAssessments: [{
 recordId: 1, measuredAt: '2026-04-30', causeLabel: 'Unbalance', grade: '초기 결함', unit: 'mm/s',
 harmonics: [{ order: 1, amplitude: 5, score: 1, label: '초기 결함' }, { order: 2, score: null, label: '판정 불가' }],
}] });
const content = JSON.stringify(nodes['ai-analysis-details']);
assert.match(content, /FFT 기준 판정/);
assert.match(content, /1X 5.0000 mm\/s: 초기 결함/);
assert.match(content, /2X: 판정 불가/);
assert.match(content, /베어링 교체/);
'''
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=Path(__file__).resolve().parents[1], check=True)


def test_unknown_frequency_scale_does_not_produce_a_grade():
    raw = record()
    raw['frequencyUnit'] = 'bin'
    assert assess_fft_harmonics(raw)[0]['grade'] == '판정 불가'


def test_server_preserves_prepared_reference_grades_and_caches_without_extra_queries():
    evidence = _fft_summary(record(2, values=(25, 1, 1)))
    calls = []
    class Gateway:
        async def analyze(self, context):
            return diagnosis().model_copy(update={'fft_reference_record_ids': [2]})
    async def execute(name, arguments):
        calls.append((name, arguments))
        return {'fft': evidence}
    context = {'equipmentAnalysis': True, 'preparedFftEvidence': {'representativeRecords': [evidence]}}
    service = AiAnalysisService(Gateway(), 'test-model')
    async def run():
        response = await service.analyze(context, execute=execute)
        assert response.fft_severity_assessments[0]['grade'] == '정지'
        assert response.model_dump(by_alias=True)['fftSeverityAssessments'][0]['recordId'] == 2
        cached = await service.analyze(context, execute=execute)
        assert cached.cached and calls == []
        assert cached.fft_severity_assessments == response.fft_severity_assessments
    asyncio.run(run())


def test_weekly_peak_evidence_and_integrated_explanation(monkeypatch):
    from app.services.fft_status import weekly_explanation_facts
    value = weekly(monkeypatch, [record(1, '2026-04-29 12:00:00', values=(5, 1, 1)),
                                record(2, values=(1, 11, 1)),
                                record(3, cause='misalignment', values=(5, 1, 1))])
    peak = value['representative']['peakEvidence']
    assert peak['recordId'] == 2 and peak['harmonicOrder'] == 2
    assert peak['frequency'] == 60 and peak['amplitude'] == 11
    summary = ' '.join(weekly_explanation_facts(value))
    assert '2X의 11.0000 mm/s' in summary
    assert 'Unbalance 2건' in summary and '3점' in summary
    assert '속도' in summary and '최고 등급' in summary


def test_weekly_explanation_missing_data_and_partial(monkeypatch):
    from app.services.fft_status import weekly_explanation_facts
    for value in (weekly_fft_diagnosis(None), weekly(monkeypatch, [record(values=(1, 1, 1))])):
        summary = ' '.join(weekly_explanation_facts(value))
        assert value['label'] in summary
    raw = record()
    raw['analysis']['diagnosis']['harmonics'][2]['detected'] = False
    value = weekly(monkeypatch, [raw])
    assert '제한' in ' '.join(weekly_explanation_facts(value))
