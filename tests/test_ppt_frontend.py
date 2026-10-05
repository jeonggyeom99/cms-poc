"""Exercise the download controller with DOM/Plotly doubles, without a browser."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_download_metadata_and_warning_controller():
    script = r"""
import assert from 'node:assert/strict';
const api = await import('./app/static/modules/api/ppt-report.js');
let header;
globalThis.fetch = async () => new Response(new Blob(['pptx']), {
  headers: header ? { 'X-PPT-Validation': header } : {},
});
for (const state of ['passed', 'warning', 'unverified']) {
  header = encodeURIComponent(JSON.stringify({ status: state, repairs: 1, issues: ['설명 잘림'] }));
  const result = await api.fetchDiagnosticPpt('1', {});
  assert.equal(result.validation.status, state);
  assert.equal(await result.blob.text(), 'pptx');
}
for (const invalid of [undefined, '%invalid', '{}',
    encodeURIComponent(JSON.stringify({ status:'passed', repairs:99, issues:[] }))]) {
  header = invalid;
  const result = await api.fetchDiagnosticPpt('1', {});
  assert.equal(result.validation.status, 'unverified');
  assert.equal(result.blob.size, 4);
}
globalThis.fetch = async () => new Response('', { status: 200 });
await assert.rejects(api.fetchDiagnosticPpt('1', {}), /비어/);

const status = { dataset: {}, textContent: '' };
let listener;
const button = { addEventListener: (event, callback) => { listener = callback; }, setAttribute() {} };
const chart = { classList: { contains: () => false }, data: [{ x: [1,2], y: [3,4] }],
  layout: { font: { size: 11 }, legend: { yanchor: 'top', y: -0.18 }, xaxis: { title: { text: '측정일', font: { size: 10 } } },
    yaxis: { tickfont: { size: 10 } }, yaxis2: { side: 'right', tickfont: { size: 10 } } } };
const originalLayout = JSON.stringify(chart.layout);
const graphs = [];
let downloads = 0;
globalThis.document = {
  getElementById(id) { return id === 'report-action-status' ? status : id === 'diagnostic-ppt-export' ? button : chart; },
  createElement(tag) { return { style:{}, remove() {}, click() { if (tag === 'a') downloads++; } }; },
  body: { append() {} },
};
globalThis.window = { Plotly: {
  async newPlot(target, traces, layout) { graphs.push({ traces, layout }); },
  async toImage(target, options) { assert.equal(options.width,1120); assert.equal(options.height,480); return 'data:image/png;base64,eA=='; },
  purge() {},
} };
const controller = await import('./app/static/modules/report/ppt-export.js');
controller.bindPptExport(() => ({ datasetId:'1', recordId:2 }));
controller.setPptExportAvailable(true);
for (const state of ['passed','warning','unverified']) {
  globalThis.fetch = async () => new Response(new Blob(['pptx']), {
    headers: { 'X-PPT-Validation':encodeURIComponent(JSON.stringify({status:state,repairs:0,issues:['설명 잘림']})) },
  });
  const expectedDownloads = downloads + 1;
  listener();
  for (let count=0; count<100 && (downloads < expectedDownloads || button.disabled); count++) await new Promise(resolve=>setTimeout(resolve,1));
  assert.equal(status.dataset.state, state === 'passed' ? 'success' : 'warning');
  assert.match(status.textContent, state === 'passed' ? /통과/ : /설명 잘림/);
}
assert.equal(downloads,3);
assert.equal(JSON.stringify(chart.layout), originalLayout);
assert.equal(graphs.length,6);
assert.equal(graphs[0].layout.xaxis.title.font.size,28);
assert.equal(graphs[0].layout.yaxis2.tickfont.size,26);
assert.equal(graphs[0].layout.legend.yanchor,'bottom');
"""
    result = subprocess.run([shutil.which("node"), "--input-type=module", "-"], input=script,
                            text=True, capture_output=True, cwd=ROOT, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
