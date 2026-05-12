import asyncio
from collections.abc import Sequence

from business_agent import (
    AgentRequest,
    BusinessAgent,
    BusinessTool,
    RoleContext,
    RuntimeResult,
    TaskEvent,
    TaskStatus,
    ToolCallRecord,
    ToolRegistry,
    business_tool,
)


class FakeRuntime:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.seen_tools: list[str] = []

    async def ainvoke(
        self,
        request: AgentRequest,
        tools: Sequence[BusinessTool],
    ) -> RuntimeResult:
        self.seen_tools = [tool.name for tool in tools]
        if self.should_fail:
            raise ValueError("runtime exploded")
        return RuntimeResult(
            output=f"done: {request.input}",
            steps=[ToolCallRecord(tool_name="fake_tool", input={"value": 1}, output="ok")],
        )


def test_agent_returns_task_result_and_emits_completion_event() -> None:
    @business_tool(name="query_orders", allowed_roles=["sales_manager"])
    def query_orders() -> list[str]:
        return []

    events: list[TaskEvent] = []
    runtime = FakeRuntime()
    agent = BusinessAgent(
        tool_registry=ToolRegistry([query_orders]),
        runtime=runtime,
        on_complete=events.append,
    )

    async def run_agent() -> None:
        result = await agent.ainvoke(
            AgentRequest(
                input="summarize orders",
                role=RoleContext(role="sales_manager"),
                task_id="task-1",
            )
        )

        assert result.task_id == "task-1"
        assert result.status == TaskStatus.SUCCEEDED
        assert result.output == "done: summarize orders"
        assert result.steps[0].tool_name == "fake_tool"
        assert runtime.seen_tools == ["query_orders"]
        assert len(events) == 1
        assert events[0].status == TaskStatus.SUCCEEDED
        assert events[0].result is result

    asyncio.run(run_agent())


def test_agent_filters_tools_before_runtime() -> None:
    @business_tool(name="admin_tool", allowed_roles=["admin"])
    def admin_tool() -> str:
        return "admin"

    @business_tool(name="guest_tool", allowed_roles=["guest"])
    def guest_tool() -> str:
        return "guest"

    runtime = FakeRuntime()
    agent = BusinessAgent(
        tool_registry=ToolRegistry([admin_tool, guest_tool]),
        runtime=runtime,
    )

    async def run_agent() -> None:
        await agent.ainvoke(
            AgentRequest(
                input="hello",
                role=RoleContext(role="guest"),
            )
        )

        assert runtime.seen_tools == ["guest_tool"]

    asyncio.run(run_agent())


def test_agent_returns_failed_result_and_callback_on_runtime_error() -> None:
    events: list[TaskEvent] = []
    agent = BusinessAgent(
        runtime=FakeRuntime(should_fail=True),
        on_complete=events.append,
    )

    async def run_agent() -> None:
        result = await agent.ainvoke(
            AgentRequest(
                input="fail",
                role=RoleContext(role="admin"),
            )
        )

        assert result.status == TaskStatus.FAILED
        assert result.error == "runtime exploded"
        assert result.metadata["error_type"] == "ValueError"
        assert len(events) == 1
        assert events[0].status == TaskStatus.FAILED

    asyncio.run(run_agent())
