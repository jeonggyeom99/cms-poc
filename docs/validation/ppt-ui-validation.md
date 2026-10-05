# PPT UI 검증 구현 확인

- 작업 브랜치: `feat/ppt-ui-validation`
- 독립 검증 서브 에이전트 최종 판정: **PASS**
- 관련 테스트: **55 passed**
- 전체 회귀 테스트: **144 passed, 3 failed**. 아래 실패는 작업 시작 전에 존재하던 사용자 변경과 연결되어 있으며 해당 변경을 보존했다.

## 검증 근거

| 확인 항목 | 결과 |
| --- | --- |
| 실제 PPT → PDF → PNG 및 독립 이미지 검증 입력 | 구현·테스트 확인 |
| 최대 두 번 수정·세 번 검증, 변경 없는 수정 종료 | 관련 테스트 통과 |
| 도형 경계·겹침 검사와 병합 셀 좌표 수집 | 관련 테스트 통과 |
| 진단 수치·조건·근거 보존 | 동일 반복 문장만 제거, 한국어 근거 삭제 회귀 테스트 통과 |
| 경고·검증 미완료 시 다운로드 유지와 이전 산출물 보존 | 관련 테스트 통과 |
| 다운로드 상태 헤더와 화면 표시 | Node DOM·Plotly 대역 테스트 통과 |
| 렌더러 프로필 격리·제한 시간·프로세스 그룹 종료·임시 파일 정리 | 관련 테스트 통과 |
| 대표 및 긴 한국어 설비명·설명 PPT의 실제 렌더링 | 경계 이탈·잘림·비의도적 겹침 없음 |

독립 검토에서 문장 발췌가 수치 없는 한국어 진단 근거를 삭제할 수 있음을 발견하여 최초 FAIL을 받았다. 모든 서로 다른 원문 문장을 유지하고 완전히 동일한 반복 문장만 제거하도록 수정했다. 그래프 범례를 위쪽에 배치할 때 기존 `yanchor: top`이 남는 문제도 `bottom`으로 보정했다. 수정 후 검증 에이전트가 코드·산출물·관련 테스트를 다시 확인하여 PASS를 반환했다.

## 기존 사용자 변경에 따른 테스트 실패

- `tests/test_app.py::test_dashboard_page_is_served`: 기존 HTML 변경으로 `ai-analysis-result`가 제거됨.
- `tests/test_report_ui.py::test_equipment_ai_diagnosis_is_pinned_until_manual_reanalysis`: 기존 HTML 변경으로 `ai-analysis-reference`가 제거됨.
- `tests/test_report_ui.py::test_ai_analysis_shows_generated_diagnosis_in_overview`: 기존 AI 화면 변경으로 `result.textContent` 설정이 제거됨.

## 검증 한계

라이브 OpenAI 호출과 실제 Plotly 캡처 이미지의 시각 검증은 수행하지 않았다. 실제 LibreOffice 렌더링에는 PIL로 만든 대표 그래프를 사용했고, 캡처 설정·범례·글꼴·다운로드 흐름은 Node 대역으로 검증했다. 웹 변경은 상태 표시 중심이므로 브라우저·모바일 검증을 생략했다. LibreOffice와 PowerPoint 표시에는 차이가 있을 수 있다.

렌더링 확인 파일은 `/tmp/cms-ppt-validation-qa/`의 `representative` 및 `long-korean` PPTX·PNG·좌표 JSON이며 저장소에는 포함하지 않는다.
