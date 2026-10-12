"""Demo display preserves measurement inputs and bypasses live AI only for #1."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_demo_display_and_api_boundaries():
    script = r"""
import assert from 'node:assert/strict';
import { demoDashboard, demoSummary, demoRelatedHistory, demoFftRecord } from './app/static/modules/demo.js';
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
assert.equal(result.fftWeeklyDiagnosis.representative.grade,'속도 알람');
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
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[1], check=True,
        capture_output=True, text=True,
    )
