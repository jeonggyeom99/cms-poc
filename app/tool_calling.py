"""Shared, bounded OpenAI function-calling loop."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai_analysis import AiResponseError


MAX_TOOL_ROUNDS = 4
MAX_TOOL_CALLS = 8


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
) -> tuple[str, list[dict[str, Any]]]:
    """Run model-selected server tools and return final text plus an audit trace."""
    required = set(required_tools or ())
    executed: set[str] = set()
    trace: list[dict[str, Any]] = []
    calls_count = 0
    tool_rounds = 0

    for _ in range(MAX_TOOL_ROUNDS + 1):
        waiting_for_required = bool(required - executed) or (require_first_tool and not trace)
        tools_allowed = allow_additional_tools and tool_rounds < MAX_TOOL_ROUNDS
        if waiting_for_required and tool_rounds >= MAX_TOOL_ROUNDS:
            raise AiResponseError()
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
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
        message = response.choices[0].message if response.choices else None
        if message is None or getattr(message, "refusal", None):
            raise AiResponseError()

        calls = getattr(message, "tool_calls", None) or []
        if not calls:
            content = getattr(message, "content", None)
            if waiting_for_required or not content:
                raise AiResponseError()
            return content, trace

        calls_count += len(calls)
        if calls_count > MAX_TOOL_CALLS:
            raise AiResponseError()

        tool_rounds += 1
        messages.append(message)
        for call in calls:
            if getattr(call, "type", "function") != "function":
                raise AiResponseError()
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments)
            except (TypeError, ValueError) as error:
                raise AiResponseError() from error
            if not isinstance(arguments, dict):
                raise AiResponseError()
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

    raise AiResponseError()
