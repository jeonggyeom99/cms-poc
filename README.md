# CMS AI PoC

CSV 기반 설비 진동 데이터(Trend·FFT)와 진단 이력을 조회하고, AI 종합 분석·챗봇·진단 보고서를 제공하는 FastAPI PoC입니다. 프런트엔드는 HTML·CSS·JavaScript 정적 파일로 구성되어 FastAPI에서 함께 제공하므로 별도의 프런트엔드 빌드 없이 실행할 수 있습니다.

## 실행 방법

### 1. 준비 사항

- Python 3.11 이상
- [uv](https://docs.astral.sh/uv/getting-started/installation/): Python 환경과 의존성 관리
- 프로젝트 루트의 `data/` 폴더와 원본 CSV·베어링 결함계수 파일
- 실제 AI 기능을 사용할 경우 OpenAI API 키

아래 명령은 모두 프로젝트 루트(`pyproject.toml`이 있는 폴더)에서 실행합니다.

### 2. 의존성 설치

```bash
uv sync
```

`uv sync`는 프로젝트의 `.venv/`를 만들고 개발·테스트 의존성까지 설치합니다. 의존성 버전은 `uv.lock`으로 관리합니다.

### 3. 환경 변수 설정 (AI 기능 사용 시)

루트에 `.env`가 없다면 `.env.example`을 복사합니다. Windows PowerShell에서는 다음과 같이 실행합니다.

```powershell
Copy-Item .env.example .env
```

생성한 `.env`에 `OPENAI_API_KEY`와 사용할 `OPENAI_MODEL`을 설정합니다. 이미 `.env`가 있으면 덮어쓰지 말고 필요한 값만 수정합니다. 상세 설정은 아래 **AI 종합 분석** 절을 참고하세요.

API 키 없이도 CSV 기반 설비 목록·Trend/FFT 그래프·진단 이력은 조회할 수 있습니다. 실제 AI 분석·챗봇·보고서 생성에는 유효한 API 키가 필요하며 사용량에 따라 비용이 발생할 수 있습니다.

### 4. 개발 서버 실행

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

브라우저에서 <http://127.0.0.1:8000>에 접속합니다. `--reload`는 코드 변경 시 서버를 자동으로 재시작하며, 서버 종료는 실행한 터미널에서 `Ctrl+C`를 누릅니다.

8000 포트를 이미 사용 중이면 `--port 8010`처럼 다른 포트로 실행하고, 아래 URL의 포트도 함께 변경합니다.

### 주요 접속 주소

| 화면 | 주소 |
| --- | --- |
| 설비 현황 목록 (기본 화면) | <http://127.0.0.1:8000/> |
| 설비 진단 상세 (1번 데이터셋 예시) | <http://127.0.0.1:8000/dashboard2?dataset=1> |
| 대시보드 | <http://127.0.0.1:8000/dashboard_ui6> |
| 중앙 관제 | <http://127.0.0.1:8000/main_ct> |
| 현장 관제 | <http://127.0.0.1:8000/main_sv> |
| 진단 과거 이력 | <http://127.0.0.1:8000/history2> |
| API 문서 (Swagger UI) | <http://127.0.0.1:8000/docs> |

CSV 데이터가 연결된 설비를 목록에서 선택하면 해당 설비의 상세 화면으로 이동합니다. 기존 주소인 `/dashboard`와 `/history`도 사용할 수 있습니다.

## 폴더 구성

```text
cms-poc/
├── app/                         # FastAPI 애플리케이션
│   ├── main.py                  # 앱 생성, API·화면 라우팅, 데이터·서비스 초기화
│   ├── presentation.py          # 공통 화면 셸과 페이지 렌더링
│   ├── equipment_metadata.json  # 설비 메타데이터
│   ├── agents/                  # Trend·FFT·History 전문 Agent와 종합 분석
│   ├── analysis/                # 진동 데이터 분석 로직
│   ├── data_loader/             # CSV·FFT·진단 이력 데이터 로딩
│   ├── services/                # 대시보드 분석·조회 서비스
│   ├── reporting/               # PPT·이메일 초안 생성과 보고서 검증
│   ├── static/                  # 화면 HTML, CSS, JavaScript 및 정적 리소스
│   ├── ai_analysis.py           # AI 설정·종합 분석 서비스·캐시
│   ├── chat.py                  # 설비 진단 챗봇
│   ├── agent_tools.py           # AI가 조회하는 대시보드 도구
│   ├── equipment_analysis.py    # 설비 분석 컨텍스트와 도구 구성
│   ├── equipment_evidence.py    # 설비 분석 근거 구성
│   └── tool_calling.py          # AI 도구 호출 처리
├── data/                        # 설비별 Trend·FFT·WarningStatus CSV, 과거 이력·베어링 마스터
├── docs/                        # 설계·구현·검증 문서와 보고서
├── equipment-status-demo/       # 설비 현황 데모용 정적 리소스
├── scripts/                     # AI 벤치마크 등 보조 스크립트
├── tests/                       # API·분석·AI·보고서 등 자동화 테스트
│   └── ui/                      # Playwright 기반 브라우저 UI 테스트
├── .env.example                 # 환경 변수 설정 예시
├── .env                         # 로컬 환경 변수 (직접 생성, Git 제외)
├── .cache/                      # AI 분석 캐시·선택적 Agent 추적 결과 (자동 생성, Git 제외)
├── pyproject.toml               # 프로젝트 설정, 의존성, pytest 설정
├── uv.lock                      # 의존성 잠금 파일
└── README.md
```

서버는 시작할 때 루트 `data/`에서 데이터를 읽습니다. `app/static/`은 `/static`으로, `equipment-status-demo/`는 `/static/equipment-status-demo`로 제공됩니다. `.venv/`와 `.cache/`는 로컬 실행 중 생성되는 폴더이며 소스나 원본 데이터가 아닙니다.

## 테스트 실행

기본 테스트는 UI 테스트를 제외하고 실행합니다.

```bash
uv run pytest -q
```

브라우저 UI 테스트는 Chromium을 설치한 뒤, 별도 터미널에서 위 개발 서버를 실행한 상태로 수행합니다. 기본 서버 주소는 `http://127.0.0.1:8000`입니다.

```bash
uv run playwright install chromium
uv run pytest -q -m ui tests/ui
```

다른 포트의 서버를 검사하려면 테스트를 실행할 터미널에서 `CMS_UI_BASE_URL`을 지정합니다. 예를 들어 Windows PowerShell에서 8010 포트를 사용하는 경우:

```powershell
$env:CMS_UI_BASE_URL = "http://127.0.0.1:8010"
uv run pytest -q -m ui tests/ui
```

### Unified CMS Design Acceptance

Current safe review server: <http://127.0.0.1:8010>. The existing VS Code task
`shell: cms-task2-safe-live-8010` runs the isolated launcher below. Reuse it;
do not start a second server on the same port. Static assets update live;
Python changes require restarting that safe task.

```powershell
# Safe server, only when 8010 is free. No dotenv or external Python sockets.
.\.venv\Scripts\python.exe -B .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task2-server.py
# Final non-UI: portable Node 20 PATH + ESM option; no skipped Node tests.
.\.venv\Scripts\python.exe .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py --node task8-final-non-ui.txt -q
# Final UI: bundled Playwright Node, NODE_OPTIONS explicitly cleared.
.\.venv\Scripts\python.exe .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py task8-final-all-ui.txt -q -m ui tests/ui
```

These validation launchers belong to this checkout's SDD handoff. They disable
dotenv/provider access; the browser fixture intercepts AI/chat/email/PPT with
local success/error fixtures and denies unregistered writes. The normal
development server above is not this isolated validation runtime.

| Owner | Responsibility |
| --- | --- |
| [app/presentation.py](app/presentation.py), [app/static/partials](app/static/partials) | Explicit shell slots/retained-document regions; assets and sidebar exactly once |
| [app/static/cms-tokens.css](app/static/cms-tokens.css) | Shared typography, spacing, colors and 244/76px sidebar tokens |
| [app/static/cms-operations.css](app/static/cms-operations.css) | Shared shell, role consumers, controls, explicit-toggle sidebar; no hover/focus resizing |
| Page CSS beside each HTML owner | Page layout; detail uses [app/static/styles.css](app/static/styles.css) and [app/static/dashboard2-shell.css](app/static/dashboard2-shell.css); no new override layer |
| JavaScript modules | Behavior, data-driven geometry and chart configuration, not migrated static CSS injection. Export-document styles are separate output owners |

All 25 primary/compatible/comparison URLs and six additional direct HTML
entries remain retained; unknown external usage is not grounds for deletion.
See [docs/current-operation.md](docs/current-operation.md#11-unified-design-operations)
for the complete route list and [docs/validation/cms-design-acceptance.md](docs/validation/cms-design-acceptance.md)
for requirements, evidence, validator, results and limitations. Screenshots,
geometry, actual glyph metrics and request audits live in `.cache/cms-ui/`.
The non-UI baseline has **16 known failures**, not an all-green acceptance;
independent review is **pending**. No mobile or paid-provider validation is claimed.

## AI 종합 분석

루트 `.env`에 OpenAI API key를 설정하면 상세 대시보드의 **AI 종합 분석** 카드에서 설비 전체의 Trend·FFT·과거 이력을 분석할 수 있습니다. `.env` 값보다 운영 환경 변수의 값이 우선합니다.

```dotenv
OPENAI_API_KEY=your-api-key
# 선택 사항
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=20
AI_ANALYSIS_CACHE_TTL_SECONDS=86400
AI_ANALYSIS_MODE=multi
# 선택: 서버 출처를 붙인 Hand-off JSON/Markdown과 실행 지표 저장
# AI_AGENT_TRACE_DIR=.cache/agent-traces
```

설비 상세 화면을 열면 AI가 최근 3개월 추세와 보유한 전체 주파수 이력을 조회해 **설비 단위**로 한 번 분석합니다. 추세는 최신 측정값·단위·임계값 대비 상태와 확인 사항을 2~3문단(최대 500자), FFT는 모드·결함 후보·주요 성분 해석과 권장 점검을 2~3문단(공개 응답 최대 1,200자)으로 작성하도록 요청합니다. 공통 전문 Agent 내부 요약 한도는 기존 500자를 유지합니다. 과거 이력은 실제 사례의 조치·조치 후 확인과 조건부 권고를 최대 3개 항목(항목당 700자)으로 표시하며, 종합 `headline`은 상태·원인 가능성과 우선 점검을 연결한 2문단을 허용하도록 최대 700자로 확대했습니다. 개행은 문단으로 표시하고 HTML처럼 보이는 문자열도 `textContent`로 안전하게 표시합니다. 입력에 없는 상승 시작일·조치 효과를 지어내지 않도록 프롬프트에 지시하지만, 답변의 사실 여부는 서버에서 대조하지 않습니다. 추세 근거는 최신 추세 측정일 기준 최근 90일이며 월별 평균·표본 수·부분 월의 관측 기간을 제공합니다. 화면 날짜 범위와 AI 전달 범위의 기존 불일치는 이번 변경에서 해결하지 않았습니다.

첫 AI 요청에는 최근 90일 추세·설정 임계값과 전체 FFT 이력을 서버에서 압축한 근거를 함께 제공합니다. FFT는 측정 모드·단위·측정점·RPM·주파수 범위·분해능별로 나누며, 월별 주요 성분의 최초·최신·최소·최대값과 원본 기록 ID·측정일, 이상 기록 수·최초 이상 관측일을 포함합니다. 이 값은 월평균이 아닌 실제 관측값입니다. 각 그룹의 최초·최신·최초 이상·주요 진폭 최대 기록에서 중복을 제거한 최대 6개 대표 기록과 관련 과거 이력도 제공합니다. 해석하지 못한 기록은 제한사항으로 표시합니다.

기본 `multi` 경로는 Trend·FFT·History 전문 LLM을 병렬 호출하고, 서버 출처를 붙인 Hand-off JSON과 중복을 제거한 근거 테이블을 Main Synthesis LLM에 전달합니다. Markdown은 사람이 확인하는 추적 파일로 저장합니다. 종합 LLM은 전체 요약·위험도·통합 원인 가설·반대 근거·우선 점검만 작성하고, 서버가 전문 Agent의 요약·관측 결과와 주간 등급·기간·대표 기록을 조립해 기존 응답 형식으로 반환합니다. 근거가 있는 세 영역의 정상 경로는 LLM 4회이며, 자료가 없는 영역은 호출을 생략하고 제한을 전달합니다. `AI_ANALYSIS_MODE=single`은 기존 단일 Agent 경로를 선택하며, 충분한 근거가 있으면 LLM 1회로 분석합니다. 추가 근거가 꼭 필요한 경우에만 `get_fft_evidence`, `get_fft_history_evidence`, `get_related_history`를 사용하며, Multi-Agent는 FFT·History 각각 최대 1회 도구 응답 단계와 전체 공유 예산 4개 호출로 제한합니다. 동일 인자 반복 호출은 차단하며 Trend와 Synthesis는 추가 도구를 호출하지 않습니다. 기존 single 경로는 최대 2회 도구 응답 단계·4개 호출을 유지합니다. 이력 추가 조회는 페이지당 최대 50개이며 다음 페이지는 같은 날짜·모드 필터로 조회합니다. 서로 다른 단위나 측정 조건을 같은 추세로 비교하지 않으며, 듬성듬성한 측정에서 정확한 고장 시작일을 단정하지 않습니다. `OPENAI_TIMEOUT_SECONDS`는 각 OpenAI 응답 제한시간이며, 전체 설비 분석은 기존과 같이 최대 10배까지 허용합니다.

같은 설비·원본 측정 이력·관련 이력·모델·분석 버전의 결과는 기본 24시간 동안 재사용하며, 서버 재시작 후에도 유지됩니다. 주파수 기록이나 베어링 결함을 화면에서 바꿔도 설비 AI 분석을 다시 실행하지 않습니다. `다시 분석`은 설비 전체의 캐시를 건너뛰고 결과를 갱신합니다. 동시에 진행 중인 동일 분석은 요청을 공유합니다. 주파수 분석 아래에 실제 비교 기간과 대표 기록을 표시하며, 보고서 버튼도 서버가 FFT Hand-off의 원본 근거에서 조립한 첫 번째 대표 FFT 기록을 사용합니다.

`POST /api/dashboard/{dataset_id}/ai-analysis`는 `until`(선택), `force`(기본 false)로 요청합니다. 기존 `recordId`·`selectedFaultType`은 호환성을 위해 받지만 설비 분석의 조회 기준으로 사용하지 않습니다. 응답의 `analysis`에는 기존 상세 진단과 함께 `trendSummary`, `fftSummary`, `fftAnalysisPeriod`(실제 관측 시작·종료 일시), `fftReferenceRecordIds`가 포함됩니다.

History는 서로 다른 관측 결과를 최대 3개까지 우선 보존합니다. 중복을 제거한 뒤 자리가 남으면 별도 요약을 첫 항목으로 추가하며, 관측 결과가 없는 요약만의 응답도 표시합니다.

캐시는 프로젝트 `.cache/ai-analysis/`의 키별 JSON 파일에 저장되며, 구조화된 분석 결과와 같은 내용의 마크다운 본문을 함께 보관합니다. Git에는 포함하지 않습니다. 유효기간은 `AI_ANALYSIS_CACHE_TTL_SECONDS`의 양의 정수로 변경할 수 있으며, 잘못된 값은 기본값 `86400`을 사용합니다. 만료 여부는 요청 시 확인하고, 원본 분석 입력·모델·내부 분석 기준 버전·Agent 구성·Hand-off 버전이 바뀌면 새로 분석합니다. 압축 Prefetch도 원본 fingerprint와 조회 범위로 최대 32건·24시간 재사용하며, 명시적 재분석에서는 새로 준비합니다. 분석 실패 시 기존 파일을 유지하고 오류를 반환하며, 파일 저장 실패 시에는 분석 결과를 반환하고 메모리 캐시와 서버 로그를 남깁니다. 단일 서버 프로세스를 기준으로 하며 별도의 만료 파일 정리 작업은 없습니다.

모델은 요청마다 필요한 조회 도구를 선택하며 여러 도구를 호출할 수 있습니다. 서버는 조회 설비와 날짜·레코드 ID를 확인하고, 원본 FFT 주파수/진폭 배열은 도구 결과에서 제외합니다. API key는 브라우저에 전송되지 않습니다. 채팅 API 응답의 `toolCalls`에는 호출한 도구와 인자, 반환된 근거가 담깁니다.

`single`·`multi` 모두 최종 출력은 한 번만 JSON 파싱과 기존 Pydantic 형식 처리를 수행합니다. AI 문장의 수치·단위·날짜·기간·설비/기록/인용 ID·Agent 목록을 원본과 대조해 거부하는 검사와, 형식 또는 근거 오류를 고치는 후속 LLM 호출은 제거했습니다. `single`의 잘림·빈 응답·형식 오류는 기존 안전한 API 오류로 종료하며, `multi`의 일부 전문 Agent 또는 종합 실패는 가능한 하위 분석과 서버 근거를 담은 제한 응답을 반환합니다. 추가 single fallback은 호출하지 않습니다. 최초 single 출력 한도는 설비 분석 3,200토큰, 기존 단일 기록 분석 2,400토큰을 유지합니다. 요청 파라미터·Tool 조회 범위·CSV 유효성·데이터셋 격리·규칙 계산·파일/이미지 검사와 채팅 및 PPT의 독립 검증은 유지합니다. 검증 제거로 잘못된 수치나 해석이 그대로 표시될 수 있으며, 정상 최초 응답의 지연 개선률은 보장하지 않습니다.

추세 도구의 월평균에는 이전 월평균과의 차이(`changeFromPreviousMonth`)를 함께 제공합니다. 변화량은 도구가 제공한 값만 사용하며, 서로 다른 단위의 측정값을 하나의 증가·감소로 비교하지 않습니다.

서버 로그의 `request_id`로 분석 요청과 형식 처리 실패를 추적할 수 있습니다. 모델·데이터셋 ID·도구 제한·응답 종료 사유·JSON/스키마 오류 코드와 허용된 제공자 오류 메타데이터를 기록합니다. 제거한 원본 값 대조의 실패 상세는 수집하지 않습니다. API key, 원문 제공자 응답, 원본 측정 배열은 기록하지 않습니다. API 오류 응답의 기존 `code`와 `message` 구조는 유지하며 인증·서비스 장애·요청 제한·시간 초과를 자동으로 재작성하지 않습니다.

AI 결과는 Trend/FFT의 기존 규칙 기반 판정을 보조하는 참고 정보입니다. 남은 수명이나 MTBF를 예측하지 않으며, 현장 운전 조건과 점검 결과를 포함한 최종 판단은 담당자가 수행해야 합니다.

## AI 진단 보고서

AI 종합 분석 카드의 `진단결과 PPT`는 현재 선택한 FFT와 화면에 표시된 Trend/FFT 그래프를 바탕으로 한 장짜리 진단결과 PPTX를 다운로드합니다. `이메일 본문 복사`는 별도 수신자나 실제 메일 전송 없이, AI가 작성한 한국어 메일 초안과 두 그래프를 서식 있는 클립보드 항목으로 준비합니다. 미리보기에서 복사한 뒤 사용하는 메일 클라이언트에 붙여넣을 수 있습니다.

두 기능은 기존 `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS` 설정을 사용합니다. 브라우저가 서식 있는 클립보드 쓰기를 지원하지 않거나 권한을 거부하면 초안은 미리보기에 남고 복사 실패 메시지가 표시됩니다. 원본 FFT 주파수·진폭 배열은 AI에 전송하지 않습니다.

PPT는 작성 후 독립된 UI 검증 에이전트가 실제 렌더링 이미지와 도형·표 좌표를 확인합니다. 경계 이탈, 글자 잘림·겹침, 가독성, 그래프 축·범례 잘림이 발견되면 작성 에이전트에 돌려보내 최대 두 번 수정하고 다시 검증합니다. 그래프는 비율을 유지하여 전체를 삽입하며, 글자는 최소 10pt를 유지합니다. 문구 수정은 완전히 동일한 반복 문장 제거로 제한하여 수치·단위·조건·불확실성과 모든 진단 근거를 보존합니다.

렌더링에는 서버의 `libreoffice`와 `pdftoppm`(Poppler), 한국어 글꼴이 필요하며 명령별 제한 시간은 30초입니다. 이미지 입력과 구조화 응답을 지원하는 OpenAI 모델을 사용해야 합니다. 검증·수정에는 추가 AI 호출이 발생합니다. 도구 부재나 검증 실패 시에는 **UI 검증 미완료**, 수정 후에도 문제가 남으면 **UI 검증 경고**와 함께 PPT를 다운로드합니다. 다운로드 응답의 `X-PPT-Validation` 헤더에는 URL 인코딩한 JSON으로 상태, 수정 시도 횟수, 문제 요약을 담습니다. LibreOffice 렌더링은 PowerPoint 표시와 차이가 있을 수 있으므로 검증 통과가 모든 뷰어의 동일한 표시를 보장하지는 않습니다.

## FFT 진폭 등급과 주간 상태

상세 대시보드의 **현재 주파수 상태**는 조회 범위 내 최신 FFT 측정일과 이전 6일을 집계합니다.
속도는 회전수 기반 1X·2X·3X, 가속도 ALL·ENV는 BPFO·BPFI·BSF·FTF의 베어링 계수 기반
1X·2X·3X 진폭을 사용합니다. 속도는 ≤4 mm/s 양호, >4~≤10 초기 결함, >10~≤20 심각,
>20 정지이며, 가속도는 ≤0.2 g 양호, >0.2~<1 초기 결함, ≥1 베어링 교체입니다.

초기 결함 이상 기록에서 원인별 발생 횟수를 먼저 비교하고, 동률이면 누적 등급 점수,
최고 등급, 최근 발생 시각, 원인 코드 순으로 선택합니다. 초기 결함은 1점, 심각은 2점,
정지·베어링 교체는 3점이며 표시 등급은 선택 원인의 주간 최고 등급입니다.
가속도 한 기록에서 여러 결함이 기준을 넘으면 각각 한 번 집계합니다.
미검출 고조파는 0이나 양호로 처리하지 않고 판정 제한을 표시합니다.
이 등급은 진폭 기준 판정이며 기존 원인 진단의 확실성과 구분됩니다.

대시보드 API의 `fftWeeklyDiagnosis`는 기간, 평가·제외 기록 수, 원인별 집계와 대표 원인을
반환하며, 원인별 `peakEvidence`에는 최고 진폭의 기록·측정일·모드·고조파·주파수·단위가 포함됩니다.
상태 카드는 원인명과 등급, 기간, 통계를 분리해 표시합니다. **AI 주파수 분석**은 최대 1,200자로
입력 근거를 자연스러운 문단으로 설명하도록 요청합니다. 주간 집계는 근거와 상태/기준 카드에 유지하며,
`weeklyExplanationFacts` 전체를 요약 앞에 자동으로 붙이거나 모두 반복시키지 않습니다. AI 분석 응답의 최상위 `fftSeverityAssessments`에는 AI 대표 기록의 고조파별
값·단위·등급이 서버 계산 결과로 포함됩니다. AI가 등급 문구를 생략해도 분석 카드의
**FFT 기준 판정**에서 필수 표시하며, 기존 AI 진단 JSON 구조는 유지합니다.

## FFT 점검 방식

FFT CSV의 `ResultData`는 float32 진폭 배열로 읽습니다. `MeasureLineNum`과 배열 길이가
일치해야 하며, `MeasureFreq`가 알려진 코드이면 해당 주파수 범위를 라인 수로 나누어 각 bin의
주파수(Hz)를 계산합니다. 알 수 없는 주파수 범위는 bin 번호를 X축으로 사용하므로, 회전수 또는
베어링 결함 주파수 기반 진단은 할 수 없습니다.

공통적으로 유효한 양의 주파수만 대상으로 진폭이 큰 상위 10개 후보를 고르고, 가까운 주파수는
하나의 피크 그룹으로 합칩니다. 그룹별 최대 진폭이 기준 이상인 최대 5개 피크를 표시합니다.

| 측정모드 | 단위 | 주요 피크 기준 | 피크 그룹화 범위 |
| --- | --- | ---: | ---: |
| 속도 (`MeasureMode=3`) | mm/s | 0.5 mm/s 이상 | 1 Hz 이내 |
| 가속도 ALL (`0`) | g | 0.2 g 이상 | 5 Hz 이내 |
| 가속도 ENV (`2`) | g | 0.2 g 이상 | 5 Hz 이내 |

### 속도 FFT: 회전수 기반 점검

설비에 설정된 RPM으로 회전 주파수 `fₛ = RPM / 60`을 구한 뒤, `1X`, `2X`, `3X`
(`fₛ`, `2fₛ`, `3fₛ`) 각각의 ±1 Hz에서 가장 큰 피크를 찾습니다.

- 1X 피크가 0.5 mm/s 미만이면 판정하지 않습니다.
- 1X 대비 2X 비율이 0.4 초과이거나 3X 비율이 0.3 초과이면 `Misalignment`로 분류합니다.
- 2X/1X가 0.2 미만이고 3X/1X가 0.1 미만이면 `Unbalance`로 분류합니다.
- 그 밖의 비율은 `복합 또는 판정 불확실`로 표시합니다.

RPM이 없거나 0 이하이면 회전 주파수를 산출할 수 없으므로 속도 진단은 보류합니다.

### 가속도 ALL·ENV FFT: 베어링 결함 주파수 점검

가속도 ALL과 ENV는 설비의 RPM, 베어링 제조사·형번, 그리고
`data/0. Bearing_Fault_Frequency_Master_File.txt`의 결함계수(BPFO, BPFI, BSF, FTF)를 사용합니다.

```text
회전 주파수 = RPM / 60
결함 1X = 회전 주파수 × 결함계수
결함 2X, 3X = 결함 1X × 2, 3
```

각 결함 유형의 1X·2X·3X 목표 주파수와 그 좌우 회전 주파수 사이드밴드에서 ±5 Hz 내 최대 피크를
찾습니다. 1X·2X·3X 중 하나라도 0.5 g 이상이면 해당 결함을 이상 후보로 판단합니다. 후보가 여러
개이면 `1X + 2X/2 + 3X/3`에 사이드밴드 점수를 더한 값, 최대 피크, BPFO/BPFI/BSF/FTF 순서로
대표 결함을 선택합니다. 이상 후보가 없으면 BPFO를 기본 결함으로 선택하고 “베어링 결함 Peak 없음”을
표시합니다.

RPM, 제조사 또는 형번이 없거나 베어링 마스터에 일치하는 유효 계수가 없으면 결함 주파수 판정은 하지
않고 사유를 표시합니다. 다만 가속도 ENV는 이 경우에도 원본 FFT 스펙트럼 그래프를 계속 표시하므로
측정값 자체는 확인할 수 있습니다.

이 규칙은 스펙트럼 기반의 1차 선별을 위한 것이며, 최종 설비 판정에는 운전 조건, 추세와 현장 점검을
함께 고려해야 합니다.

## 1번·5번 설비 데모

`demo` 브랜치는 1번 설비를 초기 결함 · Unbalance · 우상향 상태로 표시하고, 직접 작성한 고정 AI 분석을 보여줍니다. 변경은 브라우저 표시 계층에만 적용합니다. CSV 원본, 추세·FFT 그래프와 서버의 실제 분석 결과는 유지됩니다. 고정 데모 분석과 이메일 초안은 API 키 없이 제공하며, 데모 설비의 보고서 버튼은 화면의 AI 답변과 그래프를 포함한 HTML 데모 보고서를 저장합니다.

<http://127.0.0.1:8000/dashboard_ui6>에서는 진단 이력 카드가 열린 상태로 시작하며 1번 설비가 맨 위에 표시됩니다. 상세 데모는 <http://127.0.0.1:8000/dashboard2?dataset=1>에서 확인합니다.

1번 설비 챗봇은 API 키 없이 고정 데모 답변을 제공합니다. 추천 질문과 직접 입력한 점검 우선순위·판단 근거·추세·FFT·유사 이력 질문을 기존 데모 분석에 맞춰 안내하며, 기타 질문에는 데모 요약과 지원 질문을 표시합니다.

1번 설비의 연관 과거 이력은 2번 Fume Exhaust Fan의 Unbalance 유사 사례로 표시하며, 바로 아래에 AI 비교 분석을 제공합니다. `그래프 보기`는 2번 데이터셋의 최신 상세 화면으로 이동합니다.

5번 Dust Collect Fan 데모는 <http://127.0.0.1:8000/dashboard2?dataset=5>에서 확인합니다. 현재 CSV의 속도 주의 알람·상승 추세와 베어링 내륜(BPFI) 초기 결함을 근거로 고정 AI 답변을 표시합니다. FFT 선택·그래프·주간 집계·연관 과거 이력은 실제 데이터를 사용합니다. 현재 CSV의 속도 8.88 mm/s, 가속도 5.37 g 및 ENV 141.25 Hz·0.788 g와 2026년 4월 27일 진단 PPT의 과거 수치를 구분하며, CSV 과거 이력의 외륜(BPFO) 진단과 PPT 내륜 진단 간 차이도 점검 사항으로 안내합니다. 재분석 시에도 같은 데모 답변을 제공하고, 이메일·HTML 데모 보고서에 동일한 답변을 사용합니다.

## Multi-Agent 출력 정책과 추적

현재 무검증 PoC 정책은 `validationPolicyVersion=disabled-poc-v1`, `outputValueValidation=false`, `specialistRepairs=0`, `synthesisRepairs=0`이며 single·multi 모두 이전 정책의 캐시와 분리됩니다. TTL과 기존 캐시 파일은 유지합니다. 성공한 종합 trace 상태는 `completed`입니다. 기존 지표 수집기와의 호환을 위해 `repair_seconds`, `validation_seconds`, `validation_assembly_seconds` 키를 남기는 곳은 모두 `0`으로 기록하며, 검증·교정 소요시간을 측정한 값이 아닙니다. `validation_failures`에는 JSON/스키마 등 출력 처리 실패 코드만 남기며 삭제한 원본 값 대조의 실패 상세는 수집하지 않습니다. 요청 ID, Agent별 상태·전체/LLM 시간·호출 수·토큰, Tool 수, 오류 코드와 최종 조립 결과는 계속 기록합니다.

전문 Agent는 서버가 제공한 원본 근거 ID를 선택해 해석합니다. 서버는 현재 요청의 카탈로그에 존재하는 근거만 연결하고 값·단위·관측일·집계 기간·측정 조건·실제 원본 기록 ID와 설비 메타데이터를 채웁니다. 존재하지 않는 인용 ID나 잘못된 설비·기간을 담은 정상 JSON도 원본 대조나 교정 호출 없이 처리하며, 이 출처 조립은 AI 해석이 사실과 일치한다는 보증이 아닙니다. History Hand-off에는 실제 FFT별 cutoff·결함 유형·조회 정책과 반환 ID를 보존합니다. 측정 조건 차이와 불확실성을 설명하라는 프롬프트 지침은 유지합니다.

전문 Agent와 Synthesis의 교정 호출은 모두 0회입니다. 자료 없음·일부 Agent 실패는 실패 코드와 제한을 보존하고 가능한 영역의 분석을 계속합니다. 정상 결과는 Trend·FFT·History 병렬 호출 뒤 Synthesis 호출이라는 기존 실행 구조를 유지합니다. 전체 시간 예산은 `10 × OPENAI_TIMEOUT_SECONDS`이며 공통 제공자 장애·인증·할당량 문제에는 fallback을 반복하지 않습니다.

새 캐시 버전은 `cms-dashboard-analysis-v12-narrative-no-value-validation`, `cms-multi-agent-v6-linked-measurements`, `source-linked-handoff-v8-measurement-bundles`입니다. 정책 버전 및 설정을 single·multi 캐시 키에 모두 포함해 이전 결과와 분리하며 기존 TTL·파일은 유지합니다.

FFT 근거는 기록·측정일·모드·주파수·진폭을 한 묶음(`evidence_catalog.measurements`)으로 함께 전달하고 기존 인용 ID를 유지합니다. 선별 및 Synthesis 전달 과정에서도 주파수·진폭 쌍을 보존합니다. 주간 최고값의 출처는 `peakEvidence.measuredAt`이며 `latestAt`은 별도 최신 발생일입니다. 주간 전체 건수는 `countsByMode`로 ALL·ENV·속도 모드별 건수와 구분합니다. 등급 계산과 대표 원인 선정 순서는 그대로입니다.

전문 Agent 내부 요약도 Trend 500자, FFT 1,200자로 구분합니다. 전체 JSON 출력 예산은 FFT 3,600토큰, Trend·History 각 2,200토큰, Synthesis 2,400토큰입니다. 요약에는 관측 → 가능한 해석 → 우선 점검을 담고, 관측·가설 항목에는 추가 설명을 중심으로 씁니다. History 자료 없음과 API 호출 실패 안내는 서버가 구분합니다. [실제 CSV 재검증 보고서](docs/multi-agent/linked-fft-evidence-validation.md)에 응답 품질과 잔존 오류를 기록했습니다. 이 방식은 정확성을 보장하지 않습니다.

`AI_AGENT_TRACE_DIR`를 지정하면 같은 요청 ID의 `<request_id>.json`과 사람이 읽을 수 있는 `<request_id>.md`를 각각 저장합니다. 동시에 `<dataset_id>/trend.md`, `<dataset_id>/fft.md`, `<dataset_id>/history.md`와 `<dataset_id>/synthesis.md`에 각 Agent의 최신 Hand-off를 개별 저장합니다(예: `.cache/agent-traces/1/trend.md`). 종합 파일은 성공 시 최종 진단을, 실패 시 실패 코드와 제한 결과를 저장합니다. 요청별 로그와 최신 파일에 동일한 요청 ID를 기록합니다. 개별 파일은 재분석 시 갱신되며 요청별 파일은 유지됩니다. Markdown 파일에는 데이터셋 ID·요청 ID·실행 지표와 서버 출처를 붙인 Hand-off가 포함됩니다. Agent별 시간·상태, 실패/성공을 포함한 LLM 호출 수·토큰, Tool 수와 fallback을 기록합니다. 제공자가 usage를 반환하지 않으면 토큰은 `null`입니다. 원문 제공자 응답·원본 측정 배열·API Key는 저장하지 않습니다. 추적 파일 보관/정리는 운영자가 관리합니다.

실제 API 호출 없는 통합 검증은 다음 명령으로 실행합니다. 실제 CSV를 읽고 전문 응답과 종합만 Mock하며, 테스트의 OpenAI client 생성 guard가 `.env` 키 유무와 관계없이 실제 호출을 막습니다.

```bash
uv run pytest -q tests/test_linked_fft_evidence.py tests/test_ai_narrative.py tests/test_multi_agent.py tests/test_ai_analysis.py tests/test_ai_reliability.py tests/test_equipment_analysis.py tests/test_prefetched_analysis.py tests/test_tool_calling.py tests/test_ai_wording_ui.py
uv run pytest -q tests/test_app.py tests/test_chat_analysis_tools.py tests/test_history.py tests/test_fft_severity.py tests/test_report_ai.py tests/test_report_contracts.py tests/test_report_endpoints.py tests/test_report_ui.py tests/test_ppt_report.py tests/test_ppt_validation.py tests/test_ppt_frontend.py tests/test_email_draft.py tests/test_demo_presentation.py
uv run pytest -q
```

Windows에서는 `PYTHONUTF8=1`을 설정하고, 이미 설치된 환경의 `.venv/Scripts/python.exe -m pytest`로 같은 그룹을 실행할 수 있습니다. Mock 테스트는 응답 계약과 회귀를 확인하며 실제 LLM 문체·응답 지연·진단 정확도를 측정하지 않습니다. 아래 이력 보고서의 과거 실측 결과는 당시 정책의 기록으로 유지합니다.

실제 비교에는 설정된 API Key가 사용되고 과금될 수 있습니다.

```bash
uv run python scripts/benchmark_ai.py --dataset-id 1 --repeats 3 --cache-repeats 5
# 한 경로만: --mode multi 또는 --mode single
uv run pytest -q tests/test_multi_agent.py tests/test_tool_calling.py tests/test_ai_reliability.py
```

이 작업 브랜치는 모든 설비에서 실제 Dashboard·AI·관련 이력·챗봇·PPT·이메일 API를 사용합니다. 고정 응답을 사용하던 기존 `demo` 브랜치는 변경하지 않았습니다. 챗봇은 기존 Tool Calling 구조를 유지합니다.

구현·검증 보고서와 실제 Hand-off 예시는 [docs/multi-agent/implementation.md](docs/multi-agent/implementation.md)를 참고하세요.

Agent 입력·출력 중복 및 교정 개선의 구현·실제 3회 측정 결과는 [Agent 성능 개선 보고서](docs/multi-agent/compact-agent-performance.md)를 참고하세요.
