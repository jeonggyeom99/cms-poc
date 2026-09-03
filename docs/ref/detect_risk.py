import pyodbc
import pandas as pd
import numpy as np
import re
import os
import ast

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

import warnings
warnings.filterwarnings('ignore')  # 모든 경고 무시


# ============================================================
# 데이터 경로
# ============================================================

path = 'DataBase'

file_list = os.listdir(path)
print(file_list)


# ============================================================
# 1. 진단 : 축 - 속도
# ============================================================

file = 'FFT 수처리_No.2 Direct Cooling Pump_Pump DS-V032 (V032).csv'

fft_data = pd.read_csv(
    os.path.join(path, file)
)

print(fft_data)


# ------------------------------------------------------------
# 분석할 데이터 확인
# ------------------------------------------------------------

target_list = fft_data[
    (fft_data.MeasureDate.str.startswith("2026-04-15")) &
    (fft_data.MeasureMode == 3)
]

print(target_list)


# ------------------------------------------------------------
# 특정 시점 FFT 선택
# ------------------------------------------------------------

fft_data_target = fft_data[
    fft_data.MeasureDate.str.startswith(
        "2026-04-15 09:00:20"
    )
]

print(fft_data_target)


# ------------------------------------------------------------
# Time Waveform 복원
# ------------------------------------------------------------

val = fft_data_target.TimeWaveSampling.iloc[0]

time_raw = np.frombuffer(
    ast.literal_eval(val),
    dtype='<f4'
)


# ------------------------------------------------------------
# Time Waveform 그래프
# ------------------------------------------------------------

plt.figure(figsize=(14, 4))

plt.plot(time_raw)

plt.xlabel("Sample Index")
plt.ylabel("Amplitude")
plt.title("Time Waveform")

plt.xlim(
    0,
    len(time_raw)
)

plt.grid(True)
plt.tight_layout()

plt.show()


# ------------------------------------------------------------
# FFT 데이터 복원
# ------------------------------------------------------------

val = fft_data_target.ResultData.iloc[0]

fft_amp = np.frombuffer(
    ast.literal_eval(val),
    dtype='<f4'
)

MeasureFreq = 500  # 변경필요

fft_freq = np.linspace(
    0,
    MeasureFreq,
    len(fft_amp)
)


# ------------------------------------------------------------
# 주요 Peak 추출
# ------------------------------------------------------------

top_idx = np.argsort(
    fft_amp
)[-10:][::-1]


# 진폭
amp = fft_amp[top_idx].astype(float)

# 주파수
freq = fft_freq[top_idx].astype(float)


# 유사 주파수 판단 기준
tolerance = 1  # Hz


# 주파수 오름차순 정렬
order = np.argsort(freq)

freq_sorted = freq[order]
amp_sorted = amp[order]


# ------------------------------------------------------------
# 가까운 주파수를 하나의 그룹으로 묶기
# ------------------------------------------------------------

groups = []

current_group = [0]

for i in range(
    1,
    len(freq_sorted)
):

    if (
        freq_sorted[i]
        - freq_sorted[i - 1]
        <= tolerance
    ):

        current_group.append(i)

    else:

        groups.append(
            current_group
        )

        current_group = [i]


groups.append(
    current_group
)


# ------------------------------------------------------------
# 각 그룹에서 진폭이 가장 큰 Peak 선택
# ------------------------------------------------------------

result = []

for group in groups:

    group = np.array(group)

    peak_pos = group[
        np.argmax(
            amp_sorted[group]
        )
    ]

    result.append({

        "대표주파수":
            freq_sorted[peak_pos],

        "최대진폭":
            amp_sorted[peak_pos],

        "그룹주파수":
            freq_sorted[group].tolist(),

        "그룹진폭":
            amp_sorted[group].tolist(),

        "개수":
            len(group)

    })


result_df = pd.DataFrame(
    result
)


# 진폭이 큰 그룹부터 정렬
result_df = result_df.sort_values(
    by="최대진폭",
    ascending=False
).reset_index(
    drop=True
)


# ------------------------------------------------------------
# 진폭 Threshold
# ------------------------------------------------------------

AMP_THRESHOLD = 0.5

# (*속도 >= 4, 가속도 >= 0.2)
# 변경필요


# 대표주파수 중 진폭 기준 만족 데이터
# 최대 5개 출력
selected_df = result_df[
    result_df["최대진폭"]
    >= AMP_THRESHOLD
].head(5)


print(selected_df)


# ------------------------------------------------------------
# FFT 주요 Peak 그래프
# ------------------------------------------------------------

plt.figure(
    figsize=(14, 4)
)

plt.plot(
    fft_freq,
    fft_amp,
    label="FFT"
)


# 그래프 y축 범위 확보
y_max = np.max(
    fft_amp
)


for _, row in selected_df.iterrows():

    freq = row["대표주파수"]
    amp = row["최대진폭"]

    plt.axvline(
        x=freq,
        color="red",
        linestyle="--",
        linewidth=1,
        alpha=0.7
    )

    plt.text(
        freq,
        y_max * 0.9,

        f"{freq:.2f} Hz\n"
        f"Amp: {amp:.3f}",

        rotation=90,
        color="red",
        ha="right",
        va="top",
        fontsize=13
    )


plt.xlim(
    0,
    MeasureFreq
)

plt.xlabel("Frequency")
plt.ylabel("Amplitude")
plt.title("FFT")

plt.grid(True)
plt.tight_layout()

plt.show()


# ============================================================
# 축 결함 진단 함수
# ============================================================

def diagnose_velocity(
    freq,
    amp,
    fr,
    tol=1,
    amp_threshold=4
):

    """
    freq, amp:
        FFT 스펙트럼의 주파수/진폭 배열

    fr:
        회전속도 (Hz = RPM / 60)

    tol:
        주파수 오차 허용범위 (Hz)
    """

    def get_amp(
        target_freq
    ):

        idx = np.where(
            np.abs(
                freq - target_freq
            ) <= tol
        )[0]

        return (
            np.max(amp[idx])
            if len(idx) > 0
            else 0.0
        )


    # 회전주파수 1X
    amp_1x = get_amp(
        fr
    )

    # 2X
    amp_2x = get_amp(
        2 * fr
    )

    # 3X
    amp_3x = get_amp(
        3 * fr
    )


    if amp_1x == amp_threshold:

        return (
            "Unknown "
            "(1X Peak Not Found)"
        )


    # 1X 대비 2X 비율
    ratio_2x = (
        amp_2x
        / amp_1x
    )

    # 1X 대비 3X 비율
    ratio_3x = (
        amp_3x
        / amp_1x
    )


    # --------------------------------------------------------
    # 판별 로직
    # --------------------------------------------------------

    if (
        ratio_2x > 0.4
        or
        ratio_3x > 0.3
    ):

        return (
            f"Misalignment "
            f"(2X Ratio: "
            f"{ratio_2x:.2f})"
        )


    elif (
        ratio_2x < 0.2
        and
        ratio_3x < 0.1
    ):

        return (
            f"Unbalance "
            f"(1X Dominant, "
            f"2X Ratio: "
            f"{ratio_2x:.2f})"
        )


    else:

        return (
            "Complex / "
            "Suspected Misalignment "
            "or Looseness"
        )


# ------------------------------------------------------------
# 축 결함 진단 실행
# ------------------------------------------------------------

RPM = 1780  # 변경필요

fr = round(
    RPM / 60,
    2
)


velocity_result = diagnose_velocity(
    fft_freq,
    fft_amp,
    fr,
    AMP_THRESHOLD
)

print(
    velocity_result
)


# ============================================================
# 2. 진단 : 베어링
# ============================================================

file = (
    'FFT NO.1 DUST COLLECT FAN_'
    'IMPELLER SIDE (V191).csv'
)

fft_data = pd.read_csv(
    os.path.join(
        path,
        file
    )
)

print(
    fft_data
)


# ------------------------------------------------------------
# 대상 데이터 확인
# ------------------------------------------------------------

target_list = fft_data[
    (
        fft_data.MeasureDate
        .str.startswith(
            "2026-04-27"
        )
    )
    &
    (
        fft_data.MeasureMode
        == 2
    )
]

print(
    target_list
)


# ------------------------------------------------------------
# 분석 시점 선택
# ------------------------------------------------------------

fft_data_target = fft_data[
    fft_data.MeasureDate
    .str.startswith(
        "2026-04-27 11:04:25"
    )
]

print(
    fft_data_target
)


# ------------------------------------------------------------
# Time Waveform 복원
# ------------------------------------------------------------

val = (
    fft_data_target
    .TimeWaveSampling
    .iloc[0]
)

time_raw = np.frombuffer(
    ast.literal_eval(val),
    dtype='<f4'
)


# ------------------------------------------------------------
# Time Waveform Plot
# ------------------------------------------------------------

plt.figure(
    figsize=(14, 4)
)

plt.plot(
    time_raw
)

plt.xlabel(
    "Sample Index"
)

plt.ylabel(
    "Amplitude"
)

plt.title(
    "Time Waveform"
)

plt.xlim(
    0,
    len(time_raw)
)

plt.grid(True)
plt.tight_layout()

plt.show()


# ------------------------------------------------------------
# FFT 데이터 복원
# ------------------------------------------------------------

val = (
    fft_data_target
    .ResultData
    .iloc[0]
)

fft_amp = np.frombuffer(
    ast.literal_eval(val),
    dtype='<f4'
)


MeasureFreq = 1000  # 변경필요


fft_freq = np.linspace(
    0,
    MeasureFreq,
    len(fft_amp)
)


# ------------------------------------------------------------
# 주요 Peak 검출
# ------------------------------------------------------------

top_idx = np.argsort(
    fft_amp
)[-10:][::-1]


amp = (
    fft_amp[top_idx]
    .astype(float)
)

freq = (
    fft_freq[top_idx]
    .astype(float)
)


# 베어링에서는 5Hz 기준
tolerance = 5


# 주파수 오름차순 정렬
order = np.argsort(
    freq
)

freq_sorted = freq[
    order
]

amp_sorted = amp[
    order
]


# ------------------------------------------------------------
# 유사 주파수 그룹
# ------------------------------------------------------------

groups = []

current_group = [0]


for i in range(
    1,
    len(freq_sorted)
):

    if (
        freq_sorted[i]
        - freq_sorted[i - 1]
        <= tolerance
    ):

        current_group.append(
            i
        )

    else:

        groups.append(
            current_group
        )

        current_group = [
            i
        ]


groups.append(
    current_group
)


# ------------------------------------------------------------
# 대표 Peak 선택
# ------------------------------------------------------------

result = []


for group in groups:

    group = np.array(
        group
    )

    peak_pos = group[
        np.argmax(
            amp_sorted[group]
        )
    ]


    result.append({

        "대표주파수":
            freq_sorted[
                peak_pos
            ],

        "최대진폭":
            amp_sorted[
                peak_pos
            ],

        "그룹주파수":
            freq_sorted[
                group
            ].tolist(),

        "그룹진폭":
            amp_sorted[
                group
            ].tolist(),

        "개수":
            len(group)
    })


result_df = pd.DataFrame(
    result
)


result_df = (
    result_df
    .sort_values(
        by="최대진폭",
        ascending=False
    )
    .reset_index(
        drop=True
    )
)


AMP_THRESHOLD = 0.2

# (*속도 >= 4,
#   가속도 >= 0.2)
# 변경필요


selected_df = result_df[
    result_df[
        "최대진폭"
    ] >= AMP_THRESHOLD
].head(5)


print(
    selected_df
)


# ------------------------------------------------------------
# FFT Plot
# ------------------------------------------------------------

plt.figure(
    figsize=(14, 4)
)


plt.plot(
    fft_freq,
    fft_amp,
    label="FFT"
)


y_max = np.max(
    fft_amp
)


for _, row in selected_df.iterrows():

    freq = row[
        "대표주파수"
    ]

    amp = row[
        "최대진폭"
    ]


    plt.axvline(
        x=freq,
        color="red",
        linestyle="--",
        linewidth=1,
        alpha=0.7
    )


    plt.text(
        freq,
        y_max * 0.9,

        f"{freq:.2f} Hz\n"
        f"Amp: {amp:.3f}",

        rotation=90,
        color="red",
        ha="right",
        va="top",
        fontsize=13
    )


plt.xlim(
    0,
    MeasureFreq
)

plt.xlabel(
    "Frequency"
)

plt.ylabel(
    "Amplitude"
)

plt.title(
    "FFT"
)

plt.grid(True)
plt.tight_layout()

plt.show()


# ============================================================
# 베어링 결함 진단 함수
# ============================================================

def diagnose_bearing_fault(
    fft_freq,
    fft_amp,
    rpm,
    bearing_number,
    maker,
    master_df,
    tolerance=None,
    harmonics=3,
    use_sideband=False,
):

    """
    master_df 컬럼:

    Number
    Maker
    BPFO
    BPFI
    BSF
    FTF

    결함 계수는 Order 기준
    """

    freq = np.asarray(
        fft_freq,
        dtype=float
    )

    amp = np.asarray(
        fft_amp,
        dtype=float
    )


    if len(freq) != len(amp):

        raise ValueError(
            "fft_freq와 "
            "fft_amp의 길이가 다릅니다."
        )


    # --------------------------------------------------------
    # 형번·제조사 문자열 정리
    # --------------------------------------------------------

    master = master_df.copy()


    master["Number"] = (
        master["Number"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


    master["Maker"] = (
        master["Maker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


    number = (
        str(bearing_number)
        .strip()
        .upper()
    )


    maker = (
        str(maker)
        .strip()
        .upper()
    )


    matched = master[
        (
            master["Number"]
            == number
        )
        &
        (
            master["Maker"]
            == maker
        )
    ]


    if matched.empty:

        raise ValueError(
            "마스터 파일에서 "
            "베어링을 찾을 수 없습니다: "
            f"{maker} "
            f"{bearing_number}"
        )


    bearing = matched.iloc[0]


    # 회전주파수
    shaft_freq = round(
        rpm / 60.0,
        2
    )


    # --------------------------------------------------------
    # FFT 주파수 분해능 기반 허용오차
    # --------------------------------------------------------

    resolution = np.median(
        np.diff(freq)
    )


    if tolerance is None:

        tolerance = round(
            float(
                max(
                    resolution * 1.5,
                    shaft_freq * 0.03
                )
            ),
            2
        )


    # --------------------------------------------------------
    # 목표 주파수 부근 최대 Peak 검색
    # --------------------------------------------------------

    def find_peak(
        target_freq
    ):

        mask = (
            np.abs(
                freq - target_freq
            )
            <= tolerance
        )


        if not np.any(mask):

            return (
                np.nan,
                0.0
            )


        indices = np.where(
            mask
        )[0]


        peak_idx = indices[
            np.argmax(
                amp[indices]
            )
        ]


        return (
            freq[peak_idx],
            amp[peak_idx]
        )


    # --------------------------------------------------------
    # 진단 대상
    # --------------------------------------------------------

    fault_orders = [
        "BPFO",
        "BPFI",
        "BSF",
        "FTF"
    ]


    result = []


    # --------------------------------------------------------
    # 각 베어링 결함 계산
    # --------------------------------------------------------

    for fault_name in fault_orders:


        order = pd.to_numeric(
            bearing[fault_name],
            errors="coerce"
        )


        if pd.isna(order):
            continue


        # 결함 기본주파수
        #
        # 결함 Order × 회전주파수

        base_freq = round(
            float(order)
            * shaft_freq,
            2
        )


        harmonic_result = []


        weighted_score = 0.0


        # ----------------------------------------------------
        # Harmonic 검색
        # ----------------------------------------------------

        for h in range(
            1,
            harmonics + 1
        ):


            target_freq = (
                base_freq * h
            )


            detected_freq, detected_amp = (
                find_peak(
                    target_freq
                )
            )


            # 기본 주파수에 더 높은 가중치 적용
            weight = (
                1.0 / h
            )


            weighted_score += (
                detected_amp
                * weight
            )


            harmonic_result.append({

                "배수":
                    h,

                "목표주파수_Hz":
                    target_freq,

                "검출주파수_Hz":
                    round(
                        float(
                            detected_freq
                        ),
                        2
                    ),

                "진폭":
                    round(
                        float(
                            detected_amp
                        ),
                        2
                    )
            })


        # ----------------------------------------------------
        # 1X Sideband 진폭 추가 반영
        # ----------------------------------------------------

        sideband_score = 0.0


        if use_sideband:


            for h in range(
                1,
                harmonics + 1
            ):


                for sign in [
                    -1,
                    1
                ]:


                    sideband_freq = (
                        base_freq * h
                        +
                        sign * shaft_freq
                    )


                    if sideband_freq > 0:


                        _, sideband_amp = (
                            find_peak(
                                sideband_freq
                            )
                        )


                        sideband_score += (
                            sideband_amp
                            * 0.25
                        )


        result.append({

            "결함유형":
                fault_name,

            "결함계수_Order":
                float(order),

            "기준주파수_Hz":
                base_freq,

            "점수":
                round(
                    weighted_score
                    +
                    sideband_score,
                    2
                ),

            "고조파정보":
                harmonic_result
        })


    # --------------------------------------------------------
    # 결과 DataFrame
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        result
    )


    if result_df.empty:

        return (
            None,
            result_df
        )


    # --------------------------------------------------------
    # 점수 정규화
    # --------------------------------------------------------

    max_score = (
        result_df[
            "점수"
        ].max()
    )


    result_df[
        "상대점수"
    ] = round(

        result_df[
            "점수"
        ] / max_score

        if max_score > 0

        else 0,

        2
    )


    result_df = (
        result_df
        .sort_values(
            "점수",
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )


    # --------------------------------------------------------
    # 1위와 2위 Score 차이
    # --------------------------------------------------------

    if len(result_df) >= 2:


        dominance = (

            result_df.loc[
                0,
                "점수"
            ]

            /

            (
                result_df.loc[
                    1,
                    "점수"
                ]
                +
                1e-12
            )
        )


    else:

        dominance = np.inf


    # --------------------------------------------------------
    # 최종 Diagnosis
    # --------------------------------------------------------

    if (
        result_df.loc[
            0,
            "점수"
        ]
        == 0
    ):


        diagnosis = (
            "판정불가: "
            "결함주파수 주변에 "
            "유의한 피크 없음"
        )


    elif dominance >= 1.5:


        diagnosis = (

            f"{result_df.loc[0, '결함유형']} "
            "가능성 높음"
        )


    else:


        diagnosis = (
            "복합 결함 또는 "
            "판정 불확실"
        )


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = {

        "제조사":
            maker,

        "베어링형번":
            bearing_number,

        "RPM":
            rpm,

        "회전주파수_Hz":
            shaft_freq,

        "허용오차_Hz":
            tolerance,

        "판정":
            diagnosis,

        "지배비율":
            round(
                float(
                    dominance
                ),
                2
            )
    }


    return (
        summary,
        result_df
    )


# ============================================================
# Bearing Fault Frequency Master
# ============================================================

master_df = pd.read_csv(

    os.path.join(
        "Bearing_Fault_Frequency_Master_File",
        "Bearing_Fault_Frequency_Master_File.txt"
    ),

    sep="\t"
)


# 6315 확인
print(
    master_df[
        master_df.Number
        == "6315"
    ]
)


# ============================================================
# 지배비율 기준
# ============================================================

# 지배비율 = 1위 점수 ÷ 2위 점수
#
# 1.0 ~ 1.2
#   두 결함 유형 점수가 비슷함
#   → 복합 결함 또는 판정 불확실
#
# 1.2 ~ 1.5
#   특정 결함이 약간 우세
#   → 참고 수준
#
# 1.5 이상
#   1위 결함 패턴이 2위보다 뚜렷함
#   → 해당 결함 가능성 높음
#
# 2.0 이상
#   지배적인 결함 패턴
#   → 상대적으로 신뢰도 높음


# ============================================================
# 베어링 진단 실행
# ============================================================

summary, result_df = (
    diagnose_bearing_fault(

        fft_freq=fft_freq,

        fft_amp=fft_amp,

        rpm=1750,

        bearing_number="6315",

        maker="SKF",

        master_df=master_df,

        tolerance=5,

        harmonics=3,

        use_sideband=True
    )
)


print(
    summary
)

print(
    result_df
)


# 각 결함 Harmonic 확인

print(
    result_df[
        "고조파정보"
    ].iloc[0]
)

print(
    result_df[
        "고조파정보"
    ].iloc[1]
)

print(
    result_df[
        "고조파정보"
    ].iloc[2]
)

print(
    result_df[
        "고조파정보"
    ].iloc[3]
)


# ============================================================
# 지배적인 베어링 결함 Plot
# ============================================================

dominant = (
    result_df
    .sort_values(
        by="점수",
        ascending=False
    )
    .iloc[0]
)


fault_type = (
    dominant[
        "결함유형"
    ]
)

fault_order = (
    dominant[
        "결함계수_Order"
    ]
)

fault_score = (
    dominant[
        "점수"
    ]
)

relative_score = (
    dominant[
        "상대점수"
    ]
)


fault_colors = {

    "BPFI":
        "red",

    "BPFO":
        "blue",

    "BSF":
        "green",

    "FTF":
        "purple"
}


color = (
    fault_colors
    .get(
        fault_type,
        "orange"
    )
)


plt.figure(
    figsize=(14, 5)
)


plt.plot(
    fft_freq,
    fft_amp,
    color="black",
    linewidth=1,
    label="FFT"
)


y_max = np.max(
    fft_amp
)


x_max = min(
    MeasureFreq,
    np.max(
        fft_freq
    )
)


# ------------------------------------------------------------
# 지배 결함의 Harmonic만 표시
# ------------------------------------------------------------

for harmonic in (
    dominant[
        "고조파정보"
    ]
):


    order = (
        harmonic[
            "배수"
        ]
    )


    target_freq = (
        harmonic[
            "목표주파수_Hz"
        ]
    )


    detected_freq = (
        harmonic[
            "검출주파수_Hz"
        ]
    )


    detected_amp = (
        harmonic[
            "진폭"
        ]
    )


    if (
        target_freq > x_max
        or
        np.isnan(
            detected_freq
        )
    ):

        continue


    # 목표 결함주파수
    plt.axvline(

        target_freq,

        color=color,

        linestyle="--",

        linewidth=1,

        alpha=0.4
    )


    # 실제 검출 Peak
    plt.axvline(

        detected_freq,

        color=color,

        linestyle="-",

        linewidth=1.5,

        alpha=0.6
    )


    plt.text(

        detected_freq,

        y_max * (
            0.95
            -
            0.15
            *
            (
                (order - 1)
                % 3
            )
        ),

        f"{fault_type} {order}X\n"
        f"{detected_freq:.2f} Hz\n"
        f"Amp: {detected_amp:.3f}",

        rotation=90,

        color=color,

        ha="right",

        va="top",

        fontsize=10,

        fontweight="bold"
    )


# ------------------------------------------------------------
# 회전주파수 1X 표시
# ------------------------------------------------------------

shaft_freq = (
    summary[
        "회전주파수_Hz"
    ]
)


plt.axvline(

    shaft_freq,

    color="gray",

    linestyle=":",

    linewidth=1,

    alpha=0.8,

    label=(
        f"Rotation 1X "
        f"({shaft_freq:.2f} Hz)"
    )
)


plt.xlim(
    0,
    x_max
)


plt.ylim(
    0,
    y_max * 1.15
)


plt.xlabel(
    "Frequency (Hz)"
)


plt.ylabel(
    "Amplitude"
)


plt.title(

    f"Dominant Bearing Fault: "
    f"{fault_type} | "

    f"{summary['제조사']} "
    f"{summary['베어링형번']} | "

    f"Order: "
    f"{fault_order:.2f} | "

    f"Score: "
    f"{fault_score:.2f} | "

    f"Relative Score: "
    f"{relative_score:.2f}"
)


plt.grid(
    True,
    alpha=0.3
)

plt.legend()

plt.tight_layout()

plt.show()


# ============================================================
# 3. 베어링 추가 검증
# ============================================================

file = (
    'FFT 가열로_No.1 FCE '
    'Combustion Air Blower_'
    'Fan DS-V003 (V003).csv'
)


fft_data = pd.read_csv(
    os.path.join(
        path,
        file
    )
)


target_list = fft_data[
    (
        fft_data.MeasureDate
        .str.startswith(
            "2026-04-14"
        )
    )
    &
    (
        fft_data.MeasureMode
        == 2
    )
]


print(
    target_list
)


fft_data_target = fft_data[
    fft_data.MeasureDate
    .str.startswith(
        "2026-04-14 09:31:21"
    )
]


print(
    fft_data_target
)


# ------------------------------------------------------------
# FFT 복원
# ------------------------------------------------------------

val = (
    fft_data_target
    .ResultData
    .iloc[0]
)


fft_amp = np.frombuffer(
    ast.literal_eval(val),
    dtype='<f4'
)


MeasureFreq = 500


fft_freq = np.linspace(
    0,
    MeasureFreq,
    len(fft_amp)
)


# ------------------------------------------------------------
# FFT Plot
# ------------------------------------------------------------

plt.figure(
    figsize=(14, 4)
)

plt.plot(
    fft_freq,
    fft_amp,
    label="FFT"
)

y_max = np.max(
    fft_amp
)

plt.xlim(
    0,
    MeasureFreq
)

plt.xlabel(
    "Frequency"
)

plt.ylabel(
    "Amplitude"
)

plt.title(
    "FFT"
)

plt.grid(True)

plt.tight_layout()

plt.show()


# ------------------------------------------------------------
# Bearing 진단
# ------------------------------------------------------------

summary, result_df = (
    diagnose_bearing_fault(

        fft_freq=fft_freq,

        fft_amp=fft_amp,

        rpm=1785,

        bearing_number="6322",

        maker="SKF",

        master_df=master_df,

        tolerance=5,

        harmonics=3,

        use_sideband=True
    )
)


print(
    summary
)

print(
    result_df
)


print(
    result_df[
        "고조파정보"
    ].iloc[0]
)

print(
    result_df[
        "고조파정보"
    ].iloc[1]
)

print(
    result_df[
        "고조파정보"
    ].iloc[2]
)

print(
    result_df[
        "고조파정보"
    ].iloc[3]
)


# ============================================================
# 추가 검증 Plot
# ============================================================

dominant = (
    result_df
    .sort_values(
        by="점수",
        ascending=False
    )
    .iloc[0]
)


fault_type = (
    dominant[
        "결함유형"
    ]
)

fault_order = (
    dominant[
        "결함계수_Order"
    ]
)

fault_score = (
    dominant[
        "점수"
    ]
)

relative_score = (
    dominant[
        "상대점수"
    ]
)


fault_colors = {

    "BPFI":
        "red",

    "BPFO":
        "blue",

    "BSF":
        "green",

    "FTF":
        "purple"
}


color = fault_colors.get(
    fault_type,
    "orange"
)


plt.figure(
    figsize=(14, 5)
)


plt.plot(
    fft_freq,
    fft_amp,
    color="black",
    linewidth=1,
    label="FFT"
)


y_max = np.max(
    fft_amp
)


x_max = min(
    MeasureFreq,
    np.max(
        fft_freq
    )
)


for harmonic in (
    dominant[
        "고조파정보"
    ]
):


    order = (
        harmonic[
            "배수"
        ]
    )


    target_freq = (
        harmonic[
            "목표주파수_Hz"
        ]
    )


    detected_freq = (
        harmonic[
            "검출주파수_Hz"
        ]
    )


    detected_amp = (
        harmonic[
            "진폭"
        ]
    )


    if (
        target_freq > x_max
        or
        np.isnan(
            detected_freq
        )
    ):
        continue


    plt.axvline(
        target_freq,
        color=color,
        linestyle="--",
        linewidth=1,
        alpha=0.4
    )


    plt.axvline(
        detected_freq,
        color=color,
        linestyle="-",
        linewidth=1.5,
        alpha=0.6
    )


    plt.text(

        detected_freq,

        y_max * (
            0.95
            -
            0.15
            *
            (
                (order - 1)
                % 3
            )
        ),

        f"{fault_type} {order}X\n"
        f"{detected_freq:.2f} Hz\n"
        f"Amp: {detected_amp:.3f}",

        rotation=90,

        color=color,

        ha="right",

        va="top",

        fontsize=10,

        fontweight="bold"
    )


shaft_freq = (
    summary[
        "회전주파수_Hz"
    ]
)


plt.axvline(

    shaft_freq,

    color="gray",

    linestyle=":",

    linewidth=1,

    alpha=0.8,

    label=(
        f"Rotation 1X "
        f"({shaft_freq:.2f} Hz)"
    )
)


plt.xlim(
    0,
    x_max
)

plt.ylim(
    0,
    y_max * 1.15
)

plt.xlabel(
    "Frequency (Hz)"
)

plt.ylabel(
    "Amplitude"
)

plt.title(

    f"Dominant Bearing Fault: "
    f"{fault_type} | "

    f"{summary['제조사']} "
    f"{summary['베어링형번']} | "

    f"Order: "
    f"{fault_order:.2f} | "

    f"Score: "
    f"{fault_score:.2f} | "

    f"Relative Score: "
    f"{relative_score:.2f}"
)

plt.grid(
    True,
    alpha=0.3
)

plt.legend()

plt.tight_layout()

plt.show()