"""Demo display preserves measurement inputs and bypasses live AI for #1 and #5."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_demo_display_and_api_boundaries():
    script = r"""
import assert from 'node:assert/strict';
import { demoDashboard, demoSummary, demoRelatedHistory, demoFftRecord } from './app/static/modules/demo.js';
import { sendDashboardChat } from './app/static/modules/api/chat.js';
import { fetchEmailDraft } from './app/static/modules/api/email-draft.js';
import { fetchAiAnalysis } from './app/static/modules/api/ai-analysis.js';
import { fetchRelatedHistory } from './app/static/modules/api/history.js';
import { fetchDashboard, fetchDatasetSummaries } from './app/static/modules/api/dashboard.js';
const source={meta:{datasetId:'1'},equipment:{id:'V032',status:'normal'},
 trend:{points:[{value:3}],analysis:{status:'stable',isRising:false}},
 fft:{amplitudes:[0.1],frequencies:[30]},fftWeeklyDiagnosis:{state:'caution'}};
const original=structuredClone(source);
const result=demoDashboard(source);
assert.equal(result.equipment.id,'V032');
assert.equal(result.equipment.status,'caution');
assert.equal(result.trend.analysis.isRising,true);
assert.equal(result.trend.analysis.status,'rising');
assert.equal(result.fftWeeklyDiagnosis.representative.causeLabel,'Unbalance');
assert.equal(result.fftWeeklyDiagnosis.representative.grade,'초기 결함');
assert.deepEqual(source,original);
assert.strictEqual(result.fft,source.fft);
assert.strictEqual(result.trend.points,source.trend.points);
const velocity={recordId:3,metadata:{measureMode:{code:'3'}},amplitudes:[2.36],analysis:{diagnosis:{harmonics:[{order:1}],label:'uncertain'}}};
assert.equal(demoFftRecord(velocity,'1').analysis.diagnosis.label,'Unbalance');
assert.strictEqual(demoFftRecord(velocity,'1').amplitudes,velocity.amplitudes);
assert.equal(velocity.analysis.diagnosis.label,'uncertain');
assert.strictEqual(demoFftRecord(velocity,'2'),velocity);
const other={...source,meta:{datasetId:'2'}};
assert.strictEqual(demoDashboard(other),other);
const otherSummary={id:'2',status:'normal'};
assert.strictEqual(demoSummary(otherSummary),otherSummary);
const history=[{datasetId:'1',fault:'축',faultType:'Unbalance',date:'2026-04-03'},
 {datasetId:'2',fault:'축',faultType:'Unbalance',date:'2026-04-02'},
 {datasetId:'1',fault:'축',faultType:'Misalignment',date:'2026-04-01'}];
const demoHistory=demoRelatedHistory(history);
assert.equal(demoHistory[0].datasetId,"2");
assert.equal(demoHistory[0].faultType,"Unbalance");
assert.match(demoHistory[0].equipmentName,/Fume Exhaust Fan/);
assert.equal(history[0].datasetId,"1");
assert.deepEqual(demoRelatedHistory(history,'2026-04-02'),[]);
const requests=[];
globalThis.fetch=async (url,options)=>{
 requests.push({url,options});
 const body=url==='/api/history'?{items:history}:url==='/api/datasets'?{items:[{id:'1'},otherSummary]}:
 url.includes('/ai-analysis')?{analysis:{headline:'live'}}:url.includes('/related-history')?{items:[]} :source;
 return {ok:true,json:async()=>body};
};
for (const [question, expected] of [
 ['가장 먼저 볼 항목은?', /재측정/], ['판단 근거를 설명해줘', /2X·3X/],
 ['과거 이력은?', /Fume Exhaust Fan/], ['추세는?', /우상향/],
 ['FFT 1X 설명해줘', /회전 1X/], ['안녕', /점검 우선순위/],
]) {
 const reply=await sendDashboardChat('1',{message:question,history:[],recordId:3});
 assert.equal(reply.message.role,'assistant');
 assert.equal(reply.demoPresentation,true);
 assert.match(reply.message.content,expected);
 assert.match(reply.message.content,/데모 답변/);
 assert.equal(requests.length,0);
}
for (const datasetId of ['2','5']) {
 await sendDashboardChat(datasetId,{message:'점검',recordId:3,history:[]});
 assert.equal(requests.at(-1).url,`/api/dashboard/${datasetId}/chat`);
 assert.equal(requests.at(-1).options.method,'POST');
 assert.equal(JSON.parse(requests.at(-1).options.body).message,'점검');
}
requests.length=0;
const draft=await fetchEmailDraft('1',{demoPresentation:true});
assert.match(draft.draft.subject,/Unbalance/);
assert.match(draft.draft.fft,/Unbalance/);
assert.equal(requests.length,0);
const ai=await fetchAiAnalysis('1',{force:true});
assert.equal(requests.length,0);
assert.match(ai.analysis.headline,/Unbalance/);
assert.equal(ai.demoPresentation,true);
assert.equal((await fetchAiAnalysis('2',{})).analysis.headline,'live');
assert.equal(requests.at(-1).options.method,'POST');
assert.equal((await fetchDashboard('1')).meta.demoPresentation,true);
const baseFetch=globalThis.fetch;
globalThis.fetch=async (url)=>({ok:true,json:async()=>url.includes('/fft/')?velocity:{...source,fft:{...source.fft,recordId:2,records:[{id:2,measureMode:{code:'2'}},{id:3,measureMode:{code:'3'}}]}}});
const velocityDashboard=await fetchDashboard('1');
assert.equal(velocityDashboard.fft.recordId,3);
assert.equal(velocityDashboard.fft.analysis.diagnosis.label,'Unbalance');
assert.equal(velocityDashboard.fft.records.length,2);
globalThis.fetch=baseFetch;
assert.equal((await fetchDatasetSummaries())[0].status,'caution');
assert.deepEqual((await fetchRelatedHistory('1',2)).items,demoHistory);
assert.equal(requests.at(-1).url,'/api/history');
await fetchRelatedHistory('2',2);
assert.match(requests.at(-1).url,/\/api\/dashboard\/2\/related-history/);

// #5 keeps real FFT selection, weekly evidence and related history.
const fan={...source,meta:{datasetId:'5'},equipment:{id:'V191'},
 fft:{...velocity,recordId:2,metadata:{measureMode:{code:'2'}},records:[{id:2,measureMode:{code:'2'}},{id:3,measureMode:{code:'3'}}]},
 fftWeeklyDiagnosis:{representative:{cause:'BPFI',grade:'초기 결함'}}};
const fanOriginal=structuredClone(fan);
const fanDemo=demoDashboard(fan);
assert.equal(fanDemo.meta.demoPresentation,true);
assert.equal(fanDemo.equipment.id,'V191');
assert.match(fanDemo.equipment.statusLabel,/BPFI/);
assert.strictEqual(fanDemo.fft,fan.fft);
assert.strictEqual(fanDemo.trend,fan.trend);
assert.strictEqual(fanDemo.fftWeeklyDiagnosis.representative,fan.fftWeeklyDiagnosis.representative);
assert.strictEqual(demoFftRecord(velocity,'5'),velocity);
assert.deepEqual(fan,fanOriginal);
const beforeFanAi=requests.length;
const fanAi=await fetchAiAnalysis('5',{force:true});
const fanDraft=await fetchEmailDraft('5',{demoPresentation:true});
assert.equal(requests.length,beforeFanAi);
assert.match(fanAi.analysis.headline,/내륜/);
assert.match(fanAi.analysis.fftSummary,/141\.25 Hz/);
assert.match(fanAi.analysis.fftSummary,/0\.788 g/);
assert.match(fanAi.analysis.historyFindings[0].detail,/외륜/);
assert.match(fanDraft.draft.subject,/DUST COLLECT FAN.*BPFI/);
assert.equal(fanDraft.draft.fft,fanAi.analysis.fftSummary);
const fanRequests=[];
globalThis.fetch=async(url)=>{
 fanRequests.push(url);
 return {ok:true,json:async()=>url.includes('/related-history')?{items:[{datasetId:'5',faultType:'BPFO'}]}:fan};
};
assert.equal((await fetchDashboard('5')).fft.recordId,2);
assert.equal(fanRequests.length,1);
assert.equal((await fetchRelatedHistory('5',2)).items[0].faultType,'BPFO');
assert.match(fanRequests.at(-1),/\/api\/dashboard\/5\/related-history/);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[1], check=True,
        capture_output=True, text=True,
    )
