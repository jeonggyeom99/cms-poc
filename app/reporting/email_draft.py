"""Pure response presentation helpers for copy-only email drafts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.reporting.email_ai import EmailDraft, _EmailDraftModel


class EmailDraftResponse(_EmailDraftModel):
    status: Literal["ready"] = "ready"
    model: str = Field(min_length=1, max_length=160)
    draft: EmailDraft


def present_email_draft(draft: EmailDraft, model: str) -> EmailDraftResponse:
    """Wrap a generated draft in API-safe, data-only response metadata."""
    return EmailDraftResponse(model=model, draft=draft)