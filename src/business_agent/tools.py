from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from business_agent.roles import RoleContext


class ToolAccessError(PermissionError):
    """Raised when a role tries to call an invisible or unauthorized tool."""


@dataclass(frozen=True)
class BusinessTool:
    name: str
    description: str
    func: Callable[..., Any]
    allowed_roles: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def visible_to(self, role_context: RoleContext) -> bool:
        return role_context.matches_role(self.allowed_roles) and role_context.has_permissions(
            self.required_permissions
        )

    async def ainvoke(self, role_context: RoleContext, **kwargs: Any) -> Any:
        if not self.visible_to(role_context):
            raise ToolAccessError(
                f"Role {role_context.role!r} cannot access business tool {self.name!r}."
            )

        call_kwargs = self._inject_role_context(kwargs, role_context)
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**call_kwargs)

        result = await asyncio.to_thread(self.func, **call_kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _inject_role_context(
        self, kwargs: dict[str, Any], role_context: RoleContext
    ) -> dict[str, Any]:
        signature = inspect.signature(self.func)
        if "role_context" not in signature.parameters or "role_context" in kwargs:
            return kwargs
        return {**kwargs, "role_context": role_context}


class ToolRegistry:
    def __init__(self, tools: Iterable[BusinessTool | Callable[..., Any]] | None = None) -> None:
        self._tools: dict[str, BusinessTool] = {}
        for tool in tools or ():
            self.register(tool)

    def register(self, tool: BusinessTool | Callable[..., Any]) -> BusinessTool:
        business_tool_obj = ensure_business_tool(tool)
        self._tools[business_tool_obj.name] = business_tool_obj
        return business_tool_obj

    def get(self, name: str) -> BusinessTool:
        return self._tools[name]

    def all(self) -> list[BusinessTool]:
        return list(self._tools.values())

    def visible_tools_for(self, role_context: RoleContext) -> list[BusinessTool]:
        return [tool for tool in self._tools.values() if tool.visible_to(role_context)]


def ensure_business_tool(tool: BusinessTool | Callable[..., Any]) -> BusinessTool:
    if isinstance(tool, BusinessTool):
        return tool

    business_tool_obj = getattr(tool, "__business_tool__", None)
    if isinstance(business_tool_obj, BusinessTool):
        return business_tool_obj

    return BusinessTool(
        name=tool.__name__,
        description=inspect.getdoc(tool) or tool.__name__,
        func=tool,
    )


def business_tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    allowed_roles: Iterable[str] | None = None,
    required_permissions: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BusinessTool | Callable[[Callable[..., Any]], BusinessTool]:
    def decorator(inner: Callable[..., Any]) -> BusinessTool:
        return BusinessTool(
            name=name or inner.__name__,
            description=description or inspect.getdoc(inner) or inner.__name__,
            func=inner,
            allowed_roles=tuple(allowed_roles or ()),
            required_permissions=tuple(required_permissions or ()),
            metadata=dict(metadata or {}),
        )

    if func is not None:
        return decorator(func)
    return decorator


ToolCallback = Callable[..., Any] | Callable[..., Awaitable[Any]]
