# AI 도구 호출 검증 결과

검증 에이전트가 구현 전에 아래 질문과 기대 근거를 고정했다. PASS 판정은 필요한 도구 호출과 실제 답변의 근거가 모두 일치해야 한다.

## 사전 질문과 기대 기준

| ID | 입력 | 기대 도구·근거 | 금지 주장 |
|---|---|---|---|
| C01 | dataset 9, record 4: 선택 FFT 원인과 수치 근거 | `get_fft`; 속도 FFT, Unbalance, 1170 RPM, 1X 20 Hz·3.8065 mm/s, 2X/1X≈0.0737, 3X/1X≈0.0167 | 베어링 내륜 결함 확정 |
| C02 | dataset 8, record 2: 베어링 결함과 유의 고조파 | `get_bearing_fft`; NSK 6315, BPFI, 1차 141.25 Hz·2.5098 g와 2차 282.5 Hz·0.7193 g 유의 | 3차 425 Hz·0.1288 g를 유의하다고 하거나 축 1X와 혼동 |
| C03 | dataset 8, record 4: 내륜 결함 확인 여부 | `get_bearing_fft`; `no_anomaly`/`normal`, 결함 고조파 0.5 g 이상 없음 | 전체 스펙트럼 peak가 모두 0.5 g 미만이라는 주장 (400 Hz sideband 0.5392 g 존재) |
| C04 | dataset 2, record 3: 베어링 결함 판정 | `get_bearing_fft`; 형번 누락 `bearing_not_configured`, 진단 불가 | 정상 또는 특정 결함 확정 |
| C05 | dataset 1: V032의 2026-06-01~2026-09-01 Trend | `get_trend`; `no_trend_data_in_range` | 다른 기간의 수치를 해당 기간 근거로 제시 |
| C06 | dataset 9, 선택 record 4: 8월 31일 FFT | `get_fft`, start=end=2026-08-31; record 66, ENV, 베어링 형번 누락 | 9월 7일 record 4의 Unbalance 진단 재사용 |
| C07 | dataset 8, record 2: 같은 설비·결함의 과거 이력 | `get_related_history`; cutoff 2026-09-07, 동일 설비 BPFI 0건 | 다른 설비 또는 다른 결함 유형 이력을 동일 사례로 제시 |
| C08 | dataset 8, record 2: 전체 Trend·FFT·이력 종합 | Trend rising, slope≈0.0045484 > 0.00297619 mm/s/hour, BPFI 근거, 동일 설비 BPFI 이력 0건 | 관련 이력 창작 또는 추세와 FFT의 인과관계 단정 |
| C09 | C02 후속 질문: 결함 1X와 축 회전 1X의 관계 | 대화의 record 유지; 결함 1X≈141.25 Hz와 축 1X≈29.1667 Hz는 다름 | 다른 FFT의 20 Hz 답변 사용 |
| C10 | AI 분석 카드: dataset 9 record 4, dataset 8 record 2 | Trend·선택 FFT·관련 이력 도구 모두 호출; 기존 `AiDiagnosis` 구조로 응답 | dataset 9의 stable 판정을 단순 30일 증가≈0.8236 mm/s와 혼동하거나 dataset 8 상승 근거 왜곡 |

## 실행 결과

| 사례 | 결과 | 실행 근거 |
|---|---|---|
| C01 | **PASS (수정 후 재시험)** | 실 API HTTP 200. `get_fft`가 dataset 9 / record 4를 선택했고 1170 RPM, 1X 20.0 Hz·3.806462 mm/s 및 배수 비율을 답변했다. 요청 ID `req_9dd3890af2b04cff9af2886f3b3da7bd`, `req_24d4440382504009bc71f3406ec8ec01`. 이전에는 동일 코드의 중복 설비 때문에 잘못된 dataset을 선택했고, 모델 설정 문제로 HTTP 400도 재현됐다. 둘 다 수정했다. |
| C02 | **PASS** | 실 API HTTP 200. `get_bearing_fft` V191 record 2; BPFI 1·2차 유의, 3차 비유의. 실제 결정론적 진단 결과와 답변 수치가 일치했다. 요청 ID `req_82c1c708ce0d48b3bbe6bb945a62e2f5`, `req_aaf4803616e44c4e879d934f8c3d34df`. |
| C03 | **PASS** | 실 API HTTP 200. V191 record 4에서 BPFI 이상 없음으로 답했고, BPFI 3차 0.346 g를 유의하다고 하지 않았다. 전체 스펙트럼의 별도 peak와 구분했다. |
| C04 | **PASS** | 실 API HTTP 200. V056 record 3의 베어링 형번 누락을 근거로 결함 판정 불가라고 답했다. |
| C05 | **PASS** | 실 API HTTP 200. V032의 정확한 기간을 `get_trend`에 전달했으며 해당 범위 데이터 없음으로 답했다. |
| C06 | **PASS (재시험)** | 첫 호출은 선택 중인 9/7 record를 재사용해 실패했다. 프롬프트를 수정한 재시험은 HTTP 200, `get_fft`에 start=end=`2026-08-31` 전달, record 66 / ENV를 반환했다. |
| C07 | **PASS** | 실 API HTTP 200. `get_related_history`에 V191 record 2의 결함과 2026-09-07 cutoff를 전달했고 동일 설비 유사 이력 0건이라고 답했다. |
| C08 | **PASS** | 실 API HTTP 200. Trend·FFT·bearing FFT·history 도구를 호출해 추세 상승과 BPFI 소견을 설명하고, 이력은 0건이라고 답했다. 근거 간 인과관계를 단정하지 않았다. |
| C09 | **PASS** | 실 API HTTP 200. 대화 중 선택된 record를 유지하고 BPFI 결함 1X 141.25 Hz와 축 회전 1X 29.1667 Hz를 구분했다. |
| C10 V056 | **PASS (수정 후 재시험)** | 초기 답변은 Trend가 stable인데 상승 중이라고 잘못 서술해 FAIL했다. 판정기가 이를 감지하도록 보완했다. 그 뒤 502 및 품질 보정 재시도가 있었고 최종 HTTP 200 답변은 stable, 30일 변화 +0.82 mm/s로 구분했다. |
| C10 V191 | **PASS (수정 후 재시험)** | 초기 답변은 `1차` 표현을 판정기가 놓쳐 HTTP 502 `invalid_response`가 발생했다. 판정기를 보완한 최종 HTTP 200 답변은 상승 Trend, BPFI 1·2차 유의 진폭과 이력 0건을 근거로 제시했다. |

검증은 사용자의 승인 후 설정된 실제 OpenAI API key와 `gpt-5.6-luna` 모델로 수행했다. 비밀 키는 출력하거나 보고서에 저장하지 않았다. 검증 에이전트는 API 호출 전에 C01–C10의 질문별 기대 도구, 답변 근거, 금지 주장을 고정했고, 별도 결과 감사자가 각 실행 결과를 독립 검토했다. 모든 사례는 수정 후 최종 재시험에서 PASS했지만, C06과 C10은 초기 실패/재시도 이력이 있고 C10에서는 502 응답도 발생했다. 따라서 PASS는 최종 응답과 근거가 기준을 충족했다는 뜻이며, 모델 응답의 재시도 변동성은 관찰 사항으로 남긴다.

## 로컬 검증

- `.venv/bin/pytest -q`: 115 passed.
- C07의 cutoff 경계는 결정론적 테스트에서 cutoff 전날 기록만 포함하고 당일·다음 날은 제외함을 확인했다.
- V191 record 2의 BPFI 설명은 실제 `significant` 표시와 수치에 맞춰 1·2차 유의, 3차 비유의로 교정했다.


## 2026-10-04 main 통합 검증

- AI 도구 호출을 최신 main의 JSON 캐시 및 PPT 검증 기능과 함께 통합했다.
- 종합 분석의 근거 도구 실행, 서버 재시작 후 JSON 캐시 재사용, 강제 재분석 시 도구 재실행을 API 회귀 테스트로 확인했다.
- 전체 로컬 테스트: `.venv/bin/pytest -q` — 171 passed.
- 기존 main의 제거된 AI 화면 요소를 참조하던 테스트를 현재 UI에 맞췄다. 동일 PPT 캐시 테스트는 ZIP 생성 시각에 영향을 받지 않도록 동일 파일 바이트를 재사용한다.
- 이번 통합 검증에서는 외부 OpenAI API 호출을 모의 응답으로 대체했다. 위 실 API 검증 기록은 기존 브랜치의 기록이며 이번에 재실행하지 않았다.
- UI 변경이 없어 브라우저 검증은 생략했다.
