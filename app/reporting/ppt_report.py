"""Programmatic one-slide diagnostic PPTX generation."""

from __future__ import annotations

import math
import re
import struct
from collections.abc import Mapping
from io import BytesIO
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from app.reporting.ppt_ai import PptDiagnosis


SLIDE_WIDTH = Inches(40 / 3)
SLIDE_HEIGHT = Inches(7.5)

FONT_NAME = "Malgun Gothic"
NAVY = RGBColor(15, 43, 54)
TEAL = RGBColor(18, 119, 126)
PALE_TEAL = RGBColor(224, 242, 241)
PALE_BLUE = RGBColor(234, 243, 246)
PANEL = RGBColor(248, 250, 251)
TEXT = RGBColor(27, 49, 59)
MUTED = RGBColor(92, 111, 119)
WHITE = RGBColor(255, 255, 255)
OUTLINE = RGBColor(205, 220, 224)


def build_diagnostic_ppt(
    report_context: Mapping[str, Any],
    diagnosis: PptDiagnosis,
    trend_png: bytes | None,
    fft_png: bytes | None,
) -> bytes:
    """Build one 16:9 diagnostic slide from compact evidence and chart PNGs."""
    presentation = Presentation()
    presentation.slide_width = SLIDE_WIDTH
    presentation.slide_height = SLIDE_HEIGHT
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    evidence = _evidence(report_context)
    equipment = _mapping(evidence.get("equipment"))
    trend = _mapping(evidence.get("trend"))
    fft = _mapping(evidence.get("fft"))

    equipment_name = _text(
        equipment.get("displayName") or equipment.get("name"),
        "설비명 미제공",
        70,
    )
    plant = _text(equipment.get("plant"), "공장 정보 미제공", 45)
    sensor_number = _text(
        equipment.get("sensorNumber") or equipment.get("sensor_number") or equipment.get("id"),
        "미제공",
        28,
    )
    risk_label = _risk_label(equipment)
    fft_label = _fft_label(fft)

    _add_panel(slide, 0, 0, SLIDE_WIDTH, Inches(1.04), NAVY)
    _add_panel(slide, 0, Inches(0.96), SLIDE_WIDTH, Inches(0.08), TEAL)
    _add_text(
        slide,
        equipment_name,
        Inches(0.4),
        Inches(0.16),
        Inches(7.5),
        Inches(0.34),
        20,
        WHITE,
        bold=True,
    )
    _add_text(
        slide,
        f"{plant} | SENSOR {sensor_number}",
        Inches(0.42),
        Inches(0.57),
        Inches(7.4),
        Inches(0.22),
        9.5,
        PALE_TEAL,
    )
    _add_badge(slide, f"위험도: {risk_label}", Inches(8.48), Inches(0.23), Inches(1.95))
    _add_badge(slide, f"FFT: {fft_label}", Inches(10.55), Inches(0.23), Inches(2.35))

    measured_at = _text(
        fft.get("measuredAt") or equipment.get("lastMeasuredAt"),
        "정보 없음",
        32,
    )
    metadata_items = [
        ("설비 코드", _text(equipment.get("id"), "정보 없음", 25)),
        ("측정 위치", _text(equipment.get("measurementPoint"), "정보 없음", 36)),
        ("회전수", _with_unit(equipment.get("rpm"), "rpm")),
        ("베어링", _text(equipment.get("bearing"), "정보 없음", 25)),
        ("측정 시각", measured_at),
    ]
    _add_metadata_grid(slide, metadata_items)

    _add_diagnosis_strip(slide, diagnosis)

    _add_analysis_panel(
        slide,
        title="Trend 분석",
        finding=diagnosis.trend_finding,
        png=trend_png,
        left=Inches(0.4),
        chart_label="Trend",
        context_available=bool(trend.get("available", True)),
    )
    _add_analysis_panel(
        slide,
        title="FFT 정밀 진단",
        finding=diagnosis.fft_finding,
        png=fft_png,
        left=Inches(6.8),
        chart_label="FFT",
        context_available=bool(fft.get("available", True)),
    )

    limitation = _text(
        " / ".join(diagnosis.limitations),
        "제공된 데이터 범위에서만 보조적으로 해석했습니다.",
        165,
    )
    _add_text(
        slide,
        f"AI 보조 분석 한계: {limitation}",
        Inches(0.42),
        Inches(7.1),
        Inches(12.45),
        Inches(0.19),
        7.5,
        MUTED,
    )

    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def diagnostic_ppt_filename_stem(report_context: Mapping[str, Any]) -> str:
    """Return an ASCII-safe filename stem for a generated diagnostic deck."""
    evidence = _evidence(report_context)
    equipment = _mapping(evidence.get("equipment"))
    fft = _mapping(evidence.get("fft"))
    equipment_id = _text(equipment.get("id"), "equipment", 48)
    safe_equipment_id = re.sub(r"[^A-Za-z0-9_-]+", "-", equipment_id).strip("-")
    safe_equipment_id = safe_equipment_id or "equipment"
    measured_at = _text(fft.get("measuredAt") or equipment.get("lastMeasuredAt"), "", 40)
    date_token = "".join(re.findall(r"\d", measured_at))[:8] or "report"
    return f"cms-diagnostic-{safe_equipment_id}-{date_token}"


def _evidence(report_context: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = report_context.get("evidence")
    return _mapping(evidence) if evidence is not None else report_context


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any, fallback: str, limit: int) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return fallback
    normalized = " ".join(str(value).split())
    if not normalized:
        return fallback
    return normalized if len(normalized) <= limit else f"{normalized[: max(limit - 3, 1)]}..."


def _with_unit(value: Any, unit: str) -> str:
    if isinstance(value, bool):
        return "정보 없음"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "정보 없음"
    if not math.isfinite(number):
        return "정보 없음"
    formatted = f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}".rstrip("0").rstrip(".")
    return f"{formatted} {unit}"


def _risk_label(equipment: Mapping[str, Any]) -> str:
    configured = _text(equipment.get("statusLabel"), "", 24)
    if configured:
        return configured
    return {
        "normal": "정상",
        "caution": "주의",
        "danger": "위험",
    }.get(str(equipment.get("status", "")).lower(), "미평가")


def _fft_label(fft: Mapping[str, Any]) -> str:
    measurement = _mapping(fft.get("measurement"))
    measure_mode = _mapping(measurement.get("measureMode"))
    diagnosis = _mapping(fft.get("diagnosis"))
    return _text(
        measure_mode.get("label") or diagnosis.get("label"),
        "정보 없음",
        24,
    )


def _add_panel(slide: Any, left: int, top: int, width: int, height: int, color: RGBColor) -> Any:
    panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    panel.fill.solid()
    panel.fill.fore_color.rgb = color
    panel.line.fill.background()
    return panel


def _add_text(
    slide: Any,
    value: str,
    left: int,
    top: int,
    width: int,
    height: int,
    font_size: float,
    color: RGBColor,
    bold: bool = False,
    alignment: PP_ALIGN = PP_ALIGN.LEFT,
) -> Any:
    text_box = slide.shapes.add_textbox(left, top, width, height)
    text_frame = text_box.text_frame
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    text_frame.margin_left = Inches(0.02)
    text_frame.margin_right = Inches(0.02)
    text_frame.margin_top = 0
    text_frame.margin_bottom = 0
    paragraph = text_frame.paragraphs[0]
    paragraph.alignment = alignment
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = value
    run.font.name = FONT_NAME
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    return text_box


def _add_badge(slide: Any, label: str, left: int, top: int, width: int) -> None:
    _add_panel(slide, left, top, width, Inches(0.34), TEAL)
    _add_text(
        slide,
        _text(label, "정보 없음", 32),
        left + Inches(0.03),
        top + Inches(0.02),
        width - Inches(0.06),
        Inches(0.28),
        8.5,
        WHITE,
        bold=True,
        alignment=PP_ALIGN.CENTER,
    )


def _add_metadata_grid(slide: Any, items: list[tuple[str, str]]) -> None:
    left = Inches(0.4)
    top = Inches(1.18)
    total_width = Inches(12.5)
    gap = Inches(0.06)
    cell_width = int((total_width - gap * (len(items) - 1)) / len(items))
    for index, (label, value) in enumerate(items):
        cell_left = left + index * (cell_width + gap)
        _add_panel(slide, cell_left, top, cell_width, Inches(0.64), PANEL)
        cell = slide.shapes[-1]
        cell.line.color.rgb = OUTLINE
        _add_text(slide, label, cell_left + Inches(0.08), top + Inches(0.07), cell_width - Inches(0.16), Inches(0.16), 7.5, MUTED)
        _add_text(
            slide,
            _text(value, "정보 없음", 34),
            cell_left + Inches(0.08),
            top + Inches(0.28),
            cell_width - Inches(0.16),
            Inches(0.24),
            10,
            TEXT,
            bold=True,
        )


def _add_diagnosis_strip(slide: Any, diagnosis: PptDiagnosis) -> None:
    top = Inches(1.98)
    _add_panel(slide, Inches(0.4), top, Inches(12.5), Inches(0.86), PALE_BLUE)
    _add_panel(slide, Inches(0.4), top, Inches(1.22), Inches(0.86), TEAL)
    _add_text(slide, "진단 결과", Inches(0.51), top + Inches(0.16), Inches(1.0), Inches(0.22), 11, WHITE, bold=True)
    _add_text(
        slide,
        _text(diagnosis.headline, "진단 요약 미제공", 78),
        Inches(1.83),
        top + Inches(0.09),
        Inches(7.1),
        Inches(0.28),
        13,
        TEXT,
        bold=True,
    )
    _add_text(
        slide,
        _text(diagnosis.conclusion, "제공된 근거를 추가 확인해야 합니다.", 106),
        Inches(1.83),
        top + Inches(0.43),
        Inches(7.1),
        Inches(0.28),
        8.5,
        MUTED,
    )
    _add_text(slide, "권장 조치", Inches(9.2), top + Inches(0.1), Inches(3.3), Inches(0.16), 7.5, MUTED, bold=True)
    _add_text(
        slide,
        _actions_text(diagnosis),
        Inches(9.2),
        top + Inches(0.33),
        Inches(3.28),
        Inches(0.34),
        8.5,
        TEXT,
    )


def _actions_text(diagnosis: PptDiagnosis) -> str:
    labels = {"immediate": "즉시", "high": "우선", "planned": "계획"}
    actions = [
        f"{labels[action.priority]}: {action.action}"
        for action in diagnosis.recommended_actions
    ]
    return _text(" / ".join(actions), "권장 조치 정보 없음", 118)


def _add_analysis_panel(
    slide: Any,
    title: str,
    finding: str,
    png: bytes | None,
    left: int,
    chart_label: str,
    context_available: bool,
) -> None:
    width = Inches(6.1)
    _add_panel(slide, left, Inches(3.05), width, Inches(0.23), NAVY)
    _add_text(slide, title, left + Inches(0.08), Inches(3.05), width - Inches(0.16), Inches(0.23), 10.5, WHITE, bold=True)
    finding_text = finding if context_available else "분석에 필요한 원본 정보가 충분하지 않습니다."
    _add_text(slide, _text(finding_text, "분석 결과 미제공", 145), left + Inches(0.03), Inches(3.37), width - Inches(0.06), Inches(0.5), 9, TEXT)
    _add_chart(slide, png, left, Inches(4.02), width, Inches(2.75), chart_label)


def _add_chart(
    slide: Any,
    png: bytes | None,
    left: int,
    top: int,
    width: int,
    height: int,
    label: str,
) -> None:
    _add_panel(slide, left, top, width, height, PANEL)
    chart_frame = slide.shapes[-1]
    chart_frame.line.color.rgb = OUTLINE
    dimensions = _png_dimensions(png)
    if dimensions is None:
        _add_chart_placeholder(slide, label, left, top, width, height)
        return
    image_width, image_height = dimensions
    scale = min(width / image_width, height / image_height)
    displayed_width = int(image_width * scale)
    displayed_height = int(image_height * scale)
    try:
        slide.shapes.add_picture(
            BytesIO(png),
            left + int((width - displayed_width) / 2),
            top + int((height - displayed_height) / 2),
            displayed_width,
            displayed_height,
        )
    except Exception:
        _add_chart_placeholder(slide, label, left, top, width, height)


def _png_dimensions(png: bytes | None) -> tuple[int, int] | None:
    if not isinstance(png, bytes) or len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", png[16:24])
    if width <= 0 or height <= 0:
        return None
    return width, height


def _add_chart_placeholder(slide: Any, label: str, left: int, top: int, width: int, height: int) -> None:
    _add_text(slide, f"{label} 그래프 미제공", left, top + Inches(1.03), width, Inches(0.28), 12, MUTED, bold=True, alignment=PP_ALIGN.CENTER)
    _add_text(
        slide,
        "캡처된 그래프가 제공되지 않았습니다.",
        left,
        top + Inches(1.35),
        width,
        Inches(0.2),
        8.5,
        MUTED,
        alignment=PP_ALIGN.CENTER,
    )