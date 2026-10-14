"""Internal model enum labels should not leak into Korean dashboard prose."""
import shutil
import subprocess
from pathlib import Path
import pytest


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
