import base64
import struct
import zlib

import pytest
from pydantic import ValidationError

from app.reporting.contracts import (
    DiagnosticPptRequest,
    PNG_DATA_URL_PREFIX,
    decode_png_data_url,
)


def tiny_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x1c\x91\xa8")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def png_data_url(payload: bytes | None = None) -> str:
    payload = tiny_png() if payload is None else payload
    return PNG_DATA_URL_PREFIX + base64.b64encode(payload).decode("ascii")


def test_diagnostic_ppt_request_accepts_camel_case_png_inputs() -> None:
    request = DiagnosticPptRequest.model_validate(
        {
            "recordId": 7,
            "selectedFaultType": "BPFO",
            "trendImageDataUrl": png_data_url(),
            "fftImageDataUrl": png_data_url(),
        }
    )

    assert request.record_id == 7
    assert request.selected_fault_type == "BPFO"
    assert decode_png_data_url(request.trend_image_data_url).startswith(b"\x89PNG")


@pytest.mark.parametrize(
    "value",
    [
        "data:image/jpeg;base64,ZmFrZQ==",
        PNG_DATA_URL_PREFIX + "not base64!",
        PNG_DATA_URL_PREFIX + base64.b64encode(b"not a png").decode("ascii"),
        PNG_DATA_URL_PREFIX + base64.b64encode(b"\x89PNG\r\n\x1a\nnot-valid").decode("ascii"),
    ],
)
def test_diagnostic_ppt_request_rejects_invalid_graph_capture(value: str) -> None:
    with pytest.raises(ValidationError):
        DiagnosticPptRequest.model_validate(
            {
                "recordId": 7,
                "trendImageDataUrl": value,
                "fftImageDataUrl": png_data_url(),
            }
        )