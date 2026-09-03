# CMS AI PoC

설비별 진동 Trend와 FFT CSV를 표시하는 FastAPI 기반 로컬 대시보드입니다.
서버 시작 시 저장소 루트의 `data/` 폴더를 읽고, 화면의 설비 드롭다운에서
선택한 데이터셋을 확인할 수 있습니다.

## CSV 파일 규칙

파일명 앞의 번호를 하나의 데이터셋으로 묶습니다.

```text
1.Trend_<설비 정보>.csv
1.FFT_<설비 정보>.csv
```

- 같은 번호의 `WarningStatus` CSV가 있으면 최신 행에서 가속도 ALL/BPF/PEAK, 속도, 변위의 주의·위험 Level을 읽습니다. 속도 외 Level 컬럼은 선택 사항입니다.
- Trend는 `DataDate`, `VelAve`, `AccAllAve`를 필수로 사용하며, 확대 화면의 측정값 선택에는 `AccBpfAve`, `AccPeakAve`, `CrestfactorAve`를 추가로 사용합니다. 현재 PoC에서는 `CrestfactorAve`를 변위(`µm`)로 표시합니다.
- FFT는 모든 측정모드의 이력을 제공하며, 기본 화면에서는 최신 `MeasureMode=3` 속도 기록을 선택합니다. 속도 기록이 없으면 가장 최신 FFT를 사용합니다.
- FFT 확대 화면의 왼쪽 측정일시 목록에서 다른 기록을 선택할 수 있으며, 선택 결과는 기본 FFT 그래프에도 반영됩니다.
- `MeasureMode`에 따라 가속도 ALL/ENV는 `g`, 속도는 `mm/s`로 표시합니다. `MeasureFreq` 코드 `5`, `6`, `9`, `10`은 각각 500 Hz, 1 kHz, 10 kHz, 20 kHz 범위로 변환합니다.
- FFT 메타데이터 코드표는 [`docs/fft-data-metadata.md`](docs/fft-data-metadata.md)를 참고합니다.
- Trend 또는 FFT 한쪽이 없어도 설비 목록에 표시되며, 해당 그래프에는 데이터 없음 상태가 표시됩니다.
- `data/`의 실제 CSV는 저장소에 포함되지 않으므로 실행 환경에서 별도로 제공해야 합니다.

온도, 운전율 및 AI 진단은 현재 CSV에 포함되지 않아 화면에서 후속 단계 항목으로 표시됩니다.

Trend Graph를 확대하면 가속도 ALL/BPF/PEAK, 속도, 변위 계열을 선택해 함께 비교할 수 있습니다. 가속도와 속도 또는 변위를 함께 선택하면 단위별 이중 축을 사용하며, 속도와 변위는 동시에 선택할 수 없습니다.

## VelAve Level 적정선 분석

Trend CSV의 가장 최근 시각을 기준으로 최근 3개월(달력 기준)의 `VelAve`를 분석합니다. Q1과 Q3에서 IQR을 계산하고 `Q1 - 1.5 × IQR` 이상, `Q3 + 1.5 × IQR` 이하인 값을 정상 범위로 사용합니다.

- 정상값 평균의 2배를 주의 권고 Level, 4배를 위험 권고 Level로 계산합니다.
- 같은 데이터셋의 최신 `WarningStatus`에 설정된 `VELJudgeWarnValue`, `VELJudgeDangValue`와 권고값의 차이를 표시합니다.
- 차이는 `현재 설정값 - 권고값`이며, 별도의 허용오차나 적정/부적정 이진 판정은 적용하지 않습니다.
- WarningStatus가 없으면 권고값만 표시하고, Trend가 없으면 Level 분석 불가로 표시합니다.
- Level 비교 결과는 우상향 분석에 따른 설비 종합 상태와 독립적인 참고 정보입니다.

## VelAve 상승 경향 분석

현재 상태 패널은 Trend CSV의 `VelAve`를 시간 단위 이력으로 분석합니다. 평균−3σ 미만의 저값 이상치는 선형 보간하고, 양 끝의 이상치 구간은 가장 가까운 유효값으로 채웁니다. 보정한 값의 72시간 이동평균에 대해 최근 72개 구간의 선형회귀 기울기를 계산합니다.

- 기울기가 `1 / (24 × 14)` mm/s/시간보다 크면 `상승 경향`(`caution`)으로 표시합니다.
- 그 외에는 `정상`(`normal`)으로 표시합니다.
- 72시간 이동평균과 72개 회귀 구간을 모두 계산하려면 최소 143개 포인트가 필요하며, 부족하면 `추세 판단 불가`(`unknown`)로 표시합니다.

## 실행

```bash
uv run uvicorn app.main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>에 접속합니다.

## 테스트

```bash
uv run pytest
```
