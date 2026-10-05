"""Bounded, editable regions for a single diagnostic slide (in inches)."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


SLIDE_WIDTH = 13 + 1 / 3
SLIDE_HEIGHT = 7.5
SAFE_MARGIN = 0.25


class PptRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=SAFE_MARGIN, allow_inf_nan=False)
    y: float = Field(ge=SAFE_MARGIN, allow_inf_nan=False)
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    font_size: float = Field(ge=10, le=28, allow_inf_nan=False)

    @model_validator(mode="after")
    def inside_slide(self):
        if self.x + self.width > SLIDE_WIDTH - SAFE_MARGIN + 1e-6:
            raise ValueError("PPT 영역이 슬라이드 가로 안전 경계를 벗어났습니다.")
        if self.y + self.height > SLIDE_HEIGHT - SAFE_MARGIN + 1e-6:
            raise ValueError("PPT 영역이 슬라이드 세로 안전 경계를 벗어났습니다.")
        return self


class PptLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: PptRegion
    metadata: PptRegion
    trend_text: PptRegion
    fft_text: PptRegion
    trend_chart: PptRegion
    fft_chart: PptRegion

    @model_validator(mode="after")
    def usable_regions(self):
        for name in ("trend_chart", "fft_chart"):
            region = getattr(self, name)
            if region.width < 2 or region.height < 1:
                raise ValueError("그래프 영역은 최소 2 x 1 inch여야 합니다.")
        for name in ("title", "metadata", "trend_text", "fft_text"):
            if getattr(self, name).width < 2:
                raise ValueError("텍스트 영역 너비는 최소 2 inch여야 합니다.")
        if self.metadata.height < 1:
            raise ValueError("설비 표 높이는 최소 1 inch여야 합니다.")
        for name in ("trend_text", "fft_text", "trend_chart", "fft_chart"):
            region = getattr(self, name)
            if (region.x < SAFE_MARGIN + 0.1 or region.y < SAFE_MARGIN + 0.4
                    or region.x + region.width > SLIDE_WIDTH - SAFE_MARGIN - 0.1 + 1e-6
                    or region.y + region.height > SLIDE_HEIGHT - SAFE_MARGIN - 0.1 + 1e-6):
                raise ValueError("설명·그래프를 둘러싼 표의 안전 여백을 확보해야 합니다.")
        return self


def default_ppt_layout() -> PptLayout:
    return PptLayout.model_validate({
        "title": dict(x=0.5, y=0.25, width=12.33, height=0.55, font_size=26),
        "metadata": dict(x=0.5, y=0.95, width=12.33, height=2.15, font_size=11),
        "trend_text": dict(x=0.65, y=3.6, width=5.85, height=0.9, font_size=12),
        "fft_text": dict(x=6.85, y=3.6, width=5.85, height=0.9, font_size=12),
        "trend_chart": dict(x=0.65, y=4.6, width=5.85, height=2.55, font_size=12),
        "fft_chart": dict(x=6.85, y=4.6, width=5.85, height=2.55, font_size=12),
    })
