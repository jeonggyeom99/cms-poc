import base64
import json
import struct
import zlib
from io import BytesIO
from typing import Any

from pptx import Presentation

from app.ai_analysis import OpenAISettings
from app.main import create_app
from app.reporting.ai import OpenAIReportGateway
from app.reporting.email_ai import EMAIL_DRAFT_REPORT_KIND, EmailDraft
from app.reporting.ppt_ai import PPT_REPORT_KIND, PptDiagnosis
from app.reporting.ppt_validation import PptReview
from tests.test_app import make_data_dir, post


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


def png_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(tiny_png()).decode("ascii")


class FakeReportGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def generate(
        self,
        report_kind: str,
        instructions: str,
        context: dict[str, Any],
        response_model: type[Any],
    ) -> Any:
        self.calls.append((report_kind, context))
        if response_model is PptDiagnosis:
            return PptDiagnosis(
                headline="Trend와 FFT 근거를 추가 확인해야 합니다.",
                conclusion="제공된 측정값과 현장 운전 조건을 함께 검토합니다.",
                trend_finding="Trend 변화는 제공된 측정 범위에서 확인이 필요합니다.",
                fft_finding="선택 FFT의 주요 Peak를 같은 운전 조건에서 재확인합니다.",
                recommended_actions=[],
                limitations=["현장 운전 조건 정보가 없습니다."],
            )
        if response_model is EmailDraft:
            return EmailDraft(
                subject="V001 CMS 진단 근거 검토 요청",
                greeting="안녕하세요.",
                status="선택한 CMS 측정 근거를 검토해 주세요.",
                trend="Trend 변화는 제공된 측정 범위에서 확인이 필요합니다.",
                fft="FFT Peak와 규칙 기반 진단 요약을 함께 확인해 주세요.",
                priority_actions=[{"priority": "high", "action": "동일 조건에서 재측정합니다."}],
                limitations=["현장 운전 조건 정보가 없습니다."],
                closing="검토 후 필요한 확인 사항을 공유해 주세요.",
            )
        raise AssertionError(f"Unexpected response model: {response_model}")


def test_email_draft_endpoint_uses_email_specific_compact_context(tmp_path) -> None:
    gateway = FakeReportGateway()
    response = post(
        create_app(make_data_dir(tmp_path), report_gateway=gateway),
        "/api/dashboard/1/email-draft",
        {"recordId": 2},
    )

    assert response.status_code == 200
    assert response.json()["draft"]["subject"] == "V001 CMS 진단 근거 검토 요청"
    assert gateway.calls[0][0] == EMAIL_DRAFT_REPORT_KIND
    assert "frequencies" not in json.dumps(gateway.calls[0][1])
    assert "amplitudes" not in json.dumps(gateway.calls[0][1])


def test_diagnostic_ppt_endpoint_returns_one_slide_download(tmp_path) -> None:
    gateway = FakeReportGateway()

    class PassingPptGateway:
        async def generate(self, report_kind, instructions, context, response_model):
            return PptReview(issues=[])

    async def render(presentation):
        return tiny_png()

    response = post(
        create_app(make_data_dir(tmp_path), report_gateway=gateway,
                   ppt_gateway=PassingPptGateway(), ppt_renderer=render),
        "/api/dashboard/1/diagnostic-ppt",
        {
            "recordId": 2,
            "trendImageDataUrl": png_data_url(),
            "fftImageDataUrl": png_data_url(),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert response.headers["content-disposition"].startswith("attachment; filename=\"cms-diagnostic-")
    assert len(Presentation(BytesIO(response.content)).slides) == 1
    assert gateway.calls[0][0] == PPT_REPORT_KIND
    assert "frequencies" not in json.dumps(gateway.calls[0][1])


def test_report_endpoints_validate_selection_captures_and_ai_configuration(tmp_path) -> None:
    target_app = create_app(make_data_dir(tmp_path), report_gateway=FakeReportGateway())
    missing_dataset = post(target_app, "/api/dashboard/99/email-draft", {"recordId": 2})
    invalid_capture = post(
        target_app,
        "/api/dashboard/1/diagnostic-ppt",
        {
            "recordId": 2,
            "trendImageDataUrl": "data:image/jpeg;base64,ZmFrZQ==",
            "fftImageDataUrl": png_data_url(),
        },
    )
    missing_key = post(
        create_app(
            make_data_dir(tmp_path),
            report_gateway=OpenAIReportGateway(
                OpenAISettings(api_key=None, model="test-model", timeout_seconds=1.0)
            ),
        ),
        "/api/dashboard/1/email-draft",
        {"recordId": 2},
    )

    assert missing_dataset.status_code == 404
    assert invalid_capture.status_code == 422
    assert missing_key.status_code == 503
    assert missing_key.json()["detail"]["code"] == "missing_api_key"
