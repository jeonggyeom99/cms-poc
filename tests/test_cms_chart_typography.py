import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_node(script):
    node = shutil.which("node")
    assert node, "Node.js is required for chart typography verification"
    result = subprocess.run(
        [node, "--input-type=module", "-"], input=script, text=True,
        capture_output=True, cwd=ROOT, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_chart_layout_uses_common_typography():
    run_node(r"""
import assert from 'node:assert/strict';
const { baseLayout } = await import('./app/static/modules/core/plot.js');
const layout = baseLayout();
assert.equal(layout.font.size, 12);
assert.match(layout.font.family, /Pretendard.*Malgun Gothic/);
for (const font of [layout.xaxis.tickfont, layout.yaxis.tickfont,
  layout.legend.font, layout.hoverlabel.font]) {
  assert.equal(font.size, 12);
  assert.equal(font.family, layout.font.family);
}
""")


def test_chart_typography_reads_computed_tokens_and_falls_back():
    run_node(r"""
import assert from 'node:assert/strict';
const plot = await import('./app/static/modules/core/plot.js');
assert.equal(typeof plot.readChartTypography, 'function');
const fallback = plot.readChartTypography();
assert.equal(fallback.size, 12);
assert.match(fallback.family, /Pretendard.*Malgun Gothic/);
globalThis.document = { documentElement: { role: 'root' } };
globalThis.getComputedStyle = root => {
  assert.equal(root.role, 'root');
  return { getPropertyValue: name => ({
    '--cms-font-family': ' "Test Korean", sans-serif ', '--cms-type-chart': ' 15px ',
  })[name] ?? '' };
};
assert.deepEqual(plot.readChartTypography(), { family: '"Test Korean", sans-serif', size: 15 });
assert.equal(plot.baseLayout().font.size, 15);
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
assert.deepEqual(plot.readChartTypography(), fallback);
globalThis.getComputedStyle = () => ({ getPropertyValue: () => 'invalid' });
assert.equal(plot.readChartTypography().size, 12);
assert.deepEqual(plot.readChartTypography(null), fallback);
""")


@pytest.mark.parametrize("computed", [False, True], ids=["node-fallback", "computed-tokens"])
def test_local_chart_fonts_follow_core_typography(computed):
    run_node((r"""
globalThis.document = { documentElement: {} };
globalThis.getComputedStyle = () => ({ getPropertyValue: name => ({
  '--cms-font-family': '"Test Korean", sans-serif', '--cms-type-chart': '15px',
})[name] ?? '' });
""" if computed else "") + r"""
import assert from 'node:assert/strict';
const { baseLayout } = await import('./app/static/modules/core/plot.js');
const { buildFftFigure, buildFftDiagnosisFigure } = await import('./app/static/modules/fft/chart.js');
const { buildTrendFigure, buildExpandedTrendFigure } = await import('./app/static/modules/trend/chart.js');
const { buildTimeWaveFigure } = await import('./app/static/modules/timewave/chart.js');
const harmonic = { targetFrequency: 10, detectedFrequency: 10, order: 1, detected: true, amplitude: 2 };
const fft = { frequencies: [0, 10, 20], amplitudes: [0, 2, 1], frequencyUnit: 'Hz',
  amplitudeUnit: 'g', timeWaveSamples: [0, 1, -1], sampling: { valid: true, frequencyHz: 100 },
  analysis: { diagnosis: { harmonics: [harmonic] } } };
const bearing = { ...fft, analysis: { diagnosis: { defaultFaultType: 'BPFI',
  faults: [{ type: 'BPFI', harmonics: [harmonic] }] } } };
const data = { current: { warningThreshold: 6, dangerThreshold: 12 }, trend: {
  points: [{ timestamp: '2026-10-28 00:00:00', value: 3, acceleration: 1 }],
  metrics: [
    { key: 'velocity', pointKey: 'value', label: 'Velocity', unit: 'mm/s', available: true },
    { key: 'acceleration', pointKey: 'acceleration', label: 'Acceleration', unit: 'g', available: true },
  ],
} };
const expected = baseLayout().font;
function checkFonts(value) {
  for (const [key, child] of Object.entries(value ?? {})) {
    if (/font$/.test(key)) {
      assert.equal(child.size, expected.size, JSON.stringify(value));
      assert.equal(child.family, expected.family);
    } else if (child && typeof child === 'object') checkFonts(child);
  }
}
const figures = [buildFftFigure(fft), buildFftFigure(bearing, 'BPFI'),
  buildFftDiagnosisFigure(bearing), buildTrendFigure('all', data),
  buildExpandedTrendFigure('all', data, new Set(['velocity', 'acceleration'])),
  buildTimeWaveFigure(fft), buildTimeWaveFigure({ ...fft, sampling: null })];
assert.equal(figures[4].layout.yaxis2.title.font.size, expected.size);
assert.ok(figures[0].layout.annotations.length);
assert.ok(figures[1].traces[1].textfont);
for (const figure of figures) checkFonts(figure);
const charts = Object.fromEntries([
  ['trend-chart', figures[3]], ['fft-analysis-chart', figures[1]],
].map(([id, figure]) => [id, { classList: { contains: () => false },
  data: figure.traces, layout: figure.layout }]));
const captures = [];
const targets = [];
globalThis.document = {
  documentElement: {}, getElementById: id => charts[id],
  createElement: () => ({ style: {}, remove() { this.removed = true; } }),
  body: { append: target => targets.push(target) },
};
globalThis.window = { Plotly: {
  newPlot: async (target, traces, layout, config) => {
    assert.equal(config.staticPlot, true);
    captures.push({ traces, layout });
  },
  toImage: async (target, options) => {
    assert.equal(options.width, 1120);
    assert.equal(options.height, 480);
    return 'data:image/png;base64,local-fixture';
  },
  purge: target => { target.purged = true; },
} };
const { captureDashboardCharts } = await import('./app/static/modules/report/chart-capture.js');
await captureDashboardCharts({ fft: bearing, selectedFaultType: 'BPFI', presentation: true });
await captureDashboardCharts({ presentation: true });
assert.equal(captures.length, 4);
for (const { traces, layout } of captures) {
  assert.equal(layout.font.size, 28);
  assert.equal(layout.legend.font.size, 26);
  for (const [key, axis] of Object.entries(layout)) {
    if (!/^[xy]axis\d*$/.test(key)) continue;
    assert.equal(axis.tickfont.size, 26);
    assert.equal(axis.title.font.size, 28);
  }
  for (const annotation of layout.annotations) assert.equal(annotation.font.size, 26);
  for (const trace of traces) assert.equal(trace.textfont.size, 26);
}
assert.ok(targets.every(target => target.removed && target.purged));
""")