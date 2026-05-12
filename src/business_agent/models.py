from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from business_agent.roles import RoleContext


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED}


@dataclass(frozen=True)
class AgentRequest:
    input: str
    role: RoleContext
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_task_id(self) -> str:
        return self.task_id or str(uuid4())


@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    input: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "input": dict(self.input),
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: TaskStatus
    input: str
    role: RoleContext
    output: Any = None
    error: str | None = None
    steps: list[ToolCallRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == TaskStatus.SUCCEEDED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "input": self.input,
            "role": self.role.to_dict(),
            "output": self.output,
            "error": self.error,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": dict(self.metadata),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    status: TaskStatus
    role: RoleContext
    result: TaskResult
    occurred_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "role": self.role.to_dict(),
            "result": self.result.to_dict(),
            "occurred_at": self.occurred_at.isoformat(),
        }
