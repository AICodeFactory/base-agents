from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from business_agent.models import AgentRequest, ToolCallRecord
from business_agent.tools import BusinessTool


@dataclass(frozen=True)
class RuntimeResult:
    output: Any
    steps: list[ToolCallRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRuntime(Protocol):
    async def ainvoke(
        self,
        request: AgentRequest,
        tools: Sequence[BusinessTool],
    ) -> RuntimeResult:
        """Run the agent request with tools visible to the current role."""


class DeepAgentsRuntime:
    """Default runtime adapter for DeepAgents/LangChain/LangGraph.

    The adapter imports framework dependencies lazily, so business tests can inject a fake runtime
    without requiring model credentials or starting a real LLM call.
    """

    def __init__(
        self,
        *,
        model: str | Any | None = None,
        instructions: str | None = None,
        agent_factory: Any | None = None,
        agent_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.instructions = instructions or (
            "You are a business-friendly agent. Respect role-based tool visibility and "
            "pass role context to business tools."
        )
        self.agent_factory = agent_factory
        self.agent_kwargs = dict(agent_kwargs or {})

    async def ainvoke(
        self,
        request: AgentRequest,
        tools: Sequence[BusinessTool],
    ) -> RuntimeResult:
        agent = self._create_agent(request, tools)
        payload = {"messages": [{"role": "user", "content": request.input}]}
        raw_result = await agent.ainvoke(payload)
        return RuntimeResult(
            output=self._extract_output(raw_result),
            metadata={"raw_result": raw_result},
        )

    def _create_agent(self, request: AgentRequest, tools: Sequence[BusinessTool]) -> Any:
        create_deep_agent = self.agent_factory or self._load_default_factory()
        langchain_tools = [
            self._to_langchain_tool(tool, request.role)
            for tool in tools
        ]
        kwargs = {
            "model": self.model,
            "tools": langchain_tools,
            "instructions": self.instructions,
            **self.agent_kwargs,
        }
        try:
            return create_deep_agent(**kwargs)
        except TypeError:
            kwargs["system_prompt"] = kwargs.pop("instructions")
            return create_deep_agent(**kwargs)

    @staticmethod
    def _load_default_factory() -> Any:
        try:
            from deepagents import create_deep_agent
        except ImportError as exc:  # pragma: no cover - covered by integration environments.
            raise RuntimeError(
                "DeepAgents is required for the default runtime. "
                "Install the package dependencies or inject a custom runtime."
            ) from exc
        return create_deep_agent

    @staticmethod
    def _to_langchain_tool(tool: BusinessTool, role_context: Any) -> Any:
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:  # pragma: no cover - covered by integration environments.
            raise RuntimeError(
                "langchain-core is required to adapt business tools for DeepAgents."
            ) from exc

        async def _run(**kwargs: Any) -> Any:
            return await tool.ainvoke(role_context, **kwargs)

        signature = inspect.signature(tool.func)
        public_parameters = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.name != "role_context"
        ]
        _run.__name__ = tool.name
        _run.__doc__ = tool.description
        _run.__annotations__ = {
            key: value
            for key, value in getattr(tool.func, "__annotations__", {}).items()
            if key != "role_context"
        }
        _run.__signature__ = signature.replace(parameters=public_parameters)  # type: ignore[attr-defined]
        return StructuredTool.from_function(
            coroutine=_run,
            name=tool.name,
            description=tool.description,
        )

    @staticmethod
    def _extract_output(raw_result: Any) -> Any:
        if not isinstance(raw_result, dict):
            return raw_result

        messages = raw_result.get("messages")
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            content = getattr(last_message, "content", None)
            if content is not None:
                return content
            if isinstance(last_message, dict) and "content" in last_message:
                return last_message["content"]

        for key in ("output", "final", "result"):
            if key in raw_result:
                return raw_result[key]
        return raw_result
