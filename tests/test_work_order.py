import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js unavailable')
def test_work_order_defaults():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import {workOrderDefaults} from './app/static/modules/report/work-order.js';
const fields=workOrderDefaults({name:'Pump',plant:'4 선재'},'Unbalance',new Date(2026,3,30,10));
const values=Object.fromEntries(fields.map(([key,value])=>[key,value]));
assert.equal(fields.length,26);
assert.equal(values['설비'],'Pump');
assert.equal(values['area'],'4 선재');
assert.equal(values['보조설명'],'Unbalance');
assert.equal(values['계획 시작일시'],'2026-05-01T09:00');
assert.equal(values['계획 완료일시'],'2026-05-01T17:00');
assert.equal(values['상태'],'작성 중');
'''],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
