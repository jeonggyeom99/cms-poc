from pathlib import Path
import re


BASE_DIR = Path(__file__).resolve().parent.parent
EQUIPMENT_RPM_CONFIG_PATH = BASE_DIR / "equipment_rpm.json"

DATASET_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.")
EQUIPMENT_CODE_PATTERN = re.compile(r"\b(V\d+)\b", re.IGNORECASE)
DATA_KIND_PATTERN = re.compile(r"^(?:FFT|Trend)[ _]*", re.IGNORECASE)
TRAILING_CODE_PATTERN = re.compile(r"\s+\(V\d+.*$", re.IGNORECASE)
INLINE_CODE_PATTERN = re.compile(r"-V\d+$", re.IGNORECASE)

FREQUENCY_RANGES_HZ = {
    "5": 500.0,
    "6": 1000.0,
    "9": 10000.0,
    "10": 20000.0,
}

EXTRACTION_TYPE_LABELS = {
    "2": "정기",
    "3": "주의경보",
    "4": "위험경보",
}

DIAG_MODE_LABELS = {
    "0": "없음",
    "1": "기구부",
    "2": "구름베어링",
    "11": "기어2",
    "12": "기어1",
}

MEASURE_MODE_DEFINITIONS = {
    "0": {"label": "가속도ALL", "amplitudeUnit": "g"},
    "2": {"label": "가속도ENV", "amplitudeUnit": "g"},
    "3": {"label": "속도", "amplitudeUnit": "mm/s"},
}

FFT_PEAK_SETTINGS = {
    "3": {"amplitudeThreshold": 0.5, "frequencyTolerance": 1.0},
    "0": {"amplitudeThreshold": 0.2, "frequencyTolerance": 5.0},
    "2": {"amplitudeThreshold": 0.2, "frequencyTolerance": 5.0},
}

FFT_ALERT_AMPLITUDE_THRESHOLD = 0.5
FFT_ALERT_EXTRACTION_TYPES = frozenset({"3", "4"})

MEASURE_FREQ_LABELS = {
    "5": "500 Hz",
    "6": "1 kHz",
    "9": "10 kHz",
    "10": "20 kHz",
}

TREND_MOVING_AVERAGE_POINTS = 72
TREND_REGRESSION_POINTS = 72
TREND_REQUIRED_POINTS = TREND_MOVING_AVERAGE_POINTS + TREND_REGRESSION_POINTS - 1
TREND_RISING_THRESHOLD = 1 / (24 * 14)
LEVEL_ANALYSIS_MONTHS = 3

TREND_METRIC_DEFINITIONS = (
    {
        "key": "accelerationAll",
        "pointKey": "acceleration",
        "column": "AccAllAve",
        "label": "가속도 ALL",
        "unit": "g",
        "thresholdPrefix": "ACCALL",
    },
    {
        "key": "accelerationBpf",
        "pointKey": "accelerationBpf",
        "column": "AccBpfAve",
        "label": "가속도 BPF",
        "unit": "g",
        "thresholdPrefix": "ACCBPF",
    },
    {
        "key": "accelerationPeak",
        "pointKey": "accelerationPeak",
        "column": "AccPeakAve",
        "label": "가속도 PEAK",
        "unit": "g",
        "thresholdPrefix": "ACCPEAK",
    },
    {
        "key": "velocity",
        "pointKey": "value",
        "column": "VelAve",
        "label": "속도",
        "unit": "mm/s",
        "thresholdPrefix": "VEL",
    },
)
