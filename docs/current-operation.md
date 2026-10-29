# CMS AI PoC 현재 동작 정리

> 기준일: 2026-10-12. 현재 체크아웃된 저장소의 구현을 기준으로 작성했다. 진단 규칙의 현장 타당성이나 AI 응답의 정확도를 보증하는 문서는 아니다.

## 1. 목적과 구성

CSV 기반 설비 상태감시(CMS) 데이터를 조회하고, 설비 현황·Trend·FFT·시간 파형·과거 진단 이력을 연결하는 웹 PoC다. 서버의 규칙 기반 분석에 OpenAI를 이용한 설비 종합 분석과 질의응답을 더하고, 진단 PPTX와 이메일 초안을 생성한다. 운영 화면에는 실제 CSV 집계와 데모 지표가 함께 있으므로 구분해서 해석해야 한다.

```text
data/ CSV + equipment_metadata.json + 베어링 마스터
                         │
                         ▼
FastAPI (app/main.py)
├─ data_loader/: CSV 로드, 메타데이터, 측정 배열 해석
├─ analysis/ + services/: 공통 진단 규칙, 기간 조회, 이력 연결
├─ equipment_analysis.py + equipment_evidence.py: 설비 단위 AI 근거
├─ ai_analysis.py + chat.py + agent_tools.py: AI 분석·채팅·도구 실행
├─ reporting/: PPTX·이메일 초안 생성, PPT 렌더링 검증
└─ static/: HTML, JavaScript 모듈, Plotly 그래프
                         │
                         ▼
운영 대시보드 → 설비 알람 현황 → 설비 상세 → 진단 이력
                                     ├─ AI 종합 분석·채팅
                                     ├─ 진단결과 PPT
                                     └─ 이메일 본문 복사
```

Python 3.11 이상과 `uv`를 사용한다. 실행 방법은 다음과 같다.

```bash
uv sync
uv run uvicorn app.main:app --reload
```

기본 주소는 <http://127.0.0.1:8000>이며 루트는 설비 알람 현황을 표시한다. API 문서는 `/docs`에서 확인할 수 있다.

## 2. 입력 데이터와 갱신 방식

| 입력 | 내용과 사용처 |
| --- | --- |
| `data/*Trend*.csv` | `DataDate`, `VelAve`, `AccAllAve` 등을 읽어 Trend, 현재값, 상승 경향, Level 분석 구성 |
| `data/*FFT*.csv` | 측정일시·모드·주파수 범위·라인 수·`ResultData` 등으로 FFT 및 시간 파형 구성 |
| `data/*WarningStatus*.csv` | 속도 주의·위험 설정값과 발생 시각. 파일이 없으면 동일 센서의 유일하게 일치하는 파일을 재사용할 수 있음 |
| `data/CMS history.csv` | 진단일·공정·설비·결함·현상·분석·조치·피드백 등 과거 이력 |
| `app/equipment_metadata.json` | 설비 코드별 RPM, 베어링 제조사·형번 등 보강 정보 |
| `data/0. Bearing_Fault_Frequency_Master_File.txt` | BPFO/BPFI/BSF/FTF 결함계수 |
| `equipment-status-demo/*.js` | 설비 분류 트리와 센서 목록을 위한 데모 데이터 |

파일명 앞 숫자를 데이터셋 ID로 사용하고 같은 ID의 파일을 묶는다. 서버 시작 시 설비 데이터와 AI/연관 이력용 과거 이력을 메모리에 보관한다. 일부 입력을 읽지 못하면 가능한 다른 데이터를 제공하고 데이터셋의 `meta.errors`에 오류를 남긴다.

FFT `ResultData`는 little-endian float32 배열로 해석하며 `MeasureLineNum`과 배열 길이를 확인한다. 알려진 `MeasureFreq`는 주파수 범위를 라인 수로 나누어 Hz 축을 만들고, 알 수 없는 코드는 bin 축으로 표시해 주파수 기반 진단을 제한한다. 시간 파형은 유효한 샘플링 주파수가 있으면 초 단위 축을, 그렇지 않으면 샘플 번호를 사용한다.

설비 CSV 변경은 서버 재시작이 필요하다. 예외적으로 `GET /api/history`는 요청마다 이력 CSV를 다시 읽는다. 따라서 파일 수정 후 이력 화면과 서버 시작 시 저장된 AI/연관 이력의 내용이 달라질 수 있다.

## 3. 화면과 사용자 흐름

### 주요 운영 경로

| 경로 | 현재 역할 |
| --- | --- |
| `/dashboard_ui6` | 운영 대시보드. 설비 상태 요약, 주의 이상 설비의 진단 이력, 공정별 집계 및 데모 운영 지표 |
| `/`, `/equipment-status2` | 설비 알람 현황. 분류 트리·검색·필터, 공장별 상태 차트, 실제 데이터 연결 센서의 상세 진입 |
| `/dashboard2?dataset=<ID>` | 공통 운영 사이드바가 있는 설비 상세 대시보드 |
| `/history2` | 공통 운영 사이드바가 있는 진단 이력 |
| `/main_ct` | 중앙 관제. 공장별 위험 현황·점검 대상·최근 진단 활동 |
| `/dashboard`, `/history` | 기존 상세 대시보드와 이력 화면. 같은 분석/이력 API 사용 |

`/main`, `/main_sv`, `/main_ct1`~`/main_ct3`, `/main_sv1`~`/main_sv3`, `/dashboard_ui1`, `/dashboard_ui2`, `/dashboard_ui3`, `/dashboard_ui4`, `/dashboard_ui5`, `/dashboard_ui1_canvas`도 비교용 화면으로 남아 있다. 모두 별개의 운영 기능이 완성되었다는 의미는 아니다. 운영 화면에는 공통 색상·타이포그래피·사이드바 표시를 적용하며, 설정은 중앙 관제로 연결되고 도움말 등 일부 링크는 자리표시자다.

### 설비 현황과 운영 대시보드

- 설비 트리와 센서 목록은 JavaScript 분류 데이터에 `/api/datasets`의 설비 요약을 연결한다. 공장·공정·설비 종류·상태·설비명으로 필터링하고 연결된 센서를 선택하면 `/dashboard2`로 이동한다.
- 연결된 센서 상태는 주로 서버의 Trend 상승 경향을 사용한다. 데이터가 연결되지 않은 목록 항목은 정상으로 표시하는 데모 동작이 있다.
- `3전기강판|3DNL|V056`은 목록에서 `심각`을 강제로 표시한다. 서버 요약이나 다른 화면의 집계와 같지 않을 수 있다. 이전 문서의 V191 강제 심각 표시는 현재 목록 코드에는 없다.
- `/dashboard_ui6`의 요약 카드를 클릭하거나 키보드로 활성화하면 주의 이상 설비와 연결된 실제 진단 이력을 보여 준다. 그래프 링크에는 진단일을 `until`로 전달한다.
- 설비 수·상태 비율·공정별 이력 건수 등은 실제 API 집계다. 다만 “알람 건수” 일부는 과거 진단 이력 건수를 사용하며 별도 알람 이벤트 저장소를 조회하지 않는다.
- 생산량·목표량, 알람 활성율 78%·조치 연계율 64%·조치율 91%, 12개월 Trend View 등은 고정값이다. 목표 건수·장애 유형 A/B/C/D도 이력 건수를 가공한 데모 수치이며 실제 생산·작업지시·조치 실적과 연결되지 않는다.

### 설비 상세

1. URL의 `dataset`이 유효하면 해당 설비, 아니면 목록의 첫 설비를 선택한다.
2. 상세 API로 현재값, Trend, Level, FFT 목록과 기본 기록, 최근 7일 FFT 판정을 가져온다.
3. Trend는 최신 추세 측정일 기준 최근 90일로 표시한다. 속도·가속도 지표와 설정 임계값을 확인하고 그래프를 확대할 수 있다.
4. FFT 기록을 바꾸면 스펙트럼·시간 파형·규칙 진단·연관 이력을 갱신하며 조회한 기록은 브라우저 메모리에 캐시한다. 기본 FFT는 최신 ENV/속도 기록을 우선하며 둘 다 없으면 최신 기록을 선택한다. 과거 경보 여부는 기본 선택을 결정하지 않는다.
5. 기록 목록은 이상 기록 중심이며 측정 조건 등의 필터를 제공한다. 경보 채취 종류(3·4), 최대 진폭 0.5 초과, 또는 속도 FFT의 원인 진단 완료 중 하나에 해당하면 이상 목록 대상으로 분류한다.
6. 설비를 열면 AI 종합 분석을 자동 요청한다. FFT 기록이나 베어링 결함 선택을 바꿔도 설비 AI 결과는 유지한다. `다시 분석`으로 갱신한다.
7. 그래프 아래에 AI 추세·주파수 분석, 실제 FFT 비교 기간과 대표 기록을 표시한다. 보고서는 AI가 지정한 첫 대표 FFT 기록을 기준으로 준비한다.

`start=YYYY-MM-DD`, `until=YYYY-MM-DD`가 있으면 상세 데이터와 FFT 조회를 해당 날짜 범위로 제한한다. 종료일은 당일 23:59:59까지 포함한다. 설비 선택을 바꾸면 두 날짜 조건을 지운다. 설비 AI와 보고서 API는 `until`을 받지만 `start`는 분석 범위로 사용하지 않으므로 화면의 시작일 제한과 AI 범위가 동일하다고 해석하면 안 된다.

### 진단 이력과 연관 이력

이력 화면은 공정·키워드 검색과 행 확장으로 현상·분석·결과·피드백·측정 정보를 제공한다. 연결된 데이터셋이 있으면 진단일 기준 상세 화면으로 이동한다.

화면의 연관 이력은 선택 FFT의 표준화된 결함 유형과 일치하는 이력을 표시하며 `until`이 있으면 그 날짜까지 제한한다. 다른 설비의 같은 결함도 포함할 수 있다. AI 이력은 더 좁게 **동일 설비이면서 동일 결함이고 FFT 측정일보다 앞선 사례**를 최대 5건 선택한다. 화면과 AI의 이력 조회 기준이 다르다.

## 4. 규칙 기반 분석

규칙은 `app/analysis/`에 모으며 기준 버전은 `cms-poc-v1`이다. 화면과 AI 도구는 공통 분석 서비스의 결정론적 결과를 조회한다.

### Trend 상승 경향과 속도 Level

상승 경향은 VelAve 표본 143개 이상에서 판단한다. 전체 평균보다 3 표준편차 이상 낮은 값을 보간하고, 72개 표본 이동평균을 만든 뒤 마지막 72개 이동평균에 선형회귀를 적용한다. 기울기가 `1 / (24 × 14)`보다 크면 `caution`(상승 경향), 아니면 `normal`이다. 표본이 부족하면 `unknown`이다.

기울기는 실제 경과 시간이 아닌 표본 인덱스로 계산하며 시간당 표본을 전제한다. 불규칙 측정에서도 실제 시간 간격을 자동 보정하는 방식은 아니다. 이 판정 창은 AI의 최근 90일 비교와 구분된다.

Level은 최신 측정일에서 3개월을 뺀 시점부터의 VelAve를 사용한다. IQR의 1.5배 범위 밖 값을 제외한 평균의 2배를 권장 주의값, 4배를 권장 위험값으로 계산하며 설정값과의 차이를 표시한다. Level의 3개월은 달력 월을 빼서 구하므로 Trend의 90일과 정확히 같지는 않다.

### FFT 피크와 원인 후보

양의 주파수 중 진폭 상위 10개 후보를 고르고 가까운 주파수를 묶어 기준 이상인 최대 5개 피크 그룹을 표시한다.

| 모드 | 단위 | 주요 피크 기준 | 그룹화/진단 허용오차 |
| --- | --- | --- | --- |
| 속도 (`3`) | mm/s | 0.5 이상 | ±1 Hz |
| 가속도 ALL (`0`) | g | 0.2 이상 | ±5 Hz |
| 가속도 ENV (`2`) | g | 0.2 이상 | ±5 Hz |

속도는 `1X = RPM / 60`과 2X·3X 주변 피크를 비교한다. 1X가 0.5 mm/s 미만이면 판정을 보류한다. `2X/1X > 0.4` 또는 `3X/1X > 0.3`이면 Misalignment 후보, `2X/1X < 0.2`이면서 `3X/1X < 0.1`이면 Unbalance 후보, 나머지는 복합/불확실이다.

가속도는 RPM과 베어링 계수로 BPFO/BPFI/BSF/FTF의 1X·2X·3X 및 축 회전수 사이드밴드를 찾는다. 고조파 중 하나라도 0.5 g 이상이면 이상 후보로 보고 여러 후보면 고조파·사이드밴드 점수, 최대 피크, 결함 순서로 대표를 고른다. 후보가 없으면 BPFO를 기본 선택으로 두고 “베어링 결함 Peak 없음”을 표시한다.

RPM·베어링 정보·유효 계수·Hz 축 등 필수 근거가 없으면 해당 판정을 제한한다. ENV도 베어링 정보가 없어도 원본 스펙트럼은 표시한다.

### 진폭 등급과 최근 7일 FFT 상태

원인 후보 규칙과 별도로 고조파의 실제 진폭을 다음 기준으로 등급화한다.

| 단위 | 양호 | 초기 결함 | 심각 | 정지 / 베어링 교체 |
| --- | --- | --- | --- | --- |
| mm/s | ≤4 | >4~≤10 | >10~≤20 | >20: 정지 |
| g | ≤0.2 | >0.2~<1 | 해당 없음 | ≥1: 베어링 교체 |

속도는 축 회전수 1X·2X·3X, 가속도 ALL/ENV는 각 베어링 결함의 1X·2X·3X를 사용한다. 미검출 고조파는 0이나 양호로 대체하지 않고 판정 제한으로 남긴다. 가속도 원인 후보 임계값 0.5 g와 진폭 등급의 초기 결함 경계 0.2 g는 서로 다른 기준이다.

현재 주파수 상태는 조회 범위 내 최신 FFT 측정일과 이전 6일을 집계하며 선택 FFT 변경과 독립적이다. 초기 결함 이상에서 원인별 발생 횟수, 누적 점수, 최고 등급, 최근 발생 시각, 원인 코드 순으로 대표 원인을 고른다. 초기 결함은 1점, 심각은 2점, 정지·베어링 교체는 3점이다. 한 가속도 기록의 여러 결함은 각각 집계한다.

표시 등급은 대표 원인의 주간 최고 등급이다. 최고 진폭의 원본 기록·측정일·모드·고조파·주파수·단위도 제공한다. 유효 판정 기록에 초기 결함 이상이 없으면 양호, 근거가 없으면 판정 불가다. 응답의 `fftWeeklyDiagnosis`에 집계와 제한사항을 포함한다. 진폭 기반 선별이며 물리적 결함을 확정하지 않는다.

설비 요약 상태는 여전히 Trend 중심이다. 주간 FFT 등급이나 AI 위험 수준을 통합해 전체 상태를 자동 변경하지 않는다.

## 5. 설비 단위 AI 종합 분석

루트 `.env` 또는 운영 환경변수로 설정하며 운영 환경변수가 우선한다.

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=20
AI_ANALYSIS_CACHE_TTL_SECONDS=86400
```

키가 없으면 AI 기능은 오류 안내를 반환하고 CSV 조회와 규칙 분석은 계속 사용할 수 있다. 키는 브라우저에 전달하지 않는다.

### 분석 근거와 도구

분석 단위는 설비다. 첫 요청에 다음 근거를 서버에서 미리 압축해 제공한다.

- 최신 추세 측정일 기준 최근 90일 통계·임계값, 월평균·표본 수·관측 기간·이전 월평균 대비 변화량
- 조회 종료일 내 전체 FFT 이력을 모드·단위·측정점·RPM·대역·분해능별로 나눈 요약
- 월별 성분의 최초·최신·최소·최대 관측값과 원본 기록 ID·측정일, 이상 기록 수·최초 이상 관측일
- 그룹마다 최초·최신·최초 이상·주요 진폭 최대 기록에서 중복을 제거한 최대 6개 대표 기록과 관련 이력
- 최근 7일 FFT 집계, 서버의 선정·등급 설명 근거, 해석하지 못한 기록 등 제한사항

FFT 월별 요약은 월평균이 아닌 실제 관측값이다. 서로 다른 단위나 조건을 하나의 추세로 비교하지 않고 최초 이상 관측일을 정확한 고장 시작일로 단정하지 않는다. 원본 FFT 배열은 AI에 보내지 않는다.

충분한 근거가 있으면 추가 도구 없이 한 번의 AI 요청으로 분석한다. 필요한 경우에만 `get_fft_evidence`, `get_fft_history_evidence`, `get_related_history`를 사용하며 최대 2회 도구 응답 단계·총 4개 호출로 제한한다. 이력 조회는 페이지당 최대 50개이고 같은 필터로 다음 페이지를 조회한다.

### 응답 검증과 오류

응답에는 종합 요약·위험 수준·추세/주파수 요약·상세 소견·원인 후보·반증·우선 조치·실제 FFT 비교 기간·대표 기록 ID를 포함한다. 종합 요약은 변화·근거가 있는 원인 가능성·점검을 연결하며 1X 우세만으로 축정렬 불량을 단정하지 않도록 한다.

서버는 JSON 구조와 수치·단위·기간·원인·대표 기록의 근거를 검사한다. 최종 응답 잘림·빈 응답·구조 또는 근거 오류는 이미 제공한 근거로 최대 두 번 보정하며 보정 단계에서는 도구를 다시 호출하지 않는다. 현재 설비 분석의 최초 출력 한도는 **3,200토큰**, 보정은 **4,800토큰**이다. 전체 시간은 응답당 제한시간의 최대 10배다. 인증·서비스 장애·요청 제한·시간 초과는 이 보정 대상이 아니다.

주파수 요약은 최대 1,200자로 주간 횟수·점수·선정 순서·최고 진폭·등급 기준·제한을 설명하도록 검증한다. 응답 최상위 `fftSeverityAssessments`는 AI 대표 기록의 고조파별 서버 계산 등급이며 화면의 “FFT 기준 판정”에도 표시한다.

로그는 `request_id`, 모델, 설비, 시도, 실패 단계, 검증 규칙과 허용된 제공자 오류 정보를 기록하며 키·원문 응답·측정 배열은 기록하지 않는다. API 오류는 `code`와 `message` 구조로 반환한다.

### 캐시

같은 설비·분석 근거·관련 이력·모델·분석 버전의 결과는 기본 24시간 재사용한다. 메모리와 `.cache/ai-analysis/`의 키별 JSON에 구조화된 결과·마크다운을 보관해 서버 재시작 후에도 유지한다. 캐시 폴더는 Git에서 제외한다.

`force=true` 또는 “다시 분석”은 캐시를 건너뛰고 갱신한다. 진행 중인 동일 요청은 공유한다. TTL은 양의 정수로 설정하며 잘못된 값은 86,400초를 사용한다. 분석 실패 시 기존 파일은 유지하고 저장 실패 시 결과를 반환하면서 메모리 캐시와 로그를 남긴다. 단일 프로세스를 전제하며 만료 파일 자동 정리는 없다.

## 6. AI 채팅

채팅은 선택 설비·FFT·베어링 결함·조회 종료일을 맥락으로 전달한다. 모델은 `get_trend`, `get_fft`, `get_bearing_fft`, `get_related_history`를 선택하며 알려진 다른 설비 코드나 과거 날짜 범위를 조회할 수도 있다.

서버는 도구 인자와 설비·날짜·레코드를 검증하고 원본 배열을 제외한 공통 분석 결과를 반환한다. 최대 4회 도구 응답 단계·8개 호출, 전체 시간은 응답당 제한시간의 최대 6배다. 응답 `toolCalls`에는 실제 호출 이름·인자·근거가 담긴다.

대화는 브라우저 `sessionStorage`에 설비별 최대 12개 메시지를 보관한다. 같은 설비의 FFT나 과거 조회일을 바꿔도 유지하고 초기화 버튼으로 지울 수 있다. 서버에 영구 대화 이력을 저장하지 않는다.

## 7. 진단 보고서와 이메일 초안

- **진단결과 PPT**: 보고서 기준 FFT와 화면 Trend/FFT 그래프 PNG를 이용해 한 장짜리 PPTX를 다운로드한다.
- **이메일 본문 복사**: AI 한국어 메일 초안과 그래프를 미리보기로 보여 주고 서식 있는 클립보드에 복사한다. 실제 메일 발송은 하지 않는다. 쓰기 미지원·권한 거부 시 미리보기와 오류 안내를 남긴다.

보고서는 근거에서 별도 AI 문안을 생성한다. OpenAI 설정을 공유하며 문안 결과는 메모리에 캐시하고 동일 진행 요청을 공유한다. 설비 분석의 디스크 캐시와는 별개다.

PPT 작성 후 별도 AI 검증 단계에서 실제 렌더링 이미지와 도형·표 좌표를 검사한다. 경계 이탈·글자 잘림/겹침·가독성·그래프 축/범례 누락이 있으면 최대 두 번 수정하고 재검증한다. 그래프 비율을 유지하고 글자는 최소 10pt를 사용한다. 문구 수정은 동일한 반복 문장 제거로 제한해 근거·수치·단위·조건·불확실성을 보존한다.

렌더링에는 `libreoffice`, `pdftoppm`(Poppler), 한국어 글꼴이 필요하며 명령별 제한시간은 30초다. 검증 모델은 이미지 입력과 구조화 응답을 지원해야 한다. 렌더링·검증 불가 시 `unverified`(UI 검증 미완료), 수정 후 문제 잔존 시 `warning`(UI 검증 경고), 통과 시 `passed`다. 경고/미완료도 다운로드하며 `X-PPT-Validation` 헤더의 URL 인코딩 JSON에 상태·수정 횟수·문제 요약을 담는다. LibreOffice와 PowerPoint의 표시 차이는 남을 수 있다.

## 8. 주요 API

| API | 조회 조건 / 용도 |
| --- | --- |
| `GET /api/datasets` | 설비 요약과 상태 |
| `GET /api/dashboard` | 첫 데이터셋의 상세 데이터 |
| `GET /api/dashboard/{dataset_id}` | `start`, `until` 선택. 상세 데이터와 `fftWeeklyDiagnosis` |
| `GET /api/dashboard/{dataset_id}/fft/{record_id}` | `start`, `until` 선택. 원본 배열 포함 FFT |
| `GET /api/history` | 이력 CSV 재조회. 화면에서 검색/필터 |
| `GET /api/dashboard/{dataset_id}/related-history` | `record_id` 필수, `selected_fault_type`, `until` 선택. 화면용 이력 |
| `POST /api/dashboard/{dataset_id}/ai-analysis` | `until`, `force` 선택. 설비 종합 분석 |
| `POST /api/dashboard/{dataset_id}/chat` | 질문·대화·선택 기록·날짜 맥락을 사용한 채팅 |
| `POST /api/dashboard/{dataset_id}/diagnostic-ppt` | 기준 FFT와 그래프 이미지로 PPTX 생성 |
| `POST /api/dashboard/{dataset_id}/email-draft` | 기준 FFT의 한국어 이메일 초안 생성 |

AI 분석은 기존 `recordId`, `selectedFaultType`을 호환용으로 받지만 분석 범위를 결정하지 않는다. 전달한 `recordId`의 유효성은 검사하므로 없는 기록은 오류가 된다. 보고서 API는 FFT `recordId`를 실제 기준으로 사용한다.

## 9. 현재 범위와 후속 논의

1. **조회 PoC**: 실시간 수집·DB·CSV 자동 갱신은 없다. 이력 화면과 AI 이력 스냅샷 간 갱신 정책도 통일되지 않았다.
2. **상태 체계 분리**: Trend 상태, 주간 FFT 등급, AI 위험 수준은 별개다. 데모 강제 상태와 화면별 `unknown` 표시 방식도 달라 동일한 운영 위험도로 볼 수 없다.
3. **운영 지표 혼재**: 실제 집계, 이력 건수를 알람으로 표시한 지표, 고정 KPI가 공존한다. 실제 알람·생산·작업지시/조치 데이터 연결이 필요하다.
4. **고정 진단 규칙**: 시간당 표본 전제, 고정 RPM·허용오차·임계값을 사용한다. 운전/정지·부하·회전수 변동·측정 품질을 반영한 현장 검증이 필요하다.
5. **AI 결과 관리**: 디스크 캐시는 있지만 승인·피드백·감사 이력·사용자 권한은 없다. 채팅은 브라우저 세션 저장이고 보고서 문안은 메모리 캐시다.
6. **연동 미구현**: 실제 이메일·알림 발송, 작업지시 생성, 외부 CMS/설비관리 연동은 없다. 화면의 조치율/WO 지표가 기능 구현을 의미하지 않는다.
7. **판단 범위**: AI와 규칙은 점검 보조 정보이며 잔여수명·MTBF를 예측하지 않는다. 최종 판단은 운전 조건과 현장 점검을 포함해 담당자가 수행한다.

후속 논의는 상태 통합 기준, 데모 지표의 실제 데이터 전환, 설비 식별/갱신 정책, 진단 근거와 승인 흐름, 현장 규칙 검증을 중심으로 진행할 수 있다.

## 10. 구현 확인 자료

- 화면 경로와 API: `app/main.py`
- 데이터 로드·기간 제한: `app/data_loader/`, `app/services/analysis.py`
- 공통 규칙과 주간 집계: `app/analysis/`, `app/services/fft_status.py`
- 이력 선정: `app/services/history.py`
- 설비 AI 근거·검증·캐시: `app/equipment_analysis.py`, `app/equipment_evidence.py`, `app/ai_analysis.py`
- 채팅·도구: `app/chat.py`, `app/agent_tools.py`, `app/tool_calling.py`
- 보고서: `app/reporting/`
- 실제/데모 지표: `app/static/modules/equipment-status/controller.js`, `app/static/modules/main/kpi-concept.js`, `app/static/modules/main/dashboard-chart-panels.js`
- 기존 검증 기록: `docs/validation/ai-tool-calling.md`, `docs/validation/ai-prefetched-context.md`, `docs/validation/ppt-ui-validation.md`

이번 갱신은 코드와 문서의 대조를 기준으로 한다. 기존 검증 기록은 과거 수행 자료이며 이번 문서 수정에서 전체 기능 테스트·브라우저 테스트·실제 OpenAI 호출을 다시 수행했다는 의미는 아니다.

## 11. Unified Design Operations

Design integration addendum: 2026-10-30. This section records the current
design-validation runtime; it does not revise the diagnosis or API policies
described above. The Task 8 implementer performs own verification only.
Independent reproduction by the controller-dispatched Sol reviewer is pending.

### Retained Routes

| Group | URLs |
| --- | --- |
| Primary operations | `/`, `/equipment-status2`, `/dashboard_ui6`, `/dashboard2?dataset=1`, `/history2`, `/main_ct` |
| Compatible operations | `/dashboard?dataset=1`, `/history`, `/main_sv` |
| Control comparisons | `/main_ct1`, `/main_ct2`, `/main_ct3`, `/main_sv1`, `/main_sv2`, `/main_sv3` |
| Retained comparisons | `/main`, `/dashboard_ui1`, `/dashboard_ui2`, `/dashboard_ui3`, `/dashboard_ui4`, `/dashboard_ui5`, `/dashboard_ui1_canvas` |
| Retained direct entries in the 25-route matrix | `/static/history2.html`, `/static/dashboard-ui1-fresh.html`, `/static/dashboard-lab.html` |
| Six additional retained direct documents | `/static/main.html`, `/static/dashboard-ui1-kpi.html`, `/static/dashboard-ui1-canvas.html`, `/static/design-lab.html`, `/static/dashboard-ui5.html`, `/static/equipment-status.html` |

Unknown-use comparison pages require owner confirmation before removal or
redirection. `/history2` is rendered from the operational history document,
not the retained direct history2 document. `/dashboard_ui2` preserves its
comparison controls; `/dashboard_ui6` remains the operating KPI dashboard.
Links retain each existing `dataset`/`until`/`start` policy. Do not invent an
`as_of` alias or extend the AI/report start-date scope.

### Ownership And Runtime

- [../app/presentation.py](../app/presentation.py) owns assembly, using four explicit slots for operational documents and four explicit paired regions for complete retained documents. Shared assets precede page CSS and appear once.
- [../app/static/cms-tokens.css](../app/static/cms-tokens.css) owns design values; [../app/static/cms-operations.css](../app/static/cms-operations.css) owns shared role consumers, controls and shell behavior. [../app/static/cms-sidebar-icons.css](../app/static/cms-sidebar-icons.css) owns sidebar icon rendering.
- [../app/static/equipment-status2.css](../app/static/equipment-status2.css) owns the reference equipment page; [../app/static/styles.css](../app/static/styles.css) and [../app/static/dashboard2-shell.css](../app/static/dashboard2-shell.css) own detail layout. History/workspace/control/KPI/chart-panel and retained HTML documents keep their corresponding CSS owners. No route-generated style block or migrated JS static stylesheet injection is allowed.
- JS retains tooltip coordinates, data-derived bar lengths, canvas drawing, Plotly configuration and exported document styles. These are not duplicate static CMS styles. Sidebar width changes only via the explicit toggle and `cms.sidebar.expanded`; storage failure remains nonblocking.
- Safe server: <http://127.0.0.1:8010>, existing task `shell: cms-task2-safe-live-8010`. Launch only if absent: `.\.venv\Scripts\python.exe -B .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task2-server.py`. Reuse and leave it running. Python edits need a safe-task restart; static edits are served live.

### Reproduction And Debt

From the repository root in PowerShell, with the existing `.venv` and portable
Node at `.cache/node/node-v20.18.0-win-x64/node.exe`:

```powershell
$verify = '.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py'
.\.venv\Scripts\python.exe $verify --node task8-final-ownership.txt -q tests/test_cms_presentation.py tests/test_report_ui.py tests/test_cms_chart_typography.py tests/test_operations_ui.py
.\.venv\Scripts\python.exe $verify --node task8-final-non-ui.txt -q
.\.venv\Scripts\python.exe $verify task8-final-all-ui.txt -q -m ui tests/ui
.\.venv\Scripts\python.exe $verify task8-final-reopen.txt -q -m ui tests/ui/test_cms_typography.py -k 'task8 or metadata_uses_role_typography'
.\.venv\Scripts\python.exe -B .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task8-evidence.py
```

The verifier disables dotenv, clears provider keys and denies external Python
sockets. Only `--node` adds the ESM option; UI mode clears it for Playwright's
bundled Node. Browser fixtures block external/unknown writes and supply local
AI/chat/email/PPT success and failure states. Clipboard tests consume data in
the page, not the OS clipboard. PPT success is a local synthetic file and is
not paid renderer/model validation. W/O remains the existing local demo download.

Final non-UI: **414 passed, 16 failed, 0 skipped**. The unchanged Task 7
baseline has 16 failures in API/analysis/source-history expectations and a
Windows process-group timeout test. Exact parametrized IDs and the final UI
results belong to the [acceptance record](validation/cms-design-acceptance.md)
and its evidence manifest; none are suppressed or repaired as design work.
Demo/real data boundaries remain unchanged. No mobile, native-menu zoom,
real provider/email, or exhaustive manual whole-page contrast claim is made.
