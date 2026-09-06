import asyncio
import inspect
import json

from app.reporting.ai import ReportAiService
from app.reporting.context import build_report_context
from app.reporting.email_ai import (
    EMAIL_DRAFT_PROMPT_VERSION,
    EMAIL_DRAFT_REPORT_KIND,
    EMAIL_DRAFT_SYSTEM_PROMPT,
    EmailDraft,
    generate_email_draft,
)
from app.reporting.email_draft import EmailDraftResponse, present_email_draft


def draft_payload() -> dict:
    return {
        "subject": "V001 설비 상태 검토 요청",
        "greeting": "안녕하세요.",
        "status": "선택한 측정 기록의 상태 근거를 검토해 주세요.",
        "trend": "Trend 변화는 제공된 요약 범위에서 확인이 필요합니다.",
        "fft": "FFT 피크와 진단 요약을 함께 확인해 주세요.",
        "priorityActions": [
            {"priority": "high", "action": "다음 점검 시 동일 조건의 측정값을 비교해 주세요."}
        ],
        "limitations": ["제공된 근거만으로 원인을 확정할 수 없습니다."],
        "closing": "검토 후 필요한 확인 사항을 공유해 주세요.",
    }


class FakeEmailDraftGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, type[EmailDraft]]] = []

    async def generate(
        self,
        report_kind: str,
        instructions: str,
        context: dict,
        response_model: type[EmailDraft],
    ) -> EmailDraft:
        self.calls.append((report_kind, instructions, context, response_model))
        return response_model.model_validate(draft_payload())


def compact_email_context() -> dict:
    return build_report_context(
        EMAIL_DRAFT_REPORT_KIND,
        "1",
        {"equipment": {"id": "V001", "name": "Pump"}},
        {
            "recordId": 1,
            "frequencies": [1.0, 2.0, 3.0],
            "amplitudes": [0.1, 0.2, 0.3],
            "analysis": {},
        },
        [],
    )


def test_email_draft_schema_has_text_only_sections_and_presentation() -> None:
    draft = EmailDraft.model_validate(draft_payload())
    response = present_email_draft(draft, "fake-model")

    assert list(EmailDraft.model_fields) == [
        "subject",
        "greeting",
        "status",
        "trend",
        "fft",
        "priority_actions",
        "limitations",
        "closing",
    ]
    assert draft.model_dump(by_alias=True)["priorityActions"][0]["priority"] == "high"
    assert response == EmailDraftResponse(status="ready", model="fake-model", draft=draft)
    assert "html" not in json.dumps(EmailDraft.model_json_schema()).lower()


def test_generate_email_draft_uses_distinct_kind_and_isolates_cache() -> None:
    async def run() -> tuple[FakeEmailDraftGateway, EmailDraft, EmailDraft, EmailDraft]:
        gateway = FakeEmailDraftGateway()
        service = ReportAiService(gateway, "fake-model")
        context = compact_email_context()
        first = await generate_email_draft(service, context)
        cached = await generate_email_draft(service, context)
        alternate = await service.generate(
            "diagnostic-ppt",
            "cms-diagnostic-ppt-v1",
            "alternate prompt",
            context,
            EmailDraft,
        )
        return gateway, first, cached, alternate

    gateway, first, cached, alternate = asyncio.run(run())

    assert EMAIL_DRAFT_REPORT_KIND == "email-draft"
    assert EMAIL_DRAFT_PROMPT_VERSION != "cms-diagnostic-ppt-v1"
    assert [call[0] for call in gateway.calls] == ["email-draft", "diagnostic-ppt"]
    assert gateway.calls[0][1] == EMAIL_DRAFT_SYSTEM_PROMPT
    assert gateway.calls[0][3] is EmailDraft
    assert first == cached == alternate


def test_email_draft_context_uses_compact_evidence_without_raw_fft_arrays() -> None:
    context = compact_email_context()
    serialized = json.dumps(context)

    assert context["reportKind"] == EMAIL_DRAFT_REPORT_KIND
    assert "frequencies" not in serialized
    assert "amplitudes" not in serialized


def test_email_draft_contains_no_delivery_fields_or_configuration() -> None:
    field_names = set(EmailDraft.model_fields) | set(EmailDraftResponse.model_fields)
    source = inspect.getsource(__import__("app.reporting.email_ai", fromlist=["*"]))
    source += inspect.getsource(__import__("app.reporting.email_draft", fromlist=["*"]))

    assert field_names.isdisjoint({"to", "cc", "bcc", "recipient", "recipients"})
    assert "smtplib" not in source.lower()
    assert "smtp" not in source.lower()
    assert "recipient" not in source.lower()