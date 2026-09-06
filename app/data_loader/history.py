from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any


HISTORY_FILE_NAME = "0. CMS history.csv"
HISTORY_YEAR = 2026
HISTORY_DATASET_IDS = {3: "1", 6: "3", 12: "4", 14: "5"}
HISTORY_COLUMNS = (
    "NO",
    "월",
    "일",
    "공정",
    "설비명",
    "센서번호",
    "현상 및 문제점",
    "분석 내용",
    "분석 결과",
    "FB 내용",
    "Trend 주요 인자",
    "Trend 파일명",
    "FFT 주요 인자",
    "FFT 파일명",
    "주요 인자",
    "알람 발생 이력",
    "모터 kW",
    "RPM",
    "베어링 형번",
    "결함",
    "유형",
)
FAULT_TYPES = {
    "베어링": {"BPFI", "BSF", "BPFO", "FTF", "Complex"},
    "축": {"Misalignment", "Unbalance", "Complex"},
}


def _required_integer(value: str, column: str, row_number: int) -> int:
    try:
        return int(value.strip())
    except ValueError as error:
        raise ValueError(
            f"CMS 이력 CSV {row_number}행의 {column} 값이 정수가 아닙니다."
        ) from error


def _optional_number(value: str, column: str, row_number: int) -> int | float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        number = float(stripped)
    except ValueError as error:
        raise ValueError(
            f"CMS 이력 CSV {row_number}행의 {column} 값이 숫자가 아닙니다."
        ) from error
    return int(number) if number.is_integer() else number


def _fault_fields(values: list[str], row_number: int) -> tuple[str, str]:
    fault = values[19]
    fault_type = values[20]
    if not fault or not fault_type:
        raise ValueError(f"CMS 이력 CSV {row_number}행의 결함과 유형 값은 필수입니다.")
    allowed_types = FAULT_TYPES.get(fault)
    if allowed_types is not None and fault_type not in allowed_types:
        raise ValueError(
            f"CMS 이력 CSV {row_number}행의 {fault} 유형은 허용된 값이 아닙니다."
        )
    return fault, fault_type


def _history_item(row: list[str], row_number: int) -> dict[str, Any]:
    values = [value.strip() for value in row]
    fault, fault_type = _fault_fields(values, row_number)
    record_number = _required_integer(values[0], "NO", row_number)
    month = _required_integer(values[1], "월", row_number)
    day = _required_integer(values[2], "일", row_number)
    try:
        measured_date = date(HISTORY_YEAR, month, day)
    except ValueError as error:
        raise ValueError(
            f"CMS 이력 CSV {row_number}행의 월/일 값이 유효하지 않습니다."
        ) from error

    return {
        "id": str(record_number),
        "datasetId": HISTORY_DATASET_IDS.get(record_number),
        "number": record_number,
        "date": measured_date.isoformat(),
        "process": values[3],
        "equipmentName": values[4].removeprefix("- "),
        "sensorNumber": values[5],
        "issue": values[6].removeprefix("- "),
        "analysis": values[7].removeprefix("- "),
        "result": values[8].removeprefix("- "),
        "feedback": values[9].removeprefix("- "),
        "trend": {"factor": values[10], "fileName": values[11]},
        "fft": {"factor": values[12], "fileName": values[13]},
        "primaryFactor": values[14],
        "alarmHistory": values[15],
        "motorKw": _optional_number(values[16], "모터 kW", row_number),
        "rpm": _optional_number(values[17], "RPM", row_number),
        "bearingModel": values[18],
        "fault": fault,
        "faultType": fault_type,
    }


def load_history(data_dir: Path) -> dict[str, Any]:
    history_path = data_dir / HISTORY_FILE_NAME
    if not history_path.is_file():
        raise FileNotFoundError(history_path)

    with history_path.open(encoding="utf-8-sig", newline="") as history_file:
        reader = csv.reader(history_file)
        try:
            columns = next(reader)
        except StopIteration as error:
            raise ValueError("CMS 이력 CSV가 비어 있습니다.") from error

        if tuple(columns) != HISTORY_COLUMNS:
            raise ValueError("CMS 이력 CSV 헤더가 예상한 21개 컬럼과 일치하지 않습니다.")

        items = []
        for row_number, row in enumerate(reader, start=2):
            if not any(value.strip() for value in row):
                continue
            if len(row) != len(HISTORY_COLUMNS):
                raise ValueError(
                    f"CMS 이력 CSV {row_number}행은 {len(HISTORY_COLUMNS)}개 컬럼이어야 합니다."
                )
            items.append(_history_item(row, row_number))

    return {
        "source": HISTORY_FILE_NAME,
        "total": len(items),
        "items": items,
    }
