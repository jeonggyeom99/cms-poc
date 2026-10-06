"""Shared, bounded OpenAI function-calling loop."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai_analysis import AiResponseError


MAX_TOOL_ROUNDS = 4
MAX_TOOL_CALLS = 8
logger = logging.getLogger(__name__)


def workflow_timeout_seconds(per_call_timeout: float) -> float:
    """Budget for tool rounds, the final answer, and one diagnosis repair call."""
    return per_call_timeout * (MAX_TOOL_ROUNDS + 2)


async def complete_with_tools(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    execute: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    *,
    required_tools: set[str] | None = None,
    require_first_tool: bool = False,
    allow_additional_tools: bool = True,
    response_format: dict[str, Any] | None = None,
    max_completion_tokens: int = 1600,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    max_tool_calls: int = MAX_TOOL_CALLS,
    prioritize_required: bool = False,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run model-selected server tools and return final text plus an audit trace."""
    required = set(required_tools or ())
    executed: set[str] = set()
    trace: list[dict[str, Any]] = []
    calls_count = 0
    tool_rounds = 0
    diagnostics = diagnostics if diagnostics is not None else {}

    def fail(reason: str) -> None:
        diagnostics.update(tool_rounds=tool_rounds, tool_calls=calls_count,
                           missing_required=sorted(required - executed))
        raise AiResponseError(reason, trace=trace, diagnostics=dict(diagnostics))

    for _ in range(max_tool_rounds + 1):
        waiting_for_required = bool(required - executed) or (require_first_tool and not trace)
        tools_allowed = allow_additional_tools and tool_rounds < max_tool_rounds
        if waiting_for_required and tool_rounds >= max_tool_rounds:
            fail("required_tool_round_limit")
        offered_tools = tools
        missing = required - executed
        if prioritize_required and missing and max_tool_rounds - tool_rounds <= len(missing):
            offered_tools = [tool for tool in tools if tool["function"]["name"] in missing]
        diagnostics.update(tool_rounds=tool_rounds, tool_calls=calls_count,
                           missing_required=sorted(missing),
                           phase="tools" if waiting_for_required or tools_allowed else "final")
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": offered_tools,
            "tool_choice": "required" if waiting_for_required else ("auto" if tools_allowed else "none"),
            "parallel_tool_calls": False,
            "max_completion_tokens": max_completion_tokens,
        }
        # GPT-5.6 Luna requires reasoning_effort="none" when function tools
        # are used with Chat Completions.
        if model.startswith("gpt-5.6-"):
            params["reasoning_effort"] = "none"
        if response_format is not None and not waiting_for_required:
            params["response_format"] = response_format
        response = await client.chat.completions.create(**params)
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        diagnostics.update(finish_reason=finish_reason,
                           provider_request_id=getattr(response, "_request_id", None))
        message = response.choices[0].message if response.choices else None
        if message is None:
            fail("empty_response")
        if getattr(message, "refusal", None):
            fail("refusal")

        calls = getattr(message, "tool_calls", None) or []
        diagnostics["phase"] = "tools" if calls or waiting_for_required else "final"
        logger.info("AI completion request_id=%s model=%s phase=%s rounds=%s calls=%s finish=%s provider_request_id=%s",
                    diagnostics.get("request_id"), model, diagnostics["phase"], tool_rounds,
                    calls_count, finish_reason, diagnostics.get("provider_request_id"))
        if finish_reason == "length":
            fail("response_truncated")
        if not calls:
            content = getattr(message, "content", None)
            if waiting_for_required:
                fail("required_tools_missing")
            if not content:
                fail("empty_response")
            return content, trace

        calls_count += len(calls)
        if calls_count > max_tool_calls:
            fail("tool_call_limit")
        if not tools_allowed and not waiting_for_required:
            fail("unexpected_tool_call")

        tool_rounds += 1
        messages.append(message)
        for call in calls:
            if getattr(call, "type", "function") != "function":
                fail("invalid_tool_type")
            name = call.function.name
            if name not in {tool["function"]["name"] for tool in offered_tools}:
                fail("invalid_tool_name")
            try:
                arguments = json.loads(call.function.arguments)
            except (TypeError, ValueError):
                fail("invalid_tool_arguments")
            if not isinstance(arguments, dict):
                fail("invalid_tool_arguments")
            result = await execute(name, arguments)
            executed.add(name)
            trace.append({"name": name, "arguments": arguments, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                }
            )

    fail("tool_round_limit")
