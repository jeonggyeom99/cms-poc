"""CSV dataset loading and CMS analysis helpers.

This package preserves the former ``app.data_loader`` import surface while
separating configuration, CSV I/O, metadata transformation, and analysis.
"""

from .constants import (
    BASE_DIR,
    BEARING_FAULT_MASTER_PATH,
    BEARING_FAULT_TYPES,
    DATA_KIND_PATTERN,
    DATASET_NUMBER_PATTERN,
    DIAG_MODE_LABELS,
    EQUIPMENT_CODE_PATTERN,
    EQUIPMENT_METADATA_CONFIG_PATH,
    EXTRACTION_TYPE_LABELS,
    FFT_PEAK_SETTINGS,
    FREQUENCY_RANGES_HZ,
    INLINE_CODE_PATTERN,
    LEVEL_ANALYSIS_MONTHS,
    MEASURE_FREQ_LABELS,
    MEASURE_MODE_DEFINITIONS,
    TRAILING_CODE_PATTERN,
    TREND_METRIC_DEFINITIONS,
    TREND_MOVING_AVERAGE_POINTS,
    TREND_REGRESSION_POINTS,
    TREND_REQUIRED_POINTS,
    TREND_RISING_THRESHOLD,
)
from .csv_loader import (
    _classify_csv,
    _load_fft,
    _load_trend,
    _load_warning_status,
    load_fft_record,
)
from .datasets import (
    _dataset_sort_key,
    _load_equipment_metadata,
    dataset_summaries,
    load_datasets,
)
from .fft import (
    _build_fft_record,
    _decode_float32_bytes,
    _fft_record_summary,
    analyze_fft_diagnosis,
    analyze_fft_spectrum,
    analyze_acceleration_bearing_fft,
    analyze_velocity_fft,
)
from .bearing import lookup_bearing_coefficients
from .level import _linear_quantile, _subtract_months, analyze_velave_level
from .metadata import (
    _build_trend_metrics,
    _coded_value,
    _equipment_metadata,
    _fft_metadata,
)
from .numeric import _optional_finite_float
from .trend import _fill_low_outliers, analyze_velave_trend
from .history import HISTORY_COLUMNS, HISTORY_FILE_NAME, HISTORY_YEAR, load_history


__all__ = [
    "BASE_DIR",
    "BEARING_FAULT_MASTER_PATH",
    "BEARING_FAULT_TYPES",
    "DATA_KIND_PATTERN",
    "DATASET_NUMBER_PATTERN",
    "DIAG_MODE_LABELS",
    "EQUIPMENT_CODE_PATTERN",
    "EQUIPMENT_METADATA_CONFIG_PATH",
    "EXTRACTION_TYPE_LABELS",
    "FFT_PEAK_SETTINGS",
    "FREQUENCY_RANGES_HZ",
    "HISTORY_COLUMNS",
    "HISTORY_FILE_NAME",
    "HISTORY_YEAR",
    "INLINE_CODE_PATTERN",
    "LEVEL_ANALYSIS_MONTHS",
    "MEASURE_FREQ_LABELS",
    "MEASURE_MODE_DEFINITIONS",
    "TRAILING_CODE_PATTERN",
    "TREND_METRIC_DEFINITIONS",
    "TREND_MOVING_AVERAGE_POINTS",
    "TREND_REGRESSION_POINTS",
    "TREND_REQUIRED_POINTS",
    "TREND_RISING_THRESHOLD",
    "_build_fft_record",
    "_build_trend_metrics",
    "_classify_csv",
    "_coded_value",
    "_dataset_sort_key",
    "_decode_float32_bytes",
    "_equipment_metadata",
    "_fft_metadata",
    "_fft_record_summary",
    "_fill_low_outliers",
    "_linear_quantile",
    "_load_equipment_metadata",
    "_load_fft",
    "_load_trend",
    "_load_warning_status",
    "_optional_finite_float",
    "_subtract_months",
    "analyze_fft_diagnosis",
    "analyze_acceleration_bearing_fft",
    "analyze_fft_spectrum",
    "analyze_velave_level",
    "analyze_velave_trend",
    "analyze_velocity_fft",
    "dataset_summaries",
    "load_datasets",
    "load_fft_record",
    "load_history",
    "lookup_bearing_coefficients",
]
