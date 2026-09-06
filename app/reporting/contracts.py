"""Validated request contracts shared by CMS report endpoints."""

from __future__ import annotations

import base64
import binascii
from datetime import date
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_PNG_BYTES = 2_500_000
MAX_PNG_PIXELS = 8_000_000
PNG_DATA_URL_PREFIX = "data:image/png;base64,"
MAX_PNG_DATA_URL_LENGTH = len(PNG_DATA_URL_PREFIX) + ((MAX_PNG_BYTES + 2) // 3) * 4
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ReportRequest(BaseModel):
    """Selection state needed to build an evidence-only report context."""

    model_config = ConfigDict(
        alias_generator=_camel_case,
        populate_by_name=True,
        extra="forbid",
    )

    record_id: int = Field(gt=0)
    selected_fault_type: str | None = Field(default=None, max_length=32)
    until: date | None = None
    force: bool = False


def decode_png_data_url(value: str) -> bytes:
    """Decode one bounded PNG data URL received from the rendered dashboard."""
    if not value.startswith(PNG_DATA_URL_PREFIX):
        raise ValueError("그래프 이미지는 PNG data URL이어야 합니다.")

    encoded = value[len(PNG_DATA_URL_PREFIX) :]
    if not encoded or len(encoded) > MAX_PNG_DATA_URL_LENGTH - len(PNG_DATA_URL_PREFIX):
        raise ValueError("그래프 이미지 크기가 허용 범위를 초과했습니다.")

    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("그래프 이미지 형식이 올바르지 않습니다.") from error

    if len(image) > MAX_PNG_BYTES:
        raise ValueError("그래프 이미지 크기가 허용 범위를 초과했습니다.")
    if not image.startswith(PNG_SIGNATURE):
        raise ValueError("그래프 이미지는 PNG 형식이어야 합니다.")
    try:
        with Image.open(BytesIO(image)) as opened:
            if opened.format != "PNG":
                raise ValueError("그래프 이미지는 PNG 형식이어야 합니다.")
            width, height = opened.size
            if width * height > MAX_PNG_PIXELS:
                raise ValueError("그래프 이미지 해상도가 허용 범위를 초과했습니다.")
            opened.verify()
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
    ) as error:
        raise ValueError("그래프 이미지 형식이 올바르지 않습니다.") from error
    return image


class DiagnosticPptRequest(ReportRequest):
    """PPT-specific request including the currently rendered graph captures."""

    trend_image_data_url: str = Field(min_length=len(PNG_DATA_URL_PREFIX) + 1, max_length=MAX_PNG_DATA_URL_LENGTH)
    fft_image_data_url: str = Field(min_length=len(PNG_DATA_URL_PREFIX) + 1, max_length=MAX_PNG_DATA_URL_LENGTH)

    @field_validator("trend_image_data_url", "fft_image_data_url")
    @classmethod
    def validate_png_data_url(cls, value: str) -> str:
        decode_png_data_url(value)
        return value