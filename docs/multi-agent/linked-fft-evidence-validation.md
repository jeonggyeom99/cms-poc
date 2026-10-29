# FFT 연결 근거·출력 한도 재검증

검증일: 2026-10-30 (한국 시간). 작업 브랜치: `codex/agent`.

## 구현 범위

- 기존 Trend·FFT·History 병렬 호출 → Synthesis 구조 유지. 원본 값 대조와 교정 재호출은 모두 비활성 상태 유지.
- FFT 입력에 기록·날짜·모드·주파수·진폭과 기존 근거 ID를 연결한 `measurements` 추가. 카탈로그 선별, 추가 Tool 응답 및 Hand-off에서도 쌍을 유지한다. 주간 `maxAmplitude`만 인용한 경우에도 해당 `peakEvidence`를 Synthesis에 전달한다.
- 최고 진폭의 측정일·기록을 `peakEvidence`에서 가져오고, 최신 발생일 `latestAt`은 별도 근거로 제공한다. `countsByMode`와 서버 설명에서 전체·ENV·ALL 건수를 구분한다. 기존 등급·순위 계산은 변경하지 않았다.
- FFT 전용 내부 응답 스키마는 요약 1,200자, Trend는 500자. 출력 토큰 예산은 FFT 3,600, Trend·History 각 2,200, Synthesis 2,400이다. 문자 한도와 전체 JSON 토큰 한도는 서로 다른 제한이다.
- 요약 자체에 관측·가능한 해석·우선 점검을 담고, 보조 관측·가설에서 같은 설명의 반복을 줄이도록 지시한다. History 자료 없음·API 호출 실패·응답 처리 실패 문구는 서버가 구분한다.

## 회귀 사례

`tests/test_linked_fft_evidence.py`는 실제 저장소 CSV를 읽으며, 외부 응답이 필요한 테스트에서는 제공자 완료 응답만 대체한다.

| 사례 | 서버 입력에서 고정한 사실 |
|---|---|
| Dataset 2 / V056 기록 51 | 2026-06-18 21:46:39.127 / 속도 / 20 Hz / 약 4.07358 mm/s |
| Dataset 2 최신 발생일 | 2026-06-21 21:46:39.127; 최고값 측정일과 별도 |
| Dataset 9 기록 51 | 날짜가 이동한 별도 CSV: 2026-09-02; 6월 18일로 재사용하면 오류 |
| Dataset 5 / V191 BPFI | 전체 2건 = ENV 1건 + ALL 1건; 피크는 5월 25일 ENV 기록 2 / 141.25 Hz |
| 내부 출력 한도 | FFT 501·1,200자 보존, 1,201자는 스키마 실패로 제한 결과; 교정 없음 |
| History | 자료 없음과 제공자 API 실패를 서로 다른 서버 문구로 표시 |

최초 신규 회귀 9개가 기존 코드에서 실패함을 확인한 뒤 구현했다. Synthesis 피크 전달도 별도 실패 → 통과를 확인했다. 추가로 실제 혼합 모드 CSV 및 Tool 근거의 주파수·진폭·날짜·모드 연결을 검사한다.

## 실제 호출

사용자가 CSV 요약 근거를 설정된 OpenAI API로 전송하도록 승인한 뒤, 기존 `scripts/benchmark_ai.py`로 Dataset 2·5를 각 1회 호출했다. 최초 응답은 FFT 요약이 한 문단에 그쳐 품질 기준을 충족하지 못했다. 요약을 주 설명으로 지정한 뒤 추가 승인된 각 1회 호출을 수행했다. 사용 모델은 `gpt-6-luna`다. History 조회 결과가 없어 각 분석은 Trend·FFT·Synthesis 3회이며 History API 호출은 생략됐다.

| 최종 실측 | Dataset 2 | Dataset 5 |
|---|---:|---:|
| 전체 지연(전처리·저장 포함) | 16.29초 | 17.45초 |
| LLM 호출 / Tool / 교정 | 3 / 0 / 0 | 3 / 0 / 0 |
| 입력 / 출력 토큰 합계 | 27,695 / 2,340 | 33,806 / 2,612 |
| FFT 출력 토큰 / 상한 | 755 / 3,600 | 989 / 3,600 |
| Synthesis 출력 토큰 / 상한 | 976 / 2,400 | 941 / 2,400 |
| FFT 요약 글자 / 빈 줄로 구분한 문단 | 421 / 2 | 470 / 2 |
| 종합 요약 글자 / 빈 줄로 구분한 문단 | 482 / 2 | 409 / 2 |
| Trend 요약 글자 | 398 | 318 |
| 최종 FFT 참조 기록 | 543, 4, 51, 542 | 2, 44 |
| 응답 잘림 / 스키마 실패 | 없음 / 없음 | 없음 / 없음 |

모든 완료 응답의 `finish_reason=stop`이었다. 요약과 문장의 종결, 문단, 참조 기록 및 출처를 직접 검토했다. Dataset 2 FFT 요약은 기록 51의 6월 18일 피크와 6월 21일 최신 발생일을 구분하며, Dataset 5 FFT 요약은 전체 2건과 ENV·ALL 각 1건을 정확히 설명했다. 핵심 점검도 FFT 요약 안에 포함됐다. 단일 표본의 지연이므로 성능 개선 수치로 일반화하지 않는다.

### 잔존 품질 문제: 전체 통과 아님

Dataset 5의 **Synthesis headline**에는 “ENV 주간 집계에서는 BPFI가 2건”이라는 잘못된 범위 표현이 남았다. 실제 ENV는 1건이고 전체가 2건이다. 같은 응답의 FFT 요약에는 올바른 구분이 있다. 따라서 주간 범위 회귀의 **입력 계약은 통과하지만 실제 종합 문장의 정확성은 통과하지 못했다.**

Dataset 2 Trend 요약은 두 문장 묶음을 단일 개행으로 구분했다. FFT 및 headline은 빈 줄로 두 문단을 구분했으나 Trend까지 동일 서식을 보장하지는 못했다. `stable`, `unbalance` 등 영문 상태·원인 코드도 일부 남았다. 긴 수치 표기와 제한 설명의 반복도 완전히 제거되지는 않았다.

HTTP 200이나 `status=ready`, `synthesis_status=completed`는 본 품질 평가의 통과 기준이 아니다. 이 변경은 오류를 줄이는 입력·예산 개선이며 정확성을 보장하지 않는다. 수치·날짜·집계 범위 문장을 강하게 보장하려면 사용자가 제안한 서버 문장 작성과 AI 해석 분리가 후속 선택지다. 현재 요청에서는 그 방식이나 의미 대조·교정 재호출을 추가하지 않았다.

## 원자료와 재현

- 최초 실측: `.cache/linked-fft-live/dataset-{2,5}/benchmark.json` 및 각 `traces/`.
- 최종 실측: `.cache/linked-fft-live-final/dataset-{2,5}/benchmark.json` 및 각 `traces/`.
- 최종 요청 ID: Dataset 2 `487af255f5c84abea59888da699b4977`, Dataset 5 `54a448c76ba74a44abd5524c95b27c75`.
- 캐시·추적 파일은 Git 제외 경로에 보존했다. API 키나 원본 FFT 배열은 보고서에 포함하지 않았다.

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_linked_fft_evidence.py tests/test_multi_agent.py tests/test_ai_narrative.py tests/test_fft_severity.py --basetemp=.cache/pytest-linked-focused-new
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-linked-full-new
# 실제 호출은 현재 API 설정을 사용한다.
.\.venv\Scripts\python.exe scripts/benchmark_ai.py --dataset-id 2 --mode multi --repeats 1 --cache-repeats 0 --output .cache/linked-fft-recheck/dataset-2
```

Windows 제한 환경은 asyncio 내부 로컬 소켓 생성에서 멈춰 동일 테스트를 제한 밖에서 실행했다. 기존 `test_renderer_timeout_kills_process_group`은 Windows의 `os.killpg` 미지원으로 실패하며, 이 작업에서 해당 테스트·PPT 코드는 수정하지 않았다.

최종 전체 실행 결과: **367 passed, 1 failed, 1 warning (54.24초)**. 실패는 위 Windows 렌더러 테스트 1개이며, 경고는 기존 Starlette TestClient의 httpx 사용 중단 예정 안내다. 최종 12개 연결 근거 회귀는 전체 실행에 포함되어 모두 통과했다.

읽기 전용 별도 코드 검토에서 이번 입력·스키마 변경의 추가 결함은 발견되지 않았다. 실측 문장 품질은 위와 같이 별도 평가했다. commit·merge·push는 실행하지 않았다.
