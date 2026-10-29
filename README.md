# CMS AI PoC

CSV 기반 설비 진동 데이터(Trend·FFT)와 진단 이력을 조회하고, AI 종합 분석·챗봇·진단 보고서를 제공하는 FastAPI PoC입니다.

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