from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from business_agent.models import TaskEvent

CompletionCallback = Callable[[TaskEvent], Any | Awaitable[Any]]


@dataclass(frozen=True)
class CallbackFailure:
    callback_name: str
    error: BaseException


class CallbackError(RuntimeError):
    def __init__(self, failures: list[CallbackFailure]) -> None:
        self.failures = failures
        names = ", ".join(failure.callback_name for failure in failures)
        super().__init__(f"Completion callback failed: {names}")


async def emit_completion_callbacks(
    callbacks: CompletionCallback | Iterable[CompletionCallback] | None,
    event: TaskEvent,
) -> list[CallbackFailure]:
    failures: list[CallbackFailure] = []
    for callback in normalize_callbacks(callbacks):
        try:
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        except BaseException as exc:  # noqa: BLE001 - callback failures are reported to caller.
            failures.append(CallbackFailure(callback_name=callback_name(callback), error=exc))
    return failures


def normalize_callbacks(
    callbacks: CompletionCallback | Iterable[CompletionCallback] | None,
) -> tuple[CompletionCallback, ...]:
    if callbacks is None:
        return ()
    if callable(callbacks):
        return (callbacks,)
    return tuple(callbacks)


def callback_name(callback: CompletionCallback) -> str:
    return getattr(callback, "__name__", callback.__class__.__name__)
