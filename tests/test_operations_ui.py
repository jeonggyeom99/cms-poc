"""Regressions for operating-page presentation and central-control filtering."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "path, styled",
    [("/", True), ("/equipment-status2", True), ("/dashboard_ui6", True),
     ("/history2", True), ("/main_ct", True), ("/dashboard2", True),
     ("/dashboard", False), ("/history", False), ("/dashboard_ui2", False)],
)
def test_shared_presentation_is_limited_to_operating_pages(path, styled):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://test",
        ) as client:
            response = await client.get(path)
            assert response.status_code == 200
            assert ("data-cms-operations" in response.text) is styled
            assert ('href="/static/cms-operations.css' in response.text) is styled
            assert ('src="/static/modules/core/cms-operations.js' in response.text) is styled
            if path == "/main_ct":
                assert 'id="process-select"' in response.text
                assert 'id="trend-bars"' in response.text

    asyncio.run(check())


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_workspace_missing_clock_filter_reset_empty_and_error_states():
    script = r"""
import assert from 'node:assert/strict';
const items = [
  {id:'1',plant:'A',line:'A1',status:'normal',name:'normal',statusLabel:'정상'},
  {id:'2',plant:'A',line:'A2',status:'caution',name:'<주의>',statusLabel:'주의'},
  {id:'3',plant:'B',line:'B1',status:'critical',name:'critical',statusLabel:'심각'},
  {id:'4',plant:'B',line:'B1',status:'unknown',name:'unknown',statusLabel:'미지정'},
];
const history = [
  {datasetId:'1',date:'2026-04-01',equipmentName:'old'},
  {datasetId:'2',date:'2026-04-02',equipmentName:'attention'},
  {datasetId:'3',date:'2026-04-03',equipmentName:'critical'},
  {datasetId:null,date:'2026-04-04',equipmentName:'latest'},
];
class Node {
  constructor() { this.textContent=''; this.innerHTML=''; this.value='all'; this.listeners={}; }
  replaceChildren(...options) { this.options=options; this.value=options[0].value; }
  addEventListener(event, listener) { (this.listeners[event] ||= []).push(listener); }
  change(value) { this.value=value; for(const listener of this.listeners.change || []) listener(); }
}
globalThis.Option = class { constructor(label,value) { this.label=label; this.value=value; } };
async function setup(path, fail=false, data=items, records=history) {
  const ids=['total','ring-critical','ring-attention','ring-normal','risk-rate','history-count',
    'risk-map','signals','work-count','work-rows','recent-activity','trend-bars',
    'workspace-title','role-label','hero-title','hero-description','chart-title',
    'scope-select','process-select'];
  if(path==='/main_sv') ids.push('sidebar-time');
  const nodes=Object.fromEntries(ids.map(id=>['#'+id,new Node()]));
  globalThis.document={querySelector:selector=>nodes[selector] || null};
  globalThis.location={pathname:path};
  let ready;
  globalThis.window={addEventListener:(_,callback)=>{ready=callback;}};
  const errors=[];
  console.error=(...args)=>errors.push(args);
  let requests=0;
  globalThis.fetch=async url=>{
    requests++;
    if(fail) throw new Error('offline');
    return {ok:true,json:async()=>({items:url==='/api/datasets'?data:records})};
  };
  await import('./app/static/modules/main/workspace.js?case='+Math.random());
  await ready();
  return {nodes,errors,requests};
}
const {nodes:n,errors,requests}=await setup('/main_ct');
assert.equal(requests,2); // A single initialization, with no duplicate fetch/listener flow.
assert.equal(errors.length,0); // The CMS page intentionally has no #sidebar-time.
assert.equal(n['#total'].textContent,4);
assert.match(n['#risk-map'].innerHTML,/B/);
assert.doesNotMatch(n['#risk-map'].innerHTML,/NaN/);
assert.match(n['#signals'].innerHTML,/&lt;주의&gt;/);
assert.equal(n['#work-count'].textContent,'2건');
assert.match(n['#work-rows'].innerHTML,/dashboard2\?dataset=3/);
assert.ok(n['#work-rows'].innerHTML.indexOf('critical') < n['#work-rows'].innerHTML.indexOf('&lt;주의&gt;'));
assert.ok(n['#recent-activity'].innerHTML.indexOf('latest') < n['#recent-activity'].innerHTML.indexOf('old'));

n['#scope-select'].change('A');
assert.equal(n['#scope-select'].value,'A');
assert.equal(n['#total'].textContent,2);
assert.equal(n['#history-count'].textContent,2);
assert.deepEqual(n['#process-select'].options.map(o=>o.value),['all','A1','A2']);
n['#process-select'].change('A2');
assert.equal(n['#total'].textContent,1);
assert.equal(n['#history-count'].textContent,1);
assert.match(n['#signals'].innerHTML,/&lt;주의&gt;/);
n['#scope-select'].change('B');
assert.equal(n['#process-select'].value,'all'); // Reset a process unavailable in the new plant.
assert.equal(n['#total'].textContent,2);
n['#scope-select'].change('all');
assert.equal(n['#total'].textContent,4); // Restore from the original data, not the last filtered subset.
assert.deepEqual(n['#scope-select'].options.map(o=>o.value),['all','A','B']);
n['#process-select'].change('A1');
assert.match(n['#signals'].innerHTML,/현재 이상 신호가 없습니다/);
assert.match(n['#work-rows'].innerHTML,/점검 대상이 없습니다/);

const noData=await setup('/main_ct',false,[],[]);
assert.equal(noData.nodes['#risk-rate'].textContent,'0%');
assert.match(noData.nodes['#risk-map'].innerHTML,/설비가 없습니다/);
assert.match(noData.nodes['#trend-bars'].innerHTML,/진단 이력이 없습니다/);
const failure=await setup('/main_ct',true);
assert.equal(failure.errors.length,1);
for(const id of ['risk-map','signals','work-rows','recent-activity','trend-bars'])
  assert.match(failure.nodes['#'+id].innerHTML,/데이터를 불러오지 못했습니다/);
const legacy=await setup('/main_sv');
assert.equal(legacy.errors.length,0);
assert.ok(legacy.nodes['#sidebar-time'].textContent);
assert.match(legacy.nodes['#work-rows'].innerHTML,/href="\/dashboard\?dataset=3"/);
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-"],
        input=script, text=True, capture_output=True, cwd=ROOT, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
