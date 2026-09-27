"""Template-based one-slide CMS diagnostic PPTX generation."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

from app.reporting.ppt_ai import PptDiagnosis


TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "docs" / "ppt_result_sample.pptx"
FONT_NAME = "Malgun Gothic"
TITLE_COLOR = (15, 81, 127)
BODY_COLOR = (0, 0, 0)
ACTION_COLOR = (0, 0, 255)


def build_diagnostic_ppt(
    report_context: Mapping[str, Any],
    diagnosis: PptDiagnosis,
    trend_png: bytes | None,
    fft_png: bytes | None,
) -> bytes:
    """Fill the supplied single-slide template with current diagnostic evidence."""
    if not TEMPLATE_PATH.is_file():
        raise ValueError("진단 보고서 PPT 템플릿을 찾을 수 없습니다.")

    presentation = Presentation(TEMPLATE_PATH)
    if not presentation.slides:
        raise ValueError("진단 보고서 PPT 템플릿에 슬라이드가 없습니다.")

    _remove_extra_slides(presentation)
    slide = presentation.slides[0]
    evidence = _evidence(report_context)
    equipment = _mapping(evidence.get("equipment"))
    trend = _mapping(evidence.get("trend"))
    fft = _mapping(evidence.get("fft"))
    metrics = _metrics_by_key(trend)

    tables = [shape.table for shape in slide.shapes if getattr(shape, "has_table", False)]
    if len(tables) < 2:
        raise ValueError("진단 보고서 PPT 템플릿의 표 구성을 확인할 수 없습니다.")
    _, metadata_table = tables[:2]
    title = _find_title_shape(slide)
    trend_text, fft_text = _find_analysis_text_shapes(slide)
    picture_frames = _picture_frames(slide)
    if len(picture_frames) < 2:
        raise ValueError("진단 보고서 PPT 템플릿의 그래프 영역을 확인할 수 없습니다.")

    plant = _plain_text(equipment.get("plant"), 45)
    title_text = f"[{plant}] CMS Data 모니터링 및 진단결과" if plant else "CMS Data 모니터링 및 진단결과"
    _set_text(title, title_text, 27, TITLE_COLOR, bold=True)
    _fill_metadata_table(metadata_table, equipment, metrics, fft, diagnosis)
    _set_text(trend_text, _plain_text(diagnosis.trend_finding, 120), 12, BODY_COLOR, bold=True)
    _set_fft_panel_text(fft_text, diagnosis)

    _clear_template_annotations(slide, (title, trend_text, fft_text))
    _replace_chart_images(slide, picture_frames, trend_png, fft_png)

    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def diagnostic_ppt_filename_stem(report_context: Mapping[str, Any]) -> str:
    """Return an ASCII-safe filename stem for a generated diagnostic deck."""
    evidence = _evidence(report_context)
    equipment = _mapping(evidence.get("equipment"))
    fft = _mapping(evidence.get("fft"))
    equipment_id = _plain_text(equipment.get("id"), 48) or "equipment"
    safe_equipment_id = re.sub(r"[^A-Za-z0-9_-]+", "-", equipment_id).strip("-") or "equipment"
    measured_at = _plain_text(fft.get("measuredAt") or equipment.get("lastMeasuredAt"), 40)
    date_token = "".join(re.findall(r"\d", measured_at))[:8] or "report"
    return f"cms-diagnostic-{safe_equipment_id}-{date_token}"


def _remove_extra_slides(presentation: Presentation) -> None:
    while len(presentation.slides) > 1:
        slide_id = presentation.slides._sldIdLst[-1]
        presentation.part.drop_rel(slide_id.rId)
        del presentation.slides._sldIdLst[-1]


def _evidence(report_context: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = report_context.get("evidence")
    return _mapping(evidence) if evidence is not None else report_context


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _plain_text(value: Any, limit: int) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    normalized = " ".join(str(value).split())
    return normalized[:limit] if normalized else ""


def _format_number(value: Any, digits: int = 2) -> str:
    if isinstance(value, bool):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    if digits == 0:
        return f"{number:,.0f}"
    return f"{number:,.{digits}f}".rstrip("0").rstrip(".")


def _format_with_unit(value: Any, unit: str, digits: int = 2) -> str:
    formatted = _format_number(value, digits)
    return f"{formatted} {unit}" if formatted and unit else formatted


def _format_thresholds(metric: Mapping[str, Any]) -> str:
    warning = _format_number(metric.get("warningThreshold"))
    danger = _format_number(metric.get("dangerThreshold"))
    return f"{warning} / {danger}" if warning and danger else warning or danger


def _metrics_by_key(trend: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    metrics = trend.get("metrics")
    if not isinstance(metrics, list):
        return {}
    return {
        str(metric.get("key")): metric
        for metric in metrics
        if isinstance(metric, Mapping) and isinstance(metric.get("key"), str)
    }


def _find_title_shape(slide: Any) -> Any:
    candidates = [
        shape
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False) and not getattr(shape, "has_table", False)
    ]
    if not candidates:
        raise ValueError("진단 보고서 PPT 템플릿의 제목 영역을 확인할 수 없습니다.")
    return min(candidates, key=lambda shape: shape.top)


def _find_analysis_text_shapes(slide: Any) -> tuple[Any, Any]:
    candidates = [
        shape
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False)
        and not getattr(shape, "has_table", False)
        and shape.top > 2_000_000
    ]
    if len(candidates) < 2:
        raise ValueError("진단 보고서 PPT 템플릿의 분석 설명 영역을 확인할 수 없습니다.")
    candidates.sort(key=lambda shape: shape.left)
    return candidates[0], candidates[1]


def _picture_frames(slide: Any) -> list[tuple[int, int, int, int]]:
    frames = [
        (shape.left, shape.top, shape.width, shape.height)
        for shape in slide.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    return sorted(frames)


def _fill_metadata_table(
    table: Any,
    equipment: Mapping[str, Any],
    metrics: Mapping[str, Mapping[str, Any]],
    fft: Mapping[str, Any],
    diagnosis: PptDiagnosis,
) -> None:
    velocity = metrics.get("velocity", {})
    acceleration = metrics.get("accelerationAll", {})
    values = {
        (0, 1): _plain_text(equipment.get("plant"), 45),
        (0, 5): "",
        (0, 8): _format_report_timestamp(fft.get("measuredAt")),
        (0, 11): "",
        (1, 1): _plain_text(equipment.get("name") or equipment.get("displayName"), 80),
        (1, 8): "",
        (1, 11): _plain_text(equipment.get("sensorNumber") or equipment.get("sensor_number"), 24),
        (2, 2): _format_with_unit(equipment.get("rpm"), "RPM", 0),
        (2, 6): _plain_text(equipment.get("bearing"), 32),
        (2, 9): _format_thresholds(velocity),
        (2, 12): _format_thresholds(acceleration),
        (3, 1): _phenomenon_text(velocity, acceleration, diagnosis.trend_finding),
        (4, 1): _plain_text(diagnosis.headline, 150),
    }
    for (row, column), value in values.items():
        font_size = 10 if row == 4 else 11
        _set_table_cell_text(table.cell(row, column), value, font_size)


def _format_report_timestamp(value: Any) -> str:
    source = _plain_text(value, 40)
    if not source:
        return ""
    try:
        parsed = datetime.fromisoformat(source.replace("Z", "+00:00"))
    except ValueError:
        return source
    return f"’{parsed:%y}.{parsed.month}.{parsed.day} {parsed:%H:%M}"


def _phenomenon_text(
    velocity: Mapping[str, Any], acceleration: Mapping[str, Any], finding: str
) -> str:
    readings = [
        _format_with_unit(velocity.get("latestValue"), _plain_text(velocity.get("unit"), 12)),
        _format_with_unit(acceleration.get("latestValue"), _plain_text(acceleration.get("unit"), 12)),
    ]
    labels = ("속도", "가속도 ALL")
    current = ", ".join(
        f"{label} {reading}" for label, reading in zip(labels, readings, strict=True) if reading
    )
    return ". ".join(part for part in (current, _plain_text(finding, 150)) if part)


def _set_fft_panel_text(shape: Any, diagnosis: PptDiagnosis) -> None:
    text_frame = shape.text_frame
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    _add_paragraph(text_frame.paragraphs[0], _plain_text(diagnosis.fft_finding, 150), 12, BODY_COLOR, bold=True)
    action = next((item.action for item in diagnosis.recommended_actions if item.action), "")
    if action:
        _add_paragraph(text_frame.add_paragraph(), _plain_text(action, 100), 12, ACTION_COLOR)


def _set_text(shape: Any, value: str, size: float, color: tuple[int, int, int], bold: bool = False) -> None:
    text_frame = shape.text_frame
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    _add_paragraph(text_frame.paragraphs[0], value, size, color, bold)


def _set_table_cell_text(cell: Any, value: str, font_size: float) -> None:
    text_frame = cell.text_frame
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    _add_paragraph(text_frame.paragraphs[0], value, font_size, BODY_COLOR)


def _add_paragraph(paragraph: Any, value: str, size: float, color: tuple[int, int, int], bold: bool = False) -> None:
    paragraph.alignment = PP_ALIGN.LEFT
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = value
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*color)


def _clear_template_annotations(slide: Any, retained_text_shapes: tuple[Any, ...]) -> None:
    """Remove sample images and frequency callouts after preserving text and tables."""
    retained_elements = {id(shape._element) for shape in retained_text_shapes}
    for shape in list(slide.shapes):
        if getattr(shape, "has_table", False) or id(shape._element) in retained_elements:
            continue
        shape._element.getparent().remove(shape._element)


def _replace_chart_images(
    slide: Any,
    frames: list[tuple[int, int, int, int]],
    trend_png: bytes | None,
    fft_png: bytes | None,
) -> None:
    for frame, image in zip(frames[:2], (trend_png, fft_png), strict=True):
        if image:
            slide.shapes.add_picture(_fit_png_to_frame(image, frame[2], frame[3]), *frame)


def _fit_png_to_frame(image: bytes, width: int, height: int) -> BytesIO:
    """Center-crop a PNG to the template's fixed chart frame without distortion."""
    with Image.open(BytesIO(image)) as source:
        source = source.convert("RGB")
        source_ratio = source.width / source.height
        target_ratio = width / height
        if source_ratio > target_ratio:
            cropped_width = round(source.height * target_ratio)
            left = (source.width - cropped_width) // 2
            source = source.crop((left, 0, left + cropped_width, source.height))
        elif source_ratio < target_ratio:
            cropped_height = round(source.width / target_ratio)
            top = (source.height - cropped_height) // 2
            source = source.crop((0, top, source.width, top + cropped_height))
        output = BytesIO()
        source.save(output, format="PNG")
        output.seek(0)
        return output
