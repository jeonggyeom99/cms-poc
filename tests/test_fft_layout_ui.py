"""Exercise FFT rendering across measurement modes and fault selections."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_fft_layout_modes_fault_selection_and_missing_bearing():
    script = r"""
import assert from 'node:assert/strict';
const nodes = {
  'fft-analysis-details': { className: '', innerHTML: '' },
  'fft-analysis-chart': { className: '', textContent: '' },
};
globalThis.document = { getElementById: id => nodes[id] };
const plots = [];
let purges = 0;
globalThis.window = { Plotly: {
  react(plot, traces, layout) { plots.push({ traces, layout }); plot.data = traces; },
  purge(plot) { purges++; delete plot.data; },
} };
const { renderFftAnalysis } = await import('./app/static/modules/fft/analysis.js');
const harmonic = (order, amplitude, frequency) => ({
  order, amplitude, targetFrequency: frequency, detectedFrequency: frequency,
  detected: true, significant: amplitude >= 0.5,
});
const harmonics = [harmonic(1, 1, 30), harmonic(2, 0.2, 60), harmonic(3, 0.1, 90)];
const fft = {
  frequencyUnit: 'Hz', amplitudeUnit: 'mm/s', frequencies: [0, 30, 60, 90, 200],
  amplitudes: [0, 1, 0.2, 0.1, 0], metadata: { measureMode: { code: '3', label: '속도' } },
  analysis: { diagnosis: {
    status: 'analyzed', diagnosis: 'unbalance', label: '불균형',
    rpm: 1800, shaftFrequency: 30, harmonics,
  } },
};
const html = () => nodes['fft-analysis-details'].innerHTML;
function checkOrder() {
  assert.ok(html().indexOf('fft-analysis-grid') < html().indexOf('fft-analysis-chart-section'));
  assert.ok(html().indexOf('fft-analysis-chart-section') < html().indexOf('fft-diagnosis-card'));
}
renderFftAnalysis(fft);
checkOrder();
assert.match(html(), /1\.0000 mm\/s/);
assert.doesNotMatch(html(), /data-bearing-fault/);
assert.equal(plots.at(-1).layout.annotations[0].text, '1X');

fft.analysis.diagnosis.status = 'insufficient_1x';
fft.analysis.diagnosis.label = '판정 불가';
fft.analysis.diagnosis.message = '1X 피크가 기준 미만입니다.';
renderFftAnalysis(fft);
checkOrder();
assert.match(html(), /판정 불가/);
assert.match(html(), /1X 피크가 기준 미만/);

const fault = (type, amplitude, frequency) => ({
  type, coefficient: frequency / 30, baseFrequency: frequency, score: amplitude,
  hasAnomaly: amplitude >= 0.5, label: amplitude >= 0.5 ? '결함 의심' : '결함 Peak 없음',
  harmonics: [1, 2, 3].map(order => harmonic(order, amplitude, frequency * order)),
});
const bearing = {
  status: 'analyzed', rpm: 1800, shaftFrequency: 30,
  bearing: { available: true, maker: 'SKF', number: '6315' },
  message: '베어링 분석 근거', defaultFaultType: 'BPFI',
  faults: [fault('BPFO', 0.1, 40), fault('BPFI', 0.8, 50)],
};
fft.amplitudeUnit = 'g';
fft.analysis.diagnosis = bearing;
for (const code of ['0', '2']) {
  fft.metadata.measureMode = { code, label: '가속도' };
  renderFftAnalysis(fft);
  checkOrder();
  assert.ok(html().indexOf('bearing-analysis-summary') > html().indexOf('fft-analysis-chart-section'));
  assert.match(html(), /BPFI 1X 피크/);
  assert.match(html(), /0\.8000 g/);
  assert.match(html(), /data-bearing-fault="BPFI" class="active" aria-pressed="true"/);
  assert.match(html(), /계수 1\.6667/);
  assert.equal(plots.at(-1).layout.annotations[0].text, 'BPFI 1X');
  renderFftAnalysis(fft, 'BPFO');
  assert.match(html(), /BPFO 1X 피크/);
  assert.match(html(), /0\.1000 g/);
  assert.match(html(), /fft-diagnosis-card normal/);
  assert.match(html(), /data-bearing-fault="BPFO" class="active" aria-pressed="true"/);
  assert.equal(plots.at(-1).layout.annotations[0].text, 'BPFO 1X');
  renderFftAnalysis(fft, 'invalid');
  assert.match(html(), /BPFI 1X 피크/);
}

fft.analysis.diagnosis = {
  status: 'unavailable', label: '가속도 베어링 분석 불가',
  message: '베어링 제조사 또는 형번이 설정되지 않았습니다.',
  rpm: 1800, shaftFrequency: null, bearing: {}, faults: [], harmonics: [],
};
renderFftAnalysis(fft);
checkOrder();
assert.match(html(), /베어링 제조사 또는 형번/);
assert.doesNotMatch(html(), /data-bearing-fault/);
assert.equal(plots.at(-1).traces.length, 1);
assert.deepEqual(plots.at(-1).traces[0].y, fft.amplitudes);

fft.frequencyUnit = 'bin';
const plotCount = plots.length;
renderFftAnalysis(fft);
assert.equal(nodes['fft-analysis-details'].className, 'analysis-placeholder');
assert.equal(plots.length, plotCount);
renderFftAnalysis(null);
assert.match(html(), /스펙트럼 데이터가 없습니다/);
assert.ok(purges > 0);
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-"],
        input=script, text=True, capture_output=True, cwd=ROOT, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_related_history_card_shows_empty_state_and_matching_records():
    script = r"""
import assert from 'node:assert/strict';
function node() {
  return {
    hidden: true, textContent: '', children: [], attributes: {}, dataset: {},
    replaceChildren(...children) { this.children = children; },
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...children) { this.children.push(...children); },
    classList: { toggle() {} },
  };
}
const nodes = {
  'fft-related-history': node(),
  'fft-related-history-count': node(),
  'fft-related-history-list': node(),
};
globalThis.document = { createElement: node, getElementById: id => nodes[id] };
const { renderRelatedHistory } = await import('./app/static/modules/fft/related-history.js');
renderRelatedHistory(null, []);
assert.equal(nodes['fft-related-history'].hidden, false);
assert.equal(nodes['fft-related-history-count'].textContent, '0건');
assert.equal(nodes['fft-related-history-list'].children[0].textContent, '일치하는 과거 이력이 없습니다.');
renderRelatedHistory({ fault: '축', faultType: 'Unbalance' }, [{
  id: 'history-1', date: '2026-09-01', equipmentName: '펌프', process: '수처리',
  sensorNumber: '001', fault: '축', faultType: 'Unbalance', datasetId: '1',
}]);
assert.equal(nodes['fft-related-history'].hidden, false);
assert.equal(nodes['fft-related-history-count'].textContent, '1건');
assert.equal(nodes['fft-related-history-list'].children.length, 1);
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-"],
        input=script, text=True, capture_output=True, cwd=ROOT, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
