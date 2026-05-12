from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from business_agent.callbacks import (
    CallbackError,
    CompletionCallback,
    emit_completion_callbacks,
)
from business_agent.models import AgentRequest, TaskEvent, TaskResult, TaskStatus, utc_now
from business_agent.runtime import AgentRuntime, DeepAgentsRuntime
from business_agent.tools import BusinessTool, ToolRegistry


class BusinessAgent:
    def __init__(
        self,
        *,
        model: str | Any | None = None,
        tool_registry: ToolRegistry | None = None,
        tools: Iterable[BusinessTool] | None = None,
        runtime: AgentRuntime | None = None,
        on_complete: CompletionCallback | Iterable[CompletionCallback] | None = None,
        raise_callback_errors: bool = False,
        runtime_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry(tools)
        self.runtime = runtime or DeepAgentsRuntime(model=model, **dict(runtime_kwargs or {}))
        self.on_complete = on_complete
        self.raise_callback_errors = raise_callback_errors

    async def ainvoke(self, request: AgentRequest) -> TaskResult:
        task_id = request.resolved_task_id()
        started_at = utc_now()
        visible_tools = self.tool_registry.visible_tools_for(request.role)

        try:
            runtime_result = await self.runtime.ainvoke(request, visible_tools)
        except asyncio.CancelledError:
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED,
                input=request.input,
                role=request.role,
                error="Task was cancelled.",
                metadata={
                    **request.metadata,
                    "visible_tools": [tool.name for tool in visible_tools],
                },
                started_at=started_at,
                finished_at=utc_now(),
            )
            await self._emit_complete(result)
            raise
        except Exception as exc:  # noqa: BLE001 - runtime failures are converted to TaskResult.
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                input=request.input,
                role=request.role,
                error=str(exc),
                metadata={
                    **request.metadata,
                    "error_type": exc.__class__.__name__,
                    "visible_tools": [tool.name for tool in visible_tools],
                },
                started_at=started_at,
                finished_at=utc_now(),
            )
            await self._emit_complete(result)
            return result

        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.SUCCEEDED,
            input=request.input,
            role=request.role,
            output=runtime_result.output,
            steps=runtime_result.steps,
            metadata={
                **request.metadata,
                **runtime_result.metadata,
                "visible_tools": [tool.name for tool in visible_tools],
            },
            started_at=started_at,
            finished_at=utc_now(),
        )
        await self._emit_complete(result)
        return result

    async def _emit_complete(self, result: TaskResult) -> None:
        event = TaskEvent(
            task_id=result.task_id,
            status=result.status,
            role=result.role,
            result=result,
        )
        failures = await emit_completion_callbacks(self.on_complete, event)
        if not failures:
            return

        result.metadata["callback_failures"] = [
            {"callback_name": failure.callback_name, "error": str(failure.error)}
            for failure in failures
        ]
        if self.raise_callback_errors:
            raise CallbackError(failures)
