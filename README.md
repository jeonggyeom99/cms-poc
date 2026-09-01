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

- `WarningStatus` CSV는 읽지 않습니다.
- Trend는 `DataDate`, `VelAve`, `AccAllAve` 컬럼을 사용합니다.
- FFT는 최신 `MeasureMode=3` 행의 `ResultData`를 속도 스펙트럼으로 사용합니다.
- `MeasureFreq` 코드 `5`는 500 Hz, `6`은 1000 Hz 범위로 변환합니다.
- Trend 또는 FFT 한쪽이 없어도 설비 목록에 표시되며, 해당 그래프에는 데이터 없음 상태가 표시됩니다.
- `data/`의 실제 CSV는 저장소에 포함되지 않으므로 실행 환경에서 별도로 제공해야 합니다.

온도, 운전율, 상태 기준, Level 분석 및 AI 진단은 현재 CSV에 포함되지 않아
화면에서 후속 단계 항목으로 표시됩니다.

## 실행

```bash
uv run uvicorn app.main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>에 접속합니다.

## 테스트

```bash
uv run pytest
```
