# 근거 중심 검증 정책

설비 Multi-Agent 분석은 수치·단위·측정일·집계 기간·설비/근거/기록 ID를 원본과 대조한다. 구조화된 Hand-off는 원본과 정확히 일치해야 한다. 전문 Agent 문장 수치에는 기존 0.005 또는 0.01% 허용치를, 종합 문장에는 기존 0.055 또는 1% 허용치를 유지한다. 횟수와 점수는 정확히 일치해야 한다. 제목, 영역별 요약·분석, 원인 설명, 제한 설명과 권장 행동도 검증한다.

원인 키워드, 확정 표현, supports_causes, 점검 행동 포함 여부와 조건 비교 표현을 근거로 거부하지 않는다. 조건이 다르면 비교를 제한하고 불확실성을 설명하라는 프롬프트 지침은 유지한다. 통과는 수치 근거 일치를 의미하며 진단의 정답을 보증하지 않는다. 기존 single 분석과 챗봇은 변경하지 않았다.

각 Agent는 최초 호출 뒤 최대 한 번 교정한다. 전문 분석 실패는 실패 코드와 원본 근거를 전달한다. 종합 검증 실패는 검증된 하위 결과와 서버 근거로 원인 미확정 응답을 반환하며 single 재분석을 호출하지 않는다. 인증·제공자 장애·시간 초과 오류 처리는 유지한다. 검증 정책 버전을 캐시 설정에 포함한다.

AI_AGENT_TRACE_DIR 설정 시 요청별 JSON/Markdown과 데이터셋별 synthesis.md에 같은 요청 ID를 기록한다. 종합 성공은 검증된 진단, 검증 실패는 실패 코드와 제한 진단을 기록한다. 제공자 오류로 응답을 생성하지 못하면 오류 코드와 미생성 상태를 기록한다.

## 검증 결과 (2026-10-14)

- 관련 테스트: `UV_CACHE_DIR=/tmp/cms-uv uv run pytest -q tests/test_multi_agent.py tests/test_tool_calling.py tests/test_ai_reliability.py tests/test_equipment_analysis.py` — 최종 113개 통과(5.91초). 독립 검증 109개 통과 후 추가된 제목/라벨 회귀 5개도 통과.
- 독립 검증 PASS. diff 공백 검사 통과. 전체 기능 및 브라우저 검증은 서버 분석 경로 변경 범위에 따라 생략했다.
- 일반 샌드박스의 asyncio 스레드 종료 대기로 API 테스트가 멈췄으나, 승인된 실행 환경에서는 관련 테스트가 모두 통과했다.
- 실제 설정으로 데이터셋 1을 캐시 없이 1회 분석: 21.122초(근거 준비 0.929초 포함), LLM 3회, 도구 0회, 입력 41,519 / 출력 3,074 토큰. History는 자료 없음으로 호출 생략. 종합 상태 validated, 검증 실패 0회, single fallback 없음.
- 이전 86초 대비 64.878초(약 75.4%) 감소. 과거 실행의 호출 수는 제공되지 않아 직접 비교하지 않았다. 단일 실행이며 응답시간 변동을 포함한다.
- 요청 ID: `13c02bfd8cbe448d98e6bfe954665b54`. 요청별 로그와 최신 `synthesis.md`의 ID 및 결과 일치 확인.
- 실행 명령: `UV_CACHE_DIR=/tmp/cms-uv uv run python scripts/benchmark_ai.py --dataset-id 1 --mode multi --repeats 1 --cache-repeats 0 --output .cache/evidence-policy-benchmark`.
- 결과 파일은 `.cache/evidence-policy-benchmark/benchmark.json` 및 `traces/1/synthesis.md`에 보존한다(Git 제외).
