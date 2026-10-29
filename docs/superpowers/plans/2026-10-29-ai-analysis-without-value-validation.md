# AI 반환값 검증 제거와 분석 문장 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 분석 구조와 API를 유지하면서 AI 반환값의 근거 대조·교정 재호출을 제거하고, Trend·FFT·History·종합 분석을 현장 담당자가 읽기 쉬운 한국어 문장으로 제공한다.

**Architecture:** 기존 `MultiAgentAnalysisGateway`의 전문 Agent 독립 호출과 종합 호출을 유지한다. 근거 카탈로그와 공통 분석 서비스를 재사용하되, AI 결과를 검증하는 단계는 서버 소유 메타데이터를 조립하는 단계로 대체한다. 기존 single 경로에도 같은 검증 제거 정책을 적용한다.

**Tech Stack:** Python >=3.11, FastAPI, Pydantic, asyncio, OpenAI SDK, pytest, 브라우저 ES modules/CSS, 기존 Node 기반 UI 테스트.

**Spec:** 이 문서의 「확정 범위와 출력 계약」. 사용자가 2026-10-29에 선택한 ‘1번: 기존 구조 유지·필요 부분 수정’과 마지막 분석 문체 요청을 기준으로 한다. 이번 요청은 계획 저장만 허용하며, 구현 승인을 뜻하지 않는다.

## Global Constraints

- 작업 위치: `C:\Users\jeong\Documents\open-source\cms-poc-codex-agent` 내부만 사용한다. 시작 브랜치는 `codex/agent`다.
- `Git commit, merge, push는 사용자 승인 없이 실행하지 마세요.` 각 작업 후 diff를 검토하되 자동 커밋 단계는 넣지 않는다.
- `기존 변경 사항을 삭제하거나 덮어쓰지 마세요.` 계획 작성 시 기존 변경은 `AGENTS.md`이며 수정하지 않는다.
- 현재 단계에서는 이 계획 파일만 작성한다. 제품 코드·테스트·설정·CSV를 수정하거나 의존성을 설치하지 않는다.
- 향후 구현은 기존 FastAPI, CSV 처리, 공통 Tool, 규칙 기반 Trend/FFT/Level 분석과 주간 FFT 집계 계산을 유지한다. 새 의존성과 Agent 프레임워크는 추가하지 않는다.
- 기존 API 필드명·중첩 구조·오류 응답 형식을 유지한다. AI 캐시, 다시 분석, Chatbot, 진단 PPT, 이메일 초안을 유지한다.
- 원본 측정 배열, API Key, 민감정보 및 원문 제공자 응답을 로그에 추가하지 않는다.
- 기본 검증 수단은 API 호출 없는 단위 테스트와 Mock 통합 테스트다. 실서비스 AI 호출·비용 발생 벤치마크는 이 계획에 포함하지 않는다.

## Review Focus

1. 존재하지 않는 인용 ID와 잘못된 설비·기간을 담은 정상 JSON: 근거 대조나 재호출 없이 텍스트를 처리하고, 조회·출처 메타데이터는 현재 요청의 서버 자료로 조립한다. Task 1·2에서 테스트한다.
2. 깨진 JSON, 잘린 응답, 타임아웃, Agent 일부 실패: 교정 호출 없이 기존 오류 또는 제한 응답으로 종료하고 성공한 영역을 보존한다. Task 1·2에서 테스트한다.
3. 베어링 메타데이터 누락, 해석 불가 FFT, 과거 사례 없음: 설명을 만들어 채우지 않고 한계/없음 안내를 유지한다. Task 3·6에서 테스트한다.
4. 여러 문단·긴 종합 설명·HTML처럼 보이는 문자열: 기존 필드에 문단이 표시되고 실행 가능한 HTML로 해석되지 않으며 보고서 입력 계약도 유지한다. Task 3·4·6에서 테스트한다.
5. 이전 캐시·동일 센서의 여러 데이터셋·FFT 선택 변경·늦게 도착한 응답: 새 정책 캐시가 분리되고 결과가 다른 설비나 새 화면으로 섞이지 않는다. Task 4·5·6에서 테스트한다.

## 확정 범위와 출력 계약

### 선택한 접근과 대안

- **선택: 기존 구조 유지·필요 부분 수정.** 검증/교정 경로와 문장 생성·조립·표시만 수정한다. 내부 `AgentDraft`, `Handoff`, 근거 카탈로그는 재사용해 호환성 변경을 줄인다.
- **미선택: 내부 Agent 응답과 근거 전달까지 경량화.** 입력량을 줄일 여지는 있으나 내부 계약과 테스트를 크게 바꿔야 하므로 이번 작업에서 제외한다.

### 제거하는 것과 유지하는 것

- **제거:** AI 문장의 수치·단위·날짜·기간·기록 ID·인용 ID·Agent 목록을 원본과 대조하여 응답을 거부하는 로직. 검증 실패 또는 출력 형식 오류를 고치기 위한 후속 LLM 호출도 제거한다.
- **유지:** JSON 파싱과 기존 Pydantic 응답 형식 처리. 이것이 실패하면 기존 오류/제한 응답으로 처리하며 수정 요청을 LLM에 보내지 않는다.
- **유지:** 요청 파라미터·Tool 조회 범위 검사, 서버 데이터셋 격리, CSV 유효성 검사, 공통 규칙 계산, 파일·이미지 입력 검사. AI 답변의 사실 여부를 검사하는 로직과 구분한다.
- **유지:** 채팅 및 PPT 생성의 독립 동작. 특히 PPT 레이아웃/렌더링 검증은 이번 Dashboard AI 반환값 검증 제거와 별개이므로 변경하지 않는다.
- **유지:** 전문 Agent들의 현재 병렬 실행과 이후 종합 호출. Supervisor/Diagnosis 재설계, History 실행 순서 변경, 화면/AI 날짜 범위 전달 불일치 수정은 이번에 선택한 최소 변경 범위에 포함하지 않는다. 기존 날짜 불일치는 후속 과제로 기록한다.

### 문장과 필드 매핑

| 영역 | 기존 필드 | 작성 방식 |
| --- | --- | --- |
| AI 추세 분석 | `trendSummary` | 최신 측정일·속도와 단위 → 주의/위험 기준 대비 상태 → 근거에 있는 상승 시작 시점·가속도 → 모니터링/추가 확인. 2~3문단, 최대 500자 |
| FFT 데이터 AI 분석 | `fftSummary` | 측정 모드와 주요 결함 후보 → 1X/2X/3X 또는 베어링 결함 성분의 해석 → 권장 점검. 2~3문단, 최대 1,200자 |
| AI 연관과거 이력 분석 | `historyFindings[].detail` | 실제 조회 사례의 설비·결함·조치·조치 후 확인 → 현재 설비에 적용할 조건부 권고. 기존 3개 항목/항목당 700자 유지 |
| AI 분석 | `headline` | 설비 상태·추세·FFT를 연결한 원인 가능성 → 우선 점검과 동일 조건 재측정 후 판단. 2문단을 허용하도록 기존 최대 180자에서 700자로 확대 |

- `SynthesisDraft.headline`의 기존 140자 제한도 700자로 맞춘다. 필드를 추가하거나 기존 소비자에게 새 필드를 요구하지 않는다.
- 예시의 `8.88 mm/s`, `6 mm/s`, `12 mm/s`, `5.37 g`, `2026-05-26`, Fume Exhaust Fan, Unbalance, BPFI는 문체 예시다. 실제 프롬프트에는 해당 값·설비·결론을 정답처럼 고정하지 않는다.
- 숫자·날짜를 쓰지 말라는 지시를 제거하고, 입력 근거에 있는 값은 자연스럽게 설명하도록 한다. 상승 시작일·조치 효과가 입력에 없으면 지어내지 말라는 프롬프트 지침은 유지한다. 이를 서버의 사실 대조 검증으로 재구현하지 않는다.
- FFT 주간 집계는 입력 근거와 기존 상태/기준 카드에 유지한다. 긴 `weeklyExplanationFacts` 전체를 AI 요약 앞에 자동으로 붙이거나 모든 문구를 반드시 반복시키지 않는다.
- Markdown `**` 강조는 필수 요구로 보지 않는다. 기존 `textContent` 표시를 유지하고 문단 개행으로 가독성을 확보한다.
- 검증 제거로 지연을 줄일 여지가 있지만 정상 최초 응답의 속도 개선률은 보장하지 않는다. 주로 교정 호출과 반복 대조 작업을 제거하는 변경이다.

## 변경 파일 지도

| 파일 | 책임 |
| --- | --- |
| `app/agents/handoff.py` | 기존 계약/카탈로그 유지, 검증 없는 `hydrate_handoff` 추가, 더 이상 쓰지 않는 대조 함수 정리 |
| `app/agents/orchestrator.py` | 전문/종합 대조·교정 제거, 문체 지시, 결과 조립, 버전/실행 로그 변경 |
| `app/ai_analysis.py` | single 경로 대조·교정 제거, 공통 문체와 `headline` 한도, 프롬프트 버전 변경 |
| `app/equipment_analysis.py` | 설비 분석 프롬프트의 짧은 headline/주간 전문 강제 지시 제거, 미사용 반환값 검증 정리 |
| `app/static/modules/analysis/ai.js` | 기존 API 결과 표시 및 History 해석 전달 |
| `app/static/modules/fft/related-history.js` | 실제 History AI 결과 표시, 비동기 이력 재렌더링 시 유지 |
| `app/static/modules/dashboard/controller.js` | 설비/기간 변경 및 최신 요청에 맞춰 History AI 표시 초기화 |
| `app/static/styles.css` | 네 분석 영역의 문단 개행 표시 |
| `tests/test_multi_agent.py`, `tests/test_ai_analysis.py`, `tests/test_ai_reliability.py`, `tests/test_equipment_analysis.py`, `tests/test_prefetched_analysis.py` | 제거되는 정책의 테스트 교체, 기존 fixture 재사용 |
| `tests/test_ai_wording_ui.py`, 신규 `tests/test_ai_narrative.py` | 문장 전달·조립, 프롬프트 계약, UI 표시·요청 전환 테스트 |
| `README.md` | 현재 정책, 남은 제한 및 테스트 방법 안내 |

`app/main.py`, 규칙 계산 모듈, CSV, `app/static/modules/demo.js`, 채팅/보고서 코드는 원칙적으로 변경하지 않는다. 기존 static import의 버전 규칙을 확인하고 실제로 수정한 프론트엔드 모듈의 import URL만 함께 갱신한다.

## Task 1: 전문·종합 Agent의 대조와 교정 호출 제거

**Files:** Modify `app/agents/handoff.py`, `app/agents/orchestrator.py`; Test `tests/test_multi_agent.py`.

**Interfaces:**
- Consumes: 기존 `AgentDraft`, `Handoff`, `Period`, `Evidence`, `SynthesisDraft`와 `tests/test_multi_agent.py`의 `context`, `draft`, `synthesis`, `gateway`, `FakeClient`.
- Produces: `hydrate_handoff(draft: AgentDraft, name: AgentName, context: dict, catalog: dict[str, Evidence], period: Period | None = None) -> Handoff`.
- Preserves: `MultiAgentAnalysisGateway.analyze(context: dict, execute: Any = None) -> AiDiagnosis`와 기존 Tool 호출 예산.

- [ ] **Step 1: 실패 테스트 작성.** 기존 Mock 완료 응답을 재사용해 `test_specialists_accept_prose_without_value_validation`에 원본과 다른 수치·단위·날짜와 알 수 없는 인용 ID를 넣는다. 텍스트가 전달되고 3개 전문 호출+1개 종합 호출로 끝나는지 확인한다. `test_synthesis_accepts_prose_without_value_validation`은 종합 문장의 미인용 수치와 `used_agents` 불일치가 재호출을 유발하지 않는지 확인한다. 핵심 단언:

```python
assert len(requests) == 4  # 모든 전문 데이터가 있는 fixture, Tool 추가 조회 없음
assert result.trend_summary == returned_trend_text
assert result.headline == returned_headline
assert original_context == context_after_call
```

- [ ] **Step 2: 실패 확인.** `uv run pytest -q tests/test_multi_agent.py -k "accept_prose_without_value_validation"` → 기존 검증/교정 동작 때문에 FAIL이어야 한다.
- [ ] **Step 3: `hydrate_handoff` 구현.** 기존 카탈로그에서 top-level/findings/candidate 인용의 합집합에 해당하는 사실을 중복 없이 복사한다. 없는 인용은 사실 목록에 추가하지 않으며 거부/교정하지 않는다. `agent_name`, `equipment_id`, `analysis_period`, `source_record_ids`, History 조회 메타데이터는 호출 역할과 현재 서버 자료로 채운다. AI가 제공한 식별자를 실제 조회 범위로 사용하지 않는다. 텍스트를 원본과 비교하지 않는다.
- [ ] **Step 4: `_specialist`·`_synthesize`·`analyze` 수정.** 형식 파싱 후 조립만 수행한다. `validate_draft`, `validate_handoff`, `prose_issues` 호출과 교정 루프/프롬프트를 제거한다. 각 역할은 출력 생성을 한 번 시도한다. 정상적인 Tool 조회에 따른 추가 completion은 기존 한도 내에서 허용하되 출력 교정과 구분한다.
- [ ] **Step 5: 실패 처리 테스트.** `test_invalid_specialist_json_does_not_retry`, `test_invalid_synthesis_json_preserves_specialist_results`, `test_partial_provider_failure_keeps_other_domains`를 추가한다. 깨진 JSON·잘린 출력은 재작성 없이 실패/제한 결과로 처리한다. 부분 성공은 보존하고 전체 제공자 장애는 기존 오류 코드를 유지한다. 역할별 출력 시도는 1회이고 추가 single fallback은 없어야 한다.
- [ ] **Step 6: 관련 테스트 통과.** `uv run pytest -q tests/test_multi_agent.py` → 새 정책으로 교체한 검증/교정 테스트와 기존 병렬/Tool/실패 테스트가 모두 PASS. 제거된 정책의 테스트를 무조건 skip하지 않는다.

## Task 2: single 경로에도 같은 정책 적용하고 미사용 검증 정리

**Files:** Modify `app/ai_analysis.py`, `app/equipment_analysis.py`, `app/agents/handoff.py`, `app/agents/orchestrator.py`; Test `tests/test_ai_analysis.py`, `tests/test_ai_reliability.py`, `tests/test_equipment_analysis.py`, `tests/test_prefetched_analysis.py`.

**Interfaces:**
- Consumes: Task 1의 `hydrate_handoff`와 기존 `OpenAIAnalysisGateway.analyze`, `AiResponseError`, Tool 실행기.
- Produces: 기존 single/equipment single의 정상 응답은 첫 파싱 결과로 반환한다. 응답 형식 오류는 `AiResponseError("schema_validation")` 등 기존 오류 체계를 사용한다.

- [ ] **Step 1: 실패 테스트 작성.** `test_single_accepts_first_schema_valid_answer_without_evidence_repair`, `test_equipment_single_accepts_first_answer_without_evidence_repair`, `test_single_malformed_json_does_not_retry`를 추가한다. 기존 `test_ai_gateway_rewrites_generic_answer_once`, `test_ai_gateway_reports_evidence_failure_after_bounded_repairs`, equipment schema repair 테스트를 새 정책으로 교체한다. Tool로 근거를 가져오는 호출 수는 그대로이고 최종 답변 작성은 1회인지 단언한다.
- [ ] **Step 2: 실패 확인.** `uv run pytest -q tests/test_ai_analysis.py tests/test_ai_reliability.py -k "without_evidence_repair or malformed_json_does_not_retry"` → FAIL.
- [ ] **Step 3: single 실행 수정.** `OpenAIAnalysisGateway.analyze`에서 `diagnosis_quality_issues`/`equipment_quality_issues`에 따른 거부와 모든 출력 교정 루프를 제거한다. 기존 초기 Tool 조회·타임아웃·클라이언트 정리는 보존한다. `normalize_equipment_period_timezone` 같은 서버 표현 정규화는 대조/교정 호출 없이 유지한다.
- [ ] **Step 4: 미사용 검증 삭제.** 호출부/테스트 의존성을 `rg`로 확인하고 `prose_issues`, `validate_draft`, `validate_handoff`, `diagnosis_quality_issues`, `equipment_quality_issues`, `weekly_summary_issues` 및 전용 보조 코드/상수를 제거한다. 공통 파싱·카탈로그·규칙 계산에 사용되는 함수는 보존한다. 해당 함수만 검증하던 테스트는 새 ‘대조 없음/재호출 없음’ 계약 테스트로 교체하고, 공유 fixture 함수는 보존한다.
- [ ] **Step 5: 통과 확인.** `uv run pytest -q tests/test_ai_analysis.py tests/test_ai_reliability.py tests/test_equipment_analysis.py tests/test_prefetched_analysis.py tests/test_tool_calling.py` → PASS. Tool 범위/예산 검사와 CSV/규칙 테스트는 그대로 통과해야 한다.

## Task 3: 네 영역의 문체와 서버 결과 조립 개선

**Files:** Modify `app/agents/orchestrator.py`, `app/ai_analysis.py`, `app/equipment_analysis.py`; Create `tests/test_ai_narrative.py`; Modify `tests/test_multi_agent.py`.

**Interfaces:**
- Consumes: Task 1·2의 검증 없는 실행, 기존 `assemble_diagnosis(context: dict, handoffs: list[Handoff], draft: SynthesisDraft | None, failure_codes: list[str] | None = None) -> AiDiagnosis`.
- Produces: 「문장과 필드 매핑」을 따르는 기존 `AiDiagnosis`. `headline` 한도만 700자로 확대하고 기존 JSON 키는 모두 유지한다.

- [ ] **Step 1: 실패 테스트 작성.** `tests/test_ai_narrative.py`에 `test_narrative_paragraphs_survive_assembly`, `test_headline_accepts_two_paragraphs_up_to_700_characters`, `test_weekly_facts_are_not_prepended_to_fft_summary`를 추가한다. Task 1의 조립 함수로 만든 Handoff를 사용하며 핵심 단언은 다음과 같다.

```python
assert result.trend_summary == trend_handoff.summary
assert result.fft_summary == fft_handoff.summary
assert result.headline == synthesis_draft.headline
assert "\n\n" in result.headline
assert result.fft_findings  # 기존 상세 근거 필드 보존
```

- [ ] **Step 2: 실패 확인.** `uv run pytest -q tests/test_ai_narrative.py` → 긴 headline/주간 전문 자동 부착으로 FAIL.
- [ ] **Step 3: 프롬프트 변경.** `SPECIALIST_INSTRUCTIONS`, 전문 공통 지시, 종합 프롬프트, `COMMON_INSTRUCTIONS`/`SYSTEM_INSTRUCTIONS`, `EQUIPMENT_INSTRUCTIONS`의 상충 지시를 일관되게 수정한다. 숫자·날짜 금지, 140자 headline 강제, 모든 주간 사실 반복 강제를 제거한다. Trend는 측정일·최신값·기준·상승·점검, FFT는 후보·패턴·점검, History는 실제 조치·현재 적용 조건, 종합은 관측·가능성·우선 조치를 작성하게 한다. 내부 필드명·인용표·같은 결론의 반복은 줄인다.
- [ ] **Step 4: 조립 변경.** `AiDiagnosis.headline`과 `SynthesisDraft.headline` 한도를 700자로 맞춘다. `assemble_diagnosis`의 주간 전문 자동 prepend를 제거한다. `historyFindings`에는 History 요약과 관측을 중복 없이 최대 3개로 전달해 요약만 있는 정상 응답도 표시할 수 있게 한다. History 요약을 일률적으로 `counterEvidence`에 복제하지 않는다. 실패 안내의 ‘검증된/종합 검증 실패’ 문구를 실제 상태에 맞는 ‘분석 실패/제한’으로 바꾼다. 필수 데이터 한계와 서버 계산 등급은 유지한다.
- [ ] **Step 5: 한계 입력 테스트.** `test_missing_metadata_keeps_limitations_without_forced_cause`, `test_no_history_does_not_create_a_case`, `test_prompts_allow_source_numbers_and_request_narrative`를 추가한다. prompt 테스트는 정책의 핵심 지시만 확인하며 문장 전체 스냅샷을 고정하지 않는다. Mock 테스트의 문장이 통과한다고 실제 LLM 문체/정답률이 보장된다고 해석하지 않는다.
- [ ] **Step 6: 통과 확인.** `uv run pytest -q tests/test_ai_narrative.py tests/test_multi_agent.py tests/test_ai_analysis.py` → PASS.

## Task 4: 문단 표시와 실제 History AI 해석 연결

**Files:** Modify `app/static/modules/analysis/ai.js`, `app/static/modules/fft/related-history.js`, `app/static/modules/dashboard/controller.js`, `app/static/styles.css`, 직접 참조하는 기존 import URL; Test `tests/test_ai_wording_ui.py`, `tests/test_demo_presentation.py`.

**Interfaces:**
- Consumes: Task 3의 `headline`, `trendSummary`, `fftSummary`, `historyFindings`와 기존 `renderAiAnalysis(payload, baseline)`.
- Produces: `renderRelatedHistoryAi(findings)`와 `resetRelatedHistoryAi()`를 `related-history.js`에서 export한다. `findings`는 기존 `{heading, detail}[]`이며 추가 API/LLM 호출을 만들지 않는다.

- [ ] **Step 1: 실패 테스트 작성.** 기존 Node subprocess 방식으로 최소 DOM fixture를 구성해 `test_analysis_paragraphs_are_rendered_as_text`, `test_history_ai_survives_related_history_rerender`, `test_history_ai_resets_on_scope_change`를 추가한다. `textContent`가 `\n\n`과 `8.88 mm/s`, BPFI를 그대로 유지하고 HTML 태그 문자열이 노드로 생성되지 않는지 확인한다. CSS는 네 영역의 `white-space: pre-line` 적용을 확인한다.
- [ ] **Step 2: 실패 확인.** `uv run pytest -q tests/test_ai_wording_ui.py` → History 연결/개행 정책 테스트 FAIL. Node가 없어 skip되면 구현 검증 완료로 간주하지 않고 미검증으로 기록한다.
- [ ] **Step 3: 표시 연결.** `renderAiAnalysis`가 `historyFindings`를 실제 History AI 표시 함수에도 전달하도록 한다. `renderRelatedHistory`는 펼침/접힘 및 비동기 이력 조회가 완료되어도 저장된 AI 해석을 다시 표시한다. 기존 ‘AI 연관과거 이력 분석’ 제목을 사용하며 AI 해석에는 ‘설비 전체 분석 기준’을 표시해 현재 선택 FFT 한 건의 조회 사례로 오해하지 않게 한다. 과거 이력 CSV 카드의 조회 정책을 바꾸지 않는다.
- [ ] **Step 4: 요청 전환 처리.** controller의 설비/기간 변경·새 분석 시작·오류 시 실제 AI History 영역을 초기화하고, 기존 `aiAnalysisRequest`의 최신 응답 확인 이후에만 채운다. FFT 선택 변경만으로 설비 전체 AI 결과를 지우거나 재호출하지 않는다. 기존 demoRelated 설명과 실제 해석이 중복되면 실제 해석이 있을 때만 대체하고 데모 단독 동작은 유지한다.
- [ ] **Step 5: 문단 스타일 적용.** `#ai-analysis-description`, `#trend-ai-summary`, `#fft-ai-summary`, 기존 AI finding detail 및 새 History AI 본문에 한정해 `white-space: pre-line`을 적용한다. `innerHTML`/Markdown 파서는 도입하지 않는다. 레이아웃 전반은 바꾸지 않는다.
- [ ] **Step 6: 통과 확인.** `uv run pytest -q tests/test_ai_wording_ui.py tests/test_demo_presentation.py tests/test_ai_narrative.py` → PASS. 실제 AI 경로는 API Mock으로 검증하고 데이터셋 1·5의 데모 고정 답변을 실제 LLM 결과로 오인하지 않는다.

## Task 5: 캐시 정책 버전과 실행 추적 정합성

**Files:** Modify `app/agents/orchestrator.py`, `app/ai_analysis.py`, `app/agents/handoff.py`; Test `tests/test_multi_agent.py`, `tests/test_ai_analysis.py`.

**Interfaces:**
- Consumes: 기존 `analysis_configuration(mode: str, model: str) -> dict`, `AiAnalysisService.analyze`, `_save_trace`, `handoff_markdown`.
- Produces: 새 정책 버전 및 기존 응답/추적 파일 형식을 유지하는 상태 메타데이터.

- [ ] **Step 1: 실패 테스트 작성.** `test_no_validation_policy_separates_old_cache`, `test_trace_reports_completion_without_claiming_validation`, `test_no_correction_requests_are_logged`를 추가한다. 기존 cache hit/force 및 source fingerprint 테스트를 재사용한다. 새 설정은 `specialistRepairs == 0`, `synthesisRepairs == 0`, `outputValueValidation is False`를 단언한다.
- [ ] **Step 2: 실패 확인.** `uv run pytest -q tests/test_multi_agent.py -k "no_validation_policy or without_claiming_validation or no_correction_requests"` → FAIL.
- [ ] **Step 3: 버전/메트릭 수정.** `AGENT_VERSION = "cms-multi-agent-v5-no-value-validation"`, `HANDOFF_VERSION = "source-linked-handoff-v7-no-value-validation"`, `PROMPT_VERSION = "cms-dashboard-analysis-v12-narrative-no-value-validation"`로 변경한다. `analysis_configuration`의 `validationPolicyVersion`은 `"disabled-poc-v1"`, repair 수는 0으로 하고 `outputValueValidation: false`를 추가한다. single 설정에도 정책 정보가 포함되므로 이전 캐시와 분리된다. TTL·캐시 파일을 지우지 않는다.
- [ ] **Step 4: 추적 정리.** 결과 상태 `validated`를 `completed`로 바꾸고 ‘검증된 JSON’ 같은 주석/Markdown 문구를 수정한다. 삭제한 검증의 실패 상세·검증 시간은 수집하지 않는다. 기존 수집기 호환을 위해 `repair_seconds`, `validation_seconds`, `validation_assembly_seconds` 키를 남기는 곳은 0으로 명시하고 이를 README에 기록한다. 요청 ID, Agent별 상태/소요시간/LLM 호출·토큰, Tool 수, 오류 코드, 최종 조립 결과는 유지한다. 원문 오류 payload를 새로 기록하지 않는다.
- [ ] **Step 5: 격리/출처 테스트.** 없는 인용 ID가 들어와도 실제 반환 FFT 참조 ID는 서버 카탈로그에서 조립되므로 `AiAnalysisService._run`이 임의 기록을 추가 조회하지 않는지 확인한다. 같은 설비 코드의 다른 dataset/source fingerprint는 캐시를 공유하지 않고, `force=True`는 새 역할 호출을 수행하는지 확인한다. 기존 FFT 기준 판정/주간 집계 결과가 동일한지도 단언한다.
- [ ] **Step 6: 통과 확인.** `uv run pytest -q tests/test_multi_agent.py tests/test_ai_analysis.py tests/test_equipment_analysis.py tests/test_fft_severity.py` → PASS.

## Task 6: 실제 CSV 기반 오프라인 통합 회귀와 문서 갱신

**Files:** Modify `tests/test_ai_narrative.py`, 필요한 기존 endpoint/UI 테스트, `README.md`. 규칙 계산·CSV·채팅/보고서 구현은 변경하지 않는다.

**Interfaces:**
- Consumes: Task 1~5의 공개 API와 기존 `load_datasets`, `load_history`, FastAPI TestClient 및 보고서 Mock gateway.
- Produces: AI 네트워크 호출 없이 재현 가능한 통합 검증 결과와 최종 변경 요약.

- [ ] **Step 1: 통합 테스트 작성.** V032 실제 CSV로 서버 context → Mock 전문 응답 → Mock 종합 → 기존 API 응답까지 실행한다. dataset 2/7/9처럼 같은 V056을 갖는 데이터도 함께 적재해 context/cache/참조가 섞이지 않는지 확인한다. `test_v032_mock_analysis_preserves_api_and_server_fft_facts`, `test_same_sensor_datasets_do_not_share_analysis_cache`, `test_fft_selection_keeps_equipment_analysis_scope`로 이름을 고정한다.
- [ ] **Step 2: Mock 정책 확인.** 모든 gateway를 fake/Mock으로 주입한다. 실제 OpenAI client 생성은 테스트 실패로 처리하는 guard를 사용하고 `.env` 키가 존재해도 외부 요청을 보내지 않는다. 없는 FFT·해석 불가 FFT·History 없음·일부 Agent 실패를 parameterize해 API가 제한 응답 또는 기존 안전한 오류로 종료하는지 확인한다.
- [ ] **Step 3: 영향 범위 테스트 실행.** `uv run pytest -q tests/test_ai_narrative.py tests/test_multi_agent.py tests/test_ai_analysis.py tests/test_ai_reliability.py tests/test_equipment_analysis.py tests/test_prefetched_analysis.py tests/test_tool_calling.py tests/test_ai_wording_ui.py` → PASS.
- [ ] **Step 4: 기능 회귀 실행.** `uv run pytest -q tests/test_app.py tests/test_chat_analysis_tools.py tests/test_history.py tests/test_fft_severity.py tests/test_report_ai.py tests/test_report_contracts.py tests/test_report_endpoints.py tests/test_report_ui.py tests/test_ppt_report.py tests/test_ppt_validation.py tests/test_ppt_frontend.py tests/test_email_draft.py tests/test_demo_presentation.py` → PASS. PPT UI 검증은 별도 기능으로 계속 동작해야 한다.
- [ ] **Step 5: 전체 테스트 실행.** `uv run pytest -q` → 새 실패 0건이 완료 기준이다. 기존 실패가 있으면 구현 전 baseline과 비교해 정확한 테스트명과 재현 결과를 기록하고, 근거 없이 기존 문제라고 단정하지 않는다. 구현 시작 시 baseline을 먼저 확보한다.
- [ ] **Step 6: 화면 확인.** 로컬 Mock 응답으로 Trend·FFT·History·종합의 여러 문단, 작은 화면 줄바꿈, 다시 분석, FFT 기록 선택 후 설비 전체 분석 유지, 보고서/이메일 동작을 확인한다. 데모 데이터셋 1·5는 고정 답변을 사용하므로 일반 데이터셋/API Mock 경로도 확인한다. 실제 LLM 문체/지연 측정은 별도 실행 사항으로 남긴다.
- [ ] **Step 7: README와 결과 정리.** 현재 동작을 설명하는 근거 검증·교정 횟수 설명을 새 정책으로 수정하고, 이력 문서의 과거 측정 결과는 덮어쓰지 않는다. 제거/유지한 검사 범위, 문체, 긴 headline, 새 캐시 버전, Mock 테스트 명령을 적는다. 최종 보고에는 변경 파일, 기존 Agent 실행 구조 유지, 통과/실패/skip, 미측정 실제 AI 지연·문체, 알려진 화면/AI 날짜 범위 불일치, 검증 미수행에 따른 수치 오류 가능성을 간결히 기록한다.

## 실행 순서와 완료 기준

1. 구현 승인을 받은 후 브랜치/기존 변경을 다시 확인하고 전체 테스트 baseline을 기록한다.
2. Task 1 → 2 → 3 → 4 → 5 → 6 순서로 실행한다. 서로 같은 계약·fixture를 수정하므로 병렬 편집하지 않는다.
3. 각 작업은 해당 회귀 테스트와 diff 검토로 마친다. commit/merge/push는 별도 사용자 승인 없이는 실행하지 않는다.
4. 정상 JSON의 사실 대조·출력 교정 LLM 호출이 0이고, Mock으로 문단 및 기존 기능 호환성이 확인되면 구현 완료로 본다. 추가 Tool 조회까지 ‘LLM 총 1회’로 제한하는 요구로 해석하지 않는다.

## 계획 자체 점검 및 현재 상태

- 사용자 선택과 범위, 제거/보존할 검사, 문체별 필드, 700자 headline의 소비자 영향, 캐시/로그/오류 정책, 실제 CSV·기존 기능 회귀를 작업별로 대응시켰다.
- Review Focus 5개 항목의 테스트 소유 작업과 기존 fixture 경로를 확인했다. 기존 삭제 정책을 skip으로 숨기지 않도록 명시했다.
- 현재는 계획 작성만 수행했다. 제품/테스트 구현, pytest 실행, 실제 AI 호출, Git commit/merge/push는 수행하지 않았다.
- 계획을 자체 검토했으며, 후속 구현 방식은 아직 선택하지 않았다. 사용자의 ‘구현하지 마’ 지시가 유지되는 동안 실행하지 않는다.
