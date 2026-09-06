# CMS AI PoC

## 실행 방법

```bash
uv sync
uv run uvicorn app.main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>에 접속하면 설비 현황 목록이 표시됩니다. CSV 데이터가 연결된 설비를 선택하면 기존 상세 대시보드로 이동하며, 상세 화면은 <http://127.0.0.1:8000/dashboard>에서도 직접 열 수 있습니다.

CMS 진단 과거 이력은 <http://127.0.0.1:8000/history>에서 검색하거나 공정별로 조회할 수 있습니다.
