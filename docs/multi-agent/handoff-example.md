## Trend Agent Result

### Summary
- 가속도 ALL, BPF, PEAK는 최근 상승과 주의 이상을 보이며, 특히 BPF는 현재 위험 상태입니다. 속도는 상승 경향 규칙에는 해당하지 않지만 설정 경고 수준에 근접했습니다. 추세만으로 물리적 결함 원인은 특정할 수 없습니다.
- Status: limited; LLM success: True
- Period: 2026-01-30 23:00:00 ~ 2026-04-30 23:00:00

### Evidence
- [t:7] trend.trend.metrics[0].latestValue: 2.351137 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:11] trend.trend.metrics[0].change30Days: 1.209252 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:12] trend.trend.metrics[0].change90Days: 2.333662 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:15] trend.trend.metrics[0].thresholdState: caution ; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:39] trend.trend.metrics[1].latestValue: 2.233399 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:43] trend.trend.metrics[1].change30Days: 1.274755 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:44] trend.trend.metrics[1].change90Days: 2.219887 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:47] trend.trend.metrics[1].thresholdState: danger ; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:63] trend.trend.metrics[1].monthlyAverages[3].mean: 1.275582 g; record=None; measured=None; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None
- [t:66] trend.trend.metrics[1].monthlyAverages[3].changeFromPreviousMonth: 0.448683 g; record=None; measured=2026-04-30 23:00:00; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None
- [t:71] trend.trend.metrics[2].latestValue: 12.505223 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:75] trend.trend.metrics[2].change30Days: 6.406108 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:76] trend.trend.metrics[2].change90Days: 12.456083 g; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:79] trend.trend.metrics[2].thresholdState: caution ; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:103] trend.trend.metrics[3].latestValue: 4.657935 mm/s; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:107] trend.trend.metrics[3].change30Days: 0.158361 mm/s; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:108] trend.trend.metrics[3].change90Days: 4.495861 mm/s; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:111] trend.trend.metrics[3].thresholdState: normal ; record=None; measured=2026-04-30 23:00:00; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:131] trend.trend.analysis.status: stable ; record=None; measured=None; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:132] trend.trend.analysis.isRising: False ; record=None; measured=None; period=2026-01-30 23:00:00~2026-04-30 23:00:00; group=None
- [t:95] trend.trend.metrics[2].monthlyAverages[3].mean: 8.287764 g; record=None; measured=None; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None
- [t:98] trend.trend.metrics[2].monthlyAverages[3].changeFromPreviousMonth: 3.124839 g; record=None; measured=2026-04-30 23:00:00; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None
- [t:127] trend.trend.metrics[3].monthlyAverages[3].mean: 4.77531 mm/s; record=None; measured=None; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None
- [t:130] trend.trend.metrics[3].monthlyAverages[3].changeFromPreviousMonth: 0.59522 mm/s; record=None; measured=2026-04-30 23:00:00; period=2026-04-01 00:00:00~2026-04-30 23:00:00; group=None

### Interpretation
- 가속도 ALL은 최근 단기 및 전체 관찰 구간에서 상승했고 현재 주의 상태입니다. [t:7, t:11, t:12, t:15]
- 가속도 BPF는 최근 상승과 월별 상승이 이어지며 현재 위험 상태입니다. [t:39, t:43, t:44, t:47, t:63, t:66]
- 가속도 PEAK는 월별 상승과 최근 상승이 뚜렷하지만 현재는 주의 상태입니다. [t:71, t:75, t:76, t:79, t:95, t:98]
- 속도는 최근 월별 평균이 상승했으나 이동평균 상승 규칙은 비상승으로 판정되었고 현재 상태는 정상입니다. [t:103, t:107, t:108, t:111, t:127, t:130, t:131, t:132]

### Limitations
- 추세 데이터에는 운전 상태 메타데이터가 없어 운전·비운전 상태를 분리할 수 없습니다.
- 시간 간격 가정은 충족되지만, 제공된 기울기는 기존 시간당 샘플 인덱스 기반 결과이므로 새로운 시간 기울기로 재해석하지 않았습니다.
- 선택 FFT에서 유의한 피크 요약이 없어 추세만으로 불균형, 정렬불량 또는 베어링 원인을 구분할 수 없습니다.

### Recommended Checks
- 가속도 BPF와 PEAK의 다음 측정에서 동일 조건 반복 여부와 급격한 변화를 확인하십시오.
- 운전 상태와 부하 조건을 함께 기록하여 추세를 운전 조건별로 재검토하십시오.
- 현재 센서 설치 상태와 측정 방향을 점검하고, 원인 판별을 위해 주파수 스펙트럼과 위상 정보를 확인하십시오.


## Fft Agent Result

### Summary
- 주간 진폭 등급에서는 베어링 케이지(FTF)가 가장 빈번한 이상으로 표시되지만, 이는 진폭 기준 초기 결함 등급이며 물리적 결함 원인을 확정하지 않습니다. 동일 조건의 유의한 Peak 요약이 없어 미스얼라인먼트 판단도 제한적입니다.
- Status: limited; LLM success: True
- Period: 2026-02-09 09:42:00.833 ~ 2026-04-30 20:00:31.853

### Evidence
- [f:1710] fft.representativeRecords[5].frequencyRange: 500.0 Hz; record=fft:18; measured=2026-04-30 07:00:22.853000; period=2026-02-09 09:42:00.833~2026-04-30 20:00:31.853; group=group:cdac491af426
- [f:1725] fft.representativeRecords[5].spectrum.peaks[0].frequency: 89.375 Hz; record=fft:18; measured=2026-04-30 07:00:22.853000; period=2026-02-09 09:42:00.833~2026-04-30 20:00:31.853; group=group:cdac491af426
- [f:1726] fft.representativeRecords[5].spectrum.peaks[0].amplitude: 4.141418 mm/s; record=fft:18; measured=2026-04-30 07:00:22.853000; period=2026-02-09 09:42:00.833~2026-04-30 20:00:31.853; group=group:cdac491af426
- [f:1727] fft.representativeRecords[5].spectrum.peaks[0].count: 3.0 count; record=fft:18; measured=2026-04-30 07:00:22.853000; period=2026-02-09 09:42:00.833~2026-04-30 20:00:31.853; group=group:cdac491af426
- [f:1728] fft.representativeRecords[5].spectrum.peaks[1].frequency: 30.0 Hz; record=fft:18; measured=2026-04-30 07:00:22.853000; period=2026-02-09 09:42:00.833~2026-04-30 20:00:31.853; group=group:cdac491af426
- [f:2442] fft.weekly.causes[0].count: 30.0 count; record=None; measured=2026-04-30 15:42:17.353; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2443] fft.weekly.causes[0].totalScore: 30.0 score; record=None; measured=2026-04-30 15:42:17.353; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2444] fft.weekly.causes[0].highestScore: 1.0 score; record=None; measured=2026-04-30 15:42:17.353; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2448] fft.weekly.causes[0].maxAmplitude: 0.4042252004146576 g; record=None; measured=2026-04-30 15:42:17.353; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2437] fft.weekly.evaluatedRecordCount: 189.0 count; record=None; measured=None; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2438] fft.weekly.excludedRecordCount: 0.0 count; record=None; measured=None; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None
- [f:2439] fft.weekly.partialRecordCount: 0.0 count; record=None; measured=None; period=2026-04-24 00:00:00~2026-04-30 20:00:31.853000; group=None

### Interpretation
- 500 Hz·mm/s 조건에서 1X, 2X, 3X 성분이 관찰되며 일부 스펙트럼은 미스얼라인먼트 후보를 지원합니다. 다만 주어진 대표 기록 간 피크 구성이 일관되지 않아 원인 확정 근거로는 제한적입니다. [f:1710, f:1725, f:1726, f:1727, f:1728]
- 주간 진단은 FTF를 발생 횟수 우선으로 대표 원인으로 선정했으며, 해당 결과는 진폭 기준 초기 결함 등급입니다. 주간 등급만으로 베어링 케이지의 물리적 결함을 확정할 수 없습니다. [f:2442, f:2443, f:2444, f:2448]
- 동일 조건의 유의한 Peak 요약이 없고, 선택 시점 이전의 동일 설비 또는 동일 결함 이력이 없다는 품질 제한이 있습니다. [f:2442, f:2437, f:2438, f:2439]
- misalignment (low): 동일 500 Hz·mm/s 조건의 대표 스펙트럼에서 1X·2X·3X 피크가 관찰되고 제공 카탈로그가 미스얼라인먼트를 지원하지만, 피크 요약이 제한적이고 비교 가능한 연속 이력이 없어 낮은 신뢰도로 분류합니다. [f:1710, f:1725, f:1726, f:1727, f:1728]

### Limitations
- 대표 FFT에 유의한 Peak 요약이 없어 주파수 패턴 해석이 제한됩니다.
- 동일 조건 그룹의 연속적인 과거 스펙트럼 비교가 제공되지 않았습니다.
- FTF·BSF·BPFI·BPFO 주간 등급은 진폭 기준이며, 물리적 베어링 원인으로 해석하지 않습니다.

### Recommended Checks
- 동일 RPM·측정점·측정 모드·주파수 범위·해상도의 FFT를 재취득해 1X·2X·3X 패턴과 위상 일관성을 확인하십시오.
- 커플링 정렬, 베이스 강성, 소프트 풋 및 체결 상태를 점검하십시오.
- 베어링 원인 판단 전 FTF 관련 유의한 조화 성분과 베어링 계수 일치 여부를 확인하십시오.


## History Agent Result

### Summary
- HISTORY 분석 자료 없음: 전문 LLM 해석을 사용할 수 없어 판단이 제한됩니다.
- Status: unavailable; LLM success: False
- Period: None ~ None

### Evidence
- [h:1] history.relatedHistory[0].relatedHistory.sameEquipmentCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:2] history.relatedHistory[0].relatedHistory.similarFaultCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:3] history.relatedHistory[1].relatedHistory.sameEquipmentCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:4] history.relatedHistory[1].relatedHistory.similarFaultCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:5] history.relatedHistory[2].relatedHistory.sameEquipmentCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:6] history.relatedHistory[2].relatedHistory.similarFaultCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:7] history.relatedHistory[3].relatedHistory.faultTag.fault: 축 ; record=None; measured=None; period=None~None; group=None
- [h:8] history.relatedHistory[3].relatedHistory.faultTag.faultType: Complex ; record=None; measured=None; period=None~None; group=None
- [h:9] history.relatedHistory[3].relatedHistory.sameEquipmentCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:10] history.relatedHistory[3].relatedHistory.similarFaultCount: 0.0 count; record=None; measured=None; period=None~None; group=None
- [h:11] history.relatedHistory[4].relatedHistory.faultTag.fault: 축 ; record=None; measured=None; period=None~None; group=None
- [h:12] history.relatedHistory[4].relatedHistory.faultTag.faultType: Complex ; record=None; measured=None; period=None~None; group=None

### Interpretation

### Limitations
- HISTORY 분석 자료 없음: 전문 LLM 해석을 사용할 수 없어 판단이 제한됩니다.

### Recommended Checks
- 원본 자료와 측정 조건을 확인하세요.

### Source Queries
- FFT #631; strictly before 2026-02-09; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #4; strictly before 2026-04-30; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #25; strictly before 2026-04-30; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #630; strictly before 2026-02-09; fault=Complex; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #3; strictly before 2026-04-30; fault=Complex; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #18; strictly before 2026-04-30; fault=Misalignment; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #306; strictly before 2026-04-14; fault=Complex; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #225; strictly before 2026-04-20; fault=Complex; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #629; strictly before 2026-02-09; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #2; strictly before 2026-04-30; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=
- FFT #47; strictly before 2026-04-29; fault=None; policy=same_equipment_and_same_fault_strictly_before_cutoff_limit_5; records=

### Validation Failures
- no_source_data
