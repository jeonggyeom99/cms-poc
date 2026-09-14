"""Small shared result contracts; public responses remain dictionary-compatible."""

from typing import Any, TypedDict


class AnalysisResult(TypedDict, total=False):
    status: str
    reason: str
    ruleId: str
    rulesetVersion: str
    Feature: dict[str, Any]
    Evidence: list[dict[str, Any]]
