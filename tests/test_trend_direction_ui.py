"""Check server trend verdicts and state transitions in the card renderer."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_trend_direction_verdicts_and_reset_states():
    script = r"""
import assert from 'node:assert/strict';
const nodes = Object.fromEntries([
  'trend-direction-details', 'trend-direction-status', 'trend-direction-description',
].map(id => [id, { textContent: '', className: '', attributes: {},
  setAttribute(name, value) { this.attributes[name] = value; } }]));
globalThis.document = { getElementById: id => nodes[id] };
const { renderTrendDirection } = await import('./app/static/modules/analysis/trend-direction.js');
const details = nodes['trend-direction-details'];
const label = nodes['trend-direction-status'];
const description = nodes['trend-direction-description'];
const render = analysis => renderTrendDirection({ trend: { analysis } });

// Display the server verdict rather than inferring it again from slope or isRising.
render({ status: 'rising', isRising: false, slope: 0 });
assert.equal(label.textContent, '상승 경향');
assert.match(details.className, /is-caution/);
assert.equal(details.attributes['aria-busy'], 'false');
render({ status: 'stable', isRising: true, slope: 1 });
assert.equal(label.textContent, '안정');
assert.match(description.textContent, /감지되지 않았/);
assert.match(details.className, /is-normal/);

render({ status: 'insufficient_data', usedPoints: 142, requiredPoints: 143 });
assert.equal(label.textContent, '판단 불가');
assert.match(description.textContent, /현재 142개 \/ 필요 143개/);
assert.match(details.className, /is-neutral/);
for (const data of [null, {}, { trend: null }, { trend: { analysis: null } }]) {
  renderTrendDirection(data);
  assert.equal(label.textContent, '판단 불가');
  assert.match(description.textContent, /데이터가 없습니다/);
}

render({ status: 'rising' });
renderTrendDirection(null, 'loading');
assert.equal(label.textContent, '확인 중');
assert.match(details.className, /is-neutral/);
assert.equal(details.attributes['aria-busy'], 'true');
renderTrendDirection(null, 'error');
assert.equal(label.textContent, '판단 불가');
assert.match(description.textContent, /불러오지 못했/);
assert.equal(details.attributes['aria-busy'], 'false');
render({ status: 'stable' });
assert.equal(label.textContent, '안정');
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-"],
        input=script, text=True, capture_output=True, cwd=ROOT, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
