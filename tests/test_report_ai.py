import asyncio
import json

from pydantic import BaseModel, ConfigDict

from app.reporting.ai import ReportAiService
from app.reporting.context import build_report_context


class SampleReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str


class CountingReportGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(
        self,
        report_kind: str,
        instructions: str,
        context: dict,
        response_model: type[SampleReport],
    ) -> SampleReport:
        self.calls.append(report_kind)
        return response_model(headline=f"{report_kind} report")


def test_report_ai_service_separates_caches_by_report_kind() -> None:
    async def run() -> tuple[list[str], str, str, str]:
        gateway = CountingReportGateway()
        service = ReportAiService(gateway, "test-model")
        context = {"evidence": {"equipment": {"id": "V001"}}}
        first = await service.generate("diagnostic-ppt", "v1", "prompt", context, SampleReport)
        cached = await service.generate("diagnostic-ppt", "v1", "prompt", context, SampleReport)
        email = await service.generate("email-draft", "v1", "prompt", context, SampleReport)
        return gateway.calls, first.headline, cached.headline, email.headline

    assert asyncio.run(run()) == (
        ["diagnostic-ppt", "email-draft"],
        "diagnostic-ppt report",
        "diagnostic-ppt report",
        "email-draft report",
    )


def test_report_context_contains_compact_evidence_only() -> None:
    context = build_report_context(
        "diagnostic-ppt",
        "1",
        {"equipment": {"id": "V001"}},
        {
            "recordId": 1,
            "frequencies": [1.0, 2.0],
            "amplitudes": [0.1, 0.2],
            "analysis": {},
        },
        [],
    )

    serialized = json.dumps(context)
    assert context["reportKind"] == "diagnostic-ppt"
    assert "frequencies" not in serialized
    assert "amplitudes" not in serialized