"""Internal model enum labels should not leak into Korean dashboard prose."""
import shutil
import subprocess
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
DOM_FIXTURE = r"""
import assert from 'node:assert/strict';
class Node {
  constructor(tagName='div') {
    this.tagName=tagName; this.children=[]; this.attributes={}; this.dataset={}; this.listeners={};
    this.classList={toggle:()=>{}}; this._text='';
  }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(node=>node.textContent).join(''); }
  get childElementCount() { return this.children.length; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text=''; this.children=[...nodes]; }
  setAttribute(key,value) { this.attributes[key]=value; }
  getAttribute(key) { return this.attributes[key]; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(name,handler) { this.listeners[name]=handler; }
  focus() {}
}
const ids=new Map();
globalThis.document={
  createElement: tag=>new Node(tag),
  getElementById: id=>{if(!ids.has(id)) ids.set(id,new Node()); return ids.get(id);},
  querySelector: ()=>null,
};
const byId=id=>document.getElementById(id);
const descendants=node=>[node,...node.children.flatMap(descendants)];
const finding={heading:'실제 조회 사례',detail:'8.88 mm/s에서 BPFI 확인\n\n<img src=x onerror=alert(1)> 점검'};
const payload={analysis:{headline:finding.detail,trendSummary:finding.detail,fftSummary:finding.detail,
  historyFindings:[finding],trendFindings:[finding],fftFindings:[]}};
const historyItem={id:'h1',date:'2026-01-01',equipmentName:'과거 설비',process:'공정',sensorNumber:'1',
  fault:'축',faultType:'Unbalance',issue:'현상',analysis:'분석',result:'결과',feedback:'조치'};
"""


def run_node(script):
    result = subprocess.run(
        ['node', '--experimental-vm-modules', '--input-type=module', '-e', DOM_FIXTURE + script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is unavailable')
def test_analysis_paragraphs_are_rendered_as_text():
    run_node(r"""
import { readFileSync } from 'node:fs';
const {renderAiAnalysis}=await import('./app/static/modules/analysis/ai.js');
renderAiAnalysis(payload);
for(const id of ['ai-analysis-description','trend-ai-summary','fft-ai-summary']) {
  assert.equal(byId(id).textContent,finding.detail);
}
const list=byId('fft-related-history-list');
assert.ok(list.textContent.includes(finding.detail),'History AI must receive the real findings');
assert.ok(list.textContent.includes('설비 전체 분석 기준'));
assert.ok(descendants(byId('ai-analysis-details')).some(node=>node.tagName==='p'&&node.textContent===finding.detail));
for(const root of [list,byId('ai-analysis-details')]) {
  assert.equal(descendants(root).filter(node=>node.tagName==='img').length,0);
}
const css=readFileSync('./app/static/styles.css','utf8');
for(const selector of ['#ai-analysis-description','#trend-ai-summary','#fft-ai-summary','.ai-analysis-finding p','.related-history-ai-detail']) {
  assert.ok([...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].some(([,selectors,body])=>
    selectors.split(',').map(s=>s.trim()).includes(selector)&&/white-space:\s*pre-line/.test(body)),selector);
}
""")


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is unavailable')
def test_history_ai_survives_related_history_rerender():
    run_node(r"""
const history=await import('./app/static/modules/fft/related-history.js?v=ai-paragraphs-v1');
const {renderAiAnalysis}=await import('./app/static/modules/analysis/ai.js');
history.bindRelatedHistory();
renderAiAnalysis(payload);
for(const items of [[historyItem],[],[{...historyItem,demoRelated:true}]]) {
  history.renderRelatedHistory({fault:'축',faultType:'Unbalance'},items);
  const list=byId('fft-related-history-list');
  assert.ok(list.textContent.includes(finding.detail),'async history response must retain equipment AI');
  assert.equal(descendants(list).filter(node=>node.getAttribute('aria-label')==='AI 연관과거 이력 분석').length,1);
  assert.ok(!list.textContent.includes('Fume Exhaust Fan'));
}
const button={dataset:{relatedHistoryId:'h1'}};
byId('fft-related-history').listeners.click({target:{closest:selector=>selector==='[data-related-history-id]'?button:null}});
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
assert.ok(byId('fft-related-history-list').textContent.includes('현상'));
history.resetRelatedHistoryAi();
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail));
assert.ok(byId('fft-related-history-list').textContent.includes('Fume Exhaust Fan'),'demo-only explanation must survive');
history.renderRelatedHistoryAi([finding]);
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
history.renderRelatedHistoryAi([]);
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail));
""")


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is unavailable')
def test_history_ai_resets_on_scope_change():
    run_node(r"""
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const ai=await import('./app/static/modules/analysis/ai.js');
const history=await import('./app/static/modules/fft/related-history.js?v=ai-paragraphs-v1');
const state=await import('./app/static/modules/core/state.js');
let runAnalysis,selectFft;
let fetchRecord=async(dataset,recordId)=>({recordId,frequencies:[2],amplitudes:[2]});
const pending=[];
const dashboard={meta:{datasetId:'1'},fft:{recordId:1,frequencies:[1],amplitudes:[1],records:[{id:1},{id:2}]} };
let fetchDashboardFor=async dataset=>({...dashboard,meta:{datasetId:dataset}});
const overrides={...ai,...history,...state,
  fetchDashboard:(...args)=>fetchDashboardFor(...args),
  fetchDatasetSummaries:async()=>[],
  fetchFftRecord:(...args)=>fetchRecord(...args),
  fetchRelatedHistory:async()=>({faultTag:null,items:[]}),
  fetchAiAnalysis:()=>new Promise((resolve,reject)=>pending.push({resolve,reject})),
  bindAiAnalysis:callback=>{runAnalysis=callback;},
  bindGraphModal:callbacks=>{selectFft=callbacks.onFftRecordSelect;},
};
globalThis.window={location:{search:'',href:'http://localhost/dashboard2?dataset=1'}};
const source=readFileSync('./app/static/modules/dashboard/controller.js','utf8');
const controller=new vm.SourceTextModule(source);
await controller.link(async(specifier)=>{
  const match=[...source.matchAll(/import\s*\{([^}]+)\}\s*from\s*["']([^"']+)["']/g)].find(m=>m[2]===specifier);
  const names=match[1].split(',').map(s=>s.trim()).filter(Boolean);
  return new vm.SyntheticModule(names,function(){for(const name of names)this.setExport(name,overrides[name]??(()=>{}));});
});
await controller.evaluate();
controller.namespace.initializeDashboardApplication();
const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
await flush();
await controller.namespace.loadDashboard('1');
await flush();
pending.shift().resolve(payload); await flush();
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
await selectFft(2); await flush();
assert.equal(pending.length,0,'FFT-only selection must not rerun equipment AI');
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
runAnalysis(true); await flush();
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail),'new analysis resets history AI');
const old=pending.shift();
window.location.search='?until=2026-02-01';
await controller.namespace.loadDashboard('2'); await flush();
old.resolve(payload); await flush();
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail),'stale previous scope response ignored');
pending.shift().resolve({...payload,analysis:{...payload.analysis,historyFindings:[{heading:'현재',detail:'새 설비 결과'}]}}); await flush();
assert.ok(byId('fft-related-history-list').textContent.includes('새 설비 결과'));
runAnalysis(true); await flush();
pending.shift().reject(new Error('mock API unavailable')); await flush();
assert.ok(!byId('fft-related-history-list').textContent.includes('새 설비 결과'));
await controller.namespace.loadDashboard('1'); await flush();
const representativePending=pending.shift();
let finishRepresentative;
fetchRecord=()=>new Promise(resolve=>{finishRepresentative=resolve;});
representativePending.resolve({...payload,analysis:{...payload.analysis,fftReferenceRecordIds:[99]}}); await flush();
assert.equal(typeof finishRepresentative,'function');
runAnalysis(true); await flush();
finishRepresentative({recordId:99}); await flush();
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail),'stale representative response ignored');
pending.shift().resolve(payload); await flush();
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
// Changing only the date scope clears the old AI before the dashboard fetch finishes.
let finishDashboard;
fetchDashboardFor=()=>new Promise(resolve=>{finishDashboard=resolve;});
window.location.search='?until=2026-03-01';
const loading=controller.namespace.loadDashboard('1');
assert.ok(!byId('fft-related-history-list').textContent.includes(finding.detail));
finishDashboard(dashboard); await loading; await flush();
pending.shift().resolve(payload); await flush();
assert.ok(byId('fft-related-history-list').textContent.includes(finding.detail));
""")


@pytest.mark.skipif(shutil.which('node') is None,reason='Node.js is unavailable')
def test_ai_status_translation_preserves_numeric_evidence_and_physics():
    subprocess.run(['node','--input-type=module','-e',r"""
import assert from 'node:assert/strict';
import { formatAiText } from './app/static/modules/analysis/ai.js';
assert.equal(formatAiText('thresholdState가 normal이고 추세는 stable입니다.'),'기준값 대비 상태가 양호이고 추세는 안정입니다.');
assert.equal(formatAiText('가속도 BPF caution, danger · 0.4042 g / 147 Hz'),'가속도 BPF 주의, 위험 · 0.4042 g / 147 Hz');
assert.equal(formatAiText('Misalignment / BPFO / BPFI / BSF / FTF 1X·2X·3X'),'Misalignment / BPFO / BPFI / BSF / FTF 1X·2X·3X');
assert.equal(formatAiText('NormalData normalMean 8.557002 mm/s'),'NormalData 정상 범위 평균 8.557002 mm/s');
assert.equal(formatAiText(null),null);
"""],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
