"""Shared structured AI gateway for feature-specific CMS reports."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Protocol, TypeVar, cast

from pydantic import BaseModel, ValidationError

from app.ai_analysis import (
    AiConfigurationError,
    AiProviderError,
    AiRateLimitError,
    AiResponseError,
    AiTimeoutError,
    OpenAISettings,
)


ReportModel = TypeVar("ReportModel", bound=BaseModel)


class ReportAiGateway(Protocol):
    """Generates one validated report-specific schema from compact evidence."""

    async def generate(
        self,
        report_kind: str,
        instructions: str,
        context: dict[str, Any],
        response_model: type[ReportModel],
    ) -> ReportModel:
        """Return an instance of the requested response model."""


class OpenAIReportGateway:
    """OpenAI implementation for bounded report-specific JSON responses."""

    def __init__(self, settings: OpenAISettings) -> None:
        self._settings = settings

    async def generate(
        self,
        report_kind: str,
        instructions: str,
        context: dict[str, Any],
        response_model: type[ReportModel],
    ) -> ReportModel:
        if not self._settings.api_key:
            raise AiConfigurationError()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self._settings.api_key,
            timeout=self._settings.timeout_seconds,
            max_retries=0,
        )
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                response = await client.chat.completions.create(
                    model=self._settings.model,
                    max_completion_tokens=1400,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": _schema_name(report_kind),
                            "strict": True,
                            "schema": response_model.model_json_schema(),
                        },
                    },
                    messages=[
                        {"role": "system", "content": instructions},
                        {
                            "role": "user",
                            "content": json.dumps(
                                context, ensure_ascii=False, separators=(",", ":")
                            ),
                        },
                    ],
                )
        except asyncio.TimeoutError as error:
            raise AiTimeoutError() from error
        except Exception as error:
            if type(error).__name__ == "RateLimitError":
                raise AiRateLimitError() from error
            raise AiProviderError() from error
        finally:
            await client.close()

        message = response.choices[0].message if response.choices else None
        content = message.content if message is not None else None
        if not content or getattr(message, "refusal", None):
            raise AiResponseError()
        try:
            return response_model.model_validate_json(content)
        except ValidationError as error:
            raise AiResponseError() from error


def _schema_name(report_kind: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]", "_", report_kind.lower())[:40]
    return f"cms_report_{normalized or 'response'}"


class ReportAiService:
    """Caches report responses by kind, prompt version, and evidence context."""

    def __init__(self, gateway: ReportAiGateway, model: str) -> None:
        self._gateway = gateway
        self._model = model
        self._cache: dict[str, BaseModel] = {}
        self._in_flight: dict[str, asyncio.Task[BaseModel]] = {}

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        report_kind: str,
        prompt_version: str,
        instructions: str,
        context: dict[str, Any],
        response_model: type[ReportModel],
        force: bool = False,
    ) -> ReportModel:
        cache_key = self._cache_key(report_kind, prompt_version, context)
        cached = self._cache.get(cache_key)
        if not force and cached is not None:
            return response_model.model_validate(cached.model_dump())

        task = self._in_flight.get(cache_key)
        if task is None:
            task = asyncio.create_task(
                self._run(report_kind, instructions, context, response_model, cache_key)
            )
            self._in_flight[cache_key] = task
        try:
            result = await task
            return cast(ReportModel, result)
        finally:
            if task.done() and self._in_flight.get(cache_key) is task:
                self._in_flight.pop(cache_key, None)

    def _cache_key(
        self, report_kind: str, prompt_version: str, context: Mapping[str, Any]
    ) -> str:
        serialized = json.dumps(
            {
                "reportKind": report_kind,
                "promptVersion": prompt_version,
                "context": context,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode()).hexdigest()

    async def _run(
        self,
        report_kind: str,
        instructions: str,
        context: dict[str, Any],
        response_model: type[ReportModel],
        cache_key: str,
    ) -> BaseModel:
        response = await self._gateway.generate(
            report_kind, instructions, context, response_model
        )
        if not isinstance(response, response_model):
            raise AiResponseError()
        self._cache[cache_key] = response
        return response
