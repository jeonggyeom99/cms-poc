# Agent 중복·교정 개선 결과

## 변경

전문 Agent 세 개의 병렬 구조와 현재 모델은 유지한다. 종합 Agent에는 Markdown 없이 검증된 JSON 해석과 중복 제거한 근거 테이블을 전달한다. 반복되는 출처 접두어·기간·조건은 인덱스 테이블로 표현하며 원본 근거의 값·단위·날짜·기록·조건·종류를 복원할 수 있다. 기존 FFT 기본 128개 선택에 같은 기록/조건 그룹의 RPM·모드·단위·대역·분해능을 필수 인용 근거로 추가한다. 필수 조건은 기본 개수 제한 때문에 버리지 않는다.

종합의 내부 계약은 요약·위험도·통합 원인 가설·반대 근거·권장 조치·사용 Agent와 인용 ID로 축소했다. 서버가 검증된 전문 Agent의 요약·관측 설명, Rule 주간 등급, 실제 FFT 기간·기록을 기존 `AiDiagnosis`로 조립한다. History 관측은 최대 3개다. 필수 제한은 보존하고, 공개 목록 상한을 넘으면 마지막 항목에 묶는다. 길이가 너무 긴 영역 요약은 자르지 않고 전체를 반대 근거에 보존한 뒤 그 위치를 안내한다. 종합 실패에도 검증된 전문 요약·관측은 유지한다.

교정에는 오류 코드·필드·값·단위·인용 ID·기대 기록 ID를 전달한다. 같은 기록·조건의 근거를 인용하거나 해당 수치 표현을 삭제하도록 안내하며 같은 숫자가 있다는 이유로 다른 기록을 자동 연결하지 않는다. 최대 1회 교정, 추가 single 재분석 금지, 원인명 의미 검증 제외와 원본 수치 검증은 유지한다.

Agent/Hand-off 버전은 `cms-multi-agent-v4-compact` / `source-linked-handoff-v6-compact`다. 캐시 키에 새 구성과 역할을 포함한다. 모델, 공개 API 필드, Rule 계산·History 조회 조건·single·챗봇은 변경하지 않았다. Markdown은 계속 요청별·데이터셋별로 저장한다.

실행 지표는 Agent별 LLM 시간·토큰·교정 추가 시간·검증 시간, 전문 병렬 구간, 종합 검증/조립을 구분한다. 벤치마크 요청별 로그에는 준비·후처리/저장 시간과 요청 ID도 포함한다. 추적 파일 저장 시간은 서버 로그에 별도 남긴다.

## 검증

- 관련: `UV_CACHE_DIR=/tmp/cms-uv-cache uv run pytest -q tests/test_multi_agent.py tests/test_ai_reliability.py tests/test_tool_calling.py` — 독립 검증 **106 passed**, PASS.
- 전체: `UV_CACHE_DIR=/tmp/cms-uv-cache uv run pytest -q` — **350 passed, 16 failed**. 실패는 작업 시작 HEAD를 `/tmp/cms-agent-baseline-20261016`에 `git archive`로 복사해 동일 명령을 실행했을 때도 모두 재현됐다(**346 passed, 같은 16 failed**). 이번 Agent 테스트 변경으로 통과 수가 4개 늘었다. 기존 실패는 정적 URL 버전 기대와 이전 의미 검증/필수 문구 정책 기대다. 이번 변경에 의한 신규 실패는 없다.
- 근거 테이블 복원, RPM 인용 교정, 병렬 호출, 영역별 결과 재사용, 필수 제한 보존, 내부 종합 계약의 영역 덮어쓰기 차단, 잘못된 값·단위·날짜·기간·ID 거부, 교정 상한, 공개 API·캐시·Markdown을 확인했다.
- 테스트는 샌드박스의 기존 TestClient 대기 문제 때문에 승인된 실행 환경에서 완료했다. UI 변경이 없어 브라우저·모바일 검증은 생략했다.

## 승인 후 실제 데이터셋 1 분석

사용자가 설비 정보·Trend·FFT 압축 근거·관련 이력을 기존 OpenAI API로 전송해 캐시 없이 3회 분석하는 것과 과금 가능성을 명시적으로 승인했다. 같은 설정 모델 `gpt-5.6-luna`를 사용했다.

실행: `UV_CACHE_DIR=/tmp/cms-uv-cache uv run python scripts/benchmark_ai.py --dataset-id 1 --mode multi --repeats 3 --cache-repeats 0 --output .cache/compact-agent-benchmark`.

| 항목 | 기존 표본 | 개선 1회 | 개선 2회 | 개선 3회 |
|---|---:|---:|---:|---:|
| 전체 응답(초) | 33.687 | 18.628 | 14.470 | 15.792 |
| LLM 호출 | 4 | 3 | 3 | 3 |
| 교정 호출 | 1 | 0 | 0 | 0 |
| 근거 준비(초) | 0.925 | 0.938 | 1.035 | 1.018 |
| 전문 병렬 구간(초) | 약 19.90 | 9.685 | 7.626 | 8.090 |
| 종합 구간(초) | 12.661 | 7.865 | 5.798 | 6.674 |
| 종합 입력 토큰 | 16,536 | 5,929 | 5,805 | 5,963 |
| 종합 출력 토큰 | 1,499 | 896 | 827 | 862 |

중앙값은 **15.792초**, 범위는 **14.470~18.628초**다. 기존 단일 표본 33.687초 대비 중앙값이 약 **53.1%** 짧다. 종합 입력은 세 표본 모두 절반 이하로 줄었고 출력은 모두 약 900토큰 이하 목표를 충족했다. 전문 분석과 이후 종합 호출의 순차 대기는 남아 **10초 목표는 달성하지 못했다**. 같은 모델에서도 제공자 지연과 출력 분량은 달라지며, 기존은 FFT 교정 실패 표본이므로 동일 품질의 성공 결과끼리 비교한 개선율로 해석하지 않는다.

세 실행 모두 Trend·FFT 전문 해석의 수치 검증과 Synthesis 검증이 최초 호출에 통과했다. 전문 상태 `limited`는 운전조건·진단 근거 부족을 설명하는 정상 제한 상태이며 `llm_success=true`다. 기존 표본의 FFT `failed`와 구분한다. History는 기존 조회 조건상 사례가 없어 호출을 생략했다. 도구 호출·검증 실패·single fallback은 모두 0이다. 실제 History LLM 성공 경로는 이번 설비에서 실행하지 않았으며 사례 fixture로 검증했다. 검증 통과는 진단의 정답을 보증하지 않는다.

요청 ID:

- `7f027d73da8a4f26a7c8d7ce066eca76`
- `0507b95704b343ce8374b7ab5a9fed6c`
- `01af37af812f42e9a3280bfc022087ee`

실제 결과와 요청별 JSON/Markdown은 `.cache/compact-agent-benchmark/benchmark.json`, `traces/<request_id>.json`, `traces/<request_id>.md`에 보존한다(Git 제외). 최신 네 Agent Markdown은 `traces/1/{trend,fft,history,synthesis}.md`에 있으며 마지막 요청 ID를 공유한다. 이전 비교 표본은 `.cache/source-facts-live/benchmark.json`과 요청 `6448c3d6470c4882a2be08ed0fd707a3`이다.

실제 3회 산출물의 별도 독립 검증도 **PASS**다. 공개 analysis·trace·전문 결과·필수 제한·주간 근거·최신 네 Markdown의 요청 ID 일치를 확인했다. 공개 참조 50개 초과분과 긴 주간 근거도 삭제하지 않고 반대 근거에 보존하는 경계 테스트를 추가했다. 이 경계 처리는 실제 데이터셋 1의 세 표본 결과에 영향을 주지 않는다. 로컬 서버의 최종 `/dashboard?dataset=1` 접속은 HTTP 200이며 서버는 실행 중이다.
