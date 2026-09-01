# CMS AI PoC

V032 설비의 상태, 진동 추세, FFT, Level 분석 및 Mock 진단 결과를 보여주는
FastAPI 기반 로컬 대시보드입니다. 현재 버전은 정적 Mock JSON만 사용하며 CSV
업로드나 실제 분석 로직은 포함하지 않습니다.

## 실행

```bash
uv run uvicorn app.main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>에 접속합니다.

## 테스트

```bash
uv run pytest
```

