"""Reference demo helpers remain isolated; this branch uses real APIs for every equipment."""
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
 url.includes('/ai-analysis')?{analysis:{headline:'live'}}:url.includes('/email-draft')?{draft:{subject:'live'}}:
 url.includes('/chat')?{message:{role:'assistant',content:'live'}}:url.includes('/related-history')?{items:history}:source;
 return {ok:true,json:async()=>body};
};
for (const datasetId of ['1','2','5']) {
 const reply=await sendDashboardChat(datasetId,{message:'점검',recordId:3,history:[]});
 assert.equal(reply.message.content,'live');
 assert.equal(requests.at(-1).url,`/api/dashboard/${datasetId}/chat`);
 const ai=await fetchAiAnalysis(datasetId,{force:true});
 assert.equal(ai.analysis.headline,'live');
 assert.equal(ai.demoPresentation,undefined);
 assert.equal(JSON.parse(requests.at(-1).options.body).force,true);
 const draft=await fetchEmailDraft(datasetId,{recordId:3,demoPresentation:true});
 assert.equal(draft.draft.subject,'live');
 assert.equal(requests.at(-1).url,`/api/dashboard/${datasetId}/email-draft`);
 const dashboard=await fetchDashboard(datasetId);
 assert.equal(dashboard.equipment.status,'normal');
 assert.equal(dashboard.trend.analysis.isRising,false);
 assert.equal(dashboard.meta.demoPresentation,undefined);
 const related=await fetchRelatedHistory(datasetId,2,'BPFO','2026-04-02');
 assert.deepEqual(related.items,history);
 assert.match(requests.at(-1).url,/related-history\?record_id=2&selected_fault_type=BPFO&until=2026-04-02/);
}
assert.equal((await fetchDatasetSummaries())[0].status,undefined);
const selectedRequests=[];
globalThis.fetch=async (url)=>{
 selectedRequests.push(url);
 return {ok:true,json:async()=>({...source,fft:{recordId:2,records:[{id:2,measureMode:{code:'2'}},{id:3,measureMode:{code:'3'}}]}})};
};
assert.equal((await fetchDashboard('1')).fft.recordId,2);
assert.equal(selectedRequests.length,1); // no forced demo velocity selection
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[1], check=True,
        capture_output=True, text=True,
    )
