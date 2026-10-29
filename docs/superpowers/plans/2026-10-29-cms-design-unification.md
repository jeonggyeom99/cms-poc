# CMS Dashboard Design Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 기능을 보존하면서 전체 화면을 하나의 밝고 정돈된 산업용 B2B 대시보드로 통일하고, 박스별 글자 크기와 정보 정렬의 불일치를 해소한다.

**Architecture:** FastAPI와 정적 HTML/CSS/JavaScript, Plotly를 유지한다. 공통 토큰, 공통 레이아웃과 컨트롤, 페이지 전용 배치의 소유권을 분리하고 서버 문자열과 JS에 흩어진 정적 스타일을 실제 원본에서 제거한다. 설비 알람 현황을 대표 화면으로 완성한 뒤 나머지 화면에 확장한다.

**Tech Stack:** Python >=3.11, FastAPI, native JavaScript modules, CSS custom properties, Plotly 3.1.0, pytest/HTTPX, 기존 Node 기반 UI 단위 테스트. 구현 시에만 개발용 Python Playwright를 추가한다.

**Spec:** 이 문서의 [Requirements Baseline](#requirements-baseline). 2026-10-29 대화의 디자인 통일 계획과 타이포그래피 추가 요구사항을 원문 설계 기준으로 삼았다. `docs/superpowers/specs/feature.md`는 존재하지 않으며, 별도의 승인된 설계 파일이 있다고 가정하지 않는다.

## Global Constraints

- "단순히 전체 폰트 크기를 일괄 변경하는 작업이 아닙니다." 같은 역할은 통일하되 제목, 라벨, 값, 핵심 수치의 위계를 보존한다.
- "디자인 통일성과 정보 가독성을 최우선으로 작업해주세요."
- "기존 API, 데이터, 진단 로직은 변경하지 않습니다."
- "설비·이력에서 상세로 이동하는 링크와 조회 시점 조건을 유지합니다."
- "FFT 선택, 차트 확대, AI 분석, PPT·이메일·채팅 기능을 보존합니다." 기존 W/O 기능도 회귀시키지 않는다.
- "실험·구버전 페이지: 임의 삭제하지 않고 사용 여부를 확인합니다. 유지할 페이지도 공통 디자인 적용 범위에 포함합니다."
- "단순히 override 파일을 하나 더 얹지는 않습니다." 기존 선언의 책임을 옮기고 중복 원본을 제거한다.
- "모바일 검증은 별도 요청 전까지 제외합니다." 기존 모바일 동작을 의도적으로 제거하지 않는다.
- "마지막 수정 후 대상 화면을 다시 열어 확인하고, 서버는 실행 상태로 남깁니다." 이는 향후 구현 완료 기준이며 계획 작성 단계에서는 서버를 시작하지 않는다.
- 현재 요청은 계획 파일 저장까지다. 제품 코드 수정, 의존성 설치, 테스트 구현, 서버 실행, 브랜치 생성과 커밋을 수행하지 않는다.

## Review Focus

1. 긴 한글 공장명과 짧은 센서번호가 나란히 표시될 때 같은 역할의 글자 크기, 줄 높이와 기준선이 일치해야 한다. Task 2/5의 실측 테스트로 검증한다.
2. 사이드바 호버, 내부 포커스 이동, 저장소 접근 실패가 본문 폭을 바꾸거나 네비게이션을 막으면 안 된다. Task 3의 클릭/키보드/저장소 실패 테스트로 검증한다.
3. 과거 이력에서 진입한 `dataset`, `until`, `start`와 선택 FFT가 스타일 변경이나 링크 재구성으로 소실되면 안 된다. Task 5/6의 URL 및 요청 인자 테스트로 검증한다.
4. 로딩, 빈 결과, API 오류, 긴 AI 응답에서 영역이 겹치거나 정보가 잘리지 않아야 한다. Task 4/5/6의 네트워크 제어 테스트로 검증한다.
5. 사이드바 전환 이후 Plotly와 확대 모달이 정상 크기로 다시 그려지고 PPT/이메일용 캡처 규칙은 유지되어야 한다. Task 3/5/8의 차트 및 출력 회귀 테스트로 검증한다.

---

## Requirements Baseline

### Intent And Scope

- 옅은 회색 배경, 흰색 정보 영역, 절제된 파란색 포인트를 사용한다. 정상·주의·심각 색은 상태 의미에만 사용한다.
- 장식성 문구, 과도한 그림자와 그라데이션을 줄이고 정렬, 간격, 타이포그래피로 구분한다. 섹션을 장식용 카드로 중첩하지 않는다.
- 운영 대시보드는 핵심 지표 → 위험 설비 → 추세 → 조치 대상 순서로 읽히게 한다.
- 알람 현황은 필터와 결과 수의 연결, 설비 트리·목록의 선택 상태, 상태 배지를 정리한다.
- 상세는 설비 정보와 액션을 상단에 모으고 Trend·FFT 공간을 확보한다. AI 요약과 근거의 위계를 구분한다.
- 이력은 검색 조건, 결과 표, 진단 내용의 위계와 긴 텍스트·날짜·상태 표시를 정리한다.
- 중앙·현장 관제는 기존 데이터 의미를 유지하며 위험도와 작업 우선순위를 먼저 보여준다.
- 역할별 글자 크기·굵기·줄 높이를 통일한다. 본문뿐 아니라 표, 필터, 배지, 버튼, 동적 생성 내용, 차트 제목·축·범례까지 포함한다.
- `공장 / 3 전기강판 3DNL`, `센서번호 / 56`은 라벨끼리, 값끼리 크기·굵기·줄 높이·시작 위치를 맞춘다. 서로 다른 역할까지 같은 크기로 만들지 않는다.
- 동일 행의 정보 박스는 내부 여백과 라벨-값 간격을 맞춘다. 긴 이름은 개별 폰트 축소 대신 줄바꿈과 공간 배분으로 처리한다.
- CSS 숫자 일치만으로 완료하지 않는다. 모든 대상 화면을 실제 데스크톱 브라우저에서 열어 잘림·겹침·불필요한 줄바꿈·높이 불균형을 확인한다.

### Approaches

| 방식 | 장단점 | 이번 계획의 판단 |
| --- | --- | --- |
| 마지막에 override CSS 추가 | 빠르지만 서버/JS/페이지 CSS 충돌이 남는다 | 요구사항과 충돌하여 제외 |
| 프런트엔드 전체 재작성 | 구조를 새로 만들 수 있으나 차트·진단·출력 기능 회귀 위험이 크다 | 범위에서 제외 |
| 현재 기술의 점진적 리팩토링 | 중간 검증이 가능하고 기존 컨트롤러를 보존한다. 중복 원본 제거가 필요하다 | 사용자 제시 방향을 구현 계획의 기준으로 채택 |

### Planner Decisions

다음 값과 도구는 사용자가 지정한 확정 수치가 아니라 계획 작성자의 제안이다. Task 4 대표 화면 검토에서 조정하면 공통 토큰 한 곳과 대응 테스트를 함께 갱신한다.

| 역할/규칙 | 제안값 |
| --- | --- |
| 페이지 제목 | 24px / 32px, weight 700 |
| 패널 제목 | 16px / 24px, weight 600 |
| 본문·항목 값·입력·버튼 | 14px / 22px, weight 400 또는 값 강조 600 |
| 라벨·보조 설명·표 머리글 | 13px / 20px, weight 400 또는 머리글 600 |
| 핵심 KPI 수치 | 28px / 36px, weight 700; 일반 메타데이터에 적용하지 않음 |
| 차트 축·범례·툴팁 | 12px / 18px 상당; Plotly는 font.size=12 |
| 글꼴 | 기존 Pretendard 우선, Noto Sans KR 등 한국어 fallback 유지; 새 폰트 다운로드를 전제로 하지 않음 |
| 자간 | 0; viewport 기반 폰트 크기와 음수 자간 제거 |
| 간격·컨트롤 | 4/8/12/16/24/32px, 입력·버튼 높이 36px, 기본 표 행 최소 44px |
| 배경·텍스트·테두리·포인트 | #f4f6f8 / #20262e / #dce1e6 / #2563eb |
| 정상·주의·심각 | #17824d / #a15b00 / #c93434; 텍스트 상태명도 함께 표시 |
| 프레임 | 개별 정보 항목·모달 radius 6px, 최대 8px; 큰 섹션은 비부유 레이아웃 |
| 사이드바 | 펼침 244px, 접힘 76px; 최초 펼침, 명시적 버튼으로만 변경 |
| 상태 보존 | localStorage key `cms.sidebar.expanded`; 저장 실패 시 메모리 상태로 계속 동작 |
| 데스크톱 점검 | 1280x800, 1440x900, 1920x1080; 대표 화면에서 125% 브라우저 확대도 수동 점검 |
| 브라우저 자동화 | 개발 의존성 `playwright>=1.55,<2`, Chromium; 새 UI 프레임워크나 런타임 의존성 없음 |

## Current Code Anchors

- `app/main.py:65`의 `operations_page(page: str) -> str`는 속성과 CSS/JS 링크를 치환한다. 페이지 라우트의 별도 `<style>` 주입은 이 함수 밖에도 존재한다.
- `app/main.py:198-320`의 관제/대시보드/알람/상세/이력 라우트가 HTML과 스타일을 개별 변경한다. API 처리 구간은 변경 대상이 아니다.
- `app/static/cms-operations.css:124`의 hover/focus-within 확장과 `dashboard2-shell.css`, 알람 HTML, 서버 주입 CSS가 중복된다.
- `app/static/index.html:41`, `modules/summary/summary.js`의 `populateSummary(data)`가 공장·센서번호를 표시한다. `styles.css:307`의 14px과 `cms-operations.css:724`의 12px 규칙이 충돌한다.
- `modules/core/plot.js`의 `baseLayout()`와 FFT/Trend/Timewave의 로컬 설정은 별도 폰트 값을 가진다. 보고서 `modules/report/chart-capture.js`의 확대된 출력용 글자는 별도 목적이므로 보존한다.
- 기존 검증은 pytest/HTTPX와 Node 스텁이다. 브라우저 기하·폰트·실제 Plotly 확대를 확인하는 자동화는 새로 필요하다.
- 현재 `tests/test_operations_ui.py`는 구버전에 공통 스타일이 없어야 한다고 검증한다. 사용 여부 확인 후 유지 페이지의 공통 적용 범위를 넓힐 때 이 기대를 의도적으로 갱신한다.

## Route Inventory

Task 1에서 아래 전부를 열어 실제 사용 링크와 화면 상태를 기록한다. 현재 분류는 코드상의 분류이며 미사용 판정이 아니다.

| 분류 | URL | 소유 파일 |
| --- | --- | --- |
| 대표 알람 현황 | `/`, `/equipment-status2` | `equipment-status2.html`, `equipment-status.css`, `modules/equipment-status/controller.js`, `equipment-status2.js` |
| 운영 대시보드 | `/dashboard_ui6` | `kpi-dashboard-concept.html`, `modules/main/kpi-concept.js`, `dashboard-chart-panels.js` |
| 설비 상세 | `/dashboard`, `/dashboard2` | `index.html`, `styles.css`, `dashboard2-shell.css`, `modules/dashboard/controller.js` |
| 진단 이력 | `/history`, `/history2` | 두 라우트 모두 `history.html`, `history.css`, `modules/history/controller.js` |
| 중앙·현장 | `/main_ct`, `/main_sv` | `main-workspace.html`, `main-workspace.css`, `modules/main/workspace.js` |
| 관제 변형 | `/main_ct1`, `/main_ct2`, `/main_ct3`, `/main_sv1`, `/main_sv2`, `/main_sv3` | `main-control.html`, `main-control.css`, `modules/main/control-dashboard.js` |
| 비교 화면 | `/main`, `/dashboard_ui1`, `/dashboard_ui2` | `main.html`, `dashboard-ui1-kpi.html`, `kpi-dashboard-concept.html`; 대응 CSS/JS |
| 실험 화면 | `/dashboard_ui3`, `/dashboard_ui4`, `/dashboard_ui5`, `/dashboard_ui1_canvas` | `design-lab.html`, `dashboard-ui5.html`, `dashboard-ui1-canvas.html`; 대응 CSS/JS |
| 직접 정적 접근 | `/static/history2.html`, `/static/dashboard-ui1-fresh.html`, `/static/dashboard-lab.html` | 같은 이름의 HTML 및 참조 CSS/JS; 접근 경로와 사용 여부를 확인 |
| 공유 데모 데이터 | `/static/equipment-status-demo/*` | `equipment-status-demo/equipment-status-excel-data.js`, `equipment-status-tree-data.js` |

`equipment-status-demo/`는 현 알람 화면에서 읽는 데이터 파일이다. 구버전이라는 이유로 제거하거나 데이터 값을 변경하지 않는다. 정적 직접 접근 HTML은 서버 템플릿 슬롯을 처리할 수 없으므로 Task 7에서 정적으로 완성된 공통 자산 참조를 사용한다.

## File Ownership And Interfaces

기존 파일의 경계는 유지하며 아래 작은 단위만 추가한다. 아래 신규 경로는 구현 때 생성할 대상이지 현재 존재하는 파일이라는 뜻이 아니다.

| 파일 | 책임 |
| --- | --- |
| Create `app/static/cms-tokens.css` | 색상·역할별 글자·줄 높이·간격·높이 토큰. 레이아웃 selector를 넣지 않음 |
| Modify `app/static/cms-operations.css` | 공통 셸·헤더·컨트롤·상태 배지. 기존 충돌 선언을 대체하며 토큰 사용 |
| Create `app/presentation.py`, `app/static/partials/cms-sidebar.html` | 공통 사이드바와 명시적 HTML 슬롯 조립. 스타일 문자열은 생성하지 않음 |
| Modify `app/main.py` | 화면 라우트만 위 조립기로 연결. API·lifespan·진단 서비스는 보존 |
| Modify `app/static/modules/core/cms-operations.js` | 공통 네비게이션·날짜·명시적 접기 상태·레이아웃 변경 이벤트 |
| Create `app/static/equipment-status2.css` | 알람 페이지의 인라인/주입 정적 스타일을 이관한 페이지 전용 배치 |
| Create `app/static/dashboard-chart-panels.css` | JS가 삽입하던 공통 지표·차트·툴팁 정적 스타일 |
| Modify 기존 페이지 HTML/CSS | 페이지 전용 배치와 명시적 공통 슬롯. 공통 폰트·사이드바 규칙 복제 금지 |
| Create `tests/ui/conftest.py`, `tests/ui/helpers.py` | 브라우저·스크린샷·데이터 fixture와 실측 공통 도구 |
| Create `tests/ui/test_cms_{baseline,shell,typography,equipment_status,detail,history,control,variants}.py` | 작업별 실제 화면 회귀 테스트 |
| Create `tests/test_cms_presentation.py`, `tests/test_cms_chart_typography.py` | 서버 조립·스타일 소유권·Plotly 설정 단위 테스트 |
| Create `docs/validation/cms-design-{baseline,acceptance}.md` | 화면 목록, 기존 실패, 전후 시각 결과와 독립 검증 결과 |

## Implementation Tasks

아래 작업과 명령은 모두 향후 구현자를 위한 것이다. 현재 문서 작성에서는 실행하지 않는다. 각 작업은 자체 red/green 검증 뒤 검토 가능한 단위로 끝낸다. 커밋은 사용자가 허용한 경우에만 명시된 파일을 대상으로 수행한다.

### Task 1: 기준선과 데스크톱 검증 기반

**Files:**
- Read: `docs/current-operation.md`, `tests/test_operations_ui.py`, `tests/test_app.py`, `tests/test_history.py`.
- Modify: `pyproject.toml`.
- Create: `tests/ui/conftest.py`, `tests/ui/helpers.py`, `tests/ui/test_cms_baseline.py`, `docs/validation/cms-design-baseline.md`.

**Interfaces:** `cms_page: playwright.sync_api.Page` fixture는 `CMS_UI_BASE_URL` 또는 `http://127.0.0.1:8000`에 연결한다. `open_page(cms_page, path: str) -> None`는 DOM과 폰트 준비를 기다린다. `text_metrics(locator: Locator) -> dict`는 computed `fontSize`, `lineHeight`, `fontWeight`, `fontFamily`와 Range의 top/bottom을 반환한다. `capture_page(cms_page, name: str) -> Path`는 `.cache/cms-ui/`에 이미지를 저장한다.

- [ ] **Step 1:** 기존 기준선을 실행한다: `uv run pytest -q`. Node/uv/브라우저 가용성과 기존 실패를 baseline 문서에 기록한다. 기존 실패는 UI 작업의 실패와 구별하고 무관한 테스트를 수정하지 않는다.
- [ ] **Step 2:** UI marker를 사용하는 `test_primary_routes_render`를 작성한다. `assert response.status == 200`, `assert page.locator("main").count() >= 1`, `assert page_errors == []`를 운영 라우트 목록에 적용한다. 아직 없는 fixture 때문에 실패하는지 `uv run pytest -q -m ui tests/ui/test_cms_baseline.py`로 확인한다.
- [ ] **Step 3:** 개발 의존성에 Playwright와 pytest `ui` marker를 등록한다. 기본 테스트는 `-m 'not ui'`로 UI 서버를 요구하지 않게 하며, fixture에서 Playwright를 지연 import한다. `uv sync`, `uv run playwright install chromium`은 이 구현 단계에서만 실행한다. 서버 연결 실패를 무조건 skip하거나 AI 키를 요구하지 않는다.
- [ ] **Step 4:** 비어 있는 포트를 확인하고 VS Code 실행 task로 `uv run uvicorn app.main:app --host 127.0.0.1 --port <확인한 포트>`를 시작한다. `CMS_UI_BASE_URL`을 해당 URL로 설정하고 Step 2 명령이 PASS인지 확인한다. 네트워크 지연·오류·빈 결과용 fixture는 실제 API 스키마를 유지하고 AI/출력/채팅은 기존 테스트의 유효 응답을 사용해 유료 호출을 차단한다.
- [ ] **Step 5:** Route Inventory의 모든 화면과 로딩/빈 결과/오류, 주요 링크, 기본 글꼴 가용성을 캡처한다. 사용 여부가 불명확한 화면은 유지 대상으로 기록하고 담당자 확인 전 삭제·리다이렉트를 하지 않는다. baseline 문서와 테스트 기반을 검토한 뒤 허용 시 `test: add desktop CMS UI baseline`로 커밋한다.

### Task 2: 역할별 토큰과 차트 타이포그래피

**Files:**
- Create: `app/static/cms-tokens.css`, `tests/ui/test_cms_typography.py`, `tests/test_cms_chart_typography.py`.
- Modify: `app/main.py`, `app/static/cms-operations.css`, `app/static/styles.css`, `app/static/modules/core/plot.js`, `app/static/modules/fft/chart.js`, `app/static/modules/trend/chart.js`, `app/static/modules/timewave/chart.js`.

**Interfaces:** `cms-tokens.css`의 `:root`는 `--cms-font-family`, `--cms-type-{page,section,body,label,kpi,chart}`, 대응 `--cms-leading-*`, `--cms-weight-*`, `--cms-space-*`, `--cms-control-height`, `--cms-nav-{expanded,collapsed}`를 제공한다. `readChartTypography(root: Element = document.documentElement) -> {family: string, size: number}`를 `plot.js`에 export하고 기존 `baseLayout() -> object` 시그니처는 유지한다. computed style이 없는 Node 스텁에는 위 표의 fallback을 사용한다.

- [ ] **Step 1:** `test_metadata_uses_role_typography`에 `assert label_sizes == {"13px"}`, `assert value_sizes == {"14px"}`, `assert value_line_heights == {"22px"}`를 작성한다. `test_chart_layout_uses_common_typography`는 기존 Node 테스트 방식으로 `assert.equal(layout.font.size, 12)`와 축/범례/툴팁의 12px를 검증한다.
- [ ] **Step 2:** `uv run pytest -q tests/test_cms_chart_typography.py`와 `uv run pytest -q -m ui tests/ui/test_cms_typography.py`를 실행해 현재 10/11/12/14px 혼용 때문에 실패하는지 확인한다.
- [ ] **Step 3:** 제안 토큰을 정의하고 공통 제목·본문·라벨·값·컨트롤에 연결한다. HTML의 의미 구조를 유지하고 메타데이터는 라벨/값 행의 line-height와 시작 위치를 분리해 맞춘다. 차트 기본값과 로컬 override를 정리하되 캡처 전용 `chart-capture.js`의 출력 크기는 변경하지 않는다. 현재 `operations_page`의 자산 조립에 토큰 참조를 추가해 페이지 CSS보다 먼저 정확히 한 번 읽는다. Task 3에서 이 책임을 새 조립기로 옮긴다.
- [ ] **Step 4:** Step 2와 `uv run pytest -q tests/test_fft_layout_ui.py tests/test_report_ui.py tests/test_trend_direction_ui.py`를 실행한다. 이 단계의 브라우저 대상은 기존 공통 자산이 적용되는 `/dashboard2`다. `3 전기강판 3DNL`과 `56`을 실제 summary 렌더링 경로로 넣고 1280/1440/1920에서 한 줄인 라벨끼리·값끼리 Range top/bottom 편차 <=1px인지 확인한다. 긴 여러 줄 값은 첫 줄 top 편차 <=1px와 글자 잘림 없음으로 확인하며 전체 높이가 짧은 값과 같도록 강제하지 않는다. 한글 글꼴 fallback도 확인한다.
- [ ] **Step 5:** 페이지/박스별 스타일 숫자를 복제하지 않았는지 검토한다. 허용 시 명시된 파일만 `refactor: unify CMS semantic typography and chart fonts`로 커밋한다.

### Task 3: 공통 셸과 명시적 사이드바

**Files:**
- Create: `app/presentation.py`, `app/static/partials/cms-sidebar.html`, `tests/test_cms_presentation.py`, `tests/ui/test_cms_shell.py`.
- Modify: `app/main.py`, `app/static/cms-operations.css`, `app/static/dashboard2-shell.css`, `app/static/modules/core/cms-operations.js`, `tests/test_operations_ui.py`.
- Modify: `app/static/equipment-status2.html`, `app/static/kpi-dashboard-concept.html`, `app/static/index.html`, `app/static/history.html`, `app/static/main-workspace.html`.

**Interfaces:** `render_operations_page(page: str, *, active_page: str, body_classes: tuple[str, ...] = ()) -> str`는 명시적 `<!-- cms:assets -->`, `<!-- cms:sidebar -->`, `<!-- cms:scripts -->`, `<!-- cms:body-attributes -->` 슬롯만 조립한다. 누락·중복 슬롯은 `ValueError`로 처리한다. 새 fragment에만 표준 라이브러리 `string.Template`를 사용하고 동적 속성은 `html.escape`한다. 기존 HTML/CSS 조각을 검색해 바꾸는 방식은 제거한다.

JS는 `initCmsShell(root: Document = document) -> void`, `setSidebarExpanded(expanded: boolean) -> void`를 export한다. 상태는 `body.dataset.cmsNav = "expanded" | "collapsed"`; 버튼은 `aria-controls="cms-sidebar"`, `aria-expanded`와 명확한 접근성 이름을 가진다. 실제 상태 전환 후 `cms:layout-change` 이벤트를 한 번 발행한다.

- [ ] **Step 1:** `test_shared_shell_assets_once`에 CSS/JS/사이드바가 각각 한 번이라는 assertion과 누락 슬롯 예외를 작성한다. `test_hover_and_focus_do_not_resize_content`에는 hover/Tab 전후 `abs(after.width - before.width) <= 1`을, `test_sidebar_keyboard_and_persistence`에는 클릭/Enter/Space, 새 페이지 이동, 저장소 예외 시에도 토글 가능함을 검증한다. `test_sidebar_resize_keeps_plot_visible`은 클릭 전환 뒤 Plotly 폭과 부모 폭의 차이 <=1px, trace 존재, 추가 dashboard API 요청 0건을 검증한다.
- [ ] **Step 2:** `uv run pytest -q tests/test_cms_presentation.py`와 `uv run pytest -q -m ui tests/ui/test_cms_shell.py`로 실패를 확인한다.
- [ ] **Step 3:** 공통 슬롯과 fragment를 도입한다. 같은 HTML을 공유하는 별칭(`/dashboard`, `/history`, `/dashboard_ui2`, `/main_sv`)도 함께 조립하여 미처리 슬롯을 노출하지 않는다. `main.py`의 해당 스타일 주입과 기존 셸의 hover/focus 폭 변경을 제거하고 CSS는 데이터 상태만 참조하게 한다. 현재 활성 메뉴와 날짜 갱신을 보존하며 아이콘은 기존 자산을 재사용한다.
- [ ] **Step 4:** `cms:layout-change` 후 기존 Plotly 노드만 `Plotly.Plots.resize`하고 새 데이터 요청이나 중복 이벤트 등록을 만들지 않는다. 기존 상세 스크롤 복원 처리는 공통 JS의 상세 전용 분기로 이동해 동작을 보존한다. 단위/브라우저 테스트와 `uv run pytest -q tests/test_operations_ui.py tests/test_app.py -k "presentation or workspace or page_is_served or styles_are_not_nested"`를 실행한다.
- [ ] **Step 5:** 헤더 높이·본문 여백이 라우트마다 같고 호버 시 차트와 표가 움직이지 않는지 캡처한다. 의도적으로 늘어난 공통 적용 범위만 기존 테스트에서 갱신한다. 허용 시 `refactor: centralize CMS shell and explicit sidebar state`로 커밋한다.

### Task 4: 대표 화면인 설비 알람 현황 완성

**Files:**
- Create: `app/static/equipment-status2.css`, `tests/ui/test_cms_equipment_status.py`.
- Modify: `app/main.py`, `app/static/equipment-status2.html`, `app/static/equipment-status.css`, `app/static/modules/equipment-status/controller.js`, `app/static/modules/equipment-status/equipment-status2.js`.

**Interfaces:** 기존 필터 ID `equipment-status-type`, `equipment-status-name`과 controller의 조회·트리 데이터 계약을 유지한다. 결과 수에 `data-cms-result-count`, 선택 트리/목록에 `aria-selected` 또는 해당 위젯에 맞는 동등한 접근성 상태를 부여한다. 데이터 계산은 기존 controller가 계속 소유한다.

- [ ] **Step 1:** `test_filters_tree_and_count_stay_in_sync`에 필터 결과 행 수와 표시 건수가 같고 트리/목록 선택이 일치함을 검증한다. `test_alarm_loading_empty_error_and_long_names`는 지연 응답 중 조회 상태, 결과 0건, 실패 표시, 긴 한글 이름에서 잘림이 없고 폰트 크기가 14px로 유지됨을 검증한다. 실제 선택 가능한 데이터는 baseline에서 기록한 항목을 사용한다.
- [ ] **Step 2:** `uv run pytest -q -m ui tests/ui/test_cms_equipment_status.py`를 실행해 새 상태/기하 계약의 실패를 확인한다.
- [ ] **Step 3:** 서버가 추가하던 필터·notice 마크업을 HTML 원본에 둔다. 알람 HTML과 `main.py` 및 `equipment-status2.js`의 정적 스타일 문자열을 `equipment-status2.css`로 이관하고 기존 원본을 제거한다. 데이터 기반 막대 길이와 툴팁 좌표 같은 동적 값만 JS에 남긴다.
- [ ] **Step 4:** 필터, 결과 수, 트리, 리스트, 상태 배지를 공통 토큰에 맞춘다. 표 행과 선택 상태를 정리하되 `equipment-status-demo/` 입력과 기존 상세 링크를 바꾸지 않는다. Step 2와 `uv run pytest -q tests/test_app.py -k "equipment_status or styles_are_not_nested"`를 실행한다.
- [ ] **Step 5:** 세 데스크톱 크기에서 대표 화면 전후를 검토해 확정된 시각 기준을 baseline 문서에 기록한다. 조정 시 Task 2 토큰과 대응 테스트를 함께 바꾼다. 허용 시 `feat: align equipment alarm screen with shared CMS design`로 커밋한다.

### Task 5: 설비 상세의 정보 위계와 기능 보존

**Files:**
- Create: `tests/ui/test_cms_detail.py`.
- Modify: `app/static/index.html`, `app/static/styles.css`, `app/static/dashboard2-shell.css`, `app/static/modules/summary/summary.js`, `app/static/modules/dashboard/controller.js`.
- Read: `app/static/modules/api/dashboard.js`, `app/static/modules/fft/related-history.js`, `app/static/modules/report/chart-capture.js`, `tests/test_report_ui.py`, `tests/test_ppt_frontend.py`.

**Interfaces:** `populateSummary(data)`와 `fetchDashboard(datasetId, until, start)`, `fetchFftRecord(datasetId, recordId, until, start)`를 그대로 유지한다. `equipment-title`, `plant-name`, `sensor-number`, `trend-chart`, `fft-chart` 및 기존 확대/분석/보고서 버튼 ID와 컨트롤러 바인딩을 보존한다. 메타데이터 측정에는 Task 1 `text_metrics`를 사용한다.

- [ ] **Step 1:** `test_metadata_alignment_and_long_equipment_name`는 공장/센서 라벨 및 값의 역할별 크기와 줄 높이, 동일 행의 첫 줄 위치 편차 <=1px를 검증한다. 긴 값은 여러 줄 높이를 허용하되 넘치지 않고 14px를 유지해야 한다. `test_historical_detail_keeps_cutoff_and_fft`는 기존 유효 과거 이력 URL로 진입해 `dataset`, `until`, `start`와 FFT 요청의 record ID가 유지됨을 검증한다.
- [ ] **Step 2:** `test_detail_actions_and_states`에는 Trend/FFT 렌더링, FFT 변경, 확대/닫기, AI 재분석, PPT 다운로드, 이메일 미리보기/복사 성공·권한 거절, 채팅과 W/O를 작성한다. AI 지연·오류와 긴 요약을 주입하고 핵심 액션이 가려지지 않는지 검증한다. `uv run pytest -q -m ui tests/ui/test_cms_detail.py`로 실패를 확인한다.
- [ ] **Step 3:** 설비명·메타데이터·액션을 상단에 정렬하고 차트에 안정적인 grid track/min-height를 준다. AI 요약, 상세 근거와 상태 판정을 구분하되 기존에 노출하지 않던 별도 진단 기능을 새로 만들지 않는다. 텍스트는 줄바꿈하고 수치·단위는 임의 생략하지 않는다. 관련 이력 이동과 선택 변경 시 날짜 초기화 등 기존 동작을 유지한다.
- [ ] **Step 4:** Step 2와 `uv run pytest -q tests/test_fft_layout_ui.py tests/test_report_ui.py tests/test_ppt_frontend.py tests/test_work_order.py tests/test_chat_analysis_tools.py`를 실행한다. `uv run pytest -q tests/test_app.py -k "dashboard_until or dashboard_chat"`도 통과시킨다. 출력은 테스트 fixture로 검증하며 실제 AI 과금이나 이메일 전송은 하지 않는다.
- [ ] **Step 5:** 화면용 차트 글자와 보고서 캡처용 글자를 각각 확인한다. Clipboard 미지원은 기존 미리보기와 오류 안내를 보존한다. 허용 시 `feat: unify equipment detail hierarchy and metadata alignment`로 커밋한다.

### Task 6: 운영 대시보드·진단 이력·중앙 및 현장 관제

**Files:**
- Create: `app/static/dashboard-chart-panels.css`, `app/static/kpi-dashboard-concept.css`, `tests/ui/test_cms_history.py`, `tests/ui/test_cms_control.py`.
- Modify: `app/static/kpi-dashboard-concept.html`, `app/static/modules/main/kpi-concept.js`, `app/static/modules/main/dashboard-chart-panels.js`.
- Modify: `app/static/history.html`, `app/static/history.css`, `app/static/modules/history/controller.js`.
- Modify: `app/static/main-workspace.html`, `app/static/main-workspace.css`, `app/static/modules/main/workspace.js`, `app/static/main-control.html`, `app/static/main-control.css`, `app/static/modules/main/control-dashboard.js`.

**Interfaces:** 이력의 검색/행 상세/그래프 링크와 관제의 `scope-select`, `process-select`, `risk-map`, `work-rows`, `recent-activity`, `trend-bars`를 보존한다. 차트 패널 정적 스타일은 새 CSS가 소유하고 tooltip 위치와 데이터 기반 크기는 JS가 소유한다. 새로운 정렬 로직이나 진단 규칙을 만들지 않고 기존 위험도·우선순위 값을 표시한다.

- [ ] **Step 1:** `test_history_filters_long_text_dates_and_detail_context`에 검색 결과 수, 긴 진단 내용 접근 가능성, 날짜·상태 표시와 실제 `until` 포함 상세 링크가 보존됨을 검증한다. `test_control_scope_process_reset_priority_and_states`에는 공장 변경 시 공정 초기화, 위험도별 기존 우선순위, 빈 결과·API 오류·loading을 검증한다. `test_dashboard_reading_order`에는 주요 지표→위험 설비→추세→조치 대상의 DOM 순서를 검증한다.
- [ ] **Step 2:** `uv run pytest -q -m ui tests/ui/test_cms_history.py tests/ui/test_cms_control.py`로 의도한 화면 계약의 실패를 확인한다.
- [ ] **Step 3:** 대시보드 인라인 CSS는 페이지 전용 CSS `app/static/kpi-dashboard-concept.css`로 추출하고 `dashboard-chart-panels.js`의 반복 `styles()` 및 tooltip CSS 삽입은 공통 차트 CSS로 옮긴다. 이력 필터·표·본문과 관제의 패널 위계에 대표 화면 기준을 적용한다. 큰 히어로·중첩 카드·장식 문구는 정보 중심 배치로 대체한다.
- [ ] **Step 4:** Step 2와 `uv run pytest -q tests/test_operations_ui.py tests/test_history.py tests/test_report_ui.py`를 실행한다. 중앙과 현장의 데이터 범위·용어·기존 링크 목적지 차이를 그대로 유지하고 공유 CSS로 덮어써 의미를 합치지 않는다. 새 링크 날짜 정책을 추측하지 않으며 기존 동작과 결함은 baseline에 구분한다.
- [ ] **Step 5:** 중앙과 현장, 이력의 일반/빈 결과/긴 내용 상태를 각기 캡처하고 공통 헤더·컨트롤·배지의 computed style을 비교한다. 허용 시 `feat: align CMS overview history and control screens`로 커밋한다.

### Task 7: 유지되는 실험·구버전 화면까지 확장

**Files:**
- Create: `tests/ui/test_cms_variants.py`.
- Modify: `app/main.py`, `tests/test_operations_ui.py`.
- Modify: `app/static/main.html`, `app/static/main.css`, `app/static/dashboard-ui1-kpi.html`, `app/static/dashboard-ui1-kpi.css`.
- Modify: `app/static/design-lab.html`, `app/static/design-lab.css`, `app/static/dashboard-ui5.html`, `app/static/dashboard-ui5.css`, `app/static/dashboard-ui1-canvas.html`, `app/static/dashboard-ui1-canvas.css`.
- Modify: `app/static/history2.html`, `app/static/history2.css`, `app/static/dashboard-ui1-fresh.html`, `app/static/dashboard-ui1-fresh.css`, `app/static/dashboard-lab.html`, `app/static/dashboard-lab.css`.

**Interfaces:** Route Inventory 전체를 테스트 매개변수로 재사용한다. 유지 화면의 고유 콘텐츠·데모 구분·기존 URL은 보존하고 공통 토큰·타이포그래피·컨트롤·명시적 사이드바 상태만 공유한다. 서버 라우트는 Task 3 조립기를 사용하고 직접 정적 파일은 완성된 HTML 및 공통 자산 참조를 사용한다.

- [ ] **Step 1:** `test_retained_variants_share_roles_without_losing_content`에 각 URL 200, 기존 고유 콘텐츠 존재, 1개 공통 자산 집합, 미처리 슬롯 없음, 역할별 글자 규칙과 hover 폭 불변을 검증한다. Canvas 화면은 canvas 크기 >0이고 샘플 픽셀이 균일한 단색이 아닌지도 검사한다.
- [ ] **Step 2:** `uv run pytest -q -m ui tests/ui/test_cms_variants.py`로 현재 미통일 화면의 실패를 확인한다.
- [ ] **Step 3:** Task 1 사용 여부 기록에 따라 유지되는 화면에 공통 규칙을 적용한다. 미확인 화면은 기본적으로 유지한다. 같은 템플릿을 공유하는 변형은 데이터/역할 분기만 남기고 스타일 문자열 치환을 없앤다. `history2.html`을 `/history2` 라우트의 실제 소유 파일로 오인하지 않는다.
- [ ] **Step 4:** Step 2 및 `uv run pytest -q tests/test_operations_ui.py tests/test_demo_presentation.py`를 실행한다. 비교 화면에도 공통 디자인이 생긴다는 의도만 테스트에 반영하며 실제/데모 응답 구분이나 정적 데이터 연결은 변경하지 않는다.
- [ ] **Step 5:** URL, 사용 여부 근거, 적용 여부를 baseline 문서에 확정한다. 임의 삭제가 없고 직접 정적 접근에서도 자산 경로가 유효한지 캡처한다. 허용 시 `refactor: share CMS design across retained UI variants`로 커밋한다.

### Task 8: 스타일 소유권 마무리와 독립 통합 검증

**Files:**
- Create: `docs/validation/cms-design-acceptance.md`.
- Modify: `tests/test_cms_presentation.py`, `tests/ui/test_cms_typography.py`, `docs/current-operation.md`, `README.md`.
- Modify: Tasks 2-7에서 이관한 CSS/HTML/JS 원본의 잔여 중복 선언만 제거한다.

**Interfaces:** 앞선 테스트와 화면 목록을 재사용한다. 새로운 진단/조회 인터페이스는 만들지 않는다. acceptance 문서는 URL·viewport·상태·스크린샷 경로·검증 결과·검증자·남은 문제·실행 서버 URL을 기록한다.

- [ ] **Step 1:** `test_static_presentation_has_single_owner`에 `main.py` 화면 경로의 `<style>` 생성 없음, 이관한 JS의 `style.textContent`/`createElement("style")` 정적 CSS 삽입 없음, 공통 자산 중복 없음, sidebar hover/focus에 width/grid/margin 변경 없음이라는 assertion을 추가한다. 동적 tooltip 좌표/막대 길이와 보고서 출력용 스타일은 금지 대상으로 혼동하지 않는다.
- [ ] **Step 2:** `uv run pytest -q tests/test_cms_presentation.py`로 잔여 중복을 드러낸 뒤 같은 소유권 경계 안에서 정리한다. `uv run pytest -q`와 `uv run pytest -q -m ui tests/ui`를 실행해 PASS를 확인한다. Node 미설치로 skip된 기능 테스트를 통과로 보고하지 말고 검증 환경을 갖춘 후 재실행한다.
- [ ] **Step 3:** 사용자 제시 요구사항마다 Task 번호·테스트·시각 증거를 acceptance 문서에 연결한다. 마지막 수정 이후 모든 대상 화면을 세 viewport에서 다시 열고 제목·라벨·값·표·필터·상태 배지·차트 글자와 잘림/겹침을 재확인한다. 대표 화면의 125% 브라우저 확대도 확인하며 모바일 점검 완료를 주장하지 않는다.
- [ ] **Step 4:** 구현자와 다른 검증 담당자가 문서·diff·실제 화면을 검토한다. 정확한 메타데이터 예시, hover/Tab 폭 불변, 이력 조회 시점, FFT·확대·AI·PPT·이메일·채팅·W/O를 독립 재현한다. 차단 문제 수정 후 영향받는 좁은 테스트부터 다시 실행하고 최종 브라우저 캡처를 갱신한다.
- [ ] **Step 5:** 운영/비교 화면 목록, 공통 CSS 소유권과 검증 명령을 문서화한다. 실행 서버를 종료하지 않고 URL·포트와 검증 한계를 사용자에게 전달한다. 허용 시 검증 문서와 잔여 정리를 `test: verify unified CMS design and preserved workflows`로 커밋한다.

## Verification And Handoff

- 구현 순서는 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8이다. Task 4가 다른 화면의 시각 기준이며 먼저 확정한다.
- 기능 유지, 공유 파일과 상태 경계가 중요하므로 실행 시 task별 구현자/검토자를 분리하는 subagent-driven 방식을 권장한다. 현재 요청은 계획만이므로 실행 방법 선택이나 구현을 자동으로 시작하지 않는다.
- 시각 비교는 baseline에서 확인된 실제 데이터와 테스트 fixture를 사용한다. 스크린샷 저장 위치는 `.cache/cms-ui/`; 비밀값이나 `.env`를 문서·이미지·테스트에 포함하지 않는다.
- 기존 테스트 실패와 기존의 조회 시점 예외는 문서화한다. UI 변경과 무관한 사업 로직 수정이나 무조건적인 snapshot 갱신으로 숨기지 않는다.
- 구현자가 실행 전 확인할 사항: 실험 화면의 외부 사용 여부, 기존 글꼴 실제 설치 여부, 가능한 개발 서버 포트. 사용 여부 미확인은 삭제 사유가 아니며, 폰트 부재는 공통 fallback으로 처리한다.

## Plan Self-Review

- 범위: 전체 화면 점검(Task 1), 공통 기반(Task 2/3), 대표 화면(Task 4), 나머지 확장(Task 5/6/7), 소유권 정리(Task 3/4/6/8), 독립 통합 검증(Task 8)에 모두 대응한다.
- 타이포그래피: 역할별 크기, 한글/숫자 높이, 라벨/값 정렬, 여백, 긴 이름, 차트·동적 영역 및 실제 브라우저 검증을 포함한다.
- 계약: `dataset`/`until`/`start`, FFT 선택, 차트 확대, AI, PPT, 이메일, 채팅, W/O 및 데모 입력 보존을 명시했다. 확인되지 않은 `as_of` 별칭을 새로 만들지 않는다.
- 경계: 소유권별 파일 책임과 호출 계약, 실패/성공 확인 명령을 지정했다. 보고서용 글자 크기와 데이터 기반 동적 위치는 예외로 분리했다.
- 이 문서는 계획 산출물이다. 위 체크박스는 구현 완료를 뜻하지 않으며 테스트·설치·서버 실행도 아직 수행하지 않았다.