"""Single source of deterministic CMS thresholds (cms-poc-v1)."""

RULESET_VERSION = "cms-poc-v1"
TREND_MOVING_AVERAGE_POINTS = 72
TREND_REGRESSION_POINTS = 72
TREND_REQUIRED_POINTS = 143
TREND_RISING_THRESHOLD = 1 / (24 * 14)
LEVEL_ANALYSIS_MONTHS = 3
VELOCITY_FFT_TOLERANCE_HZ = 1.0
VELOCITY_FFT_MINIMUM_1X = 0.5
BEARING_FFT_TOLERANCE_HZ = 5.0
BEARING_FFT_SIGNIFICANT_AMPLITUDE = 0.5
FFT_PEAK_SETTINGS = {
    "3": {"amplitudeThreshold": 0.5, "frequencyTolerance": 1.0},
    "0": {"amplitudeThreshold": 0.2, "frequencyTolerance": 5.0},
    "2": {"amplitudeThreshold": 0.2, "frequencyTolerance": 5.0},
}
BEARING_FAULT_TYPES = ("BPFO", "BPFI", "BSF", "FTF")
