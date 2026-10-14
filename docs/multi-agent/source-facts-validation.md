# 원본 근거 중심 검증 변경

기존 Multi-Agent 경로의 수치·기록 검증과 교정 1회/제한 응답을 유지하며, 단일 설비 Agent에 남아 있던 원인 지원 코드·확정 표현·부정 문구·단위 비교 표현 검증을 제거했다. 원인 후보는 자유 문자열로 받아 기존 Rule 목록 밖의 가설도 허용한다. 공개 응답 필드는 바꾸지 않았다.

Hand-off Markdown은 Observations, Cause Hypotheses, Limitations를 분리한다. 가설과 진폭 등급을 구분하고 추가 점검을 제안하도록 프롬프트에 명시한다. 문장에 포함된 수치·단위·측정일은 인용 근거와 비교하며 기존 반올림 허용 범위를 유지한다. 단일 Agent의 요약·제목·원인명·권장 점검·반대 근거·이력 문장에도 수치 검증을 적용했다.

전문/Synthesis 검증 오류에는 필드·문제 값·단위·인용 근거 ID를 요청별 로그에 추가했다. 원본 ID/기간 불일치도 선택 값과 관련 근거를 기록한다. 정책 버전은 `source-facts-only-v2`이며 캐시 키에 포함된다. 기존 요청별 로그 및 데이터셋별 Trend·FFT·History·Synthesis Markdown 저장은 유지한다. single은 교정 1회 후 제한 응답을 반환하고 추가 도구를 반복 호출하지 않는다.

검증: `UV_CACHE_DIR=/tmp/cms-uv-cache uv run pytest -q tests/test_multi_agent.py tests/test_ai_reliability.py tests/test_tool_calling.py` — 102 passed. 샌드박스 안에서는 기존 FastAPI TestClient 테스트가 대기하여 제한 밖에서 동일 관련 검사를 완료했다. 전체 회귀·브라우저·모바일 검증은 변경 범위에 따라 생략했다. UI 변경은 없다. README 실행 명령으로 서버를 시작했으며 `/dashboard?dataset=1` HTTP 200을 확인했다.

## 승인 후 실제 분석

사용자가 OpenAI API 전송과 과금 가능성을 승인한 뒤 데이터셋 1을 force 분석했다.

| 항목 | 이전 실행 | 이번 실행 |
|---|---|---|
| 응답시간 | 약 86초(Agent 로그 85.028초) | 33.687초(Prefetch 0.925초 포함) |
| LLM 호출 | 8회 | 4회(Trend 1, FFT 2, Synthesis 1) |
| 도구 호출 | 기존 로그 비교 대상 아님 | 0회 |
| 원인명 검증 실패 | Synthesis 3회, BPFI/BPFO/BSF unsupported_cause | 없음 |
| 단일 Agent 재호출 | 3회 | 없음 |
| 최종 상태 | 종합 검증 실패 후 fallback | Synthesis validated, FFT 전문 해석 제한 |

이번 실행은 약 52.313초(60.8%) 짧고 LLM 호출 수는 절반이었다. 단일 표본이며, 실패 영역과 제공자 지연이 달라 동일 품질의 성공 결과끼리 비교한 속도 개선을 보증하지 않는다. 이전 로그 ID는 `4dabb167ff3a469d839a8992c6aeed62`다.

Trend는 1회 통과했으며 제한 상태를 명시했다. FFT는 인용한 근거에 없는 `1780 rpm` 측정값과 최초 응답의 source_record_mismatch로 교정을 1회 수행했다. 두 번째 출력도 같은 RPM 인용 오류가 있어 원본 근거 기반 실패 Hand-off를 전달했다. 오류 로그에서 summary, recommended_checks[0], findings[0].interpretation, candidate_causes[0] 및 관련 근거 ID를 확인했다. History는 기존 조회 정책상 사례가 없어 LLM 호출을 생략했다. Synthesis는 한 번에 수치 검증을 통과했고 FFT/HISTORY 제한과 진폭 등급·물리 가설 구분을 최종 응답에 표시했다. 전체 전문 분석이 성공한 결과로 해석하면 안 된다.

입력/출력 토큰은 55,950/5,041(합계 60,991), 요청 ID는 `6448c3d6470c4882a2be08ed0fd707a3`다. 요청별 JSON/Markdown과 데이터셋별 Trend·FFT·History·Synthesis Markdown의 요청 ID 및 최종 응답 일치를 확인했다.

실행 명령: `UV_CACHE_DIR=/tmp/cms-uv-cache uv run python scripts/benchmark_ai.py --dataset-id 1 --mode multi --repeats 1 --cache-repeats 0 --output .cache/source-facts-live`.

결과는 `.cache/source-facts-live/benchmark.json`, `traces/<request_id>.json`, `traces/<request_id>.md`, `traces/1/{trend,fft,history,synthesis}.md`에 보존했다(Git 제외). 실제 응답은 기존 공개 JSON 필드를 유지하며, 챗봇·Rule 계산·History 조회 조건은 바꾸지 않았다.

독립 검증 결과는 **PASS**다. 같은 관련 테스트를 별도 담당자가 재실행하여 101개 통과 및 API 계약 1개 별도 통과를 확인했다. 제한 밖 실제 실행 승인 요청에 앞서 시작했던 샌드박스 분석 시도는 201.19초에 timeout으로 끝났다(호출 시도 2회, 토큰 정보 없음). 이 환경 제한 결과는 정상 외부 LLM 성능 표본으로 비교하지 않는다.

승인 후 실제 실행 산출물에 대한 별도 독립 검증도 **PASS**다. JSON/Markdown·공개 analysis 일치, 호출 수·교정 횟수·제한 표시·과거 실행 비교 수치를 확인했다. 외부 추가 호출과 테스트 재실행은 하지 않았다. 최종 서버 대상 경로는 HTTP 200이며 서버는 계속 실행 중이다.
