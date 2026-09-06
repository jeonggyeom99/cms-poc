"""Text-only AI email draft generation for maintenance communication."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.reporting.ai import ReportAiService


EMAIL_DRAFT_REPORT_KIND = "email-draft"
EMAIL_DRAFT_PROMPT_VERSION = "cms-email-draft-v1"


def _camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(word.capitalize() for word in rest)


class _EmailDraftModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel_case,
        populate_by_name=True,
        extra="forbid",
    )


class EmailDraftAction(_EmailDraftModel):
    priority: Literal["immediate", "high", "planned"]
    action: str = Field(min_length=1, max_length=240)


class EmailDraft(_EmailDraftModel):
    """Structured plain-text sections for a maintenance communication draft."""

    subject: str = Field(min_length=1, max_length=160)
    greeting: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=600)
    trend: str = Field(min_length=1, max_length=600)
    fft: str = Field(min_length=1, max_length=600)
    priority_actions: list[EmailDraftAction] = Field(min_length=1, max_length=4)
    limitations: list[str] = Field(min_length=1, max_length=4)
    closing: str = Field(min_length=1, max_length=240)


EMAIL_DRAFT_SYSTEM_PROMPT = """
당신은 설비 상태 근거를 정비 담당자가 빠르게 검토할 수 있도록 한국어 메일 초안으로 정리하는 유지보수 커뮤니케이션 작성자입니다.

제공된 compact evidence만 사용하십시오. evidence에 없는 수치, 원인, 상태, 추세, 조치 필요성을 사실처럼 추가하거나 추정하지 마십시오. RUL, MTBF 또는 잔여수명 추정은 절대 작성하지 마십시오. 최종 정비 판정, 교체 승인, 운전 중지 결정도 제시하지 마십시오.

모든 값은 평문으로 작성하십시오. HTML, Markdown, 태그, 표, 링크를 사용하지 마십시오. 각 문장은 간결하고 중립적으로 작성하며, 근거가 부족하면 limitations에 명확히 적으십시오.

반드시 다음 JSON 필드를 모두 채우십시오.
- subject: 설비와 관측 시점 또는 검토 목적을 담은 짧은 제목
- greeting: 짧고 일반적인 인사
- status: 현재 상태를 근거 범위 안에서 1~2문장으로 요약
- trend: Trend 근거 또는 Trend 데이터 한계를 1~2문장으로 요약
- fft: FFT 근거 또는 FFT 데이터 한계를 1~2문장으로 요약
- priorityActions: immediate, high, planned 중 하나의 priority와 짧은 action을 가진 1~4개 항목
- limitations: 데이터 한계 또는 추가 확인 필요 사항 1~4개
- closing: 검토 또는 확인을 요청하는 짧은 마무리
""".strip()


async def generate_email_draft(
    service: ReportAiService,
    context: dict[str, Any],
    force: bool = False,
) -> EmailDraft:
    """Generate one bounded, evidence-only maintenance communication draft."""
    return await service.generate(
        EMAIL_DRAFT_REPORT_KIND,
        EMAIL_DRAFT_PROMPT_VERSION,
        EMAIL_DRAFT_SYSTEM_PROMPT,
        context,
        EmailDraft,
        force=force,
    )