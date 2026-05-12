import asyncio

from business_agent import AgentRequest, BusinessAgent, RoleContext, TaskEvent, business_tool
from business_agent.tools import ToolRegistry


@business_tool(
    name="query_orders",
    description="Query customer orders from the business system.",
    allowed_roles=["sales_manager", "customer_service"],
    required_permissions=["order:read"],
)
async def query_orders(customer_id: str, role_context: RoleContext) -> dict[str, object]:
    # The business system can do its own final permission check with role_context.
    return {
        "customer_id": customer_id,
        "tenant_id": role_context.tenant_id,
        "orders": [],
    }


async def persist_task_event(event: TaskEvent) -> None:
    # Replace this with your database, message queue, log platform, or task center.
    print("persist task event:", event.to_dict())


async def main() -> None:
    agent = BusinessAgent(
        model="gpt-4.1",
        tool_registry=ToolRegistry([query_orders]),
        on_complete=persist_task_event,
    )

    result = await agent.ainvoke(
        AgentRequest(
            input="帮我查询客户 c_001 最近 30 天的订单情况，并总结异常点",
            role=RoleContext(
                role="sales_manager",
                user_id="u_123",
                tenant_id="tenant_001",
                permissions=["order:read", "customer:read"],
            ),
        )
    )

    print(result.status)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
